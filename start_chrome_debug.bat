@echo off
REM Запуск Chrome с удаленной отладкой для Ozon Auto Registration

echo ========================================================
echo   Chrome Debug Launcher
echo ========================================================
echo.

REM Проверяем стандартные пути Chrome
set CHROME_PATH=""

if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
    set CHROME_PATH="C:\Program Files\Google\Chrome\Application\chrome.exe"
    goto :launch
)

if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
    set CHROME_PATH="C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
    goto :launch
)

if exist "%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe" (
    set CHROME_PATH="%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"
    goto :launch
)

echo ERROR: Chrome не найден в стандартных папках
echo.
echo Пожалуйста, укажите путь к chrome.exe вручную
echo Пример: "C:\Program Files\Google\Chrome\Application\chrome.exe"
pause
exit /b 1

:launch
echo Найден Chrome: %CHROME_PATH%
echo.
echo Запуск Chrome с удаленной отладкой на порту 9222...
echo.
echo ВАЖНО: НЕ ЗАКРЫВАЙТЕ ЭТО ОКНО ПОКА РАБОТАЕТ РЕГИСТРАЦИЯ!
echo.

REM Создаем папку для профиля если её нет
if not exist "C:\ChromeDebug" mkdir "C:\ChromeDebug"

REM Запускаем Chrome с отладкой
%CHROME_PATH% --remote-debugging-port=9222 --user-data-dir="C:\ChromeDebug"

echo.
echo Chrome закрыт.
pause
