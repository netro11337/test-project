"""
Примеры использования Ozon Auto-Registration модуля
"""

from ozon_autoregister import OzonAutoRegister, OzonAccount
from dotenv import load_dotenv
import os
import json
from datetime import datetime


def example_1_single_registration():
    """Пример 1: Регистрация одного аккаунта"""
    print("\n" + "="*60)
    print("ПРИМЕР 1: Регистрация одного аккаунта")
    print("="*60 + "\n")

    # Загрузка переменных окружения
    load_dotenv()
    api_key = os.getenv("OZON_API_KEY")

    # Инициализация регистратора
    registrar = OzonAutoRegister(api_key=api_key)

    # Создание данных аккаунта
    account = OzonAccount(
        email="new_user_123@example.com",
        password="SecurePass123",
        phone="+79101234567",
        first_name="Иван",
        last_name="Петров"
    )

    # Регистрация
    success, message, account_id = registrar.register_account(account)

    print(f"Email: {account.email}")
    print(f"Результат: {'✓ Успешно' if success else '✗ Ошибка'}")
    print(f"Сообщение: {message}")
    if account_id:
        print(f"ID аккаунта: {account_id}")


def example_2_batch_registration():
    """Пример 2: Массовая регистрация нескольких аккаунтов"""
    print("\n" + "="*60)
    print("ПРИМЕР 2: Массовая регистрация аккаунтов")
    print("="*60 + "\n")

    load_dotenv()
    api_key = os.getenv("OZON_API_KEY")

    # Инициализация регистратора
    registrar = OzonAutoRegister(api_key=api_key)

    # Создание списка аккаунтов
    accounts = [
        OzonAccount(
            email=f"user_{i}@example.com",
            password=f"SecurePass{i}!",
            phone=f"+7910{i:07d}",
            first_name=f"Name{i}",
            last_name=f"User{i}"
        )
        for i in range(1, 4)
    ]

    # Массовая регистрация
    results = registrar.batch_register(accounts)

    # Вывод результатов
    print("\n" + "-"*60)
    print("РЕЗУЛЬТАТЫ МАССОВОЙ РЕГИСТРАЦИИ")
    print("-"*60)
    print(f"Всего аккаунтов: {results['total']}")
    print(f"Успешно зарегистрировано: {results['success']}")
    print(f"Ошибок: {results['failed']}")

    if results['successful_accounts']:
        print("\n✓ Успешно зарегистрированные:")
        for acc in results['successful_accounts']:
            print(f"  - {acc['email']} (ID: {acc['account_id']})")

    if results['failed_accounts']:
        print("\n✗ Ошибки при регистрации:")
        for acc in results['failed_accounts']:
            print(f"  - {acc['email']}: {acc['error']}")

    # Экспортировать результаты
    registrar.export_results("registration_results.json")


def example_3_validation():
    """Пример 3: Проверка данных перед регистрацией"""
    print("\n" + "="*60)
    print("ПРИМЕР 3: Валидация данных")
    print("="*60 + "\n")

    registrar = OzonAutoRegister()

    # Проверка email
    print("Проверка email адресов:")
    emails = [
        "valid@example.com",
        "invalid.email",
        "user@test.ru"
    ]
    for email in emails:
        is_valid = registrar.validate_email(email)
        print(f"  {email}: {'✓ Валидный' if is_valid else '✗ Невалидный'}")

    # Проверка телефонов
    print("\nПроверка номеров телефонов (Россия):")
    phones = [
        "+79101234567",
        "89101234567",
        "+7910123456",  # Неправильное количество цифр
        "+14155552671"  # Не русский номер
    ]
    for phone in phones:
        is_valid = registrar.validate_phone(phone)
        print(f"  {phone}: {'✓ Валидный' if is_valid else '✗ Невалидный'}")

    # Проверка пароля
    print("\nПроверка надежности пароля:")
    passwords = [
        "WeakPass",
        "StrongPass123",
        "NoDigits!",
        "nouppercase123"
    ]
    for password in passwords:
        is_valid, message = registrar.validate_password(password)
        status = '✓ Надежный' if is_valid else f'✗ {message}'
        print(f"  '{password}': {status}")


