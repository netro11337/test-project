"""Согласованный отпечаток браузера.

Перенесено из ветки claude/chrome-fingerprint-spoofing-vc8hxj без изменений:
profiles.py и stealth.js провайдеро-независимы. Оригинальный browser.py
рассчитан на Playwright и здесь не используется — наше приложение на Selenium,
и та же подмена применяется через CDP в cart_bot/stealth.py.
"""

from .profiles import (
    LOCALES,
    OS_PRESETS,
    Fingerprint,
    brand_list,
    build_fingerprint,
)

__all__ = [
    "Fingerprint",
    "build_fingerprint",
    "brand_list",
    "OS_PRESETS",
    "LOCALES",
]
