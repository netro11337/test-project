@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Сборка корзин — Ozon / Wildberries

rem Работаем из папки самого файла, поэтому ярлык можно положить куда угодно.

if not exist "main.py" (
    echo.
    echo Рядом с этим файлом нет main.py.
    echo Положите "Запуск.bat" в ту же папку, где лежит main.py и папка cart_bot.
    echo.
    pause
    exit /b 1
)

rem Сначала пробуем лаунчер py — он есть даже когда python не прописан в PATH.
set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)

if not defined PY (
    echo.
    echo Python не найден.
    echo Установите его с https://www.python.org/downloads/
    echo и обязательно поставьте галку "Add python.exe to PATH".
    echo.
    pause
    exit /b 1
)

rem Первый запуск: библиотек ещё нет, ставим их сами.
%PY% -c "import selenium" >nul 2>nul
if errorlevel 1 (
    echo Первый запуск: устанавливаю библиотеки, это займёт пару минут...
    echo.
    %PY% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo Не удалось установить библиотеки. Текст ошибки выше.
        echo.
        pause
        exit /b 1
    )
    echo.
)

%PY% main.py
if errorlevel 1 (
    echo.
    echo Программа завершилась с ошибкой — текст выше.
    echo Скопируйте его и пришлите, если непонятно, что делать.
    echo.
    pause
)
