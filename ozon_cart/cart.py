"""Работа со страницей корзины: подсчёт позиций и получение ссылки «Поделиться»."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Optional

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .config import BASE_URL, CART_URL, Settings

log = logging.getLogger(__name__)

# Кнопка «Поделиться» на странице корзины. Ищем по тексту без первой буквы —
# так одинаково ловится и «Поделиться», и «поделиться корзиной».
_SHARE_BUTTON = (
    "//button[contains(., 'оделиться')]"
    " | //a[contains(., 'оделиться')]"
    " | //*[contains(@aria-label, 'оделиться')]"
    " | //div[@data-widget='cartShare']//button"
)

# Модалка со ссылкой: поле ввода, ссылка или просто текст со ссылкой.
_MODAL = "//div[@role='dialog'] | //div[contains(@data-widget, 'modal')]"
_MODAL_INPUT = (
    "//div[@role='dialog']//input | //div[contains(@data-widget, 'modal')]//input"
)
_MODAL_ANCHOR = (
    "//div[@role='dialog']//a[contains(@href, 'ozon')]"
    " | //div[contains(@data-widget, 'modal')]//a[contains(@href, 'ozon')]"
)

# Нежадный префикс: ловим и www.ozon.ru, и короткий ozon.ru/t/... без «www»,
# и не склеиваем две ссылки, если в тексте их несколько.
_URL_RE = re.compile(r"https?://[^\s\"'<>]*?ozon\.ru/[^\s\"'<>]*", re.IGNORECASE)
_TRAILING_PUNCT = ".,;:!?"
_SENTINEL = "__ozon_cart_no_link__"

_CART_READY = "div[data-widget='split'], div[data-widget='cartEmpty']"
_CART_ITEM = "div[data-widget='cartItem']"


@dataclass
class ShareResult:
    """Ссылка на корзину и то, каким способом её удалось достать."""

    url: str
    method: str  # input | anchor | text | clipboard | fallback
    message: str = ""

    @property
    def is_shared(self) -> bool:
        """True, если это настоящая ссылка «поделиться», а не адрес /cart."""
        return self.method != "fallback"


def _fallback(message: str) -> ShareResult:
    return ShareResult(CART_URL, "fallback", message)


def open_cart(driver: WebDriver, cfg: Settings) -> bool:
    """Открывает корзину, если мы ещё не на ней. True — страница готова."""
    try:
        if "/cart" not in (driver.current_url or ""):
            driver.get(CART_URL)
    except TimeoutException:
        pass
    except WebDriverException as exc:
        log.debug("Не удалось открыть корзину: %s", exc)
        return False

    try:
        WebDriverWait(driver, cfg.element_timeout, poll_frequency=0.1).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, _CART_READY))
        )
        return True
    except TimeoutException:
        return False


def count_items(driver: WebDriver) -> int:
    """Число позиций в корзине; -1, если посчитать не вышло."""
    try:
        return len(driver.find_elements(By.CSS_SELECTOR, _CART_ITEM))
    except WebDriverException:
        return -1


def _grant_clipboard(driver: WebDriver) -> bool:
    """Разрешает странице читать буфер обмена — иначе readText() отклоняется."""
    try:
        driver.execute_cdp_cmd(
            "Browser.grantPermissions",
            {
                "origin": BASE_URL,
                "permissions": ["clipboardReadWrite", "clipboardSanitizedWrite"],
            },
        )
        return True
    except WebDriverException as exc:
        log.debug("Не выдал права на буфер обмена: %s", exc)
        return False


def _prime_clipboard(driver: WebDriver) -> bool:
    """Кладёт в буфер метку, чтобы отличить свежую ссылку от старого содержимого."""
    try:
        driver.execute_script(
            "navigator.clipboard && navigator.clipboard.writeText(arguments[0]);",
            _SENTINEL,
        )
        return True
    except WebDriverException:
        return False


def _read_clipboard(driver: WebDriver) -> str:
    """Синхронно читает буфер обмена через async-скрипт."""
    try:
        return (
            driver.execute_async_script(
                "const done = arguments[arguments.length - 1];"
                "if (!navigator.clipboard) { done(''); return; }"
                "navigator.clipboard.readText().then(done).catch(() => done(''));"
            )
            or ""
        )
    except WebDriverException:
        return ""


def _extract_url(text: str) -> Optional[str]:
    if not text:
        return None
    match = _URL_RE.search(text)
    if not match:
        return None
    # Ссылка часто стоит в конце фразы («…скопирована: https://ozon.ru/t/x.»),
    # поэтому финальная пунктуация в URL не входит.
    return match.group(0).rstrip(_TRAILING_PUNCT) or None


def _find_share_button(driver: WebDriver, cfg: Settings) -> Optional[WebElement]:
    try:
        WebDriverWait(driver, cfg.element_timeout, poll_frequency=0.1).until(
            EC.presence_of_element_located((By.XPATH, _SHARE_BUTTON))
        )
    except TimeoutException:
        return None
    elements = driver.find_elements(By.XPATH, _SHARE_BUTTON)
    for element in elements:
        try:
            if element.is_displayed():
                return element
        except WebDriverException:
            continue
    return elements[0] if elements else None


def _from_modal(driver: WebDriver, deadline: float) -> Optional[ShareResult]:
    """Опрашивает модалку: поле со ссылкой, затем ссылка, затем текст."""
    while time.monotonic() < deadline:
        for xpath, method, attribute in (
            (_MODAL_INPUT, "input", "value"),
            (_MODAL_ANCHOR, "anchor", "href"),
        ):
            for element in driver.find_elements(By.XPATH, xpath):
                try:
                    url = _extract_url(element.get_attribute(attribute) or "")
                except WebDriverException:
                    continue
                if url:
                    return ShareResult(url, method)

        for element in driver.find_elements(By.XPATH, _MODAL):
            try:
                url = _extract_url(element.text)
            except WebDriverException:
                continue
            if url:
                return ShareResult(url, "text")

        time.sleep(0.1)
    return None


def _from_clipboard(driver: WebDriver, deadline: float) -> Optional[ShareResult]:
    """Ждёт, пока в буфере вместо метки появится ссылка."""
    while time.monotonic() < deadline:
        content = _read_clipboard(driver)
        if content and content != _SENTINEL:
            url = _extract_url(content)
            if url:
                return ShareResult(url, "clipboard")
        time.sleep(0.15)
    return None


def share_cart(driver: WebDriver, cfg: Settings) -> ShareResult:
    """Жмёт «Поделиться корзиной» и достаёт выданную ссылку.

    Ozon по этой кнопке либо показывает модалку со ссылкой, либо молча кладёт
    её в буфер обмена, поэтому пробуем оба пути. Если ссылку получить не
    удалось, отдаём обычный /cart — корзина всё равно собрана.
    """
    if not open_cart(driver, cfg):
        return _fallback("Страница корзины не загрузилась")

    if count_items(driver) == 0:
        return _fallback("Корзина пуста — делиться нечем")

    _grant_clipboard(driver)
    _prime_clipboard(driver)

    button = _find_share_button(driver, cfg)
    if button is None:
        return _fallback("Кнопка «Поделиться» не найдена")

    try:
        try:
            button.click()
        except WebDriverException:
            driver.execute_script("arguments[0].click();", button)
    except WebDriverException as exc:
        return _fallback(f"Клик по «Поделиться» не прошёл: {exc}".splitlines()[0])

    time.sleep(cfg.micro_pause)
    deadline = time.monotonic() + cfg.element_timeout

    result = _from_modal(driver, deadline)
    if result is not None:
        return result

    result = _from_clipboard(driver, deadline + 1.0)
    if result is not None:
        return result

    return _fallback("Ссылка не появилась ни в окне, ни в буфере обмена")


def read_cart_summary(driver: WebDriver, cfg: Settings) -> tuple[ShareResult, int]:
    """Открывает корзину и возвращает (ссылка, число позиций)."""
    if not open_cart(driver, cfg):
        return _fallback("Страница корзины не загрузилась"), -1

    items = count_items(driver)
    if not cfg.fetch_share_link:
        return _fallback("Получение ссылки отключено"), items

    return share_cart(driver, cfg), items
