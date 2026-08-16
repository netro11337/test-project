#!/usr/bin/env python3
"""Демонстрация: открывает страницу и печатает отпечаток, который её увидел.

    python demo.py                          # локальная проверка, без сети
    python demo.py --seed user-42 --os macos
    python demo.py --url https://abrahamjuliot.github.io/creepjs/ --headful
    python demo.py --compare                # два профиля рядом
"""

from __future__ import annotations

import argparse
import json

from chrome_fingerprint import StealthBrowser, build_fingerprint
from chrome_fingerprint.profiles import LOCALES, OS_PRESETS


def show(title: str, data: dict) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(data, indent=2, ensure_ascii=False))


def run_once(args: argparse.Namespace, seed: str | int | None) -> dict:
    fp = build_fingerprint(seed=seed, os_key=args.os, locale=args.locale)
    print(f"\n--- профиль (seed={fp.seed}) ---\n{fp.summary()}")

    with StealthBrowser(fingerprint=fp, headless=not args.headful) as browser:
        if args.url:
            browser.page.goto(args.url, wait_until="domcontentloaded", timeout=60_000)
            print(f"открыт {args.url}: {browser.page.title()!r}")
            if args.screenshot:
                browser.page.screenshot(path=args.screenshot, full_page=False)
                print(f"скриншот: {args.screenshot}")
            if args.wait:
                browser.page.wait_for_timeout(args.wait * 1000)
        return browser.read_fingerprint()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", help="страница, которую открыть (по умолчанию — офлайн-проверка)")
    parser.add_argument("--seed", help="строка/число: одинаковый seed = одинаковый профиль")
    parser.add_argument("--os", choices=sorted(OS_PRESETS), help="принудительно выбрать ОС")
    parser.add_argument("--locale", choices=sorted(LOCALES), help="принудительно выбрать локаль")
    parser.add_argument("--headful", action="store_true", help="показать окно браузера")
    parser.add_argument("--screenshot", help="сохранить скриншот в файл")
    parser.add_argument("--wait", type=int, default=0, help="подождать N секунд перед закрытием")
    parser.add_argument("--compare", action="store_true", help="показать два разных профиля подряд")
    args = parser.parse_args()

    first = run_once(args, args.seed)
    show("что видит страница", first)

    if args.compare:
        second = run_once(args, f"{args.seed or 'profile'}-b")
        show("второй профиль", second)
        print("\nодинаковый хеш канвы?", first["canvasHash"] == second["canvasHash"])


if __name__ == "__main__":
    main()
