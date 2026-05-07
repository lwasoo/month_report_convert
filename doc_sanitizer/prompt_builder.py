"""External AI prompt generation from sanitization mapping payloads.

The copyable prompt must not expose original sensitive terms. Internal audit text is built
separately so users can review grouping decisions without leaking that data externally.
"""

from __future__ import annotations

import json
from typing import Any

from .entity_matching import EntityGroup, find_entity_matches, group_entity_matches
from .mapping import ReplacementItem, mapping_entries, normalize_entries


def payload_from_json_text(raw: str) -> dict[str, Any]:
    """Load either the current entries schema or the older replacements/categories schema."""
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("JSON 顶层必须是对象。")
    if "entries" in data:
        entries = data["entries"]
    else:
        replacements = data.get("replacements", {})
        categories = data.get("categories", {})
        if not isinstance(replacements, dict):
            raise ValueError("JSON 中没有 entries，也没有有效 replacements。")
        entries = [
            {
                "placeholder": placeholder,
                "original": original,
                "category": categories.get(placeholder, "AUTO") if isinstance(categories, dict) else "AUTO",
                "enabled": True,
                "source": "imported",
            }
            for placeholder, original in replacements.items()
        ]
    payload = {"version": 2, "entries": normalize_entries(entries if isinstance(entries, list) else [])}
    if not payload["entries"]:
        raise ValueError("JSON 中没有可用映射条目。")
    return payload


def enabled_items_from_payload(payload: dict[str, Any]) -> list[ReplacementItem]:
    return mapping_entries(payload, only_enabled=True)


def build_external_ai_prompt(payload: dict[str, Any]) -> str:
    return build_external_ai_prompt_sections(payload)[0]


def build_external_ai_prompt_sections(payload: dict[str, Any]) -> tuple[str, str]:
    items = enabled_items_from_payload(payload)
    groups = group_entity_matches(items)
    return "\n".join(_build_external_prompt_lines(groups)), "\n".join(_build_internal_audit_lines(items, groups))


def _build_external_prompt_lines(groups: list[EntityGroup]) -> list[str]:
    """Build the copyable prompt section that must not expose original sensitive terms."""
    prompt_lines = [
        "你将处理一份已经脱敏的文档。请遵守：",
        "1. 占位符必须逐字保留，只能使用输入中已经出现的占位符，如 __COMPANY_001__、__PERSON_003__。",
        "2. 不得新增、猜测、改写、重新编号任何占位符。",
        "3. 除非删除整句，否则句中的占位符必须保留原样。",
        "",
    ]

    if groups:
        prompt_lines.extend(["同一对象提示：以下多个占位符可能指向同一个对象，改写时请保持指代关系一致。"])
        for idx, group in enumerate(groups, start=1):
            placeholders = " / ".join(item.placeholder for item in group.items)
            prompt_lines.append(f"- 组 {idx}: {placeholders}")
        prompt_lines.append("")

    prompt_lines.extend(
        [
            "最终交付要求：",
            "- 返回前自检：所有仍被保留的占位符必须与输入完全一致。",
        ]
    )
    return prompt_lines


def _build_internal_audit_lines(items: list[ReplacementItem], groups: list[EntityGroup]) -> list[str]:
    """Build the internal-only audit section with original terms for human review."""
    audit_lines = [
        "内部审核说明（不要发给外部 AI）：",
        "以下信息用于解释为什么这些占位符被归为同一对象，包含原始敏感词。",
        "",
    ]
    if groups:
        audit_lines.append("同一对象归组理由：")
        for idx, group in enumerate(groups, start=1):
            placeholders = " / ".join(item.placeholder for item in group.items)
            originals = " / ".join(item.original for item in group.items)
            audit_lines.append(f"- 组 {idx}: {placeholders}")
            audit_lines.append(f"  原始名称线索：{originals}")
            audit_lines.append(f"  规则理由：{group.reason}，相似度 {group.score:.2f}")
    else:
        audit_lines.append("未发现高置信同一对象归组。")

    review_matches = [
        match
        for match in find_entity_matches(items, threshold=0.62)
        if all(match.left not in group.items or match.right not in group.items for group in groups)
    ][:20]
    if review_matches:
        audit_lines.extend(["", "仅供内部人工复核的相近对象候选："])
        for match in review_matches:
            audit_lines.append(
                f"- {match.left.placeholder}（{match.left.original}） <-> "
                f"{match.right.placeholder}（{match.right.original}），相似度 {match.score:.2f}，理由：{match.reason}"
            )

    return audit_lines
