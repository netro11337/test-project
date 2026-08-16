"""Добавление одного SKU в корзину внутри уже открытой сессии."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Tuple

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .config import Settings
from .markets import Market

log = logging.getLogger(__name__)


class Outcome(str, Enum):
    ADDED = "added"
    ALREADY = "already"
    OUT_OF_STOCK = "out_of_stock"
    NOT_FOUND = "not_found"
    BLOCKED = "blocked"
    ERROR = "error"


@dataclass
class SkuResult:
    sku: str
    outcome: Outcome
    message: str = ""
    elapsed: float = 0.0

    @property
    def ok(self) -> bool:
        return self.outcome in (Outcome.ADDED, Outcome.ALREADY)


def _find_first(driver: WebDriver, xpath: str) -> Optional[WebElement]:
    """Мгновенная проверка наличия элемента, без ожидания."""
    try:
        elements = driver.find_elements(By.XPATH, xpath)
        return elements[0] if elements else None
    except WebDriverException:
        return None


def is_blocked(driver: WebDriver, market: Market) -> bool:
    """Показывает ли магазин страницу антибота вместо запрошенной.

    Сначала смотрим заголовок вкладки: у служебной страницы Ozon он равен
    «Antibot Captcha» независимо от того, что написано в теле страницы. Текст
    магазин переписывает, заголовок — почти никогда.
    """
    try:
        title = (driver.title or "").lower()
    except WebDriverException:
        title = ""
    if any(marker in title for marker in market.antibot_titles):
        return True
    return _find_first(driver, market.antibot) is not None


def wait_until_unblocked(
    driver: WebDriver,
    market: Market,
    timeout: float,
    should_stop=None,
) -> bool:
    """Ждёт, пока человек не пройдёт проверку в окне браузера.

    Капчу решает пользователь: окно потока для этого открыто. Как только
    страница перестаёт быть страницей антибота, поток продолжает работу.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if should_stop is not None and should_stop():
            return False
        if not is_blocked(driver, market):
            return True
        time.sleep(1.0)
    return not is_blocked(driver, market)


def _click(driver: WebDriver, element: WebElement) -> None:
    """Обычный клик, при перехвате — через JS."""
    try:
        element.click()
    except (ElementClickInterceptedException, WebDriverException):
        driver.execute_script("arguments[0].click();", element)


def find_add_button(
    driver: WebDriver, cfg: Settings, market: Market
) -> Tuple[Optional[WebElement], str]:
    """Ищет кнопку «В корзину», перебирая кандидатов по порядку.

    Возвращает ещё и сработавший селектор: когда магазин перерисует вёрстку,
    по логу будет видно, какой вариант ещё живой.
    """
    deadline = time.monotonic() + cfg.element_timeout
    while True:
        for xpath in market.add_buttons:
            try:
                elements = driver.find_elements(By.XPATH, xpath)
            except WebDriverException:
                continue
            for element in elements:
                try:
                    if element.is_displayed() and element.is_enabled():
                        return element, xpath
                except WebDriverException:
                    continue
        if time.monotonic() >= deadline:
            return None, ""
        time.sleep(0.15)


def _confirm_added(
    driver: WebDriver,
    cfg: Settings,
    market: Market,
    button: WebElement,
    before: str,
) -> bool:
    """Ждёт подтверждения, что товар оказался в корзине.

    Считаем успехом любой из признаков: появился маркер «в корзине» либо сама
    кнопка изменилась — исчезла, отвалилась из DOM или сменила надпись.
    Опираться только на один текст рискованно: магазин их меняет, и тогда
    добавленный товар засчитывался бы как ошибка.
    """
    deadline = time.monotonic() + cfg.element_timeout
    while time.monotonic() < deadline:
        if _find_first(driver, market.in_cart_marker) is not None:
            return True
        try:
            if not button.is_displayed():
                return True
            if (button.text or "").strip() != before:
                return True
        except StaleElementReferenceException:
            return True
        except WebDriverException:
            return True
        time.sleep(0.1)
    return False


