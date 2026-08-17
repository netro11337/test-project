# 📱 Telegram Media Downloader

Скачивание фото и видео из Telegram чатов с автоматическим созданием папок по подписям медиа.

## 🎯 Функционал

- ✅ Скачивание медиа-альбомов (фото + видео вместе)
- ✅ Создание папок с названием "подпись + 5 рандомных букв"
- ✅ Три режима: скачать всё, слушать новые, фильтр по подписи
- ✅ Поддержка как приватных чатов, так и групп
- ✅ Автоматическое создание папок структуры

## 📋 Требования

- Python 3.7+
- Аккаунт Telegram
- API credentials (API ID и API Hash)

## 🚀 Установка

### 1. Получите API credentials

Перейдите на https://my.telegram.org и создайте приложение:
- Перейдите в раздел **API development tools**
- Заполните форму (название, описание)
- Получите **API ID** и **API Hash**

### 2. Установите зависимости

```bash
pip install -r requirements.txt
```

### 3. Установите переменные окружения

```bash
# Linux / macOS
export TELEGRAM_API_ID=12345
export TELEGRAM_API_HASH='xxxxxxxxxxxxxxxxxxxxxxx'
export TELEGRAM_PHONE='+79991234567'

# Windows (Command Prompt)
set TELEGRAM_API_ID=12345
set TELEGRAM_API_HASH=xxxxxxxxxxxxxxxxxxxxxxx
set TELEGRAM_PHONE=+79991234567

# Windows (PowerShell)
$env:TELEGRAM_API_ID="12345"
$env:TELEGRAM_API_HASH="xxxxxxxxxxxxxxxxxxxxxxx"
$env:TELEGRAM_PHONE="+79991234567"
```

## 📥 Использование

### Запуск скрипта

```bash
python telegram_media_downloader.py
```

Вам будет предложено выбрать режим:

### Режим 1: Скачать всё из чата

```
Выберите режим (1-3): 1
Введите ID/username чата: @mychat
```

Скачает все медиа из последних 100 сообщений чата.

### Режим 2: Слушать новые сообщения

```
Выберите режим (1-3): 2
Введите ID/username чата: -1001234567890
```

Скрипт будет ждать новые медиа-сообщения и скачивать их автоматически.

### Режим 3: Фильтр по подписи

```
Выберите режим (1-3): 3
Введите ID/username чата: @mychat
Введите подпись для поиска: 0891-1
```

Скачает только сообщения с подписью "0891-1".

## 🔍 Как найти ID чата?

### Для приватного чата (DM):
1. Откройте диалог
2. Нажмите на название чата вверху
3. В URL будет ID (если это веб-версия)
4. Или используйте username если есть

### Для группы/канала:
- **Если есть username**: `@groupname`
- **Если нет username**: сложнее, нужно ID
  1. Добавьте бота в группу
  2. Отправьте команду
  3. Бот вернет ID

### Простой способ:
Можно использовать username вида `@mychannel` вместо числового ID.

## 📁 Структура сохранения

```
~/Downloads/telegram_downloads/
├── 0891-1aBcDe/       # подпись + 5 букв
│   ├── photo1.jpg
│   ├── photo2.jpg
│   ├── photo3.jpg
│   ├── video1.mp4
│   └── video2.mp4
├── 0124-1xYzAb/
│   ├── image.png
│   └── movie.mp4
└── message_12345aBcDe/  # если нет подписи
    └── file.pdf
```

## ⚙️ Дополнительные опции

Можно отредактировать строку в `main()`:
```python
downloads_folder = str(Path.home() / "Downloads" / "telegram_downloads")
```

Чтобы изменить папку сохранения.

## 🔐 Безопасность

- ⚠️ **Не делитесь API Hash** - это как пароль
- 🔒 Сессия сохраняется локально в файле `session_telegram.session`
- 🛡️ Подтверждение по SMS при первом входе

## ❌ Решение проблем

### "Введите код, отправленный в Telegram"
При первом запуске нужно подтвердить вход - введите код из Telegram.

### "Invalid session" или ошибка подключения
Удалите файл `session_telegram.session` и запустите снова.

### Медиа не скачиваются
1. Проверьте, что у вас есть доступ к чату
2. Убедитесь, что это медиа-сообщения, а не ссылки
3. Проверьте место на диске

### Нужен числовой ID чата?
Для групп/каналов используйте:
```python
# В скрипте добавьте это перед запуском:
from telethon.sync import TelegramClient

async def get_chat_id():
    async with TelegramClient('session', API_ID, API_HASH) as client:
        chat = await client.get_entity('@username')
        print(chat.id)
```

## 📝 Примеры

### Скачать из приватного чата
```
Режим: 1
ID чата: 123456789
```

### Слушать канал и скачивать новое
```
Режим: 2
ID чата: @myfinancialchannel
# Будет слушать и скачивать новые медиа
```

### Только конкретные подписи
```
Режим: 3
ID чата: @archive
Подпись: 2024-08
# Скачает только сообщения с "2024-08"
```

## 🐛 Логирование

Скрипт выводит подробные логи:
```
2026-08-17 10:30:45 - INFO - 🔍 Получение сообщений из чата: @mychat
2026-08-17 10:30:47 - INFO - 📁 Создана папка: 0891-1AbCdE
2026-08-17 10:30:48 - INFO - ✅ Скачано: photo1.jpg
```

## 📞 Поддержка

При проблемах с Telethon:
- Документация: https://docs.telethon.dev/
- GitHub issues: https://github.com/LonamiWebs/Telethon/issues
