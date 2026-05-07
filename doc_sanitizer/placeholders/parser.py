"""Placeholder token parsing and normalization."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


PLACEHOLDER_RE = re.compile(r"_{0,2}([A-Za-z][A-Za-z0-9]*)(?:[\s_\-]+(\d{1,5}|MANUAL))_{0,2}")
PLACEHOLDER_LIKE_RE = re.compile(
    r"_{0,2}(COMPANY|PERSON|PROJECT|CASE|CODE|CUSTOMER|SUPPLIER|TITLE|AMOUNT)(?:[\s_\-]+)(\d{1,5}|MANUAL)[A-Za-z]*_{0,2}",
    re.IGNORECASE,
)
PLACEHOLDER_CATEGORIES = ("COMPANY", "PERSON", "PROJECT", "CASE", "CODE", "CUSTOMER", "SUPPLIER", "TITLE", "AMOUNT")


@dataclass(frozen=True)
class PlaceholderParts:
    category: str
    index: str
    raw_index: str
    canonical: str


def canonical_placeholder(value: str) -> str:
    parts = parse_placeholder_parts(value)
    return parts.canonical if parts else ""


def parse_placeholder_parts(value: str) -> PlaceholderParts | None:
    """Parse a placeholder-like token into normalized category and index parts."""
    match = PLACEHOLDER_RE.fullmatch(unicodedata.normalize("NFKC", value).strip())
    if not match:
        return None
    category = match.group(1).upper()
    index = match.group(2)
    if not index:
        return PlaceholderParts(category=category, index="", raw_index="", canonical=f"__{category}__")
    if index.upper() == "MANUAL":
        return PlaceholderParts(category=category, index="MANUAL", raw_index="MANUAL", canonical=f"__{category}_MANUAL__")
    normalized_index = f"{int(index):03d}"
    return PlaceholderParts(category=category, index=normalized_index, raw_index=index, canonical=f"__{category}_{normalized_index}__")


def parse_placeholder_like_parts(token: str) -> PlaceholderParts | None:
    match = PLACEHOLDER_LIKE_RE.fullmatch(unicodedata.normalize("NFKC", token).strip())
    if not match:
        return None
    category = match.group(1).upper()
    raw_index = match.group(2)
    if raw_index.upper() == "MANUAL":
        return PlaceholderParts(category=category, index="MANUAL", raw_index="MANUAL", canonical=f"__{category}_MANUAL__")
    normalized_index = f"{int(raw_index):03d}"
    return PlaceholderParts(category=category, index=normalized_index, raw_index=raw_index, canonical=f"__{category}_{normalized_index}__")


def placeholder_token_category(token: str) -> str:
    match = PLACEHOLDER_LIKE_RE.fullmatch(unicodedata.normalize("NFKC", token).strip())
    return match.group(1).upper() if match else ""
