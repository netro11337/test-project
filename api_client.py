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
    # Пока это заготовка — раскомментируйте после указания реальных URL.
    logger.info("Клиенты готовы: %s, %s", first_api.base_url, second_api.base_url)


if __name__ == "__main__":
    main()
