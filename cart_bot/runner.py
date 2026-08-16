"""Параллельный запуск потоков: один поток — один браузер — одна корзина."""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional, Sequence

from selenium.common.exceptions import WebDriverException

from .cart import ShareResult, read_cart_summary
from .config import Settings, ensure_app_dir
from .driver import (
    apply_resource_blocking,
    clear_resource_blocking,
    create_driver,
    quit_driver,
)
from .worker import (
    Outcome,
    SkuResult,
    add_sku_with_retry,
    warm_up,
    wait_until_unblocked,
)

log = logging.getLogger(__name__)


class EventKind(str, Enum):
    THREAD_STARTED = "thread_started"
    SKU_DONE = "sku_done"
    THREAD_DONE = "thread_done"
    THREAD_FAILED = "thread_failed"
    ALL_DONE = "all_done"
    LOG = "log"


@dataclass
class Event:
    kind: EventKind
    thread_id: int = -1
    message: str = ""
    result: Optional[SkuResult] = None
    cart: Optional["CartResult"] = None


@dataclass
class CartResult:
    """Итог одного потока — его собственная корзина."""

    thread_id: int
    url: str = ""
    share_method: str = "fallback"
    share_note: str = ""
    profile: str = ""
    total: int = 0
    added: int = 0
    failed: int = 0
    items_in_cart: int = -1
    elapsed: float = 0.0
    error: str = ""
    results: List[SkuResult] = field(default_factory=list)

    @property
    def done(self) -> int:
        return self.added + self.failed

    @property
    def has_share_link(self) -> bool:
        """Ссылка получена кнопкой «Поделиться», а не подставлена как /cart."""
        return self.share_method != "fallback"

    def apply_share(self, share: ShareResult) -> None:
        self.url = share.url
        self.share_method = share.method
        self.share_note = share.message


Emit = Callable[[Event], None]


