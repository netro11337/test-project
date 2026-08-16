"""Применение отпечатка браузера к Selenium-драйверу через CDP.

Оригинальный модуль отпечатков написан под Playwright. Здесь та же подмена
делается для Selenium: JS-патчи ставятся скриптом на каждый новый документ, а
UA, языки, локаль и таймзона — командами CDP, чтобы заголовки реальных
запросов не расходились со значениями в JS. Разъехавшийся отпечаток заметнее
честного.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Optional

from .config import Settings
from .fingerprint import Fingerprint, brand_list, build_fingerprint

log = logging.getLogger(__name__)

_STEALTH_JS = Path(__file__).parent / "fingerprint" / "stealth.js"

# Флаги запуска. Ключевой — отключение AutomationControlled: без него Blink
# сам выставляет navigator.webdriver и меняет поведение части API.
LAUNCH_ARGS = (
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-infobars",
    "--password-store=basic",
)


def fingerprint_for(cfg: Settings, thread_id: int) -> Fingerprint:
    """Отпечаток потока. Один и тот же профиль — один и тот же отпечаток.

    Привязка к профилю принципиальна: браузер, который при каждом запуске
    приходит с новым железом и экраном, но со старыми куками, выглядит
    страннее любого честного отпечатка.
    """
    return build_fingerprint(
        seed=f"{cfg.market_key}-thread-{thread_id}",
        os_key=cfg.fp_os or None,
        locale=cfg.fp_locale or None,
    )


def build_init_script(fp: Fingerprint) -> str:
    """Подставляет профиль в шаблон stealth.js."""
    payload = fp.to_dict()
    payload["ua_brands"] = brand_list(fp.chrome_major)
    return _STEALTH_JS.read_text(encoding="utf-8").replace(
        "__FINGERPRINT__", json.dumps(payload, ensure_ascii=False)
    )


def launch_arguments(fp: Fingerprint) -> list:
    """Аргументы запуска Chrome, согласованные с отпечатком."""
    return list(LAUNCH_ARGS) + [
        f"--window-size={fp.viewport_width},{fp.viewport_height}",
        f"--lang={fp.locale}",
    ]


def _sync_chrome_version(driver, fp: Fingerprint) -> None:
    """Подгоняет версию в UA под реально запущенный Chrome.

    UA, который врёт о версии сильнее чем на пару релизов, расходится с
    поведением движка и с sec-ch-ua — это заметный сигнал сам по себе.
    """
    try:
        version = str(driver.capabilities.get("browserVersion") or "")
    except Exception:  # noqa: BLE001
        return
    major = version.split(".")[0]
    if not major.isdigit():
        return
    fp.chrome_full_version = version
    fp.chrome_major = int(major)
    fp.user_agent = re.sub(r"Chrome/[\d.]+", f"Chrome/{major}.0.0.0", fp.user_agent)
    fp.app_version = fp.user_agent[len("Mozilla/") :]


def apply_stealth(driver, fp: Fingerprint) -> bool:
    """Ставит подмену на драйвер. True — применилось полностью."""
    _sync_chrome_version(driver, fp)

    try:
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": build_init_script(fp)},
        )
    except Exception as exc:  # noqa: BLE001
        log.debug("JS-подмена не применилась: %s", exc)
        return False

    brands = brand_list(fp.chrome_major)
    commands = (
        ("Network.enable", {}),
        ("Emulation.setLocaleOverride", {"locale": fp.locale}),
        ("Emulation.setTimezoneOverride", {"timezoneId": fp.timezone}),
        (
            "Network.setUserAgentOverride",
            {
                "userAgent": fp.user_agent,
                # Простой список без q-весов: Chrome расставит их сам.
                "acceptLanguage": ",".join(fp.languages),
                "platform": fp.platform,
                "userAgentMetadata": {
                    "brands": brands,
                    "fullVersionList": [
                        {
                            "brand": b["brand"],
                            "version": "99.0.0.0"
                            if b["brand"] == "Not;A=Brand"
                            else fp.chrome_full_version,
                        }
                        for b in brands
                    ],
                    "fullVersion": fp.chrome_full_version,
                    "platform": fp.ua_data_platform,
                    "platformVersion": fp.ua_data_platform_version,
                    "architecture": fp.ua_data_architecture,
                    "model": fp.ua_data_model,
                    "mobile": False,
                    "bitness": fp.ua_data_bitness,
                    "wow64": False,
                },
            },
        ),
    )

    complete = True
    for name, params in commands:
        try:
            driver.execute_cdp_cmd(name, params)
        except Exception as exc:  # noqa: BLE001
            # JS-патчи уже стоят, расходятся только заголовки — работу это не
            # останавливает, но знать об этом надо.
            log.debug("CDP %s не прошла: %s", name, exc)
            complete = False
    return complete


def describe(fp: Fingerprint) -> str:
    """Короткое описание отпечатка для лога."""
    return (
        f"{fp.os_key}, {fp.locale}, {fp.timezone}, "
        f"{fp.screen_width}×{fp.screen_height}, Chrome {fp.chrome_major}"
    )


def stealth_fingerprint(cfg: Settings, thread_id: int) -> Optional[Fingerprint]:
    """Отпечаток для потока или None, если подмена выключена/неприменима."""
    if not cfg.stealth or cfg.attach_to_chrome:
        return None
    return fingerprint_for(cfg, thread_id)
