"""Detection of placeholder-like tokens in external AI output."""

from __future__ import annotations

import re

from ..mapping import ReplacementItem
from .parser import (
    PLACEHOLDER_CATEGORIES,
    PLACEHOLDER_LIKE_RE,
    parse_placeholder_parts,
    placeholder_token_category,
)
from .scoring import placeholder_category_score


BROKEN_PLACEHOLDER_TAIL_RE = re.compile(
    r"([A-Za-z]{3,})(?:[\s_\-]+)(\d{1,5}|MANUAL)[A-Za-z]*_{0,2}",
    re.IGNORECASE,
)


def find_placeholder_like_tokens(text: str) -> list[str]:
    """Find unknown or damaged placeholder tokens that may need user confirmation."""
    tokens: list[str] = []
    seen_spans: list[tuple[int, int]] = []
    for match in PLACEHOLDER_LIKE_RE.finditer(text):
        tokens.append(match.group(0))
        seen_spans.append(match.span())
    for match in BROKEN_PLACEHOLDER_TAIL_RE.finditer(text):
        if any(start <= match.start() < end for start, end in seen_spans):
            continue
        token = best_broken_placeholder_tail(match.group(0))
        if token:
            tokens.append(token)
    return tokens


def best_broken_placeholder_tail(token: str) -> str:
    """Recover the placeholder-like tail from glued text such as QuantaMPANY_007."""
    parts = re.match(r"([A-Za-z]{3,})([\s_\-]+)(\d{1,5}|MANUAL)([A-Za-z]*_{0,2})$", token, re.IGNORECASE)
    if not parts:
        return ""
    prefix, separator, index, suffix = parts.groups()
    upper_prefix = prefix.upper()
    best_score = 0.0
    best_tail_start = 0
    for category in PLACEHOLDER_CATEGORIES:
        min_start = max(0, len(prefix) - len(category) - 2)
        for tail_start in range(min_start, len(prefix)):
            candidate = upper_prefix[tail_start:]
            if len(candidate) < 3:
                continue
            score = placeholder_category_score(candidate, category)
            if score > best_score:
                best_score = score
                best_tail_start = tail_start
    if best_score < 0.86:
        return ""
    return f"{prefix[best_tail_start:]}{separator}{index}{suffix}"


def unresolved_placeholder_tokens(
    text: str,
    items: list[ReplacementItem],
    placeholder_repairs: dict[str, str] | None = None,
) -> list[str]:
    known = {item.placeholder.upper() for item in items}
    repaired = {token.upper() for token in (placeholder_repairs or {})}
    tokens: list[str] = []
    seen: set[str] = set()
    for token in find_placeholder_like_tokens(text):
        if token.upper() in repaired:
            continue
        parts = parse_placeholder_parts(token)
        if parts and parts.canonical.upper() in known:
            continue
        key = token.upper()
        if key in seen:
            continue
        seen.add(key)
        tokens.append(token)
    return tokens


__all__ = [
    "best_broken_placeholder_tail",
    "find_placeholder_like_tokens",
    "placeholder_token_category",
    "unresolved_placeholder_tokens",
]
