from pathlib import Path
from typing import Optional
import re
import html
import xml.etree.ElementTree as eT

from lasku_html import tee_lasku_html
from taulukko_html import (
    TaulukkoAsetukset,
    muodosta_taulukko,
    muodosta_rivit,
    muodosta_javascript, muodosta_css,
)

"""
Luetaan kaikki Dansken elaskujen XML-tiedostot ./xml-hakemistosta
ja elaskut ./pdf-hakemistosta
ja muodostetaan niistä
laskulista, joka kirjoitetaan HTML-muodossa ./laskut.html
XML--tiedostoista tehdään vastaava html-tiedosto html-hakemistoon, jonka
voi avata taulukosta klikkaamalla.
Laskuja voi etsiä ja suodattaa selaimessa.

Copyright (c) 2026 vesal & ChatGPT. All rights reserved.
"""

VERSION = "1.1.4"

# ============================================================
# Asetukset
# ============================================================

TAULUKKO = TaulukkoAsetukset(
    sarakkeet=["Päivä", "Saaja", "Aihe", "Summa"],
    numeeriset_sarakkeet=[3],
    summa_sarake=3,
    sarakeleveydet=[110, 220, 300, 90],
    koontirivit=True,
)


XML_HAKEMISTO = Path("./xml")
PDF_HAKEMISTO = Path("./pdf")
HTML_HAKEMISTO = Path("./html")
TULOSTIEDOSTO = Path("./laskut.html")
SUMMA_SARAKE = 3
NUMEERISET_SARAKKEET = [SUMMA_SARAKE]

# Tekstien korjaukset, joita XML:stä tulee väärässä muodossa.
TEKSTIKORJAUKSET = {
    "Kaerkkaeinen Jyvaesk": "Kärkkäinen Jyväskylä",
    "Gigantti Jyvaeskylae": "Gigantti Jyväskylä",
}


# ============================================================
# XML-apufunktiot
# ============================================================

def muotoile_paiva(paiva):
    """
    Muuttaa päivämäärän muotoon YYYY-MM-DD.
    paiva voi olla muodossa DD.MM.YYYY tai YYYYMMDD.
    Muotoilu on tarpeen, koska Dansken E-laskuissa
    ostopäivä on DD.MM.YYYY, mutta tiedostonimessä on YYYY-MM-DD.
    :param paiva: Päivämäärä merkkijonona.
    :return: Päivämäärä muodossa YYYY-MM-DD tai tyhjä merkkijono,
            jos muotoilu ei onnistunut.
    """
    if not paiva:
        return ""

    paiva = paiva.strip()

    # DD.MM.YYYY
    match = re.fullmatch(r"(\d{2})\.(\d{2})\.(\d{4})", paiva)

    if match:
        paiva, kuukausi, vuosi = match.groups()
        return f"{vuosi}-{kuukausi}-{paiva}"

    # YYYYMMDD
    if len(paiva) == 8 and paiva.isdigit():
        return f"{paiva[0:4]}-{paiva[4:6]}-{paiva[6:8]}"

    return paiva


def tagin_nimi(tag):
    """
    Palauttaa XML-tagista pelkän nimen ilman namespacea.
    :param tag: XML-tag merkkijonona.
    :return: Tagin nimi ilman namespacea.
    """
    return tag.rsplit("}", 1)[-1]


def etsi_elementti(element, nimi) -> Optional[eT.Element]:
    """
    Etsii XML:stä ensimmäisen annetun nimisen elementin.
    :param element: XML-elementti.
    :param nimi: Elementin nimi.
    :return: Etsitty elementti tai None, jos ei löydy.
    """
    for child in element.iter():
        if tagin_nimi(child.tag) == nimi:
            return child

    return None


def etsi_teksti(element, nimi) -> str:
    """
    Etsii annetun nimisen XML-elementin tekstin.
    :param element: XML-elementti.
    :param nimi: Elementin nimi.
    :return: Elementin teksti tai tyhjä merkkijono, jos ei löydy
            tai tekstikenttä on tyhjä.
    """
    child = etsi_elementti(element, nimi)

    if child is None or child.text is None:
        return ""

    return child.text.strip()


