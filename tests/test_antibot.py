import unittest

from cart_bot.markets import OZON, WB
from cart_bot.worker import is_blocked


class FakeDriver:
    """Минимальная заглушка: заголовок вкладки и наличие текста на странице."""

    def __init__(self, title="", matches_antibot=False):
        self.title = title
        self._matches = matches_antibot

    def find_elements(self, by, xpath):
        return [object()] if self._matches else []


class IsBlockedTest(unittest.TestCase):
    def test_detects_ozon_antibot_page_by_tab_title(self):
        # Реальный случай: вкладка «Antibot Captcha», а в теле страницы только
        # «Ой, что-то пошло не так» — под старые тексты это не подпадало, и
        # программа сообщала «Кнопка добавления не появилась».
        driver = FakeDriver(title="Antibot Captcha")
        self.assertTrue(is_blocked(driver, OZON))

    def test_title_check_is_case_insensitive(self):
        self.assertTrue(is_blocked(FakeDriver(title="ANTIBOT CAPTCHA"), OZON))
        self.assertTrue(is_blocked(FakeDriver(title="Доступ ограничен"), WB))

    def test_detects_by_page_text_when_title_is_clean(self):
        driver = FakeDriver(title="Ozon", matches_antibot=True)
        self.assertTrue(is_blocked(driver, OZON))

    def test_normal_product_page_is_not_blocked(self):
        driver = FakeDriver(title="Наушники — купить на OZON", matches_antibot=False)
        self.assertFalse(is_blocked(driver, OZON))

    def test_empty_title_is_not_blocked(self):
        self.assertFalse(is_blocked(FakeDriver(title=""), OZON))

    def test_both_markets_carry_title_markers(self):
        for market in (OZON, WB):
            self.assertIn("antibot", market.antibot_titles)
            self.assertIn("captcha", market.antibot_titles)


if __name__ == "__main__":
    unittest.main()
