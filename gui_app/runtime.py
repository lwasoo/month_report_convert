"""Runtime helpers for GUI logging, background work, and model detection."""

from __future__ import annotations

import json
import locale
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import traceback
import urllib.error
import urllib.request
import webbrowser
from collections.abc import Callable
from pathlib import Path
from tkinter import messagebox
from tkinter.scrolledtext import ScrolledText

from office_conversion import LIBREOFFICE_DOWNLOAD_URL, OfficeConversionError
from report_converter.common import route_logs_to


class RuntimeMixin:
    def _get_log_widget(self, target: str) -> ScrolledText:
        if target == "sanitize":
            return self.mask_log_text
        if target == "restore":
            return self.restore_log_text
        return self.log_text

    def append_log(self, msg: str, target: str) -> None:
        widget = self._get_log_widget(target)
        tag = self._log_tag_for_message(msg)
        widget.configure(state=tk.NORMAL)
        widget.insert(tk.END, msg + "\n", tag)
        widget.see(tk.END)
        widget.configure(state=tk.DISABLED)

    @staticmethod
    def _log_tag_for_message(msg: str) -> str:
        upper = msg.upper()
        if "外部 AI 使用提醒" in msg:
            return "NOTICE"
        if "[ERROR]" in upper:
            return "ERROR"
        if "[WARN]" in upper:
            return "WARN"
        return "INFO"

    def _pump_logs(self) -> None:
        """Move worker-thread log messages onto Tk's main thread."""
        try:
            while True:
                target, msg = self.log_queue.get_nowait()
                self.append_log(msg, target)
        except queue.Empty:
            pass
        self.root.after(100, self._pump_logs)

    def detect_models(self) -> None:
        self.detect_models_async(silent=False)

    def detect_models_async(self, silent: bool = True) -> None:
        url = self.ollama_url_var.get().strip().rstrip("/") + "/api/tags"
        threading.Thread(target=self._detect_models_worker, args=(silent, url), daemon=True).start()

    def _detect_models_worker(self, silent: bool, url: str) -> None:
        try:
            req = urllib.request.Request(url=url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            models = [m.get("name", "") for m in payload.get("models", []) if m.get("name")]
            self.root.after(0, lambda: self._apply_models(models, silent))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            models = self._detect_models_from_cli()
            if models:
                self.root.after(0, lambda: self._apply_models(models, silent))
                self.log_queue.put(("convert", f"[WARN] HTTP 检测失败，已回退到 ollama list: {exc}"))
            else:
                self.root.after(0, lambda: self._handle_model_detect_error(exc, silent))

    def _detect_models_from_cli(self) -> list[str]:
        try:
            completed = subprocess.run(["ollama", "list"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=8, check=False)
            if completed.returncode != 0:
                return []
            lines = [line.strip() for line in completed.stdout.splitlines() if line.strip()]
            return [line.split()[0] for line in lines[1:] if line.split()]
        except Exception:
            return []

    def _apply_models(self, models: list[str], silent: bool) -> None:
        if not models:
            if not silent:
                messagebox.showinfo("检测结果", "未检测到模型。")
            self.log_queue.put(("convert", "[WARN] 未检测到可用模型"))
            return
        self.model_combo["values"] = models
        self.sanitize_model_combo["values"] = models
        if self.model_var.get() not in models:
            self.model_var.set(models[0])
        self.log_queue.put(("convert", f"[INFO] 检测到模型: {', '.join(models)}"))
        self.log_queue.put(("sanitize", f"[INFO] 检测到模型: {', '.join(models)}"))

    def _handle_model_detect_error(self, exc: Exception, silent: bool) -> None:
        self.log_queue.put(("convert", f"[WARN] 模型检测失败: {exc}"))
        self.log_queue.put(("sanitize", f"[WARN] 模型检测失败: {exc}"))
        if not silent:
            messagebox.showerror("检测失败", f"无法检测模型：{exc}")

    def _start_worker(self, target: str, status_var: tk.StringVar, start_msg: str, func: Callable[[], None]) -> None:
        """Run an in-process task once, routing shared converter logs to the selected tab."""
        if self.worker_running or (self.process and self.process.poll() is None):
            messagebox.showinfo("正在运行", "当前已有任务在运行。")
            return
        self.worker_running = True
        status_var.set("运行中")
        self.log_queue.put((target, start_msg))

        def runner() -> None:
            try:
                with route_logs_to(lambda _message, _level, formatted: self.log_queue.put((target, formatted))):
                    func()
            except OfficeConversionError as exc:
                self.root.after(0, status_var.set, "运行失败")
                self.root.after(0, self._show_office_conversion_error, exc)
                self.log_queue.put((target, f"[ERROR] {exc}"))
            except Exception as exc:
                self.root.after(0, status_var.set, "运行失败")
                message = str(exc) or repr(exc)
                self.log_queue.put((target, f"[ERROR] {message}"))
                self.log_queue.put((target, traceback.format_exc().rstrip()))
            finally:
                self.root.after(0, self._mark_worker_idle)

        threading.Thread(target=runner, daemon=True).start()

    def _mark_worker_idle(self) -> None:
        self.worker_running = False

    def _show_office_conversion_error(self, exc: OfficeConversionError) -> None:
        open_page = messagebox.askyesno(
            "需要安装 LibreOffice",
            f"{exc}\n\n是否打开 LibreOffice 下载页面？",
        )
        if open_page:
            webbrowser.open(LIBREOFFICE_DOWNLOAD_URL)

    def _open_path_in_file_manager(self, path: Path) -> None:
        if sys.platform == "win32":
            subprocess.Popen(["explorer", "/select,", str(path)])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", "-R", str(path)])
        else:
            webbrowser.open(str(path.parent))

    def _resolve_script(self, script_name: str) -> Path | None:
        local = Path(__file__).resolve().parent.parent / script_name
        if local.exists():
            return local
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            bundled = Path(meipass) / script_name
            if bundled.exists():
                return bundled
        return None

    @staticmethod
    def _unique_output_path(path: Path) -> Path:
        if not path.exists():
            return path
        stem = path.stem
        suffix = path.suffix
        parent = path.parent
        index = 2
        while True:
            candidate = parent / f"{stem}_{index}{suffix}"
            if not candidate.exists():
                return candidate
            index += 1

    def _start_subprocess(self, cmd: list[str], target: str, status_var: tk.StringVar, start_msg: str, on_success: Callable[[], None] | None = None) -> None:
        """Start a CLI conversion task and stream child output into the GUI log."""
        status_var.set("运行中")
        self.log_queue.put((target, start_msg))
        self.log_queue.put((target, "[CMD] " + " ".join(f'"{x}"' if " " in x else x for x in cmd)))
        threading.Thread(target=self._run_process, args=(cmd, target, status_var, on_success), daemon=True).start()

    def _run_process(self, cmd: list[str], target: str, status_var: tk.StringVar, on_success: Callable[[], None] | None) -> None:
        try:
            child_env = os.environ.copy()
            child_env["PYTHONIOENCODING"] = "utf-8"
            child_env["PYTHONUTF8"] = "1"
            child_env["PYTHONUNBUFFERED"] = "1"
            self.process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=False, env=child_env, bufsize=0)
            assert self.process.stdout is not None
            while True:
                raw = self.process.stdout.readline()
                if not raw:
                    if self.process.poll() is not None:
                        break
                    continue
                self.log_queue.put((target, self._decode_output_line(raw).rstrip("\r\n")))
            code = self.process.wait()
            if code == 0:
                self.root.after(0, status_var.set, "已完成")
                self.log_queue.put((target, "[INFO] 任务完成。"))
                if on_success:
                    self.root.after(0, on_success)
            else:
                self.root.after(0, status_var.set, "运行失败")
                self.log_queue.put((target, f"[ERROR] 任务失败，退出码={code}"))
        except Exception as exc:
            self.root.after(0, status_var.set, "启动失败")
            self.log_queue.put((target, f"[ERROR] 启动失败: {exc}"))
        finally:
            self.process = None

    @staticmethod
    def _decode_output_line(raw: bytes) -> str:
        for enc in ("utf-8", locale.getpreferredencoding(False), "gbk", "cp936"):
            try:
                return raw.decode(enc)
            except Exception:
                continue
        return raw.decode("utf-8", errors="replace")

    def stop_task(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            convert_tab = getattr(self, "convert_tab_controller", None)
            if convert_tab is not None:
                convert_tab.status_var.set("已停止")
            self.log_queue.put(("convert", "[INFO] 已请求停止任务。"))
            return
        self.log_queue.put(("convert", "[INFO] 当前无可终止的子进程任务。"))
