@echo off
title Makeup Analyzer — Build Tool
echo.
echo ========================================
echo  Makeup Analyzer — Windows Build Script
echo ========================================
echo.
echo This will install required tools and build MakeupAnalyzer.exe
echo It only needs to be run ONCE. This may take a few minutes.
echo.
pause

echo.
echo [1/3] Installing required Python packages...
pip install pandas openpyxl pyinstaller
if errorlevel 1 (
    echo.
    echo ERROR: pip failed. Make sure Python is installed and added to PATH.
    echo Download Python from https://www.python.org/downloads/
    echo During install, check "Add Python to PATH"
    pause
    exit /b 1
)

echo.
echo [2/3] Building MakeupAnalyzer.exe...
pyinstaller ^
    --onefile ^
    --windowed ^
    --name "MakeupAnalyzer" ^
    --hidden-import analyzer_core ^
    --add-data "analyzer_core.py;." ^
    --hidden-import pandas ^
    --hidden-import openpyxl ^
    --hidden-import openpyxl.cell._writer ^
    --hidden-import babel.numbers ^
    makeup_analyzer_app.py

if errorlevel 1 (
    echo.
    echo ERROR: Build failed. See the output above for details.
    pause
    exit /b 1
)

echo.
echo [3/3] Done!
echo.
echo Your executable is at:
echo   dist\MakeupAnalyzer.exe
echo.
echo You can copy MakeupAnalyzer.exe anywhere and double-click to run.
echo No Python or any other software needed on the target computer.
echo.
pause
