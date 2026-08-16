"""
MegaSMS Service Integration
Получение номеров телефонов и SMS кодов с сервиса MegaSMS
"""

import requests
import time
from typing import Optional, Tuple, List
from dataclasses import dataclass


@dataclass
class SMSMessage:
    """SMS сообщение"""
    phone: str
    code: str
    timestamp: str


class MegaSMSService:
    """Работа с MegaSMS API"""

    def __init__(self, api_key: str):
        """
        Инициализация MegaSMS сервиса

        Args:
            api_key: API ключ MegaSMS
        """
        self.api_key = api_key
        self.base_url = "https://megasms.lol/api"
        self.session = requests.Session()

    def get_phone_number(self, service: str = "ozончик") -> Optional[str]:
        """
        Получить номер телефона для регистрации

        Args:
            service: Сервис (по умолчанию 'ozончик')

        Returns:
            Номер телефона или None при ошибке
        """
        try:
            response = self.session.get(
                f"{self.base_url}/get",
                params={
                    "apikey": self.api_key,
                    "service": service,
                    "lang": "en"
                },
                timeout=10
            )

            if response.status_code == 200:
                data = response.text
                # API возвращает: активирован:номер_телефона:ID_активации
                if ":" in data:
                    parts = data.split(":")
                    if len(parts) >= 3:
                        phone_id = parts[1]
                        activation_id = parts[2]
                        return {
                            "phone": phone_id,
                            "activation_id": activation_id,
                            "raw": data
                        }
                return None
            else:
                print(f"Ошибка при получении номера: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            print(f"Ошибка подключения к MegaSMS: {str(e)}")
            return None

    def get_sms_code(self, activation_id: str, attempt: int = 1) -> Optional[str]:
        """
        Получить SMS код

        Args:
            activation_id: ID активации из get_phone_number
            attempt: Номер попытки (по умолчанию 1)

        Returns:
            SMS код или None
        """
        try:
            response = self.session.get(
                f"{self.base_url}/status",
                params={
                    "apikey": self.api_key,
                    "id": activation_id
                },
                timeout=10
            )

            if response.status_code == 200:
                data = response.text
                # API возвращает: статус:код или просто статус
                if ":" in data:
                    parts = data.split(":")
                    if len(parts) >= 2:
                        status = parts[0]
                        sms_code = parts[1]
                        if status == "ok":
                            return sms_code
                        elif status == "wait_sms":
                            return None  # SMS еще не пришла
                        elif status == "no_activation":
                            return None  # Активация не найдена
                return None

        except Exception as e:
            print(f"Ошибка при получении SMS кода: {str(e)}")
            return None

    def wait_for_sms(self, activation_id: str, max_wait: int = 120,
                     check_interval: int = 5) -> Optional[str]:
        """
        Ждать SMS код с таймаутом

        Args:
            activation_id: ID активации
            max_wait: Максимальное время ожидания (сек)
            check_interval: Интервал проверки (сек)

        Returns:
            SMS код или None если истекло время
        """
        elapsed = 0
        while elapsed < max_wait:
            sms_code = self.get_sms_code(activation_id)
            if sms_code:
                return sms_code

            time.sleep(check_interval)
            elapsed += check_interval
            print(f"Ожидание SMS... ({elapsed}/{max_wait} сек)")

        return None

    def cancel_activation(self, activation_id: str) -> bool:
        """
        Отменить активацию

        Args:
            activation_id: ID активации

        Returns:
            True если успешно
        """
        try:
            response = self.session.get(
                f"{self.base_url}/cancel",
                params={
                    "apikey": self.api_key,
                    "id": activation_id
                },
                timeout=10
            )

            return response.status_code == 200

        except Exception:
            return False

    def finish_activation(self, activation_id: str) -> bool:
        """
        Завершить активацию

        Args:
            activation_id: ID активации

        Returns:
            True если успешно
        """
        try:
            response = self.session.get(
                f"{self.base_url}/finish",
                params={
                    "apikey": self.api_key,
                    "id": activation_id
                },
                timeout=10
            )

            return response.status_code == 200

        except Exception:
            return False

    def get_balance(self) -> Optional[float]:
        """
        Получить баланс на аккаунте

        Returns:
            Баланс в рублях или None
        """
        try:
            response = self.session.get(
                f"{self.base_url}/balance",
                params={"apikey": self.api_key},
                timeout=10
            )

            if response.status_code == 200:
                balance_str = response.text
                try:
                    return float(balance_str)
                except ValueError:
                    return None

        except Exception:
            return None

    def get_activation_cost(self, service: str = "ozончик") -> Optional[float]:
        """
        Получить стоимость активации

        Args:
            service: Сервис

        Returns:
            Стоимость или None
        """
        try:
            response = self.session.get(
                f"{self.base_url}/prices",
                params={
                    "apikey": self.api_key,
                    "service": service
                },
                timeout=10
            )

            if response.status_code == 200:
                # API возвращает: услуга:стоимость
                parts = response.text.split(":")
                if len(parts) >= 2:
                    try:
                        return float(parts[1])
                    except ValueError:
                        return None

        except Exception:
            return None


if __name__ == "__main__":
    # Пример использования
    api_key = "lpkfsipROdyEIHPv"
    sms_service = MegaSMSService(api_key)

    print("Проверка баланса...")
    balance = sms_service.get_balance()
    if balance is not None:
        print(f"✓ Баланс: {balance} руб")
    else:
        print("✗ Не удалось получить баланс")

    print("\nПолучение номера телефона...")
    phone_data = sms_service.get_phone_number("ozончик")
    if phone_data:
        print(f"✓ Получен номер: {phone_data['phone']}")
        print(f"  ID активации: {phone_data['activation_id']}")

        print("\nОжидание SMS кода...")
        sms_code = sms_service.wait_for_sms(phone_data['activation_id'])
        if sms_code:
            print(f"✓ SMS код получен: {sms_code}")
        else:
            print("✗ SMS код не получен в отведенное время")
    else:
        print("✗ Не удалось получить номер телефона")
