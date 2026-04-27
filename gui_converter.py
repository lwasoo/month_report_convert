#!/usr/bin/env python3
"""Tkinter GUI for DOCX -> PPT converter."""

from __future__ import annotations

import json
import locale
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
import urllib.error
import urllib.request
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


DEFAULT_MODEL = "qwen2.5:7b-instruct-q4_K_M"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434"


class ConverterGUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Word 月报转 PPT")
        self.root.geometry("980x700")

        self.log_queue: queue.Queue[str] = queue.Queue()
        self.process: subprocess.Popen[str] | None = None

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
        self.diversity_var = tk.StringVar(value="medium")
        self.seed_var = tk.StringVar(value="0")

        self._build_ui()
        self._pump_logs()
        self.root.after(300, self.detect_models_async)

    def _build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=12)
        frame.pack(fill=tk.BOTH, expand=True)

        frame.columnconfigure(1, weight=1)

        row = 0
        self._add_path_row(frame, row, "Word 路径", self.docx_var, self._browse_docx)
        row += 1
        self._add_path_row(frame, row, "模板路径", self.template_var, self._browse_template)
        row += 1
        self._add_path_row(frame, row, "输出路径", self.output_var, self._browse_output)
        row += 1

        ttk.Label(frame, text="Ollama 地址").grid(row=row, column=0, sticky="w", pady=6)
        ttk.Entry(frame, textvariable=self.ollama_url_var).grid(row=row, column=1, sticky="ew", pady=6)
        row += 1

        ttk.Label(frame, text="模型").grid(row=row, column=0, sticky="w", pady=6)
        model_row = ttk.Frame(frame)
        model_row.grid(row=row, column=1, sticky="ew", pady=6)
        model_row.columnconfigure(0, weight=1)
        self.model_combo = ttk.Combobox(model_row, textvariable=self.model_var)
        self.model_combo.grid(row=0, column=0, sticky="ew")
        ttk.Button(model_row, text="检测模型", command=self.detect_models).grid(row=0, column=1, padx=(8, 0))
        row += 1

        adv_row = ttk.Frame(frame)
        adv_row.grid(row=row, column=1, sticky="w", pady=6)
        ttk.Label(adv_row, text="timeout").pack(side=tk.LEFT)
        ttk.Entry(adv_row, textvariable=self.timeout_var, width=8).pack(side=tk.LEFT, padx=(6, 16))
        ttk.Label(adv_row, text="retries").pack(side=tk.LEFT)
        ttk.Entry(adv_row, textvariable=self.retries_var, width=8).pack(side=tk.LEFT, padx=(6, 16))
        ttk.Checkbutton(adv_row, text="只用规则模式（不调用模型）", variable=self.no_llm_var).pack(side=tk.LEFT)
        row += 1

        layout_row = ttk.Frame(frame)
        layout_row.grid(row=row, column=1, sticky="w", pady=6)
        ttk.Label(layout_row, text="排版模式").pack(side=tk.LEFT)
        self.layout_combo = ttk.Combobox(
            layout_row,
            textvariable=self.layout_mode_var,
            values=["formal", "classic"],
            width=12,
            state="readonly",
        )
        self.layout_combo.pack(side=tk.LEFT, padx=(8, 0))
        row += 1

        style_row = ttk.Frame(frame)
        style_row.grid(row=row, column=1, sticky="w", pady=6)
        ttk.Label(style_row, text="主题").pack(side=tk.LEFT)
        ttk.Combobox(
            style_row,
            textvariable=self.theme_var,
            values=["formal_blue", "corporate_gray", "legal_red"],
            width=16,
            state="readonly",
        ).pack(side=tk.LEFT, padx=(8, 16))
        ttk.Label(style_row, text="多样化").pack(side=tk.LEFT)
        ttk.Combobox(
            style_row,
            textvariable=self.diversity_var,
            values=["low", "medium", "high"],
            width=10,
            state="readonly",
        ).pack(side=tk.LEFT, padx=(8, 16))
        ttk.Label(style_row, text="seed").pack(side=tk.LEFT)
        ttk.Entry(style_row, textvariable=self.seed_var, width=8).pack(side=tk.LEFT, padx=(8, 0))
        row += 1

        button_row = ttk.Frame(frame)
        button_row.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(10, 8))
        ttk.Button(button_row, text="开始转换", command=self.start_convert).pack(side=tk.LEFT)
        ttk.Button(button_row, text="停止", command=self.stop_convert).pack(side=tk.LEFT, padx=8)
        row += 1

        ttk.Label(frame, text="运行日志").grid(row=row, column=0, sticky="w", pady=(8, 4))
        row += 1

        self.log_text = tk.Text(frame, height=22, wrap=tk.WORD)
        self.log_text.grid(row=row, column=0, columnspan=2, sticky="nsew")
        frame.rowconfigure(row, weight=1)

    def _add_path_row(self, frame: ttk.Frame, row: int, label: str, var: tk.StringVar, browse_cmd) -> None:
        ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=6)
        row_frame = ttk.Frame(frame)
        row_frame.grid(row=row, column=1, sticky="ew", pady=6)
        row_frame.columnconfigure(0, weight=1)
        ttk.Entry(row_frame, textvariable=var).grid(row=0, column=0, sticky="ew")
        ttk.Button(row_frame, text="浏览", command=browse_cmd).grid(row=0, column=1, padx=(8, 0))

    def _browse_docx(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Word", "*.docx")])
        if path:
            self.docx_var.set(path)
            if not self.output_var.get():
                stem = Path(path).stem
                self.output_var.set(str(Path(path).with_name(f"{stem}_自动填充.pptx")))

    def _browse_template(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("PowerPoint", "*.pptx")])
        if path:
            self.template_var.set(path)

    def _browse_output(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".pptx",
            filetypes=[("PowerPoint", "*.pptx")],
        )
        if path:
            self.output_var.set(path)

    def append_log(self, msg: str) -> None:
        self.log_text.insert(tk.END, msg + "\n")
        self.log_text.see(tk.END)

    def _pump_logs(self) -> None:
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.append_log(msg)
        except queue.Empty:
            pass
        self.root.after(100, self._pump_logs)

    def detect_models(self) -> None:
        self.detect_models_async(silent=False)

    def detect_models_async(self, silent: bool = True) -> None:
        thread = threading.Thread(target=self._detect_models_worker, args=(silent,), daemon=True)
        thread.start()

    def _detect_models_worker(self, silent: bool) -> None:
        url = self.ollama_url_var.get().strip().rstrip("/") + "/api/tags"
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
                self.log_queue.put(f"[WARN] HTTP 检测失败，已回退到 `ollama list`: {exc}")
            else:
                self.root.after(0, lambda: self._handle_model_detect_error(exc, silent))

    def _detect_models_from_cli(self) -> list[str]:
        try:
            completed = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=8,
                check=False,
            )
            if completed.returncode != 0:
                return []
            lines = [ln.strip() for ln in completed.stdout.splitlines() if ln.strip()]
            if not lines:
                return []
            models: list[str] = []
            for line in lines[1:]:
                parts = line.split()
                if parts:
                    models.append(parts[0])
            return models
        except Exception:
            return []

    def _apply_models(self, models: list[str], silent: bool) -> None:
        if not models:
            if not silent:
                messagebox.showinfo("检测结果", "未检测到模型。")
            self.append_log("[WARN] 未检测到可用模型")
            return
        self.model_combo["values"] = models
        if self.model_var.get() not in models:
            self.model_var.set(models[0])
        self.append_log(f"[INFO] 检测到模型: {', '.join(models)}")

    def _handle_model_detect_error(self, exc: Exception, silent: bool) -> None:
        self.append_log(f"[WARN] 模型检测失败: {exc}")
        if not silent:
            messagebox.showerror("检测失败", f"无法检测模型：{exc}")

    def _validate_inputs(self) -> bool:
        if not self.docx_var.get().strip():
            messagebox.showwarning("缺少参数", "请先选择 Word 文件。")
            return False
        if not self.template_var.get().strip():
            messagebox.showwarning("缺少参数", "请先选择 PPT 模板。")
            return False
        if not self.output_var.get().strip():
            messagebox.showwarning("缺少参数", "请先填写输出路径。")
            return False
        try:
            int(self.seed_var.get().strip() or "0")
        except ValueError:
            messagebox.showwarning("参数错误", "seed 必须是整数。")
            return False
        return True

    def start_convert(self) -> None:
        if self.process and self.process.poll() is None:
            messagebox.showinfo("正在运行", "当前已有任务在运行。")
            return
        if not self._validate_inputs():
            return

        args = [
            "--docx",
            self.docx_var.get().strip(),
            "--template",
            self.template_var.get().strip(),
            "--output",
            self.output_var.get().strip(),
            "--model",
            self.model_var.get().strip() or DEFAULT_MODEL,
            "--ollama-url",
            self.ollama_url_var.get().strip() or DEFAULT_OLLAMA_URL,
            "--timeout",
            self.timeout_var.get().strip() or "180",
            "--retries",
            self.retries_var.get().strip() or "2",
            "--layout-mode",
            self.layout_mode_var.get().strip() or "formal",
            "--theme",
            self.theme_var.get().strip() or "formal_blue",
            "--diversity",
            self.diversity_var.get().strip() or "medium",
            "--seed",
            self.seed_var.get().strip() or "0",
        ]
        if self.no_llm_var.get():
            args.append("--no-llm")

        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--run-cli", *args]
        else:
            cli_script = self._resolve_cli_script()
            if not cli_script:
                messagebox.showerror("启动失败", "未找到转换脚本 docx_to_ppt_converter.py。")
                return
            cmd = [sys.executable, "-u", str(cli_script), *args]

        self.append_log("[INFO] 开始转换...")
        self.append_log("[CMD] " + " ".join(f'"{x}"' if " " in x else x for x in cmd))

        thread = threading.Thread(target=self._run_process, args=(cmd,), daemon=True)
        thread.start()

    def _resolve_cli_script(self) -> Path | None:
        local = Path(__file__).with_name("docx_to_ppt_converter.py")
        if local.exists():
            return local
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            bundled = Path(meipass) / "docx_to_ppt_converter.py"
            if bundled.exists():
                return bundled
        return None

    def _run_process(self, cmd: list[str]) -> None:
        try:
            child_env = os.environ.copy()
            child_env["PYTHONIOENCODING"] = "utf-8"
            child_env["PYTHONUTF8"] = "1"
            child_env["PYTHONUNBUFFERED"] = "1"
            self.process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=False,
                env=child_env,
                bufsize=0,
            )
            assert self.process.stdout is not None
            while True:
                raw = self.process.stdout.readline()
                if not raw:
                    if self.process.poll() is not None:
                        break
                    continue
                line = self._decode_output_line(raw)
                self.log_queue.put(line.rstrip("\r\n"))
            code = self.process.wait()
            if code == 0:
                self.log_queue.put("[INFO] 转换完成。")
            else:
                self.log_queue.put(f"[ERROR] 转换失败，退出码={code}")
        except Exception as exc:
            self.log_queue.put(f"[ERROR] 启动失败: {exc}")
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

    def stop_convert(self) -> None:
        if self.process and self.process.poll() is None:
            self.process.terminate()
            self.append_log("[INFO] 已请求停止任务。")
        else:
            self.append_log("[INFO] 当前无运行中的任务。")


def main() -> int:
    # For packaged EXE: allow background worker mode instead of opening another GUI window.
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

    root = tk.Tk()
    app = ConverterGUI(root)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
