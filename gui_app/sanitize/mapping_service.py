"""Pure mapping operations used by the sanitize GUI.

The sanitize tab owns widgets and user interactions. This service owns mapping data rules:
summary text, metadata refresh, placeholder numbering, batch-line parsing, and category
inference. Keeping these operations out of Tk components makes them easier to test and reuse.
"""

from __future__ import annotations

import re
from typing import Any

from doc_sanitizer.mapping import (
    EntryLike,
    MappingPayload,
    ReplacementItem,
    coerce_mapping_payload,
    compact_entry_placeholders,
    entries_to_dicts,
    normalize_entries,
)


MappingData = MappingPayload | dict[str, Any]


class SanitizeMappingService:
    CATEGORY_TOKENS = {"COMPANY", "PERSON", "PROJECT", "CASE", "CODE", "CUSTOMER", "SUPPLIER", "TITLE", "MANUAL"}
    BATCH_SEPARATOR_TRANSLATION = str.maketrans(
        {
            "\uff5c": "|",
            "\u2223": "|",
            "\u00a6": "|",
            "\uffe8": "|",
            "\ufe31": "|",
            "\u2502": "|",
            "\u2503": "|",
        }
    )

    @staticmethod
    def entries(payload: MappingData | None) -> list[ReplacementItem]:
        if not payload:
            return []
        normalized = coerce_mapping_payload(payload)
        if isinstance(payload, dict):
            payload["entries"] = normalized.entries if normalized.entries is not None else []
        return normalized.entries if normalized.entries is not None else []

    @staticmethod
    def _items(entries: list[EntryLike]) -> list[ReplacementItem]:
        return normalize_entries(entries)

    @staticmethod
    def summary_text(entries: list[EntryLike]) -> str:
        entries = SanitizeMappingService._items(entries)
        enabled = sum(1 for entry in entries if entry.enabled)
        categories: dict[str, int] = {}
        for entry in entries:
            if not entry.enabled:
                continue
            category = entry.category
            categories[category] = categories.get(category, 0) + 1
        top = " / ".join(f"{key}:{value}" for key, value in list(categories.items())[:6]) if categories else "无"
        return f"当前候选 {len(entries)} 条，启用 {enabled} 条；分类概览：{top}"

    @staticmethod
    def rebuild_metadata(payload: MappingData | None) -> None:
        if not payload:
            return
        entries = SanitizeMappingService.entries(payload)
        normalized = MappingPayload(entries=entries)
        if isinstance(payload, MappingPayload):
            payload.entries = normalized.entries
            payload.refresh()
            return
        payload["entries"] = entries_to_dicts(normalized.entries or [])
        payload["replacements"] = normalized.replacements
        payload["categories"] = normalized.categories
        payload["counts"] = normalized.counts

    @staticmethod
    def compact_placeholders(entries: list[EntryLike]) -> dict[str, str]:
        return compact_entry_placeholders(entries)

    @staticmethod
    def parse_batch_line(line: str) -> tuple[str, str, str]:
        text = SanitizeMappingService.normalize_batch_line(line)
        if not text:
            return "", "", ""
        if "=>" in text:
            left, right = [part.strip() for part in text.split("=>", 1)]
            if left and right:
                return left, "", right
        if "->" in text:
            left, right = [part.strip() for part in text.split("->", 1)]
            if left and right:
                return left, "", right
        for sep in ("|", "\t", "，", ","):
            if sep in text:
                left, right = [part.strip() for part in text.split(sep, 1)]
                if not left or not right:
                    continue
                if SanitizeMappingService.looks_like_category_token(left) or SanitizeMappingService.looks_like_custom_category_token(left):
                    return right, left.upper(), ""
        return text, "", ""

    @staticmethod
    def normalize_batch_line(line: str) -> str:
        text = line.strip().translate(SanitizeMappingService.BATCH_SEPARATOR_TRANSLATION)
        text = text.replace("\uff1d\uff1e", "=>").replace("\uff0d\uff1e", "->")
        text = text.replace("\u2192", "->").replace("\u21d2", "=>")
        return text

    @staticmethod
    def looks_like_category_token(text: str) -> bool:
        return text.strip().upper() in SanitizeMappingService.CATEGORY_TOKENS

    @staticmethod
    def looks_like_custom_category_token(text: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{1,24}", text.strip()))

    @staticmethod
    def looks_like_placeholder_token(text: str) -> bool:
        return bool(re.fullmatch(r"(?:__)?[A-Za-z]+(?:_[0-9]{1,4})?(?:__)?", text.strip()))

    @staticmethod
    def looks_like_explicit_placeholder_token(text: str) -> bool:
        return bool(re.fullmatch(r"(?:__)?[A-Za-z]+_[0-9]{1,4}(?:__)?", text.strip()))

    @staticmethod
    def next_placeholder(entries: list[EntryLike], category: str = "MANUAL", exclude_index: int | None = None) -> str:
        entries = SanitizeMappingService._items(entries)
        index = 1
        used = {
            item.placeholder.strip().upper()
            for idx, item in enumerate(entries)
            if exclude_index is None or idx != exclude_index
        }
        while True:
            candidate = f"__{category.upper()}_{index:03d}__"
            if candidate.upper() not in used:
                return candidate
            index += 1

    @staticmethod
    def normalize_placeholder_input(
        raw_value: str,
        entries: list[EntryLike],
        preferred_category: str,
        exclude_index: int | None = None,
    ) -> tuple[str, str]:
        raw = raw_value.strip()
        entries = SanitizeMappingService._items(entries)
        category = preferred_category.upper() or "MANUAL"
        if raw:
            cleaned = raw.upper().replace("-", "_").replace(" ", "_")
            cleaned = re.sub(r"_+", "_", cleaned).strip("_")
            if cleaned.isdigit():
                desired = f"__{category}_{int(cleaned):03d}__"
                used = {
                    item.placeholder.strip().upper()
                    for idx, item in enumerate(entries)
                    if exclude_index is None or idx != exclude_index
                }
                if desired.upper() not in used:
                    return desired, category
                return SanitizeMappingService.tail_placeholder(entries, category, exclude_index=exclude_index), category
            match = re.fullmatch(r"(?:__)?([A-Z]+)(?:_)?(\d+)?(?:__)?", cleaned)
            if match:
                category = match.group(1).upper()
                if match.group(2):
                    desired = f"__{category}_{int(match.group(2)):03d}__"
                    used = {
                        item.placeholder.strip().upper()
                        for idx, item in enumerate(entries)
                        if exclude_index is None or idx != exclude_index
                    }
                    if desired.upper() not in used:
                        return desired, category
                return SanitizeMappingService.tail_placeholder(entries, category, exclude_index=exclude_index), category
        return SanitizeMappingService.next_placeholder(entries, category, exclude_index=exclude_index), category

    @staticmethod
    def tail_placeholder(entries: list[EntryLike], category: str, exclude_index: int | None = None) -> str:
        entries = SanitizeMappingService._items(entries)
        category = category.upper()
        max_index = 0
        for idx, item in enumerate(entries):
            if exclude_index is not None and idx == exclude_index:
                continue
            placeholder = item.placeholder.strip().upper()
            if not placeholder.startswith(f"__{category}_"):
                continue
            match = re.search(r"_(\d{1,5})__", placeholder)
            if match:
                max_index = max(max_index, int(match.group(1)))
        return f"__{category}_{max_index + 1:03d}__"

    @staticmethod
    def infer_manual_category(placeholder: str, sensitive: str = "") -> str:
        text = placeholder.strip().upper()
        inner = text.removeprefix("__")
        if inner.endswith("__"):
            inner = inner[:-2]
        if "_" in inner:
            return inner.split("_", 1)[0]
        return SanitizeMappingService.infer_sensitive_category(sensitive, placeholder) or "MANUAL"

    @staticmethod
    def infer_sensitive_category(sensitive: str, placeholder: str = "") -> str:
        text = (placeholder or "").strip().upper()
        if text.startswith("__"):
            inner = text.removeprefix("__")
            if inner.endswith("__"):
                inner = inner[:-2]
            if "_" in inner:
                return inner.split("_", 1)[0]
        raw = sensitive.strip()
        if re.search(r"(律师事务所|律所)$", raw):
            return "COMPANY"
        if re.search(r"(股份有限公司|有限责任公司|有限公司|分公司|集团|公司|科技|技术|电子|实业|贸易|国际)$", raw):
            return "COMPANY"
        if re.fullmatch(r"[A-Z][A-Za-z&.\-]+(?:\s+[A-Z][A-Za-z&.\-]+){0,5}", raw):
            return "COMPANY"
        if re.fullmatch(r"(?:欧阳|司马|上官|诸葛|皇甫|尉迟|公孙|长孙|慕容|司徒|夏侯|东方|独孤|南宫|闻人|令狐|轩辕|赵|钱|孙|李|周|吴|郑|王|冯|陈|褚|卫|蒋|沈|韩|杨|朱|秦|尤|许|何|吕|施|张|孔|曹|严|华|金|魏|陶|姜|戚|谢|邹|喻|柏|窦|章|云|苏|潘|葛|范|彭|郎|鲁|韦|昌|马|苗|凤|花|方|俞|任|袁|柳|鲍|史|唐|费|廉|岑|薛|雷|贺|倪|汤|殷|罗|毕|郝|邬|安|常|乐|于|时|傅|皮|卞|齐|康|伍|余|元|卜|顾|孟|平|黄|和|穆|萧|尹)[一-龥某]{1,2}", raw):
            return "PERSON"
        if re.fullmatch(r"[A-Z]{2,}(?:[-_][A-Z0-9]+)+", raw):
            return "CODE"
        if "项目" in raw:
            return "PROJECT"
        return "MANUAL"

    @staticmethod
    def manual_entry(original: str, placeholder_hint: str, entries: list[EntryLike]) -> ReplacementItem:
        category = SanitizeMappingService.infer_sensitive_category(original, placeholder_hint)
        placeholder, _ = SanitizeMappingService.normalize_placeholder_input(placeholder_hint or "", entries, category)
        return ReplacementItem(
            placeholder=placeholder,
            original=original,
            category=SanitizeMappingService.infer_manual_category(placeholder, original),
            enabled=True,
            source="manual",
        )
