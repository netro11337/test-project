"""Проверки подмены. Работают офлайн — сеть не нужна.

    pytest -q
"""

from __future__ import annotations

import pytest

from chrome_fingerprint import StealthBrowser, build_fingerprint


@pytest.fixture(scope="module")
def windows_browser():
    fp = build_fingerprint(seed="test-windows", os_key="windows", locale="de-DE")
    with StealthBrowser(fingerprint=fp) as browser:
        yield browser, fp, browser.read_fingerprint()


# --- профиль -------------------------------------------------------------


def test_seed_is_reproducible():
    a = build_fingerprint(seed="stable")
    b = build_fingerprint(seed="stable")
    assert a.to_dict() == b.to_dict()


def test_different_seeds_differ():
    a = build_fingerprint(seed="one")
    b = build_fingerprint(seed="two")
    assert a.to_dict() != b.to_dict()


def test_profile_is_internally_consistent():
    for os_key in ("windows", "macos", "linux"):
        fp = build_fingerprint(seed=f"consistency-{os_key}", os_key=os_key)
        assert fp.avail_height <= fp.screen_height
        assert fp.avail_width <= fp.screen_width
        assert fp.viewport_width <= fp.screen_width
        assert fp.viewport_height <= fp.screen_height
        assert fp.languages[0] == fp.locale
        assert fp.accept_language.startswith(fp.locale)
        assert fp.locale in fp.accept_language


# --- то, что видит страница ---------------------------------------------


def test_no_webdriver_flag(windows_browser):
    _, _, seen = windows_browser
    assert seen["webdriver"] is False
    # Геттер должен выглядеть нативным, иначе патч сам себя выдаёт.
    assert seen["webdriverToStringLooksNative"] is True


def test_navigator_matches_profile(windows_browser):
    _, fp, seen = windows_browser
    assert seen["userAgent"] == fp.user_agent
    assert seen["platform"] == fp.platform
    assert seen["vendor"] == "Google Inc."
    assert seen["languages"] == fp.languages
    assert seen["language"] == fp.locale
    assert seen["hardwareConcurrency"] == fp.hardware_concurrency
    assert seen["deviceMemory"] == fp.device_memory
    assert "Windows" in seen["userAgent"]


def test_client_hints_match_user_agent(windows_browser):
    _, fp, seen = windows_browser
    assert seen["uaDataPlatform"] == fp.ua_data_platform
    brands = {b["brand"]: b["version"] for b in seen["uaDataBrands"]}
    assert brands.get("Google Chrome") == str(fp.chrome_major)
    assert f"Chrome/{fp.chrome_major}." in seen["userAgent"]


def test_screen_and_window(windows_browser):
    _, fp, seen = windows_browser
    assert seen["screen"]["width"] == fp.screen_width
    assert seen["screen"]["height"] == fp.screen_height
    assert seen["screen"]["availHeight"] == fp.avail_height
    assert seen["window"]["devicePixelRatio"] == fp.device_scale_factor
    assert seen["window"]["outerHeight"] > seen["window"]["innerHeight"]


def test_timezone_applied(windows_browser):
    _, fp, seen = windows_browser
    assert seen["timezone"] == fp.timezone


def test_webgl_reports_fake_gpu(windows_browser):
    _, fp, seen = windows_browser
    assert seen["webglVendor"] == fp.webgl_vendor
    assert seen["webglRenderer"] == fp.webgl_renderer
    assert "SwiftShader" not in seen["webglRenderer"]  # маркер headless


def test_plugins_are_not_empty(windows_browser):
    _, _, seen = windows_browser
    assert seen["pluginsCount"] >= 5
    assert "Chrome PDF Viewer" in seen["pluginNames"]


def test_chrome_object_present(windows_browser):
    _, _, seen = windows_browser
    assert seen["hasChromeObject"] is True


# --- HTTP-заголовки ------------------------------------------------------


def test_http_headers_match_profile(windows_browser):
    """Сервер должен видеть те же UA/язык/платформу, что и JS на странице."""
    browser, fp, _ = windows_browser
    captured: dict[str, str] = {}

    def handler(route):
        # именно all_headers(): .headers отдаёт приблизительный набор,
        # без заголовков, которые Chrome дописывает сам
        captured.update(route.request.all_headers())
        route.fulfill(status=200, content_type="text/html", body="<title>headers</title>")

    page = browser.new_page()  # не context.new_page(): подмену ставит обёртка
    page.route("https://headers.local/**", handler)
    page.goto("https://headers.local/")
    page.close()

    assert captured["user-agent"] == fp.user_agent
    assert captured["accept-language"] == fp.accept_language
    assert captured["sec-ch-ua-platform"].strip('"') == fp.ua_data_platform
    assert captured["sec-ch-ua-mobile"] == "?0"
    assert f'"Google Chrome";v="{fp.chrome_major}"' in captured["sec-ch-ua"]


# --- канва ---------------------------------------------------------------


def test_canvas_hash_differs_between_profiles():
    hashes = []
    for seed in ("canvas-a", "canvas-b"):
        fp = build_fingerprint(seed=seed, os_key="windows", locale="en-US")
        with StealthBrowser(fingerprint=fp) as browser:
            hashes.append(browser.read_fingerprint()["canvasHash"])
    assert hashes[0] != hashes[1], "разные профили обязаны давать разный хеш канвы"


def test_canvas_hash_is_stable_within_profile():
    fp = build_fingerprint(seed="canvas-stable", os_key="windows", locale="en-US")
    with StealthBrowser(fingerprint=fp) as browser:
        first = browser.read_fingerprint()["canvasHash"]
        second = browser.read_fingerprint()["canvasHash"]
    assert first == second, "внутри сессии отпечаток канвы должен быть постоянным"


def test_locale_affects_real_formatting(windows_browser):
    """Локаль должна быть настоящей, а не только в navigator.language."""
    _, fp, seen = windows_browser
    assert seen["intlLocale"] == fp.locale
    assert seen["localizedMonth"] == "Januar"  # de-DE, не English 'January'
