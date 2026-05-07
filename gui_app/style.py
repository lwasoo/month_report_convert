"""Shared GUI theme and ttk style setup."""

from __future__ import annotations

import sys
import tkinter as tk
from tkinter import ttk

import customtkinter as ctk


class StyleMixin:
    def _configure_style(self) -> None:
        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")
        self.ttk_style = ttk.Style()
        try:
            self.ttk_style.theme_use("vista" if sys.platform == "win32" else "clam")
        except tk.TclError:
            try:
                self.ttk_style.theme_use("clam")
            except tk.TclError:
                pass
        self._apply_base_style()

    def _palette(self) -> dict[str, str]:
        return {
            "app_bg": "#eef3f8",
            "panel": "#eef3f8",
            "card": "#ffffff",
            "sidebar": "#172236",
            "sidebar_hover": "#22324c",
            "text": "#17324d",
            "muted": "#64748b",
            "field": "#2f485f",
            "accent": "#2f6fed",
            "tree_bg": "#ffffff",
            "tree_heading": "#f5f8fc",
        }

    def _apply_base_style(self) -> None:
        colors = self._palette()
        try:
            self.root.configure(fg_color=colors["app_bg"])
        except tk.TclError:
            self.root.configure(bg=colors["app_bg"])
        style = self.ttk_style
        style.configure(".", font=("Microsoft YaHei UI", 10))
        style.configure("App.TFrame", background=colors["card"])
        style.configure("Card.TFrame", background=colors["card"])
        style.configure("Header.TFrame", background=colors["app_bg"])
        style.configure("HeaderTitle.TLabel", background=colors["app_bg"], foreground=colors["text"], font=("Microsoft YaHei UI", 16, "bold"))
        style.configure("HeaderSub.TLabel", background=colors["app_bg"], foreground=colors["muted"], font=("Microsoft YaHei UI", 9))
        style.configure("AboutThanks.TLabel", background=colors["card"], foreground=colors["text"], font=("Microsoft YaHei UI", 22, "bold"))
        style.configure("RiskNotice.TLabel", background=colors["card"], foreground="#f97361", font=("Microsoft YaHei UI", 10))
        style.configure("Section.TLabelframe", background=colors["card"], borderwidth=1, relief="solid")
        style.configure("Section.TLabelframe.Label", background=colors["card"], foreground=colors["text"], font=("Microsoft YaHei UI", 11, "bold"))
        style.configure("Field.TLabel", background=colors["card"], foreground=colors["field"])
        style.configure("Mono.TLabel", background=colors["card"], foreground=colors["text"], font=("Consolas", 10))
        style.configure("Hint.TLabel", background=colors["card"], foreground=colors["muted"], font=("Microsoft YaHei UI", 9))
        style.configure("Status.TLabel", background=colors["card"], foreground=colors["muted"], font=("Microsoft YaHei UI", 9))
        style.configure("TButton", padding=(10, 6))
        style.configure("TEntry", padding=(6, 4), fieldbackground=colors["card"], foreground=colors["text"])
        style.configure("TCombobox", padding=(6, 4), fieldbackground=colors["card"], foreground=colors["text"])
        style.configure("Primary.TButton", font=("Microsoft YaHei UI", 10, "bold"), padding=(11, 6))
        style.configure("Secondary.TButton", padding=(10, 6))
        style.configure("Mapping.Treeview", rowheight=32, font=("Microsoft YaHei UI", 11), borderwidth=0, background=colors["tree_bg"], fieldbackground=colors["tree_bg"], foreground=colors["text"])
        style.configure("Mapping.Treeview.Heading", font=("Microsoft YaHei UI", 10, "bold"), background=colors["tree_heading"], foreground=colors["field"])
