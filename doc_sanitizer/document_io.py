from __future__ import annotations

from pathlib import Path
from typing import Any

from docx import Document
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

from report_converter.common import log, normalize_text
from .mapping import ReplacementItem, mapping_entries, read_mapping, write_mapping_data

SUPPORTED_FILE_SUFFIXES = {".docx", ".pptx"}


def ensure_supported_path(input_path: Path) -> None:
    if input_path.suffix.lower() not in SUPPORTED_FILE_SUFFIXES:
        raise ValueError("当前仅支持 .docx 和 .pptx 文件。")


def default_sanitized_path(input_path: Path) -> Path:
    ensure_supported_path(input_path)
    return input_path.with_name(f"{input_path.stem}_脱敏{input_path.suffix.lower()}")


def collect_texts_for_path(input_path: Path) -> list[str]:
    ensure_supported_path(input_path)
    if input_path.suffix.lower() == ".docx":
        return collect_doc_texts(Document(str(input_path)))
    return collect_ppt_texts(Presentation(str(input_path)))


def collect_doc_texts(doc: Document) -> list[str]:
    texts: list[str] = []
    for paragraph in iter_doc_paragraphs(doc):
        text = normalize_text(paragraph.text)
        if text:
            texts.append(text)
    return texts


def collect_ppt_texts(prs: Presentation) -> list[str]:
    texts: list[str] = []
    for paragraph in iter_ppt_paragraphs(prs):
        text = normalize_text(paragraph.text)
        if text:
            texts.append(text)
    return texts


def iter_doc_paragraphs(doc: Document):
    for paragraph in doc.paragraphs:
        yield paragraph
    for table in doc.tables:
        yield from iter_doc_table_paragraphs(table)
    for section in doc.sections:
        for paragraph in section.header.paragraphs:
            yield paragraph
        for table in section.header.tables:
            yield from iter_doc_table_paragraphs(table)
        for paragraph in section.footer.paragraphs:
            yield paragraph
        for table in section.footer.tables:
            yield from iter_doc_table_paragraphs(table)


def iter_doc_table_paragraphs(table):
    for row in table.rows:
        for cell in row.cells:
            for paragraph in cell.paragraphs:
                yield paragraph
            for inner in cell.tables:
                yield from iter_doc_table_paragraphs(inner)


def iter_ppt_paragraphs(prs: Presentation):
    for slide in prs.slides:
        for shape in slide.shapes:
            yield from iter_ppt_shape_paragraphs(shape)


def iter_ppt_shape_paragraphs(shape):
    if getattr(shape, "shape_type", None) == MSO_SHAPE_TYPE.GROUP:
        for inner in shape.shapes:
            yield from iter_ppt_shape_paragraphs(inner)
        return
    if getattr(shape, "has_table", False):
        for row in shape.table.rows:
            for cell in row.cells:
                for paragraph in cell.text_frame.paragraphs:
                    yield paragraph
        return
    if getattr(shape, "has_text_frame", False):
        for paragraph in shape.text_frame.paragraphs:
            yield paragraph


def apply_replacements_to_doc(doc: Document, items: list[ReplacementItem], reverse: bool = False) -> None:
    ordered = sorted(items, key=lambda item: len(item.placeholder if reverse else item.original), reverse=True)
    for paragraph in iter_doc_paragraphs(doc):
        replace_in_doc_paragraph(paragraph, ordered, reverse=reverse)


def apply_replacements_to_ppt(prs: Presentation, items: list[ReplacementItem], reverse: bool = False) -> None:
    ordered = sorted(items, key=lambda item: len(item.placeholder if reverse else item.original), reverse=True)
    for paragraph in iter_ppt_paragraphs(prs):
        replace_in_ppt_paragraph(paragraph, ordered, reverse=reverse)


def replace_in_doc_paragraph(paragraph, items: list[ReplacementItem], reverse: bool = False) -> None:
    source = paragraph.text or ""
    updated = source
    for item in items:
        old = item.placeholder if reverse else item.original
        new = item.original if reverse else item.placeholder
        if old in updated:
            updated = updated.replace(old, new)
    if updated == source:
        return
    if len(paragraph.runs) == 1:
        paragraph.runs[0].text = updated
        return
    if paragraph.runs:
        paragraph.runs[0].text = updated
        for run in paragraph.runs[1:]:
            run.text = ""
        return
    paragraph.add_run(updated)


def replace_in_ppt_paragraph(paragraph, items: list[ReplacementItem], reverse: bool = False) -> None:
    source = paragraph.text or ""
    updated = source
    for item in items:
        old = item.placeholder if reverse else item.original
        new = item.original if reverse else item.placeholder
        if old in updated:
            updated = updated.replace(old, new)
    if updated == source:
        return
    runs = list(paragraph.runs)
    if len(runs) == 1:
        runs[0].text = updated
        return
    if runs:
        runs[0].text = updated
        for run in runs[1:]:
            run.text = ""
        return
    paragraph.text = updated


def apply_mapping_to_file(
    input_path: Path,
    output_path: Path,
    payload: dict[str, Any],
    mapping_path: Path | None = None,
) -> None:
    ensure_supported_path(input_path)
    if input_path.suffix.lower() == ".docx":
        doc = Document(str(input_path))
        apply_replacements_to_doc(doc, mapping_entries(payload))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))
    else:
        prs = Presentation(str(input_path))
        apply_replacements_to_ppt(prs, mapping_entries(payload))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        prs.save(str(output_path))
    if mapping_path is not None:
        mapping_path.parent.mkdir(parents=True, exist_ok=True)
        payload["sanitized_file"] = str(output_path)
        write_mapping_data(mapping_path, payload)


def restore_file(input_path: Path, output_path: Path, mapping_path: Path) -> None:
    ensure_supported_path(input_path)
    payload = read_mapping(mapping_path)
    items = mapping_entries(payload, only_enabled=False)
    if not items:
        raise ValueError("映射文件中未找到有效 entries。")
    if input_path.suffix.lower() == ".docx":
        doc = Document(str(input_path))
        apply_replacements_to_doc(doc, items, reverse=True)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_path))
    else:
        prs = Presentation(str(input_path))
        apply_replacements_to_ppt(prs, items, reverse=True)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        prs.save(str(output_path))
    log(f"还原完成: {output_path}")


def apply_mapping_to_docx(
    input_path: Path,
    output_path: Path,
    payload: dict[str, Any],
    mapping_path: Path | None = None,
) -> None:
    apply_mapping_to_file(input_path, output_path, payload, mapping_path)


def restore_docx(input_path: Path, output_path: Path, mapping_path: Path) -> None:
    restore_file(input_path, output_path, mapping_path)
