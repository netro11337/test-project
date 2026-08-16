"""Добавление одного SKU в корзину внутри уже открытой сессии."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
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


def _click(driver: WebDriver, element: WebElement) -> None:
    """Обычный клик, при перехвате — через JS."""
    try:
        element.click()
    except (ElementClickInterceptedException, WebDriverException):
        driver.execute_script("arguments[0].click();", element)


def _confirm_added(driver: WebDriver, cfg: Settings, market: Market) -> bool:
    """Ждёт, пока кнопка не переключится в состояние «в корзине».

    Ждём именно смену состояния, а не фиксированный sleep: на быстрой
    странице это десятки миллисекунд.
    """
    try:
        WebDriverWait(driver, cfg.element_timeout, poll_frequency=0.1).until(
            EC.presence_of_element_located((By.XPATH, market.in_cart_marker))
        )
        return True
    except TimeoutException:
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

    if _find_first(driver, market.antibot) is not None:
        return SkuResult(
            sku,
            Outcome.BLOCKED,
            f"{market.title} показал антибот-проверку",
            _since(started),
        )
    if _find_first(driver, market.not_found) is not None:
        return SkuResult(sku, Outcome.NOT_FOUND, "Товар не найден", _since(started))

    try:
        WebDriverWait(driver, cfg.element_timeout, poll_frequency=0.1).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, market.add_widget))
        )
    except TimeoutException:
        if _find_first(driver, market.out_of_stock) is not None:
            return SkuResult(
                sku, Outcome.OUT_OF_STOCK, "Нет в наличии", _since(started)
            )
        return SkuResult(
            sku, Outcome.ERROR, "Кнопка добавления не появилась", _since(started)
        )

    if _find_first(driver, market.in_cart_marker) is not None:
        return SkuResult(sku, Outcome.ALREADY, "Уже в корзине", _since(started))

    button = _find_first(driver, market.add_button)
    if button is None:
        if _find_first(driver, market.out_of_stock) is not None:
            return SkuResult(
                sku, Outcome.OUT_OF_STOCK, "Нет в наличии", _since(started)
            )
        return SkuResult(
            sku, Outcome.ERROR, "Кнопка «В корзину» не найдена", _since(started)
        )

    try:
        _click(driver, button)
    except (NoSuchElementException, WebDriverException) as exc:
        return SkuResult(sku, Outcome.ERROR, str(exc).splitlines()[0], _since(started))

    if _confirm_added(driver, cfg, market):
        time.sleep(cfg.micro_pause)
        return SkuResult(sku, Outcome.ADDED, "Добавлен", _since(started))

    if _find_first(driver, market.out_of_stock) is not None:
        return SkuResult(sku, Outcome.OUT_OF_STOCK, "Нет в наличии", _since(started))

    return SkuResult(
        sku, Outcome.ERROR, "Клик прошёл, но корзина не подтвердилась", _since(started)
    )


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
