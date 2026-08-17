@echo off
chcp 65001 >nul
cls

echo.
echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║                                                            ║
echo ║      📱 TELEGRAM MEDIA DOWNLOADER                          ║
echo ║                                                            ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python не установлен!
    echo.
    echo Скачайте Python с https://www.python.org/downloads/
    echo При установке отметьте "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo ✅ Python найден
echo.

REM Run setup wizard
python setup_wizard.py
if errorlevel 1 (
    echo.
    echo ❌ Ошибка при запуске
    pause
    exit /b 1
)

pause
