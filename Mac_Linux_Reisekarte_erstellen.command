#!/bin/bash
# Reisekarte – Doppelklick-Starter für macOS und Linux
# https://github.com/Niwo911/Reisekarte

cd "$(dirname "$0")" || exit 1

echo ""
echo "========================================"
echo "  Reisekarte"
echo "========================================"
echo ""

# ============================================================
# 1. Python finden (python3 oder python)
# ============================================================

PYTHON_CMD=""
if command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    if python -c "import sys; sys.exit(0 if sys.version_info[0] == 3 else 1)" 2>/dev/null; then
        PYTHON_CMD="python"
    fi
fi

if [ -z "$PYTHON_CMD" ]; then
    echo "[FEHLER] Python 3 wurde nicht gefunden."
    echo ""
    echo "So installierst du es:"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "  - Einfach:       https://www.python.org/downloads/"
        echo "  - Mit Homebrew:  brew install python"
    else
        echo "  - Ubuntu/Debian: sudo apt install python3 python3-venv python3-pip"
        echo "  - Fedora:        sudo dnf install python3 python3-pip"
    fi
    echo ""
    read -r -p "Drücke Enter zum Schließen..."
    exit 1
fi

echo "[OK] Python gefunden"
$PYTHON_CMD --version
echo ""

# ============================================================
# 2. venv anlegen, falls nicht vorhanden
# ============================================================

if [ ! -f "venv/bin/activate" ]; then
    echo "Erstelle virtuelle Umgebung..."
    if ! $PYTHON_CMD -m venv venv 2>/dev/null; then
        echo "[FEHLER] Konnte virtuelle Umgebung nicht erstellen."
        if [[ "$OSTYPE" == "linux-gnu"* ]]; then
            echo "  Auf Ubuntu/Debian fehlt evtl.: sudo apt install python3-venv"
        fi
        read -r -p "Drücke Enter zum Schließen..."
        exit 1
    fi
    echo "[OK] Virtuelle Umgebung erstellt"
    echo ""
fi

# ============================================================
# 3. venv aktivieren
# ============================================================

# shellcheck disable=SC1091
source venv/bin/activate

# ============================================================
# 4. Dependencies installieren, falls Pillow fehlt
# ============================================================

if ! python -c "import PIL" 2>/dev/null; then
    echo "Installiere Dependencies, dauert ca. 1 Minute..."
    echo ""

    python -m pip install --upgrade pip
    pip install -r requirements.txt

    if ! python -c "import PIL" 2>/dev/null; then
        echo ""
        echo "[FEHLER] Pillow konnte nicht installiert werden."
        echo "  Apple Silicon (M1/M2/M3/M4) Tipp: brew install libheif"
        read -r -p "Drücke Enter zum Schließen..."
        exit 1
    fi

    echo ""
    echo "[OK] Dependencies installiert"
    echo ""
fi

# ============================================================
# 5. Skript ausführen
# ============================================================

echo "Lese Fotos aus dem fotos/-Ordner..."
echo ""
python foto_karte.py

# ============================================================
# 6. Karte im Browser öffnen
# ============================================================

if [ -f "reisekarte.html" ]; then
    echo ""
    echo "[FERTIG] Öffne Karte im Browser..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        open reisekarte.html
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open reisekarte.html >/dev/null 2>&1 &
    else
        echo "  Bitte reisekarte.html manuell im Browser öffnen."
    fi
else
    echo ""
    echo "[WARNUNG] Es wurde keine reisekarte.html erstellt."
    echo "Liegen Fotos mit GPS-Daten im fotos/-Ordner?"
fi

echo ""
read -r -p "Drücke Enter zum Schließen..."
