"""Pure mapping operations used by the sanitize GUI.

The sanitize tab owns widgets and user interactions. This service owns mapping data rules:
summary text, metadata refresh, placeholder numbering, batch-line parsing, and category
inference. Keeping these operations out of Tk mixins makes them easier to test and reuse.
"""

from __future__ import annotations

import re
from typing import Any

from doc_sanitizer.mapping import MappingPayload, compact_entry_placeholders


MappingData = MappingPayload | dict[str, Any]


class SanitizeMappingService:
    CATEGORY_TOKENS = {"COMPANY", "PERSON", "PROJECT", "CASE", "CODE", "CUSTOMER", "SUPPLIER", "TITLE", "MANUAL"}

    @staticmethod
    def entries(payload: MappingData | None) -> list[dict[str, object]]:
        if not payload:
            return []
        raw_entries = payload.get("entries", [])
        return raw_entries if isinstance(raw_entries, list) else []

    @staticmethod
    def summary_text(entries: list[dict[str, object]]) -> str:
        enabled = sum(1 for entry in entries if bool(entry.get("enabled", True)))
        categories: dict[str, int] = {}
        for entry in entries:
            if not bool(entry.get("enabled", True)):
                continue
            category = str(entry.get("category", "MANUAL"))
            categories[category] = categories.get(category, 0) + 1
        top = " / ".join(f"{key}:{value}" for key, value in list(categories.items())[:6]) if categories else "无"
        return f"当前候选 {len(entries)} 条，启用 {enabled} 条；分类概览：{top}"

    @staticmethod
    def rebuild_metadata(payload: MappingData | None) -> None:
        if not payload:
            return
        entries = SanitizeMappingService.entries(payload)
        replacements: dict[str, str] = {}
        categories: dict[str, str] = {}
        counts: dict[str, int] = {}
        for entry in entries:
            if not bool(entry.get("enabled", True)):
                continue
            placeholder = str(entry.get("placeholder", "")).strip()
            original = str(entry.get("original", "")).strip()
            category = str(entry.get("category", "MANUAL")).strip().upper()
            if not placeholder or not original:
                continue
            replacements[placeholder] = original
            categories[placeholder] = category
            counts[category] = counts.get(category, 0) + 1
        payload["entries"] = entries
        payload["replacements"] = replacements
        payload["categories"] = categories
        payload["counts"] = counts

    @staticmethod
    def compact_placeholders(entries: list[dict[str, object]]) -> dict[str, str]:
        return compact_entry_placeholders(entries)

    @staticmethod
    def parse_batch_line(line: str) -> tuple[str, str, str]:
        text = line.strip()
        if not text:
            return "", "", ""
        if "=>" in text:
            left, right = [part.strip() for part in text.split("=>", 1)]
            if left and right:
                if SanitizeMappingService.looks_like_category_token(left):
                    return right, left.upper(), ""
                return left, "", right
        if "->" in text:
            left, right = [part.strip() for part in text.split("->", 1)]
            if left and right:
                if SanitizeMappingService.looks_like_category_token(left):
                    return right, left.upper(), ""
                return left, "", right
        for sep in ("|", "\t", "，", ","):
            if sep in text:
                left, right = [part.strip() for part in text.split(sep, 1)]
                if not left or not right:
                    continue
                if SanitizeMappingService.looks_like_category_token(left):
                    return right, left.upper(), ""
                if SanitizeMappingService.looks_like_placeholder_token(right):
                    return left, "", right
                if SanitizeMappingService.looks_like_category_token(right):
                    return left, right.upper(), ""
        return text, "", ""

    @staticmethod
    def looks_like_category_token(text: str) -> bool:
        return text.strip().upper() in SanitizeMappingService.CATEGORY_TOKENS

    @staticmethod
    def looks_like_placeholder_token(text: str) -> bool:
        return bool(re.fullmatch(r"(?:__)?[A-Za-z]+(?:_[0-9]{1,4})?(?:__)?", text.strip()))

    @staticmethod
    def next_placeholder(entries: list[dict[str, object]], category: str = "MANUAL", exclude_index: int | None = None) -> str:
        index = 1
        used = {
            str(item.get("placeholder", "")).strip().upper()
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
        entries: list[dict[str, object]],
        preferred_category: str,
        exclude_index: int | None = None,
    ) -> tuple[str, str]:
        raw = raw_value.strip()
        category = preferred_category.upper() or "MANUAL"
        if raw:
            cleaned = raw.upper().replace("-", "_").replace(" ", "_")
            cleaned = re.sub(r"_+", "_", cleaned).strip("_")
            match = re.fullmatch(r"(?:__)?([A-Z]+)(?:_)?(\d+)?(?:__)?", cleaned)
            if match:
                category = match.group(1).upper()
                if match.group(2):
                    desired = f"__{category}_{int(match.group(2)):03d}__"
                    used = {
                        str(item.get("placeholder", "")).strip().upper()
                        for idx, item in enumerate(entries)
                        if exclude_index is None or idx != exclude_index
                    }
                    if desired.upper() not in used:
                        return desired, category
                return SanitizeMappingService.tail_placeholder(entries, category, exclude_index=exclude_index), category
        return SanitizeMappingService.next_placeholder(entries, category, exclude_index=exclude_index), category

    @staticmethod
    def tail_placeholder(entries: list[dict[str, object]], category: str, exclude_index: int | None = None) -> str:
        category = category.upper()
        max_index = 0
        for idx, item in enumerate(entries):
            if exclude_index is not None and idx == exclude_index:
                continue
            placeholder = str(item.get("placeholder", "")).strip().upper()
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
    def manual_entry(original: str, placeholder_hint: str, entries: list[dict[str, object]]) -> dict[str, object]:
        category = SanitizeMappingService.infer_sensitive_category(original, placeholder_hint)
        placeholder, _ = SanitizeMappingService.normalize_placeholder_input(placeholder_hint or "", entries, category)
        return {
            "placeholder": placeholder,
            "original": original,
            "category": SanitizeMappingService.infer_manual_category(placeholder, original),
            "enabled": True,
            "source": "manual",
        }
