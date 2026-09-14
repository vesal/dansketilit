#Requires AutoHotkey v2.0

SetTitleMatchMode 2

latauskansio := "E:\oma\vesa\tilit\2026\elaskut\pdf"

tallennetut := 0

Loop
{
    windows := WinGetList("ahk_exe chrome.exe")

    signalHwnd := 0
    signalIndex := 0
    fileName := ""

    ; ============================================================
    ; ETSI DANSKE_AHK_SAVE -HERÄTEIKKUNA
    ; ============================================================

    for index, hwnd in windows
    {
        try
        {
            title := WinGetTitle(hwnd)
        }
        catch
        {
            continue
        }

        if InStr(title, "DANSKE_AHK_SAVE|")
        {
            signalHwnd := hwnd
            signalIndex := index

            fileName := SubStr(
                title,
                StrLen("DANSKE_AHK_SAVE|") + 1
            )

            ; Chrome lisää otsikkoon tämän.
            fileName := RegExReplace(
                fileName,
                "\s+-\s+Google Chrome$",
                ""
            )

            break
        }
    }

    if (!signalHwnd)
    {
        Sleep(300)
        continue  ; Jatka isoa silmukkaa ja odota löytyykö kohta
    }


    ; ============================================================
    ; LASKUIKKUNAN ETSIMINEN
    ; ============================================================

    if (signalIndex >= windows.Length)
    {
        MsgBox(
            "Laskuikkunaa ei löytynyt." .
            "`n`nHeräteikkunan indeksi: " signalIndex .
            "`nChrome-ikkunoita: " windows.Length
        )
        ExitApp
    }

	; ============================================================
	; ETSI PDF-IKKUNA
	;
	; Nimettömät Chrome-ikkunat jätetään huomiotta.
	; Ensimmäinen nimetty ikkuna, joka ei ole heräteikkuna,
	; on laskun PDF-ikkuna.
	; ============================================================

	pdfHwnd := 0
	pdfTitle := ""

	for index, hwnd in windows
	{
		try
		{
			otsikko := WinGetTitle(hwnd)
		}
		catch
		{
			continue
		}

		; Ohitetaan nimettömät ikkunat.
		if (otsikko = "")
			continue

		; Ohitetaan AHK:n heräteikkuna.
		if InStr(otsikko, "DANSKE_AHK_SAVE|")
			continue

        ; MsgBox("HWND = " hwnd "`nTitle = [" otsikko		"]")
		pdfHwnd := hwnd
		pdfTitle := otsikko
		break
	}

	if (!pdfHwnd)
	{
		MsgBox("Nimettyä PDF-ikkunaa ei löytynyt.")
		ExitApp
	}


    ; ============================================================
    ; AKTIVOI LASKUIKKUNA
    ; ============================================================

    WinActivate(pdfHwnd)

    if !WinWaitActive(pdfHwnd,, 3)
    {
        MsgBox("Laskuikkunaa ei saatu aktiiviseksi.")
        ExitApp
    }

    Sleep(500)

    ; ============================================================
    ; AVAA TALLENNA NIMELLÄ
    ; ============================================================

    Send("^s")

    ; ============================================================
    ; ODOTA CHROMEN TALLENNA NIMELLÄ -IKKUNAA
    ; ============================================================

    saveDialog := 0

    Loop 50
    {
        allWindows := WinGetList()

        for index, hwnd in allWindows
        {
            try
            {
                winClass := WinGetClass(hwnd)
            }
            catch
            {
                continue
            }

            if (winClass != "#32770")
                continue

            try
            {
                processName := WinGetProcessName(hwnd)
            }
            catch
            {
                continue
            }

            if (StrLower(processName) = "chrome.exe")
            {
                saveDialog := hwnd
                break
            }
        }

        if (saveDialog)
            break

        Sleep(100)
    }

    if (!saveDialog)
    {
        MsgBox(
            "Chromen Save As -ikkunaa ei löytynyt." .
            "`n`nTiedostonimi olisi ollut:" .
            "`n" fileName
        )
        ExitApp
    }

    ; ============================================================
    ; CHROME ON JO AVANNUT SAVE AS -IKKUNAN
    ;
    ; Tiedostonimikentän pitäisi olla automaattisesti aktiivinen.
    ; ============================================================

    Sleep(500)

	A_Clipboard := fileName
	Sleep(100)
	Send("^v")
	Sleep(300)
	Send("{Enter}")
	
    ; ============================================================
    ; ODOTA LOPULLISTA TIEDOSTOA
    ; ============================================================

    valmis := false

    Loop 40
    {
        hakumaski := latauskansio "\" fileName ".*"

        if DirExist(latauskansio)
        {
            Loop Files, hakumaski, "F"
            {
                valmis := true
                break
            }
        }

        if (valmis)
            break

        Sleep(500)
    }

    if (!valmis)
    {
        MsgBox(
            "Tiedostoa ei löytynyt tallennuksen jälkeen." .
            "`n`nOdotettu nimi:" .
            "`n" fileName
        )
        ExitApp
    }

    tallennetut++


    ; ============================================================
    ; SULJE LASKUIKKUNA
    ; ============================================================

    WinClose(pdfHwnd)

    Sleep(500)

    ; Jos WinClose ei sulkenut, yritetään Ctrl+W.
    if WinExist(pdfHwnd)
    {
        WinActivate(pdfHwnd)

        if WinWaitActive(pdfHwnd,, 2)
        {
            Sleep(300)
            Send("^w")
            Sleep(700)
        }
    }

    ; ============================================================
    ; VARMISTA, ETTÄ LASKUIKKUNA ON SULJETTU
    ; ============================================================

    if WinExist(pdfHwnd)
    {
        MsgBox(
            "Lasku tallennettiin, mutta PDF-ikkuna ei sulkeutunut." .
            "`n`nOtsikko:" .
            "`n" pdfTitle .
            "`n`nTiedosto:" .
            "`n" fileName
        )
        ExitApp
    }

    ; ============================================================
    ; SULJE HERÄTEIKKUNA
    ; ============================================================

    if WinExist(signalHwnd)
    {
        WinClose(signalHwnd)
    }

    ; Tampermonkey odottaa heräteikkunan sulkeutumista
    ; ennen seuraavan laskun avaamista.
    Sleep(500)
}