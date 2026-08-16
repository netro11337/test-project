"""
Пример полного цикла регистрации с обновлением профиля
"""

from ozon_autoregister import OzonAutoRegister, OzonAccount
from dotenv import load_dotenv
import os


def example_1_single_account_complete_workflow():
    """Пример 1: Полный цикл для одного аккаунта"""
    print("\n" + "="*60)
    print("ПРИМЕР 1: Полный цикл регистрации одного аккаунта")
    print("="*60 + "\n")

    load_dotenv()
    api_key = os.getenv("OZON_API_KEY")
    sms_service_url = os.getenv("SMS_SERVICE_URL")
    sms_api_key = os.getenv("SMS_API_KEY")

    # Инициализация регистратора с SMS сервисом
    registrar = OzonAutoRegister(
        api_key=api_key,
        sms_service_url=sms_service_url,
        sms_api_key=sms_api_key
    )

    # Задаем список ПВЗ (замените на реальные ID)
    registrar.set_pvz_list([
        "00000000000000000001",
        "00000000000000000002",
        "00000000000000000003",
    ])

    # Создание аккаунта
    account = OzonAccount(
        email="complete_user_123@example.com",
        password="SecurePass123!",
        phone="+79101234567",
        first_name="Иван",
        last_name="Петров"
    )

    # Полный цикл (регистрация + профиль + ПВЗ + email)
    success, message, formatted_result = registrar.complete_registration_workflow(account)

    print(f"\n{'='*60}")
    print("РЕЗУЛЬТАТЫ:")
    print(f"{'='*60}")
    print(f"Статус: {'✓ Успешно' if success else '✗ Ошибка'}")
    print(f"Сообщение: {message}")
    if formatted_result:
        print(f"Результат (номер:почта): {formatted_result}")


