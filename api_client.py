"""Основа для работы с двумя внешними API.

Скрипт создаёт единую requests.Session() с сохранением куки и заголовков
между запросами. User-Agent выбирается случайно через fake_useragent.

Зависимости:
    pip install requests fake_useragent
"""

from __future__ import annotations

import logging
from typing import Any, Optional

import requests
from fake_useragent import UserAgent

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def build_session() -> requests.Session:
    """Создаёт requests.Session() со случайным User-Agent.

    Сессия хранит куки и заголовки между запросами, поэтому заголовки
    задаются один раз и переиспользуются всеми клиентами.
    """
    session = requests.Session()

    try:
        user_agent = UserAgent().random
    except Exception:  # noqa: BLE001 — fake_useragent может не достучаться до своих данных
        # Фолбэк на случай проблем с сетью/кэшем fake_useragent.
        user_agent = (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
        logger.warning("fake_useragent недоступен, использую запасной User-Agent")

    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    logger.info("Создана сессия с User-Agent: %s", user_agent)
    return session


class BaseAPIClient:
    """Базовый клиент API, работающий поверх общей сессии."""

    base_url: str = ""

    def __init__(self, session: requests.Session, timeout: float = 15.0) -> None:
        self.session = session
        self.timeout = timeout

    def _request(
        self,
        method: str,
        endpoint: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Выполняет запрос и возвращает Response, поднимая исключение на ошибках."""
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        logger.info("%s %s", method.upper(), url)
        response = self.session.request(
            method,
            url,
            params=params,
            json=json,
            timeout=self.timeout,
            **kwargs,
        )
        response.raise_for_status()
        return response

    def get(self, endpoint: str, **kwargs: Any) -> requests.Response:
        return self._request("GET", endpoint, **kwargs)

    def post(self, endpoint: str, **kwargs: Any) -> requests.Response:
        return self._request("POST", endpoint, **kwargs)


class FirstAPIClient(BaseAPIClient):
    """Клиент для первого внешнего API. Замените base_url и методы на свои."""

    base_url = "https://api.example-one.com"

    def fetch_items(self, **params: Any) -> Any:
        """Пример GET-запроса к первому API."""
        return self.get("/v1/items", params=params).json()


class SecondAPIClient(BaseAPIClient):
    """Клиент для второго внешнего API. Замените base_url и методы на свои."""

    base_url = "https://api.example-two.com"

    def create_record(self, payload: dict[str, Any]) -> Any:
        """Пример POST-запроса ко второму API."""
        return self.post("/v2/records", json=payload).json()


# --- SMS-приёмник (например, sms-activate.org) -----------------------------

SMS_ACTIVATE_URL = "https://api.sms-activate.org/stubs/handler_api.php"


class SMSActivateError(RuntimeError):
    """Ошибка, возвращённая API сервиса приёма SMS (например, BAD_KEY)."""


def get_phone_number(
    api_key: str,
    service_code: str,
    *,
    session: Optional[requests.Session] = None,
    timeout: float = 15.0,
) -> tuple[str, str]:
    """Запрашивает номер телефона у сервиса приёма SMS.

    Отправляет GET-запрос вида
        ?api_key=...&action=getNumber&service=<service_code>
    и парсит успешный ответ формата ``ACCESS_NUMBER:ID:NUMBER``.

    Args:
        api_key: Ключ доступа к API сервиса.
        service_code: Код сервиса, для которого нужен номер (например, "vk", "tg").
        session: Необязательная requests.Session; если не передана — создаётся
            новая со случайным User-Agent.
        timeout: Таймаут запроса в секундах.

    Returns:
        Кортеж ``(activation_id, phone_number)``.

    Raises:
        SMSActivateError: Если сервис вернул ошибку (например, NO_NUMBERS,
            BAD_KEY, BAD_SERVICE) или ответ не распознан.
    """
    if session is None:
        session = build_session()

    params = {
        "api_key": api_key,
        "action": "getNumber",
        "service": service_code,
    }

    logger.info("Запрос номера для сервиса '%s'", service_code)
    response = session.get(SMS_ACTIVATE_URL, params=params, timeout=timeout)
    response.raise_for_status()

    body = response.text.strip()

    # Успех: ACCESS_NUMBER:ID:NUMBER
    if body.startswith("ACCESS_NUMBER:"):
        parts = body.split(":")
        if len(parts) >= 3:
            activation_id, phone_number = parts[1], parts[2]
            logger.info("Получен номер %s (ID активации %s)", phone_number, activation_id)
            return activation_id, phone_number
        raise SMSActivateError(f"Не удалось разобрать ответ: {body!r}")

    # Любой другой ответ — это код ошибки сервиса (BAD_KEY, NO_NUMBERS и т.п.).
    raise SMSActivateError(f"API вернул ошибку: {body!r}")


def main() -> None:
    # Одна сессия — общие куки и заголовки для обоих API.
    session = build_session()

    first_api = FirstAPIClient(session)
    second_api = SecondAPIClient(session)

    # Здесь размещается основная логика работы с двумя API, например:
    #
    #     items = first_api.fetch_items(limit=10)
    #     result = second_api.create_record({"source": items})
    #     logger.info("Готово: %s", result)
    #
    # Пример работы с сервисом приёма SMS (та же сессия — общий User-Agent):
    #
    #     activation_id, phone = get_phone_number("YOUR_API_KEY", "vk", session=session)
    #     logger.info("ID активации %s, номер %s", activation_id, phone)
    #
    # Пока это заготовка — раскомментируйте после указания реальных ключей/URL.
    logger.info("Клиенты готовы: %s, %s", first_api.base_url, second_api.base_url)


if __name__ == "__main__":
    main()
