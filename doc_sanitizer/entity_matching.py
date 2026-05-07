"""Fuzzy entity matching for sanitization mappings.

This module owns same-entity grouping for mapping entries. Placeholder repair and prompt
building live in sibling modules so each fuzzy workflow stays narrow.
"""

from __future__ import annotations

import re
import string
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

from .mapping import ReplacementItem


COMPANY_SUFFIXES = (
    "股份有限公司",
    "有限责任公司",
    "集团股份有限公司",
    "集团有限公司",
    "有限公司",
    "责任公司",
    "控股集团",
    "控股",
    "集团",
    "公司",
    "技术",
    "科技",
    "corporation",
    "company",
    "limited",
    "incorporated",
    "ltd",
    "llc",
    "inc",
    "co",
)
PUNCT_TRANSLATION = str.maketrans("", "", string.punctuation + "，。、《》？；：‘’“”（）【】「」『』、·—…￥")


@dataclass(frozen=True)
class EntityMatch:
    left: ReplacementItem
    right: ReplacementItem
    score: float
    reason: str


@dataclass(frozen=True)
class EntityGroup:
    items: list[ReplacementItem]
    score: float
    reason: str


def normalize_entity_name(value: str, category: str = "") -> str:
    """Normalize entity names for fuzzy grouping without changing the stored original value."""
    text = unicodedata.normalize("NFKC", value).strip().lower()
    text = text.translate(PUNCT_TRANSLATION)
    text = re.sub(r"\s+", "", text)
    if category.upper() in {"COMPANY", "CUSTOMER", "SUPPLIER", "AUTO", "MANUAL"}:
        changed = True
        while changed:
            changed = False
            for suffix in COMPANY_SUFFIXES:
                if text.endswith(suffix) and len(text) > len(suffix) + 1:
                    text = text[: -len(suffix)]
                    changed = True
                    break
    return text


def entity_similarity(left: ReplacementItem, right: ReplacementItem) -> tuple[float, str]:
    """Score whether two mapping entries likely refer to the same real-world entity."""
    if left.placeholder == right.placeholder:
        return 0.0, "same placeholder"
    if left.category != right.category and left.category not in {"AUTO", "MANUAL"} and right.category not in {"AUTO", "MANUAL"}:
        return 0.0, "category mismatch"

    a = normalize_entity_name(left.original, left.category)
    b = normalize_entity_name(right.original, right.category)
    if not a or not b:
        return 0.0, "empty"
    if a == b:
        return 0.98, "normalized exact match"

    shorter, longer = sorted((a, b), key=len)
    if len(shorter) >= 2 and shorter in longer:
        ratio = len(shorter) / len(longer)
        return min(0.94, 0.76 + ratio * 0.18), "substring match"

    seq = SequenceMatcher(None, a, b).ratio()
    common = longest_common_substring_ratio(a, b)
    score = max(seq, common)
    if score >= 0.72:
        return score, "fuzzy text match"
    return score, "weak match"


def longest_common_substring_ratio(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    matcher = SequenceMatcher(None, left, right)
    match = max(matcher.get_matching_blocks(), key=lambda block: block.size, default=None)
    if not match or match.size == 0:
        return 0.0
    return (match.size * 2) / (len(left) + len(right))


def find_entity_matches(items: list[ReplacementItem], threshold: float = 0.70) -> list[EntityMatch]:
    matches: list[EntityMatch] = []
    for idx, left in enumerate(items):
        for right in items[idx + 1 :]:
            score, reason = entity_similarity(left, right)
            if score >= threshold:
                matches.append(EntityMatch(left=left, right=right, score=score, reason=reason))
    return sorted(matches, key=lambda item: item.score, reverse=True)


def group_entity_matches(items: list[ReplacementItem], threshold: float = 0.78) -> list[EntityGroup]:
    """Build same-entity groups from pairwise similarity scores."""
    parent = list(range(len(items)))

    def find(idx: int) -> int:
        while parent[idx] != idx:
            parent[idx] = parent[parent[idx]]
            idx = parent[idx]
        return idx

    def union(left: int, right: int) -> None:
        root_left = find(left)
        root_right = find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    pair_meta: dict[tuple[int, int], tuple[float, str]] = {}
    for i, left in enumerate(items):
        for j, right in enumerate(items[i + 1 :], start=i + 1):
            score, reason = entity_similarity(left, right)
            if score >= threshold:
                union(i, j)
                pair_meta[(i, j)] = (score, reason)

    groups_by_root: dict[int, list[int]] = {}
    for idx in range(len(items)):
        groups_by_root.setdefault(find(idx), []).append(idx)

    groups: list[EntityGroup] = []
    for indexes in groups_by_root.values():
        if len(indexes) < 2:
            continue
        scores = [
            pair_meta[(min(i, j), max(i, j))]
            for pos, i in enumerate(indexes)
            for j in indexes[pos + 1 :]
            if (min(i, j), max(i, j)) in pair_meta
        ]
        best_score, reason = max(scores, default=(threshold, "related names"))
        group_items = sorted((items[idx] for idx in indexes), key=lambda item: (-len(item.original), item.placeholder))
        groups.append(EntityGroup(items=group_items, score=best_score, reason=reason))
    return sorted(groups, key=lambda group: group.score, reverse=True)


