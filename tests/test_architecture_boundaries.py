"""Architecture boundary tests for recently split modules.

These tests are intentionally small: they protect import contracts and ownership boundaries
so future refactors can move implementation without silently breaking callers.
"""

from __future__ import annotations

import json
import unittest

from doc_sanitizer import prompt_builder
from doc_sanitizer.services import DocumentSanitizer
from doc_sanitizer.mapping import MappingPayload, ReplacementItem
from gui_app.app import ConverterGUI
from gui_app.convert.tab import ConvertTabController
from gui_app.prompt.tab import PromptTabController
from gui_app.runtime import RuntimeMixin
from gui_app.restore.tab import RestoreTabController
from gui_app.sanitize.actions import SanitizeActions
from gui_app.sanitize.layout import SanitizeLayout
from gui_app.sanitize.mapping_service import SanitizeMappingService
from gui_app.sanitize.table import SanitizeMappingTable
from gui_app.sanitize.tab import SanitizeTabController
from gui_app.style import StyleMixin
from gui_app.update.about_tab import AboutTabController
from gui_app.widgets import SharedWidgetsMixin
from report_converter.models import Metrics, ParsedReport, ReportParagraph, ReportSection, SelectedSources, TitleProfile
from report_converter.services import ReportConverter


class ArchitectureBoundaryTests(unittest.TestCase):
    """Check import contracts and ownership boundaries after module splits."""

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

    def test_converter_gui_uses_support_mixins_for_cross_cutting_helpers(self) -> None:
        # Ownership contract: app.py should not grow runtime/style/widget methods again.
        self.assertIs(ConverterGUI._start_worker, RuntimeMixin._start_worker)
        self.assertIs(ConverterGUI._palette, StyleMixin._palette)
        self.assertIs(ConverterGUI._create_log_widget, SharedWidgetsMixin._create_log_widget)
        self.assertFalse(hasattr(ConverterGUI, "start_convert"))
        self.assertFalse(hasattr(ConverterGUI, "start_restore"))
        self.assertFalse(hasattr(ConverterGUI, "generate_external_ai_prompt"))
        self.assertFalse(hasattr(ConverterGUI, "check_updates_async"))
        self.assertFalse(hasattr(ConverterGUI, "start_scan_mapping"))

    def test_sanitize_tab_is_composed_from_smaller_components(self) -> None:
        # Ownership contract: the sanitize controller composes layout, background actions,
        # and mapping table behavior without exposing them on the app shell.
        self.assertIs(SanitizeTabController._build_sanitize_tab, SanitizeLayout._build_sanitize_tab)
        self.assertIs(SanitizeTabController.start_scan_mapping, SanitizeActions.start_scan_mapping)
        self.assertIs(SanitizeTabController._refresh_mapping_tree, SanitizeMappingTable._refresh_mapping_tree)
        self.assertTrue(hasattr(SanitizeTabController, "start_scan_mapping"))

    def test_restore_tab_is_scoped_to_controller(self) -> None:
        self.assertTrue(hasattr(RestoreTabController, "start_restore"))
        self.assertTrue(hasattr(RestoreTabController, "_show_unknown_placeholder_dialog"))
        self.assertFalse(hasattr(ConverterGUI, "_show_unknown_placeholder_dialog"))

    def test_convert_tab_is_scoped_to_controller(self) -> None:
        self.assertTrue(hasattr(ConvertTabController, "start_convert"))
        self.assertFalse(hasattr(ConverterGUI, "_browse_docx"))

    def test_prompt_tab_is_scoped_to_controller(self) -> None:
        self.assertTrue(hasattr(PromptTabController, "generate_external_ai_prompt"))
        self.assertFalse(hasattr(ConverterGUI, "copy_external_ai_prompt"))

    def test_about_tab_is_scoped_to_controller(self) -> None:
        self.assertTrue(hasattr(AboutTabController, "check_updates_async"))
        self.assertFalse(hasattr(ConverterGUI, "download_latest_update_async"))

    def test_sanitize_mapping_logic_lives_in_service(self) -> None:
        # Ownership contract: pure mapping rules should live outside Tk components.
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
        # Readability contract: mapping payload entries are named domain objects internally,
        # while JSON/dict access remains available at the boundary.
        payload = MappingPayload(entries=[{"placeholder": "__COMPANY_001__", "original": "Acme", "category": "company"}])
        item = ReplacementItem(placeholder="__COMPANY_001__", original="Acme", category="COMPANY")

        self.assertIsInstance(payload.entries[0], ReplacementItem)
        self.assertEqual(payload.entries[0].category, "COMPANY")
        self.assertEqual(payload["replacements"], {"__COMPANY_001__": "Acme"})
        self.assertIsInstance(payload.to_dict()["entries"][0], dict)
        self.assertEqual(item.original, "Acme")

if __name__ == "__main__":
    unittest.main()

