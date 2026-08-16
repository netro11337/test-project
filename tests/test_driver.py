import unittest
from pathlib import Path

from cart_bot.config import Settings
from cart_bot.driver import _build_options, _patterns_for

PROFILE = Path("/tmp/cart-bot-test-profile")


class ResourceBlockingTest(unittest.TestCase):
    """Блокировка ресурсов должна сниматься на ходу.

    Капча Ozon показывает пазл картинкой. Если картинки выключены флагами
    запуска браузера, вернуть их во время работы нельзя, и проверка вечно
    крутит спиннер — решить её невозможно.
    """

    def test_images_are_not_disabled_at_startup(self):
        options = _build_options(Settings(block_images=True), PROFILE, True)
        self.assertFalse(
            any("imagesEnabled" in arg for arg in options.arguments),
            "картинки выключены флагом запуска — их нельзя вернуть на ходу",
        )

    def test_images_are_not_disabled_through_prefs(self):
        options = _build_options(Settings(block_images=True), PROFILE, True)
        prefs = options.experimental_options.get("prefs", {})
        self.assertNotIn("profile.managed_default_content_settings.images", prefs)

    def test_blocking_goes_through_toggleable_patterns(self):
        patterns = _patterns_for(Settings(block_images=True, block_analytics=True))
        self.assertTrue(any(p.endswith(".png") for p in patterns))
        self.assertTrue(any("analytics" in p for p in patterns))

    def test_nothing_blocked_when_both_toggles_are_off(self):
        self.assertEqual(
            _patterns_for(Settings(block_images=False, block_analytics=False)), []
        )

    def test_images_only(self):
        patterns = _patterns_for(Settings(block_images=True, block_analytics=False))
        self.assertTrue(patterns)
        self.assertTrue(all(p.startswith("*.") for p in patterns))


class HeadlessTest(unittest.TestCase):
    def test_headless_flag_follows_the_setting(self):
        visible = _build_options(Settings(), PROFILE, False)
        self.assertFalse(any("headless" in arg for arg in visible.arguments))
        hidden = _build_options(Settings(), PROFILE, True)
        self.assertTrue(any("headless" in arg for arg in hidden.arguments))

    def test_profile_directory_is_passed(self):
        options = _build_options(Settings(), PROFILE, True)
        self.assertTrue(
            any(str(PROFILE) in arg for arg in options.arguments),
            "поток должен работать в своём профиле, иначе корзина будет общей",
        )


if __name__ == "__main__":
    unittest.main()
