"""Tests for prompt tab state transitions without launching the full GUI."""

from __future__ import annotations

import json
import unittest
import tkinter as tk

from doc_sanitizer.mapping import MappingPayload
from gui_app.prompt.tab import PromptTabMixin


class FakeText:
    def __init__(self) -> None:
        self.value = ""

    def delete(self, *_args) -> None:
        self.value = ""

    def insert(self, _index: str, value: str) -> None:
        self.value = value


class PromptTabTests(unittest.TestCase):
    """Protect prompt generation inputs shared from the sanitize tab."""

    def test_use_current_mapping_accepts_mapping_payload_dataclass(self) -> None:
        tab = object.__new__(PromptTabMixin)
        tab.current_mapping_data = MappingPayload(
            source_file="source.docx",
            sanitized_file="source_脱敏.docx",
            entries=[
                {"placeholder": "__COMPANY_001__", "original": "Acme", "category": "COMPANY", "enabled": True}
            ],
        )
        tab.prompt_json_text = FakeText()
        tab.prompt_status_var = tk.StringVar(master=tk.Tcl())

        tab.use_current_mapping_for_prompt()

        payload = json.loads(tab.prompt_json_text.value)
        self.assertEqual(payload["replacements"], {"__COMPANY_001__": "Acme"})
        self.assertIn("当前", tab.prompt_status_var.get())


if __name__ == "__main__":
    unittest.main()
