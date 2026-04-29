from __future__ import annotations

from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from doc_sanitizer import restore_file


class RestoreTabMixin:
    def _build_restore_tab(self, parent: ttk.Frame) -> None:
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

        restore_group = ttk.LabelFrame(left_card, text="还原文档", style="Section.TLabelframe", padding=14)
        restore_group.grid(row=0, column=0, sticky="ew")
        restore_group.columnconfigure(1, weight=1)
        self._add_path_row(restore_group, 0, "AI 修改后 DOCX", self.restore_input_var, self._browse_restore_input)
        self._add_path_row(restore_group, 1, "映射 JSON", self.restore_mapping_var, self._browse_restore_mapping)
        self._add_path_row(restore_group, 2, "还原输出", self.restore_output_var, self._browse_restore_output)
        action_row = ttk.Frame(restore_group, style="Card.TFrame")
        action_row.grid(row=3, column=1, sticky="w", pady=(8, 0))
        ttk.Button(action_row, text="开始还原", style="Primary.TButton", command=self.start_restore).pack(side="left")
        ttk.Label(action_row, textvariable=self.restore_status_var, style="Status.TLabel").pack(side="left", padx=(12, 0))

        ttk.Label(right_card, text="运行日志", style="Field.TLabel").grid(row=0, column=0, sticky="w")
        self.restore_log_text = self._create_log_widget(right_card)
        self.restore_log_text.grid(row=1, column=0, sticky="nsew", pady=(8, 0))

    def _browse_restore_input(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("Supported", "*.docx *.pptx"), ("Word", "*.docx"), ("PowerPoint", "*.pptx")])
        if path:
            self.restore_input_var.set(path)
            if not self.restore_output_var.get():
                suffix = Path(path).suffix.lower()
                self.restore_output_var.set(str(Path(path).with_name(f"{Path(path).stem}_还原{suffix}")))

    def _browse_restore_mapping(self) -> None:
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if path:
            self.restore_mapping_var.set(path)

    def _browse_restore_output(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".docx", filetypes=[("Supported", "*.docx *.pptx"), ("Word", "*.docx"), ("PowerPoint", "*.pptx")])
        if path:
            self.restore_output_var.set(path)

    def _validate_restore_inputs(self) -> bool:
        if not self.restore_input_var.get().strip() or not self.restore_mapping_var.get().strip() or not self.restore_output_var.get().strip():
            messagebox.showwarning("缺少参数", "请填写还原所需的 DOCX / 映射 / 输出路径。")
            return False
        return True

    def start_restore(self) -> None:
        if not self._validate_restore_inputs():
            return
        self._start_worker("restore", self.restore_status_var, "[INFO] 开始还原文档...", self._restore_worker)

    def _restore_worker(self) -> None:
        input_path = Path(self.restore_input_var.get().strip())
        mapping_path = Path(self.restore_mapping_var.get().strip())
        output_path = self._unique_output_path(Path(self.restore_output_var.get().strip()))
        restore_file(input_path=input_path, output_path=output_path, mapping_path=mapping_path)
        self.log_queue.put(("restore", f"[INFO] 还原输入: {input_path}"))
        self.log_queue.put(("restore", f"[INFO] 使用映射: {mapping_path}"))
        self.log_queue.put(("restore", f"[INFO] 还原完成: {output_path}"))
        self.root.after(0, lambda: self._after_restore_complete(output_path))

    def _after_restore_complete(self, output_path: Path) -> None:
        self.restore_output_var.set(str(output_path))
        self.restore_status_var.set("已完成")
