"""GUI tab for restoring sanitized documents from reviewed mappings."""

from __future__ import annotations

import queue
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText

from .actions import RestoreActions
from .dialogs import RestoreDialogs
from .layout import RestoreLayout
from .repairs import RestoreRepairPlanner


class RestoreTabController(RestoreLayout, RestoreActions, RestoreRepairPlanner, RestoreDialogs):
    """Own restore-tab state and behavior without exposing it on the app shell."""

    def __init__(
        self,
        parent: ttk.Frame,
        *,
        root: tk.Tk,
        log_queue: queue.Queue[tuple[str, str]],
        start_worker: Callable[[str, tk.StringVar, str, Callable[[], None]], None],
        unique_output_path: Callable[[Path], Path],
        create_log_widget: Callable[[ttk.Frame], ScrolledText],
        add_path_row: Callable[[ttk.Frame, int, str, tk.StringVar, Callable[[], None]], None],
    ) -> None:
        self.root = root
        self.log_queue = log_queue
        self._start_worker_callback = start_worker
        self._unique_output_path_callback = unique_output_path
        self._create_log_widget_callback = create_log_widget
        self._add_path_row_callback = add_path_row

        self.restore_input_var = tk.StringVar()
        self.restore_output_var = tk.StringVar()
        self.restore_mapping_var = tk.StringVar()
        self.restore_status_var = tk.StringVar(value="就绪")
        self.restore_log_text: ScrolledText
        self._last_manual_placeholder_repairs: dict[str, str] = {}

        self._build_restore_tab(parent)

    def _start_worker(self, target: str, status_var: tk.StringVar, start_msg: str, func: Callable[[], None]) -> None:
        self._start_worker_callback(target, status_var, start_msg, func)

    def _unique_output_path(self, path: Path) -> Path:
        return self._unique_output_path_callback(path)

    def _create_log_widget(self, parent: ttk.Frame) -> ScrolledText:
        return self._create_log_widget_callback(parent)

    def _add_path_row(self, frame: ttk.Frame, row: int, label: str, var: tk.StringVar, browse_cmd: Callable[[], None]) -> None:
        self._add_path_row_callback(frame, row, label, var, browse_cmd)

    def set_mapping_path_if_empty(self, mapping_path: Path) -> None:
        if not self.restore_mapping_var.get().strip():
            self.restore_mapping_var.set(str(mapping_path))

