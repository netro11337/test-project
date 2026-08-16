# chrome-fingerprint

Запуск Chromium через Playwright с подменой отпечатка браузера: согласованный
профиль (ОС, экран, GPU, локаль, таймзона, железо) + шум в canvas/audio.

Для чего это нужно: тестировать собственную антибот-/антифрод-логику, проверять,
что и как о вас собирают сайты, и снижать уникальность браузера при автоматизации.

## Установка

```bash
pip install -r requirements.txt
playwright install chromium
```

## Быстрый старт

```python
from chrome_fingerprint import StealthBrowser

# seed — «личность»: один и тот же seed всегда даёт один и тот же профиль
with StealthBrowser(seed="user-42", headless=False) as browser:
    browser.page.goto("https://example.com")
    print(browser.page.title())
```

Явное управление профилем:

```python
from chrome_fingerprint import StealthBrowser, build_fingerprint

fp = build_fingerprint(seed="user-42", os_key="macos", locale="de-DE")
print(fp.summary())

with StealthBrowser(fingerprint=fp, proxy={"server": "http://user:pass@host:3128"}) as browser:
    browser.page.goto("https://example.com")
    page2 = browser.new_page()          # не context.new_page(): обёртка ставит подмену
    print(browser.read_fingerprint())    # что реально видит страница
```

Демо и проверка:

```bash
python demo.py --seed user-42 --os windows --locale ru-RU   # офлайн, без сети
python demo.py --compare                                    # два профиля рядом
python demo.py --url https://abrahamjuliot.github.io/creepjs/ --headful --wait 20
pytest -q                                                   # 15 тестов, сеть не нужна
```

## Что именно подменяется

| Слой | Что |
|---|---|
| Запуск | `--disable-blink-features=AutomationControlled`, снятие `--enable-automation` |
| Сеть (CDP) | `User-Agent`, `Accept-Language` с q-весами, `sec-ch-ua*`, метаданные Client Hints, локаль (`Emulation.setLocaleOverride`) |
| Контекст | таймзона, размер экрана и вьюпорта, `deviceScaleFactor` |
| JS | `navigator.webdriver`, `userAgent`/`platform`/`vendor`/`languages`, `userAgentData` + `getHighEntropyValues`, `hardwareConcurrency`, `deviceMemory`, `screen.*`, `outerWidth/Height`, `devicePixelRatio`, `navigator.plugins`/`mimeTypes`, `window.chrome`, `Permissions.query`, WebGL vendor/renderer, шум canvas и AudioContext |

Два принципа, на которых всё держится:

1. **Согласованность.** Профиль собирается целиком: Windows-UA идёт вместе с
   `Win32`, D3D11-рендерером и правдоподобным разрешением. Рассогласование
   (UA — Windows, WebGL — Apple M1) заметнее, чем честный отпечаток.
2. **Патчи не должны выдавать себя.** Все геттеры ставятся там, где они
   объявлены (обычно на прототипе), а `Function.prototype.toString`
   проксируется, чтобы подменённые функции возвращали `[native code]`.
   Тест `test_no_webdriver_flag` это проверяет.

`seed` фиксирует профиль: одинаковый seed → одинаковые UA, экран, GPU и шум
канвы между запусками; разные seed → разные «пользователи».

## Ограничения

Что этот код **не** делает — и о чём стоит знать заранее:

- **Шрифты.** Список установленных шрифтов и метрики их отрисовки не
  подменяются; на Linux-хосте набор шрифтов отличается от Windows-профиля.
- **WebRTC.** Реальный IP может утечь через ICE-кандидатов. Нужен proxy/VPN на
  уровне сети (параметр `proxy=` — только HTTP-прокси браузера).
- **TLS/HTTP2-отпечаток.** JA3/JA4 и порядок заголовков определяются самим
  Chromium; из JS это не меняется.
- **Поведение.** Движения мыши, тайминги ввода, скорость навигации — отдельный
  и часто более весомый сигнал, чем статический отпечаток.
- **GPU-рендер.** WebGL-вендор подменён строкой, но реальная отрисовка
  (`readPixels`-хеш) идёт на GPU/SwiftShader хоста и профилю не соответствует.
- Шум в canvas ломает совпадение хешей, но сам факт нестабильного хеша между
  сайтами — тоже сигнал. Здесь шум детерминированный: внутри профиля хеш
  постоянный (`test_canvas_hash_is_stable_within_profile`).

## Структура

```
chrome_fingerprint/
  profiles.py   генерация согласованного профиля (пресеты ОС, GPU, локали)
  stealth.js    init-скрипт: патчи navigator/screen/WebGL/canvas/audio
  browser.py    запуск Chromium, CDP-подмена, чтение итогового отпечатка
demo.py         CLI-демо
tests/          офлайн-проверки (перехват запросов, сеть не нужна)
```

## Ответственность

Инструмент для тестирования своих систем, исследований и приватности.
Обход защит чужих сервисов, нарушение их правил использования и любые действия
без разрешения владельца — не то, для чего он написан.
