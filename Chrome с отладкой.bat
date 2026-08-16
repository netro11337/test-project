@echo off
cd /d "%~dp0"
title Chrome с отладкой - для сборки корзин

rem Запускает обычный Chrome с открытым портом управления (9222).
rem Chrome 136 и новее не разрешает управлять основным профилем, поэтому
rem используется отдельный профиль. Войдите в нём в магазин один раз -
rem профиль сохранится и будет использоваться дальше.

set "PORT=9222"
set "PROFILE=%LOCALAPPDATA%\OzonCartChrome"

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

echo Запускаю Chrome с портом управления %PORT%.
echo Профиль: %PROFILE%
echo.
echo Это окно можно закрыть. Браузер закрывать НЕ надо -
echo программа будет работать именно в нём.
echo.

start "" "%CHROME%" --remote-debugging-port=%PORT% --user-data-dir="%PROFILE%" https://www.ozon.ru
