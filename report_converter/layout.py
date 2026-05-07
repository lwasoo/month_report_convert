"""Deprecated compatibility facade for PowerPoint layout helpers.

Implementation is split into slide operations, content regions, formal visual layouts, table
filling, and pagination.

Do not add rendering logic here. Older callers may keep importing this module, but new code
must import the narrower modules directly.
"""

from __future__ import annotations

from .content_regions import (
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
from .formal_layout import (
    add_formal_layout_content_v2,
    add_visual_accent,
    choose_formal_variant,
    render_kpi_cards,
    render_risk_matrix,
    render_single_column,
    render_timeline,
    render_two_column,
)
from .pagination import split_into_pages
from .slide_ops import extract_template_slides, insert_slide_after, remove_auto_shapes, set_slide_title_text
from .table_fill import fill_table_metrics

__all__ = [
    "add_content_textbox",
    "add_formal_layout_content_v2",
    "add_visual_accent",
    "choose_formal_variant",
    "extract_template_slides",
    "fill_table_metrics",
    "get_theme_palette",
    "insert_slide_after",
    "remove_auto_shapes",
    "render_kpi_cards",
    "render_risk_matrix",
    "render_single_column",
    "render_timeline",
    "render_two_column",
    "set_slide_title_text",
    "split_balanced",
    "split_into_pages",
    "style_paragraph",
    "suggest_font_size",
]
