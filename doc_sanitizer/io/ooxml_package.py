"""Direct OOXML package patching for text not exposed by document libraries."""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from ..mapping import ReplacementItem
from .ooxml_parts import is_docx_text_xml_part, is_pptx_text_xml_part
from ..placeholders.repair import repair_placeholder_text
from .replacement_engine import ReplacementDirection, source_value, target_value


def apply_replacements_to_docx_package(
    path: Path,
    items: list[ReplacementItem],
    direction: ReplacementDirection = ReplacementDirection.SANITIZE,
    placeholder_repairs: dict[str, str] | None = None,
) -> None:
    """Patch DOCX XML package text after python-docx saves the main document."""
    apply_replacements_to_package(path, items, is_docx_text_xml_part, direction, placeholder_repairs)


def apply_replacements_to_pptx_package(
    path: Path,
    items: list[ReplacementItem],
    direction: ReplacementDirection = ReplacementDirection.SANITIZE,
    placeholder_repairs: dict[str, str] | None = None,
) -> None:
    """Patch PPTX XML package text after python-pptx saves the presentation."""
    apply_replacements_to_package(path, items, is_pptx_text_xml_part, direction, placeholder_repairs)


def apply_replacements_to_package(
    path: Path,
    items: list[ReplacementItem],
    part_filter,
    direction: ReplacementDirection,
    placeholder_repairs: dict[str, str] | None = None,
) -> None:
    if not items:
        return
    temp_path = path.with_name(f"{path.stem}.tmp{path.suffix}")
    changed_any = False
    with ZipFile(path, "r") as zin, ZipFile(temp_path, "w", ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if part_filter(info.filename):
                try:
                    text = data.decode("utf-8")
                except UnicodeDecodeError:
                    text = ""
                if text:
                    updated = replace_xml_text(text, items, direction=direction, placeholder_repairs=placeholder_repairs)
                    if updated != text:
                        data = updated.encode("utf-8")
                        changed_any = True
            zout.writestr(info, data)
    if changed_any:
        temp_path.replace(path)
    else:
        temp_path.unlink(missing_ok=True)


def replace_xml_text(
    xml_text: str,
    items: list[ReplacementItem],
    direction: ReplacementDirection = ReplacementDirection.SANITIZE,
    placeholder_repairs: dict[str, str] | None = None,
) -> str:
    """Replace escaped XML text, including confirmed placeholder repairs during restore."""
    xml_repairs = {token: escape(value) for token, value in (placeholder_repairs or {}).items()}
    updated = repair_placeholder_text(xml_text, items, confirmed_repairs=xml_repairs) if direction.is_restore else xml_text
    for item in items:
        old = source_value(item, direction)
        new = target_value(item, direction)
        if old:
            updated = updated.replace(escape(old), escape(new))
    return updated
