import unittest

from selenium.common.exceptions import StaleElementReferenceException

from cart_bot.config import Settings
from cart_bot.markets import OZON, WB
from cart_bot.cart import count_items
from cart_bot.worker import _confirm_added, _looks_added


class FakeElement:
    def __init__(self, text=""):
        self.text = text


class FakeDriver:
    """Драйвер, у которого маркер «в корзине» либо есть, либо нет."""

    def __init__(self, has_marker=False, css_matches=None):
        self.has_marker = has_marker
        self.css_matches = css_matches or {}

    def find_elements(self, by, selector):
        if str(by).lower().startswith("xpath") or selector.startswith("//"):
            return [FakeElement()] if self.has_marker else []
        return self.css_matches.get(selector, [])


class ConfirmAddedTest(unittest.TestCase):
    """Ложный успех хуже честной ошибки: человек решит, что корзина собрана."""

    def setUp(self):
        self.cfg = Settings(element_timeout=0.2)

    def test_marker_is_proof(self):
        evidence = _confirm_added(
            FakeDriver(has_marker=True), self.cfg, OZON, FakeElement("В корзину"), "В корзину"
        )
        self.assertIsNotNone(evidence)
        self.assertIn("маркер", evidence)

    def test_meaningful_caption_change_is_proof(self):
        button = FakeElement("В корзине")
        evidence = _confirm_added(
            FakeDriver(has_marker=False), self.cfg, OZON, button, "В корзину"
        )
        self.assertIsNotNone(evidence)
        self.assertIn("В корзине", evidence)

    def test_nothing_changed_is_not_success(self):
        button = FakeElement("В корзину")
        self.assertIsNone(
            _confirm_added(
                FakeDriver(has_marker=False), self.cfg, OZON, button, "В корзину"
            )
        )

    def test_unrelated_caption_change_is_not_success(self):
        # Страница перерисовалась, надпись поменялась, но про корзину в ней
        # ничего нет — засчитывать такое нельзя.
        button = FakeElement("Доставим 19 августа")
        self.assertIsNone(
            _confirm_added(
                FakeDriver(has_marker=False), self.cfg, OZON, button, "В корзину"
            )
        )

    def test_redrawn_button_is_not_success(self):
        # Раньше любая ошибка браузера засчитывалась успехом — отсюда и брался
        # отчёт «добавлен» при пустой корзине. Перерисовка страницы происходит
        # и без добавления, доказательством она не является.
        class Stale:
            @property
            def text(self):
                raise StaleElementReferenceException("элемент перерисован")

        self.assertIsNone(
            _confirm_added(
                FakeDriver(has_marker=False), self.cfg, OZON, Stale(), "В корзину"
            )
        )


class LooksAddedTest(unittest.TestCase):
    def test_cart_captions(self):
        for text in ("В корзине", "1 товар", "Перейти в корзину"):
            self.assertTrue(_looks_added(text))

    def test_other_captions(self):
        for text in ("В корзину", "Доставим 19 августа", "Купить сейчас"):
            self.assertFalse(_looks_added(text))


class CountItemsTest(unittest.TestCase):
    """«Пусто» и «не смог посчитать» — разные вещи."""

    def test_explicit_empty_cart_is_zero(self):
        driver = FakeDriver(css_matches={OZON.cart_empty: [FakeElement()]})
        self.assertEqual(count_items(driver, OZON), 0)

    def test_unknown_markup_is_minus_one(self):
        self.assertEqual(count_items(FakeDriver(), OZON), -1)

    def test_items_are_counted(self):
        driver = FakeDriver(
            css_matches={OZON.cart_item: [FakeElement(), FakeElement()]}
        )
        self.assertEqual(count_items(driver, OZON), 2)

    def test_both_markets_declare_empty_selector(self):
        for market in (OZON, WB):
            self.assertTrue(market.cart_empty, f"{market.key}: нет признака пустоты")


if __name__ == "__main__":
    unittest.main()
