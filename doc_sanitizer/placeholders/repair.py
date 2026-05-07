"""High-level placeholder repair helpers.

External AI tools often drop underscores, change category spelling, or glue placeholders to
neighboring text. Parsing, detection, and scoring live in narrower modules; this file combines
them into repair suggestions and repair application.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..mapping import ReplacementItem
from .detection import (
    BROKEN_PLACEHOLDER_TAIL_RE,
    best_broken_placeholder_tail,
    find_placeholder_like_tokens,
    unresolved_placeholder_tokens,
)
from .parser import (
    PLACEHOLDER_CATEGORIES,
    PLACEHOLDER_LIKE_RE,
    PLACEHOLDER_RE,
    PlaceholderParts,
    canonical_placeholder,
    parse_placeholder_like_parts,
    parse_placeholder_parts,
    placeholder_token_category,
)
from .scoring import (
    closest_placeholder_for_token,
    placeholder_category_score,
    placeholder_index_score,
    placeholder_repair_score,
)


@dataclass(frozen=True)
class PlaceholderRepair:
    token: str
    canonical: str
    score: float


def suggest_placeholder_repairs(text: str, items: list[ReplacementItem], min_score: float = 0.70) -> list[PlaceholderRepair]:
    """Suggest placeholder repairs; callers decide which score bands can be auto-applied."""
    canonical_set = {item.placeholder.upper(): item.placeholder for item in items}
    target_parts = [
        (item.placeholder, parsed)
        for item in items
        for parsed in [parse_placeholder_parts(item.placeholder)]
        if parsed is not None
    ]
    repairs: list[PlaceholderRepair] = []
    for match in PLACEHOLDER_RE.finditer(text):
        if is_embedded_placeholder_match(text, match.start(), match.end()):
            continue
        token = match.group(0)
        token_parts = parse_placeholder_parts(token)
        if not token_parts:
            continue
        target = canonical_set.get(token_parts.canonical.upper())
        if target and token != target:
            repairs.append(PlaceholderRepair(token=token, canonical=target, score=1.0))
            continue
        best_target = ""
        best_score = 0.0
        for placeholder, parts in target_parts:
            score = placeholder_repair_score(token_parts, parts)
            if score > best_score:
                best_score = score
                best_target = placeholder
        if best_target and best_score >= min_score and token != best_target:
            repairs.append(PlaceholderRepair(token=token, canonical=best_target, score=best_score))
    return repairs


def is_embedded_placeholder_match(text: str, start: int, end: int) -> bool:
    before = text[start - 1] if start > 0 else ""
    after = text[end] if end < len(text) else ""
    return bool((before and is_ascii_word_char(before)) or (after and is_ascii_word_char(after)))


def is_ascii_word_char(char: str) -> bool:
    return char == "_" or ("0" <= char <= "9") or ("A" <= char <= "Z") or ("a" <= char <= "z")


def repair_placeholder_text(
    text: str,
    items: list[ReplacementItem],
    min_score: float = 0.84,
    confirmed_repairs: dict[str, str] | None = None,
) -> str:
    """Apply confirmed repairs first, or derive repairs from the current mapping when absent."""
    repairs = confirmed_repairs
    if repairs is None:
        repairs = {repair.token: repair.canonical for repair in suggest_placeholder_repairs(text, items, min_score=min_score)}
    return apply_placeholder_repairs(text, repairs)


def apply_placeholder_repairs(text: str, repairs: dict[str, str]) -> str:
    updated = text
    for token, canonical in sorted(repairs.items(), key=lambda item: len(item[0]), reverse=True):
        if token and canonical and token != canonical:
            updated = updated.replace(token, canonical)
    return updated


__all__ = [
    "PlaceholderParts",
    "PlaceholderRepair",
    "BROKEN_PLACEHOLDER_TAIL_RE",
    "PLACEHOLDER_CATEGORIES",
    "PLACEHOLDER_LIKE_RE",
    "PLACEHOLDER_RE",
    "apply_placeholder_repairs",
    "best_broken_placeholder_tail",
    "canonical_placeholder",
    "closest_placeholder_for_token",
    "find_placeholder_like_tokens",
    "is_ascii_word_char",
    "is_embedded_placeholder_match",
    "parse_placeholder_like_parts",
    "parse_placeholder_parts",
    "placeholder_category_score",
    "placeholder_index_score",
    "placeholder_repair_score",
    "placeholder_token_category",
    "repair_placeholder_text",
    "suggest_placeholder_repairs",
    "unresolved_placeholder_tokens",
]
