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
            runner_module.probe_debug_ports,
            runner_module.launch_user_browsers,
        )
        runner_module.create_driver = lambda *a, **k: object()
        runner_module.quit_driver = lambda *a, **k: None
        runner_module.warm_up = lambda *a, **k: True
        # По умолчанию считаем, что запущен один браузер пользователя.
        self.browsers = ["127.0.0.1:9222"]
        runner_module.probe_debug_ports = lambda cfg, wanted: list(self.browsers)
        # Программа сама открывает браузеры; в тесте считаем, что они уже есть.
        runner_module.launch_user_browsers = (
            lambda cfg, wanted, note=None: list(self.browsers)
        )

    def tearDown(self):
        (
            runner_module.create_driver,
            runner_module.quit_driver,
            runner_module.warm_up,
            runner_module.probe_debug_ports,
            runner_module.launch_user_browsers,
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
        # Браузер один, значит вкладки пойдут кругами в нём же.
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




class MultipleBrowsersTest(RoundsTest):
    """Несколько браузеров пользователя работают параллельно."""

    def test_each_browser_takes_its_own_tabs(self):
        self.browsers = ["127.0.0.1:9222", "127.0.0.1:9223"]
        runner, _ = self._runner([["1" * 9], ["2" * 9], ["3" * 9]])
        carts = runner.run()
        self.assertEqual(len(carts), 3)
        self.assertEqual(sorted(tid for tid, _ in self.collected), [1, 2, 3])

    def test_tabs_are_spread_across_browsers(self):
        # Три вкладки на два браузера: первый берёт 1 и 3, второй — 2.
        self.browsers = ["127.0.0.1:9222", "127.0.0.1:9223"]
        runner, events = self._runner([["1" * 9], ["2" * 9], ["3" * 9]])
        runner.run()
        spread = [e.message for e in events if "вкладки" in e.message]
        self.assertIn("Браузер 127.0.0.1:9222: вкладки 1, 3", spread)
        self.assertIn("Браузер 127.0.0.1:9223: вкладки 2", spread)

    def test_no_browser_could_be_opened_is_reported(self):
        # Chrome не нашёлся и поднять окна не вышло — молчать об этом нельзя.
        self.browsers = []
        runner, events = self._runner([["1" * 9]])
        carts = runner.run()
        self.assertEqual(carts, [])
        self.assertTrue(
            any("Не удалось открыть ни одного браузера" in e.message for e in events),
            [e.message for e in events],
        )



class BrowserCountTest(RoundsTest):
    """Число окон задаётся отдельно от числа потоков."""

    def _runner_with(self, batches, browsers_open, browser_count):
        self.browsers = browsers_open
        return self._runner(batches, browser_count=browser_count)

    def test_one_browser_runs_carts_one_after_another(self):
        # То, ради чего это и нужно: один аккаунт, корзины по очереди.
        runner, events = self._runner_with(
            [["1" * 9], ["2" * 9], ["3" * 9]], ["127.0.0.1:9222"], 1
        )
        carts = runner.run()
        self.assertEqual([tid for tid, _ in self.collected], [1, 2, 3])
        self.assertEqual(len(carts), 3, "должно получиться три отдельные корзины")
        self.assertTrue(
            any("кругами" in e.message for e in events),
            [e.message for e in events],
        )

    def test_browser_count_limits_parallelism(self):
        self.browsers = ["127.0.0.1:9222", "127.0.0.1:9223", "127.0.0.1:9224"]
        asked = []
        import cart_bot.runner as rm

        rm.launch_user_browsers = lambda cfg, wanted, note=None: (
            asked.append(wanted) or self.browsers[:wanted]
        )
        runner, _ = self._runner([["1" * 9], ["2" * 9], ["3" * 9]], browser_count=2)
        runner.run()
        self.assertEqual(asked, [2], "запрошено не то число окон")

    def test_never_opens_more_windows_than_tabs(self):
        asked = []
        import cart_bot.runner as rm

        rm.launch_user_browsers = lambda cfg, wanted, note=None: (
            asked.append(wanted) or ["127.0.0.1:9222"]
        )
        runner, _ = self._runner([["1" * 9]], browser_count=5)
        runner.run()
        self.assertEqual(asked, [1], "открыл лишние окна под одну вкладку")

if __name__ == "__main__":
    unittest.main()
