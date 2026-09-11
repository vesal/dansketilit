# nimea_laskut.py
from pathlib import Path
import re

VERSION = "1.0.2"


HAKEMISTO = Path("./pdf")

SAAJAT = (
    "Jyväskylän kaupunki",
    "KESKI-SUOMEN MEDIA OY",
    "PÄIJÄNNE MEDIA OY",
    "Aktia Bank Abp",
    "Elenia Verkko Oyj",
    "Telia Finland Oyj",
    "Mustankorkea Oy",
    "MUSTANKORKEA OY",
    "Alva-yhtiöt Oy",
    "Oomi Oy",
    "DNA Oyj",
)


def uusi_nimi(polku):
    if not polku.is_file():
        return None

    if polku.suffix.lower() not in {".pdf", ".html", ".htm"}:
        return None

    match = re.match(r"^(\d{4}-\d{2}-\d{2})\s+(.+)$", polku.stem)
    if not match:
        return None

    paiva = match.group(1)
    loppu = match.group(2).strip()

    match = re.search(r"\s+(-?\d+[.,]\d+)$", loppu)
    if not match:
        return None

    summa = match.group(1)
    alku = loppu[:match.start()].strip()

    for saaja in SAAJAT:
        if alku.startswith(saaja):
            aihe = alku[len(saaja):].strip()
            return f"{paiva} - {saaja} - {aihe} - {summa} - {polku.suffix}"

    return None


def main():
    print(f"nimea_laskut.py v{VERSION}")
    print()

    for polku in sorted(HAKEMISTO.iterdir()):
        uusi = uusi_nimi(polku)

        if uusi is None:
            continue

        uusi_polku = polku.with_name(uusi)

        if uusi_polku == polku:
            continue

        if uusi_polku.exists():
            print(f"OHITETAAN, kohde on jo olemassa:")
            print(f"  {uusi_polku.name}")
            continue

        print(f"{polku.name}")
        print(f"  -> {uusi_polku.name}")

        polku.rename(uusi_polku)


if __name__ == "__main__":
    main()