def korjaa_teksti(teksti):
    """
    Korjaa tunnetut XML:n tekstimuotovirheet.
    :param teksti: Korjattava teksti.
    :return: Korjattu teksti.
    """
    teksti = (teksti or "").strip()

    for vanha, uusi in TEKSTIKORJAUKSET.items():
        teksti = teksti.replace(vanha, uusi)

    return teksti


def lue_summa(teksti):
    """
    Muuttaa summan numeroksi.
    :param teksti: Summa merkkijonona, esim. "123,45" tai "123.45".
    :return: Summa float-tyyppisenä tai None, jos muunnos ei onnistunut.
    """
    if not teksti:
        return None

    teksti = teksti.strip().replace(",", ".")

    try:
        return float(teksti)
    except ValueError:
        return None


# ============================================================
# Tiedostonimen käsittely
# ============================================================

def pura_tiedostonimi(polku):
    """
    Purkaa tiedostonimestä päivämäärän, saajan ja aiheen.

    Esimerkiksi:

        2026-09-28 - Pohjola Vakuutus Oy - Vakuutuslaskut - 81.14 - .xml
    :param polku: Tiedoston polku Path-objektina.
    :return: Tuple (paiva, saaja, aihe) merkkijonoina.
    """

    stem = polku.stem

    osat = stem.split(" - ")

    if len(osat) < 5:
        return "", stem, "", ""

    paiva = osat[0].strip()
    saaja = osat[1].strip()
    aihe = osat[2].strip()
    summa = osat[3].strip()

    return paiva, saaja, aihe, summa


# ============================================================
# PDF-tiedostojen lukeminen
# ============================================================

def lue_pdf_tiedostot():
    """Lukee ./pdf-hakemiston laskutiedostot."""
    """
    Lukee PDF-tiedostot ja palauttaa laskut tietorakenteessa.
    :return: Lista laskuista.
    """

    laskut = []
    if not PDF_HAKEMISTO.is_dir():
        return laskut

    for polku in sorted(PDF_HAKEMISTO.iterdir()):

        # Hakemistot, kuten *_files, jätetään rauhaan.
        if not polku.is_file():
            continue

        paiva, saaja, aihe, summa_teksti = pura_tiedostonimi(polku)

        if not paiva or not saaja or not summa_teksti:
            continue

        summa = lue_summa(summa_teksti)

        # Linkki tehdään tiedostoon sellaisenaan.
        tiedosto = (PDF_HAKEMISTO / polku.name).as_posix()

        laskut.append(
            {
                "paiva": paiva,
                "saaja": saaja,
                "aihe": aihe,
                "summa": summa,
                "tiedosto": tiedosto,
            }
        )

    return laskut


# ============================================================
# Laskujen lukeminen
# ============================================================

