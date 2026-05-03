from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from doc_sanitizer import read_mapping, restore_file
from doc_sanitizer.document_io import collect_texts_for_path
from doc_sanitizer.fuzzy_mapping import PlaceholderRepair, closest_placeholder_for_token, placeholder_token_category, suggest_placeholder_repairs, unresolved_placeholder_tokens
from doc_sanitizer.mapping import mapping_entries


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

        restore_group = ttk.LabelFrame(left_card, text="1. 还原文件", style="Section.TLabelframe", padding=14)
        restore_group.grid(row=0, column=0, sticky="ew")
        restore_group.columnconfigure(1, weight=1)
        self._add_path_row(restore_group, 0, "AI 修改后文件", self.restore_input_var, self._browse_restore_input)
        self._add_path_row(restore_group, 1, "映射 JSON", self.restore_mapping_var, self._browse_restore_mapping)
        self._add_path_row(restore_group, 2, "还原输出", self.restore_output_var, self._browse_restore_output)

        action_row = ttk.Frame(restore_group, style="Card.TFrame")
        action_row.grid(row=3, column=1, sticky="w", pady=(8, 0))
        ttk.Button(action_row, text="开始还原", style="Primary.TButton", command=self.start_restore).pack(side="left")
        ttk.Label(action_row, textvariable=self.restore_status_var, style="Status.TLabel").pack(side="left", padx=(12, 0))

        help_group = ttk.LabelFrame(left_card, text="2. 使用说明", style="Section.TLabelframe", padding=14)
        help_group.grid(row=1, column=0, sticky="ew", pady=(14, 0))
        ttk.Label(
            help_group,
            text=(
                "还原会按映射 JSON 中的占位符，把当前文件里仍然保留的占位符替换回原始敏感信息。"
                "如果外部 AI 把占位符改成相似但不完全一致的写法，开始前会弹出确认列表。"
                "如果整段内容已被删除，对应敏感信息不会被重新补回。"
            ),
            style="Hint.TLabel",
            wraplength=420,
            justify="left",
        ).grid(row=0, column=0, sticky="w")

        ttk.Label(right_card, text="运行日志", style="Field.TLabel").grid(row=0, column=0, sticky="w")
        self.restore_log_text = self._create_log_widget(right_card)
        self.restore_log_text.grid(row=1, column=0, sticky="nsew", pady=(8, 0))

    def _browse_restore_input(self) -> None:
        path = filedialog.askopenfilename(
            filetypes=[("支持的文件", "*.doc *.docx *.ppt *.pptx"), ("Word 文档", "*.doc *.docx"), ("PPT 文档", "*.ppt *.pptx")]
        )
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
        path = filedialog.asksaveasfilename(
            defaultextension=".docx",
            filetypes=[("支持的文件", "*.doc *.docx *.ppt *.pptx"), ("Word 文档", "*.doc *.docx"), ("PPT 文档", "*.ppt *.pptx")],
        )
        if path:
            self.restore_output_var.set(path)

    def _validate_restore_inputs(self) -> bool:
        if not self.restore_input_var.get().strip() or not self.restore_mapping_var.get().strip() or not self.restore_output_var.get().strip():
            messagebox.showwarning("缺少参数", "请填写还原所需的文件 / 映射 / 输出路径。")
            return False
        return True

    def start_restore(self) -> None:
        if not self._validate_restore_inputs():
            return
        input_path = Path(self.restore_input_var.get().strip())
        mapping_path = Path(self.restore_mapping_var.get().strip())
        try:
            repair_plan = self._confirm_placeholder_repairs(input_path, mapping_path)
        except Exception as exc:
            messagebox.showerror("占位符检查失败", f"无法检查相似占位符：{exc}")
            return
        if repair_plan is None:
            self.restore_status_var.set("已取消")
            return
        placeholder_repairs, auto_repairs, confirmed_repairs = repair_plan
        manual_repairs = getattr(self, "_last_manual_placeholder_repairs", {})
        params = {
            "input_path": input_path,
            "mapping_path": mapping_path,
            "output_path": self._unique_output_path(Path(self.restore_output_var.get().strip())),
            "placeholder_repairs": placeholder_repairs,
            "auto_repairs": auto_repairs,
            "confirmed_repairs": confirmed_repairs,
            "manual_repairs": manual_repairs,
        }
        self._start_worker("restore", self.restore_status_var, "[INFO] 开始还原文档...", lambda: self._restore_worker(params))

    def _restore_worker(self, params: dict[str, object]) -> None:
        input_path = params["input_path"]
        mapping_path = params["mapping_path"]
        output_path = params["output_path"]
        placeholder_repairs = params["placeholder_repairs"]
        auto_repairs = params["auto_repairs"]
        confirmed_repairs = params["confirmed_repairs"]
        manual_repairs = params["manual_repairs"]
        assert isinstance(input_path, Path)
        assert isinstance(mapping_path, Path)
        assert isinstance(output_path, Path)
        assert isinstance(placeholder_repairs, dict)
        assert isinstance(auto_repairs, dict)
        assert isinstance(confirmed_repairs, dict)
        assert isinstance(manual_repairs, dict)
        restore_file(
            input_path=input_path,
            output_path=output_path,
            mapping_path=mapping_path,
            placeholder_repairs=placeholder_repairs,
        )
        payload = read_mapping(mapping_path)
        originals_by_placeholder = {
            str(entry.get("placeholder", "")): str(entry.get("original", ""))
            for entry in payload.get("entries", [])
            if isinstance(entry, dict)
        }
        self.log_queue.put(("restore", f"[INFO] 还原输入: {input_path}"))
        self.log_queue.put(("restore", f"[INFO] 使用映射: {mapping_path}"))
        for token, canonical in auto_repairs.items():
            original = originals_by_placeholder.get(canonical, "")
            self.log_queue.put(("restore", f"[INFO] 自动修复相似占位符: {token} -> {canonical} -> {original}"))
        for token, canonical in confirmed_repairs.items():
            original = originals_by_placeholder.get(canonical, "")
            self.log_queue.put(("restore", f"[INFO] 已按用户确认修复占位符: {token} -> {canonical} -> {original}"))
        for token, canonical in manual_repairs.items():
            original = originals_by_placeholder.get(canonical, canonical)
            self.log_queue.put(("restore", f"[INFO] 已按用户指定还原未知占位符: {token} -> {canonical} -> {original}"))
        unresolved = self._collect_unresolved_placeholders(output_path, mapping_path, placeholder_repairs)
        if unresolved:
            self.log_queue.put(("restore", f"[WARN] 还原后仍发现 {len(unresolved)} 个未还原占位符，通常是外部 AI 生成了映射表里不存在的新编号。"))
            for token in unresolved[:20]:
                self.log_queue.put(("restore", f"[WARN] 未还原占位符: {token}"))
            if len(unresolved) > 20:
                self.log_queue.put(("restore", f"[WARN] 其余 {len(unresolved) - 20} 个未显示，请检查输出文件。"))
        self.log_queue.put(("restore", f"[INFO] 还原完成: {output_path}"))
        self.root.after(0, lambda: self._after_restore_complete(output_path))

    def _collect_unresolved_placeholders(self, output_path: Path, mapping_path: Path, placeholder_repairs: dict[str, str]) -> list[str]:
        payload = read_mapping(mapping_path)
        items = mapping_entries(payload, only_enabled=False)
        tokens: list[str] = []
        seen: set[str] = set()
        for text in collect_texts_for_path(output_path):
            for token in unresolved_placeholder_tokens(text, items, placeholder_repairs=placeholder_repairs):
                key = token.upper()
                if key in seen:
                    continue
                seen.add(key)
                tokens.append(token)
        return tokens

    def _after_restore_complete(self, output_path: Path) -> None:
        self.restore_output_var.set(str(output_path))
        self.restore_status_var.set("已完成")

    def _confirm_placeholder_repairs(self, input_path: Path, mapping_path: Path) -> tuple[dict[str, str], dict[str, str], dict[str, str]] | None:
        payload = read_mapping(mapping_path)
        items = mapping_entries(payload, only_enabled=False)
        repairs_by_pair: dict[tuple[str, str], PlaceholderRepair] = {}
        unresolved_tokens: list[str] = []
        unresolved_seen: set[str] = set()
        texts = collect_texts_for_path(input_path)
        for text in texts:
            for repair in suggest_placeholder_repairs(text, items, min_score=0.70):
                key = (repair.token, repair.canonical)
                current = repairs_by_pair.get(key)
                if current is None or repair.score > current.score:
                    repairs_by_pair[key] = repair
            for token in unresolved_placeholder_tokens(text, items):
                key = token.upper()
                if key in unresolved_seen:
                    continue
                unresolved_seen.add(key)
                unresolved_tokens.append(token)
        repairs = sorted(repairs_by_pair.values(), key=lambda item: (item.canonical, item.token))
        self._last_manual_placeholder_repairs = {}
        if not repairs and not unresolved_tokens:
            return {}, {}, {}
        auto_repairs = {repair.token: repair.canonical for repair in repairs if repair.score >= 0.90}
        needs_confirmation = [repair for repair in repairs if repair.score < 0.90]
        confirmed_repairs: dict[str, str] = {}
        if needs_confirmation:
            selected_repairs = self._show_placeholder_repair_dialog(needs_confirmation, payload)
            if selected_repairs is None:
                return None
            confirmed_repairs = selected_repairs
        covered_tokens = {repair.token.upper() for repair in repairs}
        manual_tokens = [token for token in unresolved_tokens if token.upper() not in covered_tokens]
        manual_repairs: dict[str, str] = {}
        if manual_tokens:
            selected_manual_repairs = self._show_unknown_placeholder_dialog(manual_tokens, payload, items)
            if selected_manual_repairs is None:
                return None
            manual_repairs = selected_manual_repairs
            self._last_manual_placeholder_repairs = manual_repairs
        all_repairs = {**auto_repairs, **confirmed_repairs, **manual_repairs}
        return all_repairs, auto_repairs, confirmed_repairs

    def _show_unknown_placeholder_dialog(self, tokens: list[str], payload: dict[str, object], items) -> dict[str, str] | None:
        labels_by_category, placeholder_by_label = self._placeholder_choice_labels(payload)
        rows: list[tuple[str, str, str, str]] = []
        for token in tokens:
            closest_placeholder, score = closest_placeholder_for_token(token, items, min_score=0.65)
            rows.append(
                (
                    token,
                    placeholder_token_category(token),
                    closest_placeholder,
                    f"{score:.2f}" if closest_placeholder else "",
                )
            )
        dialog = self._build_placeholder_choice_dialog(
            title="指定未知占位符",
            intro="发现映射表里不存在的占位符。请选择对应映射项，或直接输入要还原的原词；留空的项目会保留在文件中，并在日志里提示。",
            rows=rows,
            labels_by_category=labels_by_category,
            placeholder_by_label=placeholder_by_label,
        )
        return dialog

    def _show_placeholder_repair_dialog(self, repairs: list[PlaceholderRepair], payload: dict[str, object]) -> dict[str, str] | None:
        labels_by_category, placeholder_by_label = self._placeholder_choice_labels(payload)
        rows: list[tuple[str, str, str, str]] = []
        for repair in repairs:
            category = placeholder_token_category(repair.canonical) or placeholder_token_category(repair.token)
            rows.append((repair.token, category, repair.canonical, f"{repair.score:.2f}"))
        return self._build_placeholder_choice_dialog(
            title="确认相似占位符",
            intro="发现可能被外部 AI 改坏的占位符。系统已给出建议，你可以改选映射项，也可以直接输入要还原的原词；留空则不还原。",
            rows=rows,
            labels_by_category=labels_by_category,
            placeholder_by_label=placeholder_by_label,
        )

    def _placeholder_choice_labels(self, payload: dict[str, object]) -> tuple[dict[str, list[str]], dict[str, str]]:
        entries = [
            entry
            for entry in payload.get("entries", [])
            if isinstance(entry, dict) and str(entry.get("placeholder", "")).strip() and str(entry.get("original", "")).strip()
        ]
        labels_by_category: dict[str, list[str]] = {}
        placeholder_by_label: dict[str, str] = {}
        for entry in entries:
            placeholder = str(entry.get("placeholder", "")).strip()
            original = str(entry.get("original", "")).strip()
            category = str(entry.get("category", "")).strip().upper() or placeholder.strip("_").split("_", 1)[0].upper()
            label = f"{placeholder} -> {original}"
            labels_by_category.setdefault(category, []).append(label)
            placeholder_by_label[label] = placeholder
        for category in labels_by_category:
            labels_by_category[category].sort()
        return labels_by_category, placeholder_by_label

    def _build_placeholder_choice_dialog(
        self,
        title: str,
        intro: str,
        rows: list[tuple[str, str, str, str]],
        labels_by_category: dict[str, list[str]],
        placeholder_by_label: dict[str, str],
    ) -> dict[str, str] | None:
        dialog = tk.Toplevel(self.root)
        dialog.title(title)
        dialog.geometry("980x460")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(1, weight=1)

        ttk.Label(
            dialog,
            text=intro,
            style="Field.TLabel",
            wraplength=920,
            justify="left",
        ).grid(row=0, column=0, sticky="ew", padx=14, pady=(14, 8))

        body = ttk.Frame(dialog, padding=(14, 0, 14, 0))
        body.grid(row=1, column=0, sticky="nsew")
        body.columnconfigure(2, weight=1)
        ttk.Label(body, text="文件中出现", style="Field.TLabel").grid(row=0, column=0, sticky="w", pady=(0, 6))
        ttk.Label(body, text="置信度", style="Field.TLabel").grid(row=0, column=1, sticky="w", pady=(0, 6), padx=(12, 0))
        ttk.Label(body, text="选择对应映射", style="Field.TLabel").grid(row=0, column=2, sticky="w", pady=(0, 6), padx=(12, 0))

        choices: dict[str, tk.StringVar] = {}
        all_labels = [label for values in labels_by_category.values() for label in values]
        label_by_placeholder = {placeholder: label for label, placeholder in placeholder_by_label.items()}
        for row, (token, category, default_placeholder, score) in enumerate(rows, start=1):
            labels = labels_by_category.get(category, [])
            if not labels:
                labels = all_labels
            values = ["", *labels]
            default_label = label_by_placeholder.get(default_placeholder, "")
            var = tk.StringVar(value=default_label)
            choices[token] = var
            ttk.Label(body, text=token, style="Mono.TLabel").grid(row=row, column=0, sticky="w", pady=4)
            ttk.Label(body, text=score or "-", style="Field.TLabel").grid(row=row, column=1, sticky="w", pady=4, padx=(12, 0))
            combo = ttk.Combobox(body, textvariable=var, values=values)
            combo.grid(row=row, column=2, sticky="ew", pady=4, padx=(12, 0))

        result: dict[str, str] | None = None

        def confirm() -> None:
            nonlocal result
            result = {}
            for token, var in choices.items():
                selected = var.get().strip()
                if not selected:
                    continue
                result[token] = placeholder_by_label.get(selected, selected)
            dialog.destroy()

        def cancel() -> None:
            nonlocal result
            result = None
            dialog.destroy()

        action_row = ttk.Frame(dialog, padding=14)
        action_row.grid(row=2, column=0, sticky="ew")
        ttk.Button(action_row, text="取消", style="Secondary.TButton", command=cancel).pack(side="right", padx=(0, 8))
        ttk.Button(action_row, text="确认并还原", style="Primary.TButton", command=confirm).pack(side="right")

        dialog.protocol("WM_DELETE_WINDOW", cancel)
        self.root.wait_window(dialog)
        return result
