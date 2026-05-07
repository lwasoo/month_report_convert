"""Compatibility facade for Office document sanitize/restore I/O.

The implementation is split across narrower modules:
file type rules, text collection, replacement, OOXML package patching, and high-level
operations. Keep this file as a stable import surface for older GUI/CLI/tests.

Do not add business logic here.
"""

from __future__ import annotations

from .file_types import SUPPORTED_FILE_SUFFIXES, default_sanitized_path, ensure_supported_path, is_legacy_office_path
from .ooxml_package import (
    apply_replacements_to_docx_package,
    apply_replacements_to_pptx_package,
    is_docx_text_xml_part,
    is_pptx_text_xml_part,
    replace_xml_text,
)
from .operations import apply_mapping_to_docx, apply_mapping_to_file, restore_docx, restore_file
from .replacement_engine import (
    ReplacementDirection,
    apply_replacements_to_doc,
    apply_replacements_to_ppt,
    replace_in_doc_paragraph,
    replace_in_ppt_paragraph,
    replace_in_runs,
    replace_text,
    restore_text,
    sanitize_text,
)
from .text_collection import (
    collect_doc_texts,
    collect_docx_package_texts,
    collect_ppt_texts,
    collect_pptx_package_texts,
    collect_texts_for_path,
    dedupe_texts,
    iter_doc_paragraphs,
    iter_doc_table_paragraphs,
    iter_ppt_paragraphs,
    iter_ppt_shape_paragraphs,
)

__all__ = [
    "SUPPORTED_FILE_SUFFIXES",
    "ReplacementDirection",
    "apply_mapping_to_docx",
    "apply_mapping_to_file",
    "apply_replacements_to_doc",
    "apply_replacements_to_docx_package",
    "apply_replacements_to_ppt",
    "apply_replacements_to_pptx_package",
    "collect_doc_texts",
    "collect_docx_package_texts",
    "collect_ppt_texts",
    "collect_pptx_package_texts",
    "collect_texts_for_path",
    "dedupe_texts",
    "default_sanitized_path",
    "ensure_supported_path",
    "is_docx_text_xml_part",
    "is_legacy_office_path",
    "is_pptx_text_xml_part",
    "iter_doc_paragraphs",
    "iter_doc_table_paragraphs",
    "iter_ppt_paragraphs",
    "iter_ppt_shape_paragraphs",
    "replace_in_doc_paragraph",
    "replace_in_ppt_paragraph",
    "replace_in_runs",
    "replace_text",
    "replace_xml_text",
    "restore_docx",
    "restore_file",
    "restore_text",
    "sanitize_text",
]
