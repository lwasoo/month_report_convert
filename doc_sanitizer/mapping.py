"""Mapping file schema helpers for sanitized documents.

The mapping payload is the contract between scan, review, sanitize, prompt generation, and
restore. This module keeps entry normalization, placeholder numbering, and JSON persistence
in one place.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

from report_converter.common import normalize_text

@dataclass
class ReplacementItem:
    placeholder: str
    original: str
    category: str
    enabled: bool = True
    source: str = "auto"


@dataclass
class MappingPayload:
    """Typed mapping payload used across scan, sanitize, prompt, and restore steps.

    It exposes a small dict-like compatibility surface so older GUI/tests can continue using
    ``payload["entries"]`` while new code can rely on named fields.
    """

    version: int = 2
    source_file: str = ""
    sanitized_file: str = ""
    entries: list[dict[str, Any]] | None = None

    def __post_init__(self) -> None:
        self.entries = normalize_entries(self.entries or [])

    @property
    def enabled_entries(self) -> list[dict[str, Any]]:
        return [entry for entry in self.entries or [] if entry["enabled"]]

    @property
    def counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for entry in self.enabled_entries:
            counts[entry["category"]] = counts.get(entry["category"], 0) + 1
        return counts

    @property
    def replacements(self) -> dict[str, str]:
        return {entry["placeholder"]: entry["original"] for entry in self.enabled_entries}

    @property
    def categories(self) -> dict[str, str]:
        return {entry["placeholder"]: entry["category"] for entry in self.enabled_entries}

    def refresh(self) -> None:
        self.entries = normalize_entries(self.entries or [])

    def to_dict(self) -> dict[str, Any]:
        self.refresh()
        return {
            "version": self.version,
            "source_file": self.source_file,
            "sanitized_file": self.sanitized_file,
            "entries": self.entries,
            "counts": self.counts,
            "replacements": self.replacements,
            "categories": self.categories,
        }

    def get(self, key: str, default: Any = None) -> Any:
        return self.to_dict().get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.to_dict()[key]

    def __setitem__(self, key: str, value: Any) -> None:
        if key == "version":
            self.version = int(value)
        elif key == "source_file":
            self.source_file = str(value)
        elif key == "sanitized_file":
            self.sanitized_file = str(value)
        elif key == "entries":
            self.entries = normalize_entries(value)
        elif key in {"counts", "replacements", "categories"}:
            return
        else:
            raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return iter(self.to_dict())


MappingLike = MappingPayload | dict[str, Any]


def read_mapping(mapping_path: Path) -> MappingPayload:
    data = json.loads(mapping_path.read_text(encoding="utf-8"))
    if "entries" in data:
        entries = data["entries"]
    else:
        replacements = data.get("replacements", {})
        categories = data.get("categories", {})
        entries = [
            {
                "placeholder": placeholder,
                "original": str(original),
                "category": str(categories.get(placeholder, "AUTO")),
                "enabled": True,
                "source": "auto",
            }
            for placeholder, original in replacements.items()
        ]
    return MappingPayload(
        version=int(data.get("version", 2) or 2),
        source_file=str(data.get("source_file", "")),
        sanitized_file=str(data.get("sanitized_file", "")),
        entries=entries,
    )


def write_mapping_data(mapping_path: Path, payload: MappingLike) -> None:
    normalized = coerce_mapping_payload(payload)
    mapping_path.write_text(json.dumps(normalized.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")


def mapping_entries(payload: MappingLike, only_enabled: bool = True) -> list[ReplacementItem]:
    entries = coerce_mapping_payload(payload).entries or []
    items: list[ReplacementItem] = []
    for entry in entries:
        if only_enabled and not entry["enabled"]:
            continue
        items.append(
            ReplacementItem(
                placeholder=entry["placeholder"],
                original=entry["original"],
                category=entry["category"],
                enabled=bool(entry.get("enabled", True)),
                source=str(entry.get("source", "auto")),
            )
        )
    return items

def normalize_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for raw in entries:
        placeholder = normalize_text(str(raw.get("placeholder", "")))
        original = normalize_text(str(raw.get("original", "")))
        category = normalize_text(str(raw.get("category", "AUTO"))) or "AUTO"
        enabled = bool(raw.get("enabled", True))
        source = normalize_text(str(raw.get("source", "auto"))) or "auto"
        if not placeholder or not original:
            continue
        key = (placeholder, original)
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        out.append(
            {
                "placeholder": placeholder,
                "original": original,
                "category": category.upper(),
                "enabled": enabled,
                "source": source,
            }
        )
    return out

def coerce_mapping_payload(payload: MappingLike) -> MappingPayload:
    if isinstance(payload, MappingPayload):
        payload.refresh()
        return payload
    return MappingPayload(
        version=int(payload.get("version", 2) or 2),
        source_file=str(payload.get("source_file", "")),
        sanitized_file=str(payload.get("sanitized_file", "")),
        entries=payload.get("entries", []),
    )


def refresh_payload_metadata(payload: MappingLike) -> None:
    if isinstance(payload, MappingPayload):
        payload.refresh()
        return
    entries = normalize_entries(payload.get("entries", []))
    payload["entries"] = entries
    enabled_entries = [entry for entry in entries if entry["enabled"]]
    counts: dict[str, int] = {}
    for entry in enabled_entries:
        counts[entry["category"]] = counts.get(entry["category"], 0) + 1
    payload["counts"] = counts
    payload["replacements"] = {entry["placeholder"]: entry["original"] for entry in enabled_entries}
    payload["categories"] = {entry["placeholder"]: entry["category"] for entry in enabled_entries}

def compact_entry_placeholders(entries: list[dict[str, Any]]) -> dict[str, str]:
    normalized = normalize_entries(entries)
    grouped: dict[str, list[tuple[bool, int, int, dict[str, Any]]]] = {}
    for order, entry in enumerate(normalized):
        category = str(entry.get("category", "MANUAL")).strip().upper() or "MANUAL"
        grouped.setdefault(category, []).append(
            (bool(entry.get("enabled", True)), parse_placeholder_index(str(entry.get("placeholder", ""))), order, entry)
        )

    changes: dict[str, str] = {}
    for category, rows in grouped.items():
        rows.sort(key=lambda item: (not item[0], item[1] if item[1] > 0 else 10**9, item[2]))
        for new_index, (_enabled, _old_index, _order, entry) in enumerate(rows, start=1):
            old_placeholder = str(entry.get("placeholder", "")).strip()
            new_placeholder = f"__{category}_{new_index:03d}__"
            if old_placeholder != new_placeholder:
                changes[old_placeholder] = new_placeholder
                entry["placeholder"] = new_placeholder

    entries[:] = normalized
    return changes

def merge_entries(existing_entries: list[dict[str, Any]], candidates: list[tuple[str, str, str]]) -> list[dict[str, Any]]:
    merged = normalize_entries(existing_entries)
    existing_by_original = {normalize_text(entry["original"]): entry for entry in merged}
    used_placeholders = {entry["placeholder"] for entry in merged}
    counters = category_counters(merged)

    for category, value, source in candidates:
        normalized = normalize_text(value)
        if normalized in existing_by_original:
            continue
        placeholder = next_placeholder(category, counters, used_placeholders)
        entry = {
            "placeholder": placeholder,
            "original": normalized,
            "category": category,
            "enabled": True,
            "source": source,
        }
        merged.append(entry)
        existing_by_original[normalized] = entry
    return merged

def category_counters(entries: list[dict[str, Any]]) -> dict[str, int]:
    counters: dict[str, int] = {}
    for entry in entries:
        category = entry["category"]
        counters[category] = max(counters.get(category, 0), parse_placeholder_index(entry["placeholder"]))
    return counters

def parse_placeholder_index(placeholder: str) -> int:
    match = re.search(r"_(\d{3,})__", placeholder)
    return int(match.group(1)) if match else 0

def next_placeholder(category: str, counters: dict[str, int], used_placeholders: set[str]) -> str:
    category = category.upper()
    while True:
        counters[category] = counters.get(category, 0) + 1
        placeholder = f"__{category}_{counters[category]:03d}__"
        if placeholder not in used_placeholders:
            used_placeholders.add(placeholder)
            return placeholder

def make_manual_entry(original: str, placeholder: str | None = None, category: str = "MANUAL") -> dict[str, Any]:
    original = normalize_text(original)
    placeholder = normalize_text(placeholder or "")
    if not original:
        raise ValueError("敏感词不能为空。")
    if not placeholder:
        placeholder = f"__{category.upper()}_MANUAL__"
    return {
        "placeholder": placeholder,
        "original": original,
        "category": category.upper(),
        "enabled": True,
        "source": "manual",
    }

