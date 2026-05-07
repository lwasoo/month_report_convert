"""LibreOffice-backed conversion helpers for legacy Office formats.

The sanitizer and report converter work on OOXML files internally. This module isolates
the .doc/.ppt conversion boundary and raises user-facing errors when LibreOffice is missing.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


WORD_SUFFIXES = {".doc", ".docx"}
PPT_SUFFIXES = {".ppt", ".pptx"}
OFFICE_SUFFIXES = WORD_SUFFIXES | PPT_SUFFIXES
LIBREOFFICE_DOWNLOAD_URL = "https://www.libreoffice.org/download/download-libreoffice/"


class OfficeConversionError(RuntimeError):
    pass


def is_legacy_office_path(path: Path) -> bool:
    return path.suffix.lower() in {".doc", ".ppt"}


def target_ooxml_suffix(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in WORD_SUFFIXES:
        return ".docx"
    if suffix in PPT_SUFFIXES:
        return ".pptx"
    raise OfficeConversionError(f"不支持的 Office 文件类型: {path.suffix}")


def convert_to_ooxml(input_path: Path, work_dir: Path) -> Path:
    suffix = input_path.suffix.lower()
    if suffix in {".docx", ".pptx"}:
        return input_path
    if suffix not in {".doc", ".ppt"}:
        raise OfficeConversionError(f"不支持的旧版 Office 文件类型: {input_path.suffix}")
    return convert_with_libreoffice(input_path, work_dir, target_ooxml_suffix(input_path))


def convert_from_ooxml(input_path: Path, output_path: Path) -> None:
    output_suffix = output_path.suffix.lower()
    if output_suffix in {".docx", ".pptx"}:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(input_path, output_path)
        return
    if output_suffix not in {".doc", ".ppt"}:
        raise OfficeConversionError(f"不支持的 Office 输出类型: {output_path.suffix}")
    converted = convert_with_libreoffice(input_path, output_path.parent, output_suffix)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if converted.resolve() != output_path.resolve():
        if output_path.exists():
            output_path.unlink()
        converted.replace(output_path)


def convert_with_libreoffice(input_path: Path, output_dir: Path, target_suffix: str) -> Path:
    soffice = find_libreoffice()
    if not soffice:
        raise OfficeConversionError(libreoffice_missing_message())
    output_dir.mkdir(parents=True, exist_ok=True)
    target = target_suffix.lstrip(".")
    completed = subprocess.run(
        [
            str(soffice),
            "--headless",
            "--convert-to",
            target,
            "--outdir",
            str(output_dir),
            str(input_path),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
        check=False,
    )
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "LibreOffice conversion failed").strip()
        raise OfficeConversionError(f"LibreOffice 转换失败: {detail}")
    converted = output_dir / f"{input_path.stem}{target_suffix}"
    if not converted.exists():
        matches = list(output_dir.glob(f"*{target_suffix}"))
        if matches:
            converted = matches[0]
    if not converted.exists():
        raise OfficeConversionError("LibreOffice 未生成预期输出文件。")
    return converted


def find_libreoffice() -> Path | None:
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return Path(found)
    candidates: list[Path] = []
    if sys.platform == "win32":
        candidates.extend(
            [
                Path(r"C:\Program Files\LibreOffice\program\soffice.exe"),
                Path(r"C:\Program Files (x86)\LibreOffice\program\soffice.exe"),
            ]
        )
    elif sys.platform == "darwin":
        candidates.append(Path("/Applications/LibreOffice.app/Contents/MacOS/soffice"))
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def libreoffice_missing_message() -> str:
    install_hint = (
        "Windows 可运行: winget install --id TheDocumentFoundation.LibreOffice -e"
        if sys.platform == "win32"
        else "macOS 可运行: brew install --cask libreoffice"
        if sys.platform == "darwin"
        else "请使用系统包管理器安装 LibreOffice。"
    )
    return (
        "未检测到 LibreOffice，无法转换 .doc/.ppt 旧版 Office 格式。"
        "请安装 LibreOffice 后重试，或先手动另存为 .docx/.pptx。"
        f"\n{install_hint}"
        f"\n下载地址: {LIBREOFFICE_DOWNLOAD_URL}"
    )
