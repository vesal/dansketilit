from pathlib import Path
import re
from datetime import datetime
import zipfile

from pypdf import PdfReader

"""
Nimeää Tiliote-alkuiset PDF-tiedostot uudelleen PDF:n sisällön perusteella.
Esimerkiksi:
    Tiliote FI63 8000 2912 3456 78 - 2023-01-31.pdf
    ->
    2023-01-01 - Tiliote - FI63 8000 2912 3456 78 - .pdf
    
Copyright (c) 2026 vesal & ChatGPT. All rights reserved.
"""

VERSION = "1.0.0"

# PDF-tiedostot tästä hakemistosta
ARKISTOPATH = Path("arkisto")

OTTEET_PATH = Path("otteet")


def lue_pdf_teksti(pdf_tiedosto: Path) -> str:
    """
    Lukee koko PDF-tiedoston tekstin.

    :param pdf_tiedosto: Luettavan PDF-tiedoston polku.
    :return: PDF:n kaikilta sivuilta poimittu teksti.
    """
    reader = PdfReader(pdf_tiedosto)

    tekstit = []
    for sivu in reader.pages:
        teksti = sivu.extract_text() or ""
        tekstit.append(teksti)

    return "\n".join(tekstit)


def kansallinen_ibaniksi(tilinumero: str) -> str:
    """
    Muuntaa suomalaisen kansallisen tilinumeron IBAN-muotoon.
    :param tilinumero: Kansallinen suomalainen tilinumero,
    esimerkiksi 800020-38971619.
    :return: IBAN muodossa FIxx 1234 1234 1234 12.
    """
    osat = tilinumero.split("-", 1)
    if len(osat) != 2:
        raise ValueError(f"Virheellinen tilinumero: {tilinumero}")
    pankkiosa, tili = osat
    # Suomessa BBAN muodostetaan siten, että ensimmäinen osa
    # täydennetään kahdeksan merkin mittaiseksi.
    bban = pankkiosa.zfill(6) + tili
    if not re.fullmatch(r"\d{14}", bban):
        raise ValueError(f"Virheellinen tilinumero: {tilinumero}")
    # IBAN-tarkistenumeron laskenta.
    # BBAN + FI00 siirretään tarkistusta varten numeroiksi:
    # F = 15, I = 18.
    tarkistusosa = bban + "151800"
    tarkiste = 98 - (int(tarkistusosa) % 97)
    iban = f"FI{tarkiste:02d}{bban}"
    return f"{iban[:4]} {iban[4:8]} {iban[8:12]} {iban[12:16]} {iban[16:]}"


def hae_tilinumero(teksti: str) -> str | None:
    """
    Hakee tilinumeron PDF:n tekstistä ja muuntaa sen tarvittaessa IBANiksi.
    Hyväksytyt muodot ovat esimerkiksi:
        Tilinumero FI63 8000 2912 3456 78
        Tilinumero 800029-12345678

    :param teksti: PDF-tiedostosta poimittu teksti.
    :return: IBAN-muotoinen tilinumero tai None.
    """
    # Uusi IBAN-muotoinen tilinumero.
    iban_osuma = re.search(
        r"Tilinumero\s+"
        r"(FI\d{2}(?:\s+\d{4}){3}\s+\d{2})",
        teksti,
        re.IGNORECASE,
    )
    if iban_osuma:
        iban = iban_osuma.group(1)
        return re.sub(r"\s+", " ", iban).upper()

    # Vanha kansallinen suomalainen tilinumero.
    kansallinen_osuma = re.search(
        r"Tilinumero\s+(\d{6}-\d{8})",
        teksti,
        re.IGNORECASE,
    )
    if kansallinen_osuma:
        return kansallinen_ibaniksi(kansallinen_osuma.group(1))

    return None


def hae_tiedot(teksti: str) -> tuple[str, str] | None:
    """
    Hakee tiliotteen alkupäivän ja IBAN-tilinumeron PDF:n tekstistä.
    Esimerkiksi: Ajalta 01.09.2011 - 30.09.2011
                 Tilinumero 800029-12345678
    :param teksti: PDF-tiedostosta poimittu teksti.
    :return: Päivämäärä muodossa YYYY-MM-DD ja IBAN,
             tai None jos tietoja ei löydy.
     """
    pvm_osuma = re.search(r"Ajalta\s+(\d{2}\.\d{2}\.\d{4})" r"\s*-\s*\d{2}\.\d{2}\.\d{4}", teksti, re.IGNORECASE, )
    tilinumero = hae_tilinumero(teksti)
    if not pvm_osuma or not tilinumero:
        return None
    pvm = datetime.strptime(pvm_osuma.group(1), "%d.%m.%Y", ).strftime("%Y-%m-%d")
    return pvm, tilinumero


def pura_ja_nimea() -> None:
    """
    Puretaan mahdollinen *.zip ensin, jotta Tiliote-alkuiset PDF-tiedostot löytyvät.
    Sitten nimetään Tiliote-alkuiset PDF-tiedostot uudelleen
    """

    for zip_tiedosto in ARKISTOPATH.glob("*.zip"):
        print(f"Puretaan {zip_tiedosto}")
        with zipfile.ZipFile(zip_tiedosto) as z:
            z.extractall(zip_tiedosto.parent)

        zip_tiedosto.unlink()

    """
    Nimeää Tiliote-alkuiset PDF-tiedostot uudelleen PDF:n sisällön perusteella.
    """
    pdf_tiedostot = sorted(
        p
        for p in ARKISTOPATH.iterdir()
        if (
            p.is_file()
            and p.suffix.lower() == ".pdf"
            and re.search(r"\bTiliote\b", p.name)
        )
    )

    if not pdf_tiedostot:
        print("Hakemistossa ei ole Tiliote-alkuisia PDF-tiedostoja.")
        return

    for pdf in pdf_tiedostot:
        try:
            teksti = lue_pdf_teksti(pdf)
            tiedot = hae_tiedot(teksti)

            if tiedot is None:
                print(f"OHITETAAN, tietoja ei löytynyt: {pdf.name}")
                continue

            pvm, tilinumero = tiedot

            uusi_nimi = f"{pvm} - Tiliote - {tilinumero} - .pdf"

            uusi_tiedosto = OTTEET_PATH / uusi_nimi

            if uusi_tiedosto == pdf:
                # print(f"ENNALLAAN: {pdf.name}")
                continue

            OTTEET_PATH.mkdir(parents=True, exist_ok=True)
            if uusi_tiedosto.exists():
                print(f"ON JO: {pdf.name} -> {uusi_tiedosto.name} -> TARKISTA!")
                continue

            print(f"{pdf.name} -> {uusi_tiedosto.name}")

            pdf.rename(uusi_tiedosto)

        except Exception as e:
            print(f"VIRHE: {pdf.name}: {e}")


def main():
    print(f"nimea_tiliote_pvm_mukaan.py v{VERSION}")
    print()

    pura_ja_nimea()


if __name__ == "__main__":
    main()
