"""
Скрипт для диагностики MegaSMS API
"""

from megasms_service import MegaSMSService
import json

token = "lpkfsipROdyEIHPv"
sms_service = MegaSMSService(token)

print("=" * 60)
print("1. Проверка баланса")
print("=" * 60)
balance = sms_service.get_balance()
print(f"Баланс: {balance}\n")

print("=" * 60)
print("2. Получение списка доступных сервисов")
print("=" * 60)
services = sms_service.get_services()
if services:
    print(json.dumps(services, indent=2, ensure_ascii=False))
else:
    print("Сервисы не получены\n")

print("=" * 60)
print("3. Попытка получить номер с сервисом 'ozончик'")
print("=" * 60)
phone_data = sms_service.get_phone_number("ozончик")
print(f"Результат: {phone_data}\n")

print("=" * 60)
print("4. Попытка получить номер с сервисом 'ozon' (альтернатива)")
print("=" * 60)
phone_data = sms_service.get_phone_number("ozon")
print(f"Результат: {phone_data}\n")

print("=" * 60)
print("5. Прямой запрос к API через requests")
print("=" * 60)
import requests
response = requests.post(
    "https://megasms.lol/api/get_number",
    json={"service_id": "ozончик", "token": token},
    headers={"Content-Type": "application/json"},
    timeout=10
)
print(f"Статус: {response.status_code}")
print(f"Ответ: {response.text}")
