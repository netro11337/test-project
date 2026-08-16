import unittest

from cart_bot.clipboard import COPY, CUT, PASTE, SELECT_ALL, resolve_action

# Коды физических клавиш в Windows — они не зависят от раскладки.
VK_A, VK_C, VK_V, VK_X = 65, 67, 86, 88


class ResolveActionTest(unittest.TestCase):
    def test_russian_layout_by_keycode(self):
        # Windows, русская раскладка: буква приходит как «м», код — клавиши V.
        self.assertEqual(resolve_action("м", VK_V), PASTE)
        self.assertEqual(resolve_action("с", VK_C), COPY)
        self.assertEqual(resolve_action("ч", VK_X), CUT)
        self.assertEqual(resolve_action("ф", VK_A), SELECT_ALL)

    def test_russian_layout_by_keysym(self):
        # Linux/X11 сообщает осмысленное имя кириллической клавиши.
        self.assertEqual(resolve_action("Cyrillic_em", 0), PASTE)
        self.assertEqual(resolve_action("Cyrillic_es", 0), COPY)
        self.assertEqual(resolve_action("Cyrillic_che", 0), CUT)
        self.assertEqual(resolve_action("Cyrillic_ef", 0), SELECT_ALL)

    def test_latin_layout_is_left_to_tkinter(self):
        # Латиницу обрабатывает штатная привязка Tk. Возьмёмся и мы —
        # текст вставится дважды.
        for key, keycode in (("v", VK_V), ("c", VK_C), ("x", VK_X), ("a", VK_A)):
            self.assertIsNone(resolve_action(key, keycode))

    def test_uppercase_keysym(self):
        # С зажатым Shift или Caps Lock имя клавиши приходит с заглавной.
        self.assertEqual(resolve_action("CYRILLIC_EM", 0), PASTE)
        self.assertIsNone(resolve_action("V", VK_V))

    def test_unrelated_keys_ignored(self):
        self.assertIsNone(resolve_action("s", 83))
        self.assertIsNone(resolve_action("Escape", 27))
        self.assertIsNone(resolve_action("", 0))

    def test_unknown_keysym_falls_back_to_keycode(self):
        # Некоторые сборки Windows отдают вместо имени «??».
        self.assertEqual(resolve_action("??", VK_V), PASTE)


if __name__ == "__main__":
    unittest.main()
