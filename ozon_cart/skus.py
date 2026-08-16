"""Разбор и распределение SKU по потокам."""

from __future__ import annotations

import re
from typing import Iterable, List

# SKU Ozon — числовой идентификатор. Из ссылки вида
# https://www.ozon.ru/product/nazvanie-tovara-1234567890/ берём последнее число.
_SEPARATORS = re.compile(r"[,;\s]+")
_URL_SKU = re.compile(r"/product/(?:[^/?#]*?-)?(\d{6,})", re.IGNORECASE)
_DIGITS = re.compile(r"\d{6,}")

MIN_SKU = 10
MAX_SKU = 40


def parse_skus(text: str) -> List[str]:
    """Достаёт SKU из произвольного текста: через запятую, с новых строк, ссылки.

    Порядок сохраняется, дубликаты убираются.
    """
    found: List[str] = []
    seen = set()
    for token in _SEPARATORS.split(text or ""):
        token = token.strip()
        if not token:
            continue
        match = _URL_SKU.search(token)
        if match:
            sku = match.group(1)
        else:
            digits = _DIGITS.findall(token)
            if not digits:
                continue
            # Для «голого» токена берём самое длинное число: так ссылка с
            # мусорными цифрами в slug не подменяет настоящий SKU.
            sku = max(digits, key=len)
        if sku not in seen:
            seen.add(sku)
            found.append(sku)
    return found


def split_evenly(skus: Iterable[str], threads: int) -> List[List[str]]:
    """Режет список на `threads` частей максимально ровно.

    Раздаём по кругу, а не подряд: если часть SKU «тяжёлая» (медленная
    страница), нагрузка размажется по потокам, а не осядет в одном.
    """
    if threads < 1:
        raise ValueError("Число потоков должно быть >= 1")
    batches: List[List[str]] = [[] for _ in range(threads)]
    for index, sku in enumerate(skus):
        batches[index % threads].append(sku)
    return batches


def dedupe_batches(batches: Iterable[Iterable[str]]) -> List[List[str]]:
    """Чистит дубликаты внутри каждого потока.

    Между потоками дубликаты не трогаем: у каждого потока своя корзина, и
    один и тот же SKU в двух корзинах — это осознанный сценарий, а не ошибка.
    """
    result: List[List[str]] = []
    for batch in batches:
        seen = set()
        cleaned = []
        for sku in batch:
            if sku in seen:
                continue
            seen.add(sku)
            cleaned.append(sku)
        result.append(cleaned)
    return result
