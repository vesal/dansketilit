from pathlib import Path
from typing import Optional
import re
import html
import xml.etree.ElementTree as eT

from lasku_html import tee_lasku_html
from taulukko_html import TaulukkoAsetukset, muodosta_taulukko, muodosta_rivit


# ============================================================
# Luetaan kaikki XML-tiedostot ./xml-hakemistosta
# ja elaskut ./pdf-hakemistosta
# ja muodostetaan niistä
# laskulista, joka kirjoitetaan HTML-muodossa ./laskut.html
# laskuja voi etsiä ja suodattaa selaimessa.
# ============================================================


VERSION = "1.1.4"

# ============================================================
# Asetukset
# ============================================================

TAULUKKO = TaulukkoAsetukset(
    sarakkeet=["Päivä", "Saaja", "Aihe", "Summa"],
    numeeriset_sarakkeet=[3],
    summa_sarake=3,
    sarakeleveydet=[110, 220, 300, 90],
)


XML_HAKEMISTO = Path("./xml")
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
    """Muuttaa päivämäärän muotoon YYYY-MM-DD."""
    if not paiva:
        return ""

    paiva = paiva.strip()

    # DD.MM.YYYY
    match = re.fullmatch(
        r"(\d{2})\.(\d{2})\.(\d{4})",
        paiva,
    )

    if match:
        paiva, kuukausi, vuosi = match.groups()
        return f"{vuosi}-{kuukausi}-{paiva}"

    # YYYYMMDD
    if len(paiva) == 8 and paiva.isdigit():
        return (
            f"{paiva[0:4]}-"
            f"{paiva[4:6]}-"
            f"{paiva[6:8]}"
        )

    return paiva


def tagin_nimi(tag):
    """Palauttaa XML-tagista pelkän nimen ilman namespacea."""
    return tag.rsplit("}", 1)[-1]


def etsi(element, nimi) -> Optional[eT.Element]:
    """Etsii XML:stä ensimmäisen annetun nimisen elementin."""
    for child in element.iter():
        if tagin_nimi(child.tag) == nimi:
            return child

    return None


def etsi_teksti(element, nimi) -> str:
    """Etsii annetun nimisen XML-elementin tekstin."""
    child = etsi(element, nimi)

    if child is None or child.text is None:
        return ""

    return child.text.strip()


def korjaa_teksti(teksti):
    """Korjaa tunnetut XML:n tekstimuotovirheet."""
    teksti = (teksti or "").strip()

    for vanha, uusi in TEKSTIKORJAUKSET.items():
        teksti = teksti.replace(vanha, uusi)

    return teksti


