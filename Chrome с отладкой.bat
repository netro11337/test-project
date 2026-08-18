@echo off
cd /d "%~dp0"
setlocal enabledelayedexpansion
title Chrome с отладкой - для сборки корзин

rem Поднимает несколько окон Chrome, каждое на своём порту и своём профиле.
rem Разные профили обязательны: два процесса Chrome не делят одну папку
rem профиля, да и корзина у каждого должна быть своя.

set "PORT=9222"
set "COUNT="
set /p COUNT=Сколько браузеров запустить? [1]: 
if "%COUNT%"=="" set "COUNT=1"

rem Корзина магазина привязана к аккаунту: окна с одним логином делят одну
rem корзину на всех, и потоки смешают товары. Инкогнито этого не допускает,
rem но и историю с входом не сохраняет - капчу показывают чаще.
set "PRIVATE="
set "MODE="
if not "%COUNT%"=="1" (
    echo.
    echo Внимание: при входе в один аккаунт корзина у всех окон общая,
    echo и потоки смешают товары. Инкогнито даёт каждому свою корзину.
    set /p MODE=Запустить в режиме инкогнито? [д/н, по умолчанию н]: 
)
if /i "%MODE%"=="д" set "PRIVATE=--incognito"
if /i "%MODE%"=="y" set "PRIVATE=--incognito"
if /i "%MODE%"=="да" set "PRIVATE=--incognito"

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
    start "" "%CHROME%" --remote-debugging-port=!P! --user-data-dir="!DIR!" %PRIVATE% https://www.ozon.ru
    rem Пауза между запусками: одновременный старт нескольких Chrome иногда
    rem заканчивается тем, что часть окон не поднимает порт отладки.
    timeout /t 2 /nobreak >nul
)

echo.
if defined PRIVATE (
    echo Режим инкогнито: входить в аккаунт НЕ надо - иначе корзина снова
    echo станет общей. У каждого окна своя анонимная корзина.
) else (
    echo Обычный режим. Если войдёте в один аккаунт во всех окнах, корзина
    echo будет общая - запускайте тогда по одному потоку за раз.
)
echo.
echo В программе поставьте столько же потоков, сколько браузеров.
echo Это окно можно закрыть. Браузеры закрывать НЕ надо.
echo.
pause
