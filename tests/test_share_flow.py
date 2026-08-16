import unittest

from cart_bot.config import Settings
from cart_bot.cart import find_share_confirm
from cart_bot.markets import OZON, WB

try:
    from lxml import etree

    HAS_LXML = True
except ImportError:  # pragma: no cover
    HAS_LXML = False


# Окно «Поделиться списком» на Ozon: список товаров и своя кнопка,
# которая и создаёт ссылку.
SHARE_MODAL = """
<html><body>
  <div role="dialog">
    <h2>Поделиться списком</h2>
    <p>Товары из вашей корзины</p>
    <div>Инструкция к магнитоле 9д-22</div>
    <button><span>Поделиться</span><span>1 товар</span></button>
  </div>
  <button aria-label="Поделиться">иконка в шапке корзины</button>
</body></html>
"""

CART_PAGE = """
<html><body>
  <label><input type="checkbox" checked="checked"/>Выбрать все</label>
  <button aria-label="Поделиться">поделиться</button>
  <button aria-label="Удалить выбранные товары">корзина</button>
</body></html>
"""


class FakeElement:
    def __init__(self, name):
        self.name = name

    def is_displayed(self):
        return True


class FakeDriver:
    def __init__(self, matches):
        self.matches = matches

    def find_elements(self, by, xpath):
        return self.matches.get(xpath, [])


@unittest.skipUnless(HAS_LXML, "нужен lxml для разбора разметки")
class ShareModalMarkupTest(unittest.TestCase):
    def setUp(self):
        self.modal = etree.fromstring(SHARE_MODAL)
        self.cart = etree.fromstring(CART_PAGE)

    def test_confirm_button_found_inside_modal(self):
        for xpath in OZON.share_confirm:
            found = self.modal.xpath(xpath)
            if found:
                text = "".join(found[0].itertext())
                self.assertIn("Поделиться", text)
                self.assertIn("1 товар", text)
                return
        self.fail("кнопка подтверждения в окне не найдена")

    def test_share_icon_found_on_cart_page(self):
        for xpath in OZON.share_buttons:
            if self.cart.xpath(xpath):
                return
        self.fail("кнопка «Поделиться» в корзине не найдена")

    def test_clear_button_found_on_cart_page(self):
        for xpath in OZON.cart_clear_buttons:
            if self.cart.xpath(xpath):
                return
        self.fail("кнопка удаления в корзине не найдена")

    def test_select_all_found_on_cart_page(self):
        for xpath in OZON.select_all:
            if self.cart.xpath(xpath):
                return
        self.fail("чекбокс «Выбрать все» не найден")

    def test_clear_button_is_not_the_share_button(self):
        # Перепутать их — значит удалить корзину вместо получения ссылки.
        share = {id(e) for x in OZON.share_buttons for e in self.cart.xpath(x)}
        clear = {id(e) for x in OZON.cart_clear_buttons for e in self.cart.xpath(x)}
        self.assertFalse(share & clear, "селекторы пересекаются")


class FindShareConfirmTest(unittest.TestCase):
    def test_skips_the_button_already_clicked(self):
        # Иконка в шапке подходит под тот же селектор. Нажать её повторно —
        # значит закрыть окно, так и не создав ссылку.
        icon = FakeElement("иконка")
        confirm = FakeElement("подтверждение")
        driver = FakeDriver({OZON.share_confirm[0]: [icon, confirm]})
        found, _ = find_share_confirm(driver, OZON, icon, 0.0)
        self.assertIs(found, confirm)

    def test_returns_nothing_when_modal_absent(self):
        found, xpath = find_share_confirm(FakeDriver({}), OZON, None, 0.0)
        self.assertIsNone(found)
        self.assertEqual(xpath, "")

    def test_both_markets_have_confirm_candidates(self):
        for market in (OZON, WB):
            self.assertTrue(market.share_confirm)


class ClearCartSettingTest(unittest.TestCase):
    def test_clearing_is_on_by_default(self):
        self.assertTrue(Settings().clear_cart_after)


if __name__ == "__main__":
    unittest.main()
