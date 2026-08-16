#!/usr/bin/env python3
"""
Universal launcher for Ozon Registration System
Работает на Windows, macOS и Linux
"""

import os
import sys
import subprocess
import platform
from pathlib import Path


def check_python():
    """Проверка версии Python"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("✗ Требуется Python 3.8 или выше")
        print(f"  Установлена версия: {version.major}.{version.minor}.{version.micro}")
        return False
    print(f"✓ Python {version.major}.{version.minor}.{version.micro}")
    return True


def install_requirements():
    """Установка зависимостей"""
    print("\n📦 Проверка зависимостей...")

    try:
        import tkinter
        import requests
        import faker
        import playwright
        print("✓ Все базовые зависимости найдены")
        return True
    except ImportError as e:
        print(f"⚠ Отсутствует: {str(e)}")

    print("\n📦 Установка зависимостей из requirements.txt...")

    try:
        # Обновление pip
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        # Установка requirements
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )

        print("✓ Зависимости установлены")
        return True

    except subprocess.CalledProcessError as e:
        print(f"✗ Ошибка при установке: {str(e)}")
        return False


def install_playwright():
    """Установка браузера Playwright"""
    print("\n🌐 Проверка браузера Chromium...")

    try:
        from playwright.async_api import async_playwright
        print("✓ Playwright найден")
    except ImportError:
        print("⚠ Playwright не установлен")
        return False

    print("🌐 Установка браузера Chromium (это может занять время)...")

    try:
        subprocess.check_call(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        print("✓ Chromium установлен")
        return True

    except subprocess.CalledProcessError:
        print("⚠ Не удалось установить Chromium")
        print("  Попробуйте запустить вручную:")
        print("  playwright install chromium")
        return False


def launch_app():
    """Запуск приложения"""
    print("\n✓ Готово! Запуск приложения...\n")

    try:
        import ozon_ui_panel
        ozon_ui_panel.main()
        return True

    except Exception as e:
        print(f"✗ Ошибка при запуске: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Главная функция"""
    print("")
    print("═" * 60)
    print("  Ozon Auto Registration System")
    print("═" * 60)
    print("")

    # Проверка Python
    if not check_python():
        print("\nЗагрузите Python 3.8+ с https://python.org")
        input("Нажмите Enter для выхода...")
        sys.exit(1)

    # Установка зависимостей
    if not install_requirements():
        print("\nОшибка при установке зависимостей")
        print("Попробуйте запустить вручную: pip install -r requirements.txt")
        input("Нажмите Enter для выхода...")
        sys.exit(1)

    # Установка Playwright
    if not install_playwright():
        print("\nОшибка при установке браузера")
        input("Нажмите Enter для выхода...")
        sys.exit(1)

    # Запуск приложения
    if not launch_app():
        print("\nОшибка при запуске приложения")
        input("Нажмите Enter для выхода...")
        sys.exit(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nПрограмма прервана пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Неожиданная ошибка: {str(e)}")
        import traceback
        traceback.print_exc()
        input("\nНажмите Enter для выхода...")
        sys.exit(1)
