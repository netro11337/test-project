@echo off
cd /d "%~dp0"
setlocal enabledelayedexpansion
title Chrome с отладкой - для сборки корзин

rem Запасной путь: обычно окна открывает сама программа. Этот файл нужен,
rem если она не нашла Chrome.
rem Разные профили обязательны: два процесса Chrome не делят одну папку
rem профиля.

set "PORT=9222"
set "COUNT="
set /p COUNT=Сколько браузеров запустить? [1]: 
if "%COUNT%"=="" set "COUNT=1"

set "CHROME="
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not defined CHROME if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not defined CHROME if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" set "CHROME=%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"

if not defined CHROME (
    echo.
    echo Не нашёл chrome.exe в обычных местах установки.
    echo Установите Google Chrome или укажите путь к нему вручную в этом файле.
    echo.
    pause
    exit /b 1
)

echo.
for /l %%i in (1,1,%COUNT%) do (
    set /a "P=%PORT% + %%i - 1"
    set "DIR=%LOCALAPPDATA%\OzonCartChrome-%%i"
    echo Браузер %%i: порт !P!, профиль !DIR!
    start "" "%CHROME%" --remote-debugging-port=!P! --user-data-dir="!DIR!" https://www.ozon.ru
    rem Пауза между запусками: одновременный старт нескольких Chrome иногда
    rem заканчивается тем, что часть окон не поднимает порт отладки.
    timeout /t 2 /nobreak >nul
)

echo.
echo Внимание: корзина магазина привязана к аккаунту, а не к окну. Если
echo войти в один аккаунт в нескольких окнах, корзина будет общая и потоки
echo смешают товары. С одним аккаунтом ставьте в программе "Браузеров" = 1.
echo.
echo Это окно можно закрыть. Браузеры закрывать НЕ надо.
echo.
pause
