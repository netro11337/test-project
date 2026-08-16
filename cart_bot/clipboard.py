"""Ctrl+V/C/X/A при любой раскладке клавиатуры.

Штатные привязки Tkinter висят на букве: `<Control-v>`. При русской раскладке
та же клавиша приходит как `м`, привязка не находится, и вставка молча не
работает. Ловим такие нажатия отдельно — по физическому коду клавиши и по
кириллическим именам, — и выполняем действие руками.
"""

from __future__ import annotations

from typing import Optional

# tkinter импортируется внутри функций, которым он реально нужен: так разбор
# нажатия (resolve_action) остаётся проверяемым без графической оболочки.

PASTE = "paste"
COPY = "copy"
CUT = "cut"
SELECT_ALL = "select_all"

# Латиница обрабатывается штатными привязками Tk. Трогать её нельзя, иначе
# текст вставится дважды.
_LATIN = {"v": PASTE, "c": COPY, "x": CUT, "a": SELECT_ALL}

# Windows отдаёт код физической клавиши независимо от раскладки.
_KEYCODES = {86: PASTE, 67: COPY, 88: CUT, 65: SELECT_ALL}

# X11 (Linux) отдаёт осмысленное имя кириллической клавиши.
_KEYSYMS = {
    "cyrillic_em": PASTE,  # м — та же клавиша, что v
    "cyrillic_es": COPY,  # с
    "cyrillic_che": CUT,  # ч
    "cyrillic_ef": SELECT_ALL,  # ф
}

_VIRTUAL_EVENTS = {PASTE: "<<Paste>>", COPY: "<<Copy>>", CUT: "<<Cut>>"}

# Виджеты, в которых имеет смысл вставлять и копировать.
_WIDGET_CLASSES = ("Text", "Entry", "TEntry", "Spinbox", "TSpinbox")


def resolve_action(keysym: str, keycode: int) -> Optional[str]:
    """Что нажали, независимо от раскладки. None — не наше сочетание.

    Латинские буквы возвращают None намеренно: их уже обработала штатная
    привязка Tk, и повторная обработка привела бы к двойной вставке.
    """
    key = (keysym or "").lower()
    if key in _LATIN:
        return None
    action = _KEYSYMS.get(key)
    if action is not None:
        return action
    return _KEYCODES.get(keycode)


def _select_all(widget) -> bool:
    import tkinter as tk

    if isinstance(widget, tk.Text):
        widget.tag_add("sel", "1.0", "end-1c")
        widget.mark_set("insert", "1.0")
        return True
    try:
        widget.select_range(0, "end")
        return True
    except (tk.TclError, AttributeError):
        return False


def _apply(widget, action: str) -> bool:
    import tkinter as tk

    if action == SELECT_ALL:
        return _select_all(widget)
    try:
        widget.event_generate(_VIRTUAL_EVENTS[action])
        return True
    except tk.TclError:
        return False


def _on_control_key(event):
    action = resolve_action(event.keysym, event.keycode)
    if action is None:
        return None
    if not _apply(event.widget, action):
        return None
    # «break» гасит дальнейшую обработку: иначе символ клавиши может ещё и
    # напечататься в поле.
    return "break"


def enable_clipboard_hotkeys(root: tk.Misc) -> None:
    """Включает Ctrl+V/C/X/A при любой раскладке во всех полях ввода.

    Привязка идёт на класс виджета, а не на конкретное поле, поэтому работает
    и во вкладках потоков, которые пересоздаются при смене их числа.
    """
    for widget_class in _WIDGET_CLASSES:
        root.bind_class(widget_class, "<Control-KeyPress>", _on_control_key, add="+")
