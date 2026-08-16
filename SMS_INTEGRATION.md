# SMS Integration Guide / Руководство интеграции SMS

## Описание

Система поддерживает интеграцию с внешними SMS сервисами для получения кодов подтверждения при регистрации новых аккаунтов на платформе Ozon.

## Поддерживаемые SMS Сервисы

### 1. SMS-Perfect
- **URL**: https://api.sms-perfect.ru
- **Документация**: https://sms-perfect.ru/api
- **Аутентификация**: API Key в заголовке Authorization

```bash
SMS_SERVICE_URL=https://api.sms-perfect.ru
SMS_API_KEY=your_api_key
```

### 2. Twilio
- **URL**: https://api.twilio.com
- **Документация**: https://www.twilio.com/docs/sms/api
- **Аутентификация**: Basic Auth (Account SID:Auth Token)

```bash
SMS_SERVICE_URL=https://api.twilio.com
SMS_API_KEY=base64_encoded_credentials
```

### 3. Smspilot
- **URL**: https://smspilot.ru/api
- **Документация**: https://smspilot.ru/api-reference
- **Аутентификация**: API Key

```bash
SMS_SERVICE_URL=https://smspilot.ru/api
SMS_API_KEY=your_api_key
```

### 4. MessageBird
- **URL**: https://rest.messagebird.com
- **Документация**: https://developers.messagebird.com/api/sms-messaging/
- **Аутентификация**: API Key в заголовке Authorization

```bash
SMS_SERVICE_URL=https://rest.messagebird.com
SMS_API_KEY=your_api_key
```

## Интеграция с собственным SMS сервисом

Если вы хотите использовать собственный SMS сервис, требуется:

### 1. Реализовать два API endpoint:

#### GET /api/get-sms
Получить SMS код для номера телефона

**Параметры:**
```
phone: строка (например, "79101234567")
```

**Ответ при успехе (200):**
```json
{
  "code": "123456",
  "phone": "79101234567",
  "expires_in": 300
}
```

**Ответ при ошибке (400):**
```json
{
  "error": "SMS not sent",
  "message": "Invalid phone number"
}
```

#### POST /api/verify-sms
Проверить SMS код

**Тело запроса:**
```json
{
  "phone": "79101234567",
  "code": "123456"
}
```

**Ответ при успехе (200):**
```json
{
  "verified": true,
  "message": "SMS code verified"
}
```

**Ответ при ошибке (400):**
```json
{
  "verified": false,
  "message": "Invalid SMS code"
}
```

### 2. Настроить в .env:

```bash
SMS_SERVICE_URL=https://your-sms-service.com/api
SMS_API_KEY=your_secret_key
```

## Использование в коде

### Простой пример:

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

# Создание аккаунта
account = OzonAccount(
    email="user@example.com",
    password="SecurePass123",
    phone="+79101234567",
    first_name="Иван",
    last_name="Петров"
)

# Полный цикл (регистрация + SMS + профиль + ПВЗ + email)
success, message, result = registrar.complete_registration_workflow(account)

if success:
    print(f"✓ Готово: {result}")  # Выведет: +79101234567:user@example.com
else:
    print(f"✗ Ошибка: {message}")
```

## Поток работы

```
1. Регистрация аккаунта на Ozon
   ↓
2. Получение SMS кода с сервиса
   (система запрашивает код по номеру телефона)
   ↓
3. Проверка SMS кода
   (система проверяет полученный код)
   ↓
4. Обновление профиля
   (установка случайного ФИО и даты рождения)
   ↓
5. Установка ПВЗ
   (выбор пункта выдачи из списка)
   ↓
6. Привязка email
   (связывание аккаунта с email адресом)
   ↓
7. Формирование результата
   (формат: номер:почта)
```

## Обработка ошибок

Система автоматически обрабатывает следующие ошибки:

### SMS сервис недоступен
```python
# Система вернет None при ошибке подключения
sms_code = self.sms_service.get_sms_code(phone)
if not sms_code:
    print("Не удалось получить SMS код")
```

### Неверный номер телефона
```python
# Система проверяет формат перед отправкой
if not registrar.validate_phone(phone):
    print("Некорректный номер телефона")
```

### Таймаут при получении SMS
```python
# Таймаут по умолчанию 10 секунд, можно настроить
```

## Тестирование SMS интеграции

### 1. Проверка подключения:

```python
from ozon_autoregister import SMSService
import os
from dotenv import load_dotenv

load_dotenv()

sms = SMSService(
    os.getenv("SMS_SERVICE_URL"),
    os.getenv("SMS_API_KEY")
)

# Попытка получить SMS
code = sms.get_sms_code("+79101234567")
if code:
    print(f"✓ Получен SMS код: {code}")
else:
    print("✗ Ошибка при получении SMS")
```

### 2. Проверка верификации:

```python
verified = sms.verify_sms_code("+79101234567", "123456")
if verified:
    print("✓ SMS код верный")
else:
    print("✗ SMS код неверный")
```

## Рекомендуемые SMS сервисы для России

| Сервис | Цена | Надежность | Скорость |
|--------|------|-----------|----------|
| SMS-Perfect | 1-3 руб | ⭐⭐⭐⭐⭐ | <1 сек |
| Smspilot | 1-2 руб | ⭐⭐⭐⭐ | <2 сек |
| Twilion (RU) | 2-5 руб | ⭐⭐⭐⭐ | <1 сек |
| Обрани | 0.5-1 руб | ⭐⭐⭐ | <5 сек |

## Безопасность

### Важно:
- **Никогда** не передавайте SMS_API_KEY в коде
- Используйте переменные окружения (.env файл)
- Не логируйте SMS коды в логах
- Убедитесь, что .env файл в .gitignore

### Пример безопасного использования:

```python
# ✓ Правильно
api_key = os.getenv("SMS_API_KEY")
registrar = OzonAutoRegister(sms_api_key=api_key)

# ✗ Неправильно
registrar = OzonAutoRegister(sms_api_key="my_secret_key_12345")
```

## Мониторинг и логирование

Система логирует все операции с SMS:

```python
# Просмотр ошибок
errors = registrar.get_errors()
for error in errors:
    print(error)
```

## Стоимость и оптимизация

### Оптимизация расходов:
1. Использование пулинга номеров (получение SMS один раз)
2. Кэширование кодов для одного номера
3. Установка минимального интервала между SMS (5-10 сек)

### Пример:

```python
# Получить SMS один раз и использовать для всех попыток
sms_codes = {}

def get_cached_sms(phone, registrar):
    if phone not in sms_codes:
        sms_codes[phone] = registrar.sms_service.get_sms_code(phone)
    return sms_codes[phone]
```

## Чек-лист для интеграции

- [ ] Выбран SMS сервис
- [ ] Получены API ключи
- [ ] Добавлены в .env файл
- [ ] Тестирование подключения пройдено
- [ ] Обработка ошибок реализована
- [ ] Логирование настроено
- [ ] Документация обновлена
- [ ] Стоимость рассчитана

## Контакты и поддержка

При возникновении проблем:
1. Проверьте логи в `ozon_autoregister.log`
2. Убедитесь, что SMS_SERVICE_URL и SMS_API_KEY правильные
3. Тестируйте API endpoint вручную через curl
4. Проверьте документацию вашего SMS сервиса