class CartRunner:
    """Собирает N независимых корзин параллельно.

    Потоки ничего не делят между собой: у каждого свой профиль Chrome, своя
    сессия Ozon и своя корзина. Это же и даёт изоляцию при падении — упавший
    поток не портит корзины остальных.
    """

    def __init__(self, cfg: Settings, batches: Sequence[Sequence[str]], emit: Emit):
        self.cfg = cfg
        self.batches = [list(batch) for batch in batches]
        self.emit = emit
        self._cancel = threading.Event()

    def cancel(self) -> None:
        self._cancel.set()

    @property
    def cancelled(self) -> bool:
        return self._cancel.is_set()

    def run(self) -> List[CartResult]:
        ensure_app_dir()
        active = [(i, skus) for i, skus in enumerate(self.batches, start=1) if skus]
        if not active:
            self.emit(Event(EventKind.ALL_DONE, message="Нет SKU для сборки"))
            return []

        # Больше воркеров, чем непустых потоков, поднимать незачем.
        workers = min(self.cfg.max_workers, len(active))
        self.emit(
            Event(
                EventKind.LOG,
                message=f"Запускаю {len(active)} поток(ов), одновременно — {workers}",
            )
        )

        carts: List[CartResult] = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [
                pool.submit(self._run_thread, thread_id, skus)
                for thread_id, skus in active
            ]
            for future in futures:
                try:
                    carts.append(future.result())
                except Exception as exc:  # noqa: BLE001 - поток не роняет запуск
                    log.exception("Поток упал")
                    self.emit(Event(EventKind.THREAD_FAILED, message=str(exc)))

        carts.sort(key=lambda c: c.thread_id)
        self.emit(Event(EventKind.ALL_DONE, message="Сборка завершена"))
        return carts

    def _survive_block(self, driver, thread_id: int) -> bool:
        """Даёт человеку пройти капчу в окне потока. True — проверка снята.

        В headless ждать бессмысленно: окна нет, решать капчу некому, — сразу
        отвечаем «не прошли», чтобы поток не висел зря.
        """
        market = self.cfg.market
        if self.cfg.headless or self.cfg.captcha_wait <= 0:
            return False

        # Пазл в капче — картинка. С включённой экономией трафика она не
        # загрузится, и проверка будет вечно крутить спиннер. Снимаем
        # блокировку и перезагружаем страницу, иначе картинку уже не подтянуть.
        clear_resource_blocking(driver)
        try:
            driver.refresh()
        except WebDriverException as exc:
            log.debug("Не перезагрузил страницу проверки: %s", exc)

        self.emit(
            Event(
                EventKind.LOG,
                thread_id=thread_id,
                message=(
                    f"Поток {thread_id}: {market.title} показал проверку. "
                    f"Пройдите её в окне этого потока — жду "
                    f"{int(self.cfg.captcha_wait)} с."
                ),
            )
        )
        try:
            passed = wait_until_unblocked(
                driver, market, self.cfg.captcha_wait, self._cancel.is_set
            )
        finally:
            apply_resource_blocking(driver, self.cfg)
        self.emit(
            Event(
                EventKind.LOG,
                thread_id=thread_id,
                message=(
                    f"Поток {thread_id}: "
                    + ("проверка пройдена, продолжаю" if passed else "проверка не снята")
                ),
            )
        )
        return passed

    def _run_thread(self, thread_id: int, skus: List[str]) -> CartResult:
        import time

        started = time.monotonic()
        profile = self.cfg.profile_for(thread_id)
        cart = CartResult(
            thread_id=thread_id,
            total=len(skus),
            profile=str(profile),
            url=self.cfg.market.cart_url,
        )

        self.emit(
            Event(
                EventKind.THREAD_STARTED,
                thread_id=thread_id,
                message=f"Поток {thread_id}: {len(skus)} SKU",
            )
        )

        driver = None
        try:
            driver = create_driver(self.cfg, profile)

            if self.cfg.warm_up and not warm_up(driver, self.cfg):
                self._survive_block(driver, thread_id)

            for sku in skus:
                if self._cancel.is_set():
                    cart.error = "Отменено пользователем"
                    break

                result = add_sku_with_retry(driver, sku, self.cfg)
                if result.outcome is Outcome.BLOCKED and self._survive_block(
                    driver, thread_id
                ):
                    # Проверку прошли — товар, на котором споткнулись, ещё не
                    # добавлен, поэтому повторяем именно его.
                    result = add_sku_with_retry(driver, sku, self.cfg)
                cart.results.append(result)
                if result.ok:
                    cart.added += 1
                else:
                    cart.failed += 1
                self.emit(
                    Event(EventKind.SKU_DONE, thread_id=thread_id, result=result)
                )

                if result.outcome is Outcome.BLOCKED:
                    # Антибот бьёт по всей сессии: дальше в этом потоке
                    # добавлять бессмысленно, только копить ошибки.
                    cart.error = f"{self.cfg.market.title} заблокировал сессию потока"
                    break

            if not self._cancel.is_set():
                share, cart.items_in_cart = read_cart_summary(driver, self.cfg)
                cart.apply_share(share)
                if share.message:
                    # На успехе здесь лежит сработавший селектор кнопки — он
                    # нужен, когда вёрстка магазина поедет и надо будет понять,
                    # какой из вариантов ещё живой.
                    prefix = (
                        "ссылка получена"
                        if share.is_shared
                        else "ссылку «Поделиться» получить не удалось"
                    )
                    self.emit(
                        Event(
                            EventKind.LOG,
                            thread_id=thread_id,
                            message=f"Поток {thread_id}: {prefix} ({share.message})",
                        )
                    )
        except Exception as exc:  # noqa: BLE001
            cart.error = str(exc).splitlines()[0]
            log.exception("Поток %s: ошибка", thread_id)
        finally:
            quit_driver(driver)

        cart.elapsed = round(time.monotonic() - started, 2)
        self.emit(Event(EventKind.THREAD_DONE, thread_id=thread_id, cart=cart))
        return cart


def open_cart_in_browser(cfg: Settings, thread_id: int):
    """Открывает корзину потока в видимом браузере на том же профиле.

    Драйвер возвращается наружу и намеренно не закрывается: окно должно
    остаться у пользователя. Вызывать только после остановки сборки —
    Chrome не даёт двум процессам держать один user-data-dir.
    """
    driver = create_driver(cfg, cfg.profile_for(thread_id), headless=False)
    driver.get(cfg.market.cart_url)
    return driver
