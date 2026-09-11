from pathlib import Path
import re
import html
from pypdf import PdfReader
from pypdf.errors import PdfReadError
from taulukko_html import (
    TaulukkoAsetukset,
    muodosta_taulukko,
    muodosta_rivit,
    muodosta_css,
    muodosta_javascript
)

KANSIO = Path("./otteet")


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
    sarakeleveydet=[60, 60, 60, 300, 400],
)


def lue_tapahtumat() -> list[dict]:
    """
    Lukee kaikki tiliotteiden tapahtumat.
    :return: Tiliotteiden tapahtumat.
    """

    pdf_tiedostot = sorted(KANSIO.glob("Tiliote*.pdf"))

    tulokset = []

    _pattern = re.compile(  # Vanha versio ilman otsikkoa
        r'(\d{2}\.\d{2}\.)\s+\1\s+'
        r'(.*?)\s+'
        r'(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})\s+-'
    )

    pattern = re.compile(
        r'(?:^|\n)'
        r'(?:([^\d\n]+)\n)?'
        r'(\d{2}\.\d{2}\.)\s+\2\s+'
        r'(.*?)\s+'
        r'(\d{1,3}(?:\.\d{3})*,\d{2}|\d+,\d{2})\s+([-+])'
    )

    for pdf in pdf_tiedostot:

        try:
            reader = PdfReader(pdf)
        except PdfReadError:
            continue

        # Tiliotteen numero tiedostonimestä
        iban_match = re.search(
            r'Tiliote\s+(FI\d{2}(?:\s+\d{4}){3}\s+\d{2})',
            pdf.name,
            re.IGNORECASE
        )

        if iban_match:
            tilinumero = iban_match.group(1)
            tili3 = tilinumero.replace(" ", "")[-3:]
        else:
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
        erotin_match = re.search(
            r'\((\d+)\)\.pdf$',
            pdf.name,
            re.IGNORECASE
        )

        erotin = (
            erotin_match.group(1)
            if erotin_match
            else ""
        )

        linkkiteksti = f"{tili3} ({erotin})"
        oletus_maksutapa = ""

        for page in reader.pages:   # [:3]:

            text = page.extract_text() or ""

            vuosi_match = re.search(
                r'Ajalta\s+\d{2}\.\d{2}\.(\d{4})\s+-\s+\d{2}\.\d{2}\.\d{4}',
                text
            )

            if not vuosi_match:
                continue

            vuosi = vuosi_match.group(1)

            for match in pattern.finditer(text):

                otsikko = match.group(1)
                if otsikko and len(otsikko) > 5:
                    oletus_maksutapa = otsikko.strip()

                paiva = match.group(2)

                maksutapa = " ".join(
                    match.group(3).split()
                )

                summa = float(
                    match.group(4)
                    .replace(".", "")
                    .replace(",", ".")
                )

                etumerkki = match.group(5)
                if etumerkki == "+":
                    summa = -summa

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

                paiva_match = re.match(
                    r'(\d{2})\.(\d{2})\.',
                    paiva
                )

                if not paiva_match:
                    continue

                paiva_numero = paiva_match.group(1)
                kuukausi = paiva_match.group(2)

                iso_paiva = (
                    f"{vuosi}-{kuukausi}-{paiva_numero}"
                )

                tulokset.append({
                    "tiedosto": pdf.name,
                    "paiva": iso_paiva,
                    "summa": summa,
                    "maksutapa": maksutapa,
                    "kohde": kohde,
                    "linkkiteksti": linkkiteksti,
                })

    return tulokset


def kasittele_tulokset(tulokset: list[dict]) -> list[dict]:
    """
    Poistaa duplikaatit ja järjestää tapahtumat päivämäärän mukaan.

    :param tulokset: Tiliotteiden tapahtumat.
    :return: Käsitellyt tiliotteiden tapahtumat.
    """
    uniikit = {}

    for r in tulokset:

        avain = (
            r["tiedosto"],
            r["paiva"],
            r["summa"],
            r["maksutapa"],
            r["kohde"],
        )

        uniikit[avain] = r

    tulokset = list(uniikit.values())

    tulokset.sort(key=lambda x: x["paiva"], reverse=True)

    return tulokset


def muodosta_html(tulokset: list[dict]) -> None:
    """
    Muodostaa HTML-tiedoston tiliotteiden tapahtumista.

    :param tulokset: Tiliotteiden tapahtumat.
    """
    # ---------------------------------------
    # HTML
    # ---------------------------------------

    otsikot, leveydet = muodosta_taulukko(TAULUKKO)

    rivit = []

    for r in tulokset:
        summa = r["summa"]
        rivit.append([
            {
                "html": (
                    f'<a href="{html.escape(str(KANSIO / r["tiedosto"]))}" '
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

    with open("otteet.html", "w", encoding="utf-8") as f:
        f.write(f"""<!DOCTYPE html> 
<html lang="fi">
<head>
<meta charset="UTF-8">
<title>Tiliotteet</title>

<style>
{muodosta_css()}
{leveydet}
</style>
</head>
<body>

<h1>Tiliotteet</h1>

<div id="maara" class="info">
    Rivejä: <span id="laskurivimaara"></span>
    <span id="summa"></span>
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
    tulokset = lue_tapahtumat()
    tulokset = kasittele_tulokset(tulokset)
    muodosta_html(tulokset)
    print(
        f"Valmis: otteet.html ({len(tulokset)} tapahtumaa)"
    )


if __name__ == "__main__":
    main()
