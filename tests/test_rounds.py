import unittest

import cart_bot.runner as runner_module
from cart_bot.config import Settings
from cart_bot.runner import CartResult, CartRunner


class RoundsTest(unittest.TestCase):
    """В браузере пользователя вкладки идут кругами, одна за другой."""

    def setUp(self):
        self.collected = []
        self._saved = (
            runner_module.create_driver,
            runner_module.quit_driver,
            runner_module.warm_up,
        )
        runner_module.create_driver = lambda *a, **k: object()
        runner_module.quit_driver = lambda *a, **k: None
        runner_module.warm_up = lambda *a, **k: True

    def tearDown(self):
        (
            runner_module.create_driver,
            runner_module.quit_driver,
            runner_module.warm_up,
        ) = self._saved

    def _runner(self, batches, **overrides):
        cfg = Settings(attach_to_chrome=True, **overrides)
        events = []
        runner = CartRunner(cfg, batches, events.append)

        def fake_collect(driver, thread_id, skus):
            self.collected.append((thread_id, list(skus)))
            return CartResult(thread_id=thread_id, total=len(skus), added=len(skus))

        runner._collect = fake_collect
        return runner, events

    def test_each_tab_becomes_its_own_round(self):
        runner, _ = self._runner([["111111111"], ["222222222"], ["333333333"]])
        carts = runner.run()
        self.assertEqual([tid for tid, _ in self.collected], [1, 2, 3])
        self.assertEqual(len(carts), 3, "у каждого круга своя корзина и ссылка")

    def test_tabs_are_not_merged(self):
        # Раньше вкладки сливались в один список и давали одну ссылку.
        runner, _ = self._runner([["111111111", "222222222"], ["333333333"]])
        runner.run()
        self.assertEqual(
            self.collected,
            [(1, ["111111111", "222222222"]), (2, ["333333333"])],
        )

    def test_empty_tabs_are_skipped(self):
        runner, _ = self._runner([["111111111"], [], ["333333333"]])
        runner.run()
        self.assertEqual([tid for tid, _ in self.collected], [1, 3])

    def test_warns_when_clearing_is_off_for_several_rounds(self):
        # Без очистки второй круг унаследует товары первого, и ссылка соврёт.
        runner, events = self._runner(
            [["111111111"], ["222222222"]], clear_cart_after=False
        )
        runner.run()
        self.assertTrue(
            any("очистка корзины выключена" in e.message for e in events),
            "пользователя не предупредили",
        )

    def test_no_warning_for_a_single_round(self):
        runner, events = self._runner([["111111111"]], clear_cart_after=False)
        runner.run()
        self.assertFalse(any("очистка корзины выключена" in e.message for e in events))

    def test_cancel_stops_between_rounds(self):
        runner, _ = self._runner([["1" * 9], ["2" * 9], ["3" * 9]])
        original = runner._collect

        def collect_then_cancel(driver, thread_id, skus):
            result = original(driver, thread_id, skus)
            runner.cancel()
            return result

        runner._collect = collect_then_cancel
        runner.run()
        self.assertEqual(len(self.collected), 1, "отмена не остановила круги")


if __name__ == "__main__":
    unittest.main()
