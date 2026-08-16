"""Генерация согласованных профилей отпечатка браузера.

Главное правило: все поля отпечатка должны быть согласованы между собой.
Windows-овый User-Agent с рендерером Apple M1 и таймзоной Asia/Tokyo —
это более заметный сигнал, чем вообще любой честный отпечаток.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass(frozen=True)
class GPU:
    vendor: str  # то, что вернёт WEBGL_debug_renderer_info UNMASKED_VENDOR
    renderer: str  # ... UNMASKED_RENDERER


@dataclass(frozen=True)
class OSPreset:
    """Набор взаимно согласованных характеристик одной ОС."""

    key: str
    platform: str  # navigator.platform
    ua_platform: str  # часть User-Agent внутри скобок
    ua_data_platform: str  # navigator.userAgentData.platform
    ua_data_platform_version: str
    ua_data_architecture: str
    ua_data_bitness: str
    gpus: tuple[GPU, ...]
    screens: tuple[tuple[int, int], ...]
    # высота панели задач / дока — влияет на screen.availHeight
    chrome_ui_height: int = 88
    taskbar: int = 40
    device_scale_factors: tuple[float, ...] = (1.0,)


WINDOWS = OSPreset(
    key="windows",
    platform="Win32",
    ua_platform="Windows NT 10.0; Win64; x64",
    ua_data_platform="Windows",
    ua_data_platform_version="15.0.0",
    ua_data_architecture="x86",
    ua_data_bitness="64",
    gpus=(
        GPU("Google Inc. (NVIDIA)",
            "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        GPU("Google Inc. (NVIDIA)",
            "ANGLE (NVIDIA, NVIDIA GeForce GTX 1650 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        GPU("Google Inc. (Intel)",
            "ANGLE (Intel, Intel(R) UHD Graphics 630 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
        GPU("Google Inc. (AMD)",
            "ANGLE (AMD, AMD Radeon RX 6600 Direct3D11 vs_5_0 ps_5_0, D3D11)"),
    ),
    screens=((1920, 1080), (2560, 1440), (1536, 864), (1366, 768)),
    taskbar=40,
    device_scale_factors=(1.0, 1.25, 1.5),
)

MACOS = OSPreset(
    key="macos",
    platform="MacIntel",
    ua_platform="Macintosh; Intel Mac OS X 10_15_7",
    ua_data_platform="macOS",
    ua_data_platform_version="15.5.0",
    ua_data_architecture="arm",
    ua_data_bitness="64",
    gpus=(
        GPU("Google Inc. (Apple)", "ANGLE (Apple, ANGLE Metal Renderer: Apple M1 Pro, Unspecified Version)"),
        GPU("Google Inc. (Apple)", "ANGLE (Apple, ANGLE Metal Renderer: Apple M2, Unspecified Version)"),
        GPU("Google Inc. (Apple)", "ANGLE (Apple, ANGLE Metal Renderer: Apple M3 Max, Unspecified Version)"),
    ),
    screens=((1728, 1117), (1512, 982), (2560, 1440), (1920, 1080)),
    taskbar=25,  # menu bar
    device_scale_factors=(2.0,),
)

LINUX = OSPreset(
    key="linux",
    platform="Linux x86_64",
    ua_platform="X11; Linux x86_64",
    ua_data_platform="Linux",
    ua_data_platform_version="6.8.0",
    ua_data_architecture="x86",
    ua_data_bitness="64",
    gpus=(
        GPU("Google Inc. (Intel)", "ANGLE (Intel, Mesa Intel(R) UHD Graphics 620 (KBL GT2), OpenGL 4.6)"),
        GPU("Google Inc. (AMD)", "ANGLE (AMD, AMD Radeon Graphics (radeonsi renoir LLVM 17.0.6), OpenGL 4.6)"),
    ),
    screens=((1920, 1080), (2560, 1440), (1920, 1200)),
    taskbar=48,
)

OS_PRESETS = {p.key: p for p in (WINDOWS, MACOS, LINUX)}

# Локаль -> (языки Accept-Language, правдоподобные таймзоны)
LOCALES: dict[str, tuple[list[str], list[str]]] = {
    "en-US": (["en-US", "en"], ["America/New_York", "America/Chicago", "America/Los_Angeles"]),
    "en-GB": (["en-GB", "en"], ["Europe/London"]),
    "de-DE": (["de-DE", "de", "en-US", "en"], ["Europe/Berlin"]),
    "fr-FR": (["fr-FR", "fr", "en-US", "en"], ["Europe/Paris"]),
    "es-ES": (["es-ES", "es", "en"], ["Europe/Madrid"]),
    "pl-PL": (["pl-PL", "pl", "en-US", "en"], ["Europe/Warsaw"]),
    "ru-RU": (["ru-RU", "ru", "en-US", "en"], ["Europe/Moscow", "Asia/Yekaterinburg"]),
    "pt-BR": (["pt-BR", "pt", "en-US", "en"], ["America/Sao_Paulo"]),
    "ja-JP": (["ja-JP", "ja", "en-US", "en"], ["Asia/Tokyo"]),
}

# Значения, которые реально встречаются у обычных пользователей.
HARDWARE_CONCURRENCY = (4, 6, 8, 8, 12, 16)
DEVICE_MEMORY = (4, 8, 8, 8, 16)


@dataclass
class Fingerprint:
    """Полный набор значений, которые увидит страница."""

    seed: int
    os_key: str
    platform: str
    user_agent: str
    app_version: str
    chrome_major: int
    chrome_full_version: str
    ua_data_platform: str
    ua_data_platform_version: str
    ua_data_architecture: str
    ua_data_bitness: str
    ua_data_model: str
    locale: str
    languages: list[str]
    timezone: str
    screen_width: int
    screen_height: int
    avail_width: int
    avail_height: int
    color_depth: int
    device_scale_factor: float
    viewport_width: int
    viewport_height: int
    outer_height_delta: int
    hardware_concurrency: int
    device_memory: int
    max_touch_points: int
    webgl_vendor: str
    webgl_renderer: str
    canvas_noise: float
    audio_noise: float
    extra: dict[str, Any] = field(default_factory=dict)

    # ---- удобные производные значения -------------------------------------

    @property
    def accept_language(self) -> str:
        """Заголовок Accept-Language, согласованный с navigator.languages."""
        parts = [self.languages[0]]
        for i, lang in enumerate(self.languages[1:], start=1):
            parts.append(f"{lang};q={max(0.1, 1 - i * 0.1):.1f}")
        return ",".join(parts)

    @property
    def sec_ch_ua(self) -> str:
        """Client Hint sec-ch-ua в том же порядке брендов, что и в JS."""
        brands = brand_list(self.chrome_major)
        return ", ".join(f'"{b["brand"]}";v="{b["version"]}"' for b in brands)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def summary(self) -> str:
        return (
            f"{self.os_key} | Chrome {self.chrome_full_version} | {self.locale} / {self.timezone}\n"
            f"screen {self.screen_width}x{self.screen_height}@{self.device_scale_factor} | "
            f"cpu {self.hardware_concurrency} | ram {self.device_memory}GB\n"
            f"gpu  {self.webgl_renderer}"
        )


def brand_list(chrome_major: int) -> list[dict[str, str]]:
    """navigator.userAgentData.brands в формате, который отдаёт настоящий Chrome."""
    return [
        {"brand": "Not;A=Brand", "version": "99"},
        {"brand": "Chromium", "version": str(chrome_major)},
        {"brand": "Google Chrome", "version": str(chrome_major)},
    ]


def _seed_from(value: str | int | None) -> int:
    """Строковый seed -> стабильное 32-битное число (для воспроизводимости)."""
    if value is None:
        return random.getrandbits(32)
    if isinstance(value, int):
        return value & 0xFFFFFFFF
    digest = hashlib.sha256(value.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big")


def build_fingerprint(
    seed: str | int | None = None,
    os_key: str | None = None,
    locale: str | None = None,
    chrome_full_version: str = "140.0.7339.80",
) -> Fingerprint:
    """Собирает согласованный отпечаток.

    Один и тот же ``seed`` всегда даёт один и тот же профиль — это важно,
    если нужно, чтобы «пользователь» выглядел одинаково между запусками.
    """
    seed_int = _seed_from(seed)
    rnd = random.Random(seed_int)

    preset = OS_PRESETS[os_key] if os_key else rnd.choice(list(OS_PRESETS.values()))
    chrome_major = int(chrome_full_version.split(".")[0])

    loc = locale or rnd.choice(list(LOCALES))
    languages, timezones = LOCALES[loc]
    timezone = rnd.choice(timezones)

    screen_w, screen_h = rnd.choice(preset.screens)
    scale = rnd.choice(preset.device_scale_factors)
    gpu = rnd.choice(preset.gpus)

    # Окно браузера не бывает больше экрана; оставляем место под UI.
    outer_height_delta = preset.chrome_ui_height
    viewport_w = screen_w - rnd.choice((0, 0, 120, 240))
    viewport_h = screen_h - preset.taskbar - outer_height_delta - rnd.choice((0, 0, 60))

    return Fingerprint(
        seed=seed_int,
        os_key=preset.key,
        platform=preset.platform,
        user_agent=(
            f"Mozilla/5.0 ({preset.ua_platform}) AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{chrome_major}.0.0.0 Safari/537.36"
        ),
        app_version=(
            f"5.0 ({preset.ua_platform}) AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{chrome_major}.0.0.0 Safari/537.36"
        ),
        chrome_major=chrome_major,
        chrome_full_version=chrome_full_version,
        ua_data_platform=preset.ua_data_platform,
        ua_data_platform_version=preset.ua_data_platform_version,
        ua_data_architecture=preset.ua_data_architecture,
        ua_data_bitness=preset.ua_data_bitness,
        ua_data_model="",
        locale=loc,
        languages=list(languages),
        timezone=timezone,
        screen_width=screen_w,
        screen_height=screen_h,
        avail_width=screen_w,
        avail_height=screen_h - preset.taskbar,
        color_depth=24,
        device_scale_factor=scale,
        viewport_width=viewport_w,
        viewport_height=viewport_h,
        outer_height_delta=outer_height_delta,
        hardware_concurrency=rnd.choice(HARDWARE_CONCURRENCY),
        device_memory=rnd.choice(DEVICE_MEMORY),
        max_touch_points=0,
        webgl_vendor=gpu.vendor,
        webgl_renderer=gpu.renderer,
        # Шум канвы/аудио: маленький, но стабильный для этого профиля.
        canvas_noise=rnd.uniform(0.0005, 0.003),
        audio_noise=rnd.uniform(1e-7, 5e-7),
    )
