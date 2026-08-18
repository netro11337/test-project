import unittest
from pathlib import Path

import cart_bot.driver as driver_module
from cart_bot.config import Settings
from cart_bot.driver import launch_user_browsers, user_browser_profile


class AutoLaunchTest(unittest.TestCase):
    """Программа сама открывает столько браузеров, сколько задано потоков."""

    def setUp(self):
        self.saved = (
            driver_module.find_chrome,
            driver_module._port_alive,
            driver_module.probe_debug_ports,
        )
        self.commands = []
        self.alive = set()

        import subprocess

        self.saved_popen = subprocess.Popen

        def fake_popen(command, **kwargs):
            self.commands.append(command)
            # Окно поднялось — порт отвечает.
            port = next(a for a in command if a.startswith("--remote-debugging-port"))
            self.alive.add("127.0.0.1:" + port.rpartition("=")[2])
            return object()

        subprocess.Popen = fake_popen
        driver_module.find_chrome = lambda: "/usr/bin/google-chrome"
        driver_module._port_alive = lambda address: address in self.alive

    def tearDown(self):
        import subprocess

        subprocess.Popen = self.saved_popen
        (
            driver_module.find_chrome,
            driver_module._port_alive,
            driver_module.probe_debug_ports,
        ) = self.saved

    def test_opens_one_browser_per_thread(self):
        alive = launch_user_browsers(Settings(), 3)
        self.assertEqual(len(self.commands), 3)
        self.assertEqual(
            alive, ["127.0.0.1:9222", "127.0.0.1:9223", "127.0.0.1:9224"]
        )

    def test_already_open_browsers_are_not_duplicated(self):
        self.alive.add("127.0.0.1:9222")
        launch_user_browsers(Settings(), 2)
        self.assertEqual(len(self.commands), 1, "переоткрыл уже готовое окно")

    def test_each_browser_gets_its_own_profile(self):
        launch_user_browsers(Settings(), 2)
        profiles = [
            arg for command in self.commands for arg in command
            if arg.startswith("--user-data-dir=")
        ]
        self.assertEqual(len(set(profiles)), 2, "окна делят один профиль")

    def test_missing_chrome_does_not_crash(self):
        driver_module.find_chrome = lambda: None
        driver_module.probe_debug_ports = lambda cfg, wanted: []
        notes = []
        self.assertEqual(launch_user_browsers(Settings(), 2, notes.append), [])
        self.assertTrue(notes, "пользователю не сказали, что Chrome не найден")

    def test_profiles_are_separate_from_thread_profiles(self):
        cfg = Settings()
        self.assertNotEqual(user_browser_profile(cfg, 1), cfg.profile_for(1))


class BrowserCountTest(unittest.TestCase):
    def test_one_browser_by_default(self):
        # Один аккаунт — одна корзина на сервере, поэтому по умолчанию одно
        # окно и круги: так корзины не смешиваются.
        self.assertEqual(Settings().browser_count, 1)

    def test_auto_launch_on_by_default(self):
        self.assertTrue(Settings().auto_launch_browsers)


if __name__ == "__main__":
    unittest.main()