def lue_summa(teksti):
    """Muuttaa summan numeroksi."""
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

        2026-09-28 - Pohjola Vakuutus Oy -
        Vakuutuslaskut ja re - 81.14 - .xml
    """

    stem = polku.stem.rstrip()

    osat = stem.split(" - ")

    if len(osat) < 3:
        return "", stem, ""

    paiva = osat[0].strip()
    saaja = osat[1].strip()
    aihe = osat[2].strip()

    return paiva, saaja, aihe


# ============================================================
# PDF-tiedostojen lukeminen
# ============================================================

def lue_pdf_tiedostot():
    """Lukee ./pdf-hakemiston laskutiedostot."""

    laskut = []

    if not Path("./pdf").is_dir():
        return laskut

    for polku in sorted(Path("./pdf").iterdir()):

        # Hakemistot, kuten *_files, jätetään rauhaan.
        if not polku.is_file():
            continue

        # Nimen pitää alkaa päivämäärällä.
        osat = polku.stem.split(" - ")

        if len(osat) < 5:
            continue

        paiva = osat[0].strip()
        saaja = osat[1].strip()

        # Summa on toiseksi viimeinen osa.
        summa_teksti = osat[-2].strip()

        # Aihe voi sisältää " - " -erottimia.
        aihe = " - ".join(
            osa.strip()
            for osa in osat[2:-2]
        )

        summa = lue_summa(summa_teksti)

        if not paiva or not saaja:
            continue

        # Linkki tehdään tiedostoon sellaisenaan.
        tiedosto = (
            Path("pdf") / polku.name
        ).as_posix()

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

def lue_laskut():
    laskut = []

    xml_tiedostot = sorted(
        XML_HAKEMISTO.glob("*.xml"),
        key=lambda p: p.name.lower(),
    )

    for polku in xml_tiedostot:

        try:
            juuri = eT.parse(polku).getroot()

        except Exception as e:
            print(
                f"XML-virhe tiedostossa "
                f"{polku.name}: {e}"
            )
            continue

        # ----------------------------------------------------
        # Tee tästä XML:stä luettava HTML-näkymä.
        # ----------------------------------------------------

        html_polku = tee_lasku_html(
            polku,
            HTML_HAKEMISTO,
        )

        filename_paiva, filename_saaja, filename_aihe = (
            pura_tiedostonimi(polku)
        )

        seller_name = korjaa_teksti(
            etsi_teksti(
                juuri,
                "SellerOrganisationName",
            )
        )

        invoice_total = lue_summa(
            etsi_teksti(
                juuri,
                "InvoiceTotalVatIncludedAmount",
            )
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
                etsi_teksti(
                    row,
                    "ArticleName",
                )
            )

            row_free_text = etsi_teksti(
                row,
                "RowFreeText",
            )

            # Järjestys:
            # 1. RowVatIncludedAmount
            # 2. RowVatExcludedAmount
            # 3. RowAmount
            summa = lue_summa(
                etsi_teksti(
                    row,
                    "RowVatIncludedAmount",
                )
                or etsi_teksti(
                    row,
                    "RowVatExcludedAmount",
                )
                or etsi_teksti(
                    row,
                    "RowAmount",
                )
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

            # ------------------------------------------------
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
                    ostopaiva = muotoile_paiva(
                        match.group(1)
                    )
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

        onko_danske = (
            seller_name == "Danske Bank"
        )

        elasku_rivi = None

        if onko_danske:

            for rivi in rivit:

                if rivi["article_name"] == "E-lasku":
                    elasku_rivi = rivi
                    break

        if (
            elasku_rivi is not None
            and invoice_total is not None
        ):

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
                    "summa": f"*{invoice_total:.2f}",
                    "tiedosto": (
                        Path("html")
                        / html_polku.name
                    ).as_posix(),
                }
            )

        # ----------------------------------------------------
        # Varsinaiset laskurivit.
        # ----------------------------------------------------

        for rivi in rivit:

            article_name = rivi["article_name"]

            # Dansken E-lasku-rivi käsiteltiin jo yllä.
            if (
                onko_danske
                and article_name == "E-lasku"
            ):
                continue

            summa = rivi["summa"]

            saaja = filename_saaja

            if (
                    onko_danske
                    and rivi["ostopaiva"]
            ):
                saaja = f"{filename_saaja} - {filename_paiva}"

            if filename_aihe and article_name:
                aihe = (
                    f"{filename_aihe} / "
                    f"{article_name}"
                )

            elif article_name:
                aihe = article_name

            else:
                aihe = filename_aihe

            paiva = filename_paiva

            # Dansken korttilaskuissa käytetään
            # ostotapahtuman todellista ostopäivää.
            if (
                onko_danske
                and rivi["ostopaiva"]
            ):
                paiva = rivi["ostopaiva"]

            laskut.append(
                {
                    "paiva": paiva,
                    "saaja": saaja,
                    "aihe": aihe,
                    "summa": summa,
                    "tiedosto": (
                        Path("html")
                        / html_polku.name
                    ).as_posix(),
                }
            )

    # --------------------------------------------------------
    # Lisätään ./pdf-hakemiston tiedostot.
    # --------------------------------------------------------

    laskut.extend(
        lue_pdf_tiedostot()
    )

    # Uusin laskurivi ensin.
    return sorted(
        laskut,
        key=lambda x: x["paiva"],
        reverse=True,
    )


# ============================================================
# HTML-apufunktiot
# ============================================================

def h(text):
    """HTML-escape."""
    return html.escape(str(text or ""))


def rahaksi(summa):
    """Muuttaa summan kahden desimaalin tekstiksi."""
    if summa is None:
        return ""

    return f"{summa:.2f}"


# ============================================================
# Laskulistan HTML
# ============================================================

def muodosta_html(laskut):
    otsikot, leveydet = muodosta_taulukko(TAULUKKO)

    rivit = []

    for lasku in laskut:

        summa = lasku["summa"]

        if isinstance(summa, str) and summa.startswith("*"):
            summa_html = h(summa)
            data_value = summa[1:]
        else:
            summa_html = rahaksi(summa)
            data_value = f"{summa:.2f}"

        rivit.append([
            {
                "html": (
                    f'<a href="{h(lasku["tiedosto"])}">'
                    f'{h(lasku["paiva"])}'
                    f'</a>'
                ),
                "data_value": lasku["paiva"],
            },
            {
                "html": h(lasku["saaja"]),
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

body {{
    font-family: Arial, sans-serif;
    margin: 20px;
}}

table {{
    border-collapse: collapse;
    width: auto;
    table-layout: fixed;
}}

th,
td {{
    border: 1px solid #bbb;
    padding: 4px 6px;
    text-align: left;
    vertical-align: top;
}}

th {{
    position: sticky;
    top: 0;
    background: white;
    z-index: 2;
    cursor: pointer;
    user-select: none;
}}

th:hover {{
    background: #eee;
}}

th input {{
    box-sizing: border-box;
    display: block;
    width: 100%;
    margin-top: 4px;
    padding: 2px 4px;
    font-size: inherit;
    font-weight: normal;
    cursor: text;
}}

{leveydet}

#maara {{
    margin-bottom: 8px;
    font-size: 16px;
}}

#summa {{
    margin-left: 30px;
}}

#kaikki {{
    cursor: pointer;
    text-decoration: underline;
}}

#kaikki:hover {{
    background: #eee;
}}

</style>
</head>


<body>
<div id="maara">
    <span id="laskurivimaara"></span>
    <span id="summa"></span>
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

const taulu =
    document.getElementById("laskut");

const tbody =
    taulu.querySelector("tbody");

const haut =
    taulu.querySelectorAll(
        "thead input"
    );

const laskurivimaara =
    document.getElementById(
        "laskurivimaara"
    );

const summa =
    document.getElementById("summa");


// ==========================================================
// Summan näyttäminen
// ==========================================================

function rahaksi(arvo) {{

    return arvo.toLocaleString(
        "fi-FI",
        {{
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }}
    );
}}

laskurivimaara.addEventListener(
    "click",
    event => {{
        if (event.target.id === "kaikki") {{
            location.reload();
        }}
    }}
);

function paivitaMaara() {{

    const rivit = tbody.querySelectorAll("tr");

    let nakyvat = 0;
    let yhteensa = 0;

    const summaEhto = haut[SUMMA_SARAKE].value.trim();
    const laskeKoontirivit = summaEhto.startsWith("*");

    rivit.forEach(rivi => {{

        if (rivi.style.display !== "none") {{
            nakyvat++;
            const solu = rivi.cells[SUMMA_SARAKE];
            const arvo = parseFloat(solu.dataset.value);

            if (
                (!solu.textContent.trim().startsWith("*") ||
                laskeKoontirivit) &&
                !Number.isNaN(arvo)
            ) {{
                yhteensa += arvo;
            }}
        }}
    }});


    laskurivimaara.innerHTML =
        nakyvat
        + " / "
        + "<span id='kaikki'>"
        + rivit.length
        + "</span>"
        + " laskuriviä";

    summa.textContent =
        "Summa: "
        + rahaksi(yhteensa)
        + " €";
}}


// ==========================================================
// Summan ehtohaku
//
// Esimerkiksi:
//
//   =10
//   >10
//   >=10
//   <10
//   <=10
//   >=5<=20
//
// ==========================================================

function ehtoTäsmää(arvo, ehto, numeerinen) {{

    ehto = ehto.trim();

    // Ei ehtoa -> kutsuja käsittelee tämän regexpinä.
    if (!/^[<>=]/.test(ehto))
        return null;

    const osumat = [
        ...ehto.matchAll(
            /(<=|>=|=|<|>)\\s*([^<>=\\s]+)/g
        )
    ];
    
    if (typeof arvo === "string") {{
        arvo = arvo.toLowerCase().trim();
    }}

    ehto = ehto.toLowerCase().trim();

    const koottu =
        osumat.map(osuma => osuma[0]).join("");

    if (
        !osumat.length ||
        koottu.replace(/\\s/g, "") !==
        ehto.replace(/\\s/g, "")
    )
        return false;

    for (const osuma of osumat) {{

        const operaattori = osuma[1];
        let raja = osuma[2];

        if (numeerinen) {{
            raja = parseFloat(
                raja.replace(",", ".")
            );

            if (Number.isNaN(raja))
                return false;
        }}

        if (operaattori === "<" && !(arvo < raja))
            return false;

        if (operaattori === "<=" && !(arvo <= raja))
            return false;

        if (operaattori === "=" && !(arvo === raja))
            return false;

        if (operaattori === ">" && !(arvo > raja))
            return false;

        if (operaattori === ">=" && !(arvo >= raja))
            return false;
    }}

    return true;
}}

// ==========================================================
// Suodatus
// ==========================================================

const NUMEERISET_SARAKKEET = new Set({TAULUKKO.numeeriset_sarakkeet});
const SUMMA_SARAKE = {TAULUKKO.summa_sarake};

function suodata() {{
    const rivit = tbody.querySelectorAll("tr");

    rivit.forEach(rivi => {{
        const solut = rivi.querySelectorAll("td");
        let nayta = true;

        haut.forEach((haku, indeksi) => {{
            if (!nayta)
                return;

            let ehto = haku.value.trim();

            if (!ehto)
                return;

            const teksti =
                solut[indeksi].textContent.trim();

            let vainKoontirivit = false;

            if (
                indeksi === SUMMA_SARAKE &&
                ehto.startsWith("*")
            ) {{
                vainKoontirivit = true;
                ehto = ehto.substring(1).trim();

                if (!teksti.startsWith("*")) {{
                    nayta = false;
                    return;
                }}
            }}

            const numeerinen =
                NUMEERISET_SARAKKEET.has(indeksi);

            const arvo = numeerinen
                ? parseFloat(
                    solut[indeksi].dataset.value
                )
                : teksti;

            // Pelkkä "*" tarkoittaa:
            // kaikki koontirivit.
            if (!ehto && vainKoontirivit)
                return;

            const tulos = ehtoTäsmää(
                arvo,
                ehto,
                numeerinen
            );

            if (tulos !== null) {{
                if (!tulos)
                    nayta = false;

                return;
            }}

            try {{
                const regex =
                    new RegExp(ehto, "i");

                if (!regex.test(teksti))
                    nayta = false;

            }} catch (virhe) {{
                if (!teksti.toLowerCase().includes(
                    ehto.toLowerCase()
                ))
                    nayta = false;
            }}
        }});

        rivi.style.display =
            nayta ? "" : "none";
    }});

    paivitaMaara();
}}


// ==========================================================
// Hakukentät
// ==========================================================

haut.forEach(haku => {{

    haku.addEventListener(
        "input",
        suodata
    );


    haku.addEventListener(
        "click",
        event => {{
            event.stopPropagation();
        }}
    );
}});


// ==========================================================
// Lajittelu
// ==========================================================

let suunnat = [
    1,
    1,
    1,
    1
];


taulu
    .querySelectorAll("thead th")
    .forEach(
        (otsikko, indeksi) => {{

            otsikko.addEventListener(
                "click",
                () => {{

                    const rivit =
                        Array.from(
                            tbody.querySelectorAll(
                                "tr"
                            )
                        );


                    rivit.sort(
                        (a, b) => {{

                            const aSolut =
                                a.querySelectorAll(
                                    "td"
                                );

                            const bSolut =
                                b.querySelectorAll(
                                    "td"
                                );


                            // Summa lajitellaan
                            // numerona.
                            if (NUMEERISET_SARAKKEET.has(indeksi)) {{
                            
                                const av =
                                    parseFloat(
                                        aSolut[indeksi].dataset.value
                                    );
                            
                                const bv =
                                    parseFloat(
                                        bSolut[indeksi].dataset.value
                                    );
                            
                                const aOnNumero = !Number.isNaN(av);
                                const bOnNumero = !Number.isNaN(bv);
                            
                                if (aOnNumero && !bOnNumero)
                                    return -1;
                            
                                if (!aOnNumero && bOnNumero)
                                    return 1;
                            
                                if (!aOnNumero && !bOnNumero)
                                    return 0;
                            
                                return (
                                    (av - bv)
                                    * suunnat[indeksi]
                                );
                            }}

                            // Muut sarakkeet tekstinä.
                            const av =
                                aSolut[indeksi]
                                    .textContent
                                    .trim();


                            const bv =
                                bSolut[indeksi]
                                    .textContent
                                    .trim();


                            return (
                                av.localeCompare(
                                    bv,
                                    "fi",
                                    {{
                                        numeric: true,
                                        sensitivity: "base"
                                    }}
                                )
                                *
                                suunnat[indeksi]
                            );
                        }}
                    );


                    suunnat[indeksi] *= -1;


                    rivit.forEach(
                        rivi =>
                            tbody.appendChild(rivi)
                    );


                    // Lajittelu ei muuta näkyvien
                    // rivien määrää tai summaa,
                    // mutta päivitetään varmuuden vuoksi.
                    paivitaMaara();
                }}
            );
        }}
    );


// ==========================================================
// Alkuperäinen näyttö
// ==========================================================

paivitaMaara();

</script>

</body>

</html>
"""


# ============================================================
# Pääohjelma
# ============================================================

def main():

    print(
        f"E-laskut {VERSION}"
    )

    print(
        "Luetaan XML-tiedostot:"
    )

    print(
        Path.cwd()
    )

    print()

    laskut = lue_laskut()

    print()

    print(
        f"Luettu {len(laskut)} laskuriviä."
    )

    html_teksti = muodosta_html(laskut)

    TULOSTIEDOSTO.write_text(
        html_teksti,
        encoding="utf-8",
    )

    print()

    print(
        f"Kirjoitettu: "
        f"{TULOSTIEDOSTO.resolve()}"
    )


if __name__ == "__main__":
    main()
