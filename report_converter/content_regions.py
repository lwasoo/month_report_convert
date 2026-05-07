"""Compatibility facade for content region layout helpers.

Do not add business logic here.
"""

from __future__ import annotations

from .ppt.content_regions import (  # noqa: F401
    _find_content_region,
    _find_content_regions,
    _subtract_interval,
    _write_lines_to_box,
    _write_rows_across_regions,
    add_content_textbox,
    get_theme_palette,
    split_balanced,
    style_paragraph,
    suggest_font_size,
)

__all__ = [
    "_find_content_region",
    "_find_content_regions",
    "_subtract_interval",
    "_write_lines_to_box",
    "_write_rows_across_regions",
    "add_content_textbox",
    "get_theme_palette",
    "split_balanced",
    "style_paragraph",
    "suggest_font_size",
]
