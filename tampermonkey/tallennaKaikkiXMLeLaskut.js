// ==UserScript==
// @name         Danske e-laskut XML
// @namespace    danske-einvoice
// @version      14.3
// @description  Tallentaa kaikki Dansken vastaanotetut XML-e-laskut
// @match        https://verkkopankki2.danskebank.fi/DNB/BetalingFI-EIListS-GenericNS*
// @grant        GM_registerMenuCommand
// @noframes
// ==/UserScript==

"use strict";

function kaynnista() {

    console.log("========================================");
    console.log("DANSKE XML BULK 14.3");
    console.log("========================================");

    const BANK_ORIGIN = "https://verkkopankki.danskebank.fi";
    const LIST_ORIGIN = "https://verkkopankki2.danskebank.fi";


    // ------------------------------------------------------------
    // Apufunktiot
    // ------------------------------------------------------------

    function muunnaPaivamaara(pvm) {
        if (!pvm) {
            return "";
        }

        const osat = pvm.trim().split(".");

        if (osat.length !== 3) {
            return pvm.trim();
        }

        return (osat[2] + "-" + osat[1].padStart(2, "0") + "-" + osat[0].padStart(2, "0"));
    }


    function muunnaSumma(summa) {

        if (!summa) {
            return "";
        }

        return summa.trim().replace(/\s/g, "").replace(",", ".");
    }


    function siivoaTiedostonimi(nimi) {
        if (!nimi) {
            return "";
        }

        return nimi.replace(/[\\/:*?"<>|\x00-\x1F]/g, "_").replace(/\s+/g, " ").trim();
    }


    function teeTiedostonimi(lasku) {
        const pvm = muunnaPaivamaara(lasku.erapaiva);
        const summa = muunnaSumma(lasku.summa);

        let nimi = pvm + " - " + lasku.laskuttaja + " - " + lasku.aihe;

        if (summa) {
            nimi += " - " + summa;
        }

        nimi += " - .xml";
        return siivoaTiedostonimi(nimi);
    }


    // ------------------------------------------------------------
    // Lue XML-laskut nykyiseltä sivulta
    // ------------------------------------------------------------

    function haeLaskut(frame) {

        const laskut = [];

        const rivit = frame.document.querySelectorAll("tr");

        for (const tr of rivit) {
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

            // XML-laskut alkavat numerolla 1.
            if (!parm.startsWith("1")) {
                continue;
            }

            const solut = tr.querySelectorAll("td");

            if (solut.length < 6) {
                continue;
            }

            const erapaiva = solut[0].innerText.trim();
            const laskuttaja = solut[2].innerText.trim();
            const aihe = solut[3].innerText.trim();
            const summa = solut[5].innerText.trim();

            if (!/^\d{1,2}\.\d{1,2}\.\d{4}$/.test(erapaiva)) {
                console.log(
                    "Ohitetaan rivi ilman laskupäivämäärää:",
                    tr.innerText.trim()
                );
                continue;
            }

            const lasku = {erapaiva, laskuttaja, aihe, summa, parm};

            lasku.tiedostonimi = teeTiedostonimi(lasku);
            laskut.push(lasku);
        }

        return laskut;
    }


    // ------------------------------------------------------------
    // Sivunumero
    // ------------------------------------------------------------

    function haeSivunumero(frame) {
        const teksti = frame.document.body.innerText;
        const osuma = teksti.match(/Sivu\s+(\d+)\s*\/\s*(\d+)/i);

        if (!osuma) {
            return null;
        }

        return {nykyinen: Number(osuma[1]), yhteensa: Number(osuma[2])};
    }


    // ------------------------------------------------------------
    // Ohita confirm
    // ------------------------------------------------------------

    function ohitaConfirm(frame) {
        try {
            const script = frame.document.createElement("script");
            script.textContent = `window.top.confirm = () => true;`;
            (frame.document.head ||frame.document.documentElement).appendChild(script);
            script.remove();
        } catch (e) {
        }
    }


    // ------------------------------------------------------------
    // Seuraava sivu
    // Sama sivutuslogiikka kuin toimivassa PDF 5.5:ssä
    // ------------------------------------------------------------

    async function siirrySeuraavalleSivulle(frame) {

        const sivu = haeSivunumero(frame);
        if (!sivu) {
            return false;
        }
        console.log(`Sivutus: nykyinen sivu ${sivu.nykyinen}/${sivu.yhteensa}`);
        if (sivu.nykyinen >= sivu.yhteensa) {
            console.log(`Viimeinen sivu ${sivu.nykyinen}/${sivu.yhteensa} saavutettu.`);
            return false;
        }

        const seuraavaNumero = String(sivu.nykyinen + 1);

        let seuraava =
            [...frame.document.querySelectorAll('a[href*="EIR1EIListLSkift"]')].find(a =>
                a.innerText.trim() === seuraavaNumero
            );


        if (!seuraava) {
            seuraava = [...frame.document.querySelectorAll('a[href*="EIR1EIListLNed"]')][0];
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


        const ennen = haeLaskut(frame)[0]?.parm || "";

        try {
            ohitaConfirm(frame);
            seuraava.click();
        } catch (e) {
            console.error("Seuraavalle sivulle siirtyminen epäonnistui:", e);
            return false;
        }

        // Odotetaan, että sivu oikeasti vaihtuu.
        for (let i = 0; i < 40; i++) {
            await new Promise(resolve => setTimeout(resolve, 250));

            const uusiSivu = haeSivunumero(frame);
            const uusiEnsimmainen = haeLaskut(frame)[0]?.parm || "";

            if (
                uusiSivu &&
                uusiSivu.nykyinen === sivu.nykyinen + 1 &&
                uusiEnsimmainen !== ennen
            ) {
                console.log(`Uusi sivu ladattu: ${uusiSivu.nykyinen}/${uusiSivu.yhteensa}`);
                return true;
            }
        }


        // Sivunumero voi olla jo vaihtunut, vaikka
        // ensimmäisen laskun tarkistus ei onnistunut.
        const lopullinenSivu = haeSivunumero(frame);

        if (lopullinenSivu && lopullinenSivu.nykyinen === sivu.nykyinen + 1) {
            console.log(
                `Uusi sivu ladattu sivunumeron perusteella: ` +
                `${lopullinenSivu.nykyinen}/${lopullinenSivu.yhteensa}`
            );
            return true;
        }

        console.error("Seuraavalle sivulle siirtymistä ei voitu varmistaa.");

        return false;
    }


    // ------------------------------------------------------------
    // Avaa XML ja odota valmis-viestiä
    // ------------------------------------------------------------

    function avaaXMLPageWorld(frame, parm, tiedostonimi, id) {

        return new Promise((resolve, reject) => {
            let valmis = false;
            let ajastin = null;
            let timeout = null;


            function siivoa() {

                if (ajastin !== null) {
                    clearInterval(ajastin);
                    ajastin = null;
                }

                if (timeout !== null) {
                    clearTimeout(timeout);
                    timeout = null;
                }

                window.removeEventListener("message", valmisHandler);
                window.removeEventListener("message", virheHandler);
            }


            function onnistui() {
                if (valmis) {
                    return;
                }

                valmis = true;

                console.log("XML VALMIS:", tiedostonimi);

                siivoa();
                resolve();
            }


            function valmisHandler(event) {
                if (event.origin !== BANK_ORIGIN) {
                    return;
                }

                if (!event.data || event.data.type !== "danske-xml-valmis-relay") {
                    return;
                }

                if (event.data.id !== id) {
                    return;
                }

                onnistui();
            }


            function virheHandler(event) {
                if (event.origin !== BANK_ORIGIN) {
                    return;
                }

                if (!event.data || event.data.type !== "danske-xml-virhe-relay") {
                    return;
                }

                if (event.data.id !== id) {
                    return;
                }

                const virhe = event.data.virhe || "Tuntematon XML-virhe";
                siivoa();
                reject(new Error(virhe));
            }

            window.addEventListener("message", valmisHandler);
            window.addEventListener("message", virheHandler);

            const script = frame.document.createElement("script");

            script.textContent = `

                (() => {
                    const parm = ${JSON.stringify(parm)};
                    const tiedostonimi = ${JSON.stringify(tiedostonimi)};
                    const id = ${JSON.stringify(id)};
                    const BANK_ORIGIN = ${JSON.stringify(BANK_ORIGIN)};
                    const LIST_ORIGIN = ${JSON.stringify(LIST_ORIGIN)};
                    let einvoice = null;
                    let valmis = false;
                    let alkuperainenOpen = window.open;

                    // ------------------------------------------------
                    // Kaapataan Dansken avaama einvoice-ikkuna
                    // ------------------------------------------------

                    window.open = function (...args) {

                        const ikkuna =
                            alkuperainenOpen.apply(
                                this,
                                args
                            );

                        try {

                            if (
                                args[1] === "einvoice"
                            ) {

                                einvoice = ikkuna;

                                console.log(
                                    "DANSKE XML 14.3: einvoice-ikkuna kaapattu."
                                );
                            }

                        } catch (e) {
                        }

                        return ikkuna;
                    };


                    // ------------------------------------------------
                    // XML-lataajan valmisviesti
                    // ------------------------------------------------

                    function valmisHandler(event) {

                        if (
                            event.origin !==
                            BANK_ORIGIN
                        )
                            return;

                        if (
                            !event.data ||
                            event.data.type !==
                                "danske-xml-valmis"
                        )
                            return;

                        if (
                            event.source !==
                            einvoice
                        )
                            return;

                        if (valmis)
                            return;

                        valmis = true;

                        console.log(
                            "DANSKE XML 14.3: lataus valmis."
                        );


                        window.top.postMessage(
                            {
                                type:
                                    "danske-xml-valmis-relay",

                                id:
                                    id,

                                tiedostonimi:
                                    event.data.tiedostonimi
                            },
                            LIST_ORIGIN
                        );


                        siivoa();


                        setTimeout(() => {

                            try {

                                if (
                                    einvoice &&
                                    !einvoice.closed
                                ) {
                                    einvoice.close();
                                }

                            } catch (e) {
                            }

                        }, 500);
                    }


                    window.addEventListener(
                        "message",
                        valmisHandler
                    );


                    function siivoa() {

                        try {
                            window.open =
                                alkuperainenOpen;
                        } catch (e) {
                        }

                        window.removeEventListener(
                            "message",
                            valmisHandler
                        );

                        if (ajastin !== null) {
                            clearInterval(ajastin);
                            ajastin = null;
                        }
                    }


                    // ------------------------------------------------
                    // Kutsu Dansken omaa funktiota
                    // ------------------------------------------------

                    try {

                        console.log(
                            "DANSKE XML 14.3: kutsutaan EIR1VisLink"
                        );

                        console.log(
                            "parm:",
                            parm
                        );

                        EIR1VisLink(parm);

                        console.log(
                            "DANSKE XML 14.3: EIR1VisLink kutsuttu."
                        );

                    } catch (e) {

                        console.error(
                            "DANSKE XML 14.3: EIR1VisLink VIRHE",
                            e
                        );

                        window.top.postMessage(
                            {
                                type:
                                    "danske-xml-virhe-relay",

                                id:
                                    id,

                                virhe:
                                    String(e)
                            },
                            LIST_ORIGIN
                        );

                        siivoa();

                        return;
                    }


                    // ------------------------------------------------
                    // Lähetä tiedostonimi korkeintaan 3 kertaa
                    // ------------------------------------------------

                    let yritys = 0;

                    function laheta() {

                        if (valmis)
                            return;

                        yritys++;

                        if (
                            einvoice &&
                            !einvoice.closed
                        ) {

                            console.log(
                                "DANSKE XML 14.3: tiedostonimi -> XML ikkuna",
                                yritys,
                                tiedostonimi
                            );

                            try {

                                einvoice.postMessage(
                                    {
                                        type:
                                            "danske-xml-tiedostonimi",

                                        tiedostonimi:
                                            tiedostonimi
                                    },
                                    BANK_ORIGIN
                                );

                            } catch (e) {

                                console.error(
                                    "postMessage virhe:",
                                    e
                                );
                            }
                        }


                        if (yritys >= 3) {

                            clearInterval(
                                ajastin
                            );

                            ajastin = null;
                        }
                    }


                    /*
                     * Ensimmäinen lähetys 500 ms kuluttua.
                     * Seuraavat 500 ms välein.
                     *
                     * Jos valmis tulee, valmisHandler
                     * pysäyttää ajastimen heti.
                     */
                    let ajastin =
                        setInterval(
                            laheta,
                            500
                        );


                    // ------------------------------------------------
                    // Lopullinen aikakatkaisu
                    // ------------------------------------------------

                    setTimeout(() => {

                        if (valmis)
                            return;

                        console.error(
                            "DANSKE XML 14.3: aikakatkaisu."
                        );

                        window.top.postMessage(
                            {
                                type:
                                    "danske-xml-virhe-relay",

                                id:
                                    id,

                                virhe:
                                    "XML-latauksen aikakatkaisu"
                            },
                            LIST_ORIGIN
                        );

                        siivoa();

                    }, 30000);

                })();

            `;


            (
                frame.document.head ||
                frame.document.documentElement
            ).appendChild(script);

            script.remove();


            timeout =
                setTimeout(() => {

                    siivoa();

                    reject(
                        new Error(
                            "XML-latauksen aikakatkaisu: " +
                            tiedostonimi
                        )
                    );

                }, 30000);
        });
    }


    // ------------------------------------------------------------
    // Käsittele yksi lasku
    // ------------------------------------------------------------

    async function kasitteleLasku(frame, lasku, numero, maara) {
        console.log("");
        console.log("----------------------------------------");
        console.log(`XML ${numero}/${maara}`);
        console.log("Laskuttaja:", lasku.laskuttaja);
        console.log("Aihe:", lasku.aihe);
        console.log("Summa:", lasku.summa);
        console.log("Tiedostonimi:", lasku.tiedostonimi);
        console.log("parm:", lasku.parm);
        const id = "xml-" + Date.now() + "-" + Math.random().toString(36).slice(2);

        try {
            await avaaXMLPageWorld(frame, lasku.parm, lasku.tiedostonimi, id);
            console.log("Lasku valmis:", lasku.tiedostonimi);
            return true;
        } catch (e) {
            console.error("XML-LASKUN KÄSITTELY EPÄONNISTUI:", e);
            return false;
        }
    }


    // ------------------------------------------------------------
    // Kaikki laskut
    // ------------------------------------------------------------

    async function tallennaKaikki() {
        const frame = window.frames[2];

        if (!frame) {
            alert("Dansken indhold-framea ei löytynyt.");
            return;
        }
        const sivu = haeSivunumero(frame);
        if (!sivu) {
            alert("Dansken sivunumeroa ei löytynyt.");
            return;
        }

        const ensimmainenSivu = sivu.nykyinen;
        const viimeinenSivu = sivu.yhteensa;

        if (!confirm("Tallennetaanko kaikki XML-e-laskut?\n\nSivuja: " + viimeinenSivu)) {
            console.log("XML BULK: käyttäjä peruutti.");
            return;
        }


        console.log("");
        console.log("========================================");
        console.log("XML BULK 14.3 - ALOITUS");
        console.log("Sivuja:",viimeinenSivu);
        console.log("========================================");

        let tallennettu = 0;
        let epaonnistui = 0;
        let laskujaYhteensa = 0;

        for (let sivunumero = ensimmainenSivu; sivunumero <= viimeinenSivu; sivunumero++) {
            await new Promise(resolve => setTimeout(resolve, 500));

            const nykyinen = haeSivunumero(frame);
            if (!nykyinen) {
                console.error("Sivunumeroa ei enää löytynyt.");
                break;
            }

            console.log("");
            console.log(`SIVU ${nykyinen.nykyinen}/${nykyinen.yhteensa}`);
            const laskut = haeLaskut(frame);
            laskujaYhteensa += laskut.length;
            console.log(`Sivulla ${nykyinen.nykyinen}/${nykyinen.yhteensa} ${laskut.length} XML-laskua.`);

            for (let i = 0; i < laskut.length; i++) {
                const onnistui =
                    await kasitteleLasku(frame, laskut[i], i + 1, laskut.length);

                if (onnistui) {
                    tallennettu++;
                } else {
                    epaonnistui++;
                }

                await new Promise(resolve => setTimeout(resolve, 500));
            }

            if (nykyinen.nykyinen >= viimeinenSivu) {
                break;
            }

            const onnistui = await siirrySeuraavalleSivulle(frame);

            if (!onnistui) {
                console.error("Sivun vaihto epäonnistui.");
                break;
            }
        }


        console.log("");
        console.log("========================================");
        console.log("XML BULK 14.3 - VALMIS");
        console.log("Laskuja yhteensä:", laskujaYhteensa);
        console.log("Tallennettu:", tallennettu);
        console.log("Epäonnistui:", epaonnistui);
        console.log("========================================");

        alert(
            "XML-lataus valmis.\n\n" +
            "Sivuja: " +
            viimeinenSivu +
            "\n" +
            "Laskuja: " +
            laskujaYhteensa +
            "\n" +
            "Tallennettu: " +
            tallennettu +
            "\n" +
            "Epäonnistui: " +
            epaonnistui
        );
    }


    // ------------------------------------------------------------
    // Tampermonkey-valikko
    // ------------------------------------------------------------

    GM_registerMenuCommand("Tallenna kaikki XML-e-laskut", tallennaKaikki);

    console.log(
        "XML BULK 14.3 - valmis."
    );
}


kaynnista();
