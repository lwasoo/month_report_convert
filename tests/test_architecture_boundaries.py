"""Architecture boundary tests for recently split modules.

These tests are intentionally small: they protect import contracts and facade compatibility
so future refactors can move implementation without silently breaking callers.
"""

from __future__ import annotations

import json
from pathlib import Path
import unittest

from doc_sanitizer import entity_matching, fuzzy_mapping, placeholder_repair, prompt_builder
from doc_sanitizer import document_io, file_types, ooxml_package, operations, placeholder_detection, placeholder_scoring
from doc_sanitizer.services import DocumentSanitizer
from doc_sanitizer.mapping import MappingPayload, ReplacementItem
from gui_app.app import ConverterGUI
from gui_app.runtime import RuntimeMixin
from gui_app.sanitize.actions import SanitizeActionsMixin
from gui_app.sanitize.layout import SanitizeLayoutMixin
from gui_app.sanitize.mapping_service import SanitizeMappingService
from gui_app.sanitize.table import SanitizeTableMixin
from gui_app.sanitize.tab import SanitizeTabMixin
from gui_app import sanitize_actions, sanitize_layout, sanitize_mapping_service, sanitize_table, sanitize_tab
from gui_app.style import StyleMixin
from gui_app.widgets import SharedWidgetsMixin
from report_converter import content_regions, formal_layout, layout, pagination, slide_ops, table_fill
from report_converter.models import Metrics, ParsedReport, ReportParagraph, ReportSection, SelectedSources, TitleProfile
from report_converter.services import ReportConverter


