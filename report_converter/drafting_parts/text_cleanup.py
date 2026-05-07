"""Clean, compress, and deduplicate generated slide bullet text."""

from __future__ import annotations

import re

from ..common import normalize_text, slide_caps
from ..models import SlideDraft, TemplateSlide
from .rules import GENERIC_PHRASES
from .source_selection import title_profile


def extract_detail_tokens(line: str) -> list[str]:
    line = normalize_text(line)
    tokens: list[str] = []
    patterns = [
        r"BU\d+",
        r"TA\d+",
        r"\d+\s*月\s*\d+\s*日",
        r"\d+/\d+",
        r"\d+(?:件|万|万元|亿|亿元|天)",
        r"[A-Z]{2,}(?:[-_][A-Z0-9]+)?",
        r"(?:[\u4e00-\u9fff]{2,10}案)",
        r"(?:[\u4e00-\u9fffA-Za-z0-9\-]{2,20}项目)",
    ]
    for pattern in patterns:
        tokens.extend(re.findall(pattern, line))
    out: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if token not in seen:
            seen.add(token)
            out.append(token)
    return out


def clean_generated_line(line: str) -> str:
    line = normalize_text(line)
    line = re.sub(r"^(?:[-•*]\s*|\d+[.)、]\s*)", "", line)
    line = line.replace("...", "").replace("…", "")
    return line.strip("；;，,。 ")


def abbreviate_for_ppt(text: str) -> str:
    text = normalize_text(text)
    replacements = [
        ("进行", ""),
        ("开展", ""),
        ("相关", ""),
        ("目前", ""),
        ("已经", "已"),
        ("正在", "正"),
        ("对于", "对"),
        ("以及", "及"),
        ("并且", "并"),
    ]
    for src, dst in replacements:
        text = text.replace(src, dst)
    return normalize_text(text)


def compress_for_ppt(line: str, title: str) -> str:
    line = abbreviate_for_ppt(clean_generated_line(line))
    if len(line) <= 80:
        return line
    parts = re.split(r"[；;。]", line)
    parts = [normalize_text(x) for x in parts if normalize_text(x)]
    if len(parts) <= 1:
        return line
    chosen: list[str] = []
    for part in parts:
        if has_specific_signal(part, title):
            chosen.append(part)
        if sum(len(x) for x in chosen) >= 80:
            break
    return "；".join(chosen) if chosen else parts[0]


def detail_fallback_line(source: str, title: str) -> str:
    line = compress_for_ppt(source, title)
    if not has_specific_signal(line, title):
        tokens = extract_detail_tokens(source)
        if tokens:
            line = f"{line}（{ ' / '.join(tokens[:3]) }）"
    return line


def is_too_generic(line: str) -> bool:
    line = normalize_text(line)
    return any(p in line for p in GENERIC_PHRASES) or len(extract_detail_tokens(line)) == 0


def has_specific_signal(line: str, title: str) -> bool:
    if extract_detail_tokens(line):
        return True
    profile = title_profile(title)
    return any(token in line for token in profile["must_any"])


def is_near_copy(line: str, sources: list[str]) -> bool:
    key = normalize_text(line)
    for prev in sources:
        prev = normalize_text(prev)
        short, long_ = (key, prev) if len(key) <= len(prev) else (prev, key)
        if len(short) >= 24 and short in long_ and (len(short) / max(len(long_), 1)) >= 0.92:
            return True
    return False


def canonical_line(text: str) -> str:
    text = normalize_text(text).lower()
    return re.sub(r"[\W_]+", "", text)


def is_duplicate_global(line: str, seen: list[str]) -> bool:
    key = canonical_line(line)
    return any(key == prev or key in prev or prev in key for prev in seen if prev)


def dedupe_drafts_across_slides(
    drafts: list[SlideDraft],
    template_slides: list[TemplateSlide],
    selected_sources: dict[int, list[str]],
) -> list[SlideDraft]:
    by_idx = {draft.slide_index: draft for draft in drafts}
    seen: list[str] = []
    out: list[SlideDraft] = []

    for slide in template_slides:
        draft = by_idx.get(slide.slide_index, SlideDraft(slide.slide_index, []))
        caps = slide_caps(slide.title, slide.has_table)
        target_max = caps["bullet_limit"]
        deduped: list[str] = []
        for line in draft.bullets:
            if is_duplicate_global(line, seen):
                continue
            deduped.append(line)
            seen.append(canonical_line(line))
            if len(deduped) >= target_max:
                break

        if len(deduped) < target_max:
            for src in selected_sources.get(slide.slide_index, []):
                candidate = detail_fallback_line(src, slide.title)
                if is_duplicate_global(candidate, seen):
                    continue
                deduped.append(candidate)
                seen.append(canonical_line(candidate))
                if len(deduped) >= target_max:
                    break

        out.append(SlideDraft(slide.slide_index, deduped))
    return out


