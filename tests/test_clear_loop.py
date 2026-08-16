import unittest

from cart_bot.cart import _looks_checked, clear_cart
from cart_bot.config import Settings
from cart_bot.markets import WB


class FakeCheckbox:
    def __init__(self, selected=False, attributes=None):
        self.selected = selected
        self.attributes = attributes or {}
        self.clicks = 0

    def is_displayed(self):
        return True

    def is_selected(self):
        return self.selected

    def get_attribute(self, name):
        return self.attributes.get(name)


class FakeButton:
    def __init__(self, driver, removes=1):
        self.driver = driver
        self.removes = removes

    def is_displayed(self):
        return True

    def click(self):
        self.driver.items = max(0, self.driver.items - self.removes)
        self.driver.clicks += 1


class ClearDriver:
    """Корзина, у которой кнопка удаляет за раз ограниченное число позиций."""

    def __init__(self, items, removes=1, checkbox=None):
        self.items = items
        self.clicks = 0
        self.removes = removes
        self.checkbox = checkbox or FakeCheckbox(selected=True)
        self.button = FakeButton(self, removes)
        # Страница корзины уже открыта — open_cart на неё не переходит.
        self.current_url = WB.cart_url

    def find_element(self, by, selector):
        found = self.find_elements(by, selector)
        if not found:
            raise LookupError(selector)
        return found[0]

    def find_elements(self, by, selector):
        if selector == WB.cart_ready:
            return [object()]  # страница корзины загружена
        if selector in WB.select_all:
            return [self.checkbox]
        if selector == WB.cart_empty:
            return [object()] if self.items == 0 else []
        if selector == WB.cart_item:
            return [object()] * self.items
        if selector in WB.cart_clear_buttons:
            return [self.button]
        return []

    def execute_script(self, script, *args):
        return None


def settings():
    return Settings(market_key="wb", element_timeout=0.2, micro_pause=0.0)


class ClearLoopTest(unittest.TestCase):
    """Удаление повторяется, пока корзина не опустеет."""

    def test_button_removing_one_at_a_time_still_empties_the_cart(self):
        # Ровно наблюдавшийся случай: за проход уходит не всё.
        driver = ClearDriver(items=3, removes=1)
        ok, why = clear_cart(driver, settings())
        self.assertTrue(ok, why)
        self.assertEqual(driver.items, 0)
        self.assertEqual(driver.clicks, 3)

    def test_single_click_cart_is_cleared_in_one_pass(self):
        driver = ClearDriver(items=3, removes=3)
        ok, why = clear_cart(driver, settings())
        self.assertTrue(ok, why)
        self.assertEqual(driver.clicks, 1)

    def test_button_that_does_nothing_stops_instead_of_looping(self):
        driver = ClearDriver(items=3, removes=0)
        ok, why = clear_cart(driver, settings())
        self.assertFalse(ok)
        self.assertIn("ничего не удалил", why)
        self.assertLessEqual(driver.clicks, 2, "зациклилось на бесполезной кнопке")

    def test_empty_cart_needs_no_clicks(self):
        driver = ClearDriver(items=0)
        ok, why = clear_cart(driver, settings())
        self.assertTrue(ok)
        self.assertEqual(driver.clicks, 0)


class SelectAllStateTest(unittest.TestCase):
    """Клик по уже отмеченному «Все» снял бы выделение — так делать нельзя."""

    def test_plain_checkbox_state(self):
        self.assertTrue(_looks_checked(FakeCheckbox(selected=True)))
        self.assertFalse(_looks_checked(FakeCheckbox(selected=False)))

    def test_drawn_widget_reports_through_aria(self):
        widget = FakeCheckbox(selected=False, attributes={"aria-checked": "true"})
        self.assertTrue(_looks_checked(widget))

    def test_checked_attribute(self):
        widget = FakeCheckbox(selected=False, attributes={"checked": "checked"})
        self.assertTrue(_looks_checked(widget))

    def test_already_checked_box_is_left_alone(self):
        checkbox = FakeCheckbox(selected=False, attributes={"aria-checked": "true"})
        driver = ClearDriver(items=2, removes=2, checkbox=checkbox)
        clear_cart(driver, settings())
        self.assertEqual(checkbox.clicks, 0, "выделение сняли вместо удаления")


if __name__ == "__main__":
    unittest.main()
