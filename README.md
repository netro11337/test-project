# Ozon Auto-Registration System

Система автоматической регистрации аккаунтов на платформе Ozon.

## 📋 Описание

Этот проект предоставляет полнофункциональное решение для автоматической регистрации аккаунтов на платформе Ozon. Система включает:

- ✅ Валидацию данных (email, телефон, пароль)
- ✅ Регистрацию одного или нескольких аккаунтов
- ✅ Обработку ошибок с детальной информацией
- ✅ Экспорт результатов в JSON формат
- ✅ Интеграция с Ozon API
- ✅ Поддержку конфигурационных файлов

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка окружения

Скопируйте файл конфигурации:

```bash
cp .env.example .env
```

Добавьте ваш API ключ Ozon в файл `.env`:

```
OZON_API_KEY=your_api_key_here
OZON_CLIENT_ID=your_client_id_here
```

### 3. Запуск примеров

```bash
python example_usage.py
```

## 📖 Использование

### Базовая регистрация

```python
from ozon_autoregister import OzonAutoRegister, OzonAccount

# Инициализация
registrar = OzonAutoRegister(api_key="your_api_key")

# Создание аккаунта
account = OzonAccount(
    email="user@example.com",
    password="SecurePass123",
    phone="+79101234567",
    first_name="Иван",
    last_name="Петров"
)

# Регистрация
success, message, account_id = registrar.register_account(account)

if success:
    print(f"✓ Аккаунт создан. ID: {account_id}")
else:
    print(f"✗ Ошибка: {message}")
```

### Массовая регистрация

```python
from ozon_autoregister import OzonAutoRegister, OzonAccount

registrar = OzonAutoRegister(api_key="your_api_key")

# Создание списка аккаунтов
accounts = [
    OzonAccount(
        email=f"user_{i}@example.com",
        password=f"SecurePass{i}!",
        phone=f"+7910{i:07d}",
        first_name=f"Name{i}",
        last_name=f"User{i}"
    )
    for i in range(1, 11)
]

# Массовая регистрация
results = registrar.batch_register(accounts)

print(f"Успешно: {results['success']}")
print(f"Ошибок: {results['failed']}")

# Экспорт результатов
registrar.export_results("results.json")
```

### Валидация данных

```python
from ozon_autoregister import OzonAutoRegister

registrar = OzonAutoRegister()

# Проверка email
is_valid = registrar.validate_email("user@example.com")

# Проверка телефона
is_valid = registrar.validate_phone("+79101234567")

# Проверка пароля
is_valid, message = registrar.validate_password("StrongPass123")
```

## 📁 Структура проекта

```
├── ozon_autoregister.py    # Основной модуль
├── config.yaml             # Файл конфигурации
├── requirements.txt        # Зависимости Python
├── .env.example           # Пример переменных окружения
├── example_usage.py       # Примеры использования
├── README.md              # Этот файл
└── results/               # Папка для результатов
```

## 🔒 Требования к паролю

- Минимум 8 символов
- Хотя бы одна заглавная буква (A-Z)
- Хотя бы одна строчная буква (a-z)
- Хотя бы одна цифра (0-9)

**Пример надежного пароля:** `MyPass123`

## 📞 Требования к телефону

- Поддерживаются номера России
- Форматы: `+79101234567` или `89101234567`
- Всего 11 цифр (включая код страны)

## 📧 Требования к email

- Валидный формат (example@domain.com)
- Уникальность в системе Ozon

## ⚙️ Конфигурация

Отредактируйте файл `config.yaml` для настройки:

- Таймауты API запросов
- Задержка между регистрациями
- Требования к валидации
- Настройки логирования
- Параметры экспорта

## 🐛 Обработка ошибок

Система автоматически обрабатывает следующие ошибки:

- Некорректный формат данных (400)
- Email уже зарегистрирован (409)
- Ошибки подключения к серверу
- Таймауты запросов

Все ошибки сохраняются и могут быть экспортированы:

```python
errors = registrar.get_errors()
for error in errors:
    print(error)
```

## 📊 Экспорт результатов

Результаты автоматически сохраняются в JSON формат:

```json
{
  "registered_accounts": [
    {
      "email": "user@example.com",
      "account_id": "123456",
      "created_at": "2024-01-01T10:30:00"
    }
  ],
  "errors": [],
  "total_registered": 1
}
```

## 🔑 Получение API ключа Ozon

1. Перейдите на [https://ozon.ru](https://ozon.ru)
2. Авторизуйтесь в личном кабинете
3. Перейдите в раздел "API и интеграции"
4. Создайте новое приложение
5. Скопируйте API ключ и Client ID

## 📝 Логирование

Все операции логируются в файл `ozon_autoregister.log`. Уровень логирования настраивается в `config.yaml`.

## 🤝 Поддержка

При возникновении проблем:

1. Проверьте формат данных (используйте валидацию)
2. Убедитесь, что API ключ правильно добавлен в `.env`
3. Проверьте логи в `ozon_autoregister.log`
4. Посмотрите ошибки через `registrar.get_errors()`

## ⚖️ Лицензия

Этот проект предоставляется в образовательных целях.

## 📚 Дополнительные ресурсы

- [Документация Ozon API](https://api.ozon.ru/docs/)
- [Ozon Seller Portal](https://seller.ozon.ru/)
- [Python requests библиотека](https://requests.readthedocs.io/)