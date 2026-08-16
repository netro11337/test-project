@echo off
REM Ozon Auto Registration System Launcher
REM Simple launcher without Unicode issues

setlocal enabledelayedexpansion

cls
echo.
echo ========================================================
echo   Ozon Auto Registration System
echo ========================================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found!
    echo.
    echo Please install Python 3.8+ from https://python.org
    echo Make sure to check "Add Python to PATH" during installation
    echo.
    pause
    exit /b 1
)

echo OK: Python found

REM Check pip
python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: pip not installed
    pause
    exit /b 1
)

echo OK: pip ready

REM Install dependencies
echo.
echo Installing dependencies (please wait)...
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt -q

if errorlevel 1 (
    echo ERROR: Failed to install dependencies
    echo Try running: pip install -r requirements.txt
    pause
    exit /b 1
)

echo OK: Dependencies installed

REM Install Playwright
echo.
echo Installing Chromium browser (this may take a few minutes)...
python -m playwright install chromium -q

if errorlevel 1 (
    echo WARNING: Chromium installation may need manual setup
    echo Try running: python -m playwright install chromium
)

echo OK: Ready to start

REM Launch application
echo.
echo Starting application...
echo.

python ozon_ui_panel.py

if errorlevel 1 (
    echo.
    echo ERROR: Failed to start application
    pause
    exit /b 1
)

exit /b 0
