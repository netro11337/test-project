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

    # CSS пустой корзины. Нужен, чтобы отличать «корзина пуста» от «не смог
    # посчитать»: без этого несработавшее добавление выглядело бы так же, как
    # неопознанная вёрстка, и проверка результата теряла бы смысл.
    cart_empty: str = ""

    # Тост после успешного копирования: ссылка ушла в буфер обмена.
    share_toast: str = (
        "//*[contains(text(), 'Ссылка скопирована')"
        " or contains(text(), 'скопирована')]"
    )

    # Кнопка подтверждения внутри окна «Поделиться»: шага два — иконка
    # открывает окно со списком товаров, и только вторая кнопка создаёт ссылку.
    share_confirm: Tuple[str, ...] = (
        "//div[@role='dialog']//button[contains(., 'оделиться')]",
        "//button[contains(., 'оделиться') and contains(., 'товар')]",
        "//div[contains(@data-widget, 'modal')]//button[contains(., 'оделиться')]",
        "//div[@role='dialog']//button[contains(., 'копировать')]",
        "//button[contains(., 'Скопировать')]",
        # Широкий вариант напоследок: уже нажатая кнопка из шапки исключается
        # отдельно, поэтому сюда попадёт именно вторая, из окна.
        "//button[contains(., 'оделиться')]",
        "//*[self::a or self::div[@role='button']][contains(., 'оделиться')]",
    )

    # Признак того, что окно «Поделиться» открылось.
    share_dialog: str = (
        "//div[@role='dialog'] | //div[contains(@data-widget, 'modal')]"
        " | //*[contains(text(), 'Поделиться списком')]"
        " | //*[contains(text(), 'Поделиться товарами')]"
    )

    # Очистка корзины перед новым кругом: кнопка удаления рядом с «Выбрать
    # все» и подтверждение, если магазин переспрашивает.
    cart_clear_buttons: Tuple[str, ...] = (
        "//button[contains(@aria-label, 'далить')]",
        "//button[contains(@title, 'далить')]",
        "//button[contains(., 'Удалить выбранные')]",
        "//button[contains(., 'Удалить')]",
    )
    cart_clear_confirm: Tuple[str, ...] = (
        # Окно «Удалить товары» с синей кнопкой «Удалить». Точное совпадение
        # текста идёт первым: в окне это единственная кнопка с таким словом.
        "//button[normalize-space()='Удалить']",
        "//div[@role='dialog']//button[contains(., 'Удалить')]",
        "//*[contains(@class, 'modal')]//button[contains(., 'Удалить')]",
        "//button[contains(., 'Да, удалить')]",
    )

    # Текст с числом позиций («1 товар», «3 товара»). Запасной способ счёта:
    # разметку списка магазин переписывает чаще, чем эту подпись.
    cart_count_text: Tuple[str, ...] = (
        "//*[contains(text(), 'товар')]",
    )

    # Признак «вход не выполнен»: в шапке есть «Войти». Корзина магазина
    # привязана к аккаунту, поэтому несколько окон с одним логином делят одну
    # корзину, а анонимные профили — нет, у каждого своя.
    signin_marker: str = (
        "//*[self::a or self::button or self::span or self::div]"
        "[normalize-space()='Войти']"
    )

    # Кнопка удаления — иконка без подписи, по тексту её не найти. Опорой
    # служит соседняя кнопка «Поделиться»: на Ozon корзина правее неё,
    # на Wildberries — левее.
    clear_side: str = "right"


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
    cart_ready=(
        "div[data-widget='split'], div[data-widget='cartEmpty'], "
        "div[data-widget='cartList'], [data-widget*='cart']"
    ),
    cart_item="div[data-widget='cartItem'], div[data-widget='cartItemsList'] li",
    cart_empty="div[data-widget='cartEmpty']",
    select_all=(
        "//label[contains(., 'Выбрать все')]//input[@type='checkbox']",
        "//*[contains(text(), 'Выбрать все')]/preceding::input[@type='checkbox'][1]",
    ),
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
    cart_empty="div.basket-empty, div.basket__empty",
    # В окне «Поделиться товарами» кнопка подписана «Скопировать ссылку на
    # товары», а не «Поделиться» — общий селектор её не находит.
    share_confirm=(
        "//button[contains(., 'Скопировать ссылку')]",
        "//div[@role='dialog']//button[contains(., 'Скопировать')]",
        "//div[@role='dialog']//button[contains(., 'оделиться')]",
        "//button[contains(., 'оделиться') and contains(., 'товар')]",
        "//button[contains(., 'копировать')]",
        # Широкий вариант напоследок: уже нажатая иконка исключается отдельно.
        "//button[contains(., 'оделиться')]",
    ),
    clear_side="left",
)


MARKETS: Dict[str, Market] = {market.key: market for market in (OZON, WB)}
DEFAULT_MARKET = OZON.key


def get_market(key: str) -> Market:
    try:
        return MARKETS[key]
    except KeyError:
        raise ValueError(f"Неизвестный маркетплейс: {key!r}") from None
