import unittest

from ozon_cart.cart import ShareResult, _extract_url
from ozon_cart.config import CART_URL
from ozon_cart.runner import CartResult


class ExtractUrlTest(unittest.TestCase):
    def test_plain_share_url(self):
        self.assertEqual(
            _extract_url("https://www.ozon.ru/cart/share/abc123"),
            "https://www.ozon.ru/cart/share/abc123",
        )

    def test_url_inside_toast_text(self):
        text = "Ссылка скопирована: https://ozon.ru/t/AbCdEf ,поделитесь ею"
        self.assertEqual(_extract_url(text), "https://ozon.ru/t/AbCdEf")

    def test_url_with_query(self):
        text = "https://www.ozon.ru/cart?share=xyz&utm_source=cart"
        self.assertEqual(_extract_url(text), text)

    def test_ignores_foreign_host(self):
        self.assertIsNone(_extract_url("https://example.com/cart/share/abc"))

    def test_no_url(self):
        self.assertIsNone(_extract_url("Ссылка скопирована"))
        self.assertIsNone(_extract_url(""))


class ShareResultTest(unittest.TestCase):
    def test_fallback_is_not_shared(self):
        self.assertFalse(ShareResult(CART_URL, "fallback", "нет кнопки").is_shared)

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
        cart.apply_share(ShareResult(CART_URL, "fallback", "Кнопка не найдена"))
        self.assertFalse(cart.has_share_link)
        self.assertEqual(cart.share_note, "Кнопка не найдена")

    def test_default_is_not_share_link(self):
        self.assertFalse(CartResult(thread_id=3).has_share_link)


if __name__ == "__main__":
    unittest.main()
