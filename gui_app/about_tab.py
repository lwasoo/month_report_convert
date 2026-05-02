from __future__ import annotations

import threading
import webbrowser
from tkinter import messagebox, ttk

from .defaults import APP_DISPLAY_NAME, APP_VERSION, GITHUB_RELEASES_URL
from .update_checker import UpdateInfo, fetch_latest_release


class AboutTabMixin:
    def _build_about_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        card = ttk.Frame(parent, style="Card.TFrame", padding=24)
        card.grid(row=0, column=0, sticky="nsew")
        card.columnconfigure(0, weight=1)

        ttk.Label(card, text=APP_DISPLAY_NAME, style="HeaderTitle.TLabel").grid(row=0, column=0, sticky="w")
        ttk.Label(card, text=f"当前版本: v{APP_VERSION}", style="Field.TLabel").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Label(card, text="感谢支持合规工作喵~(∠・ω< )⌒★", style="AboutThanks.TLabel").grid(row=2, column=0, sticky="w", pady=(24, 0))
        ttk.Label(
            card,
            text=(
                "本工具面向法务月报、文档脱敏与还原等合规场景。"
                "由于文档格式、图片 OCR、模型识别和人工改写都可能带来遗漏或误判，"
                "工具无法保证 100% 消除数据保密、隐私保护或合规风险。"
                "对外发送或归档前，请务必进行人工复核。"
            ),
            style="RiskNotice.TLabel",
            wraplength=720,
            justify="left",
        ).grid(row=3, column=0, sticky="w", pady=(14, 0))

        self.update_status_var = self._make_string_var("等待检测更新")
        ttk.Label(card, textvariable=self.update_status_var, style="Status.TLabel").grid(row=4, column=0, sticky="w", pady=(24, 0))

        action_row = ttk.Frame(card, style="Card.TFrame")
        action_row.grid(row=5, column=0, sticky="w", pady=(14, 0))
        self.check_update_button = ttk.Button(
            action_row,
            text="检测更新",
            style="Primary.TButton",
            command=lambda: self.check_updates_async(silent=False),
        )
        self.check_update_button.pack(side="left")
        ttk.Button(action_row, text="打开 Release 页面", style="Secondary.TButton", command=lambda: webbrowser.open(GITHUB_RELEASES_URL)).pack(side="left", padx=(10, 0))

        ttk.Label(
            card,
            text="检测到新版本后会打开 GitHub Release 页面下载。当前版本不会直接覆盖正在运行的程序。",
            style="Hint.TLabel",
            wraplength=620,
            justify="left",
        ).grid(row=6, column=0, sticky="w", pady=(18, 0))

    def _make_string_var(self, value: str):
        import tkinter as tk

        return tk.StringVar(value=value)

    def check_updates_async(self, silent: bool = True) -> None:
        if hasattr(self, "check_update_button"):
            self.check_update_button.configure(state="disabled")
        self.update_status_var.set("正在检测更新...")
        threading.Thread(target=self._check_updates_worker, args=(silent,), daemon=True).start()

    def _check_updates_worker(self, silent: bool) -> None:
        try:
            info = fetch_latest_release()
        except Exception as exc:
            self.root.after(0, lambda: self._handle_update_error(exc, silent))
            return
        self.root.after(0, lambda: self._handle_update_result(info, silent))

    def _handle_update_result(self, info: UpdateInfo, silent: bool) -> None:
        if hasattr(self, "check_update_button"):
            self.check_update_button.configure(state="normal")
        if info.is_update_available:
            self.update_status_var.set(f"发现新版本: v{info.latest_version}")
            should_open = messagebox.askyesno(
                "发现新版本",
                f"当前版本: v{info.current_version}\n最新版本: v{info.latest_version}\n\n是否打开下载页面？",
            )
            if should_open:
                webbrowser.open(info.preferred_download_url)
            return
        self.update_status_var.set(f"已是最新版本: v{info.current_version}")
        if not silent:
            messagebox.showinfo("检测更新", f"当前已是最新版本：v{info.current_version}")

    def _handle_update_error(self, exc: Exception, silent: bool) -> None:
        if hasattr(self, "check_update_button"):
            self.check_update_button.configure(state="normal")
        self.update_status_var.set("检测更新失败")
        if not silent:
            messagebox.showerror("检测更新失败", str(exc))
