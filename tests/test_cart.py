import unittest

from cart_bot.cart import ShareResult, _extract_url, find_share_button
from cart_bot.config import Settings
from cart_bot.markets import OZON, WB, get_market
from cart_bot.runner import CartResult


class FakeElement:
    def __init__(self, displayed: bool = True):
        self._displayed = displayed

    def is_displayed(self) -> bool:
        return self._displayed


class FakeDriver:
    """Отдаёт заранее заданные элементы на заданные XPath."""

    def __init__(self, matches):
        self.matches = matches

    def find_elements(self, by, xpath):
        return self.matches.get(xpath, [])


class ExtractUrlTest(unittest.TestCase):
    def test_plain_ozon_share_url(self):
        self.assertEqual(
            _extract_url("https://www.ozon.ru/cart/share/abc123", OZON),
            "https://www.ozon.ru/cart/share/abc123",
        )

    def test_short_ozon_url_without_www(self):
        text = "Ссылка скопирована: https://ozon.ru/t/AbCdEf ,поделитесь ею"
        self.assertEqual(_extract_url(text, OZON), "https://ozon.ru/t/AbCdEf")

    def test_wb_share_url(self):
        text = "Скопировано: https://www.wildberries.ru/lk/basket/shared/xyz789."
        self.assertEqual(
            _extract_url(text, WB),
            "https://www.wildberries.ru/lk/basket/shared/xyz789",
        )

    def test_url_with_query(self):
        text = "https://www.ozon.ru/cart?share=xyz&utm_source=cart"
        self.assertEqual(_extract_url(text, OZON), text)

    def test_market_isolation(self):
        # Ссылку WB не принимаем за ссылку Ozon и наоборот: иначе поток отдал бы
        # ссылку не того магазина.
        wb_link = "https://www.wildberries.ru/lk/basket/shared/x"
        self.assertIsNone(_extract_url(wb_link, OZON))
        self.assertIsNone(_extract_url("https://www.ozon.ru/t/x", WB))

    def test_ignores_foreign_host(self):
        self.assertIsNone(_extract_url("https://example.com/cart/share/abc", OZON))

    def test_no_url(self):
        self.assertIsNone(_extract_url("Ссылка скопирована", OZON))
        self.assertIsNone(_extract_url("", WB))


class ShareResultTest(unittest.TestCase):
    def test_fallback_is_not_shared(self):
        self.assertFalse(ShareResult(OZON.cart_url, "fallback", "нет кнопки").is_shared)

    def test_real_methods_are_shared(self):
        for method in ("input", "anchor", "text", "clipboard"):
            self.assertTrue(ShareResult("https://ozon.ru/t/x", method).is_shared)


class CartResultShareTest(unittest.TestCase):
    def test_apply_share_link(self):
        cart = CartResult(thread_id=1)
        cart.apply_share(ShareResult("https://ozon.ru/t/abc", "clipboard"))
        self.assertEqual(cart.url, "https://ozon.ru/t/abc")
        self.assertTrue(cart.has_share_link)

    def test_apply_fallback_keeps_note(self):
        cart = CartResult(thread_id=2)
        cart.apply_share(ShareResult(WB.cart_url, "fallback", "Кнопка не найдена"))
        self.assertFalse(cart.has_share_link)
        self.assertEqual(cart.share_note, "Кнопка не найдена")

    def test_default_is_not_share_link(self):
        self.assertFalse(CartResult(thread_id=3).has_share_link)


class FindShareButtonTest(unittest.TestCase):
    """Кнопка на WB — иконка без текста, поэтому селекторы перебираются."""

    def setUp(self):
        self.cfg = Settings(market_key="wb", element_timeout=0.0)

    def test_falls_through_to_a_later_selector(self):
        # Первые варианты (aria-label, title) не сработали, спасает иконка SVG.
        svg_selector = WB.share_buttons[6]
        driver = FakeDriver({svg_selector: [FakeElement()]})
        button, selector, count = find_share_button(driver, self.cfg, WB)
        self.assertIsNotNone(button)
        self.assertEqual(selector, svg_selector)
        self.assertEqual(count, 1)

    def test_earlier_selector_wins(self):
        driver = FakeDriver(
            {
                WB.share_buttons[0]: [FakeElement()],
                WB.share_buttons[4]: [FakeElement()],
            }
        )
        _, selector, _ = find_share_button(driver, self.cfg, WB)
        self.assertEqual(selector, WB.share_buttons[0])

    def test_invisible_buttons_are_skipped(self):
        # Скрытая кнопка в свёрнутом меню кликаться не будет.
        driver = FakeDriver(
            {
                WB.share_buttons[0]: [FakeElement(displayed=False)],
                WB.share_buttons[1]: [FakeElement()],
            }
        )
        _, selector, _ = find_share_button(driver, self.cfg, WB)
        self.assertEqual(selector, WB.share_buttons[1])

    def test_reports_several_stores_in_cart(self):
        # Несколько кнопок = несколько магазинов, ссылка охватит не всё.
        driver = FakeDriver(
            {WB.share_buttons[0]: [FakeElement(), FakeElement(), FakeElement()]}
        )
        _, _, count = find_share_button(driver, self.cfg, WB)
        self.assertEqual(count, 3)

    def test_returns_nothing_when_no_selector_matches(self):
        button, selector, count = find_share_button(FakeDriver({}), self.cfg, WB)
        self.assertIsNone(button)
        self.assertEqual(selector, "")
        self.assertEqual(count, 0)


class MarketSettingsTest(unittest.TestCase):
    def test_product_url_templates(self):
        self.assertEqual(
            OZON.product_url.format(sku="123456789"),
            "https://www.ozon.ru/product/123456789/",
        )
        self.assertEqual(
            WB.product_url.format(sku="123456789"),
            "https://www.wildberries.ru/catalog/123456789/detail.aspx",
        )

    def test_profiles_are_separated_per_market(self):
        # Общий профиль означал бы одну сессию Chrome на два магазина.
        ozon_profile = Settings(market_key="ozon").profile_for(1)
        wb_profile = Settings(market_key="wb").profile_for(1)
        self.assertNotEqual(ozon_profile, wb_profile)
        self.assertEqual(ozon_profile.name, wb_profile.name)

    def test_unknown_market_rejected(self):
        with self.assertRaises(ValueError):
            get_market("aliexpress")

    def test_wb_share_selectors_are_not_text_based(self):
        # Кнопка на WB — иконка без подписи, поэтому первым идёт поиск по
        # aria-label, а не по тексту.
        self.assertIn("aria-label", WB.share_buttons[0])


if __name__ == "__main__":
    unittest.main()
