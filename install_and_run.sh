#!/bin/bash

echo ""
echo "═════════════════════════════════════════════════════════"
echo "  Ozon Auto Registration System"
echo "═════════════════════════════════════════════════════════"
echo ""

# Проверка Python
if ! command -v python3 &> /dev/null; then
    echo "✗ Python 3 не найден!"
    echo ""
    echo "Установите Python 3.8+:"
    echo "  Ubuntu/Debian: sudo apt-get install python3 python3-pip python3-venv"
    echo "  macOS: brew install python3"
    echo "  или скачайте с https://python.org"
    echo ""
    read -p "Нажмите Enter для выхода..."
    exit 1
fi

echo "✓ Python найден: $(python3 --version)"

# Проверка pip
if ! command -v pip3 &> /dev/null; then
    echo "✗ pip3 не установлен"
    echo "Установите: sudo apt-get install python3-pip"
    read -p "Нажмите Enter для выхода..."
    exit 1
fi

echo "✓ pip3 готов"

# Установка зависимостей
echo ""
echo "📦 Установка зависимостей (это может занять несколько минут)..."
pip3 install --upgrade pip -q
pip3 install -r requirements.txt -q

if [ $? -ne 0 ]; then
    echo "✗ Ошибка при установке зависимостей"
    read -p "Нажмите Enter для выхода..."
    exit 1
fi

echo "✓ Зависимости установлены"

# Установка Playwright
echo ""
echo "🌐 Установка браузера Chromium для Playwright..."
python3 -m playwright install chromium -q

if [ $? -ne 0 ]; then
    echo "✗ Ошибка при установке браузера"
    echo "Попробуйте запустить вручную: playwright install chromium"
    read -p "Нажмите Enter для выхода..."
    exit 1
fi

echo "✓ Браузер установлен"

# Запуск приложения
echo ""
echo "✓ Готово! Запуск приложения..."
echo ""

python3 ozon_ui_panel.py

if [ $? -ne 0 ]; then
    echo ""
    echo "✗ Ошибка при запуске приложения"
    read -p "Нажмите Enter для выхода..."
    exit 1
fi

exit 0
