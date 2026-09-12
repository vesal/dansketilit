# taulukko_html.py
import json
import re
from dataclasses import dataclass
import html
from typing import Any

"""
HTML-taulukon muodostamiseen liittyviä aputoimintoja.

Copyright (c) 2026 vesal & ChatGPT. All rights reserved.
"""

VERSION = "1.0.2"


@dataclass(frozen=True)
class TaulukkoAsetukset:
    """
    Taulukon asetukset.

    :param sarakkeet: Taulukon sarakeotsikot.
    :param numeeriset_sarakkeet: Numeeristen sarakkeiden indeksit.
    :param summa_sarake: Summan sisältävän sarakkeen indeksi.
    :param sarakeleveydet: Sarakkeiden leveydet pikseleinä.
    :param koontirivit: Onko taulukossa koontirivejä.
    """

    sarakkeet: list[str]
    numeeriset_sarakkeet: list[int]
    summa_sarake: int
    sarakeleveydet: list[int]
    koontirivit: bool = False


def muodosta_rivit(
    rivit: list[list[dict[str, Any]]],
) -> tuple[str, str]:
    """
    Muodostaa HTML-taulukon rivit ja JavaScriptin rivitiedot.

    :param rivit: Taulukon rivit soluineen.
    :return: HTML-rivit ja JSON-muotoinen rivitieto.
    """

    html_rivit = []
    js_rivit = []

    for rivi in rivit:
        solut_html = []
        tekstit = []
        arvot = []

        for solu in rivi:
            solu_html = solu["html"]
            if "data_value" in solu:
                solut_html.append(
                    f'<td data-value="{html.escape(str(solu["data_value"]))}">'
                    f'{solu_html}</td>'
                )
            else:
                solut_html.append(f"<td>{solu_html}</td>")

            teksti = html.unescape(re.sub(r"<[^>]*>", "", solu_html))
            tekstit.append(teksti)

            arvot.append(str(solu.get("data_value", teksti)))

        html_rivit.append("<tr>" + "".join(solut_html) + "</tr>")

        js_rivit.append({
            "tekstit": tekstit,
            "arvot": arvot,
            "html": "<tr>" + "".join(solut_html) + "</tr>",
        })

    rivit_html = "\n".join(html_rivit)
    rivit_json = json.dumps(js_rivit, ensure_ascii=False)

    return rivit_html, rivit_json


def muodosta_taulukko(
    asetukset: TaulukkoAsetukset,
) -> tuple[str, str]:
    """
    Muodostaa HTML-taulukon otsikot ja sarakeleveydet.

    :param asetukset: Taulukon asetukset.
    :return: Taulukon otsikot ja sarakeleveydet HTML/CSS-muodossa.
    """

    otsikot_html = []

    for indeksi, otsikko in enumerate(asetukset.sarakkeet):

        if indeksi == asetukset.summa_sarake:
            placeholder = "esim. >=1000<=2000"
        else:
            placeholder = "regexp"

        otsikot_html.append(
            f"""
            <th onclick="sortTable({indeksi})">
                <div>{html.escape(otsikko)}</div>
                <div class="haku">
                    <input
                        id="haku-{indeksi}"
                        type="text"
                        placeholder="{placeholder}"
                        onfocus="this.select()"
                        oninput="suodata()"
                    >
                    <span
                        class="tyhjenna"
                        onclick="event.stopPropagation(); tyhjennaHaku(this)"
                    >×</span>
                </div>
            </th>
            """
        )

    otsikot = "\n".join(otsikot_html)

    leveydet = "\n".join(
        f"    th:nth-child({i + 1}), td:nth-child({i + 1}) {{ width: {leveys}px; }}"
        for i, leveys in enumerate(asetukset.sarakeleveydet)
    )

    for indeksi in asetukset.numeeriset_sarakkeet:
        sarake = indeksi + 1

        leveydet += f"""th:nth-child({sarake}), td:nth-child({sarake}) {{
            text-align: right;
        }}
        """
    return otsikot, leveydet


