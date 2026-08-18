"""Создание Chrome-драйвера, заточенного под скорость."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import Optional

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

from .config import BLOCKED_URL_PATTERNS, Settings
from .stealth import apply_stealth, describe, launch_arguments, stealth_fingerprint

log = logging.getLogger(__name__)


def _build_options(
    cfg: Settings,
    profile_dir: Path,
    headless: bool,
    fingerprint=None,
) -> Options:
    opts = Options()

    if headless:
        # Новый headless: ведёт себя как обычный Chrome, но без отрисовки окна.
        opts.add_argument("--headless=new")

    # Каждый поток — свой профиль, то есть своя сессия и своя корзина.
    profile_dir.mkdir(parents=True, exist_ok=True)
    opts.add_argument(f"--user-data-dir={profile_dir}")

    # eager: не ждём картинки и «хвост» загрузки — DOM готов, можно кликать.
    opts.page_load_strategy = "eager"

    if fingerprint is None:
        opts.add_argument("--window-size=1280,900")
        opts.add_argument("--lang=ru-RU")
    else:
        # Размер окна и язык берём из отпечатка, иначе они разойдутся с тем,
        # что подменяется в JS.
        for argument in launch_arguments(fingerprint):
            opts.add_argument(argument)

    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-background-networking")
    opts.add_argument("--disable-notifications")
    opts.add_argument("--no-first-run")
    opts.add_argument("--no-default-browser-check")

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


# Драйвер определяем один раз на всю программу. Раньше каждый поток запускал
# установку сам, и при параллельном старте они дрались за один кэш: часть
# потоков падала с «Unable to obtain driver for chrome».
_DRIVER_LOCK = threading.Lock()
_DRIVER_PATH: Optional[str] = None
_DRIVER_RESOLVED = False


def _driver_path() -> Optional[str]:
    """Путь к chromedriver. Скачивается один раз, дальше берётся из памяти."""
    global _DRIVER_PATH, _DRIVER_RESOLVED
    if _DRIVER_RESOLVED:
        return _DRIVER_PATH

    with _DRIVER_LOCK:
        if _DRIVER_RESOLVED:
            return _DRIVER_PATH
        _DRIVER_PATH = _download_driver() or _cached_driver() or _driver_on_path()
        if _DRIVER_PATH:
            log.info("Драйвер Chrome: %s", _DRIVER_PATH)
        _DRIVER_RESOLVED = True
    return _DRIVER_PATH


def _download_driver() -> Optional[str]:
    """Штатный путь: webdriver-manager сам скачает нужную версию."""
    try:
        from webdriver_manager.chrome import ChromeDriverManager

        return ChromeDriverManager().install()
    except Exception as exc:  # noqa: BLE001 - деградируем, а не падаем
        log.warning("webdriver-manager не отработал: %s", exc)
        return None


def _cached_driver() -> Optional[str]:
    """Ищет уже скачанный chromedriver в кэше webdriver-manager.

    Кэш может побиться — например, если несколько потоков качали в него
    одновременно. Сам менеджер тогда падает, но рабочий файл рядом обычно
    остаётся, и второй раз качать его незачем.
    """
    cache = Path.home() / ".wdm" / "drivers" / "chromedriver"
    if not cache.exists():
        return None
    names = ("chromedriver.exe", "chromedriver")
    found = [
        path
        for name in names
        for path in cache.rglob(name)
        if path.is_file() and path.stat().st_size > 0
    ]
    if not found:
        return None
    # Свежайший по времени: он соответствует последней версии браузера.
    newest = max(found, key=lambda path: path.stat().st_mtime)
    log.info("Взял драйвер из кэша: %s", newest)
    return str(newest)


def _driver_on_path() -> Optional[str]:
    """chromedriver, установленный в системе вручную."""
    import shutil

    found = shutil.which("chromedriver") or shutil.which("chromedriver.exe")
    if found:
        log.info("Взял chromedriver из PATH: %s", found)
    return found


DRIVER_CACHE_HINT = (
    "Если ошибка повторяется, удалите папку с кэшем драйверов "
    "%USERPROFILE%\\.wdm (в проводнике: введите %USERPROFILE% в адресную "
    "строку и удалите папку .wdm) и запустите программу заново."
)


def _resolve_service() -> Optional[Service]:
    """Свой Service на каждый драйвер, но с общим путём к chromedriver.

    Один Service нельзя переиспользовать для нескольких браузеров — он держит
    свой процесс, — а вот путь к файлу общий, и искать его повторно незачем.
    """
    path = _driver_path()
    return Service(path) if path else None


def _new_chrome(options: Options) -> webdriver.Chrome:
    """Поднимает браузер. Запуски сериализованы.

    Одновременный старт нескольких chromedriver время от времени заканчивается
    ошибкой получения драйвера, а выигрыш от параллельного старта — доли
    секунды на фоне всей сборки.
    """
    with _DRIVER_LOCK:
        service = _resolve_service()
        try:
            if service is not None:
                return webdriver.Chrome(service=service, options=options)
            return webdriver.Chrome(options=options)
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                "Не удалось запустить Chrome. Проверьте, что браузер установлен "
                "и есть доступ в интернет для загрузки драйвера. "
                + DRIVER_CACHE_HINT
                + f" Исходная ошибка: {str(exc).splitlines()[0]}"
            ) from exc


def driver_ready() -> Optional[str]:
    """Готовит драйвер заранее, до запуска потоков.

    Так загрузка происходит один раз и до параллельной работы, а проблема
    видна одной понятной строкой, а не пятью одинаковыми падениями подряд.
    """
    return _driver_path()


def probe_debug_ports(cfg: Settings, wanted: int) -> list:
    """Какие браузеры пользователя реально запущены.

    Проверяем подряд идущие порты и берём столько, сколько отвечает: лучше
    работать двумя браузерами из трёх, чем упасть на первом же отсутствующем.
    """
    import socket

    alive = []
    for index in range(1, max(1, wanted) + 1):
        address = cfg.debug_address_for(index)
        host, _, port = address.partition(":")
        try:
            with socket.create_connection((host, int(port)), 1.0):
                alive.append(address)
        except (OSError, ValueError):
            break
    return alive


def attach_driver(cfg: Settings, address: Optional[str] = None) -> webdriver.Chrome:
    """Подключается к уже запущенному Chrome пользователя.

    Ничего не маскируем: это тот самый браузер, которым человек пользуется
    каждый день, со своим профилем, аккаунтом и историей. Свои настройки
    (headless, профиль, экономия трафика) здесь не применяются — браузер уже
    запущен, и распоряжаться им как своим нельзя.
    """
    options = Options()
    options.debugger_address = address or cfg.debug_address
    options.page_load_strategy = "eager"

    driver = _new_chrome(options)
    driver.set_page_load_timeout(cfg.page_load_timeout)
    driver.set_script_timeout(cfg.page_load_timeout)
    return driver


def create_driver(
    cfg: Settings,
    profile_dir: Path,
    headless: Optional[bool] = None,
    thread_id: int = 1,
    debug_address: Optional[str] = None,
) -> webdriver.Chrome:
    """Поднимает Chrome с отключённой графикой и короткими таймаутами."""
    if cfg.attach_to_chrome:
        return attach_driver(cfg, debug_address)

    use_headless = cfg.headless if headless is None else headless
    fingerprint = stealth_fingerprint(cfg, thread_id)
    options = _build_options(cfg, profile_dir, use_headless, fingerprint)

    driver = _new_chrome(options)

    driver.set_page_load_timeout(cfg.page_load_timeout)
    driver.set_script_timeout(cfg.page_load_timeout)

    # Отдельной кустарной подмены navigator.webdriver здесь нет: свойство
    # снимается флагом --disable-blink-features=AutomationControlled, а всё
    # остальное делает согласованный отпечаток. Ручная подстановка вешала
    # свойство на сам объект navigator, тогда как настоящее живёт в
    # Navigator.prototype, и эта разница — известный признак автоматизации.
    if fingerprint is not None:
        applied = apply_stealth(driver, fingerprint)
        log.info(
            "Отпечаток потока %s: %s%s",
            thread_id,
            describe(fingerprint),
            "" if applied else " (часть CDP-команд не прошла)",
        )

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
