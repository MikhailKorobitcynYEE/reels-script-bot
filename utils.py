"""Утилиты: разбивка длинного текста на сообщения Telegram."""

from __future__ import annotations

# Telegram жёсткий лимит — 4096 символов на сообщение.
# Берём запас на служебные символы и переносы.
MAX_MESSAGE_LEN = 3900


def split_message(text: str, max_len: int = MAX_MESSAGE_LEN) -> list[str]:
    """Разбивает текст на части не длиннее max_len.

    Режет по границам абзацев (\n\n), затем по строкам (\n),
    и только в крайнем случае — по словам.
    """
    text = text.strip()
    if not text:
        return []
    if len(text) <= max_len:
        return [text]

    parts: list[str] = []
    current = ""

    paragraphs = text.split("\n\n")
    for paragraph in paragraphs:
        candidate = f"{current}\n\n{paragraph}" if current else paragraph

        if len(candidate) <= max_len:
            current = candidate
            continue

        # Абзац не влезает целиком — сначала закроем текущую часть
        if current:
            parts.append(current)
            current = ""

        # Очень длинный абзац — режем по строкам
        if len(paragraph) > max_len:
            for line in paragraph.split("\n"):
                line_candidate = f"{current}\n{line}" if current else line
                if len(line_candidate) <= max_len:
                    current = line_candidate
                    continue
                if current:
                    parts.append(current)
                    current = ""
                # Очень длинная строка — режем по словам
                if len(line) > max_len:
                    words = line.split(" ")
                    for word in words:
                        word_candidate = f"{current} {word}" if current else word
                        if len(word_candidate) <= max_len:
                            current = word_candidate
                        else:
                            if current:
                                parts.append(current)
                            # Слово само по себе длиннее лимита — режем жёстко
                            while len(word) > max_len:
                                parts.append(word[:max_len])
                                word = word[max_len:]
                            current = word
                else:
                    current = line
        else:
            current = paragraph

    if current:
        parts.append(current)

    return [p.strip() for p in parts if p.strip()]
