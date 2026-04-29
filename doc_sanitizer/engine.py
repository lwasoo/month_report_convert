from __future__ import annotations

from pathlib import Path
from typing import Any

from report_converter.common import log
from .document_io import apply_mapping_to_docx, apply_mapping_to_file, ensure_supported_path, restore_docx, restore_file
from .scanning import scan_file_payload

__all__ = [
    "apply_mapping_to_file",
    "apply_mapping_to_docx",
    "restore_file",
    "restore_docx",
    "sanitize_file",
    "sanitize_docx",
    "scan_file",
    "scan_docx",
]


def sanitize_file(
    input_path: Path,
    output_path: Path,
    mapping_path: Path,
    custom_terms: list[str] | None = None,
    use_llm_assist: bool = False,
    model: str = "qwen2.5:7b-instruct-q4_K_M",
    ollama_url: str = "http://127.0.0.1:11434",
    timeout_sec: int = 120,
    retries: int = 2,
) -> dict[str, Any]:
    ensure_supported_path(input_path)
    payload = scan_file(
        input_path=input_path,
        custom_terms=custom_terms or [],
        use_llm_assist=use_llm_assist,
        model=model,
        ollama_url=ollama_url,
        timeout_sec=timeout_sec,
        retries=retries,
        existing_mapping_path=mapping_path if mapping_path.exists() else None,
    )
    apply_mapping_to_file(input_path, output_path, payload, mapping_path)
    log(f"脱敏完成: {output_path}")
    log(f"映射文件已输出: {mapping_path}")
    return payload


def scan_file(
    input_path: Path,
    custom_terms: list[str] | None = None,
    use_llm_assist: bool = False,
    model: str = "qwen2.5:7b-instruct-q4_K_M",
    ollama_url: str = "http://127.0.0.1:11434",
    timeout_sec: int = 120,
    retries: int = 2,
    existing_mapping_path: Path | None = None,
    existing_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ensure_supported_path(input_path)
    return scan_file_payload(
        input_path=input_path,
        custom_terms=custom_terms,
        use_llm_assist=use_llm_assist,
        model=model,
        ollama_url=ollama_url,
        timeout_sec=timeout_sec,
        retries=retries,
        existing_mapping_path=existing_mapping_path,
        existing_payload=existing_payload,
    )


def sanitize_docx(
    input_path: Path,
    output_path: Path,
    mapping_path: Path,
    custom_terms: list[str] | None = None,
    use_llm_assist: bool = False,
    model: str = "qwen2.5:7b-instruct-q4_K_M",
    ollama_url: str = "http://127.0.0.1:11434",
    timeout_sec: int = 120,
    retries: int = 2,
) -> dict[str, Any]:
    return sanitize_file(
        input_path=input_path,
        output_path=output_path,
        mapping_path=mapping_path,
        custom_terms=custom_terms,
        use_llm_assist=use_llm_assist,
        model=model,
        ollama_url=ollama_url,
        timeout_sec=timeout_sec,
        retries=retries,
    )


def scan_docx(
    input_path: Path,
    custom_terms: list[str] | None = None,
    use_llm_assist: bool = False,
    model: str = "qwen2.5:7b-instruct-q4_K_M",
    ollama_url: str = "http://127.0.0.1:11434",
    timeout_sec: int = 120,
    retries: int = 2,
    existing_mapping_path: Path | None = None,
    existing_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return scan_file(
        input_path=input_path,
        custom_terms=custom_terms,
        use_llm_assist=use_llm_assist,
        model=model,
        ollama_url=ollama_url,
        timeout_sec=timeout_sec,
        retries=retries,
        existing_mapping_path=existing_mapping_path,
        existing_payload=existing_payload,
    )
