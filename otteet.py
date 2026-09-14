from pathlib import Path
import re
import html
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from nimea_tiliote_pvm_mukaan import pura_ja_nimea

from taulukko_html import (
    TaulukkoAsetukset,
    muodosta_taulukko,
    muodosta_rivit,
    muodosta_css,
    muodosta_javascript
)

"""
Tiliotteiden käsittely

Aluksi puretaan mahdolliset arkisto/*.zip, jotta 
"* Tiliote"-alkuiset PDF-tiedostot löytyvät.
Tiedoston nimetää uudelleen PDF:n sisällön perusteella, 
ha sirrtetään otteet-hakemistoon. 
otteet-hakemistosta Luetaan tiliotteiden PDF-tiedostot
ja muodostetaan niistä HTML-taulukko.
Tiedoston nimi pitää sisältää Tiliote ja sisältää tilinumeron (FI...)
tai tiliotteen numeron (Tiliote 123-456).

Copyright (c) 2026 vesal & ChatGPT
"""


VERSION = "1.2.2"

PDF_HAKEMISTO = Path("./otteet")
TULOSTIEDOSTO = Path("./otteet.html")

TAULUKKO = TaulukkoAsetukset(
    sarakkeet=[
        "Tiliote",
        "Päivä",
        "Summa",
        "Maksutapa",
        "Kohde",
    ],
    numeeriset_sarakkeet=[2],
    summa_sarake=2,
    sarakeleveydet=[80, 100, 70, 300, 500],
)

OLETUSMAKSUTAVAT = [
    "Verkkolaskut",
    "Laskunmaksut/Tilisiirrot",
    "Suoraveloitukset ja toistuvat maksut",
    "Säästäminen ja sijoittaminen/Panot",
    "Tulot/Pano",
    "Korttiostot",
]


def tilinumero_tiedoston_nimesta(pdf_tiedosto: Path) -> str:
    """
    Hakee tiliotteen tilinumeron PDF-tiedoston nimestä.
    Tiedoston nimi voi olla esimerkiksi Dansken alkuperäisessä
    muodossa: Tiliote FI12 3456 7890 1234 56 (25).PDF
              Tiliote FI12 3456 7890 1234 56 - 2026-09-02T162433.760.PDF
              Tai uudelleennimettynä:
                2021-09-01 - Tiliote - FI12 3456 7890 1234 56 - .pdf
    Vanhoissa tiliotteissa tilinumero voi olla kansallisessa muodossa:
              Tiliote 123456-12345678 (25).PDF
    :param pdf_tiedosto: Tiliotteen PDF-tiedosto.
    :return: Tiedostonimestä löytyvä tilinumero tai tyhjä merkkijono,
             jos tilinumeroa ei löydy.
    """
    nimi = pdf_tiedosto.name
    # Uusi suomalainen IBAN-muotoinen tilinumero.
    iban_match = re.search(
        r'Tiliote\s+-\s+(FI\d{2}(?:\s+\d{4}){3}\s+\d{2})',
        nimi,
        re.IGNORECASE,
    )
    if iban_match:
        return iban_match.group(1)
    # Vanha suomalainen kansallinen tilinumero.
    numero_match = re.search(
        r'Tiliote\s+(\d+-\d+)',
        nimi,
        re.IGNORECASE,
    )
    if numero_match:
        return numero_match.group(1)
    return ""


