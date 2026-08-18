import threading
import unittest

import cart_bot.driver as driver_module
from cart_bot.driver import _driver_path


def reset_cache():
    driver_module._DRIVER_PATH = None
    driver_module._DRIVER_RESOLVED = False


class DriverResolutionTest(unittest.TestCase):
    """Драйвер ищется один раз: параллельные загрузки ломали общий кэш."""

    def setUp(self):
        self.saved = (
            driver_module._download_driver,
            driver_module._cached_driver,
            driver_module._driver_on_path,
        )
        reset_cache()

    def tearDown(self):
        (
            driver_module._download_driver,
            driver_module._cached_driver,
            driver_module._driver_on_path,
        ) = self.saved
        reset_cache()

    def test_download_is_used_first(self):
        driver_module._download_driver = lambda: "/скачанный"
        driver_module._cached_driver = lambda: "/из-кэша"
        driver_module._driver_on_path = lambda: "/из-PATH"
        self.assertEqual(_driver_path(), "/скачанный")

    def test_falls_back_to_cache_when_download_fails(self):
        # Ровно наблюдавшийся случай: менеджер падает, а файл рядом лежит.
        driver_module._download_driver = lambda: None
        driver_module._cached_driver = lambda: "/из-кэша"
        driver_module._driver_on_path = lambda: "/из-PATH"
        self.assertEqual(_driver_path(), "/из-кэша")

    def test_falls_back_to_system_driver(self):
        driver_module._download_driver = lambda: None
        driver_module._cached_driver = lambda: None
        driver_module._driver_on_path = lambda: "/из-PATH"
        self.assertEqual(_driver_path(), "/из-PATH")

    def test_none_when_nothing_found(self):
        driver_module._download_driver = lambda: None
        driver_module._cached_driver = lambda: None
        driver_module._driver_on_path = lambda: None
        self.assertIsNone(_driver_path())

    def test_resolved_once_for_all_threads(self):
        calls = []

        def slow_download():
            calls.append(1)
            import time

            time.sleep(0.05)
            return "/скачанный"

        driver_module._download_driver = slow_download
        driver_module._cached_driver = lambda: None
        driver_module._driver_on_path = lambda: None

        results = []
        threads = [
            threading.Thread(target=lambda: results.append(_driver_path()))
            for _ in range(5)
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(len(calls), 1, "драйвер качали несколько раз разом")
        self.assertEqual(results, ["/скачанный"] * 5)

    def test_failure_is_not_retried_every_time(self):
        calls = []
        driver_module._download_driver = lambda: calls.append(1) or None
        driver_module._cached_driver = lambda: None
        driver_module._driver_on_path = lambda: None
        _driver_path()
        _driver_path()
        self.assertEqual(len(calls), 1)


class ErrorMessageTest(unittest.TestCase):
    def test_hint_points_at_the_cache_folder(self):
        self.assertIn(".wdm", driver_module.DRIVER_CACHE_HINT)


if __name__ == "__main__":
    unittest.main()
