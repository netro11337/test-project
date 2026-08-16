import unittest

from cart_bot.cart import find_clear_button, find_share_button
from cart_bot.config import Settings
from cart_bot.markets import OZON, WB


class FakeElement:
    def __init__(self, name):
        self.name = name

    def is_displayed(self):
        return True

    def __repr__(self):  # для читаемых сообщений об ошибках
        return f"<{self.name}>"


class CartDriver:
    """Корзина, где иконки есть и в шапке группы, и у каждого товара.

    Порядок кнопок в шапке WB со скриншота: сердце, удалить, поделиться.
    У товаров — такие же тройки, и раньше программа брала первую попавшуюся,
    поэтому удаляла один товар вместо всей корзины.
    """

    def __init__(self, market, header, items):
        self.market = market
        self.header = header
        self.items = items
        self.checkbox = FakeElement("чекбокс «Все»")

    def find_elements(self, by, selector):
        if selector in self.market.select_all:
            return [self.checkbox]
        if selector in self.market.share_buttons:
            # Сначала иконки товаров — так их отдаёт настоящая страница.
            return [b for b in self.items + self.header if "поделиться" in b.name]
        if selector in self.market.cart_clear_buttons:
            return []  # подписи «Удалить» на странице нет, только иконки
        return []

    def execute_script(self, script, *args):
        if "querySelectorAll" in script and args and args[0] is self.checkbox:
            return list(self.header)
        return None


def wb_cart():
    header = [
        FakeElement("шапка: сердце"),
        FakeElement("шапка: удалить"),
        FakeElement("шапка: поделиться"),
    ]
    items = [
        FakeElement("товар 1: сердце"),
        FakeElement("товар 1: удалить"),
        FakeElement("товар 1: поделиться"),
        FakeElement("товар 2: сердце"),
        FakeElement("товар 2: удалить"),
        FakeElement("товар 2: поделиться"),
    ]
    return CartDriver(WB, header, items), header, items


def ozon_cart():
    header = [
        FakeElement("шапка: поделиться"),
        FakeElement("шапка: удалить"),
    ]
    return CartDriver(OZON, header, []), header


class WildberriesHeaderTest(unittest.TestCase):
    def setUp(self):
        self.cfg = Settings(element_timeout=0.0)

    def test_clear_button_comes_from_the_header(self):
        driver, header, items = wb_cart()
        button, how = find_clear_button(driver, self.cfg, WB)
        self.assertIs(button, header[1], "взята кнопка удаления не из шапки")
        self.assertIn("шапка", how)

    def test_item_delete_button_is_never_used(self):
        # Это и была ошибка: удалялся один товар вместо всей корзины.
        driver, _, items = wb_cart()
        button, _ = find_clear_button(driver, self.cfg, WB)
        self.assertNotIn(button, items)

    def test_share_button_also_comes_from_the_header(self):
        driver, header, _ = wb_cart()
        button, how, _ = find_share_button(driver, self.cfg, WB)
        self.assertIs(button, header[2])
        self.assertIn("шапка", how)


class OzonHeaderTest(unittest.TestCase):
    def setUp(self):
        self.cfg = Settings(element_timeout=0.0)

    def test_clear_button_is_right_of_share(self):
        driver, header = ozon_cart()
        button, how = find_clear_button(driver, self.cfg, OZON)
        self.assertIs(button, header[1])
        self.assertIn("шапка", how)


class PositionFallbackTest(unittest.TestCase):
    """Если «Поделиться» в шапке не опознали, берём кнопку по месту."""

    def setUp(self):
        self.cfg = Settings(element_timeout=0.0)

    def test_wb_takes_second_to_last(self):
        header = [FakeElement("сердце"), FakeElement("удалить"), FakeElement("иконка")]
        driver = CartDriver(WB, header, [])
        driver.find_elements = lambda by, sel: (
            [driver.checkbox] if sel in WB.select_all else []
        )
        button, how = find_clear_button(driver, self.cfg, WB)
        self.assertIs(button, header[1])
        self.assertIn("предпоследняя", how)

    def test_ozon_takes_last(self):
        header = [FakeElement("иконка"), FakeElement("удалить")]
        driver = CartDriver(OZON, header, [])
        driver.find_elements = lambda by, sel: (
            [driver.checkbox] if sel in OZON.select_all else []
        )
        button, how = find_clear_button(driver, self.cfg, OZON)
        self.assertIs(button, header[1])
        self.assertIn("последняя", how)


if __name__ == "__main__":
    unittest.main()
