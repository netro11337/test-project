import unittest

from cart_bot.markets import OZON, WB
from cart_bot.worker import session_is_anonymous


class FakeElement:
    def __init__(self, displayed=True):
        self._displayed = displayed

    def is_displayed(self):
        return self._displayed


class FakeDriver:
    def __init__(self, signin_visible=None, broken=False):
        self.signin_visible = signin_visible
        self.broken = broken

    def find_elements(self, by, xpath):
        if self.broken:
            raise RuntimeError("драйвер недоступен")
        if self.signin_visible is None:
            return []
        return [FakeElement(self.signin_visible)]


class SessionDetectionTest(unittest.TestCase):
    """Вход в аккаунт решает, будет ли корзина общей у нескольких окон."""

    def test_visible_signin_means_anonymous(self):
        self.assertTrue(session_is_anonymous(FakeDriver(signin_visible=True), OZON))

    def test_no_signin_link_means_signed_in(self):
        self.assertFalse(session_is_anonymous(FakeDriver(), OZON))

    def test_hidden_signin_link_means_signed_in(self):
        self.assertFalse(session_is_anonymous(FakeDriver(signin_visible=False), OZON))

    def test_broken_driver_is_unknown_not_a_crash(self):
        # Это диагностика: её поломка не должна стоить всей сборки.
        self.assertIsNone(session_is_anonymous(FakeDriver(broken=True), OZON))

    def test_both_markets_have_the_marker(self):
        for market in (OZON, WB):
            self.assertIn("Войти", market.signin_marker)


class SharedCartWarningTest(unittest.TestCase):
    """Предупреждение выдаётся ровно один раз, на втором залогиненном окне."""

    def _runner(self):
        from cart_bot.config import Settings
        from cart_bot.runner import CartRunner

        events = []
        runner = CartRunner(Settings(attach_to_chrome=True), [], events.append)
        return runner, events

    def test_warns_on_second_signed_in_browser(self):
        runner, events = self._runner()
        runner._note_session(FakeDriver(), "127.0.0.1:9222")
        self.assertFalse(any("ВНИМАНИЕ" in e.message for e in events))
        runner._note_session(FakeDriver(), "127.0.0.1:9223")
        self.assertTrue(
            any("Корзина магазина привязана к аккаунту" in e.message for e in events)
        )

    def test_anonymous_browsers_do_not_warn(self):
        runner, events = self._runner()
        for port in (9222, 9223, 9224):
            runner._note_session(FakeDriver(signin_visible=True), f"127.0.0.1:{port}")
        self.assertFalse(any("ВНИМАНИЕ" in e.message for e in events))

    def test_single_signed_in_browser_is_fine(self):
        runner, events = self._runner()
        runner._note_session(FakeDriver(), "127.0.0.1:9222")
        self.assertFalse(any("ВНИМАНИЕ" in e.message for e in events))

    def test_warning_is_not_repeated(self):
        runner, events = self._runner()
        for port in (9222, 9223, 9224, 9225):
            runner._note_session(FakeDriver(), f"127.0.0.1:{port}")
        warnings = [e for e in events if "ВНИМАНИЕ" in e.message]
        self.assertEqual(len(warnings), 1)


if __name__ == "__main__":
    unittest.main()