def example_2_batch_complete_workflow():
    """Пример 2: Полный цикл для нескольких аккаунтов"""
    print("\n" + "="*60)
    print("ПРИМЕР 2: Полный цикл для нескольких аккаунтов")
    print("="*60 + "\n")

    load_dotenv()
    api_key = os.getenv("OZON_API_KEY")
    sms_service_url = os.getenv("SMS_SERVICE_URL")
    sms_api_key = os.getenv("SMS_API_KEY")

    # Инициализация
    registrar = OzonAutoRegister(
        api_key=api_key,
        sms_service_url=sms_service_url,
        sms_api_key=sms_api_key
    )

    # Установка списка ПВЗ
    pvz_list = [
        "00000000000000000001",
        "00000000000000000002",
        "00000000000000000003",
        "00000000000000000004",
        "00000000000000000005",
    ]
    registrar.set_pvz_list(pvz_list)

    # Создание списка аккаунтов
    accounts = [
        OzonAccount(
            email=f"batch_user_{i}@example.com",
            password=f"SecurePass{i}!",
            phone=f"+791010{i:05d}",
            first_name=f"Name{i}",
            last_name=f"User{i}"
        )
        for i in range(1, 4)
    ]

    # Полный цикл для всех
    results = registrar.batch_complete_workflow(accounts, use_random_profile=True)

    # Вывод результатов
    print("\n" + "="*60)
    print("ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
    print("="*60)
    print(f"Всего аккаунтов: {results['total']}")
    print(f"✓ Успешно завершено: {results['success']}")
    print(f"✗ Ошибок: {results['failed']}")

    if results['completed_accounts']:
        print("\n✓ Успешно завершенные аккаунты:")
        for acc in results['completed_accounts']:
            print(f"  • {acc['phone']} -> {acc['email']} (PVZ: {acc['pvz_id']})")

    if results['failed_accounts']:
        print("\n✗ Ошибки:")
        for acc in results['failed_accounts']:
            print(f"  • {acc['phone']}: {acc['error']}")

    # Вывод в формате номер:почта
    print("\n" + "="*60)
    print("РЕЗУЛЬТАТЫ В ФОРМАТЕ НОМЕР:ПОЧТА")
    print("="*60)
    for result in results['results_formatted']:
        print(result)

    # Сохранение результатов
    print("\n" + "="*60)
    registrar.export_formatted_results("results_formatted.txt")

    # Сохранение полных данных
    import json
    full_results = {
        "summary": {
            "total": results['total'],
            "success": results['success'],
            "failed": results['failed']
        },
        "completed_accounts": results['completed_accounts'],
        "results_formatted": results['results_formatted'],
        "errors": registrar.get_errors()
    }

    with open("results_full.json", 'w', encoding='utf-8') as f:
        json.dump(full_results, f, ensure_ascii=False, indent=2)

    print("✓ Полные результаты сохранены в results_full.json")


def example_3_custom_pvz_list():
    """Пример 3: Использование пользовательского списка ПВЗ"""
    print("\n" + "="*60)
    print("ПРИМЕР 3: Использование пользовательского списка ПВЗ")
    print("="*60 + "\n")

    # Ваш список ПВЗ (ID пунктов выдачи)
    my_pvz_list = [
        "pvz_moscow_001",
        "pvz_moscow_002",
        "pvz_spb_001",
        "pvz_spb_002",
        "pvz_ekb_001",
    ]

    load_dotenv()
    api_key = os.getenv("OZON_API_KEY")

    registrar = OzonAutoRegister(api_key=api_key, pvz_list=my_pvz_list)

    account = OzonAccount(
        email="pvz_test@example.com",
        password="SecurePass123!",
        phone="+79101234567",
        first_name="Тест",
        last_name="ПВЗ"
    )

    success, message, result = registrar.complete_registration_workflow(account)

    print(f"Статус: {'✓ Успешно' if success else '✗ Ошибка'}")
    if success:
        print(f"Результат: {result}")
        print(f"Установленный ПВЗ: {account.pvz_id}")


def example_4_manual_profile():
    """Пример 4: Использование собственных данных профиля"""
    print("\n" + "="*60)
    print("ПРИМЕР 4: Использование собственных данных профиля")
    print("="*60 + "\n")

    load_dotenv()
    api_key = os.getenv("OZON_API_KEY")

    registrar = OzonAutoRegister(api_key=api_key)

    account = OzonAccount(
        email="manual_profile@example.com",
        password="SecurePass123!",
        phone="+79101234567",
        first_name="Вручную",
        last_name="Указанный",
        middle_name="Иванович",
        birth_date="1990-01-15"  # YYYY-MM-DD
    )

    # Полный цикл БЕЗ использования случайных данных
    success, message, result = registrar.complete_registration_workflow(
        account,
        use_random_profile=False
    )

    print(f"Статус: {'✓ Успешно' if success else '✗ Ошибка'}")
    if success:
        print(f"ФИО: {account.first_name} {account.middle_name} {account.last_name}")
        print(f"Дата рождения: {account.birth_date}")
        print(f"Результат: {result}")


def main():
    """Главная функция"""
    print("\n" + "="*60)
    print("ПРИМЕРЫ ПОЛНОГО ЦИКЛА РЕГИСТРАЦИИ OZON")
    print("="*60)

    print("""
ПРИМЕЧАНИЕ:
Перед запуском убедитесь, что в файле .env установлены:
- OZON_API_KEY: Ваш API ключ Ozon
- SMS_SERVICE_URL: URL вашего SMS сервиса (опционально)
- SMS_API_KEY: API ключ SMS сервиса (опционально)

Примеры требуют настроенной интеграции с реальными API!
    """)

    # Запуск примеров (которые не требуют реальных API)
    print("\n⚠ Запуск примеров в демонстрационном режиме...")
    print("Некоторые примеры требуют реальных API ключей Ozon и SMS сервиса.")
    print("\nДля полного функционала:")
    print("1. Получите API ключ у Ozon")
    print("2. Настройте SMS сервис (например, Twilio, SMS-Perfect и т.д.)")
    print("3. Обновите .env файл")
    print("4. Запустите примеры")


if __name__ == "__main__":
    main()

    # Раскомментируйте нужный пример:
    # example_1_single_account_complete_workflow()
    # example_2_batch_complete_workflow()
    # example_3_custom_pvz_list()
    # example_4_manual_profile()
