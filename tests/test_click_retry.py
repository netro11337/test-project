import unittest

from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.common.by import By

from cart_bot.config import Settings
from cart_bot.markets import OZON
from cart_bot.worker import Outcome, add_sku


class FakeButton:
    def __init__(self, driver):
        self.driver = driver
        self.text = "В корзину"

    def is_displayed(self):
        return True

    def is_enabled(self):
        return True

    def click(self):
        self.driver.clicks += 1


class ScriptedDriver:
    """Карточка товара, где кнопка начинает работать не с первого клика.

    Так ведёт себя настоящая страница: кнопка отрисована, но обработчик к ней
    ещё не привязан, и ранние клики уходят впустую.
    """

    def __init__(self, clicks_needed=3):
        self.clicks_needed = clicks_needed
        self.clicks = 0
        self.title = "Инструкция к магнитоле — купить"
        self.button = FakeButton(self)
        self.visited = []

    @property
    def in_cart(self):
        return self.clicks >= self.clicks_needed

    def get(self, url):
        self.visited.append(url)

    def execute_script(self, *args):
        return None

    def find_elements(self, by, selector):
        if by == By.XPATH:
            if selector == OZON.in_cart_marker:
                return [object()] if self.in_cart else []
            if selector in OZON.add_buttons:
                return [] if self.in_cart else [self.button]
            return []
        return [object()]

    def find_element(self, by, selector):
        found = self.find_elements(by, selector)
        if not found:
            raise NoSuchElementException(selector)
        return found[0]


def settings(**kwargs):
    base = dict(settle_delay=0.0, element_timeout=0.3, micro_pause=0.0, retries=0)
    base.update(kwargs)
    return Settings(**base)


class ClickRetryTest(unittest.TestCase):
    def test_button_that_works_on_the_third_click(self):
        driver = ScriptedDriver(clicks_needed=3)
        result = add_sku(driver, "5370004935", settings(click_attempts=3))
        self.assertIs(result.outcome, Outcome.ADDED)
        self.assertEqual(driver.clicks, 3)
        self.assertIn("с попытки 3", result.message)

    def test_single_click_is_not_enough(self):
        # Ровно то, что происходило раньше: один клик, и товар не добавлен.
        driver = ScriptedDriver(clicks_needed=3)
        result = add_sku(driver, "5370004935", settings(click_attempts=1))
        self.assertIs(result.outcome, Outcome.ERROR)
        self.assertEqual(driver.clicks, 1)

    def test_stops_as_soon_as_it_worked(self):
        # Лишние клики после успеха добавили бы второй экземпляр товара.
        driver = ScriptedDriver(clicks_needed=1)
        result = add_sku(driver, "5370004935", settings(click_attempts=3))
        self.assertIs(result.outcome, Outcome.ADDED)
        self.assertEqual(driver.clicks, 1)
        self.assertNotIn("попытки", result.message)

    def test_opens_the_product_url(self):
        driver = ScriptedDriver(clicks_needed=1)
        add_sku(driver, "123456789", settings(click_attempts=2))
        self.assertEqual(driver.visited, ["https://www.ozon.ru/product/123456789/"])

    def test_already_in_cart_is_not_clicked_again(self):
        driver = ScriptedDriver(clicks_needed=0)
        result = add_sku(driver, "5370004935", settings(click_attempts=3))
        self.assertIs(result.outcome, Outcome.ALREADY)
        self.assertEqual(driver.clicks, 0)


class SettingsDefaultsTest(unittest.TestCase):
    def test_defaults_match_observed_behaviour(self):
        cfg = Settings()
        self.assertGreaterEqual(cfg.settle_delay, 2.0)
        self.assertGreaterEqual(cfg.click_attempts, 3)


if __name__ == "__main__":
    unittest.main()