def example_4_error_handling():
    """Пример 4: Обработка ошибок"""
    print("\n" + "="*60)
    print("ПРИМЕР 4: Обработка ошибок")
    print("="*60 + "\n")

    registrar = OzonAutoRegister()

    # Попытка регистрации с неправильными данными
    invalid_accounts = [
        OzonAccount(
            email="not_an_email",  # Неправильный email
            password="pass123",
            phone="+79101234567",
            first_name="John",
            last_name="Doe"
        ),
        OzonAccount(
            email="user@example.com",
            password="weak",  # Слабый пароль
            phone="+79101234567",
            first_name="Jane",
            last_name="Smith"
        ),
        OzonAccount(
            email="user2@example.com",
            password="StrongPass123",
            phone="123",  # Неправильный номер
            first_name="A",  # Слишком короткое имя
            last_name="B"
        )
    ]

    print("Попытка регистрации с неправильными данными:\n")
    for account in invalid_accounts:
        success, message, _ = registrar.register_account(account)
        print(f"Email: {account.email}")
        print(f"Статус: {'✓ Успешно' if success else '✗ Ошибка'}")
        print(f"Сообщение: {message}\n")

    # Вывод всех ошибок
    if registrar.get_errors():
        print("="*60)
        print("ВСЕ ОШИБКИ:")
        print("="*60)
        for i, error in enumerate(registrar.get_errors(), 1):
            print(f"{i}. {error}")


def example_5_export_data():
    """Пример 5: Экспорт результатов"""
    print("\n" + "="*60)
    print("ПРИМЕР 5: Экспорт результатов")
    print("="*60 + "\n")

    registrar = OzonAutoRegister()

    # Создаем несколько аккаунтов
    accounts = [
        OzonAccount(
            email=f"export_test_{i}@example.com",
            password=f"ExportTest{i}!",
            phone=f"+7910{i:07d}",
            first_name=f"Test{i}",
            last_name=f"User{i}"
        )
        for i in range(1, 3)
    ]

    # Регистрируем (в реальном случае будет подключение к API)
    for account in accounts:
        registrar.register_account(account)

    # Экспортируем результаты
    output_file = "results/registration_results.json"
    registrar.export_results(output_file)
    print(f"✓ Результаты экспортированы в {output_file}")

    # Показываем содержимое файла
    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"\nВсего зарегистрировано: {data['total_registered']}")
    except FileNotFoundError:
        print(f"Примечание: файл {output_file} будет создан после настройки API ключа")


def main():
    """Главная функция с меню примеров"""
    print("\n" + "="*60)
    print("OZON AUTO-REGISTRATION - ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ")
    print("="*60)

    examples = {
        "1": ("Регистрация одного аккаунта", example_1_single_registration),
        "2": ("Массовая регистрация", example_2_batch_registration),
        "3": ("Валидация данных", example_3_validation),
        "4": ("Обработка ошибок", example_4_error_handling),
        "5": ("Экспорт результатов", example_5_export_data),
        "all": ("Все примеры", None)
    }

    print("\nДоступные примеры:")
    for key, (description, _) in examples.items():
        if key != "all":
            print(f"  {key}. {description}")
    print("  all. Запустить все примеры")

    # Запуск всех примеров для демонстрации
    print("\n" + "="*60)
    print("Запуск примеров...")
    print("="*60)

    example_3_validation()  # Валидация (не требует API)
    example_4_error_handling()  # Обработка ошибок (не требует API)

    # Остальные примеры требуют настройки API ключа
    print("\n" + "="*60)
    print("ПРИМЕЧАНИЕ")
    print("="*60)
    print("Примеры 1, 2 и 5 требуют настройки OZON_API_KEY в файле .env")
    print("Скопируйте .env.example в .env и добавьте ваш API ключ Ozon")
    print("Затем переполните эти примеры для полного тестирования")


if __name__ == "__main__":
    main()
