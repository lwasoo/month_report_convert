"""Deprecated compatibility facade for fuzzy mapping helpers.

The implementation is split by responsibility:
- entity_matching: same-entity scoring and grouping
- placeholder_repair: damaged placeholder detection and repair
- prompt_builder: external prompt and internal audit text generation

Do not add business logic here. Older callers may keep importing this module, but new code
must import the narrower modules directly.
"""

from __future__ import annotations

from .entity_matching import (
    COMPANY_SUFFIXES,
    PUNCT_TRANSLATION,
    EntityGroup,
    EntityMatch,
    entity_similarity,
    find_entity_matches,
    group_entity_matches,
    longest_common_substring_ratio,
    normalize_entity_name,
)
from .placeholder_repair import (
    BROKEN_PLACEHOLDER_TAIL_RE,
    PLACEHOLDER_CATEGORIES,
    PLACEHOLDER_LIKE_RE,
    PLACEHOLDER_RE,
    PlaceholderParts,
    PlaceholderRepair,
    apply_placeholder_repairs,
    best_broken_placeholder_tail,
    canonical_placeholder,
    closest_placeholder_for_token,
    find_placeholder_like_tokens,
    is_ascii_word_char,
    is_embedded_placeholder_match,
    parse_placeholder_like_parts,
    parse_placeholder_parts,
    placeholder_category_score,
    placeholder_index_score,
    placeholder_repair_score,
    placeholder_token_category,
    repair_placeholder_text,
    suggest_placeholder_repairs,
    unresolved_placeholder_tokens,
)
from .prompt_builder import (
    build_external_ai_prompt,
    build_external_ai_prompt_sections,
    enabled_items_from_payload,
    payload_from_json_text,
)

__all__ = [
    "BROKEN_PLACEHOLDER_TAIL_RE",
    "COMPANY_SUFFIXES",
    "PLACEHOLDER_CATEGORIES",
    "PLACEHOLDER_LIKE_RE",
    "PLACEHOLDER_RE",
    "PUNCT_TRANSLATION",
    "EntityGroup",
    "EntityMatch",
    "PlaceholderParts",
    "PlaceholderRepair",
    "apply_placeholder_repairs",
    "best_broken_placeholder_tail",
    "build_external_ai_prompt",
    "build_external_ai_prompt_sections",
    "canonical_placeholder",
    "closest_placeholder_for_token",
    "enabled_items_from_payload",
    "entity_similarity",
    "find_entity_matches",
    "find_placeholder_like_tokens",
    "group_entity_matches",
    "is_ascii_word_char",
    "is_embedded_placeholder_match",
    "longest_common_substring_ratio",
    "normalize_entity_name",
    "parse_placeholder_like_parts",
    "parse_placeholder_parts",
    "payload_from_json_text",
    "placeholder_category_score",
    "placeholder_index_score",
    "placeholder_repair_score",
    "placeholder_token_category",
    "repair_placeholder_text",
    "suggest_placeholder_repairs",
    "unresolved_placeholder_tokens",
]
