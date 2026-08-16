"""
Command-line interface для Ozon Auto-Registration системы
"""

import argparse
import sys
import json
import os
from pathlib import Path
from dotenv import load_dotenv
from ozon_autoregister import OzonAutoRegister, OzonAccount
import csv
from datetime import datetime


class OzonCLI:
    """CLI для работы с Ozon Auto-Registration"""

    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("OZON_API_KEY")
        self.client_id = os.getenv("OZON_CLIENT_ID")
        self.registrar = OzonAutoRegister(
            api_key=self.api_key,
            client_id=self.client_id
        )

    def register_single(self, args):
        """Регистрация одного аккаунта"""
        print("\n" + "="*60)
        print("РЕГИСТРАЦИЯ ОДНОГО АККАУНТА")
        print("="*60 + "\n")

        if not self.api_key:
            print("❌ Ошибка: OZON_API_KEY не установлен в .env")
            print("Скопируйте .env.example в .env и добавьте ваш API ключ")
            sys.exit(1)

        # Создание аккаунта
        account = OzonAccount(
            email=args.email,
            password=args.password,
            phone=args.phone,
            first_name=args.first_name,
            last_name=args.last_name
        )

        # Валидация
        valid, message = self.registrar.validate_account_data(account)
        if not valid:
            print(f"❌ Ошибка валидации: {message}")
            return

        # Регистрация
        print(f"📝 Регистрация аккаунта {account.email}...")
        success, msg, account_id = self.registrar.register_account(account)

        if success:
            print(f"✅ Успешно!")
            print(f"ID аккаунта: {account_id}")
            print(f"Email: {account.email}")
        else:
            print(f"❌ Ошибка: {msg}")

    def register_from_file(self, args):
        """Регистрация из CSV/JSON файла"""
        print("\n" + "="*60)
        print("МАССОВАЯ РЕГИСТРАЦИЯ ИЗ ФАЙЛА")
        print("="*60 + "\n")

        if not self.api_key:
            print("❌ Ошибка: OZON_API_KEY не установлен в .env")
            return

        if not os.path.exists(args.file):
            print(f"❌ Файл не найден: {args.file}")
            return

        accounts = self._load_accounts_from_file(args.file)
        if not accounts:
            return

        print(f"📄 Загружено {len(accounts)} аккаунтов\n")

        # Регистрация
        results = self.registrar.batch_register(accounts)

        # Вывод результатов
        self._print_results(results)

        # Экспорт
        if args.output:
            self.registrar.export_results(args.output)
            print(f"✅ Результаты сохранены в {args.output}")

    def validate(self, args):
        """Проверка данных"""
        print("\n" + "="*60)
        print("ПРОВЕРКА ДАННЫХ")
        print("="*60 + "\n")

        # Создание аккаунта для валидации
        account = OzonAccount(
            email=args.email or "test@example.com",
            password=args.password or "TestPass123",
            phone=args.phone or "+79101234567",
            first_name=args.first_name or "Test",
            last_name=args.last_name or "User"
        )

        print("Результаты проверки:\n")

        # Email
        email_valid = self.registrar.validate_email(account.email)
        print(f"📧 Email '{account.email}':")
        print(f"   {'✅ Валидный' if email_valid else '❌ Невалидный'}\n")

        # Phone
        phone_valid = self.registrar.validate_phone(account.phone)
        print(f"📱 Телефон '{account.phone}':")
        print(f"   {'✅ Валидный' if phone_valid else '❌ Невалидный'}\n")

        # Password
        pwd_valid, pwd_msg = self.registrar.validate_password(account.password)
        print(f"🔐 Пароль:")
        print(f"   {'✅ Надежный' if pwd_valid else f'❌ {pwd_msg}'}\n")

        # Name
        print(f"👤 Имя '{account.first_name}':")
        print(f"   {'✅ Валидное' if len(account.first_name) >= 2 else '❌ Слишком короткое'}\n")

        print(f"👤 Фамилия '{account.last_name}':")
        print(f"   {'✅ Валидная' if len(account.last_name) >= 2 else '❌ Слишком короткая'}\n")

        # Полная валидация
        full_valid, full_msg = self.registrar.validate_account_data(account)
        print("-"*60)
        print(f"Общая валидация: {'✅ Все данные корректны' if full_valid else f'❌ {full_msg}'}")

    def check_password_strength(self, args):
        """Проверка надежности пароля"""
        print("\n" + "="*60)
        print("ПРОВЕРКА НАДЕЖНОСТИ ПАРОЛЯ")
        print("="*60 + "\n")

        password = args.password

        # Проверка
        is_valid, message = self.registrar.validate_password(password)

        print(f"Пароль: {password}")
        print(f"Статус: {'✅ Надежный' if is_valid else f'❌ Ненадежный'}")

        if not is_valid:
            print(f"Причина: {message}")

        # Подсказки
        print("\n📋 Требования:")
        print("  - Минимум 8 символов")
        print("  - Хотя бы одна заглавная буква (A-Z)")
        print("  - Хотя бы одна строчная буква (a-z)")
        print("  - Хотя бы одна цифра (0-9)")

    def generate_template(self, args):
        """Генерация CSV шаблона для массовой регистрации"""
        output_file = args.output or "accounts_template.csv"

        # Создание примера
        headers = ["email", "password", "phone", "first_name", "last_name"]
        sample_data = [
            ["user1@example.com", "SecurePass1", "+79101234567", "Иван", "Петров"],
            ["user2@example.com", "SecurePass2", "+79101234568", "Мария", "Сидорова"],
            ["user3@example.com", "SecurePass3", "+79101234569", "Петр", "Смирнов"],
        ]

        # Запись в CSV
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(sample_data)

            print(f"✅ Шаблон создан: {output_file}")
            print("\nСтруктура файла:")
            print("  - email: адрес электронной почты")
            print("  - password: пароль (минимум 8 символов, с буквами и цифрами)")
            print("  - phone: телефон (формат: +79101234567 или 89101234567)")
            print("  - first_name: имя")
            print("  - last_name: фамилия")
            print(f"\nОтредактируйте {output_file} и используйте его с командой:")
            print(f"  python cli.py register-file -f {output_file}")

        except Exception as e:
            print(f"❌ Ошибка при создании файла: {e}")

    def export_results(self, args):
        """Экспорт результатов"""
        if not self.registrar.get_registered_accounts():
            print("❌ Нет зарегистрированных аккаунтов для экспорта")
            return

        output_file = args.output or f"results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        self.registrar.export_results(output_file)
        print(f"✅ Результаты экспортированы в {output_file}")

    def show_errors(self, args):
        """Показать все ошибки"""
        errors = self.registrar.get_errors()

        if not errors:
            print("✅ Ошибок не найдено")
            return

        print("\n" + "="*60)
        print("ОШИБКИ")
        print("="*60 + "\n")

        for i, error in enumerate(errors, 1):
            print(f"{i}. {error}")

    def _load_accounts_from_file(self, filepath):
        """Загрузка аккаунтов из файла"""
        accounts = []

        try:
            if filepath.endswith('.csv'):
                with open(filepath, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if not row['email']:
                            continue
                        account = OzonAccount(
                            email=row['email'].strip(),
                            password=row['password'].strip(),
                            phone=row['phone'].strip(),
                            first_name=row['first_name'].strip(),
                            last_name=row['last_name'].strip()
                        )
                        accounts.append(account)

            elif filepath.endswith('.json'):
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for item in data:
                        account = OzonAccount(
                            email=item['email'],
                            password=item['password'],
                            phone=item['phone'],
                            first_name=item['first_name'],
                            last_name=item['last_name']
                        )
                        accounts.append(account)

            else:
                print("❌ Поддерживаются только CSV и JSON файлы")
                return []

            return accounts

        except Exception as e:
            print(f"❌ Ошибка при чтении файла: {e}")
            return []

    def _print_results(self, results):
        """Вывод результатов"""
        print("-"*60)
        print("РЕЗУЛЬТАТЫ")
        print("-"*60)
        print(f"Всего аккаунтов: {results['total']}")
        print(f"✅ Успешно: {results['success']}")
        print(f"❌ Ошибок: {results['failed']}")

        if results['successful_accounts']:
            print("\n✅ Успешно зарегистрированные:")
            for acc in results['successful_accounts']:
                print(f"  - {acc['email']} (ID: {acc['account_id']})")

        if results['failed_accounts']:
            print("\n❌ Ошибки:")
            for acc in results['failed_accounts']:
                print(f"  - {acc['email']}: {acc['error']}")


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(
        description="Ozon Auto-Registration CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:

  # Регистрация одного аккаунта
  python cli.py register --email user@example.com --password StrongPass123 \\
    --phone +79101234567 --first-name Иван --last-name Петров

  # Массовая регистрация из CSV
  python cli.py register-file -f accounts.csv -o results.json

  # Проверка пароля
  python cli.py check-password --password MyPass123

  # Генерация шаблона
  python cli.py template

  # Валидация данных
  python cli.py validate --email user@example.com --password StrongPass123 \\
    --phone +79101234567 --first-name Иван --last-name Петров
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Доступные команды")

    # Регистрация одного аккаунта
    register_parser = subparsers.add_parser("register", help="Регистрация одного аккаунта")
    register_parser.add_argument("--email", required=True, help="Email адрес")
    register_parser.add_argument("--password", required=True, help="Пароль")
    register_parser.add_argument("--phone", required=True, help="Номер телефона")
    register_parser.add_argument("--first-name", required=True, help="Имя")
    register_parser.add_argument("--last-name", required=True, help="Фамилия")

    # Регистрация из файла
    file_parser = subparsers.add_parser("register-file", help="Массовая регистрация из файла")
    file_parser.add_argument("-f", "--file", required=True, help="CSV или JSON файл с данными")
    file_parser.add_argument("-o", "--output", help="Файл для сохранения результатов")

    # Валидация
    validate_parser = subparsers.add_parser("validate", help="Проверка данных")
    validate_parser.add_argument("--email", help="Email адрес")
    validate_parser.add_argument("--password", help="Пароль")
    validate_parser.add_argument("--phone", help="Номер телефона")
    validate_parser.add_argument("--first-name", help="Имя")
    validate_parser.add_argument("--last-name", help="Фамилия")

    # Проверка пароля
    pwd_parser = subparsers.add_parser("check-password", help="Проверка надежности пароля")
    pwd_parser.add_argument("--password", required=True, help="Пароль для проверки")

    # Генерация шаблона
    template_parser = subparsers.add_parser("template", help="Генерация CSV шаблона")
    template_parser.add_argument("-o", "--output", help="Название файла")

    # Ошибки
    subparsers.add_parser("errors", help="Показать все ошибки")

    args = parser.parse_args()

    cli = OzonCLI()

    if args.command == "register":
        cli.register_single(args)
    elif args.command == "register-file":
        cli.register_from_file(args)
    elif args.command == "validate":
        cli.validate(args)
    elif args.command == "check-password":
        cli.check_password_strength(args)
    elif args.command == "template":
        cli.generate_template(args)
    elif args.command == "errors":
        cli.show_errors(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
