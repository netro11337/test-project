#!/bin/bash
# Запуск Chrome с удаленной отладкой для Ozon Auto Registration

echo "========================================================"
echo "  Chrome Debug Launcher"
echo "========================================================"
echo ""

# Определяем ОС
OS="$(uname -s)"

case "$OS" in
    Darwin*)
        CHROME_PATH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
        PROFILE_DIR="/tmp/ChromeDebug"
        ;;
    Linux*)
        # Пробуем разные варианты
        if command -v google-chrome &> /dev/null; then
            CHROME_PATH="google-chrome"
        elif command -v chromium &> /dev/null; then
            CHROME_PATH="chromium"
        elif command -v chromium-browser &> /dev/null; then
            CHROME_PATH="chromium-browser"
        else
            echo "ERROR: Chrome/Chromium не найден"
            exit 1
        fi
        PROFILE_DIR="/tmp/ChromeDebug"
        ;;
    *)
        echo "ERROR: Неподдерживаемая ОС: $OS"
        exit 1
        ;;
esac

echo "Chrome: $CHROME_PATH"
echo ""
echo "Запуск Chrome с удаленной отладкой на порту 9222..."
echo ""
echo "ВАЖНО: НЕ ЗАКРЫВАЙТЕ ЭТО ОКНО ПОКА РАБОТАЕТ РЕГИСТРАЦИЯ!"
echo ""

mkdir -p "$PROFILE_DIR"

"$CHROME_PATH" --remote-debugging-port=9222 --user-data-dir="$PROFILE_DIR"

echo ""
echo "Chrome закрыт."
