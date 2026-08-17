#!/usr/bin/env python3
"""
Telegram Media Downloader - скачивание медиа-альбомов с подписями
Скачивает фото/видео из чатов Telegram в локальные папки
"""

import os
import string
import random
import asyncio
from pathlib import Path
from typing import Optional
from telethon import TelegramClient, events
from telethon.types import TypeMessageMedia
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class TelegramMediaDownloader:
    def __init__(self, api_id: int, api_hash: str, phone: str, downloads_folder: Optional[str] = None):
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.downloads_folder = downloads_folder or str(Path.home() / "Downloads")
        self.client = TelegramClient('session_telegram', self.api_id, self.api_hash)

    def _generate_folder_name(self, caption: str) -> str:
        """Генерирует имя папки: подпись + 5 рандомных букв"""
        random_suffix = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
        return f"{caption}{random_suffix}"

    async def _download_media_group(self, message, folder_path: str) -> int:
        """Скачивает все медиа из сообщения"""
        downloaded_count = 0

        # Проверяем, есть ли медиа
        if not message.media:
            return downloaded_count

        try:
            # Получаем имя файла если есть
            filename = None
            if hasattr(message.media, 'document'):
                filename = message.media.document.attributes
                if filename:
                    for attr in filename:
                        if hasattr(attr, 'file_name'):
                            filename = attr.file_name
                            break

            # Скачиваем медиа
            await self.client.download_media(message, folder_path)
            downloaded_count += 1
            logger.info(f"✅ Скачано: {filename or 'файл'}")

        except Exception as e:
            logger.error(f"❌ Ошибка скачивания: {e}")

        return downloaded_count

    async def download_chat_messages(self, chat_identifier: str, limit: int = 100,
                                    caption_filter: Optional[str] = None):
        """
        Скачивает все медиа из чата с подписями

        Args:
            chat_identifier: ID чата или username
            limit: количество последних сообщений для проверки
            caption_filter: если указан, скачивает только сообщения с этой подписью
        """
        async with self.client:
            logger.info(f"🔍 Получение сообщений из чата: {chat_identifier}")

            async for message in self.client.iter_messages(chat_identifier, limit=limit):
                if not message.media:
                    continue

                # Получаем подпись сообщения (caption)
                caption = message.text or ""

                # Пропускаем, если не подходит фильтр
                if caption_filter and caption_filter not in caption:
                    continue

                # Если нет подписи, используем ID сообщения
                folder_label = caption.strip() if caption else f"message_{message.id}"

                # Генерируем имя папки
                folder_name = self._generate_folder_name(folder_label)
                folder_path = os.path.join(self.downloads_folder, folder_name)
                os.makedirs(folder_path, exist_ok=True)

                logger.info(f"\n📁 Создана папка: {folder_name}")
                logger.info(f"📝 Подпись: {caption or '(без подписи)'}")

                # Скачиваем медиа
                downloaded = await self._download_media_group(message, folder_path)
                logger.info(f"✅ Скачано файлов: {downloaded}\n")

    async def listen_and_download(self, chat_identifier: str):
        """
        Слушает чат и автоматически скачивает новые медиа
        """
        async with self.client:
            logger.info(f"🎧 Слушаю чат: {chat_identifier}")
            logger.info("Ожидание новых сообщений... (Ctrl+C для выхода)")

            @self.client.on(events.NewMessage(chats=chat_identifier))
            async def handler(event):
                message = event.message

                if not message.media:
                    return

                caption = message.text or ""
                folder_label = caption.strip() if caption else f"message_{message.id}"
                folder_name = self._generate_folder_name(folder_label)
                folder_path = os.path.join(self.downloads_folder, folder_name)
                os.makedirs(folder_path, exist_ok=True)

                logger.info(f"\n🆕 Новое сообщение!")
                logger.info(f"📁 Создана папка: {folder_name}")
                logger.info(f"📝 Подпись: {caption or '(без подписи)'}")

                downloaded = await self._download_media_group(message, folder_path)
                logger.info(f"✅ Скачано файлов: {downloaded}\n")

            # Остаемся в слушающем режиме
            await self.client.run_until_disconnected()


def main():
    # ⚙️ КОНФИГУРАЦИЯ (заполните ваши данные из https://my.telegram.org)
    API_ID = int(os.getenv("TELEGRAM_API_ID", "0"))
    API_HASH = os.getenv("TELEGRAM_API_HASH", "")
    PHONE = os.getenv("TELEGRAM_PHONE", "")

    if not API_ID or not API_HASH or not PHONE:
        print("❌ Ошибка: установите переменные окружения:")
        print("   export TELEGRAM_API_ID=12345")
        print("   export TELEGRAM_API_HASH='xxxxxxxxxxxxxxx'")
        print("   export TELEGRAM_PHONE='+79991234567'")
        return

    # Папка для сохранения
    downloads_folder = str(Path.home() / "Downloads" / "telegram_downloads")
    os.makedirs(downloads_folder, exist_ok=True)

    downloader = TelegramMediaDownloader(API_ID, API_HASH, PHONE, downloads_folder)

    # Выбор режима работы
    print("\n📱 Telegram Media Downloader")
    print("=" * 40)
    print("1. 📥 Скачать все медиа из чата (последние 100 сообщений)")
    print("2. 🎧 Слушать чат и скачивать новые медиа")
    print("3. 🔍 Скачать только сообщения с определенной подписью")
    print("=" * 40)

    choice = input("\nВыберите режим (1-3): ").strip()
    chat_input = input("Введите ID/username чата (例: -1001234567890 или @mychat): ").strip()

    if choice == "1":
        asyncio.run(downloader.download_chat_messages(chat_input))
    elif choice == "2":
        asyncio.run(downloader.listen_and_download(chat_input))
    elif choice == "3":
        caption_filter = input("Введите подпись для поиска (例: 0891-1): ").strip()
        asyncio.run(downloader.download_chat_messages(chat_input, caption_filter=caption_filter))
    else:
        print("❌ Неверный выбор")


if __name__ == "__main__":
    main()