def muodosta_css(asetukset: TaulukkoAsetukset) -> str:
    """
    Muodostaa taulukon yhteisen CSS:n.

    :param asetukset: Taulukon asetukset.
    :return: Taulukon CSS-tyylit.
    """

    leveydet = "\n".join(
        f"    th:nth-child({i + 1}), td:nth-child({i + 1}) {{ width: {leveys}px; }}"
        for i, leveys in enumerate(asetukset.sarakeleveydet)
    )

    tasaukset = "\n".join(
        f"""th:nth-child({indeksi + 1}), td:nth-child({indeksi + 1}) {{
            text-align: right;
        }}
        """
        for indeksi in asetukset.numeeriset_sarakkeet
    )

    return f"""
    body {{ font-family: Arial, sans-serif; margin: 20px; }}
    h1 {{ margin-bottom: 5px; }}
    .info {{ color: #666; margin-bottom: 15px; }}
    table {{
        border-collapse: collapse;
        table-layout: fixed;
        width: fit-content;
    }}
    .sticky-header {{
        position: sticky;
        top: 0;
        background: white;
        z-index: 10;
    }}

    thead {{
        position: sticky;
        top: calc(var(--sticky-header-height) - 2px);
        z-index: 10;
        background: #eee;
    }}
        
    th {{
        cursor: pointer;
    }}
    th, td {{
        border: 1px solid #ccc;
        padding: 5px 8px;
        text-align: left;
        overflow: hidden;
    }}
    th:hover {{ background: #ddd; }}
    tr:nth-child(even) {{ background: #f8f8f8; }}
    a {{ text-decoration: none; }}
    a:hover {{ text-decoration: underline; }}
    .haku {{
        position: relative;
    }}
    .haku input {{
        width: 100%;
        box-sizing: border-box;
        padding-right: 18px;
    }}
    .tyhjenna {{
        position: absolute;
        right: 5px;
        top: 50%;
        transform: translateY(-50%);
        cursor: pointer;
        font-size: 13px;
        color: #888;
    }}
    .tyhjenna:hover {{
        color: #000;
    }}    

{leveydet}
{tasaukset}
    """


