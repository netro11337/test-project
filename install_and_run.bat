@echo off
chcp 65001 >nul
cls

echo.
echo ═════════════════════════════════════════════════════════
echo   Ozon Auto Registration System
echo ═════════════════════════════════════════════════════════
echo.

:: Проверка Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ✗ Python не найден!
    echo.
    echo Пожалуйста, установите Python 3.8+ с сайта https://python.org
    echo Во время установки отметьте "Add Python to PATH"
    echo.
    pause
    exit /b 1
)

echo ✓ Python найден

:: Проверка pip
python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo ✗ pip не установлен
    pause
    exit /b 1
)

echo ✓ pip готов

:: Установка зависимостей
echo.
echo 📦 Установка зависимостей (это может занять несколько минут)...
python -m pip install --upgrade pip -q
python -m pip install -r requirements.txt -q

if errorlevel 1 (
    echo ✗ Ошибка при установке зависимостей
    pause
    exit /b 1
)

echo ✓ Зависимости установлены

:: Установка Playwright
echo.
echo 🌐 Установка браузера Chromium для Playwright...
python -m playwright install chromium -q

if errorlevel 1 (
    echo ✗ Ошибка при установке браузера
    echo Попробуйте запустить вручную: playwright install chromium
    pause
    exit /b 1
)

echo ✓ Браузер установлен

:: Запуск приложения
echo.
echo ✓ Готово! Запуск приложения...
echo.

python ozon_ui_panel.py

if errorlevel 1 (
    echo.
    echo ✗ Ошибка при запуске приложения
    pause
    exit /b 1
)

exit /b 0