def lue_xml_tiedostot():
    """
    Lukee XML-tiedostot ja palauttaa laskut tietorakenteessa.
    XML-tiedostoista tehdään myös HTML-tiedostot ./html-hakemistoon.
    XML-tiedostoista luetaan laskurivit, joista muodostetaan laskulista.
    XML- tiedostoissa voi olla Dansken korttiostoja,
    joista tehdään omat laskurivit ja silloin itse tiedoston summa
    merkitään tähdellä, jotta se erottuu muista riveistä ja oletuksena
    *-riviä ei lasketa mukaan summaksi koko taulukosta.  Mutta
    jos taulukon hakuehdossa *-alussa, niin silloin *-merkitty summa
    lasketaan mukaan summaksi.
    :return: Lista laskuista.
    """
    laskut = []

    xml_tiedostot = sorted(XML_HAKEMISTO.glob("*.xml"), key=lambda p: p.name.lower())

    for polku in xml_tiedostot:
        try:
            juuri = eT.parse(polku).getroot()
        except Exception as e:
            print(f"XML-virhe tiedostossa {polku.name}: {e}")
            continue

        # ----------------------------------------------------
        # Tee tästä XML:stä luettava HTML-näkymä.
        # ----------------------------------------------------

        html_polku = tee_lasku_html(polku, HTML_HAKEMISTO)

        filename_paiva, filename_saaja, filename_aihe, _ = pura_tiedostonimi(polku)

        seller_name = korjaa_teksti(
            etsi_teksti(juuri, "SellerOrganisationName")
        )

        invoice_total = lue_summa(
            etsi_teksti(juuri, "InvoiceTotalVatIncludedAmount")
        )

        invoice_rows = [
            element
            for element in juuri.iter()
            if tagin_nimi(element.tag) == "InvoiceRow"
        ]

        # ----------------------------------------------------
        # Luetaan ensin kaikki oikeat laskurivit.
        # ----------------------------------------------------

        rivit = []

        for row in invoice_rows:

            article_name = korjaa_teksti(
                etsi_teksti(row, "ArticleName")
            )

            row_free_text = etsi_teksti(row, "RowFreeText")

            # Järjestys:
            # 1. RowVatIncludedAmount
            # 2. RowVatExcludedAmount
            # 3. RowAmount
            summa = lue_summa(
                etsi_teksti(row, "RowVatIncludedAmount")
                or etsi_teksti(row, "RowVatExcludedAmount")
                or etsi_teksti(row, "RowAmount")
            )

            # Ei ArticleNamea -> ei hyödyllinen rivi.
            if not article_name:
                continue

            # Dansken tekniset rivit.
            if article_name.startswith("Kortti "):
                continue

            if row_free_text.startswith("Luottosaldo"):
                continue

            if row_free_text in (
                "Korttitapahtumat yhteensä",
                "Kuukausierä",
            ):
                continue

            # Ilman summaa ei tehdä laskuriviä.
            if summa is None:
                continue

            # ----------------------------------------------------
            # Ostopäivä RowFreeText-kentästä.
            # ------------------------------------------------

            ostopaiva = ""

            for child in row.iter():

                if tagin_nimi(child.tag) != "RowFreeText":
                    continue

                teksti = (child.text or "").strip()

                match = re.search(
                    r"Ostopäivä\s*:\s*"
                    r"(\d{2}\.\d{2}\.\d{4})",
                    teksti,
                    re.IGNORECASE,
                )

                if match:
                    ostopaiva = muotoile_paiva(match.group(1))
                    break

            rivit.append(
                {
                    "article_name": article_name,
                    "row_free_text": row_free_text,
                    "summa": summa,
                    "ostopaiva": ostopaiva,
                }
            )

        # ----------------------------------------------------
        # Ei oikeita summallisia rivejä.
        # ----------------------------------------------------

        if not rivit:
            continue

        # ----------------------------------------------------
        # Dansken E-lasku-kokonaissumma.
        # ----------------------------------------------------

        onko_danske = (seller_name == "Danske Bank")

        elasku_rivi = None

        if onko_danske:
            for rivi in rivit:
                if rivi["article_name"] == "E-lasku":
                    elasku_rivi = rivi
                    break

        if elasku_rivi is not None and invoice_total is not None:
            # Korttiostoja kuvaava XML-tiedosto

            aihe = filename_aihe

            if aihe:
                aihe = f"E-lasku {aihe}"
            else:
                aihe = "E-lasku"

            laskut.append(
                {
                    "paiva": filename_paiva,
                    "saaja": filename_saaja,
                    "aihe": aihe,
                    "summa": f"*{rahaksi(invoice_total)}",
                    "tiedosto": (HTML_HAKEMISTO / html_polku.name).as_posix(),
                }
            )

        # ----------------------------------------------------
        # Varsinaiset laskurivit.
        # ----------------------------------------------------

        for rivi in rivit:
            article_name = rivi["article_name"]

            # Dansken E-lasku-rivi käsiteltiin jo yllä.
            if onko_danske and article_name == "E-lasku":
                continue

            summa = rivi["summa"]
            saaja = filename_saaja

            if onko_danske and rivi["ostopaiva"]:
                saaja = f"{filename_saaja} - {filename_paiva}"

            if filename_aihe and article_name:
                aihe = f"{filename_aihe} / {article_name}"

            elif article_name:
                aihe = article_name

            else:
                aihe = filename_aihe

            paiva = filename_paiva

            # Dansken korttilaskuissa käytetään
            # ostotapahtuman todellista ostopäivää.
            if onko_danske and rivi["ostopaiva"]:
                paiva = rivi["ostopaiva"]

            laskut.append(
                {
                    "paiva": paiva,
                    "saaja": saaja,
                    "aihe": aihe,
                    "summa": summa,
                    "tiedosto": (HTML_HAKEMISTO / html_polku.name).as_posix(),
                }
            )

    # --------------------------------------------------------
    # Lisätään ./pdf-hakemiston tiedostot.
    # --------------------------------------------------------

    laskut.extend(lue_pdf_tiedostot())

    # Uusin laskurivi ensin.
    return sorted(laskut, key=lambda x: x["paiva"], reverse=True)


