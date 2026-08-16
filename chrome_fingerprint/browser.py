"""Запуск Chromium (Playwright) с подменённым отпечатком.

Подмена делается в двух местах, и оба нужны:

* уровень браузера/контекста — User-Agent, локаль, таймзона, размер вьюпорта,
  HTTP-заголовки. Это то, что видит сервер, и то, что нельзя убедительно
  подделать из JS (например, Accept-Language в реальном запросе).
* уровень страницы — init-скрипт, который правит navigator/screen/WebGL/canvas
  до выполнения скриптов сайта.

Если подменить только одно из двух, отпечаток разъедется: UA скажет «Windows»,
а Accept-Language и таймзона — что-то другое, и это само по себе сигнал.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

from .profiles import Fingerprint, brand_list, build_fingerprint

_STEALTH_JS = Path(__file__).with_name("stealth.js")

# Origin для офлайн-проверок: запросы к нему перехватываются, наружу не уходят.
_LOCAL_ORIGIN = "https://fingerprint.local"

# Синхронный Playwright допускает только один активный экземпляр на поток,
# поэтому держим общий с подсчётом ссылок: так несколько StealthBrowser
# спокойно живут одновременно (разные профили в одном процессе).
_playwright: Playwright | None = None
_playwright_refs = 0


def _acquire_playwright() -> Playwright:
    global _playwright, _playwright_refs
    if _playwright is None:
        _playwright = sync_playwright().start()
    _playwright_refs += 1
    return _playwright


def _release_playwright() -> None:
    global _playwright, _playwright_refs
    _playwright_refs = max(0, _playwright_refs - 1)
    if _playwright_refs == 0 and _playwright is not None:
        _playwright.stop()
        _playwright = None

# Флаги запуска. Ключевой — отключение AutomationControlled: без него Blink
# сам выставляет navigator.webdriver и меняет поведение части API.
LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-features=IsolateOrigins,site-per-process,AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-infobars",
    "--password-store=basic",
    "--use-mock-keychain",
]

# Playwright по умолчанию добавляет эти два переключателя, они видны сайту.
IGNORE_DEFAULT_ARGS = ["--enable-automation", "--disable-component-update"]


def build_init_script(fp: Fingerprint) -> str:
    """Подставляет профиль в шаблон stealth.js."""
    payload: dict[str, Any] = fp.to_dict()
    payload["ua_brands"] = brand_list(fp.chrome_major)
    return _STEALTH_JS.read_text(encoding="utf-8").replace(
        "__FINGERPRINT__", json.dumps(payload, ensure_ascii=False)
    )


def context_options(fp: Fingerprint) -> dict[str, Any]:
    """Опции контекста, согласованные с профилем."""
    return {
        "user_agent": fp.user_agent,
        # locale здесь намеренно не передаём: Playwright выставляет из него
        # Accept-Language одним языком ("de-DE") и перебивает наш полный
        # список. Локаль ставим через CDP в _apply_cdp_overrides.
        "timezone_id": fp.timezone,
        "viewport": {"width": fp.viewport_width, "height": fp.viewport_height},
        "screen": {"width": fp.screen_width, "height": fp.screen_height},
        "device_scale_factor": fp.device_scale_factor,
        "is_mobile": False,
        "has_touch": fp.max_touch_points > 0,
        "color_scheme": "light",
        "reduced_motion": "no-preference",
        "java_script_enabled": True,
        "extra_http_headers": {
            "Accept-Language": fp.accept_language,
            "sec-ch-ua": fp.sec_ch_ua,
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": f'"{fp.ua_data_platform}"',
        },
    }


class StealthBrowser:
    """Контекстный менеджер: браузер + контекст + первая страница.

    >>> with StealthBrowser(seed="user-42") as b:
    ...     b.page.goto("https://example.com")
    """

    def __init__(
        self,
        fingerprint: Fingerprint | None = None,
        seed: str | int | None = None,
        os_key: str | None = None,
        locale: str | None = None,
        headless: bool = True,
        proxy: dict[str, str] | None = None,
        executable_path: str | None = None,
        user_data_dir: str | None = None,
        slow_mo: int = 0,
    ) -> None:
        self.fingerprint = fingerprint or build_fingerprint(seed=seed, os_key=os_key, locale=locale)
        self.headless = headless
        self.proxy = proxy
        self.executable_path = executable_path
        self.user_data_dir = user_data_dir
        self.slow_mo = slow_mo

        self._pw: Playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self._cdp_sessions: list[Any] = []
        self._patched_pages: list[Page] = []

    # -- жизненный цикл ------------------------------------------------------

    def start(self) -> "StealthBrowser":
        self._pw = _acquire_playwright()
        launch_kwargs: dict[str, Any] = {
            "headless": self.headless,
            "args": LAUNCH_ARGS,
            "ignore_default_args": IGNORE_DEFAULT_ARGS,
            "slow_mo": self.slow_mo,
        }
        if self.proxy:
            launch_kwargs["proxy"] = self.proxy
        if self.executable_path:
            launch_kwargs["executable_path"] = self.executable_path

        if self.user_data_dir:
            # Персистентный профиль: куки и localStorage переживают перезапуск,
            # что для «живого» пользователя выглядит естественнее.
            self.context = self._pw.chromium.launch_persistent_context(
                self.user_data_dir, **launch_kwargs, **context_options(self.fingerprint)
            )
            self.browser = self.context.browser
            self._sync_chrome_version()
        else:
            self.browser = self._pw.chromium.launch(**launch_kwargs)
            # Версию Chrome берём из реального бинарника до создания контекста:
            # UA, который врёт о версии сильнее чем на пару релизов, расходится
            # с реальным поведением движка и с sec-ch-ua.
            self._sync_chrome_version()
            self.context = self.browser.new_context(**context_options(self.fingerprint))

        self.context.add_init_script(build_init_script(self.fingerprint))
        # Всплывающие окна и вкладки, открытые самим сайтом, тоже должны
        # получить подмену — на них event единственный способ.
        self.context.on("page", self._apply_cdp_overrides)
        for existing in self.context.pages:
            self._apply_cdp_overrides(existing)

        self.page = self.new_page() if not self.context.pages else self.context.pages[0]
        self._apply_cdp_overrides(self.page)
        return self

    def new_page(self) -> Page:
        """Создаёт страницу и сразу применяет CDP-подмену.

        Событие ``page`` доставляется асинхронно, поэтому страница, созданная
        через ``context.new_page()``, может успеть уйти в навигацию раньше
        подмены. Этот метод закрывает окно гонки.
        """
        assert self.context is not None
        page = self.context.new_page()
        self._apply_cdp_overrides(page)
        return page

    def _apply_cdp_overrides(self, page: Page) -> None:
        """Подмена UA/языков/Client Hints на уровне сети, а не только в JS.

        Опция ``locale`` в Playwright сама пишет Accept-Language и перебивает
        extra_http_headers, а sec-ch-* заголовки Chrome формирует сам из
        внутренних метаданных. Через CDP правим первоисточник, поэтому
        заголовки запроса и значения в JS перестают расходиться.
        """
        fp = self.fingerprint
        assert self.context is not None
        if any(patched is page for patched in self._patched_pages):
            return  # событие 'page' могло сработать уже после ручного вызова
        self._patched_pages.append(page)
        try:
            cdp = self.context.new_cdp_session(page)
            cdp.send("Network.enable", {})
            # Локаль: влияет и на Intl.resolvedOptions().locale, и на реальное
            # форматирование дат/чисел — проверяют и то, и другое.
            cdp.send("Emulation.setLocaleOverride", {"locale": fp.locale})
            cdp.send("Network.setUserAgentOverride", {
                "userAgent": fp.user_agent,
                # Простой список без q-весов: Chrome расставит их сам, как у
                # обычного пользователя (передашь готовые — получишь ";q=0.9;q=0.9").
                "acceptLanguage": ",".join(fp.languages),
                "platform": fp.platform,
                "userAgentMetadata": {
                    "brands": brand_list(fp.chrome_major),
                    "fullVersionList": [
                        {"brand": b["brand"],
                         "version": "99.0.0.0" if b["brand"] == "Not;A=Brand" else fp.chrome_full_version}
                        for b in brand_list(fp.chrome_major)
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
            })
            # Сессию держим открытой: после detach Chrome снимает override.
            self._cdp_sessions.append(cdp)
        except Exception:
            # Не критично: JS-патчи всё равно применены, расходятся только
            # HTTP-заголовки. Ронять из-за этого работу браузера незачем.
            pass

    def _sync_chrome_version(self) -> None:
        version = (self.browser.version if self.browser else "") or ""
        major = version.split(".")[0]
        if not major.isdigit():
            return
        fp = self.fingerprint
        fp.chrome_full_version = version
        fp.chrome_major = int(major)
        fp.user_agent = re.sub(r"Chrome/[\d.]+", f"Chrome/{major}.0.0.0", fp.user_agent)
        fp.app_version = fp.user_agent[len("Mozilla/"):]  # appVersion — это UA без префикса
        if self.context is not None:
            # Персистентный контекст уже создан — обновляем хотя бы заголовки.
            self.context.set_extra_http_headers(context_options(fp)["extra_http_headers"])

    def close(self) -> None:
        for closable in (self.context, self.browser):
            try:
                if closable:
                    closable.close()
            except Exception:  # браузер мог уже упасть — это не повод падать самим
                pass
        if self._pw:
            self._pw = None
            _release_playwright()

    def __enter__(self) -> "StealthBrowser":
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- диагностика ---------------------------------------------------------

    def read_fingerprint(self, page: Page | None = None) -> dict[str, Any]:
        """Считывает со страницы то, что реально видит сайт."""
        page = page or self.page
        assert page is not None
        if page.url in ("", "about:blank"):
            # Нужен защищённый origin: navigator.userAgentData и часть Crypto API
            # недоступны на about:blank и data:. Отдаём страницу через перехват
            # запроса — сеть при этом не нужна.
            page.route(f"{_LOCAL_ORIGIN}/**", lambda route: route.fulfill(
                status=200, content_type="text/html; charset=utf-8",
                body="<!doctype html><title>fingerprint</title>",
            ))
            page.goto(f"{_LOCAL_ORIGIN}/")
        return page.evaluate(_READ_FINGERPRINT_JS)


_READ_FINGERPRINT_JS = r"""
() => {
  const gl = document.createElement('canvas').getContext('webgl');
  const dbg = gl && gl.getExtension('WEBGL_debug_renderer_info');

  // Хеш канвы — то, чем сайты и различают браузеры.
  const canvas = document.createElement('canvas');
  canvas.width = 220; canvas.height = 60;
  const ctx = canvas.getContext('2d');
  ctx.textBaseline = 'top';
  ctx.font = '14px Arial';
  ctx.fillStyle = '#f60';
  ctx.fillRect(0, 0, 100, 20);
  ctx.fillStyle = '#069';
  ctx.fillText('fingerprint-check \u{1F512}', 2, 15);
  const dataUrl = canvas.toDataURL();
  let hash = 0;
  for (let i = 0; i < dataUrl.length; i++) {
    hash = ((hash << 5) - hash + dataUrl.charCodeAt(i)) | 0;
  }

  return {
    userAgent: navigator.userAgent,
    platform: navigator.platform,
    vendor: navigator.vendor,
    webdriver: navigator.webdriver,
    languages: navigator.languages,
    language: navigator.language,
    hardwareConcurrency: navigator.hardwareConcurrency,
    deviceMemory: navigator.deviceMemory,
    maxTouchPoints: navigator.maxTouchPoints,
    pluginsCount: navigator.plugins.length,
    pluginNames: Array.from(navigator.plugins).map(p => p.name),
    uaDataPlatform: navigator.userAgentData ? navigator.userAgentData.platform : null,
    uaDataBrands: navigator.userAgentData ? navigator.userAgentData.brands : null,
    screen: { width: screen.width, height: screen.height,
              availWidth: screen.availWidth, availHeight: screen.availHeight,
              colorDepth: screen.colorDepth },
    window: { innerWidth: window.innerWidth, innerHeight: window.innerHeight,
              outerWidth: window.outerWidth, outerHeight: window.outerHeight,
              devicePixelRatio: window.devicePixelRatio },
    timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    intlLocale: Intl.DateTimeFormat().resolvedOptions().locale,
    localizedMonth: new Date(0).toLocaleString(undefined, { month: 'long' }),
    webglVendor: dbg ? gl.getParameter(dbg.UNMASKED_VENDOR_WEBGL) : null,
    webglRenderer: dbg ? gl.getParameter(dbg.UNMASKED_RENDERER_WEBGL) : null,
    canvasHash: hash,
    hasChromeObject: typeof window.chrome === 'object' && !!window.chrome.runtime,
    webdriverToStringLooksNative:
      Object.getOwnPropertyDescriptor(Navigator.prototype, 'webdriver').get.toString()
        .includes('[native code]'),
  };
}
"""
