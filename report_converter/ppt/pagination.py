"""Split generated bullet rows into slide-sized pages."""

from __future__ import annotations

from ..common import normalize_text, slide_caps


def _page_budget(title: str, has_table: bool) -> tuple[int, int]:
    bucket = slide_caps(title, has_table)
    max_rows = bucket["page_size"]
    title = normalize_text(title)
    if has_table:
        return 110, max_rows
    if "仲裁" in title or "诉讼" in title or "合同管理" in title or "典型协议" in title:
        return 460, max_rows
    if "概述" in title or "合规" in title or "知识产权" in title:
        return 400, max_rows
    return 420, max_rows


def _row_weight(text: str) -> int:
    text = normalize_text(text)
    if not text:
        return 0
    extra = 0
    if "；" in text or ";" in text:
        extra += 6
    if any(ch.isdigit() for ch in text):
        extra += 4
    return len(text) + extra


def split_into_pages(bullets: list[str], title: str, has_table: bool) -> list[list[str]]:
    if not bullets:
        return [[]]
    budget, max_rows = _page_budget(title, has_table)
    target_fill = int(budget * 0.68)
    pages: list[list[str]] = []
    current: list[str] = []
    used = 0

    for bullet in bullets:
        weight = _row_weight(bullet)
        if not current:
            current = [bullet]
            used = weight
            continue

        over_rows = len(current) >= max_rows
        over_budget = used + weight > budget
        enough_fill = used >= target_fill

        if over_rows or (over_budget and enough_fill):
            pages.append(current)
            current = [bullet]
            used = weight
            continue

        current.append(bullet)
        used += weight

    if current:
        pages.append(current)
    return pages


