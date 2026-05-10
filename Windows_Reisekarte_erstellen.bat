@echo off
setlocal enabledelayedexpansion
REM Reisekarte – Doppelklick-Starter für Windows
REM https://github.com/Niwo911/Reisekarte

cd /d "%~dp0"

echo.
echo ========================================
echo   Reisekarte
echo ========================================
echo.

REM Neueste verfuegbare Python-Version (>= 3.10) ueber py-Launcher suchen
set "PY_CMD="
for %%v in (3.13 3.12 3.11 3.10) do (
    if not defined PY_CMD (
        py -%%v --version >nul 2>nul
        if not errorlevel 1 set "PY_CMD=py -%%v"
    )
)

if not defined PY_CMD (
    echo [FEHLER] Python 3.10 oder neuer wurde nicht gefunden.
    echo Bitte aus dem Microsoft Store installieren: "Python 3.13"
    echo Oder von https://www.python.org/downloads/
    pause
    exit /b 1
)

echo [OK] Python wurde gefunden
%PY_CMD% --version
echo.

REM venv anlegen falls noetig
if not exist "venv\Scripts\activate.bat" (
    echo Erstelle virtuelle Umgebung...
    %PY_CMD% -m venv venv
    if errorlevel 1 (
        echo [FEHLER] venv konnte nicht erstellt werden.
        pause
        exit /b 1
    )
    echo [OK] Virtuelle Umgebung erstellt
    echo.
)

REM venv aktivieren
call "venv\Scripts\activate.bat"

REM Dependencies pruefen
if not exist "venv\Lib\site-packages\PIL" (
    echo Installiere Dependencies, dauert ca. 1 Minute...
    echo.

    python -m pip install --upgrade pip
    pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo [FEHLER] Dependencies konnten nicht installiert werden.
        pause
        exit /b 1
    )

    echo.
    echo [OK] Dependencies installiert
    echo.
)

REM Skript ausfuehren
echo Lese Fotos aus dem fotos-Ordner...
echo.
python foto_karte.py

REM Karte oeffnen falls vorhanden
if exist "reisekarte.html" (
    echo.
    echo [FERTIG] Oeffne Karte im Browser...
    start "" "reisekarte.html"
) else (
    echo.
    echo [WARNUNG] Es wurde keine reisekarte.html erstellt.
    echo Liegen Fotos mit GPS-Daten im fotos-Ordner?
)

echo.
pause
