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
        # Корзина тяжелее карточки товара, поэтому ждём дольше обычного:
        # преждевременная сдача здесь стоит потерянной ссылки на корзину.
        WebDriverWait(driver, cfg.element_timeout * 2, poll_frequency=0.1).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, market.cart_ready))
        )
        return True
    except TimeoutException:
        return False


_COUNT_RE = re.compile(r"(\d+)\s*товар", re.IGNORECASE)


def _count_from_text(driver: WebDriver, market: Market) -> int:
    """Читает число из подписи вида «1 товар • 400 гр»."""
    for xpath in market.cart_count_text:
        try:
            elements = driver.find_elements(By.XPATH, xpath)
        except WebDriverException:
            continue
        for element in elements:
            try:
                match = _COUNT_RE.search(element.text or "")
            except WebDriverException:
                continue
            if match:
                return int(match.group(1))
    return -1


def count_items(driver: WebDriver, market: Market) -> int:
    """Число позиций в корзине; -1, если посчитать не вышло.

    Ноль возвращаем только когда магазин прямо показал пустую корзину. Если
    вёрстка незнакомая, честнее сказать «не знаю», чем «пусто»: иначе
    несработавшее добавление не отличить от неопознанной разметки.

    Порядок способов: явная пустота, разметка списка, подпись с числом. Список
    магазин перерисовывает чаще, чем подпись «N товаров», поэтому она идёт
    запасным вариантом, а не единственным.
    """
    try:
        if market.cart_empty and driver.find_elements(
            By.CSS_SELECTOR, market.cart_empty
        ):
            return 0
        items = driver.find_elements(By.CSS_SELECTOR, market.cart_item)
        if items:
            return len(items)
    except WebDriverException:
        return -1
    return _count_from_text(driver, market)


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


def _find_first(driver: WebDriver, xpath: str) -> Optional[WebElement]:
    try:
        elements = driver.find_elements(By.XPATH, xpath)
        return elements[0] if elements else None
    except WebDriverException:
        return None


def _click(driver: WebDriver, element: WebElement) -> bool:
    """Обычный клик, при перехвате — через JS. False, если не вышло совсем."""
    try:
        element.click()
        return True
    except WebDriverException:
        try:
            driver.execute_script("arguments[0].click();", element)
            return True
        except WebDriverException as exc:
            log.debug("Клик не прошёл: %s", exc)
            return False


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


def find_share_confirm(
    driver: WebDriver, market: Market, avoid, timeout: float
) -> Tuple[Optional[WebElement], str]:
    """Ищет кнопку подтверждения внутри окна «Поделиться».

    На Ozon шага два: иконка открывает окно со списком товаров, и только
    вторая кнопка создаёт ссылку. Кнопку, которую уже нажали, пропускаем —
    иначе окно просто закроется.
    """
    deadline = time.monotonic() + timeout
    while True:
        for xpath in market.share_confirm:
            try:
                candidates = _visible(driver.find_elements(By.XPATH, xpath))
            except WebDriverException:
                continue
            for element in candidates:
                if avoid is not None and element == avoid:
                    continue
                return element, xpath
        if time.monotonic() >= deadline:
            return None, ""
        time.sleep(0.1)


def _focus_window(driver: WebDriver) -> None:
    """Возвращает фокус окну: без него чтение буфера обмена отклоняется."""
    try:
        driver.switch_to.window(driver.current_window_handle)
        driver.execute_script("window.focus();")
    except WebDriverException:
        pass


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

    if not _click(driver, button):
        return _fallback(market, "Клик по «Поделиться» не прошёл")

    time.sleep(cfg.micro_pause)

    # Второй шаг: в открывшемся окне со списком товаров есть своя кнопка
    # «Поделиться», и только она создаёт ссылку.
    confirm, confirm_selector = find_share_confirm(
        driver, market, button, min(3.0, cfg.element_timeout)
    )
    if confirm is not None:
        if _click(driver, confirm):
            note += f"; подтверждение: {confirm_selector}"
            time.sleep(cfg.micro_pause)
        else:
            note += "; подтверждение нажать не удалось"

    deadline = time.monotonic() + cfg.element_timeout

    result = _from_modal(driver, market, deadline)
    if result is None:
        _focus_window(driver)
        result = _from_clipboard(driver, market, deadline + 1.0)

    if result is not None:
        result.message = note
        return result

    # Тост «Ссылка скопирована» означает, что ссылка создана и лежит в буфере
    # обмена — просто прочитать её из браузера не вышло. Забрать её сможет
    # само приложение, из системного буфера.
    if _find_first(driver, market.share_toast) is not None:
        return ShareResult(
            market.cart_url,
            "os_clipboard_pending",
            f"{note}; магазин сообщил, что ссылка скопирована в буфер обмена",
        )

    return _fallback(
        market,
        f"Кнопка нажата ({selector}), но ссылка не появилась "
        "ни в окне, ни в буфере обмена",
    )