def lue_tapahtumat() -> list[dict]:
    """
    Lukee kaikki tiliotteiden tapahtumat.
    :return: Tiliotteiden tapahtumat.
    """

    pdf_tiedostot = sorted(PDF_HAKEMISTO.glob("*Tiliote*.pdf"))

    tulokset = []

    pattern = re.compile(
        r'(?:^|\n)'
        r'(?:([^\d\n]+)\n)?'
        r'(\d{2}\.\d{2}\.)\s+'
        r'(\d{2}\.\d{2}\.)\s+'
        r'(.*?)\s+'
        r'(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})\s+([-+])'
    )

    pdf_tapahtumat = []
    alkusaldo = None
    loppusaldo = None
    pdf = None

    for pdf in pdf_tiedostot:

        pdf_tapahtumat = []
        alkusaldo = None
        loppusaldo = None

        try:
            reader = PdfReader(pdf)
        except PdfReadError:
            print(f"Virhe: Tiedostoa {pdf.name} ei voitu lukea. Ohitetaan.")
            continue

        # Tiliotteen numero tiedostonimestä
        tilinumero = tilinumero_tiedoston_nimesta(pdf)
        tili3 = tilinumero.replace(" ", "")[-3:]

        if not tili3:
            numero_match = re.search(
                r'Tiliote\s+\d+-(\d+)',
                pdf.name,
                re.IGNORECASE
            )

            if numero_match:
                tili3 = numero_match.group(1)[-3:]
            else:
                tili3 = ""

        # Sulkeissa oleva tiliotteen numero
        erotin_match = re.search(r'\((\d+)\)\.pdf$', pdf.name, re.IGNORECASE)

        if erotin_match:
            erotin = erotin_match.group(1)
        else:
            pvm_match = re.match(
                r'(\d{4})-(\d{2})-(\d{2})\s+-\s+Tiliote',
                pdf.name,
                re.IGNORECASE,
            )

            if pvm_match:
                erotin = (
                        pvm_match.group(1)[2:]
                        + pvm_match.group(2)
                )
            else:
                erotin = ""

        linkkiteksti = f"{tili3} ({erotin})"
        oletus_maksutapa = ""

        for page in reader.pages:   # [:3]:

            text = page.extract_text() or ""

            alkusaldo_match = re.search(
                r'Alkusaldo\s+\d{2}\.\d{2}\.\d{4}\s+'
                r'(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})\s+([+-])',
                text,
            )

            if alkusaldo_match:
                alkusaldo = float(
                    alkusaldo_match.group(1)
                    .replace(".", "")
                    .replace(",", ".")
                )
                if alkusaldo_match.group(2) == "+":
                    alkusaldo = -alkusaldo

            loppusaldo_match = re.search(
                r'Loppusaldo\s+\d{2}\.\d{2}\.\d{4}\s*:?\s+'
                r'(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})\s+([+-])',
                text,
            )

            if loppusaldo_match:
                loppusaldo = float(
                    loppusaldo_match.group(1)
                    .replace(".", "")
                    .replace(",", ".")
                )
                if loppusaldo_match.group(2) == "+":
                    loppusaldo = -loppusaldo

            vuosi_match = re.search(
                r'Ajalta\s+\d{2}\.\d{2}\.(\d{4})\s+-\s+\d{2}\.\d{2}\.\d{4}',
                text
            )

            if not vuosi_match:
                continue

            vuosi = vuosi_match.group(1)

            for match in pattern.finditer(text):

                otsikko = match.group(1)
                if otsikko and otsikko in OLETUSMAKSUTAVAT:
                    oletus_maksutapa = otsikko.strip()

                _kirjauspaiva = match.group(2)
                arvopaiva = match.group(3)

                maksutapa = " ".join(
                    match.group(4).split()
                )

                summa = float(
                    match.group(5).replace(".", "").replace(",", ".")
                )

                etumerkki = match.group(6)
                if etumerkki == "+":
                    summa = -summa

                """
                if any(
                    x in maksutapa.lower()
                    for x in [
                        "saldo",
                        "yhteensä",
                        "alkusaldo",
                        "loppusaldo",
                    ]
                ):
                    continue
                """

                loppu = text[match.end() + 1:]
                if loppu:
                    seuraava = loppu.splitlines()[0].strip()
                else:
                    seuraava = ""
                if re.match(
                        r'^\d{2}\.\d{2}\.\s+\d{2}\.\d{2}\.',
                        seuraava,
                ):
                    seuraava = ""

                kohde = re.split(
                    r'\bFI\d{2}\s+\d{4}\s+\d{4}\s+\d{4}\s+\d{2}\b'
                    r'|\bViite\b'
                    r'|\bMaksajan viite\b'
                    r'|\bMaksun tiedot\b'
                    r'|\bKorttiostot yhteensä\b'
                    r'|\bSaldo\b'
                    r'|\bLoppusaldo\b'
                    r'|\bTiedot tiliotepäivältä\b'
                    r'|\bKäteisnostot yhteensä\b',
                    seuraava,
                    maxsplit=1
                )[0].strip()

                kohde = kohde.lstrip("-+ ")

                if maksutapa.endswith("))))"):
                    kohde = maksutapa[:-4].strip()
                    maksutapa = "Korttiostot"

                if not kohde:
                    kohde = maksutapa
                    maksutapa = oletus_maksutapa

                paiva_match = re.match(r'(\d{2})\.(\d{2})\.', arvopaiva)

                if not paiva_match:
                    continue

                paiva_numero = paiva_match.group(1)
                kuukausi = paiva_match.group(2)

                iso_paiva = (
                    f"{vuosi}-{kuukausi}-{paiva_numero}"
                )

                pdf_tapahtumat.append(summa)

                tulokset.append({
                    "tiedosto": pdf.name,
                    "paiva": iso_paiva,
                    "summa": summa,
                    "maksutapa": maksutapa,
                    "kohde": kohde,
                    "linkkiteksti": linkkiteksti,
                })

    if alkusaldo is not None and loppusaldo is not None:
        tapahtumien_summa = round(sum(pdf_tapahtumat), 2)
        odotettu_summa = round(loppusaldo - alkusaldo, 2)

        if pdf and tapahtumien_summa != odotettu_summa:
            print(
                f"VAROITUS: {pdf.name}\n"
                f"  alkusaldo:       {alkusaldo:.2f}\n"
                f"  loppusaldo:      {loppusaldo:.2f}\n"
                f"  odotettu muutos: {odotettu_summa:.2f}\n"
                f"  tapahtumat:      {tapahtumien_summa:.2f}\n"
                f"  ero:              {tapahtumien_summa - odotettu_summa:.2f}"
            )
    return tulokset


