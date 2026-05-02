from __future__ import annotations

import sys
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .defaults import DEFAULT_MODEL, DEFAULT_OLLAMA_URL


class ConvertTabMixin:
    def _build_convert_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        main = ttk.PanedWindow(parent, orient="horizontal")
        main.grid(row=0, column=0, sticky="nsew")

        left_card = ttk.Frame(main, style="Card.TFrame", padding=18)
        right_card = ttk.Frame(main, style="Card.TFrame", padding=18)
        main.add(left_card, weight=5)
        main.add(right_card, weight=4)

        left_card.columnconfigure(0, weight=1)
        right_card.columnconfigure(0, weight=1)
        right_card.rowconfigure(1, weight=1)

        io_group = ttk.LabelFrame(left_card, text="1. 输入与输出", style="Section.TLabelframe", padding=14)
        io_group.grid(row=0, column=0, sticky="ew")
        io_group.columnconfigure(1, weight=1)
        self._add_path_row(io_group, 0, "Word 月报", self.docx_var, self._browse_docx)
        self._add_path_row(io_group, 1, "PPT 模板", self.template_var, self._browse_template)
        self._add_path_row(io_group, 2, "输出文件", self.output_var, self._browse_output)

        model_group = ttk.LabelFrame(left_card, text="2. 模型与运行参数", style="Section.TLabelframe", padding=14)
        model_group.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        model_group.columnconfigure(1, weight=1)
        ttk.Label(model_group, text="Ollama 地址", style="Field.TLabel").grid(row=0, column=0, sticky="w", pady=6)
        ttk.Entry(model_group, textvariable=self.ollama_url_var).grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Label(model_group, text="模型", style="Field.TLabel").grid(row=1, column=0, sticky="w", pady=6)

        model_row = ttk.Frame(model_group, style="Card.TFrame")
        model_row.grid(row=1, column=1, sticky="ew", pady=6)
        model_row.columnconfigure(0, weight=1)
        self.model_combo = ttk.Combobox(model_row, textvariable=self.model_var)
        self.model_combo.grid(row=0, column=0, sticky="ew")
        ttk.Button(model_row, text="检测模型", style="Secondary.TButton", command=self.detect_models).grid(row=0, column=1, padx=(8, 0))

        adv_row = ttk.Frame(model_group, style="Card.TFrame")
        adv_row.grid(row=2, column=1, sticky="w", pady=6)
        ttk.Label(adv_row, text="超时", style="Field.TLabel").pack(side="left")
        ttk.Entry(adv_row, textvariable=self.timeout_var, width=8).pack(side="left", padx=(6, 16))
        ttk.Label(adv_row, text="重试", style="Field.TLabel").pack(side="left")
        ttk.Entry(adv_row, textvariable=self.retries_var, width=8).pack(side="left", padx=(6, 16))
        ttk.Checkbutton(adv_row, text="只用规则模式（不调用模型）", variable=self.no_llm_var).pack(side="left")

        layout_group = ttk.LabelFrame(left_card, text="3. 排版策略", style="Section.TLabelframe", padding=14)
        layout_group.grid(row=2, column=0, sticky="ew", pady=(14, 0))
        layout_group.columnconfigure(1, weight=1)
        ttk.Label(layout_group, text="排版模式", style="Field.TLabel").grid(row=0, column=0, sticky="w", pady=6)
        ttk.Combobox(layout_group, textvariable=self.layout_mode_var, values=["formal", "classic"], width=12, state="readonly").grid(row=0, column=1, sticky="w", pady=6)
        ttk.Label(layout_group, text="主题", style="Field.TLabel").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Combobox(layout_group, textvariable=self.theme_var, values=["formal_blue", "corporate_gray", "legal_red"], width=16, state="readonly").grid(row=1, column=1, sticky="w", pady=6)

        style_row = ttk.Frame(layout_group, style="Card.TFrame")
        style_row.grid(row=2, column=1, sticky="w", pady=6)
        ttk.Label(style_row, text="多样化", style="Field.TLabel").pack(side="left")
        ttk.Combobox(style_row, textvariable=self.diversity_var, values=["none", "low", "medium", "high"], width=10, state="readonly").pack(side="left", padx=(8, 18))
        ttk.Label(style_row, text="Seed", style="Field.TLabel").pack(side="left")
        ttk.Entry(style_row, textvariable=self.seed_var, width=8).pack(side="left", padx=(8, 0))
        ttk.Label(
            layout_group,
            text="formal 适合正式汇报；diversity=none 时不套用多样化版式。",
            style="Hint.TLabel",
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(8, 0))

        action_row = ttk.Frame(left_card, style="Card.TFrame")
        action_row.grid(row=3, column=0, sticky="ew", pady=(16, 0))
        ttk.Button(action_row, text="开始转换", style="Primary.TButton", command=self.start_convert).pack(side="left")
        ttk.Button(action_row, text="停止任务", style="Secondary.TButton", command=self.stop_task).pack(side="left", padx=10)
        ttk.Label(action_row, textvariable=self.status_var, style="Status.TLabel").pack(side="right")

        ttk.Label(right_card, text="运行日志", style="Field.TLabel").grid(row=0, column=0, sticky="w")
        self.log_text = self._create_log_widget(right_card)
        self.log_text.grid(row=1, column=0, sticky="nsew", pady=(8, 0))

    def _browse_docx(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Word 文档", "*.doc *.docx"), ("Word 旧格式", "*.doc"), ("Word 新格式", "*.docx")])
        if path:
            self.docx_var.set(path)
            if not self.output_var.get():
                self.output_var.set(str(Path(path).with_name(f"{Path(path).stem}_自动填充.pptx")))

    def _browse_template(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("PPT 模板", "*.ppt *.pptx"), ("PPT 旧格式", "*.ppt"), ("PPT 新格式", "*.pptx")])
        if path:
            self.template_var.set(path)

    def _browse_output(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".pptx", filetypes=[("PPT 文件", "*.ppt *.pptx"), ("PPT 旧格式", "*.ppt"), ("PPT 新格式", "*.pptx")])
        if path:
            self.output_var.set(path)

    def _validate_convert_inputs(self) -> bool:
        if not self.docx_var.get().strip():
            messagebox.showwarning("缺少参数", "请先选择 Word 月报文件。")
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
            messagebox.showwarning("参数错误", "Seed 必须是整数。")
            return False
        return True

    def start_convert(self) -> None:
        if self.process and self.process.poll() is None:
            messagebox.showinfo("正在运行", "当前已有任务在运行。")
            return
        if not self._validate_convert_inputs():
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
            self.diversity_var.get().strip() or "none",
            "--seed",
            self.seed_var.get().strip() or "0",
        ]
        if self.no_llm_var.get():
            args.append("--no-llm")

        if getattr(sys, "frozen", False):
            cmd = [sys.executable, "--run-cli", *args]
        else:
            cli_script = self._resolve_script("docx_to_ppt_converter.py")
            if not cli_script:
                messagebox.showerror("启动失败", "未找到 docx_to_ppt_converter.py。")
                return
            cmd = [sys.executable, "-u", str(cli_script), *args]
        self._start_subprocess(cmd, target="convert", status_var=self.status_var, start_msg="[INFO] 开始转换...")
