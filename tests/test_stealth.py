import json
import unittest

from cart_bot.config import Settings
from cart_bot.stealth import (
    apply_stealth,
    build_init_script,
    fingerprint_for,
    launch_arguments,
    stealth_fingerprint,
)


class FakeDriver:
    def __init__(self, version="151.0.7922.138", failing=()):
        self.capabilities = {"browserVersion": version}
        self.calls = []
        self.failing = failing

    def execute_cdp_cmd(self, name, params):
        if name in self.failing:
            raise RuntimeError(f"{name} недоступна")
        self.calls.append((name, params))
        return {}


class FingerprintStabilityTest(unittest.TestCase):
    """Отпечаток привязан к профилю потока и не должен меняться между запусками.

    Браузер, приходящий с новым железом и экраном, но со старыми куками,
    выглядит страннее любого честного отпечатка.
    """

    def test_same_thread_gets_the_same_fingerprint(self):
        cfg = Settings(stealth=True)
        first = fingerprint_for(cfg, 1)
        second = fingerprint_for(cfg, 1)
        self.assertEqual(first.user_agent, second.user_agent)
        self.assertEqual(first.webgl_renderer, second.webgl_renderer)
        self.assertEqual(first.screen_width, second.screen_width)
        self.assertEqual(first.timezone, second.timezone)

    def test_different_threads_differ(self):
        cfg = Settings(stealth=True)
        prints = {
            (
                fingerprint_for(cfg, i).webgl_renderer,
                fingerprint_for(cfg, i).screen_width,
                fingerprint_for(cfg, i).hardware_concurrency,
            )
            for i in range(1, 6)
        }
        self.assertGreater(len(prints), 1, "все потоки получили один отпечаток")

    def test_markets_do_not_share_a_fingerprint(self):
        ozon = fingerprint_for(Settings(stealth=True, market_key="ozon"), 1)
        wb = fingerprint_for(Settings(stealth=True, market_key="wb"), 1)
        self.assertNotEqual(
            (ozon.webgl_renderer, ozon.screen_width, ozon.hardware_concurrency),
            (wb.webgl_renderer, wb.screen_width, wb.hardware_concurrency),
        )

    def test_defaults_match_the_store(self):
        # Немецкая локаль с московским магазином — сигнал сама по себе.
        fp = fingerprint_for(Settings(stealth=True), 1)
        self.assertEqual(fp.locale, "ru-RU")
        self.assertEqual(fp.os_key, "windows")
        self.assertIn("ru-RU", fp.languages)


class InitScriptTest(unittest.TestCase):
    def test_placeholder_is_replaced(self):
        script = build_init_script(fingerprint_for(Settings(stealth=True), 1))
        self.assertNotIn("__FINGERPRINT__", script)
        self.assertIn("navigator", script)

    def test_profile_values_land_in_the_script(self):
        fp = fingerprint_for(Settings(stealth=True), 1)
        script = build_init_script(fp)
        self.assertIn(json.dumps(fp.webgl_renderer, ensure_ascii=False)[1:-1], script)


class ApplyStealthTest(unittest.TestCase):
    def setUp(self):
        self.fp = fingerprint_for(Settings(stealth=True), 1)

    def test_all_cdp_commands_are_sent(self):
        driver = FakeDriver()
        self.assertTrue(apply_stealth(driver, self.fp))
        sent = [name for name, _ in driver.calls]
        for expected in (
            "Page.addScriptToEvaluateOnNewDocument",
            "Emulation.setLocaleOverride",
            "Emulation.setTimezoneOverride",
            "Network.setUserAgentOverride",
        ):
            self.assertIn(expected, sent)

    def test_user_agent_version_follows_the_real_browser(self):
        # UA, обещающий Chrome 140 при запущенном 151, расходится с поведением
        # движка и с sec-ch-ua — это заметнее, чем отсутствие подмены.
        driver = FakeDriver(version="151.0.7922.138")
        apply_stealth(driver, self.fp)
        self.assertIn("Chrome/151.0.0.0", self.fp.user_agent)
        override = dict(driver.calls)["Network.setUserAgentOverride"]
        self.assertEqual(override["userAgent"], self.fp.user_agent)
        self.assertEqual(override["userAgentMetadata"]["fullVersion"], "151.0.7922.138")

    def test_headers_match_the_script(self):
        driver = FakeDriver()
        apply_stealth(driver, self.fp)
        override = dict(driver.calls)["Network.setUserAgentOverride"]
        self.assertEqual(override["acceptLanguage"], ",".join(self.fp.languages))
        self.assertEqual(override["platform"], self.fp.platform)
        self.assertEqual(
            dict(driver.calls)["Emulation.setTimezoneOverride"]["timezoneId"],
            self.fp.timezone,
        )

    def test_partial_failure_is_reported_not_raised(self):
        driver = FakeDriver(failing={"Emulation.setTimezoneOverride"})
        self.assertFalse(apply_stealth(driver, self.fp))

    def test_js_failure_stops_early(self):
        driver = FakeDriver(failing={"Page.addScriptToEvaluateOnNewDocument"})
        self.assertFalse(apply_stealth(driver, self.fp))


class StealthSwitchTest(unittest.TestCase):
    def test_off_by_default(self):
        self.assertIsNone(stealth_fingerprint(Settings(), 1))

    def test_enabled(self):
        self.assertIsNotNone(stealth_fingerprint(Settings(stealth=True), 1))

    def test_never_applied_to_someone_elses_browser(self):
        cfg = Settings(stealth=True, attach_to_chrome=True)
        self.assertIsNone(
            stealth_fingerprint(cfg, 1),
            "чужой запущенный браузер перенастраивать нельзя",
        )

    def test_launch_arguments_match_the_fingerprint(self):
        fp = fingerprint_for(Settings(stealth=True), 1)
        args = launch_arguments(fp)
        self.assertIn("--disable-blink-features=AutomationControlled", args)
        self.assertIn(f"--lang={fp.locale}", args)
        self.assertIn(f"--window-size={fp.viewport_width},{fp.viewport_height}", args)


if __name__ == "__main__":
    unittest.main()
