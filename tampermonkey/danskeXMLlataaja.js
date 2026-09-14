// ==UserScript==
// @name         Danske XML lataaja
// @namespace    https://danskebank.fi/
// @version      1.2
// @description  Vastaanottaa tiedostonimen ja lataa Dansken e-laskun XML:n
// @match        https://verkkopankki.danskebank.fi/*
// @grant        none
// ==/UserScript==

"use strict";

function kaynnista() {

    const BANK_ORIGIN = "https://verkkopankki.danskebank.fi";
    const LIST_ORIGIN = "https://verkkopankki2.danskebank.fi";

    // --------------------------------------------------
    // XML-viestin käsittely
    // --------------------------------------------------

    async function kasitteleXmlViesti(event) {
        console.log("----------------------------------------");
        console.log("XML SAAPUI POSTMESSAGE");
        console.log("----------------------------------------");

        console.log("origin:", event.origin);
        console.log("data:", event.data);


        // Hyväksytään vain Dansken omilta sivuilta tulevat viestit

        if (event.origin !== BANK_ORIGIN && event.origin !== LIST_ORIGIN) {
            console.log("Väärä origin -> ohitetaan.");
            return;
        }


        // Tarkistetaan, että kyseessä on meidän viestimme

        if (!event.data || event.data.type !== "danske-xml-tiedostonimi") {
            return;
        }


        const tiedostonimi = event.data.tiedostonimi;

        console.log("Vastaanotettu tiedostonimi:", tiedostonimi);

        if (!tiedostonimi) {
            console.error("Tiedostonimi puuttuu.");
            return;
        }

        console.log("XML URL:", location.href);

        try {
            const response = await fetch(location.href);

            if (!response.ok) {
                throw new Error("HTTP-virhe " + response.status);
            }

            const blob = await response.blob();
            console.log("XML ladattu:", blob.size, "tavua");
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");

            a.href = url;
            a.download = tiedostonimi;

            document.body.appendChild(a);
            a.click();
            a.remove();
            setTimeout(() => {URL.revokeObjectURL(url);}, 5000);

            console.log("XML TALLENNETTU:", tiedostonimi);

            // Ilmoitetaan lähettäjälle, että tiedosto on valmis

            if (event.source) {
                const vastausOrigin = event.origin === LIST_ORIGIN ? LIST_ORIGIN : BANK_ORIGIN;
                event.source.postMessage({type: "danske-xml-valmis", tiedostonimi: tiedostonimi}, vastausOrigin);
                console.log("VALMIS-VIESTI LÄHETETTY.", "kohde:", vastausOrigin);
            }
        } catch (e) {
            console.error("XML:N LATAUS EPÄONNISTUI:", e);
            if (event.source) {
                const vastausOrigin = event.origin === LIST_ORIGIN ? LIST_ORIGIN : BANK_ORIGIN;
                event.source.postMessage({type: "danske-xml-virhe", virhe: String(e)}, vastausOrigin);
            }
        }
    }


    // --------------------------------------------------
    // Kuunnellaan XML-popupille tulevia viestejä
    // --------------------------------------------------

    window.addEventListener("message", kasitteleXmlViesti);

    console.log("========================================");
    console.log("DANSKE XML LATAAJA");
    console.log("========================================");
    console.log("XML POSTMESSAGE-KUUNTELIJA VALMIS.");
}


// --------------------------------------------------
// Käynnistetään skripti
// --------------------------------------------------

kaynnista();