def kasittele_tulokset(tulokset: list[dict]) -> list[dict]:
    """
    Poistaa duplikaatit ja järjestää tapahtumat päivämäärän mukaan.

    :param tulokset: Tiliotteiden tapahtumat.
    :return: Käsitellyt tiliotteiden tapahtumat.
    """

    """
    # Dublikaatit johtuivatkin että samalle päivälle oli useampi samanlainen rivi,
    # esim osto pe ja sen perään veloitus ma. 
    Joten ei poisteta duplikaatteja.
    uniikit = {}

    for r in tulokset:
        avain = (
            r["tiedosto"],
            r["paiva"],
            r["summa"],
            r["maksutapa"],
            r["kohde"],
        )

        if avain in uniikit:
            print(
                "DUPLIKAATTI:",
                r["tiedosto"],
                r["paiva"],
                r["summa"],
                repr(r["maksutapa"]),
                repr(r["kohde"]),
            )
            continue
        uniikit[avain] = r

    tulokset = list(uniikit.values())
    """
    tulokset.sort(key=lambda x: x["paiva"], reverse=True)
    return tulokset


def muodosta_html(tulokset: list[dict]) -> None:
    """
    Muodostaa HTML-tiedoston tiliotteiden tapahtumista.

    :param tulokset: Tiliotteiden tapahtumat.
    """

    otsikot, leveydet = muodosta_taulukko(TAULUKKO)

    rivit = []

    for r in tulokset:
        summa = r["summa"]
        rivit.append([
            {
                "html": (
                    f'<a href="{html.escape(str(PDF_HAKEMISTO / r["tiedosto"]))}" '
                    f'target="_blank">{html.escape(r["linkkiteksti"])}</a>'
                )
            },
            {
                "html": html.escape(r["paiva"]),
                "data_value": r["paiva"],
            },
            {
                "html": f'{summa:,.2f}',
                "data_value": summa,
            },
            {"html": html.escape(r["maksutapa"])},
            {"html": html.escape(r["kohde"])},
        ])

    rivit_html, js_rivit = muodosta_rivit(rivit)
    javascript = muodosta_javascript(TAULUKKO, js_rivit)

    with open(TULOSTIEDOSTO, "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html> 
<html lang="fi">
<head>
<meta charset="UTF-8">
<title>Tiliotteet</title>

<style>
{muodosta_css(TAULUKKO)}
</style>
</head>
<body>

<h1>Tiliotteet</h1>
<div class="sticky-header">
    <div id="maara" class="info">
        Rivejä: <span id="laskurivimaara"></span>
        <span id="summa"></span>
    </div>
</div>
<table id="laskut">
<thead>
<tr>
{otsikot}
</tr>
</thead>

<tbody>
{rivit_html}
</tbody>
</table>
<script>
{javascript}
</script>
</body>
</html>
""")


def main():
    print(f"Tiliotteet {VERSION}")

    pura_ja_nimea()

    print(f"Lähde: {PDF_HAKEMISTO.resolve()}")
    tulokset = lue_tapahtumat()
    print(f"Löytyi {len(tulokset)} tapahtumaa")
    tulokset = kasittele_tulokset(tulokset)
    print("Muodotetaan html-tiedosto...")
    muodosta_html(tulokset)
    print(
        f"Valmis: {TULOSTIEDOSTO.name} ({len(tulokset)} tapahtumaa)"
    )


if __name__ == "__main__":
    main()
