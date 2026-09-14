// ==UserScript==
// @name         Danske e-laskut PDF
// @namespace    danske-einvoice
// @version      5.5
// @description  Tallentaa Dansken vastaanotetut e-laskut
// @match        https://verkkopankki2.danskebank.fi/DNB/BetalingFI-EIListS-GenericNS*
// @grant        GM_registerMenuCommand
// @noframes
// ==/UserScript==

(function () {

    console.log("Danske e-laskut -skripti käynnistyi");

    function odota(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    function muunnaPaivamaara(pvm) {

        const osat = pvm.trim().split(".");

        if (osat.length !== 3) {
            return pvm.trim();
        }

        const paiva = osat[0].padStart(2, "0");
        const kuukausi = osat[1].padStart(2, "0");
        const vuosi = osat[2];

        return `${vuosi}-${kuukausi}-${paiva}`;
    }

    function muunnaSumma(summa) {

        return summa
            .trim()
            .replace(/\s/g, "")
            .replace(",", ".");
    }

    function siivoaTiedostonimi(nimi) {

        nimi = nimi.replace(/[\\/:*?"<>|]/g, "");
        nimi = nimi.replace(/\s+/g, " ").trim();

        return nimi;
    }

    function teeTiedostonimi(lasku) {

        const pvm = muunnaPaivamaara(lasku.erapaiva);
        const summa = muunnaSumma(lasku.summa);

        let nimi =
            pvm + " " +
            lasku.laskuttaja + " " +
            lasku.aihe;

        if (summa) {
            nimi += " " + summa;
        }

        return siivoaTiedostonimi(nimi);
    }

    function ohitaConfirm(frame) {

        try {

            const script =
                frame.document.createElement("script");

            script.textContent = `
                window.top.confirm = () => true;
            `;

            (
                frame.document.head ||
                frame.document.documentElement
            ).appendChild(script);

            script.remove();

        } catch (e) {

            console.log(
                "confirm-ohituksen asetus epäonnistui:",
                e
            );
        }
    }

    // ============================================================
    // HAE NYKYISEN SIVUN LASKUT
    // ============================================================

    function haeLaskut() {

        const frame = window.frames[2];

        if (!frame) {

            console.error("Frame 2 ei löytynyt.");

            return [];
        }

        const rivit =
            [...frame.document.querySelectorAll("tr")];

        const laskut = [];

        for (const tr of rivit) {

            /*
             * Etsitään EIR1VisLink nimenomaan tästä
             * samasta taulukon rivistä.
             */
            const linkki =
                [...tr.querySelectorAll("a")]
                    .find(a =>
                        a.href &&
                        a.href.includes("EIR1VisLink")
                    );

            if (!linkki) {
                continue;
            }

            const osuma =
                linkki.href.match(
                    /EIR1VisLink\('([^']+)'\)/
                );

            if (!osuma) {
                continue;
            }

            const parm = osuma[1];

            /*
             * XML-laskut on jo tallennettu
             * toisella Tampermonkey-skriptillä.
             */
            if (parm.startsWith("1")) {
                continue;
            }

            const cells =
                [...tr.querySelectorAll("td")];

            /*
             * Oikeassa laskurivissä pitää olla vähintään
             * nämä kuusi solua:
             *
             * 0 = päivämäärä
             * 2 = laskuttaja
             * 3 = aihe
             * 5 = summa
             */
            if (cells.length < 6) {

                console.log(
                    "Ohitetaan puutteellinen laskurivi:",
                    tr.innerText.trim()
                );

                continue;
            }

            const erapaiva =
                cells[0].innerText.trim();

            const laskuttaja =
                cells[2].innerText.trim();

            const aihe =
                cells[3].innerText.trim();

            const summa =
                cells[5].innerText.trim();

            /*
             * Päivämäärän pitää oikeasti näyttää
             * laskurivin päivämäärältä.
             *
             * Tämä estää ylimääräisten sivun tekstirivien
             * päätymisen laskuiksi.
             */
            if (!/^\d{1,2}\.\d{1,2}\.\d{4}$/.test(erapaiva)) {

                console.log(
                    "Ohitetaan rivi, jossa ei ole laskun päivämäärää:",
                    tr.innerText.trim()
                );

                continue;
            }

            if (!laskuttaja) {
                continue;
            }

            laskut.push({
                parm: parm,
                erapaiva: erapaiva,
                laskuttaja: laskuttaja,
                aihe: aihe,
                summa: summa
            });
        }

        return laskut;
    }

    // ============================================================
    // SELVITÄ SIVUNUMERO
    // ============================================================

    function haeSivunumero() {

        const frame = window.frames[2];

        if (!frame) {
            return null;
        }

        const teksti =
            frame.document.body?.innerText || "";

        const osuma =
            teksti.match(/Sivu\s+(\d+)\s*\/\s*(\d+)/i);

        if (!osuma) {

            console.log(
                "Sivunumeroa 'Sivu x / y' ei löytynyt."
            );

            return null;
        }

        return {
            nykyinen: parseInt(osuma[1], 10),
            yhteensa: parseInt(osuma[2], 10)
        };
    }

    // ============================================================
    // SIIRRY SEURAAVALLE SIVULLE
    // ============================================================

    async function siirrySeuraavalleSivulle() {

        const frame = window.frames[2];

        if (!frame) {
            return false;
        }

        const sivu =
            haeSivunumero();

        if (!sivu) {

            console.log(
                "Sivunumeroa ei voitu selvittää."
            );

            return false;
        }

        console.log(
            `Sivutus: nykyinen sivu ${sivu.nykyinen}/${sivu.yhteensa}`
        );

        /*
         * Jos ollaan jo viimeisellä sivulla,
         * ei ole enää mitään käsiteltävää.
         */
        if (sivu.nykyinen >= sivu.yhteensa) {

            console.log(
                `Viimeinen sivu ${sivu.nykyinen}/${sivu.yhteensa} saavutettu.`
            );

            return false;
        }

        const seuraavaNumero =
            String(sivu.nykyinen + 1);

        /*
         * Etsitään ensin numeroitu seuraavan sivun linkki.
         */
        let seuraava =
            [...frame.document.querySelectorAll(
                'a[href*="EIR1EIListLSkift"]'
            )]
            .find(a =>
                a.innerText.trim() === seuraavaNumero
            );

        /*
         * Jos numeroitua linkkiä ei löytynyt,
         * kokeillaan Dansken seuraava-sivun linkkiä.
         */
        if (!seuraava) {

            seuraava =
                [...frame.document.querySelectorAll(
                    'a[href*="EIR1EIListLNed"]'
                )][0];
        }

        if (!seuraava) {

            console.error(
                `Seuraavan sivun ${seuraavaNumero} linkkiä ei löytynyt.`
            );

            return false;
        }

        console.log(
            `Siirrytään sivulta ${sivu.nykyinen}/${sivu.yhteensa} ` +
            `sivulle ${seuraavaNumero}/${sivu.yhteensa}`
        );

        /*
         * Otetaan ensimmäisen laskun parm talteen.
         * Sen avulla voidaan havaita, että uusi sivu
         * on oikeasti latautunut.
         */
        const ennen =
            haeLaskut()[0]?.parm || "";

        try {

            seuraava.click();

        } catch (e) {

            console.error(
                "Seuraavalle sivulle siirtyminen epäonnistui:",
                e
            );

            return false;
        }

        /*
         * Odotetaan uuden sivun latautumista.
         */
        for (let i = 0; i < 40; i++) {

            await odota(250);

            const uusiSivu =
                haeSivunumero();

            const uusiEnsimmainen =
                haeLaskut()[0]?.parm || "";

            if (
                uusiSivu &&
                uusiSivu.nykyinen === sivu.nykyinen + 1 &&
                uusiEnsimmainen !== ennen
            ) {

                console.log(
                    `Uusi sivu ladattu: ` +
                    `${uusiSivu.nykyinen}/${uusiSivu.yhteensa}`
                );

                return true;
            }
        }

        /*
         * Jos ensimmäinen lasku sattuu olemaan sama,
         * tarkistetaan vielä pelkkä sivunumero.
         */
        const lopullinenSivu =
            haeSivunumero();

        if (
            lopullinenSivu &&
            lopullinenSivu.nykyinen === sivu.nykyinen + 1
        ) {

            console.log(
                `Uusi sivu ladattu sivunumeron perusteella: ` +
                `${lopullinenSivu.nykyinen}/${lopullinenSivu.yhteensa}`
            );

            return true;
        }

        console.error(
            "Seuraavalle sivulle siirtymistä ei voitu varmistaa."
        );

        return false;
    }

    // ============================================================
    // KÄSITTELE YKSI LASKU
    // ============================================================

    async function kasitteleLasku(lasku, numero, maara, sivuInfo) {

        const frame = window.frames[2];

        if (!frame) {
            return false;
        }

        ohitaConfirm(frame);

        await odota(100);

        const tiedostonimi =
            teeTiedostonimi(lasku);

        console.log(
            `Sivu ${sivuInfo}/${maara} – ` +
            `lasku ${numero}/${maara}:`,
            lasku.laskuttaja,
            lasku.summa
        );

        const linkit =
            [...frame.document.querySelectorAll("a")];

        const linkki =
            linkit.find(a =>
                a.href &&
                a.href.includes(
                    "EIR1VisLink('" +
                    lasku.parm +
                    "')"
                )
            );

        if (!linkki) {

            console.error(
                "Laskun linkkiä ei löytynyt:",
                lasku.parm
            );

            return false;
        }

        // -----------------------------------------
        // 1. AVAA LASKU
        // -----------------------------------------

        try {

            linkki.click();

        } catch (e) {

            console.error(
                "Laskun avaaminen epäonnistui:",
                e
            );

            return false;
        }

        await odota(1500);

        // -----------------------------------------
        // 2. AVAA AHK-HERÄTE
        // -----------------------------------------

        let herate = null;

        try {

            herate = window.open(
                "about:blank",
                "DANSKE_AHK_SAVE",
                "width=250,height=120"
            );

        } catch (e) {

            console.error(
                "Heräteikkunan avaaminen aiheutti virheen:",
                e
            );

            return false;
        }

        if (!herate || herate.closed) {

            console.error(
                "AHK-heräteikkunaa EI avattu."
            );

            alert(
                "AHK-heräteikkunan avaaminen epäonnistui.\n\n" +
                "Laskua ei jatketa."
            );

            return false;
        }

        // -----------------------------------------
        // 3. ASETETAAN HERÄTTEEN OTSIKKO
        // -----------------------------------------

        try {

            herate.document.title =
                "DANSKE_AHK_SAVE|" +
                tiedostonimi;

            herate.document.body.innerHTML =
                "<p style='font-family:sans-serif'>" +
                "Tallennetaan...<br>" +
                tiedostonimi +
                "</p>";

        } catch (e) {

            console.error(
                "Heräteikkunan valmistelu epäonnistui:",
                e
            );

            try {
                herate.close();
            } catch (_) {}

            return false;
        }

        console.log(
            "AHK-heräte avattu:",
            tiedostonimi
        );

        await odota(300);

        // -----------------------------------------
        // 4. ODOTA, ETTÄ AHK SULKEE HERÄTTEEN
        // -----------------------------------------

        await new Promise(resolve => {

            const tarkista =
                setInterval(() => {

                    if (herate.closed) {

                        clearInterval(tarkista);

                        resolve();
                    }

                }, 300);
        });

        /*
         * AHK on nyt tallentanut laskun ja sulkenut
         * sekä PDF- että heräteikkunan.
         */
        await odota(500);

        return true;
    }

    // ============================================================
    // TALLENNA KAIKKI SIVUT
    // ============================================================

    async function tallennaKaikki() {

        let onnistuneet = 0;
        let sivujaKasitelty = 0;

        while (true) {

            sivujaKasitelty++;

            const sivuInfo =
                haeSivunumero();

            let sivuTeksti = "?/?";

            if (sivuInfo) {

                sivuTeksti =
                    `${sivuInfo.nykyinen}/${sivuInfo.yhteensa}`;

                console.log(
                    "========================================"
                );

                console.log(
                    `SIVU ${sivuTeksti}`
                );

                console.log(
                    "========================================"
                );

            } else {

                console.log(
                    "========================================"
                );

                console.log(
                    "SIVUNUMEROA EI SAATU SELVILLE"
                );

                console.log(
                    "========================================"
                );
            }

            const laskut =
                haeLaskut();

            console.log(
                `Sivulla ${sivuTeksti} on ` +
                `${laskut.length} tallennettavaa laskua.`
            );

            // -----------------------------------------
            // TÄMÄN SIVUN LASKUT
            // -----------------------------------------

            for (let i = 0; i < laskut.length; i++) {

                console.log(
                    `Sivu ${sivuTeksti} – ` +
                    `lasku ${i + 1}/${laskut.length}:`,
                    laskut[i].laskuttaja,
                    laskut[i].summa
                );

                const onnistui =
                    await kasitteleLasku(
                        laskut[i],
                        i + 1,
                        laskut.length,
                        sivuTeksti
                    );

                if (!onnistui) {

                    alert(
                        "Laskujen tallennus keskeytettiin.\n\n" +
                        "Ongelma laskussa:\n" +
                        laskut[i].laskuttaja +
                        "\n" +
                        laskut[i].erapaiva +
                        "\n\n" +
                        "Tampermonkeyn mukaan onnistuneesti käsitelty: " +
                        onnistuneet
                    );

                    return;
                }

                onnistuneet++;
            }

            console.log(
                `Sivu ${sivuTeksti} käsitelty.`
            );

            // -----------------------------------------
            // SEURAAVA SIVU
            // -----------------------------------------

            const seuraava =
                await siirrySeuraavalleSivulle();

            if (!seuraava) {
                break;
            }

            console.log(
                "Seuraavan sivun käsittely alkaa."
            );
        }

        console.log(
            "========================================"
        );

        console.log(
            "KAIKKI SIVUT KÄSITELTY"
        );

        console.log(
            "Tallennettu yhteensä:",
            onnistuneet
        );

        console.log(
            "Sivuja käsitelty:",
            sivujaKasitelty
        );

        console.log(
            "========================================"
        );

        alert(
            "Tallennus valmis.\n\n" +
            "Tampermonkeyn mukaan tallennettu: " +
            onnistuneet +
            " e-laskua.\n\n" +
            "Käsiteltyjä sivuja: " +
            sivujaKasitelty
        );
    }

    // ============================================================
    // TAMPERMONKEY-VALIKKO
    // ============================================================

    GM_registerMenuCommand(
        "Tallenna kaikki muut e-laskut",
        tallennaKaikki
    );

})();
