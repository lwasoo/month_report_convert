"""Office file type helpers for sanitization workflows.

This module owns suffix validation and default output naming. Keeping these rules separate
prevents format checks from leaking into scanning, replacement, and restore code.
"""

from __future__ import annotations

from pathlib import Path


SUPPORTED_FILE_SUFFIXES = {".doc", ".docx", ".ppt", ".pptx"}
LEGACY_OFFICE_SUFFIXES = {".doc", ".ppt"}


def ensure_supported_path(input_path: Path) -> None:
    if input_path.suffix.lower() not in SUPPORTED_FILE_SUFFIXES:
        raise ValueError("当前仅支持 .doc/.docx 和 .ppt/.pptx 文件。")


def is_legacy_office_path(path: Path) -> bool:
    return path.suffix.lower() in LEGACY_OFFICE_SUFFIXES


def default_sanitized_path(input_path: Path) -> Path:
    ensure_supported_path(input_path)
    return input_path.with_name(f"{input_path.stem}_脱敏{input_path.suffix.lower()}")
