"""
Ozon Auto-Registration Module
Автоматическая регистрация аккаунтов в системе Ozon
"""

import re
import json
import time
import requests
from typing import Dict, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass


@dataclass
class OzonAccount:
    """Данные аккаунта Ozon"""
    email: str
    password: str
    phone: str
    first_name: str
    last_name: str
    created_at: str = None
    account_id: str = None


class OzonAutoRegister:
    """
    Класс для автоматической регистрации аккаунтов на платформе Ozon
    """

    # URL APIs
    OZON_API_BASE = "https://api.ozon.ru"
    OZON_AUTH_URL = "https://auth.ozon.ru"

    def __init__(self, api_key: str = None, client_id: str = None):
        """
        Инициализация регистратора Ozon

        Args:
            api_key: API ключ Ozon
            client_id: Client ID для OAuth
        """
        self.api_key = api_key
        self.client_id = client_id
        self.session = requests.Session()
        self.registered_accounts = []
        self.errors = []

    def validate_email(self, email: str) -> bool:
        """Проверка корректности email адреса"""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None

    def validate_phone(self, phone: str) -> bool:
        """Проверка корректности номера телефона (российский формат)"""
        # Удаляем все кроме цифр
        digits = re.sub(r'\D', '', phone)
        # Проверяем, что это 11 цифр и начинается с 7 или 8 (для России)
        return len(digits) == 11 and digits[0] in ['7', '8']

    def validate_password(self, password: str) -> Tuple[bool, str]:
        """
        Проверка надежности пароля

        Требования:
        - Минимум 8 символов
        - Хотя бы одна заглавная буква
        - Хотя бы одна строчная буква
        - Хотя бы одна цифра
        """
        if len(password) < 8:
            return False, "Пароль должен содержать минимум 8 символов"

        if not re.search(r'[A-Z]', password):
            return False, "Пароль должен содержать хотя бы одну заглавную букву"

        if not re.search(r'[a-z]', password):
            return False, "Пароль должен содержать хотя бы одну строчную букву"

        if not re.search(r'\d', password):
            return False, "Пароль должен содержать хотя бы одну цифру"

        return True, "OK"

    def validate_account_data(self, account: OzonAccount) -> Tuple[bool, str]:
        """Полная проверка данных аккаунта"""
        # Проверка email
        if not self.validate_email(account.email):
            return False, f"Некорректный email: {account.email}"

        # Проверка телефона
        if not self.validate_phone(account.phone):
            return False, f"Некорректный номер телефона: {account.phone}"

        # Проверка пароля
        valid, msg = self.validate_password(account.password)
        if not valid:
            return False, msg

        # Проверка имени и фамилии
        if not account.first_name or len(account.first_name) < 2:
            return False, "Имя должно содержать минимум 2 символа"

        if not account.last_name or len(account.last_name) < 2:
            return False, "Фамилия должна содержать минимум 2 символа"

        return True, "OK"

    def register_account(self, account: OzonAccount) -> Tuple[bool, str, Optional[str]]:
        """
        Регистрация нового аккаунта на Ozon

        Args:
            account: Объект OzonAccount с данными для регистрации

        Returns:
            Кортеж (успешно, сообщение, account_id)
        """
        # Валидация данных
        valid, msg = self.validate_account_data(account)
        if not valid:
            error_msg = f"Ошибка валидации: {msg}"
            self.errors.append(error_msg)
            return False, error_msg, None

        try:
            # Подготовка данных для регистрации
            registration_data = {
                "email": account.email,
                "phone": self._normalize_phone(account.phone),
                "password": account.password,
                "first_name": account.first_name,
                "last_name": account.last_name,
                "accept_terms": True,
                "accept_marketing": True
            }

            # Отправка запроса регистрации
            headers = {
                "Content-Type": "application/json",
            }

            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            response = self.session.post(
                f"{self.OZON_AUTH_URL}/register",
                json=registration_data,
                headers=headers,
                timeout=10
            )

            # Обработка ответа
            if response.status_code == 201:
                response_data = response.json()
                account_id = response_data.get("account_id")
                account.account_id = account_id
                account.created_at = datetime.now().isoformat()

                self.registered_accounts.append(account)
                success_msg = f"Аккаунт успешно создан. ID: {account_id}"
                return True, success_msg, account_id

            elif response.status_code == 400:
                error_data = response.json()
                error_msg = error_data.get("message", "Ошибка в данных регистрации")
                self.errors.append(error_msg)
                return False, f"Ошибка валидации: {error_msg}", None

            elif response.status_code == 409:
                error_msg = "Email уже зарегистрирован в системе"
                self.errors.append(error_msg)
                return False, error_msg, None

            else:
                error_msg = f"Ошибка сервера: {response.status_code}"
                self.errors.append(error_msg)
                return False, error_msg, None

        except requests.exceptions.Timeout:
            error_msg = "Таймаут при подключении к серверу Ozon"
            self.errors.append(error_msg)
            return False, error_msg, None

        except requests.exceptions.ConnectionError:
            error_msg = "Ошибка подключения к серверу Ozon"
            self.errors.append(error_msg)
            return False, error_msg, None

        except Exception as e:
            error_msg = f"Неожиданная ошибка: {str(e)}"
            self.errors.append(error_msg)
            return False, error_msg, None

    def batch_register(self, accounts: list) -> Dict:
        """
        Массовая регистрация аккаунтов

        Args:
            accounts: Список OzonAccount объектов

        Returns:
            Словарь с результатами
        """
        results = {
            "total": len(accounts),
            "success": 0,
            "failed": 0,
            "successful_accounts": [],
            "failed_accounts": []
        }

        for i, account in enumerate(accounts):
            print(f"Регистрация аккаунта {i+1}/{len(accounts)}...")
            success, msg, account_id = self.register_account(account)

            if success:
                results["success"] += 1
                results["successful_accounts"].append({
                    "email": account.email,
                    "account_id": account_id
                })
            else:
                results["failed"] += 1
                results["failed_accounts"].append({
                    "email": account.email,
                    "error": msg
                })

            # Небольшая задержка между запросами
            time.sleep(0.5)

        return results

    def _normalize_phone(self, phone: str) -> str:
        """Нормализация номера телефона в формат 7XXXXXXXXXX"""
        digits = re.sub(r'\D', '', phone)
        if digits[0] == '8':
            digits = '7' + digits[1:]
        return f"+{digits}"

    def get_registered_accounts(self) -> list:
        """Получить список зарегистрированных аккаунтов"""
        return self.registered_accounts

    def get_errors(self) -> list:
        """Получить список ошибок"""
        return self.errors

    def export_results(self, filepath: str):
        """Экспортировать результаты регистрации в JSON"""
        results = {
            "registered_accounts": [
                {
                    "email": acc.email,
                    "account_id": acc.account_id,
                    "created_at": acc.created_at
                }
                for acc in self.registered_accounts
            ],
            "errors": self.errors,
            "total_registered": len(self.registered_accounts)
        }

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        print(f"Результаты сохранены в {filepath}")