def add_sku(driver: WebDriver, sku: str, cfg: Settings) -> SkuResult:
    """Открывает карточку товара и жмёт «Добавить в корзину».

    На главную не возвращаемся: переходим сразу с карточки на карточку,
    сессия и корзина живут в драйвере.
    """
    started = time.monotonic()
    market = cfg.market
    url = market.product_url.format(sku=sku)

    try:
        driver.get(url)
    except TimeoutException:
        # page_load_strategy=eager + короткий таймаут: DOM часто уже пригоден,
        # поэтому не сдаёмся сразу, а пробуем работать с тем, что отрисовалось.
        log.debug("SKU %s: таймаут загрузки, продолжаю по готовому DOM", sku)
    except WebDriverException as exc:
        return SkuResult(sku, Outcome.ERROR, str(exc).splitlines()[0], _since(started))

    if is_blocked(driver, market):
        return SkuResult(
            sku,
            Outcome.BLOCKED,
            f"{market.title} показал антибот-проверку",
            _since(started),
        )
    if _find_first(driver, market.not_found) is not None:
        return SkuResult(sku, Outcome.NOT_FOUND, "Товар не найден", _since(started))

    # Ждём отрисовку страницы, но не считаем это провалом: контейнер магазин
    # переименовывает, а кнопка при этом на месте — ищем её в любом случае.
    try:
        WebDriverWait(driver, cfg.element_timeout / 2, poll_frequency=0.1).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, market.add_widget))
        )
    except TimeoutException:
        log.debug("SKU %s: контейнер карточки не найден, ищу кнопку по странице", sku)

    if _find_first(driver, market.in_cart_marker) is not None:
        return SkuResult(sku, Outcome.ALREADY, "Уже в корзине", _since(started))

    button, selector = find_add_button(driver, cfg, market)
    if button is None:
        if _find_first(driver, market.out_of_stock) is not None:
            return SkuResult(
                sku, Outcome.OUT_OF_STOCK, "Нет в наличии", _since(started)
            )
        return SkuResult(
            sku, Outcome.ERROR, "Кнопка «В корзину» не найдена", _since(started)
        )

    try:
        before = (button.text or "").strip()
    except WebDriverException:
        before = ""

    try:
        _click(driver, button)
    except (NoSuchElementException, WebDriverException) as exc:
        return SkuResult(sku, Outcome.ERROR, str(exc).splitlines()[0], _since(started))

    if _confirm_added(driver, cfg, market, button, before):
        time.sleep(cfg.micro_pause)
        return SkuResult(sku, Outcome.ADDED, f"Добавлен ({selector})", _since(started))

    if _find_first(driver, market.out_of_stock) is not None:
        return SkuResult(sku, Outcome.OUT_OF_STOCK, "Нет в наличии", _since(started))

    return SkuResult(
        sku, Outcome.ERROR, "Клик прошёл, но корзина не подтвердилась", _since(started)
    )


def warm_up(driver: WebDriver, cfg: Settings) -> bool:
    """Заходит на главную перед первым товаром.

    Живой человек попадает на карточку с главной или из поиска, а не начинает
    сессию с прямого захода на товар. Заход на главную даёт скриптам магазина
    отработать и завести сессию. True — блокировки нет.
    """
    market = cfg.market
    try:
        driver.get(market.base_url)
    except TimeoutException:
        pass
    except WebDriverException as exc:
        log.debug("Разогрев не удался: %s", exc)
        return False
    time.sleep(cfg.micro_pause)
    return not is_blocked(driver, market)


def add_sku_with_retry(driver: WebDriver, sku: str, cfg: Settings) -> SkuResult:
    """add_sku + ретраи. Повторяем только то, что реально может починиться."""
    attempt = 0
    result = add_sku(driver, sku, cfg)
    while (
        attempt < cfg.retries
        and result.outcome in (Outcome.ERROR, Outcome.BLOCKED)
    ):
        attempt += 1
        time.sleep(cfg.micro_pause)
        result = add_sku(driver, sku, cfg)
    return result


def _since(started: float) -> float:
    return round(time.monotonic() - started, 2)
