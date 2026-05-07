"""OOXML package part classification helpers."""

from __future__ import annotations


def is_docx_text_xml_part(name: str) -> bool:
    if not name.startswith("word/") or not name.endswith(".xml"):
        return False
    if name.startswith("word/_rels/"):
        return False
    return True


def is_pptx_text_xml_part(name: str) -> bool:
    if not name.startswith("ppt/") or not name.endswith(".xml"):
        return False
    if "/_rels/" in name or name.startswith("ppt/_rels/"):
        return False
    return True
