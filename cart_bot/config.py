"""Настройки скорости и путей приложения."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from .markets import DEFAULT_MARKET, Market, get_market

APP_DIR = Path(os.environ.get("CART_BOT_HOME", Path.home() / ".cart_bot"))
PROFILES_DIR = APP_DIR / "profiles"

# Ресурсы, которые не нужны для клика «В корзину», — режем на уровне CDP.
BLOCKED_URL_PATTERNS = (
    "*.jpg",
    "*.jpeg",
    "*.png",
    "*.gif",
    "*.webp",
    "*.svg",
    "*.avif",
    "*.mp4",
    "*.webm",
    "*.woff",
    "*.woff2",
    "*.ttf",
    "*googletagmanager*",
    "*google-analytics*",
    "*mc.yandex.ru*",
    "*criteo*",
    "*doubleclick*",
)


@dataclass
class Settings:
    """Параметры запуска. Значения по умолчанию подобраны под скорость."""

    market_key: str = DEFAULT_MARKET

    headless: bool = True
    block_images: bool = True
    block_analytics: bool = True

    # Таймауты, сек. Больше 5 не ставим — быстрее сдаться и уйти в ретрай.
    page_load_timeout: float = 5.0
    element_timeout: float = 5.0

    # Единственная критическая пауза: даём фронту дорисовать состояние
    # кнопки после клика, прежде чем уходить на следующий товар.
    micro_pause: float = 0.35

    retries: int = 1
    max_workers: int = 4

    # После сборки жать «Поделиться корзиной» и забирать выданную ссылку.
    fetch_share_link: bool = True

    # Профили Chrome: по одному на поток и на маркетплейс. Каждый профиль —
    # отдельная сессия, то есть отдельная корзина, которая переживает
    # закрытие браузера.
    profiles_dir: Path = field(default=PROFILES_DIR)

    @property
    def market(self) -> Market:
        return get_market(self.market_key)

    def profile_for(self, thread_id: int) -> Path:
        """Профиль потока. Разведён по маркетплейсам, чтобы корзины Ozon и
        Wildberries не делили одну сессию Chrome."""
        return self.profiles_dir / self.market_key / f"thread-{thread_id}"


def ensure_app_dir() -> Path:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    return APP_DIR
