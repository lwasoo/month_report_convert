"""Shared Tk widgets and placeholder hint helpers."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from tkinter.scrolledtext import ScrolledText


class SharedWidgetsMixin:
    def _create_log_widget(self, parent: ttk.Frame) -> ScrolledText:
        widget = ScrolledText(
            parent,
            height=12,
            wrap=tk.WORD,
            font=("Cascadia Mono", 11),
            background="#0f1720",
            foreground="#d9e7f5",
            insertbackground="#d9e7f5",
            relief=tk.FLAT,
            padx=12,
            pady=12,
        )
        widget.tag_configure("INFO", foreground="#d9e7f5")
        widget.tag_configure("WARN", foreground="#ffd866")
        widget.tag_configure("ERROR", foreground="#ff6b6b")
        widget.tag_configure("NOTICE", foreground="#72d4ff")
        widget.configure(state=tk.DISABLED)
        return widget

    def _setup_placeholder_hints(self) -> None:
        self._install_entry_placeholder(self.manual_sensitive_entry, self.manual_sensitive_var, self.manual_sensitive_placeholder)
        self._install_entry_placeholder(self.manual_placeholder_entry, self.manual_placeholder_var, self.manual_placeholder_hint)
        self._install_text_placeholder(self.batch_add_text, self.batch_placeholder_text)

    @staticmethod
    def _install_entry_placeholder(entry: tk.Entry, var: tk.StringVar, placeholder: str) -> None:
        normal_fg = "#111111"
        placeholder_fg = "#9aa8b6"

        def show_placeholder() -> None:
            if not var.get():
                entry.configure(fg=placeholder_fg)
                var.set(placeholder)
                entry.selection_clear()

        def clear_placeholder() -> None:
            if entry.cget("fg") == placeholder_fg and var.get() == placeholder:
                var.set("")
                entry.configure(fg=normal_fg)

        show_placeholder()
        entry.bind("<FocusIn>", lambda _e: clear_placeholder(), add="+")
        entry.bind("<FocusOut>", lambda _e: show_placeholder() if not var.get().strip() else entry.configure(fg=normal_fg), add="+")

    @staticmethod
    def _install_text_placeholder(widget: tk.Text, placeholder: str) -> None:
        normal_fg = "#111111"
        placeholder_fg = "#9aa8b6"

        def show_placeholder() -> None:
            if widget.get("1.0", tk.END).strip():
                return
            widget.configure(fg=placeholder_fg)
            widget.delete("1.0", tk.END)
            widget.insert("1.0", placeholder)

        def clear_placeholder() -> None:
            if widget.cget("fg") == placeholder_fg:
                widget.delete("1.0", tk.END)
                widget.configure(fg=normal_fg)

        show_placeholder()
        widget.bind("<FocusIn>", lambda _e: clear_placeholder(), add="+")
        widget.bind("<FocusOut>", lambda _e: show_placeholder() if not widget.get("1.0", tk.END).strip() else widget.configure(fg=normal_fg), add="+")

    def _add_path_row(self, frame: ttk.Frame, row: int, label: str, var: tk.StringVar, browse_cmd) -> None:
        ttk.Label(frame, text=label, style="Field.TLabel").grid(row=row, column=0, sticky="w", pady=6)
        row_frame = ttk.Frame(frame, style="Card.TFrame")
        row_frame.grid(row=row, column=1, sticky="ew", pady=6)
        row_frame.columnconfigure(0, weight=1)
        ttk.Entry(row_frame, textvariable=var).grid(row=0, column=0, sticky="ew")
        ttk.Button(row_frame, text="浏览", command=browse_cmd).grid(row=0, column=1, padx=(8, 0))
