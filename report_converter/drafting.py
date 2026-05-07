"""Draft slide content generation orchestration.

The detailed responsibilities are split into source selection, LLM prompting, text cleanup,
and metric extraction modules. This module combines those pieces into final slide drafts.
"""

from __future__ import annotations

from .common import log, short_line, slide_caps
from .llm_client import build_rewrite_prompt, call_ollama_json
from .metrics import clean_metrics, extract_numeric_metrics, extract_numeric_metrics_from_ocr
from .models import Metrics, ParsedReport, SelectedSources, SlideDraft, TemplateSlide
from .source_selection import matches_title_profile, select_source_lines
from .text_cleanup import (
    clean_generated_line,
    compress_for_ppt,
    dedupe_drafts_across_slides,
    detail_fallback_line,
    has_specific_signal,
    is_near_copy,
    is_too_generic,
)


def fallback_drafts(template_slides: list[TemplateSlide], selected_sources: SelectedSources) -> list[SlideDraft]:
    log("使用规则模式生成细节要点")
    drafts: list[SlideDraft] = []
    for slide in template_slides:
        sources = selected_sources.get(slide.slide_index, [])
        caps = slide_caps(slide.title, slide.has_table)
        target_max = caps["bullet_limit"]
        target_min = caps["bullet_min"]
        if not sources:
            drafts.append(SlideDraft(slide.slide_index, []))
            continue
        lines: list[str] = []
        for src in sources:
            candidate = detail_fallback_line(src, slide.title)
            if candidate not in lines:
                lines.append(candidate)
            if len(lines) >= target_max:
                break
        while len(lines) < target_min:
            lines.append(short_line(f"{slide.title}重点事项跟进"))
        drafts.append(SlideDraft(slide.slide_index, lines[:target_max]))
    return drafts


def build_drafts_and_metrics(
    use_llm: bool,
    ollama_url: str,
    model: str,
    timeout_sec: int,
    retries: int,
    report_title: str,
    month_label: str,
    template_slides: list[TemplateSlide],
    doc_payload: ParsedReport,
) -> tuple[list[SlideDraft], Metrics]:
    selected_sources = select_source_lines(template_slides, doc_payload.sections)
    fallback = fallback_drafts(template_slides, selected_sources)
    fallback_map = {draft.slide_index: draft for draft in fallback}

    if use_llm:
        try:
            prompt = build_rewrite_prompt(report_title, month_label, template_slides, selected_sources)
            raw = call_ollama_json(ollama_url, model, prompt, timeout_sec, retries)

            by_idx: dict[int, SlideDraft] = {}
            for row in raw.get("slides", []):
                try:
                    idx = int(row.get("slide_index"))
                except Exception:
                    continue
                bullets_raw = row.get("bullets", [])
                bullets: list[str] = []
                if isinstance(bullets_raw, list):
                    for item in bullets_raw:
                        line = short_line(clean_generated_line(str(item)))
                        if line and line not in bullets:
                            bullets.append(line)
                slide_meta = next((slide for slide in template_slides if slide.slide_index == idx), None)
                bullet_limit = slide_caps(slide_meta.title, slide_meta.has_table)["bullet_limit"] if slide_meta else 12
                by_idx[idx] = SlideDraft(idx, bullets[:bullet_limit])

            drafts: list[SlideDraft] = []
            for slide in template_slides:
                draft = by_idx.get(slide.slide_index, SlideDraft(slide.slide_index, []))
                caps = slide_caps(slide.title, slide.has_table)
                target_max = caps["bullet_limit"]
                target_min = caps["bullet_min"]
                sources = selected_sources.get(slide.slide_index, [])
                if not sources:
                    drafts.append(SlideDraft(slide.slide_index, []))
                    continue

                cleaned: list[str] = []
                for bullet in draft.bullets:
                    line = bullet
                    if not matches_title_profile(line, slide.title):
                        continue
                    if is_near_copy(line, sources):
                        line = detail_fallback_line(sources[0] if sources else line, slide.title)
                    if is_too_generic(line):
                        line = detail_fallback_line(sources[0] if sources else line, slide.title)
                    if not has_specific_signal(line, slide.title):
                        line = detail_fallback_line(sources[0] if sources else line, slide.title)
                    line = compress_for_ppt(line, slide.title)
                    if line not in cleaned:
                        cleaned.append(line)
                    if len(cleaned) >= target_max:
                        break

                if len(cleaned) < target_min:
                    for bullet in fallback_map[slide.slide_index].bullets:
                        if bullet not in cleaned:
                            cleaned.append(bullet)
                        if len(cleaned) >= target_max:
                            break

                drafts.append(SlideDraft(slide.slide_index, cleaned[:target_max]))

            metrics = clean_metrics(raw.get("metrics", {}))
            metrics = extract_numeric_metrics(doc_payload.paragraphs, metrics)
            metrics = extract_numeric_metrics_from_ocr(doc_payload.sections, metrics)
            return dedupe_drafts_across_slides(drafts, template_slides, selected_sources), metrics
        except Exception as exc:
            log(f"LLM 改写失败，退回规则模式: {exc}", level="WARN")

    metrics = clean_metrics({})
    metrics = extract_numeric_metrics(doc_payload.paragraphs, metrics)
    metrics = extract_numeric_metrics_from_ocr(doc_payload.sections, metrics)
    return dedupe_drafts_across_slides(fallback, template_slides, selected_sources), metrics