def muodosta_javascript(asetukset: TaulukkoAsetukset, rivit_json: str) -> str:
    """
    Muodostaa taulukon yhteisen JavaScriptin.

    :param asetukset: Taulukon asetukset.
    :param rivit_json: Taulukon rivit JSON-muodossa JavaScriptia varten.
    :return: Taulukon JavaScript-koodi.
    """

    numeeriset = asetukset.numeeriset_sarakkeet
    summa_sarake = asetukset.summa_sarake
    koontirivit_js = str(asetukset.koontirivit).lower()

    rivit_js = rivit_json

    return f"""
    const RIVIT = {rivit_js};
    
    const taulu = document.getElementById("laskut");
    const haut = taulu.querySelectorAll("thead input");
    const tbody = taulu.querySelector("tbody");
    const laskurivimaara = document.getElementById("laskurivimaara");

    const summa = document.getElementById("summa");
    
    const NUMEERISET_SARAKKEET = new Set({numeeriset});
    const SUMMA_SARAKE = {summa_sarake};
    const KOONTIRIVIT = {koontirivit_js};

// ==========================================================
// Summan näyttäminen
// ==========================================================

function rahaksi(arvo) {{
    return arvo.toLocaleString("fi-FI", {{
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }}
    );
}}

laskurivimaara.addEventListener("click", event => {{
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
    const laskeKoontirivit = KOONTIRIVIT && summaEhto.startsWith("*");

    rivit.forEach(rivi => {{
        if (rivi.style.display !== "none") {{
            nakyvat++;
            const solu = rivi.cells[SUMMA_SARAKE];
            const arvo = parseFloat(solu.dataset.value);

            if (
                (
                    !KOONTIRIVIT ||
                    !solu.textContent.trim().startsWith("*") ||
                    laskeKoontirivit
                ) &&
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
        + RIVIT.length
        + "</span>"
        + " laskuriviä";

    summa.textContent =
        "Summa: "
        + rahaksi(yhteensa)
        + " €";
}}


// ==========================================================
// Epäyhtälöiden käsittely
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
    ehto = ehto.toLowerCase().trim();

    // Ei ehtoa -> kutsuja käsittelee tämän regexpinä.
    if (!/^[<>=]/.test(ehto)) return null;

    const osumat = [
        ...ehto.matchAll(
            /(<=|>=|=|<|>)\\s*([^<>=\\s]+)/g
        )
    ];
    
    if (typeof arvo === "string") arvo = arvo.trim().toLowerCase();
    const koottu = osumat.map(osuma => osuma[0]).join("");

    if (
        !osumat.length ||
        koottu.replace(/\\s/g, "") !==
        ehto.replace(/\\s/g, "")
    ) return false;

    for (const osuma of osumat) {{
        const operaattori = osuma[1];
        let raja = osuma[2].trim().toLowerCase();

        if (numeerinen) {{
            raja = parseFloat(raja.replace(",", "."));
            if (Number.isNaN(raja)) return false;
        }}

        if (operaattori === "<" && !(arvo < raja)) return false;
        if (operaattori === "<=" && !(arvo <= raja)) return false;
        if (operaattori === "=" && !(arvo === raja)) return false;
        if (operaattori === ">" && !(arvo > raja)) return false;
        if (operaattori === ">=" && !(arvo >= raja)) return false;
    }}

    return true;
}}


function haeRivit() {{
    const table = document.getElementById("taulukko");
    return Array.from(table.tBodies[0].rows);
}}


let lajitteluSarake = -1;
let lajitteluKaanteinen = false;


function sortTable(indeksi) {{
    if (lajitteluSarake === indeksi) {{
        lajitteluKaanteinen = !lajitteluKaanteinen;
    }} else {{
        lajitteluSarake = indeksi;
        lajitteluKaanteinen = false;
    }}

    const rivit = [...RIVIT];
    const numeerinen = NUMEERISET_SARAKKEET.has(indeksi);

    rivit.sort((a, b) => {{
        let arvoA = a.arvot[indeksi];
        let arvoB = b.arvot[indeksi];

        if (numeerinen) {{
            arvoA = parseFloat(arvoA);
            arvoB = parseFloat(arvoB);
            if (Number.isNaN(arvoA)) arvoA = 0;
            if (Number.isNaN(arvoB)) arvoB = 0;
        }} else {{
            arvoA = String(arvoA).toLowerCase();
            arvoB = String(arvoB).toLowerCase();
        }}

        if (arvoA < arvoB) return lajitteluKaanteinen ? 1 : -1;
        if (arvoA > arvoB) return lajitteluKaanteinen ? -1 : 1;

        return 0;
    }});

    RIVIT.length = 0;
    RIVIT.push(...rivit);

    suodata();
}}

    
function suodata() {{
    const naytettavat = [];

    RIVIT.forEach(rivi => {{
        let nayta = true;

        haut.forEach((haku, indeksi) => {{
            if (!nayta) return;

            let ehto = haku.value.trim().toLowerCase();
            if (!ehto) return;

            const teksti = rivi.tekstit[indeksi].trim().toLowerCase();

            if (
                KOONTIRIVIT &&
                indeksi === SUMMA_SARAKE &&
                ehto.startsWith("*")
            ) {{
                ehto = ehto.substring(1).trim();
                if (!teksti.startsWith("*")) {{
                    nayta = false;
                    return;
                }}
                if (!ehto) return;
            }}
            
            if (!ehto && vainKoontirivit) return;
                
            const numeerinen =  NUMEERISET_SARAKKEET.has(indeksi);
            const arvo = numeerinen
                ? parseFloat(rivi.arvot[indeksi])
                : teksti;

            const tulos = ehtoTäsmää(arvo, ehto, numeerinen);

            if (tulos !== null) {{
                if (!tulos) nayta = false;
                return;
            }}

            try {{
                const regex = new RegExp(ehto, "i");
                if (!regex.test(teksti)) nayta = false;
            }} catch (virhe) {{
                if (!teksti.includes(ehto)) nayta = false;
            }}
        }});

        if (nayta) naytettavat.push(rivi);
    }});

    tbody.innerHTML = naytettavat.map(rivi => rivi.html).join("");
    paivitaMaara();
}}


function tyhjennaHaku(element) {{
    const input = element.previousElementSibling;
    input.value = "";
    suodata();
}}


let suodatusAjastin = null;

haut.forEach(haku => {{
    haku.addEventListener("input", () => {{
            clearTimeout(suodatusAjastin);
            suodatusAjastin = setTimeout(suodata, 100);
        }}
    );  
    
    haku.addEventListener("click", event => {{ event.stopPropagation(); }});
}});    

paivitaMaara();  
const sticky_header = document.querySelector(".sticky-header");
document.documentElement.style.setProperty(
    "--sticky-header-height",
    `${{sticky_header.offsetHeight}}px`
);
"""