class ArchitectureBoundaryTests(unittest.TestCase):
    """Check compatibility facades and mixin ownership after module splits."""

    def test_fuzzy_mapping_facade_reexports_split_modules(self) -> None:
        # Compatibility contract: older imports from doc_sanitizer.fuzzy_mapping should keep
        # resolving to the narrower implementation modules.
        self.assertIs(fuzzy_mapping.group_entity_matches, entity_matching.group_entity_matches)
        self.assertIs(fuzzy_mapping.suggest_placeholder_repairs, placeholder_repair.suggest_placeholder_repairs)
        self.assertIs(fuzzy_mapping.find_placeholder_like_tokens, placeholder_detection.find_placeholder_like_tokens)
        self.assertIs(fuzzy_mapping.closest_placeholder_for_token, placeholder_scoring.closest_placeholder_for_token)
        self.assertIs(fuzzy_mapping.build_external_ai_prompt_sections, prompt_builder.build_external_ai_prompt_sections)

    def test_document_io_facade_reexports_split_modules(self) -> None:
        # Compatibility contract: legacy document_io imports stay valid while implementation
        # details live in narrower file type, OOXML, and operation modules.
        self.assertIs(document_io.ensure_supported_path, file_types.ensure_supported_path)
        self.assertIs(document_io.apply_mapping_to_file, operations.apply_mapping_to_file)
        self.assertIs(document_io.restore_file, operations.restore_file)
        self.assertIs(document_io.replace_xml_text, ooxml_package.replace_xml_text)

    def test_object_oriented_service_entry_points_exist(self) -> None:
        # Architecture contract: public workflows should have class-based service entry points,
        # while legacy functions remain as thin wrappers.
        sanitizer = DocumentSanitizer(use_llm_assist=False)
        converter = ReportConverter(
            model="qwen2.5:7b-instruct-q4_K_M",
            ollama_url="http://127.0.0.1:11434",
            timeout_sec=120,
            retries=2,
            use_llm=False,
        )

        self.assertFalse(sanitizer.use_llm_assist)
        self.assertEqual(converter.layout_mode, "classic")

    def test_prompt_builder_keeps_sensitive_terms_out_of_external_prompt(self) -> None:
        # Safety contract: direct use of the new prompt_builder module must preserve the same
        # external/internal split as the older facade.
        payload = prompt_builder.payload_from_json_text(
            json.dumps(
                {
                    "entries": [
                        {
                            "placeholder": "__COMPANY_001__",
                            "original": "Acme Sensitive Co",
                            "category": "COMPANY",
                            "enabled": True,
                        },
                        {
                            "placeholder": "__COMPANY_002__",
                            "original": "Acme Sensitive Company",
                            "category": "COMPANY",
                            "enabled": True,
                        }
                    ]
                },
                ensure_ascii=False,
            )
        )

        prompt, audit = prompt_builder.build_external_ai_prompt_sections(payload)

        self.assertIn("__COMPANY_001__", prompt)
        self.assertNotIn("Acme Sensitive Co", prompt)
        self.assertIn("Acme Sensitive Co", audit)

    def test_report_layout_facade_reexports_split_modules(self) -> None:
        # Compatibility contract: engine can import directly from narrow modules, while legacy
        # callers can still import the same helpers from report_converter.layout.
        self.assertIs(layout.add_content_textbox, content_regions.add_content_textbox)
        self.assertIs(layout.add_formal_layout_content_v2, formal_layout.add_formal_layout_content_v2)
        self.assertIs(layout.split_into_pages, pagination.split_into_pages)
        self.assertIs(layout.extract_template_slides, slide_ops.extract_template_slides)
        self.assertIs(layout.fill_table_metrics, table_fill.fill_table_metrics)

    def test_converter_gui_uses_support_mixins_for_cross_cutting_helpers(self) -> None:
        # Ownership contract: app.py should not grow runtime/style/widget methods again.
        self.assertIs(ConverterGUI._start_worker, RuntimeMixin._start_worker)
        self.assertIs(ConverterGUI._palette, StyleMixin._palette)
        self.assertIs(ConverterGUI._create_log_widget, SharedWidgetsMixin._create_log_widget)

    def test_sanitize_tab_is_composed_from_smaller_mixins(self) -> None:
        # Ownership contract: sanitize_tab.py should stay a composition point, with layout,
        # background actions, and mapping table behavior owned by separate modules.
        self.assertIs(SanitizeTabMixin._build_sanitize_tab, SanitizeLayoutMixin._build_sanitize_tab)
        self.assertIs(SanitizeTabMixin.start_scan_mapping, SanitizeActionsMixin.start_scan_mapping)
        self.assertIs(SanitizeTabMixin._refresh_mapping_tree, SanitizeTableMixin._refresh_mapping_tree)

    def test_sanitize_legacy_modules_reexport_feature_package(self) -> None:
        # Compatibility contract: old gui_app.sanitize_* imports stay valid while new code uses
        # gui_app.sanitize.* modules.
        self.assertIs(sanitize_tab.SanitizeTabMixin, SanitizeTabMixin)
        self.assertIs(sanitize_actions.SanitizeActionsMixin, SanitizeActionsMixin)
        self.assertIs(sanitize_layout.SanitizeLayoutMixin, SanitizeLayoutMixin)
        self.assertIs(sanitize_table.SanitizeTableMixin, SanitizeTableMixin)
        self.assertIs(sanitize_mapping_service.SanitizeMappingService, SanitizeMappingService)

    def test_sanitize_mapping_logic_lives_in_service(self) -> None:
        # Ownership contract: pure mapping rules should live outside Tk mixins.
        entries = [{"placeholder": "__COMPANY_001__", "original": "Acme", "category": "COMPANY", "enabled": True}]

        self.assertEqual(SanitizeMappingService.summary_text(entries), "当前候选 1 条，启用 1 条；分类概览：COMPANY:1")
        self.assertEqual(SanitizeMappingService.parse_batch_line("COMPANY|Acme"), ("Acme", "COMPANY", ""))
        self.assertEqual(SanitizeMappingService.normalize_placeholder_input("COMPANY_001", entries, "COMPANY"), ("__COMPANY_002__", "COMPANY"))

    def test_report_converter_core_payloads_are_dataclasses(self) -> None:
        # Readability contract: cross-module parsed report data should use explicit domain
        # objects instead of anonymous dict[str, Any] payloads.
        self.assertEqual(ParsedReport.__name__, "ParsedReport")
        self.assertEqual(ReportParagraph.__name__, "ReportParagraph")
        self.assertEqual(ReportSection.__name__, "ReportSection")
        self.assertEqual(TitleProfile.__name__, "TitleProfile")
        self.assertEqual(Metrics, dict[str, str])
        self.assertEqual(SelectedSources, dict[int, list[str]])

    def test_sanitizer_core_payloads_are_dataclasses(self) -> None:
        # Readability contract: mapping payload data should have a named domain object while
        # preserving dict-like access for older GUI code.
        payload = MappingPayload(entries=[{"placeholder": "__COMPANY_001__", "original": "Acme", "category": "company"}])
        item = ReplacementItem(placeholder="__COMPANY_001__", original="Acme", category="COMPANY")

        self.assertEqual(payload.entries[0]["category"], "COMPANY")
        self.assertEqual(payload["replacements"], {"__COMPANY_001__": "Acme"})
        self.assertEqual(item.original, "Acme")

    def test_compatibility_facades_stay_thin(self) -> None:
        # Migration contract: facade modules are allowed to re-export names, but must not grow
        # new business logic after the split.
        root = Path(__file__).resolve().parents[1]
        facades = [
            root / "doc_sanitizer" / "fuzzy_mapping.py",
            root / "doc_sanitizer" / "document_io.py",
            root / "gui_app" / "sanitize_tab.py",
            root / "report_converter" / "layout.py",
        ]

        for path in facades:
            text = path.read_text(encoding="utf-8")
            lines = text.splitlines()
            self.assertLessEqual(len(lines), 130, path.name)
            self.assertNotIn("\ndef ", text, path.name)
            self.assertNotIn("\nclass ", text, path.name)
            self.assertIn("Do not add", text, path.name)


if __name__ == "__main__":
    unittest.main()
