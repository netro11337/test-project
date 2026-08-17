#!/usr/bin/env python3
"""
Interactive setup wizard for Telegram Media Downloader
Guides user through configuration on first run
"""

import os
import sys
import subprocess
from pathlib import Path


def install_dependencies():
    """Install required packages"""
    print("\n📦 Установка зависимостей...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "-r", "requirements.txt"])
        print("✅ Зависимости установлены\n")
        return True
    except Exception as e:
        print(f"❌ Ошибка установки: {e}")
        return False


def get_credentials():
    """Interactive credentials input"""
    print("\n" + "="*60)
    print("🔐 НАСТРОЙКА API CREDENTIALS")
    print("="*60)
    print("\n1️⃣  Перейдите на https://my.telegram.org")
    print("2️⃣  Создайте приложение")
    print("3️⃣  Скопируйте API ID и API Hash\n")

    print("Введите ваши данные (или нажмите Enter чтобы пропустить):\n")

    api_id = input("API ID: ").strip()
    if not api_id:
        print("❌ API ID обязателен!")
        return None

    api_hash = input("API Hash: ").strip()
    if not api_hash:
        print("❌ API Hash обязателен!")
        return None

    phone = input("Номер телефона (+79991234567): ").strip()
    if not phone:
        print("❌ Номер телефона обязателен!")
        return None

    return {
        'api_id': api_id,
        'api_hash': api_hash,
        'phone': phone
    }


def save_env(credentials):
    """Save credentials to .env file"""
    env_content = f"""# Telegram API Credentials
# Автоматически создано setup wizard

TELEGRAM_API_ID={credentials['api_id']}
TELEGRAM_API_HASH={credentials['api_hash']}
TELEGRAM_PHONE={credentials['phone']}
"""

    with open('.env', 'w') as f:
        f.write(env_content)

    print("\n✅ Настройки сохранены в .env\n")


def check_and_load_env():
    """Check if .env exists and load it"""
    if os.path.exists('.env'):
        print("✅ Найдены сохраненные настройки\n")
        # Load .env
        from dotenv import load_dotenv
        load_dotenv()
        return True
    return False


def main():
    print("\n")
    print("╔" + "="*58 + "╗")
    print("║" + " "*58 + "║")
    print("║" + "  📱 TELEGRAM MEDIA DOWNLOADER - SETUP WIZARD".center(58) + "║")
    print("║" + " "*58 + "║")
    print("╚" + "="*58 + "╝")

    # Step 1: Check Python version
    if sys.version_info < (3, 7):
        print("❌ Python 3.7+ требуется")
        sys.exit(1)

    # Step 2: Install dependencies
    if not install_dependencies():
        sys.exit(1)

    # Step 3: Check credentials
    if not check_and_load_env():
        print("⚙️  Первый запуск - необходима настройка\n")
        credentials = get_credentials()
        if not credentials:
            print("❌ Отменено пользователем")
            sys.exit(1)
        save_env(credentials)

    # Step 4: Check env vars
    api_id = os.getenv('TELEGRAM_API_ID')
    api_hash = os.getenv('TELEGRAM_API_HASH')
    phone = os.getenv('TELEGRAM_PHONE')

    if not all([api_id, api_hash, phone]):
        print("❌ Переменные окружения не установлены!")
        sys.exit(1)

    print("="*60)
    print("✅ ВСЁ ГОТОВО К ЗАПУСКУ!")
    print("="*60)
    print(f"\n📱 Аккаунт: {phone}")
    print(f"🔑 API ID: {api_id[:4]}...{api_id[-4:]}" if len(api_id) > 8 else f"🔑 API ID: {api_id}")
    print("\n🚀 Запускаю Telegram Media Downloader...\n")

    # Step 5: Run main script
    os.execvp(sys.executable, [sys.executable, 'telegram_media_downloader.py'])


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n❌ Отменено пользователем")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        sys.exit(1)
