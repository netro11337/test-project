"""Параллельный запуск потоков: один поток — один браузер — одна корзина."""

from __future__ import annotations

import logging
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional, Sequence

from selenium.common.exceptions import WebDriverException

from .cart import (
    ShareResult,
    clear_cart,
    count_items,
    open_cart,
    read_cart_summary,
)
from .config import Settings, ensure_app_dir
from .driver import (
    DRIVER_CACHE_HINT,
    apply_resource_blocking,
    driver_ready,
    launch_user_browsers,
    probe_debug_ports,
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
    cleared: bool = False
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

        if driver_ready() is None:
            self.emit(
                Event(
                    EventKind.LOG,
                    message=(
                        "Готовый chromedriver не найден — понадеюсь на "
                        "встроенный механизм Selenium. Если браузеры не "
                        "запустятся: " + DRIVER_CACHE_HINT
                    ),
                )
            )

        if self.cfg.attach_to_chrome:
            return self._run_attached(active)

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

    def _run_attached(self, active) -> List[CartResult]:
        """Распределяет вкладки по запущенным браузерам пользователя.

        Браузеров может быть несколько (каждый на своём порту и профиле) —
        тогда они работают параллельно. Вкладки сверх их числа достаются тем же
        браузерам вторым кругом: два браузера на пять вкладок лучше, чем отказ.
        """
        def note(message: str) -> None:
            self.emit(Event(EventKind.LOG, message=message))

        if self.cfg.auto_launch_browsers:
            addresses = launch_user_browsers(self.cfg, len(active), note)
        else:
            addresses = probe_debug_ports(self.cfg, len(active))

        if not addresses:
            self.emit(
                Event(
                    EventKind.THREAD_FAILED,
                    message=(
                        "Не удалось открыть ни одного браузера. Проверьте, что "
                        "установлен Google Chrome; как запасной путь — "
                        "запустите «Chrome с отладкой.bat» вручную."
                    ),
                )
            )
            self.emit(Event(EventKind.ALL_DONE, message="Сборка не начата"))
            return []

        groups: List[List] = [[] for _ in addresses]
        for index, item in enumerate(active):
            groups[index % len(addresses)].append(item)

        self.emit(
            Event(
                EventKind.LOG,
                message=(
                    f"Нашёл браузеров: {len(addresses)}, вкладок: {len(active)}. "
                    + (
                        "Каждой вкладке свой браузер."
                        if len(addresses) >= len(active)
                        else "Лишние вкладки пойдут вторым кругом."
                    )
                ),
            )
        )

        if len(active) > len(addresses) and not self.cfg.clear_cart_after:
            self.emit(
                Event(
                    EventKind.LOG,
                    message=(
                        "ВНИМАНИЕ: кругов будет несколько, а очистка корзины "
                        "выключена — каждая следующая ссылка будет включать "
                        "товары предыдущих кругов."
                    ),
                )
            )

        carts: List[CartResult] = []
        with ThreadPoolExecutor(max_workers=len(addresses)) as pool:
            futures = [
                pool.submit(self._run_rounds, address, group)
                for address, group in zip(addresses, groups)
                if group
            ]
            for future in futures:
                try:
                    carts.extend(future.result())
                except Exception as exc:  # noqa: BLE001
                    log.exception("Браузер упал")
                    self.emit(Event(EventKind.THREAD_FAILED, message=str(exc)))

        carts.sort(key=lambda cart: cart.thread_id)
        self.emit(Event(EventKind.ALL_DONE, message="Сборка завершена"))
        return carts

    def _run_rounds(self, address: str, active) -> List[CartResult]:
        """Прогоняет доставшиеся браузеру вкладки по очереди.

        В одном браузере корзина одна, поэтому вкладки идут кругами, и между
        кругами корзина очищается — иначе товары предыдущего круга попадут в
        следующую ссылку.
        """
        rounds = len(active)
        tabs = ", ".join(str(thread_id) for thread_id, _ in active)
        self.emit(
            Event(
                EventKind.LOG,
                message=f"Браузер {address}: вкладки {tabs}",
            )
        )

        carts: List[CartResult] = []
        driver = None
        try:
            driver = create_driver(
                self.cfg, self.cfg.profile_for(1), debug_address=address
            )

            # Разогрев нужен один раз на браузер, а не на каждый круг.
            if self.cfg.warm_up and not warm_up(driver, self.cfg):
                self._survive_block(driver, active[0][0])

            for number, (thread_id, skus) in enumerate(active, start=1):
                if self._cancel.is_set():
                    break
                if rounds > 1:
                    self.emit(
                        Event(
                            EventKind.LOG,
                            message=(
                                f"— Браузер {address}: круг {number} из {rounds} —"
                            ),
                        )
                    )
                carts.append(self._collect(driver, thread_id, skus))
        except Exception as exc:  # noqa: BLE001
            log.exception("Сборка в браузере %s упала", address)
            self.emit(Event(EventKind.THREAD_FAILED, message=f"{address}: {exc}"))
        finally:
            quit_driver(driver, owned=False)

        return carts

    def _ensure_clean_start(self, driver, thread_id: int, cart) -> None:
        """Убеждается, что круг начинается с пустой корзины.

        Очистка после круга может не сработать, а профиль переживает и
        перезапуск программы. Тогда товары прошлого круга останутся и попадут
        в ссылку следующего — со стороны это выглядит так, будто поток набрал
        чужие SKU. Поэтому чистим ещё и на входе.
        """
        if not self.cfg.clear_cart_after:
            return

        if not open_cart(driver, self.cfg, self.cfg.market):
            return
        left = count_items(driver, self.cfg.market)
        if left <= 0:
            return

        self.emit(
            Event(
                EventKind.LOG,
                thread_id=thread_id,
                message=(
                    f"Поток {thread_id}: перед началом в корзине {left} чужих "
                    "позиц(ий) от прошлого круга — убираю"
                ),
            )
        )
        ok, why = clear_cart(driver, self.cfg)
        if ok:
            return

        cart.error = f"корзина не была пуста в начале ({why})"
        self.emit(
            Event(
                EventKind.LOG,
                thread_id=thread_id,
                message=(
                    f"Поток {thread_id}: ВНИМАНИЕ, очистить корзину перед "
                    f"началом не удалось ({why}). В ссылку попадут лишние "
                    "товары — доверять ей нельзя."
                ),
            )
        )

    def _verify(self, driver, thread_id: int, skus: List[str], cart) -> None:
        """Перепроверяет каждый товар и дожимает не попавшие в корзину.

        Товар иногда не добавляется, хотя клик прошёл. Заново открытая карточка
        сама показывает, лежит он в корзине или нет: если нет — жмём ещё раз.
        Итоговый счёт берём отсюда, он ближе к правде, чем отчёт по кликам.
        """
        if not self.cfg.verify_cart or not skus:
            return

        if not open_cart(driver, self.cfg, self.cfg.market):
            return

        before = count_items(driver, self.cfg.market)
        if before < 0:
            # Посчитать не вышло. Незнание — не повод гонять второй круг:
            # раньше -1 сравнивалось с числом SKU и проверка шла всегда.
            self.emit(
                Event(
                    EventKind.LOG,
                    thread_id=thread_id,
                    message=(
                        f"Поток {thread_id}: не смог пересчитать корзину, "
                        "проверочный круг пропускаю"
                    ),
                )
            )
            return
        if before >= len(skus):
            # Всё на месте — гонять по карточкам второй раз незачем.
            return

        self.emit(
            Event(
                EventKind.LOG,
                thread_id=thread_id,
                message=(
                    f"Поток {thread_id}: в корзине {before} из {len(skus)}, "
                    "перепроверяю товары"
                ),
            )
        )

        present = 0
        fixed = 0
        for sku in skus:
            if self._cancel.is_set():
                return
            result = add_sku_with_retry(driver, sku, self.cfg)
            if result.outcome is Outcome.ADDED:
                fixed += 1
                present += 1
                self.emit(
                    Event(EventKind.SKU_DONE, thread_id=thread_id, result=result)
                )
            elif result.ok:
                present += 1
            self._pace()

        cart.added = present
        cart.failed = len(skus) - present
        self.emit(
            Event(
                EventKind.LOG,
                thread_id=thread_id,
                message=(
                    f"Поток {thread_id}: проверка закончена, дожал {fixed}, "
                    f"итого в корзине {present} из {len(skus)}"
                ),
            )
        )

    def _pace(self) -> None:
        """Пауза вразнобой между товарами в человеческом темпе.

        Ровный интервал сам по себе выглядит машинно, поэтому берём случайную
        длительность из диапазона. Отмену не блокируем: спим короткими шагами.
        """
        if not self.cfg.human_pace:
            return
        delay = random.uniform(self.cfg.pace_min, self.cfg.pace_max)
        deadline = time.monotonic() + delay
        while time.monotonic() < deadline and not self._cancel.is_set():
            time.sleep(min(0.2, deadline - time.monotonic()))

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
        unblocked = clear_resource_blocking(driver)
        try:
            driver.refresh()
        except WebDriverException as exc:
            log.debug("Не перезагрузил страницу проверки: %s", exc)
        self.emit(
            Event(
                EventKind.LOG,
                thread_id=thread_id,
                message=(
                    f"Поток {thread_id}: снял экономию трафика и перезагрузил "
                    "страницу, чтобы картинка пазла загрузилась"
                    if unblocked
                    else f"Поток {thread_id}: не удалось снять экономию трафика"
                ),
            )
        )

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
        """Отдельный браузер под один список SKU."""
        driver = None
        try:
            driver = create_driver(
                self.cfg, self.cfg.profile_for(thread_id), thread_id=thread_id
            )
            if self.cfg.warm_up and not warm_up(driver, self.cfg):
                self._survive_block(driver, thread_id)
            return self._collect(driver, thread_id, skus)
        finally:
            # Чужой браузер не закрываем — у пользователя схлопнутся вкладки.
            quit_driver(driver, owned=not self.cfg.attach_to_chrome)

    def _collect(self, driver, thread_id: int, skus: List[str]) -> CartResult:
        """Собирает одну корзину в уже открытом браузере и берёт ссылку.

        Отделено от создания браузера: в режиме «мой Chrome» один и тот же
        браузер отрабатывает несколько кругов подряд, очищая корзину между
        ними.
        """
        started = time.monotonic()
        cart = CartResult(
            thread_id=thread_id,
            total=len(skus),
            profile=str(self.cfg.profile_for(thread_id)),
            url=self.cfg.market.cart_url,
        )

        # Список печатаем целиком: когда в корзине окажется чужой товар, по
        # логу сразу видно, был он выдан этому потоку или приехал из соседнего.
        self.emit(
            Event(
                EventKind.THREAD_STARTED,
                thread_id=thread_id,
                message=f"Поток {thread_id}: {len(skus)} SKU — {', '.join(skus)}",
            )
        )

        try:
            self._ensure_clean_start(driver, thread_id, cart)

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

                self._pace()

            if not self._cancel.is_set():
                self._verify(driver, thread_id, skus, cart)

                share, cart.items_in_cart = read_cart_summary(driver, self.cfg)
                cart.apply_share(share)

                if cart.items_in_cart > len(skus):
                    # Товаров больше, чем выдано потоку. Чаще всего это значит,
                    # что браузеры вошли в один аккаунт: корзина магазина
                    # привязана к аккаунту, а не к профилю браузера, и потоки
                    # складывают всё в одну общую.
                    extra = cart.items_in_cart - len(skus)
                    cart.error = (
                        f"в корзине {cart.items_in_cart} позиций против "
                        f"{len(skus)} выданных (+{extra} чужих)"
                    )
                    self.emit(
                        Event(
                            EventKind.LOG,
                            thread_id=thread_id,
                            message=(
                                f"Поток {thread_id}: ВНИМАНИЕ, {cart.error}. "
                                "Вероятная причина: браузеры вошли в один "
                                "аккаунт, а корзина привязана к аккаунту, "
                                "а не к браузеру — тогда она у всех общая. "
                                "Либо разные аккаунты в разных браузерах, "
                                "либо один поток за раз."
                            ),
                        )
                    )
                elif cart.added > 0 and cart.items_in_cart == 0:
                    # Отчитались об успехе, а корзина пуста: значит клики не
                    # дошли. Молчать об этом нельзя — человек будет уверен,
                    # что корзина собрана.
                    cart.error = (
                        f"добавлено по отчёту {cart.added}, но корзина пуста — "
                        "клики не сработали"
                    )
                    self.emit(
                        Event(
                            EventKind.LOG,
                            thread_id=thread_id,
                            message=f"Поток {thread_id}: ВНИМАНИЕ, {cart.error}",
                        )
                    )
                elif cart.items_in_cart > 0:
                    self.emit(
                        Event(
                            EventKind.LOG,
                            thread_id=thread_id,
                            message=(
                                f"Поток {thread_id}: в корзине "
                                f"{cart.items_in_cart} позиц(ий) — проверено"
                            ),
                        )
                    )

                # Чистим только после того, как ссылка получена: иначе делиться
                # будет уже нечем.
                if self.cfg.clear_cart_after and cart.items_in_cart != 0:
                    ok, why = clear_cart(driver, self.cfg)
                    cart.cleared = ok
                    self.emit(
                        Event(
                            EventKind.LOG,
                            thread_id=thread_id,
                            message=(
                                f"Поток {thread_id}: очистка корзины — {why}"
                                if ok
                                else f"Поток {thread_id}: очистить корзину не "
                                f"удалось ({why}), следующий круг начнётся не с пустой"
                            ),
                        )
                    )
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
