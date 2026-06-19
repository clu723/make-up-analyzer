#!/bin/bash
echo ""
echo "========================================"
echo " Makeup Analyzer — Mac Build Script"
echo "========================================"
echo ""
echo "This will install required tools and build MakeupAnalyzer.app"
echo "It only needs to be run ONCE. This may take a few minutes."
echo ""
read -p "Press Enter to continue..."

echo ""
echo "[1/3] Installing required Python packages..."
pip3 install pandas openpyxl pyinstaller
if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: pip3 failed. Make sure Python 3 is installed."
    echo "Download it from https://www.python.org/downloads/"
    read -p "Press Enter to exit..."
    exit 1
fi

echo ""
echo "[2/3] Building MakeupAnalyzer.app..."
pyinstaller \
    --onefile \
    --windowed \
    --name "MakeupAnalyzer" \
    --hidden-import analyzer_core \
    --add-data "analyzer_core.py:." \
    --hidden-import pandas \
    --hidden-import openpyxl \
    --hidden-import openpyxl.cell._writer \
    --hidden-import babel.numbers \
    makeup_analyzer_app.py

if [ $? -ne 0 ]; then
    echo ""
    echo "ERROR: Build failed. See the output above for details."
    read -p "Press Enter to exit..."
    exit 1
fi

echo ""
echo "[3/3] Done!"
echo ""
echo "Your app is at:  dist/MakeupAnalyzer"
echo "(on Mac this is a standalone Unix executable — double-clickable from Finder)"
echo ""
echo "To make it a proper .app bundle you can double-click from Finder,"
echo "replace --onefile with --windowed in this script and re-run."
echo ""
read -p "Press Enter to exit..."
