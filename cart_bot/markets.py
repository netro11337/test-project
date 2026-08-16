"""Описание маркетплейсов: адреса и селекторы.

Вся разница между Ozon и Wildberries живёт здесь. Остальной код (потоки,
разбор SKU, статусы, копирование ссылок) от маркетплейса не зависит.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class Market:
    key: str
    title: str
    base_url: str
    product_url: str  # шаблон с {sku}
    cart_url: str

    # --- карточка товара ---
    add_widget: str  # CSS: контейнер-подсказка, что страница отрисовалась
    # XPath-кандидаты кнопки «В корзину», по порядку надёжности. Список, а не
    # один селектор: магазин перерисовывает вёрстку, и привязка к одному
    # контейнеру ломает работу целиком.
    add_buttons: Tuple[str, ...]
    in_cart_marker: str  # XPath: признак, что товар уже в корзине
    out_of_stock: str  # XPath
    not_found: str  # XPath
    antibot: str  # XPath

    # --- страница корзины ---
    cart_ready: str  # CSS: признак загруженной корзины
    cart_item: str  # CSS: одна позиция
    share_buttons: Tuple[str, ...]  # XPath-кандидаты, по порядку надёжности
    select_all: Tuple[str, ...] = ()  # XPath: чекбокс «Все», если он есть

    # Заголовок вкладки при блокировке. Признак надёжнее текста на странице:
    # текст магазин переписывает, а служебная страница называется одинаково.
    # Сравнение идёт в нижнем регистре по вхождению.
    antibot_titles: Tuple[str, ...] = ("antibot", "captcha", "доступ ограничен")


OZON = Market(
    key="ozon",
    title="Ozon",
    base_url="https://www.ozon.ru",
    product_url="https://www.ozon.ru/product/{sku}/",
    cart_url="https://www.ozon.ru/cart",
    add_widget="div[data-widget='webAddToCart'], div[data-widget='webProductHeading']",
    # «Купить сейчас» намеренно не ищем: она ведёт прямо в оформление заказа,
    # а нам нужна только корзина. «Перейти в корзину» тоже исключаем — это
    # ссылка на уже собранную корзину, а не добавление.
    add_buttons=(
        "//div[@data-widget='webAddToCart']//button[contains(., 'В корзину')]",
        "//button[contains(., 'В корзину') and not(contains(., 'Перейти'))]",
        "//button[contains(., 'Добавить в корзину')]",
        "//div[@data-widget='webAddToCart']//button",
    ),
    in_cart_marker=(
        "//button[contains(., 'В корзине')]"
        " | //div[@data-widget='webAddToCart']//*[contains(., 'Перейти в корзину')]"
    ),
    out_of_stock=(
        "//*[contains(text(), 'Этот товар закончил')"
        " or contains(text(), 'Товар закончился')"
        " or contains(text(), 'Нет в наличии')]"
    ),
    not_found=(
        "//*[contains(text(), 'Страница не найдена')"
        " or contains(text(), 'такой страницы не существует')]"
    ),
    antibot=(
        "//*[contains(text(), 'Доступ ограничен')"
        " or contains(text(), 'Подтвердите, что вы не робот')"
        " or contains(text(), 'Вы не робот')"
        # Страница антибота Ozon: заголовок вкладки «Antibot Captcha»,
        # на самой странице только это сообщение и кнопка «Обновить».
        " or contains(text(), 'Ой, что-то пошло не так')"
        " or contains(text(), 'Обновите страницу')]"
    ),
    cart_ready="div[data-widget='split'], div[data-widget='cartEmpty']",
    cart_item="div[data-widget='cartItem']",
    # На Ozon кнопка подписана текстом — ищем по нему.
    share_buttons=(
        "//div[@data-widget='cartShare']//button",
        "//button[contains(., 'оделиться')]",
        "//a[contains(., 'оделиться')]",
        "//*[contains(@aria-label, 'оделиться')]",
    ),
)


# На Wildberries «Поделиться» — иконка без подписи, в строке магазина рядом с
# «сердечком» и корзиной удаления. Текстовый поиск тут не работает, поэтому
# идём по aria-label/title, затем по классам и data-атрибутам, затем по самой
# SVG-иконке. Порядок = от самого надёжного к самому грубому.
WB = Market(
    key="wb",
    title="Wildberries",
    base_url="https://www.wildberries.ru",
    product_url="https://www.wildberries.ru/catalog/{sku}/detail.aspx",
    cart_url="https://www.wildberries.ru/lk/basket",
    add_widget="div.product-page__aside-container, div.product-page, button.order__button",
    add_buttons=(
        "//button[contains(@class, 'order__button')]",
        "//button[contains(., 'Добавить в корзину')]",
        "//button[contains(., 'В корзину') and not(contains(., 'Перейти'))]",
        "//a[contains(@class, 'order__button')]",
    ),
    in_cart_marker=(
        "//*[contains(text(), 'Товар в корзине')"
        " or contains(text(), 'Перейти в корзину')"
        " or contains(text(), 'В корзине')]"
    ),
    out_of_stock=(
        "//*[contains(text(), 'Нет в наличии')"
        " or contains(text(), 'Товара нет в наличии')"
        " or contains(text(), 'Распродан')]"
    ),
    not_found=(
        "//*[contains(text(), 'Страница не найдена')"
        " or contains(text(), 'такой страницы не существует')"
        " or contains(text(), 'Товар не найден')]"
    ),
    antibot=(
        "//*[contains(text(), 'Доступ ограничен')"
        " or contains(text(), 'Подтвердите, что вы не робот')"
        " or contains(text(), 'Вы не робот')"
        " or contains(text(), 'Ой, что-то пошло не так')"
        " or contains(text(), 'Обновите страницу')]"
    ),
    cart_ready=(
        "div.basket, div.basket-section, div.basket-empty, "
        "div.b-basket, [data-tag='basket']"
    ),
    cart_item=(
        "div.list-item, div.basket-list__item, div.product-list__item, "
        "[data-tag='basketItem']"
    ),
    share_buttons=(
        "//button[contains(@aria-label, 'оделит')]",
        "//button[contains(@title, 'оделит')]",
        "//*[contains(@aria-label, 'оделит')][self::a or self::div[@role='button']]",
        "//button[contains(@data-testid, 'share')]",
        "//button[contains(@class, 'share')]",
        "//*[@data-tag='share']",
        # Иконка: <svg><use href="...share..."> внутри кнопки.
        "//button[.//*[local-name()='use']"
        "[contains(@*[local-name()='href'], 'share')]]",
        "//button[contains(., 'оделиться')]",
    ),
    select_all=(
        "//*[contains(@class, 'checkbox')][.//*[contains(text(), 'Все')]]"
        "//input[@type='checkbox']",
        "//label[contains(., 'Все')]//input[@type='checkbox']",
    ),
)


MARKETS: Dict[str, Market] = {market.key: market for market in (OZON, WB)}
DEFAULT_MARKET = OZON.key


def get_market(key: str) -> Market:
    try:
        return MARKETS[key]
    except KeyError:
        raise ValueError(f"Неизвестный маркетплейс: {key!r}") from None
