#!/bin/bash

# Скрипт для запуска Telegram Media Downloader

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 не установлен"
    exit 1
fi

# Проверка зависимостей
if ! python3 -c "import telethon" &> /dev/null; then
    echo "📦 Установка зависимостей..."
    pip3 install -r requirements.txt
fi

# Проверка переменных окружения
if [ -z "$TELEGRAM_API_ID" ] || [ -z "$TELEGRAM_API_HASH" ] || [ -z "$TELEGRAM_PHONE" ]; then
    echo "⚠️ Переменные окружения не установлены!"
    echo ""
    echo "Установите:"
    echo "  export TELEGRAM_API_ID=12345"
    echo "  export TELEGRAM_API_HASH='xxxxxxxxxxxxxxx'"
    echo "  export TELEGRAM_PHONE='+79991234567'"
    echo ""
    echo "Или создайте .env файл копированием .env.example:"
    echo "  cp .env.example .env"
    echo "  source .env"
    exit 1
fi

# Запуск
echo "🚀 Запуск Telegram Media Downloader..."
python3 telegram_media_downloader.py
