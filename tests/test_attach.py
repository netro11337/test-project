import unittest

from cart_bot.config import Settings
from cart_bot.driver import _patterns_for


class AttachModeTest(unittest.TestCase):
    """Работа в браузере пользователя: своим его считать нельзя."""

    def test_resource_blocking_is_off_for_someone_elses_browser(self):
        # Блокировку в чужом браузере не включаем даже при поднятых галках:
        # человек продолжит им пользоваться, и сайты без картинок ему не нужны.
        cfg = Settings(attach_to_chrome=True, block_images=True, block_analytics=True)
        from cart_bot import driver as driver_module

        calls = []

        class FakeDriver:
            def execute_cdp_cmd(self, name, params):
                calls.append(name)

        driver_module.apply_resource_blocking(FakeDriver(), cfg)
        self.assertEqual(calls, [])

    def test_patterns_still_computed_for_own_browser(self):
        cfg = Settings(attach_to_chrome=False, block_images=True)
        self.assertTrue(_patterns_for(cfg))

    def test_quit_skipped_for_attached_browser(self):
        from cart_bot.driver import quit_driver

        quits = []

        class FakeDriver:
            def quit(self):
                quits.append(True)

        quit_driver(FakeDriver(), owned=False)
        self.assertEqual(quits, [], "чужой браузер закрывать нельзя")

        quit_driver(FakeDriver(), owned=True)
        self.assertEqual(len(quits), 1)

    def test_default_debug_address(self):
        self.assertEqual(Settings().debug_address, "127.0.0.1:9222")

    def test_attach_is_off_by_default(self):
        self.assertFalse(Settings().attach_to_chrome)


class HumanPaceTest(unittest.TestCase):
    def test_pace_is_off_by_default(self):
        self.assertFalse(Settings().human_pace)

    def test_pace_range_is_sane(self):
        cfg = Settings()
        self.assertGreater(cfg.pace_min, 0)
        self.assertGreater(cfg.pace_max, cfg.pace_min)


if __name__ == "__main__":
    unittest.main()
