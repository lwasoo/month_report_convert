"""Run-preserving text replacement for sanitize and restore operations.

The engine works at paragraph/run level so formatting survives when a replacement fits the
existing run boundaries, and falls back to whole-paragraph replacement when needed.
"""

from __future__ import annotations

from enum import Enum

from docx import Document
from pptx import Presentation

from ..mapping import ReplacementItem
from ..placeholders.repair import repair_placeholder_text
from .text_collection import iter_doc_paragraphs, iter_ppt_paragraphs


class ReplacementDirection(str, Enum):
    SANITIZE = "sanitize"
    RESTORE = "restore"

    @property
    def is_restore(self) -> bool:
        return self is ReplacementDirection.RESTORE


def sanitize_text(text: str, items: list[ReplacementItem]) -> str:
    return replace_text(text, items, direction=ReplacementDirection.SANITIZE)


def restore_text(
    text: str,
    items: list[ReplacementItem],
    placeholder_repairs: dict[str, str] | None = None,
) -> str:
    return replace_text(text, items, direction=ReplacementDirection.RESTORE, placeholder_repairs=placeholder_repairs)


def apply_replacements_to_doc(
    doc: Document,
    items: list[ReplacementItem],
    direction: ReplacementDirection = ReplacementDirection.SANITIZE,
    placeholder_repairs: dict[str, str] | None = None,
) -> None:
    ordered = sorted(items, key=lambda item: len(source_value(item, direction)), reverse=True)
    for paragraph in iter_doc_paragraphs(doc):
        replace_in_doc_paragraph(paragraph, ordered, direction=direction, placeholder_repairs=placeholder_repairs)


def apply_replacements_to_ppt(
    prs: Presentation,
    items: list[ReplacementItem],
    direction: ReplacementDirection = ReplacementDirection.SANITIZE,
    placeholder_repairs: dict[str, str] | None = None,
) -> None:
    ordered = sorted(items, key=lambda item: len(source_value(item, direction)), reverse=True)
    for paragraph in iter_ppt_paragraphs(prs):
        replace_in_ppt_paragraph(paragraph, ordered, direction=direction, placeholder_repairs=placeholder_repairs)


def replace_in_doc_paragraph(
    paragraph,
    items: list[ReplacementItem],
    direction: ReplacementDirection = ReplacementDirection.SANITIZE,
    placeholder_repairs: dict[str, str] | None = None,
) -> None:
    """Replace paragraph text while preserving run formatting when possible."""
    source = paragraph.text or ""
    if not source:
        return
    if replace_in_runs(paragraph.runs, items, direction=direction, placeholder_repairs=placeholder_repairs):
        return
    updated = replace_text(source, items, direction=direction, placeholder_repairs=placeholder_repairs)
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


def replace_in_ppt_paragraph(
    paragraph,
    items: list[ReplacementItem],
    direction: ReplacementDirection = ReplacementDirection.SANITIZE,
    placeholder_repairs: dict[str, str] | None = None,
) -> None:
    """Replace PPT paragraph text using the same run-preserving path as DOCX."""
    source = paragraph.text or ""
    if not source:
        return
    runs = list(paragraph.runs)
    if replace_in_runs(runs, items, direction=direction, placeholder_repairs=placeholder_repairs):
        return
    updated = replace_text(source, items, direction=direction, placeholder_repairs=placeholder_repairs)
    if updated == source:
        return
    if len(runs) == 1:
        runs[0].text = updated
        return
    if runs:
        runs[0].text = updated
        for run in runs[1:]:
            run.text = ""
        return
    paragraph.text = updated


def replace_text(
    text: str,
    items: list[ReplacementItem],
    direction: ReplacementDirection = ReplacementDirection.SANITIZE,
    placeholder_repairs: dict[str, str] | None = None,
) -> str:
    updated = repair_placeholder_text(text, items, confirmed_repairs=placeholder_repairs) if direction.is_restore else text
    for item in items:
        old = source_value(item, direction)
        new = target_value(item, direction)
        if old in updated:
            updated = updated.replace(old, new)
    return updated


def replace_in_runs(
    runs,
    items: list[ReplacementItem],
    direction: ReplacementDirection = ReplacementDirection.SANITIZE,
    placeholder_repairs: dict[str, str] | None = None,
) -> bool:
    """Apply replacements across run boundaries without flattening the paragraph."""
    run_list = list(runs)
    if not run_list:
        return False
    texts = [run.text or "" for run in run_list]
    source = "".join(texts)
    if not source:
        return False
    if direction.is_restore and placeholder_repairs:
        return False

    char_runs: list[int] = []
    for run_idx, text in enumerate(texts):
        char_runs.extend([run_idx] * len(text))

    chunks: list[list[str]] = [[] for _ in run_list]
    changed = False
    pos = 0
    while pos < len(source):
        matched = False
        for item in items:
            old = source_value(item, direction)
            new = target_value(item, direction)
            if old and source.startswith(old, pos):
                chunks[char_runs[pos]].append(new)
                pos += len(old)
                changed = True
                matched = True
                break
        if matched:
            continue
        chunks[char_runs[pos]].append(source[pos])
        pos += 1

    if not changed:
        return False
    for run, parts in zip(run_list, chunks):
        run.text = "".join(parts)
    return True


def source_value(item: ReplacementItem, direction: ReplacementDirection) -> str:
    return item.placeholder if direction.is_restore else item.original


def target_value(item: ReplacementItem, direction: ReplacementDirection) -> str:
    return item.original if direction.is_restore else item.placeholder
