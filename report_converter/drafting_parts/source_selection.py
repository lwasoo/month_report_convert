"""Select source report lines for each template slide.

This module owns heading/title matching and source relevance scoring before drafting starts.
"""

from __future__ import annotations

import re
from ..common import log, normalize_text, section_bucket_for_title, slide_caps
from ..models import ReportSection, SelectedSources, TemplateSlide, TitleProfile
from .rules import (
    DATA_METRIC_EXCLUDE_KEYWORDS,
    DATA_METRIC_KEYWORDS,
    PREFERRED_HEADING_KEYWORDS,
    SECTION_BUCKET_KEYWORDS,
    SPECIFIC_SIGNAL_KEYWORDS,
    TITLE_KEYWORDS,
    TITLE_PROFILES,
    TITLE_SECTION_KEYWORDS,
    title_has,
)


def infer_section_bucket(section: ReportSection) -> str:
    heading = normalize_text(section.heading)
    body = " ".join(normalize_text(x) for x in section.items[:8] if normalize_text(x))
    text = f"{heading} {body}"
    scores: dict[str, int] = {k: 0 for k in SECTION_BUCKET_KEYWORDS}
    for bucket, words in SECTION_BUCKET_KEYWORDS.items():
        for word in words:
            if word in text:
                scores[bucket] += 2 if word in heading else 1
    best = max(scores.items(), key=lambda kv: kv[1])
    return best[0] if best[1] > 0 else "generic"


def section_keywords_for_title(title: str) -> list[str]:
    title = normalize_text(title)
    for markers, keywords in TITLE_SECTION_KEYWORDS:
        if title_has(title, markers):
            return keywords
    return []


def keywords_for_title(title: str) -> list[str]:
    title = normalize_text(title)
    out: list[str] = []
    for key, words in TITLE_KEYWORDS.items():
        if key in title:
            out.extend(words)
    return out or [title[:8]]


def preferred_heading_keywords(title: str) -> list[str]:
    title = normalize_text(title)
    for markers, keywords in PREFERRED_HEADING_KEYWORDS:
        if title_has(title, markers):
            return keywords
    return []


def required_terms_for_title(title: str) -> list[str]:
    title = normalize_text(title)
    if "337" in title:
        return ["337"]
    if "美国劳动诉讼" in title:
        return ["美国", "US", "劳动诉讼"]
    return []


def title_profile(title: str) -> TitleProfile:
    title = normalize_text(title)
    for markers, profile in TITLE_PROFILES:
        if title_has(title, markers):
            return profile
    return {"must_any": [], "avoid": []}


def matches_title_profile(line: str, title: str) -> bool:
    prof = title_profile(title)
    must_any = prof["must_any"]
    avoid = prof["avoid"]
    if must_any and not any(token in line for token in must_any):
        return False
    if any(token in line for token in avoid):
        return False
    return True


def apply_title_strict_filter(title: str, lines: list[str]) -> list[str]:
    out: list[str] = []
    for line in lines:
        if matches_title_profile(line, title):
            out.append(line)
    return out or lines


def score_line(line: str, keywords: list[str]) -> int:
    line = normalize_text(line)
    score = 0
    for kw in keywords:
        if kw in line:
            score += 2 if len(kw) >= 3 else 1
    if re.search(r"\d", line):
        score += 1
    if any(token in line for token in SPECIFIC_SIGNAL_KEYWORDS):
        score += 1
    return score


def is_data_metric_line(line: str) -> bool:
    line = normalize_text(line)
    if not line:
        return False
    return any(k in line for k in DATA_METRIC_KEYWORDS) and not any(k in line for k in DATA_METRIC_EXCLUDE_KEYWORDS)


def select_source_lines(template_slides: list[TemplateSlide], sections: list[ReportSection]) -> SelectedSources:
    heading_pairs: list[tuple[str, str]] = []
    all_section_lines: list[str] = []
    for sec in sections:
        heading = normalize_text(sec.heading)
        if heading:
            heading_pairs.append((heading, heading))
        for item in sec.items:
            text = normalize_text(item)
            if text:
                heading_pairs.append((heading, text))
                all_section_lines.append(text)

    selected: SelectedSources = {}
    for slide in template_slides:
        caps = slide_caps(slide.title, slide.has_table)
        kws = keywords_for_title(slide.title)
        req_terms = required_terms_for_title(slide.title)
        preferred_heads = preferred_heading_keywords(slide.title)
        candidate_pairs = heading_pairs
        section_kws = section_keywords_for_title(slide.title)
        target_bucket = section_bucket_for_title(slide.title)
        section_priority_lines: list[str] = []
        section_has_image = False
        section_has_ocr = False
        strict_section_mode = False

        for sec in sections:
            heading = normalize_text(sec.heading)
            bucket_match = infer_section_bucket(sec) == target_bucket
            keyword_match = bool(section_kws) and any(k in heading for k in section_kws)
            if keyword_match or bucket_match:
                section_priority_lines.extend([normalize_text(x) for x in sec.items if normalize_text(x)])
                if sec.image_count > 0:
                    section_has_image = True
                if normalize_text(sec.ocr_text):
                    section_has_ocr = True
        if section_priority_lines:
            strict_section_mode = True
            candidate_pairs = [("", x) for x in section_priority_lines]

        if "基础运作流程数据" in slide.title:
            metric_lines = [x for x in all_section_lines if is_data_metric_line(x)]
            if metric_lines:
                candidate_pairs = [("", x) for x in metric_lines]
                strict_section_mode = True

        if preferred_heads and not strict_section_mode:
            prioritized = [(h, line) for h, line in heading_pairs if any(k in h for k in preferred_heads)]
            if prioritized:
                candidate_pairs = prioritized + [(h, line) for h, line in heading_pairs if (h, line) not in prioritized]

        if strict_section_mode:
            lines = [line for _, line in candidate_pairs][: caps["source_limit"]]
        else:
            ranked = sorted([line for _, line in candidate_pairs], key=lambda x: score_line(x, kws), reverse=True)
            lines = [x for x in ranked if score_line(x, kws) > 0]
        if not lines and strict_section_mode:
            ranked = sorted([line for _, line in heading_pairs], key=lambda x: score_line(x, kws), reverse=True)
            lines = [x for x in ranked if score_line(x, kws) > 0]
        if req_terms:
            lines = [x for x in lines if any(t in x for t in req_terms)]
        if (not strict_section_mode) or ("337" in slide.title) or ("美国劳动诉讼" in slide.title):
            lines = apply_title_strict_filter(slide.title, lines)
        lines = lines[: caps["source_limit"]]

        unique: list[str] = []
        seen: set[str] = set()
        for line in lines:
            sig = line[:24]
            if sig in seen:
                continue
            seen.add(sig)
            unique.append(line)
        if "知识产权" in slide.title and section_has_image and not section_has_ocr:
            log("知识产权章节检测到图片内容：OCR 未生效，请人工补充关键统计。", level="WARN")
        selected[slide.slide_index] = unique[: caps["source_limit"]]
    return selected


