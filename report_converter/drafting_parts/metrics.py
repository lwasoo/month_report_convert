"""Metric extraction and normalization for template tables."""

from __future__ import annotations

import re
from typing import Any

from ..common import log, normalize_text
from ..constants import ALL_METRIC_LABELS
from ..models import Metrics, ReportParagraph, ReportSection
from .rules import BU_APPLY_CODE, BU_SURVEY_CODE, OCR_METRIC_PATTERNS, TEXT_METRIC_PATTERNS


def clean_metrics(raw_metrics: Any) -> Metrics:
    metrics = {key: "-" for key in ALL_METRIC_LABELS}
    if isinstance(raw_metrics, dict):
        for key in metrics:
            if key in raw_metrics:
                metrics[key] = normalize_text(str(raw_metrics[key])) or "-"
    return metrics


def extract_numeric_metrics(paragraphs: list[ReportParagraph], metrics: Metrics) -> Metrics:
    text = "\n".join(p.text for p in paragraphs)

    def find(pattern: str) -> str | None:
        m = re.search(pattern, text)
        return m.group(1) if m else None

    general = find(TEXT_METRIC_PATTERNS["general_seal"])
    legal = find(TEXT_METRIC_PATTERNS["legal_seal"])
    patent_apply = find(TEXT_METRIC_PATTERNS["patent_apply"])
    patent_survey = find(TEXT_METRIC_PATTERNS["patent_survey"])

    if general and metrics["一般文件用印"] == "-":
        metrics["一般文件用印"] = general
    if legal and metrics["法律文件用印"] == "-":
        metrics["法律文件用印"] = legal
    if patent_apply and metrics["BU10申请量"] == "-":
        metrics["BU10申请量"] = f"总计{patent_apply}(未拆分)"
    if patent_survey and metrics["专利调查量BU10"] == "-":
        metrics["专利调查量BU10"] = f"总计{patent_survey}(未拆分)"
    if patent_apply and metrics["其他知识产权申请"] == "-":
        metrics["其他知识产权申请"] = patent_apply
    if patent_apply:
        metrics["专利申请量"] = patent_apply
    if patent_survey:
        metrics["专利调查量"] = patent_survey
    return metrics


def extract_numeric_metrics_from_ocr(sections: list[ReportSection], metrics: Metrics) -> Metrics:
    ocr_text = "\n".join(
        normalize_text(sec.ocr_text)
        for sec in sections
        if normalize_text(sec.ocr_text)
    )
    if not ocr_text:
        return metrics

    def find(pattern: str) -> str | None:
        m = re.search(pattern, ocr_text)
        return m.group(1) if m else None

    patent_apply = next((value for pattern in OCR_METRIC_PATTERNS["patent_apply"] for value in [find(pattern)] if value), None)
    patent_survey = next((value for pattern in OCR_METRIC_PATTERNS["patent_survey"] for value in [find(pattern)] if value), None)

    if patent_apply and (metrics.get("专利申请量", "-") in {"", "-"}):
        metrics["专利申请量"] = patent_apply
        if metrics.get("其他知识产权申请", "-") in {"", "-"}:
            metrics["其他知识产权申请"] = patent_apply
    if patent_survey and (metrics.get("专利调查量", "-") in {"", "-"}):
        metrics["专利调查量"] = patent_survey

    if patent_apply or patent_survey:
        log(f"OCR 数字提取成功: 专利申请量={patent_apply or '-'} 专利调查量={patent_survey or '-'}", level="INFO")
    metrics.update(extract_bu_metrics_from_ocr(sections))
    return metrics


def extract_bu_metrics_from_ocr(sections: list[ReportSection]) -> Metrics:
    apply_counts = {"BU10": 0, "BU11": 0, "BU16": 0}
    survey_counts = {"BU10": 0, "BU11": 0, "BU16": 0}

    for sec in sections:
        text = sec.ocr_text
        if not normalize_text(text):
            continue
        current_bu = ""
        for raw in text.splitlines():
            line = normalize_text(raw)
            if not line:
                continue
            bu_match = re.search(r"\((BU\s*1[016])\)", line, flags=re.IGNORECASE)
            if bu_match:
                current_bu = bu_match.group(1).replace(" ", "").upper()
                continue
            if BU_APPLY_CODE in line and current_bu in apply_counts:
                apply_counts[current_bu] += 1
                continue
            if BU_SURVEY_CODE in line and current_bu in survey_counts:
                survey_counts[current_bu] += 1
                continue

    metrics: Metrics = {}
    for bu, count in apply_counts.items():
        if count:
            metrics[f"{bu}申请量"] = f"{count} (OCR)"
    for bu, count in survey_counts.items():
        if count:
            metrics[f"专利调查量{bu}"] = f"{count} (OCR)"
    return metrics


