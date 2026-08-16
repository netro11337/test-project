import unittest

import cart_bot.runner as runner_module
from cart_bot.cart import find_clear_button
from cart_bot.config import Settings
from cart_bot.markets import OZON, WB
from cart_bot.runner import CartResult, CartRunner
from cart_bot.worker import Outcome, SkuResult

try:
    from lxml import etree

    HAS_LXML = True
except ImportError:  # pragma: no cover
    HAS_LXML = False


# Окно «Поделиться товарами» на Wildberries: кнопка подписана иначе, чем на
# Ozon, — «Скопировать ссылку на товары».
WB_SHARE_MODAL = """
<html><body>
  <div role="dialog">
    <h2>Поделиться товарами</h2>
    <div>Лазерный уровень строительный 4D 360</div>
    <div>Рюкзак школьный тканевый для спорта</div>
    <button>Скопировать ссылку на товары</button>
  </div>
</body></html>
"""


class FakeElement:
    def __init__(self, name):
        self.name = name

    def is_displayed(self):
        return True


class FakeDriver:
    """Кнопку удаления отдаёт только скрипт поиска соседа."""

    def __init__(self, xpath_matches=None, neighbour=None):
        self.xpath_matches = xpath_matches or {}
        self.neighbour = neighbour
        self.scripts = []

    def find_elements(self, by, selector):
        return self.xpath_matches.get(selector, [])

    def execute_script(self, script, *args):
        self.scripts.append((script, args))
        return self.neighbour


@unittest.skipUnless(HAS_LXML, "нужен lxml для разбора разметки")
class WildberriesShareTest(unittest.TestCase):
    def test_copy_link_button_is_found(self):
        # Общий селектор искал слово «Поделиться» — на WB кнопка называется
        # «Скопировать ссылку на товары», и ссылка не копировалась.
        modal = etree.fromstring(WB_SHARE_MODAL)
        for xpath in WB.share_confirm:
            found = modal.xpath(xpath)
            if found:
                self.assertIn("Скопировать ссылку", "".join(found[0].itertext()))
                return
        self.fail("кнопка «Скопировать ссылку на товары» не найдена")

    def test_ozon_confirm_still_matches_its_own_wording(self):
        self.assertTrue(any("оделиться" in x for x in OZON.share_confirm))


class ClearButtonSideTest(unittest.TestCase):
    """Кнопка удаления — иконка без подписи, ищем её по соседству."""

    def setUp(self):
        self.cfg = Settings(element_timeout=0.0)

    def test_sides_match_the_stores(self):
        # Ozon: [Поделиться] [корзина] — правее.
        # WB:   [сердце] [корзина] [поделиться] — левее.
        self.assertEqual(OZON.clear_side, "right")
        self.assertEqual(WB.clear_side, "left")

    def test_named_selector_wins_when_present(self):
        driver = FakeDriver({OZON.cart_clear_buttons[0]: [FakeElement("по подписи")]})
        button, how = find_clear_button(driver, self.cfg, OZON)
        self.assertEqual(button.name, "по подписи")
        self.assertEqual(how, OZON.cart_clear_buttons[0])
        self.assertFalse(driver.scripts, "поиск соседа не понадобился")

    def test_falls_back_to_the_neighbour_of_share(self):
        share = FakeElement("поделиться")
        trash = FakeElement("корзина")
        driver = FakeDriver({WB.share_buttons[0]: [share]}, neighbour=trash)
        button, how = find_clear_button(driver, self.cfg, WB)
        self.assertIs(button, trash)
        self.assertIn("left", how)
        self.assertEqual(driver.scripts[0][1][1], "left", "передана не та сторона")

    def test_nothing_found_without_share_button(self):
        button, how = find_clear_button(FakeDriver(), self.cfg, WB)
        self.assertIsNone(button)
        self.assertEqual(how, "")


class VerifyPassTest(unittest.TestCase):
    """После сборки товары перепроверяются и недостающие дожимаются."""

    def setUp(self):
        self.saved = (
            runner_module.open_cart,
            runner_module.count_items,
            runner_module.add_sku_with_retry,
        )

    def tearDown(self):
        (
            runner_module.open_cart,
            runner_module.count_items,
            runner_module.add_sku_with_retry,
        ) = self.saved

    def _run_verify(self, in_cart, outcomes, **overrides):
        runner_module.open_cart = lambda *a, **k: True
        runner_module.count_items = lambda *a, **k: in_cart
        calls = []

        def fake_add(driver, sku, cfg):
            calls.append(sku)
            return SkuResult(sku, outcomes.get(sku, Outcome.ALREADY), "")

        runner_module.add_sku_with_retry = fake_add

        options = {"verify_cart": True, **overrides}
        cfg = Settings(**options)
        events = []
        runner = CartRunner(cfg, [], events.append)
        cart = CartResult(thread_id=1, total=3, added=3)
        runner._verify(None, 1, ["1" * 9, "2" * 9, "3" * 9], cart)
        return cart, calls, events

    def test_missing_item_is_pushed_again(self):
        cart, calls, _ = self._run_verify(
            in_cart=2, outcomes={"2" * 9: Outcome.ADDED}
        )
        self.assertEqual(len(calls), 3, "перепроверены не все товары")
        self.assertEqual(cart.added, 3)
        self.assertEqual(cart.failed, 0)

    def test_full_cart_skips_the_second_pass(self):
        # Лишний проход по карточкам стоит времени — при полной корзине не нужен.
        _, calls, _ = self._run_verify(in_cart=3, outcomes={})
        self.assertEqual(calls, [])

    def test_item_that_cannot_be_added_is_counted_as_failed(self):
        cart, _, _ = self._run_verify(
            in_cart=2, outcomes={"2" * 9: Outcome.OUT_OF_STOCK}
        )
        self.assertEqual(cart.added, 2)
        self.assertEqual(cart.failed, 1)

    def test_verification_can_be_switched_off(self):
        _, calls, _ = self._run_verify(
            in_cart=0, outcomes={}, verify_cart=False
        )
        self.assertEqual(calls, [])


class ClickAttemptsTest(unittest.TestCase):
    def test_default_is_persistent_enough(self):
        self.assertGreaterEqual(Settings().click_attempts, 5)


if __name__ == "__main__":
    unittest.main()
