#!/usr/bin/env python
"""
Launcher script for Ozon Registration UI Panel
Скрипт запуска UI панели регистрации Озон
"""

import sys
import subprocess
import platform


def check_dependencies():
    """Проверка установки зависимостей"""
    try:
        import tkinter
        import playwright
        import faker
        import requests
        print("✓ Все зависимости установлены")
        return True
    except ImportError as e:
        print(f"✗ Не хватает зависимости: {str(e)}")
        print("\nУстановите зависимости:")
        print("  pip install -r requirements.txt")
        print("  playwright install chromium")
        return False


def main():
    """Главная функция"""
    print("="*60)
    print("Ozon Auto Registration Panel")
    print("="*60)
    print()

    # Проверка зависимостей
    if not check_dependencies():
        sys.exit(1)

    print("\nЗапуск UI панели...")
    print()

    try:
        from ozon_ui_panel import main as ui_main
        ui_main()
    except Exception as e:
        print(f"✗ Ошибка при запуске: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
