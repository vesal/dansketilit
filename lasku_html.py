from pathlib import Path
from urllib.request import urlopen

from lxml import etree

"""
Muuntaa Finvoice-XML:n HTML:ksi.
"""

VERSION = "1.0.2"

XSL_URL = "https://file.finanssiala.fi/finvoice/css/270923/Finvoice.xsl"

# Finvoice-finnish.xsl on tämän Python-tiedoston vieressä.
# XSL_TIEDOSTO = Path(__file__).with_name("Finvoice-finnish.xsl")
XSL_TIEDOSTO = Path(__file__).with_name("Finvoice.xsl")

# Dansken julkinen Finvoice-tyylitiedosto.
# FINVOICE_CSS_URL = (
#    "https://verkkopankki.danskebank.fi/html/css/Finvoice.css"
# )

FINVOICE_CSS_URL = (
    "https://file.finanssiala.fi/finvoice/css/270923/Finvoice.css"
)

# Oma lisätyyli: lasku ei veny leveällä näytöllä valtavaksi.
OMA_CSS = """
<style type="text/css">
@media screen {
    body {
        max-width: 800px;
        margin-left: auto;
        margin-right: auto;
    }
}
</style>
"""


def hae_xsl() -> Path:
    """
    Hakee Finvoice.xsl-tiedoston, jos sitä ei ole jo ladattu
    ja tallentaa sen tämän Python-tiedoston viereen.
    return: Path XSL-tiedostoon.
    """
    if XSL_TIEDOSTO.exists():
        return XSL_TIEDOSTO

    XSL_TIEDOSTO.parent.mkdir(parents=True, exist_ok=True)

    with urlopen(XSL_URL) as response:
        XSL_TIEDOSTO.write_bytes(response.read())

    return XSL_TIEDOSTO


def tee_lasku_html(xml_polku: Path, tuloshakemisto: Path) -> Path:
    """
    Muuntaa Finvoice-XML:n HTML:ksi Dansken Finvoice-finnish.xsl:n avulla.
    param xml_polku: Path XML-tiedostoon.
    param tuloshakemisto: Path hakemistoon, johon HTML-tiedosto tallennetaan.
    return: Path HTML-tiedostoon.
    """
    hae_xsl()
    if not XSL_TIEDOSTO.exists():
        raise FileNotFoundError(
            f"XSL-tiedostoa ei löytynyt: {XSL_TIEDOSTO}"
        )

    tuloshakemisto.mkdir(parents=True, exist_ok=True)

    parser = etree.XMLParser(
        remove_blank_text=False,
        recover=False,
    )

    xml_tree = etree.parse(str(xml_polku), parser=parser)
    xsl_tree = etree.parse(str(XSL_TIEDOSTO), parser=parser)

    transform = etree.XSLT(xsl_tree)
    html_tree = transform(xml_tree)

    html_text = str(html_tree)

    # Muutetaan Dansken suhteellinen CSS-osoite absoluuttiseksi.
    html_text = html_text.replace(
        'href="Finvoice.css"',
        f'href="{FINVOICE_CSS_URL}"',
    )

    html_text = html_text.replace(
        'href="/html/css/Finvoice.css"',
        f'href="{FINVOICE_CSS_URL}"',
    )

    html_text = html_text.replace(
        'href="/test-html/css/Finvoice.css"',
        f'href="{FINVOICE_CSS_URL}"',
    )

    html_text = html_text.replace(
        'href="/syst-html/css/Finvoice.css"',
        f'href="{FINVOICE_CSS_URL}"',
    )

    # Lisätään oma näytölle tarkoitettu maksimileveys.
    if "</head>" in html_text:
        html_text = html_text.replace(
            "</head>",
            OMA_CSS + "\n</head>",
            1,
        )
    else:
        # Varmuuden vuoksi, jos XSL joskus tuottaa HTML:n ilman head-osaa.
        html_text = OMA_CSS + "\n" + html_text

    html_polku = tuloshakemisto / f"{xml_polku.stem}.html"

    html_polku.write_text(
        html_text,
        encoding="utf-8",
    )

    return html_polku
