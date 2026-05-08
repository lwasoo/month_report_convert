"""GUI tab for restoring sanitized documents from reviewed mappings."""

from __future__ import annotations

from .actions import RestoreActionsMixin
from .dialogs import RestoreDialogsMixin
from .layout import RestoreLayoutMixin
from .repairs import RestoreRepairsMixin


class RestoreTabMixin(RestoreLayoutMixin, RestoreActionsMixin, RestoreRepairsMixin, RestoreDialogsMixin):
    """Compose restore tab layout, actions, placeholder repair planning, and dialogs."""
