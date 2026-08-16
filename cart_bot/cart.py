"""Работа со страницей корзины: подсчёт позиций и получение ссылки «Поделиться»."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webdriver import WebDriver
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from .config import Settings
from .markets import Market

log = logging.getLogger(__name__)

# Модалка со ссылкой: поле ввода, ссылка или просто текст со ссылкой.
_MODAL = "//div[@role='dialog'] | //div[contains(@data-widget, 'modal')]"
_MODAL_INPUT = (
    "//div[@role='dialog']//input | //div[contains(@data-widget, 'modal')]//input"
)
_MODAL_ANCHOR = (
    "//div[@role='dialog']//a[contains(@href, 'http')]"
    " | //div[contains(@data-widget, 'modal')]//a[contains(@href, 'http')]"
)

_TRAILING_PUNCT = ".,;:!?"
_SENTINEL = "__cart_bot_no_link__"


@dataclass
class ShareResult:
    """Ссылка на корзину и то, каким способом её удалось достать."""

    url: str
    method: str  # input | anchor | text | clipboard | fallback
    message: str = ""

    @property
    def is_shared(self) -> bool:
        """True, если это настоящая ссылка «поделиться», а не адрес корзины."""
        return self.method != "fallback"


def _url_re(market: Market) -> re.Pattern:
    """Ссылка на домен этого маркетплейса.

    Нежадный префикс: ловим и www.ozon.ru, и короткий ozon.ru/t/... без «www»,
    и не склеиваем две ссылки, если в тексте их несколько.
    """
    host = market.base_url.split("://", 1)[-1].removeprefix("www.")
    return re.compile(
        r"https?://[^\s\"'<>]*?" + re.escape(host) + r"/[^\s\"'<>]*",
        re.IGNORECASE,
    )


def _extract_url(text: str, market: Market) -> Optional[str]:
    if not text:
        return None
    match = _url_re(market).search(text)
    if not match:
        return None
    # Ссылка часто стоит в конце фразы («…скопирована: https://ozon.ru/t/x.»),
    # поэтому финальная пунктуация в URL не входит.
    return match.group(0).rstrip(_TRAILING_PUNCT) or None


def _fallback(market: Market, message: str) -> ShareResult:
    return ShareResult(market.cart_url, "fallback", message)


def open_cart(driver: WebDriver, cfg: Settings, market: Market) -> bool:
    """Открывает корзину, если мы ещё не на ней. True — страница готова."""
    try:
        if market.cart_url not in (driver.current_url or ""):
            driver.get(market.cart_url)
    except TimeoutException:
        pass
    except WebDriverException as exc:
        log.debug("Не удалось открыть корзину: %s", exc)
        return False

    try:
        WebDriverWait(driver, cfg.element_timeout, poll_frequency=0.1).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, market.cart_ready))
        )
        return True
    except TimeoutException:
        return False


def count_items(driver: WebDriver, market: Market) -> int:
    """Число позиций в корзине; -1, если посчитать не вышло."""
    try:
        return len(driver.find_elements(By.CSS_SELECTOR, market.cart_item))
    except WebDriverException:
        return -1


def _grant_clipboard(driver: WebDriver, market: Market) -> bool:
    """Разрешает странице читать буфер обмена — иначе readText() отклоняется."""
    try:
        driver.execute_cdp_cmd(
            "Browser.grantPermissions",
            {
                "origin": market.base_url,
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


def _visible(elements: List[WebElement]) -> List[WebElement]:
    result = []
    for element in elements:
        try:
            if element.is_displayed():
                result.append(element)
        except WebDriverException:
            continue
    return result


def ensure_all_selected(driver: WebDriver, market: Market) -> None:
    """Отмечает чекбокс «Все», если он есть и снят.

    На Wildberries кнопка «Поделиться» шарит выделенные товары, поэтому со
    снятой галкой можно получить ссылку на половину корзины.
    """
    for xpath in market.select_all:
        for element in _visible(driver.find_elements(By.XPATH, xpath)):
            try:
                if not element.is_selected():
                    driver.execute_script("arguments[0].click();", element)
                    log.debug("Отметил «Все» по селектору %s", xpath)
                return
            except WebDriverException:
                continue


def find_share_button(
    driver: WebDriver, cfg: Settings, market: Market
) -> Tuple[Optional[WebElement], str, int]:
    """Ищет кнопку «Поделиться», перебирая селекторы по порядку.

    На Wildberries это иконка без подписи в строке магазина, поэтому текстовый
    поиск не годится и кандидатов приходится перебирать. Возвращаем ещё и
    сработавший селектор с числом найденных кнопок: если кнопок больше одной,
    в корзине несколько магазинов и шарится, скорее всего, только один.
    """
    deadline = time.monotonic() + cfg.element_timeout
    while True:
        for xpath in market.share_buttons:
            try:
                candidates = _visible(driver.find_elements(By.XPATH, xpath))
            except WebDriverException:
                continue
            if candidates:
                return candidates[0], xpath, len(candidates)
        if time.monotonic() >= deadline:
            return None, "", 0
        time.sleep(0.15)


def _from_modal(
    driver: WebDriver, market: Market, deadline: float
) -> Optional[ShareResult]:
    """Опрашивает модалку: поле со ссылкой, затем ссылка, затем текст."""
    while time.monotonic() < deadline:
        for xpath, method, attribute in (
            (_MODAL_INPUT, "input", "value"),
            (_MODAL_ANCHOR, "anchor", "href"),
        ):
            for element in driver.find_elements(By.XPATH, xpath):
                try:
                    url = _extract_url(element.get_attribute(attribute) or "", market)
                except WebDriverException:
                    continue
                if url:
                    return ShareResult(url, method)

        for element in driver.find_elements(By.XPATH, _MODAL):
            try:
                url = _extract_url(element.text, market)
            except WebDriverException:
                continue
            if url:
                return ShareResult(url, "text")

        time.sleep(0.1)
    return None


def _from_clipboard(
    driver: WebDriver, market: Market, deadline: float
) -> Optional[ShareResult]:
    """Ждёт, пока в буфере вместо метки появится ссылка."""
    while time.monotonic() < deadline:
        content = _read_clipboard(driver)
        if content and content != _SENTINEL:
            url = _extract_url(content, market)
            if url:
                return ShareResult(url, "clipboard")
        time.sleep(0.15)
    return None


def share_cart(driver: WebDriver, cfg: Settings) -> ShareResult:
    """Жмёт «Поделиться корзиной» и достаёт выданную ссылку.

    Маркетплейс по этой кнопке ведёт себя двояко — то показывает окно со
    ссылкой, то молча кладёт её в буфер обмена, поэтому пробуем оба пути.
    Если ссылку получить не удалось, отдаём адрес корзины: она всё равно
    собрана и её видно кнопкой «Открыть корзину».
    """
    market = cfg.market

    if not open_cart(driver, cfg, market):
        return _fallback(market, "Страница корзины не загрузилась")

    if count_items(driver, market) == 0:
        return _fallback(market, "Корзина пуста — делиться нечем")

    ensure_all_selected(driver, market)
    _grant_clipboard(driver, market)
    _prime_clipboard(driver)

    button, selector, candidates = find_share_button(driver, cfg, market)
    if button is None:
        return _fallback(market, "Кнопка «Поделиться» не найдена")

    note = f"способ поиска кнопки: {selector}"
    if candidates > 1:
        note += (
            f"; найдено кнопок: {candidates} — в корзине несколько магазинов, "
            "ссылка может охватывать только первый"
        )

    try:
        try:
            button.click()
        except WebDriverException:
            driver.execute_script("arguments[0].click();", button)
    except WebDriverException as exc:
        return _fallback(
            market, f"Клик по «Поделиться» не прошёл: {exc}".splitlines()[0]
        )

    time.sleep(cfg.micro_pause)
    deadline = time.monotonic() + cfg.element_timeout

    result = _from_modal(driver, market, deadline)
    if result is None:
        result = _from_clipboard(driver, market, deadline + 1.0)

    if result is None:
        return _fallback(
            market,
            f"Кнопка нажата ({selector}), но ссылка не появилась "
            "ни в окне, ни в буфере обмена",
        )

    result.message = note
    return result


def read_cart_summary(driver: WebDriver, cfg: Settings) -> Tuple[ShareResult, int]:
    """Открывает корзину и возвращает (ссылка, число позиций)."""
    market = cfg.market

    if not open_cart(driver, cfg, market):
        return _fallback(market, "Страница корзины не загрузилась"), -1

    items = count_items(driver, market)
    if not cfg.fetch_share_link:
        return _fallback(market, "Получение ссылки отключено"), items

    return share_cart(driver, cfg), items