def create_test_accounts(count: int = 3) -> list:
    """Создание тестовых аккаунтов для примера"""
    accounts = []
    for i in range(count):
        account = OzonAccount(
            email=f"ozon_test_{i+1}_{int(time.time())}@example.com",
            password=f"TestPass123{i}",
            phone=f"7910000{i:04d}",
            first_name=f"Test{i+1}",
            last_name=f"User{i+1}"
        )
        accounts.append(account)
    return accounts


if __name__ == "__main__":
    # Пример использования
    print("=== Ozon Auto-Registration System ===\n")

    # Инициализация регистратора (без реальных API ключей для примера)
    registrar = OzonAutoRegister()

    # Создание тестовых аккаунтов
    test_accounts = create_test_accounts(2)

    # Регистрация каждого аккаунта
    print("Начало регистрации аккаунтов...")
    for account in test_accounts:
        success, msg, account_id = registrar.register_account(account)
        print(f"Email: {account.email}")
        print(f"Статус: {'✓ Успешно' if success else '✗ Ошибка'}")
        print(f"Сообщение: {msg}\n")

    # Вывод статистики
    print("\n=== Статистика ===")
    print(f"Всего попыток: {len(test_accounts)}")
    print(f"Успешно: {len(registrar.get_registered_accounts())}")
    print(f"Ошибок: {len(registrar.get_errors())}")

    if registrar.get_errors():
        print("\n=== Ошибки ===")
        for error in registrar.get_errors():
            print(f"- {error}")
