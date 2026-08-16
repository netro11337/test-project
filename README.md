# Ozon Auto-Registration System

Система полной автоматизации регистрации аккаунтов на платформе Ozon через браузер Chrome.

## 🎯 Основные возможности

### Браузерная автоматизация (актуальное решение):
- ✅ **Полная автоматизация через браузер Chrome** (Playwright)
- ✅ **Интеграция с MegaSMS** для получения номеров телефонов и SMS кодов
- ✅ **Инкогнито режим** - каждый аккаунт в отдельном окне
- ✅ **Автоматическое заполнение профиля** (случайное ФИО, дата рождения, пол)
- ✅ **Добавление email адреса** с автоматическим подтверждением
- ✅ **Графический интерфейс** (Tkinter) для управления процессом
- ✅ **Логирование всех операций** в реальном времени
- ✅ **Результаты в формате**: номер:почта:пароль
- ✅ **Поддержка массовой регистрации** (1-100+ аккаунтов за раз)
- ✅ **Экспорт результатов** в текст или JSON

## 📁 Структура проекта

```
├── ozon_ui_panel.py                 # GUI панель (главное приложение)
├── ozon_browser_automation.py       # Браузерная автоматизация (Playwright)
├── megasms_service.py               # Интеграция с MegaSMS API
├── run_ui.py                        # Лаунчер UI панели
├── BROWSER_AUTOMATION_GUIDE.md      # Подробное руководство
├── requirements.txt                 # Зависимости
└── README.md                        # Этот файл
```

## 🚀 Быстрый старт

### 1. Установка

```bash
# Установить зависимости
pip install -r requirements.txt

# Установить Chromium для Playwright
playwright install chromium
```

### 2. Запуск UI панели

```bash
python run_ui.py
# или
python ozon_ui_panel.py
```

### 3. Использование

1. **Проверить баланс MegaSMS** - убедиться, что есть средства
2. **Загрузить email список** - нажать "Загрузить из файла" или ввести вручную
3. **Указать количество аккаунтов** - от 1 до 100
4. **Нажать "Начать"** - система автоматически создаст аккаунты
5. **Получить результаты** - скопировать или сохранить в файл

## 📋 Процесс регистрации

Система полностью автоматизирует все шаги:

1. Получение номера телефона с MegaSMS
2. Открытие Озон в браузере Chrome (инкогнито)
3. Ввод номера телефона
4. Ожидание 30 сек, затем запрос SMS кода (вместо звонка)
5. Получение и ввод SMS кода
6. Обновление профиля в https://www.ozon.ru/ozonid:
   - Случайное ФИО (генерация на русском)
   - Случайная дата рождения (18-70 лет)
   - Случайный пол (Мужской/Женский)
7. Добавление email адреса
8. Ввод кода подтверждения с email
9. Завершение регистрации
10. Результат: **номер:почта:пароль**

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

### 🆕 Полный цикл регистрации (новое!)

```python
from ozon_autoregister import OzonAutoRegister, OzonAccount
import os
from dotenv import load_dotenv

load_dotenv()

# Инициализация с SMS сервисом
registrar = OzonAutoRegister(
    api_key=os.getenv("OZON_API_KEY"),
    sms_service_url=os.getenv("SMS_SERVICE_URL"),
    sms_api_key=os.getenv("SMS_API_KEY")
)

# Установка списка ПВЗ
registrar.set_pvz_list([
    "pvz_001",
    "pvz_002",
    "pvz_003",
])

# Создание аккаунта
account = OzonAccount(
    email="user@example.com",
    password="SecurePass123",
    phone="+79101234567",
    first_name="Иван",
    last_name="Петров"
)

# Полный цикл:
# 1. Регистрация
# 2. Получение SMS
# 3. Установка случайного ФИО и даты рождения
# 4. Выбор ПВЗ
# 5. Привязка email
success, message, result = registrar.complete_registration_workflow(account)

if success:
    print(f"✓ Готово: {result}")  # Вывод: +79101234567:user@example.com
else:
    print(f"✗ Ошибка: {message}")

# Получить все результаты в формате номер:почта
results = registrar.get_formatted_results()
for res in results:
    print(res)

# Экспортировать результаты
registrar.export_formatted_results("results.txt")
```

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

## 🔗 SMS Интеграция

Система поддерживает интеграцию с внешними SMS сервисами:

- **SMS-Perfect** - надежный российский сервис (1-3 руб за SMS)
- **Twilio** - международный сервис
- **Smspilot** - доступный российский сервис (1-2 руб за SMS)
- **Собственный API** - используйте свой SMS сервис

Подробнее см. [SMS_INTEGRATION.md](SMS_INTEGRATION.md)

### Настройка SMS:

```bash
# .env файл
SMS_SERVICE_URL=https://api.sms-perfect.ru
SMS_API_KEY=your_api_key
```

## 📊 Формат вывода результатов

### Формат номер:почта

```
+79101234567:user1@example.com
+79101234568:user2@example.com
+79101234569:user3@example.com
```

Экспорт результатов:

```python
# В текстовый файл
registrar.export_formatted_results("results.txt")

# Получить в памяти
results = registrar.get_formatted_results()
```

## 📁 Структура проекта

```
├── ozon_autoregister.py         # Основной модуль с регистрацией
├── cli.py                        # Командная строка
├── example_usage.py              # Примеры базовой регистрации
├── example_complete_workflow.py  # Примеры полного цикла
├── config.yaml                   # Файл конфигурации
├── requirements.txt              # Зависимости Python
├── .env.example                  # Пример переменных окружения
├── .gitignore                    # Игнорировать файлы
├── SMS_INTEGRATION.md            # Руководство SMS интеграции
├── README.md                     # Этот файл
├── test_ozon_autoregister.py    # Модульные тесты (24 теста)
└── results/                      # Папка для результатов (создается автоматически)
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