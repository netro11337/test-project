import unittest

from cart_bot.config import Settings
from cart_bot.markets import OZON, WB
from cart_bot.worker import find_add_button

try:
    from lxml import etree

    HAS_LXML = True
except ImportError:  # pragma: no cover
    HAS_LXML = False


# Разметка карточки Ozon по скриншоту: кнопка «В корзину» с подписью о
# доставке, рядом «Купить сейчас» и ссылка «Перейти в корзину».
OZON_PAGE = """
<html><body>
  <div data-widget="webProductHeading"><h1>Инструкция к магнитоле</h1></div>
  <div data-widget="webAddToCart">
    <button><span>В корзину</span><span>Доставим 19 августа</span></button>
    <button aria-label="Отложить"></button>
  </div>
  <div data-widget="webOneClickButton"><button>Купить сейчас</button></div>
  <a href="/cart">Перейти в корзину</a>
</body></html>
"""


class FakeElement:
    def __init__(self, name, displayed=True, enabled=True):
        self.name = name
        self._displayed = displayed
        self._enabled = enabled

    def is_displayed(self):
        return self._displayed

    def is_enabled(self):
        return self._enabled


class FakeDriver:
    def __init__(self, matches):
        self.matches = matches

    def find_elements(self, by, xpath):
        return self.matches.get(xpath, [])


@unittest.skipUnless(HAS_LXML, "нужен lxml для разбора разметки")
class OzonMarkupTest(unittest.TestCase):
    def setUp(self):
        self.doc = etree.fromstring(OZON_PAGE)

    def _first_match(self):
        for xpath in OZON.add_buttons:
            found = self.doc.xpath(xpath)
            if found:
                return xpath, found
        return None, []

    def test_finds_the_add_to_cart_button(self):
        xpath, found = self._first_match()
        self.assertIsNotNone(xpath, "ни один селектор не нашёл кнопку")
        self.assertIn("В корзину", "".join(found[0].itertext()))

    def test_buy_now_is_never_matched(self):
        # «Купить сейчас» ведёт прямо в оформление заказа — нажать её нельзя.
        for xpath in OZON.add_buttons:
            for element in self.doc.xpath(xpath):
                self.assertNotIn("Купить сейчас", "".join(element.itertext()))

    def test_go_to_cart_link_is_not_matched(self):
        for xpath in OZON.add_buttons:
            for element in self.doc.xpath(xpath):
                self.assertNotIn("Перейти в корзину", "".join(element.itertext()))

    def test_already_in_cart_marker_does_not_fire_on_fresh_page(self):
        # На неоткрытом товаре маркер «уже в корзине» срабатывать не должен,
        # иначе товар будет пропущен как якобы добавленный.
        self.assertEqual(self.doc.xpath(OZON.in_cart_marker), [])


class SelectorSanityTest(unittest.TestCase):
    def test_no_market_targets_buy_now(self):
        for market in (OZON, WB):
            for xpath in market.add_buttons:
                self.assertNotIn(
                    "Купить сейчас",
                    xpath,
                    f"{market.key}: селектор может нажать «Купить сейчас»",
                )

    def test_generic_cart_selector_excludes_navigation(self):
        generic = [x for x in OZON.add_buttons if "не" not in x and "Перейти" in x]
        for xpath in generic:
            self.assertIn("not(", xpath)


class FindAddButtonTest(unittest.TestCase):
    def setUp(self):
        self.cfg = Settings(element_timeout=0.0)

    def test_earlier_candidate_wins(self):
        driver = FakeDriver(
            {
                OZON.add_buttons[0]: [FakeElement("widget")],
                OZON.add_buttons[1]: [FakeElement("generic")],
            }
        )
        button, xpath = find_add_button(driver, self.cfg, OZON)
        self.assertEqual(button.name, "widget")
        self.assertEqual(xpath, OZON.add_buttons[0])

    def test_falls_through_when_markup_changed(self):
        driver = FakeDriver({OZON.add_buttons[2]: [FakeElement("fallback")]})
        button, xpath = find_add_button(driver, self.cfg, OZON)
        self.assertEqual(button.name, "fallback")
        self.assertEqual(xpath, OZON.add_buttons[2])

    def test_hidden_and_disabled_buttons_are_skipped(self):
        driver = FakeDriver(
            {
                OZON.add_buttons[0]: [
                    FakeElement("hidden", displayed=False),
                    FakeElement("disabled", enabled=False),
                    FakeElement("good"),
                ]
            }
        )
        button, _ = find_add_button(driver, self.cfg, OZON)
        self.assertEqual(button.name, "good")

    def test_returns_nothing_when_no_candidate_matches(self):
        button, xpath = find_add_button(FakeDriver({}), self.cfg, OZON)
        self.assertIsNone(button)
        self.assertEqual(xpath, "")


if __name__ == "__main__":
    unittest.main()
