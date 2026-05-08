"""Background restore actions and worker logging."""

from __future__ import annotations

from pathlib import Path
from tkinter import messagebox

from doc_sanitizer import read_mapping, restore_file
from doc_sanitizer.io.text_collection import collect_texts_for_path
from doc_sanitizer.mapping import mapping_entries
from doc_sanitizer.placeholders.repair import unresolved_placeholder_tokens


class RestoreActionsMixin:
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
        originals_by_placeholder = {entry.placeholder: entry.original for entry in payload.entries or []}
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
