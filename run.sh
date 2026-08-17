#!/bin/bash

# Скрипт для запуска Telegram Media Downloader с автоматической настройкой

cd "$(dirname "$0")" || exit 1

echo ""
echo "============================================================"
echo "TELEGRAM MEDIA DOWNLOADER"
echo "============================================================"
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[-] Python3 not found"
    echo "Install: brew install python3 (macOS) or apt install python3 (Linux)"
    exit 1
fi

echo "[+] Python found"
echo ""

# Запуск setup wizard
python3 setup_wizard.py
exit $?
