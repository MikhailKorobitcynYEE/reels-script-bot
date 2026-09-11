"""Тесты разбивки длинных сообщений. Запуск: python -m unittest tests.test_split -v"""

import unittest

from utils import split_message


class TestSplitMessage(unittest.TestCase):
    def test_short_text_unchanged(self):
        self.assertEqual(split_message("привет"), ["привет"])

    def test_empty(self):
        self.assertEqual(split_message(""), [])
        self.assertEqual(split_message("   "), [])

    def test_exact_limit(self):
        text = "а" * 3900
        parts = split_message(text)
        self.assertEqual(len(parts), 1)

    def test_splits_on_paragraphs(self):
        paragraphs = [f"Абзац номер {i}. " + "текст " * 100 for i in range(10)]
        text = "\n\n".join(paragraphs)
        parts = split_message(text)
        self.assertGreater(len(parts), 1)
        for part in parts:
            self.assertLessEqual(len(part), 3900)
        # Ничего не потеряли и порядок сохранили
        self.assertEqual("".join(p.replace("\n", "") for p in parts).replace(" ", ""),
                         text.replace("\n", "").replace(" ", ""))

    def test_splits_on_lines_when_no_paragraphs(self):
        lines = ["строка без пустых строк между ними " * 30] * 50
        text = "\n".join(lines)
        parts = split_message(text)
        self.assertGreater(len(parts), 1)
        for part in parts:
            self.assertLessEqual(len(part), 3900)

    def test_splits_on_words_when_no_breaks(self):
        text = "слово " * 2000
        parts = split_message(text)
        self.assertGreater(len(parts), 1)
        for part in parts:
            self.assertLessEqual(len(part), 3900)

    def test_giant_single_word(self):
        text = "я" * 10000
        parts = split_message(text)
        self.assertGreater(len(parts), 1)
        for part in parts:
            self.assertLessEqual(len(part), 3900)
        self.assertEqual(sum(len(p) for p in parts), 10000)

    def test_custom_limit(self):
        text = "первый\n\nвторой\n\nтретий"
        parts = split_message(text, max_len=12)
        # «первый\n\nвторой» — это 14 символов, в лимит 12 не влезает,
        # поэтому каждый абзац уходит отдельным сообщением
        self.assertEqual(parts, ["первый", "второй", "третий"])

        parts = split_message(text, max_len=14)
        self.assertEqual(parts, ["первый\n\nвторой", "третий"])


if __name__ == "__main__":
    unittest.main()
