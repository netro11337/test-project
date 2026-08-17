"""
MegaSMS Service Integration
Получение номеров телефонов и SMS кодов с сервиса MegaSMS
"""

import requests
import time
from typing import Optional, Tuple, List, Dict
from dataclasses import dataclass


@dataclass
class SMSMessage:
    """SMS сообщение"""
    phone: str
    code: str
    timestamp: str


class MegaSMSService:
    """Работа с MegaSMS API"""

    def __init__(self, token: str):
        """
        Инициализация MegaSMS сервиса

        Args:
            token: API токен (ключ) MegaSMS
        """
        self.token = token
        self.base_url = "https://megasms.lol"
        self.session = requests.Session()
        self.headers = {
            "Content-Type": "application/json"
        }
        self.last_request_time = 0
        self.min_delay = 0.5

    def _wait_for_rate_limit(self):
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_delay:
            time.sleep(self.min_delay - elapsed)
        self.last_request_time = time.time()

    def get_phone_number(self, service_id: str = "ozon") -> Optional[Dict]:
        """
        Получить номер телефона для регистрации

        Args:
            service_id: ID сервиса (по умолчанию 'ozon')

        Returns:
            Словарь с номером и ID активации или None при ошибке
        """
        try:
            self._wait_for_rate_limit()

            payload = {
                "service_id": service_id,
                "token": self.token
            }

            response = self.session.post(
                f"{self.base_url}/api/get_number",
                json=payload,
                headers=self.headers,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()

                # Проверяем различные форматы ответа
                if isinstance(data, dict):
                    # Ищем номер в ответе
                    phone = data.get("phone") or data.get("number")
                    order_id = data.get("order_id") or data.get("id")

                    if phone and order_id:
                        return {
                            "phone": phone,
                            "order_id": order_id,
                            "activation_id": order_id,
                            "raw": data
                        }

                print(f"Ошибка в формате ответа: {data}")
                return None
            else:
                print(f"Ошибка при получении номера: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            print(f"Ошибка подключения к MegaSMS: {str(e)}")
            return None

    def get_sms_code(self, order_id: str) -> Optional[str]:
        """
        Получить SMS код

        Args:
            order_id: ID заказа (активации)

        Returns:
            SMS код или None
        """
        try:
            self._wait_for_rate_limit()

            payload = {
                "order_id": order_id,
                "token": self.token
            }

            response = self.session.post(
                f"{self.base_url}/api/get_order",
                json=payload,
                headers=self.headers,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()

                # Ищем SMS код в ответе
                sms_code = data.get("sms") or data.get("code")

                if sms_code:
                    return sms_code

                # Если кода нет, значит SMS еще не пришла
                return None

        except Exception as e:
            print(f"Ошибка при получении SMS кода: {str(e)}")
            return None

    def wait_for_sms(self, order_id: str, max_wait: int = 120,
                     check_interval: int = 5) -> Optional[str]:
        """
        Ждать SMS код с таймаутом

        Args:
            order_id: ID заказа
            max_wait: Максимальное время ожидания (сек)
            check_interval: Интервал проверки (сек)

        Returns:
            SMS код или None если истекло время
        """
        elapsed = 0
        while elapsed < max_wait:
            sms_code = self.get_sms_code(order_id)
            if sms_code:
                return sms_code

            time.sleep(check_interval)
            elapsed += check_interval
            print(f"Ожидание SMS... ({elapsed}/{max_wait} сек)")

        return None

    def cancel_order(self, order_id: str) -> bool:
        """
        Отменить заказ

        Args:
            order_id: ID заказа

        Returns:
            True если успешно
        """
        try:
            payload = {
                "order_id": order_id,
                "token": self.token
            }

            response = self.session.post(
                f"{self.base_url}/api/cancel_order",
                json=payload,
                headers=self.headers,
                timeout=10
            )

            return response.status_code == 200

        except Exception:
            return False

    def finish_order(self, order_id: str) -> bool:
        """
        Завершить заказ

        Args:
            order_id: ID заказа

        Returns:
            True если успешно
        """
        try:
            payload = {
                "order_id": order_id,
                "token": self.token
            }

            response = self.session.post(
                f"{self.base_url}/api/finish_order",
                json=payload,
                headers=self.headers,
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
            self._wait_for_rate_limit()

            payload = {
                "token": self.token
            }

            response = self.session.post(
                f"{self.base_url}/api/get_balance",
                json=payload,
                headers=self.headers,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()

                # Ищем баланс в ответе
                balance = data.get("balance") or data.get("account_balance")

                if balance is not None:
                    try:
                        return float(balance)
                    except (ValueError, TypeError):
                        return None

        except Exception as e:
            print(f"Ошибка при получении баланса: {str(e)}")
            return None

    def get_services(self) -> Optional[List[Dict]]:
        """
        Получить список доступных сервисов

        Returns:
            Список сервисов или None
        """
        try:
            response = self.session.get(
                f"{self.base_url}/api/get_services",
                timeout=10
            )

            if response.status_code == 200:
                return response.json()

        except Exception as e:
            print(f"Ошибка при получении списка сервисов: {str(e)}")
            return None


if __name__ == "__main__":
    # Пример использования
    token = "lpkfsipROdyEIHPv"
    sms_service = MegaSMSService(token)

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
        print(f"  ID заказа: {phone_data['order_id']}")

        print("\nОжидание SMS кода...")
        sms_code = sms_service.wait_for_sms(phone_data['order_id'])
        if sms_code:
            print(f"✓ SMS код получен: {sms_code}")
        else:
            print("✗ SMS код не получен в отведенное время")
    else:
        print("✗ Не удалось получить номер телефона")