# ============================================================
# HTML-apufunktiot
# ============================================================

def h(text):
    """
    HTML-escape.
    :param text: Merkkijono, joka halutaan escape:ata.
    :return: Escape:attu merkkijono.
    """
    return html.escape(str(text or ""))


def rahaksi(summa):
    """
    Muuttaa summan kahden desimaalin tekstiksi.
    :param summa: Summa float-tyyppisenä.
    :return: Summa kahden desimaalin tekstiksi.
    """
    if summa is None:
        return ""

    return f"{summa:.2f}"


# ============================================================
# Laskulistan HTML
# ============================================================

def muodosta_html(laskut):
    """
    Muodostaa laskulistan HTML-muotoon.
    :param laskut: Lista laskuista.
    :return: HTML-koodi.
    """
    otsikot, leveydet = muodosta_taulukko(TAULUKKO)

    rivit = []

    for lasku in laskut:

        summa = lasku["summa"]

        if isinstance(summa, str) and summa.startswith("*"):
            summa_html = h(summa)
            data_value = summa[1:]
        else:
            summa_html = rahaksi(summa)
            data_value = summa_html

        rivit.append([
            {
                "html": (
                    f'<a href="{h(lasku["tiedosto"])}" target="_blank">'
                    f'{h(lasku["paiva"])}'
                    f'</a>'
                ),
                "data_value": lasku["paiva"],
            },
            {
                "html": (
                    f'<a href="#" '
                    f'onclick="haeSaajanPaivalla(\'{h(lasku["paiva"])}\'); return false;">'
                    f'{h(lasku["saaja"])}'
                    f'</a>'
                    if (
                            isinstance(lasku["summa"], str)
                            and lasku["summa"].startswith("*")
                    )
                    else h(lasku["saaja"])
                ),
            },
            {
                "html": h(lasku["aihe"]),
            },
            {
                "html": summa_html,
                "data_value": data_value,
            },
        ])

    rivit_html, rivit_json = muodosta_rivit(rivit)

    return f"""<!DOCTYPE html>
<html lang="fi">
<head>
<meta charset="UTF-8">
<title>E-laskut</title>
<style>
{muodosta_css(TAULUKKO)}
</style>
</head>
<body>
<h1>E-laskut</h1>
<div class="sticky-header">
    <div id="maara">
        <span id="laskurivimaara"></span>
        <span id="summa"></span>
    </div>
</div>
<table id="laskut">
<thead>
<tr>{otsikot}</tr>
</thead>
<tbody>
{rivit_html}
</tbody>
</table>

<script>
function haeSaajanPaivalla(paiva) {{
    haut[1].value = paiva;
    suodata();
}}
{muodosta_javascript(TAULUKKO, rivit_json)}
</script>
</body>
</html>
"""


# ============================================================
# Pääohjelma
# ============================================================

def main():
    print(f"E-laskut {VERSION}")
    print("Luetaan XML-tiedostot:")
    print(Path.cwd())
    print()

    laskut = lue_xml_tiedostot()

    print()
    print(f"Luettu {len(laskut)} laskuriviä.")

    html_teksti = muodosta_html(laskut)

    TULOSTIEDOSTO.write_text(html_teksti, encoding="utf-8")

    print()
    print(f"Kirjoitettu: "f"{TULOSTIEDOSTO.resolve()}")


if __name__ == "__main__":
    main()
