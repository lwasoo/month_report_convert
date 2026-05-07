"""GUI tab for scanning, reviewing, and applying document sanitization mappings."""

from __future__ import annotations

from .actions import SanitizeActionsMixin
from .layout import SanitizeLayoutMixin
from .table import SanitizeTableMixin


class SanitizeTabMixin(SanitizeLayoutMixin, SanitizeActionsMixin, SanitizeTableMixin):
    """Compose sanitize tab layout, actions, and mapping table behavior."""

