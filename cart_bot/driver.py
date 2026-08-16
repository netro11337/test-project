"""Создание Chrome-драйвера, заточенного под скорость."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from .config import BLOCKED_URL_PATTERNS, Settings

log = logging.getLogger(__name__)

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


def _build_options(cfg: Settings, profile_dir: Path, headless: bool) -> Options:
    opts = Options()

    if headless:
        # Новый headless: ведёт себя как обычный Chrome, но без отрисовки окна.
        opts.add_argument("--headless=new")

    # Каждый поток — свой профиль, то есть своя сессия и своя корзина.
    profile_dir.mkdir(parents=True, exist_ok=True)
    opts.add_argument(f"--user-data-dir={profile_dir}")

    # eager: не ждём картинки и «хвост» загрузки — DOM готов, можно кликать.
    opts.page_load_strategy = "eager"

    opts.add_argument("--window-size=1280,900")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-background-networking")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")
    opts.add_argument("--lang=ru-RU")
    opts.add_argument(f"--user-agent={_UA}")

    # Картинки НЕ отключаем флагами запуска (--blink-settings, prefs): их
    # нельзя вернуть на ходу, а капчу с картинкой-пазлом тогда не решить.
    # Вся блокировка идёт через CDP — её можно снять и включить обратно.
    prefs = {
        "profile.default_content_setting_values.notifications": 2,
        "profile.default_content_setting_values.geolocation": 2,
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False,
    }
    opts.add_experimental_option("prefs", prefs)

    # Убираем очевидные следы автоматизации — Ozon на них реагирует.
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    return opts


def _resolve_service() -> Optional[Service]:
    """webdriver-manager, если он есть; иначе штатный Selenium Manager."""
    try:
        from webdriver_manager.chrome import ChromeDriverManager

        return Service(ChromeDriverManager().install())
    except Exception as exc:  # noqa: BLE001 - деградируем, а не падаем
        log.debug("webdriver-manager недоступен (%s), беру Selenium Manager", exc)
        return None


def attach_driver(cfg: Settings) -> webdriver.Chrome:
    """Подключается к уже запущенному Chrome пользователя.

    Ничего не маскируем: это тот самый браузер, которым человек пользуется
    каждый день, со своим профилем, аккаунтом и историей. Свои настройки
    (headless, профиль, экономия трафика) здесь не применяются — браузер уже
    запущен, и распоряжаться им как своим нельзя.
    """
    options = Options()
    options.debugger_address = cfg.debug_address
    options.page_load_strategy = "eager"

    service = _resolve_service()
    driver = (
        webdriver.Chrome(service=service, options=options)
        if service is not None
        else webdriver.Chrome(options=options)
    )
    driver.set_page_load_timeout(cfg.page_load_timeout)
    driver.set_script_timeout(cfg.page_load_timeout)
    return driver


def create_driver(
    cfg: Settings,
    profile_dir: Path,
    headless: Optional[bool] = None,
) -> webdriver.Chrome:
    """Поднимает Chrome с отключённой графикой и короткими таймаутами."""
    if cfg.attach_to_chrome:
        return attach_driver(cfg)

    use_headless = cfg.headless if headless is None else headless
    options = _build_options(cfg, profile_dir, use_headless)

    service = _resolve_service()
    driver = (
        webdriver.Chrome(service=service, options=options)
        if service is not None
        else webdriver.Chrome(options=options)
    )

    driver.set_page_load_timeout(cfg.page_load_timeout)
    driver.set_script_timeout(cfg.page_load_timeout)

    # Подмены navigator.webdriver здесь намеренно нет. Она не только пытается
    # выдать браузер за другой, но и работает против себя: подставленное
    # свойство висит на самом объекте navigator, тогда как настоящее живёт в
    # Navigator.prototype, и эта разница — известный признак автоматизации.
    apply_resource_blocking(driver, cfg)
    return driver


def _patterns_for(cfg: Settings) -> list:
    return [
        pattern
        for pattern in BLOCKED_URL_PATTERNS
        if (cfg.block_images and pattern.startswith("*."))
        or (cfg.block_analytics and not pattern.startswith("*."))
    ]


def apply_resource_blocking(driver: webdriver.Chrome, cfg: Settings) -> None:
    """Включает экономию трафика: картинки, шрифты, аналитика.

    В чужом браузере не трогаем ничего: человек продолжит им пользоваться, и
    оставлять ему сайты без картинок нельзя.
    """
    if cfg.attach_to_chrome:
        return
    patterns = _patterns_for(cfg)
    if not patterns:
        return
    try:
        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": patterns})
    except Exception as exc:  # noqa: BLE001
        log.debug("Не включил блокировку ресурсов: %s", exc)


def clear_resource_blocking(driver: webdriver.Chrome) -> bool:
    """Снимает блокировку ресурсов.

    Нужно на странице проверки: пазл в капче — это картинка, и с включённой
    блокировкой виджет крутит загрузку бесконечно, а решить капчу невозможно.
    """
    try:
        driver.execute_cdp_cmd("Network.enable", {})
        driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": []})
        return True
    except Exception as exc:  # noqa: BLE001
        log.debug("Не снял блокировку ресурсов: %s", exc)
        return False


def quit_driver(driver: Optional[webdriver.Chrome], owned: bool = True) -> None:
    """Закрывает драйвер, не роняя вызывающий код.

    owned=False — браузер не наш, мы к нему подключились. Закрывать его нельзя:
    у пользователя схлопнутся все вкладки.
    """
    if driver is None or not owned:
        return
    try:
        driver.quit()
    except Exception as exc:  # noqa: BLE001
        log.debug("Ошибка при закрытии драйвера: %s", exc)
