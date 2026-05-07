#!/usr/bin/env python3
"""Desktop GUI composition and application lifecycle.

The main window is assembled from tab and support mixins. This module owns shared Tk state,
window setup, navigation, page construction, and command-line entry handling.
"""

from __future__ import annotations

import ctypes
import queue
import re
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk

import customtkinter as ctk

from .about_tab import AboutTabMixin
from .convert_tab import ConvertTabMixin
from .defaults import APP_DISPLAY_NAME, APP_VERSION, DEFAULT_MODEL, DEFAULT_OLLAMA_URL
from .prompt_tab import PromptTabMixin
from .restore_tab import RestoreTabMixin
from .runtime import RuntimeMixin
from .sanitize_tab import SanitizeTabMixin
from .style import StyleMixin
from .update_preferences import is_auto_update_check_enabled
from .widgets import SharedWidgetsMixin


def configure_windows_dpi() -> None:
    """Opt in to Windows DPI awareness before Tk creates the main window."""
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


class ConverterGUI(
    StyleMixin,
    SharedWidgetsMixin,
    RuntimeMixin,
    ConvertTabMixin,
    SanitizeTabMixin,
    RestoreTabMixin,
    PromptTabMixin,
    AboutTabMixin,
):
    def __init__(self, root: tk.Tk, geometry: str | None = None) -> None:
        self.root = root
        self.root.title(f"{APP_DISPLAY_NAME} v{APP_VERSION}")
        self.root.geometry(geometry or "1280x820")
        self.root.minsize(1040, 700)

        self.log_queue: queue.Queue[tuple[str, str]] = queue.Queue()
        self.process: subprocess.Popen[bytes] | None = None
        self.worker_running = False

        self.docx_var = tk.StringVar()
        self.template_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.ollama_url_var = tk.StringVar(value=DEFAULT_OLLAMA_URL)
        self.model_var = tk.StringVar(value=DEFAULT_MODEL)
        self.timeout_var = tk.StringVar(value="180")
        self.retries_var = tk.StringVar(value="2")
        self.no_llm_var = tk.BooleanVar(value=False)
        self.layout_mode_var = tk.StringVar(value="formal")
        self.theme_var = tk.StringVar(value="formal_blue")
        self.diversity_var = tk.StringVar(value="none")
        self.seed_var = tk.StringVar(value="0")
        self.status_var = tk.StringVar(value="就绪")

        self.sanitize_input_var = tk.StringVar()
        self.sanitize_output_var = tk.StringVar()
        self.sanitize_mapping_var = tk.StringVar()
        self.sanitize_status_var = tk.StringVar(value="等待识别")
        self.sanitize_use_llm_var = tk.BooleanVar(value=True)

        self.restore_input_var = tk.StringVar()
        self.restore_output_var = tk.StringVar()
        self.restore_mapping_var = tk.StringVar()
        self.restore_status_var = tk.StringVar(value="就绪")

        self.manual_sensitive_var = tk.StringVar()
        self.manual_placeholder_var = tk.StringVar()
        self.mapping_search_var = tk.StringVar()
        self.current_mapping_data: dict[str, object] | None = None
        self.scan_ready = False
        self.mapping_applied = False
        self.mapping_undo_snapshot: dict[str, object] | None = None
        self.mapping_search_after_id: str | None = None
        self.mapping_editor: tk.Entry | None = None
        self.mapping_editor_item: str | None = None
        self.mapping_editor_column: str | None = None
        self.batch_placeholder_text = "示例：\nCOMPANY|Google LLC\nPERSON|张三\n示例项目=>__PROJECT_008__\n某某科技有限公司"
        self.manual_sensitive_placeholder = "输入敏感词，例如：Google LLC"
        self.manual_placeholder_hint = "可留空；也可写 COMPANY 或 __COMPANY_010__"
        self.app_icon_image: tk.PhotoImage | None = None
        self.app_icon_images: list[tk.PhotoImage] = []
        self.nav_buttons: dict[str, ctk.CTkButton] = {}
        self.nav_pages: dict[str, ttk.Frame] = {}
        self.active_nav_key = ""

        self._configure_style()
        self._apply_window_icon()
        self._build_ui()
        self._setup_placeholder_hints()
        self._update_sanitize_action_states()
        self._pump_logs()
        self.root.after(300, self.detect_models_async)
        if is_auto_update_check_enabled():
            self.root.after(1800, lambda: self.check_updates_async(silent=True))

    def _resource_path(self, relative_path: str) -> Path:
        """Resolve assets both from source checkout and PyInstaller's temporary bundle."""
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass) / relative_path
        return Path(__file__).resolve().parent.parent / relative_path

    def _apply_window_icon(self) -> None:
        icon_png = self._resource_path("assets/icon.png")
        icon_ico = self._resource_path("assets/icon.ico")
        if sys.platform == "win32":
            try:
                if icon_ico.exists():
                    self.root.iconbitmap(str(icon_ico))
            except Exception:
                pass
        try:
            if icon_png.exists():
                self.app_icon_image = tk.PhotoImage(file=str(icon_png))
                self.app_icon_images = [
                    self.app_icon_image.subsample(4, 4),
                    self.app_icon_image.subsample(8, 8),
                    self.app_icon_image.subsample(16, 16),
                    self.app_icon_image.subsample(32, 32),
                ]
                self.root.iconphoto(True, *self.app_icon_images)
        except Exception:
            self.app_icon_image = None
            self.app_icon_images = []

    def _build_ui(self) -> None:
        colors = self._palette()
        shell = ctk.CTkFrame(self.root, fg_color=colors["app_bg"], corner_radius=0)
        shell.pack(fill=tk.BOTH, expand=True)
        shell.grid_columnconfigure(1, weight=1)
        shell.grid_rowconfigure(0, weight=1)

        sidebar = ctk.CTkFrame(shell, width=226, corner_radius=0, fg_color=colors["sidebar"])
        sidebar.grid(row=0, column=0, sticky="ns")
        sidebar.grid_propagate(False)
        sidebar.grid_columnconfigure(0, weight=1)
        sidebar.grid_rowconfigure(9, weight=1)

        ctk.CTkLabel(
            sidebar,
            text=APP_DISPLAY_NAME,
            text_color="#f8fbff",
            font=("Microsoft YaHei UI", 18, "bold"),
            anchor="center",
        ).grid(row=0, column=0, sticky="ew", padx=22, pady=(22, 4))
        ctk.CTkLabel(
            sidebar,
            text=f"v{APP_VERSION}",
            text_color="#93a4bb",
            font=("Microsoft YaHei UI", 12),
            anchor="center",
        ).grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 18))

        content_shell = ctk.CTkFrame(shell, fg_color=colors["app_bg"], corner_radius=0)
        content_shell.grid(row=0, column=1, sticky="nsew")
        content_shell.grid_columnconfigure(0, weight=1)
        content_shell.grid_rowconfigure(1, weight=1)

        header = ctk.CTkFrame(content_shell, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 10))
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header,
            text="文档脱敏与还原工作台",
            text_color=colors["text"],
            font=("Microsoft YaHei UI", 20, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(
            header,
            text="审核映射、生成提示词、还原文档；月报转 PPT。",
            text_color=colors["muted"],
            font=("Microsoft YaHei UI", 11),
            anchor="w",
        ).grid(row=1, column=0, sticky="ew", pady=(4, 0))

        page_shell = ctk.CTkFrame(content_shell, fg_color=colors["card"], corner_radius=14)
        page_shell.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
        page_shell.grid_columnconfigure(0, weight=1)
        page_shell.grid_rowconfigure(0, weight=1)

        sanitize_tab = ttk.Frame(page_shell, style="App.TFrame", padding=10)
        restore_tab = ttk.Frame(page_shell, style="App.TFrame", padding=10)
        prompt_tab = ttk.Frame(page_shell, style="App.TFrame", padding=10)
        convert_tab = ttk.Frame(page_shell, style="App.TFrame", padding=10)
        about_tab = ttk.Frame(page_shell, style="App.TFrame", padding=10)
        self.nav_pages = {
            "sanitize": sanitize_tab,
            "restore": restore_tab,
            "prompt": prompt_tab,
            "convert": convert_tab,
            "about": about_tab,
        }
        for page in self.nav_pages.values():
            page.grid(row=0, column=0, sticky="nsew")

        nav_items = [
            ("sanitize", "脱敏", "识别、审核和生成脱敏文档"),
            ("prompt", "AI Prompt", "生成外部 AI 使用提示"),
            ("restore", "还原", "用映射文件恢复文档"),
            ("convert", "月报转 PPT", "暂放后续完善"),
            ("about", "关于", "版本与更新"),
        ]
        for row, (key, title, subtitle) in enumerate(nav_items, start=2):
            self._add_nav_button(sidebar, row, key, title, subtitle)

        self._build_convert_tab(convert_tab)
        self._build_sanitize_tab(sanitize_tab)
        self._build_restore_tab(restore_tab)
        self._build_prompt_tab(prompt_tab)
        self._build_about_tab(about_tab)
        self._show_nav_page("sanitize")

    def _add_nav_button(self, parent: ctk.CTkFrame, row: int, key: str, title: str, subtitle: str) -> None:
        colors = self._palette()
        button = ctk.CTkButton(
            parent,
            text=f"{title}\n{subtitle}",
            anchor="center",
            height=56,
            corner_radius=10,
            fg_color="transparent",
            hover_color=colors["sidebar_hover"],
            text_color="#d8e2ef",
            font=("Microsoft YaHei UI", 12),
            command=lambda selected=key: self._show_nav_page(selected),
        )
        button.grid(row=row, column=0, sticky="ew", padx=14, pady=5)
        self.nav_buttons[key] = button

    def _show_nav_page(self, key: str) -> None:
        colors = self._palette()
        for page_key, page in self.nav_pages.items():
            if page_key == key:
                page.grid()
            else:
                page.grid_remove()
        for button_key, button in self.nav_buttons.items():
            if button_key == key:
                button.configure(fg_color=colors["accent"], text_color="#ffffff")
            else:
                button.configure(fg_color="transparent", text_color="#d8e2ef")
        self.active_nav_key = key

def main() -> int:
    geometry = None
    if "--geometry" in sys.argv:
        idx = sys.argv.index("--geometry")
        if idx + 1 >= len(sys.argv):
            print("missing value for --geometry, expected WxH", file=sys.stderr)
            return 2
        geometry = sys.argv[idx + 1]
        if not re.fullmatch(r"\d+x\d+", geometry):
            print("invalid --geometry format, expected WxH like 1366x768", file=sys.stderr)
            return 2
        del sys.argv[idx : idx + 2]

    if "--run-cli" in sys.argv:
        idx = sys.argv.index("--run-cli")
        forward = [sys.argv[0], *sys.argv[idx + 1 :]]
        import docx_to_ppt_converter

        old_argv = sys.argv
        try:
            sys.argv = forward
            return int(docx_to_ppt_converter.main())
        finally:
            sys.argv = old_argv

    if "--run-sanitize-cli" in sys.argv:
        idx = sys.argv.index("--run-sanitize-cli")
        forward = [sys.argv[0], *sys.argv[idx + 1 :]]
        import sanitize_docx

        old_argv = sys.argv
        try:
            sys.argv = forward
            return int(sanitize_docx.main())
        finally:
            sys.argv = old_argv

    configure_windows_dpi()
    root = ctk.CTk()
    ConverterGUI(root, geometry=geometry)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
