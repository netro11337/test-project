import unittest

import cart_bot.runner as runner_module
from cart_bot.cart import _confirm_clear, _count_from_text, count_items
from cart_bot.config import Settings
from cart_bot.markets import OZON, WB
from cart_bot.runner import CartResult, CartRunner
from cart_bot.worker import Outcome, SkuResult


class FakeElement:
    def __init__(self, text="", name=""):
        self.text = text
        self.name = name
        self.clicked = False

    def is_displayed(self):
        return True

    def click(self):
        self.clicked = True


class FakeDriver:
    def __init__(self, css=None, xpath=None):
        self.css = css or {}
        self.xpath = xpath or {}

    def find_elements(self, by, selector):
        table = self.xpath if selector.startswith("//") else self.css
        return table.get(selector, [])

    def execute_script(self, *args):
        return None


class CountFromTextTest(unittest.TestCase):
    """Запасной счёт по подписи «N товаров»."""

    def test_reads_the_count_from_the_caption(self):
        driver = FakeDriver(xpath={OZON.cart_count_text[0]: [FakeElement("1 товар • 400 гр")]})
        self.assertEqual(_count_from_text(driver, OZON), 1)

    def test_reads_plural_form(self):
        driver = FakeDriver(xpath={OZON.cart_count_text[0]: [FakeElement("3 товара")]})
        self.assertEqual(_count_from_text(driver, OZON), 3)

    def test_no_caption_is_unknown(self):
        self.assertEqual(_count_from_text(FakeDriver(), OZON), -1)

    def test_used_when_item_markup_is_unknown(self):
        # Разметку списка магазин переписывает чаще, чем подпись.
        driver = FakeDriver(xpath={OZON.cart_count_text[0]: [FakeElement("2 товара")]})
        self.assertEqual(count_items(driver, OZON), 2)

    def test_item_markup_wins_when_present(self):
        driver = FakeDriver(
            css={OZON.cart_item: [FakeElement(), FakeElement(), FakeElement()]},
            xpath={OZON.cart_count_text[0]: [FakeElement("1 товар")]},
        )
        self.assertEqual(count_items(driver, OZON), 3)


class ConfirmClearTest(unittest.TestCase):
    """Окно «Удалить товары» надо подтвердить, иначе корзина останется полной."""

    def setUp(self):
        self.cfg = Settings(element_timeout=0.2)

    def test_confirm_button_is_clicked(self):
        button = FakeElement("Удалить")
        driver = FakeDriver(xpath={OZON.cart_clear_confirm[0]: [button]})
        self.assertTrue(_confirm_clear(driver, self.cfg, OZON))
        self.assertTrue(button.clicked)

    def test_exact_wording_is_tried_first(self):
        self.assertEqual(
            OZON.cart_clear_confirm[0], "//button[normalize-space()='Удалить']"
        )

    def test_no_dialog_is_not_an_error(self):
        self.assertFalse(_confirm_clear(FakeDriver(), self.cfg, OZON))

    def test_both_markets_have_confirm_selectors(self):
        for market in (OZON, WB):
            self.assertTrue(market.cart_clear_confirm)


class VerifyTriggerTest(unittest.TestCase):
    """Проверочный круг — только когда товаров реально меньше, чем SKU."""

    def setUp(self):
        self.saved = (
            runner_module.open_cart,
            runner_module.count_items,
            runner_module.add_sku_with_retry,
        )
        runner_module.open_cart = lambda *a, **k: True

    def tearDown(self):
        (
            runner_module.open_cart,
            runner_module.count_items,
            runner_module.add_sku_with_retry,
        ) = self.saved

    def _verify_with(self, in_cart):
        runner_module.count_items = lambda *a, **k: in_cart
        calls = []
        runner_module.add_sku_with_retry = lambda d, sku, cfg: (
            calls.append(sku) or SkuResult(sku, Outcome.ALREADY, "")
        )
        events = []
        runner = CartRunner(Settings(verify_cart=True), [], events.append)
        runner._verify(None, 1, ["1" * 9, "2" * 9, "3" * 9], CartResult(thread_id=1))
        return calls, events

    def test_runs_when_items_are_missing(self):
        calls, _ = self._verify_with(in_cart=2)
        self.assertEqual(len(calls), 3)

    def test_skipped_when_cart_is_full(self):
        calls, _ = self._verify_with(in_cart=3)
        self.assertEqual(calls, [])

    def test_skipped_when_count_is_unknown(self):
        # Это и был баг: -1 меньше любого числа, поэтому второй круг шёл всегда.
        calls, events = self._verify_with(in_cart=-1)
        self.assertEqual(calls, [], "проверка пошла при неизвестном количестве")
        self.assertTrue(
            any("не смог пересчитать" in e.message for e in events),
            "пользователю не сказали, почему проверки не было",
        )

    def test_runs_when_cart_is_empty(self):
        calls, _ = self._verify_with(in_cart=0)
        self.assertEqual(len(calls), 3)


if __name__ == "__main__":
    unittest.main()
