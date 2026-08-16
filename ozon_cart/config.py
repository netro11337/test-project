"""Настройки скорости и путей приложения."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

BASE_URL = "https://www.ozon.ru"
PRODUCT_URL = BASE_URL + "/product/{sku}/"
CART_URL = BASE_URL + "/cart"

APP_DIR = Path(os.environ.get("OZON_CART_HOME", Path.home() / ".ozon_cart"))
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

    headless: bool = True
    block_images: bool = True
    block_analytics: bool = True

    # Таймауты, сек. Больше 5 не ставим — быстрее сдаться и уйти в ретрай.
    page_load_timeout: float = 5.0
    element_timeout: float = 5.0

    # Единственная критическая пауза: даём фронту Ozon дорисовать состояние
    # кнопки после клика, прежде чем уходить на следующий товар.
    micro_pause: float = 0.35

    retries: int = 1
    max_workers: int = 4

    # Профили Chrome: по одному на поток. Каждый профиль — отдельная сессия,
    # то есть отдельная корзина Ozon, которая переживает закрытие браузера.
    profiles_dir: Path = field(default=PROFILES_DIR)
    keep_profiles: bool = True

    def profile_for(self, thread_id: int) -> Path:
        return self.profiles_dir / f"thread-{thread_id}"

    def worker_timeout(self, sku_count: int) -> float:
        """Грубая верхняя граница на батч, чтобы поток не висел вечно."""
        per_sku = self.page_load_timeout + self.element_timeout + self.micro_pause
        return max(60.0, per_sku * (self.retries + 1) * sku_count + 30.0)


def ensure_app_dir() -> Path:
    APP_DIR.mkdir(parents=True, exist_ok=True)
    PROFILES_DIR.mkdir(parents=True, exist_ok=True)
    return APP_DIR
