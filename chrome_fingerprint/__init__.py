"""Chromium с подменой отпечатка браузера (Playwright).

Назначение: тестирование антифрод-/антибот-логики на своих сайтах,
исследование fingerprinting и защита приватности при автоматизации.
"""

from .browser import StealthBrowser, build_init_script, context_options
from .profiles import Fingerprint, build_fingerprint, OS_PRESETS, LOCALES

__all__ = [
    "StealthBrowser",
    "Fingerprint",
    "build_fingerprint",
    "build_init_script",
    "context_options",
    "OS_PRESETS",
    "LOCALES",
]
__version__ = "0.1.0"
