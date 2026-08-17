@echo off
cls

echo.
echo ============================================================
echo.
echo        TELEGRAM MEDIA DOWNLOADER
echo.
echo ============================================================
echo.

REM Try to find Python
python --version >nul 2>&1
if errorlevel 1 (
    python3 --version >nul 2>&1
    if errorlevel 1 (
        echo ERROR: Python is not installed or not in PATH
        echo.
        echo Download Python from: https://www.python.org/downloads/
        echo.
        echo During installation, make sure to check:
        echo   [X] Add Python to PATH
        echo.
        echo After installation, restart this script.
        echo.
        pause
        exit /b 1
    )
    set PYTHON_CMD=python3
) else (
    set PYTHON_CMD=python
)

echo Python found. Checking dependencies...
echo.

REM Run setup wizard
%PYTHON_CMD% setup_wizard.py
if errorlevel 1 (
    echo.
    echo Error during startup
    echo.
    pause
    exit /b 1
)

pause