# Кнопка удаления — иконка без подписи, найти её по тексту нельзя. Опираемся
# на соседнюю кнопку «Поделиться» и берём соседа с нужной стороны: на Ozon
# корзина правее, на Wildberries левее.
_NEIGHBOUR_JS = """
const share = arguments[0], side = arguments[1];
let node = share;
for (let depth = 0; depth < 6 && node.parentElement; depth++) {
  node = node.parentElement;
  const buttons = Array.from(node.querySelectorAll('button'));
  const index = buttons.indexOf(share);
  if (index !== -1 && buttons.length > 1) {
    const target = side === 'left' ? buttons[index - 1] : buttons[index + 1];
    if (target) return target;
  }
}
return null;
"""


def find_clear_button(
    driver: WebDriver, cfg: Settings, market: Market
) -> Tuple[Optional[WebElement], str]:
    """Ищет кнопку удаления: сначала по подписи, потом по соседству."""
    for xpath in market.cart_clear_buttons:
        try:
            candidates = _visible(driver.find_elements(By.XPATH, xpath))
        except WebDriverException:
            continue
        if candidates:
            return candidates[0], xpath

    share, _, _ = find_share_button(driver, cfg, market)
    if share is None:
        return None, ""

    try:
        neighbour = driver.execute_script(_NEIGHBOUR_JS, share, market.clear_side)
    except WebDriverException as exc:
        log.debug("Поиск соседней кнопки не удался: %s", exc)
        return None, ""

    if neighbour is None:
        return None, ""
    return neighbour, f"сосед «Поделиться» {market.clear_side}"


def _confirm_clear(driver: WebDriver, cfg: Settings, market: Market) -> bool:
    """Жмёт «Удалить» в окне подтверждения. False — окна не было."""
    deadline = time.monotonic() + min(3.0, cfg.element_timeout)
    while time.monotonic() < deadline:
        for xpath in market.cart_clear_confirm:
            try:
                candidates = _visible(driver.find_elements(By.XPATH, xpath))
            except WebDriverException:
                continue
            for element in candidates:
                if _click(driver, element):
                    log.debug("Подтвердил удаление по селектору %s", xpath)
                    return True
        time.sleep(0.1)
    return False


def clear_cart(driver: WebDriver, cfg: Settings) -> Tuple[bool, str]:
    """Опустошает корзину, чтобы следующий круг начинался с чистой.

    Возвращает (получилось, пояснение). Успех подтверждаем повторным
    подсчётом: без проверки «очистил» может оказаться такой же неправдой,
    какой было «добавил».
    """
    market = cfg.market

    if not open_cart(driver, cfg, market):
        return False, "страница корзины не загрузилась"

    if count_items(driver, market) == 0:
        return True, "корзина и так пуста"

    ensure_all_selected(driver, market)

    button, how = find_clear_button(driver, cfg, market)
    if button is None:
        return False, "кнопка удаления не найдена"
    if not _click(driver, button):
        return False, f"кнопка удаления найдена ({how}), но не нажалась"

    time.sleep(cfg.micro_pause)

    # Магазин переспрашивает: окно «Удалить товары» с кнопкой «Удалить».
    # Окно появляется не мгновенно, поэтому именно ждём его, а не заглядываем
    # один раз: без подтверждения корзина останется полной.
    confirmed = _confirm_clear(driver, cfg, market)
    if confirmed:
        how += " + подтверждение"

    deadline = time.monotonic() + cfg.element_timeout
    while time.monotonic() < deadline:
        if count_items(driver, market) == 0:
            return True, f"корзина очищена ({how})"
        time.sleep(0.2)

    left = count_items(driver, market)
    return False, f"нажал кнопку ({how}), но в корзине осталось позиций: {left}"


def read_cart_summary(driver: WebDriver, cfg: Settings) -> Tuple[ShareResult, int]:
    """Открывает корзину и возвращает (ссылка, число позиций)."""
    market = cfg.market

    if not open_cart(driver, cfg, market):
        return _fallback(market, "Страница корзины не загрузилась"), -1

    items = count_items(driver, market)
    if not cfg.fetch_share_link:
        return _fallback(market, "Получение ссылки отключено"), items

    return share_cart(driver, cfg), items
