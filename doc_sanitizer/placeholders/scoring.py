"""Similarity scoring for damaged placeholder repair."""

from __future__ import annotations

from difflib import SequenceMatcher

from ..mapping import ReplacementItem
from .parser import PlaceholderParts, parse_placeholder_like_parts, parse_placeholder_parts


def placeholder_category_score(left: str, right: str) -> float:
    if left == right:
        return 1.0
    if len(left) >= 3 and right.endswith(left):
        return 0.92
    if len(right) >= 3 and left.endswith(right):
        return 0.92
    return SequenceMatcher(None, left, right).ratio()


def placeholder_index_score(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left == right:
        return 1.0
    return SequenceMatcher(None, left, right).ratio()


def placeholder_repair_score(token_parts: PlaceholderParts, target_parts: PlaceholderParts) -> float:
    """Score a damaged placeholder against a known placeholder.

    The index is weighted more heavily than category similarity. Repairing PROJECT_015 into
    an existing PROJECT_005 is worse than leaving it for manual review.
    """
    category_score = placeholder_category_score(token_parts.category, target_parts.category)
    index_score = placeholder_index_score(token_parts.raw_index, target_parts.raw_index)
    if token_parts.index == target_parts.index:
        if category_score == 1.0:
            return 1.0
        if category_score >= 0.86:
            return 0.92
        if category_score >= 0.66:
            return 0.78
        return 0.0
    if category_score >= 0.86 and index_score >= 0.78:
        return min(0.89, 0.72 + index_score * 0.16)
    return 0.0


def closest_placeholder_for_token(token: str, items: list[ReplacementItem], min_score: float = 0.0) -> tuple[str, float]:
    token_parts = parse_placeholder_parts(token) or parse_placeholder_like_parts(token)
    if token_parts is None:
        return "", 0.0
    best_placeholder = ""
    best_score = 0.0
    for item in items:
        target_parts = parse_placeholder_parts(item.placeholder)
        if target_parts is None:
            continue
        score = placeholder_repair_score(token_parts, target_parts)
        if score > best_score:
            best_placeholder = item.placeholder
            best_score = score
    if best_score < min_score:
        return "", best_score
    return best_placeholder, best_score
