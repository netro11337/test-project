#!/bin/bash

# Скрипт для запуска Telegram Media Downloader с автоматической настройкой

cd "$(dirname "$0")" || exit 1

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║                                                            ║"
echo "║      📱 TELEGRAM MEDIA DOWNLOADER                          ║"
echo "║                                                            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не установлен"
    echo "Установите: brew install python3 (macOS) или apt install python3 (Linux)"
    exit 1
fi

echo "✅ Python найден"
echo ""

# Запуск setup wizard
python3 setup_wizard.py
exit $?
