"""Focused tests for report converter rule modules.

These tests cover deterministic business rules that were split out of the former drafting
and layout files: source selection, text cleanup, metrics, and pagination.
"""

from __future__ import annotations

import unittest

from report_converter.metrics import clean_metrics, extract_bu_metrics_from_ocr, extract_numeric_metrics
from report_converter.models import ReportParagraph, ReportSection, SlideDraft, TemplateSlide
from report_converter.pagination import split_into_pages
from report_converter.source_selection import matches_title_profile, select_source_lines
from report_converter.text_cleanup import dedupe_drafts_across_slides, detail_fallback_line, is_too_generic


class ReportConverterRuleTests(unittest.TestCase):
    """Protect report conversion rules without requiring Word/PPT files or Ollama."""

    def test_source_selection_prefers_matching_section_bucket(self) -> None:
        slides = [TemplateSlide(slide_index=2, title="知识产权专项", has_table=False)]
        sections = [
            ReportSection(heading="基础运作流程数据", items=["一般文件用印数量为 12 件"]),
            ReportSection(heading="知识产权专项", items=["337 调查项目推进，BU10 专利申请提案 8 件"]),
        ]

        selected = select_source_lines(slides, sections)

        self.assertEqual(selected[2], ["337 调查项目推进，BU10 专利申请提案 8 件"])

    def test_title_profile_rejects_cross_topic_lines(self) -> None:
        self.assertTrue(matches_title_profile("合规黑名单排查完成整改", "合规事务"))
        self.assertFalse(matches_title_profile("一般文件用印数量为 12 件", "合规事务"))

    def test_metrics_extract_text_numbers_without_overwriting_existing_values(self) -> None:
        metrics = clean_metrics({"一般文件用印": "99"})
        paragraphs = [
            ReportParagraph(text="一般文件数量为 12，法律文件数量为 3。"),
            ReportParagraph(text="专利申请提案统计 8 件，专利调查统计 5 件。"),
        ]

        updated = extract_numeric_metrics(paragraphs, metrics)

        self.assertEqual(updated["一般文件用印"], "99")
        self.assertEqual(updated["法律文件用印"], "3")
        self.assertEqual(updated["专利申请量"], "8")
        self.assertEqual(updated["专利调查量"], "5")

    def test_ocr_bu_metrics_count_application_and_survey_rows(self) -> None:
        sections = [
            ReportSection(
                heading="知识产权专项",
                ocr_text="(BU10)\nZLSQ-TECH-001 连接器项目\nZLDC-TECH-002 散热项目\n(BU11)\nZLSQ-TECH-003 滤波器项目",
            )
        ]

        metrics = extract_bu_metrics_from_ocr(sections)

        self.assertEqual(metrics["BU10申请量"], "1 (OCR)")
        self.assertEqual(metrics["BU11申请量"], "1 (OCR)")
        self.assertEqual(metrics["专利调查量BU10"], "1 (OCR)")

    def test_pagination_splits_long_content_but_keeps_empty_page_contract(self) -> None:
        bullets = [f"合规风险排查事项 {idx}，包含整改数字 {idx}" for idx in range(24)]

        pages = split_into_pages(bullets, "合规事务", has_table=False)

        self.assertGreater(len(pages), 1)
        self.assertEqual(split_into_pages([], "合规事务", has_table=False), [[]])

    def test_text_cleanup_falls_back_to_specific_source_details(self) -> None:
        source = "BU10 在 3 月 12 日完成 TA123 项目合规排查"

        fallback = detail_fallback_line(source, "合规事务")

        self.assertFalse(is_too_generic(fallback))
        self.assertIn("BU10", fallback)

    def test_dedupe_drafts_backfills_from_selected_sources(self) -> None:
        slides = [TemplateSlide(slide_index=2, title="合规事务", has_table=False)]
        drafts = [SlideDraft(slide_index=2, bullets=["合规黑名单排查完成整改"])]
        selected = {
            2: [
                "合规黑名单排查完成整改",
                "BU10 出口管制项目完成 3 项整改",
                "BU11 政府项目风险排查完成",
            ]
        }

        result = dedupe_drafts_across_slides(drafts, slides, selected)

        self.assertGreaterEqual(len(result[0].bullets), 2)
        self.assertIn("BU10", "\n".join(result[0].bullets))


if __name__ == "__main__":
    unittest.main()
