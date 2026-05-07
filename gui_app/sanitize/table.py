"""Mapping table editing and metadata helpers for the sanitize tab."""

from __future__ import annotations

import copy
import tkinter as tk
from tkinter import messagebox

from .mapping_service import SanitizeMappingService


class SanitizeTableMixin:
    def _mapping_entries(self) -> list[dict[str, object]]:
        return SanitizeMappingService.entries(self.current_mapping_data)

    def _mapping_summary_text(self) -> str:
        return SanitizeMappingService.summary_text(self._mapping_entries())

    def _refresh_mapping_tree(self) -> None:
        self._close_tree_editor()
        self.mapping_tree.delete(*self.mapping_tree.get_children())
        search = self.mapping_search_var.get().strip().lower()
        for idx, entry in enumerate(self._mapping_entries()):
            haystack = " ".join(
                [
                    str(entry.get("category", "")),
                    str(entry.get("original", "")),
                    str(entry.get("placeholder", "")),
                    str(entry.get("source", "")),
                ]
            ).lower()
            if search and search not in haystack:
                continue
            self.mapping_tree.insert(
                "",
                "end",
                iid=str(idx),
                values=(
                    "是" if bool(entry.get("enabled", True)) else "否",
                    str(entry.get("category", "")),
                    str(entry.get("original", "")),
                    str(entry.get("placeholder", "")),
                    str(entry.get("source", "")),
                ),
            )

    def clear_mapping_search(self) -> None:
        self._cancel_mapping_search_refresh()
        self.mapping_search_var.set("")
        self._refresh_mapping_tree()

    def _schedule_mapping_search_refresh(self, event=None):
        self._cancel_mapping_search_refresh()
        self.mapping_search_after_id = self.root.after(300, self._run_mapping_search_refresh)
        return None

    def _cancel_mapping_search_refresh(self) -> None:
        after_id = getattr(self, "mapping_search_after_id", None)
        if not after_id:
            return
        try:
            self.root.after_cancel(after_id)
        except Exception:
            pass
        self.mapping_search_after_id = None

    def _run_mapping_search_refresh(self) -> None:
        self.mapping_search_after_id = None
        self._refresh_mapping_tree()

    def _begin_tree_edit(self, event) -> None:
        item = self.mapping_tree.identify_row(event.y)
        column = self.mapping_tree.identify_column(event.x)
        if not item or column not in {"#2", "#3", "#4"}:
            return
        self._close_tree_editor()
        bbox = self.mapping_tree.bbox(item, column)
        if not bbox:
            return
        x, y, width, height = bbox
        values = list(self.mapping_tree.item(item, "values"))
        col_index = int(column[1:]) - 1
        editor = tk.Entry(self.mapping_tree, font=("Microsoft YaHei UI", 10))
        editor.insert(0, values[col_index])
        editor.select_range(0, tk.END)
        editor.focus_set()
        editor.place(x=x, y=y, width=width, height=height)
        editor.bind("<Return>", lambda _e: self._commit_tree_edit())
        editor.bind("<Escape>", lambda _e: self._close_tree_editor())
        editor.bind("<FocusOut>", lambda _e: self._commit_tree_edit())
        self.mapping_editor = editor
        self.mapping_editor_item = item
        self.mapping_editor_column = column

    def _commit_tree_edit(self) -> None:
        if not self.mapping_editor or self.mapping_editor_item is None or self.mapping_editor_column is None:
            return
        new_value = self.mapping_editor.get().strip()
        item_id = self.mapping_editor_item
        column = self.mapping_editor_column
        self._close_tree_editor()
        entries = self._mapping_entries()
        idx = int(item_id)
        if not (0 <= idx < len(entries)):
            return
        if not self._confirm_edit_after_apply():
            return
        self._save_mapping_undo_snapshot()
        entry = entries[idx]
        if column == "#2":
            category = (new_value or "MANUAL").upper()
            entry["category"] = category
            entry["placeholder"] = SanitizeMappingService.next_placeholder(entries, category, exclude_index=idx)
        elif column == "#3":
            if new_value:
                entry["original"] = new_value
        elif column == "#4" and new_value:
            placeholder, category = SanitizeMappingService.normalize_placeholder_input(
                new_value,
                entries,
                str(entry.get("category", "MANUAL")),
                exclude_index=idx,
            )
            entry["placeholder"] = placeholder
            entry["category"] = category
        self._compact_mapping_placeholders(log_changes=False)
        self._finish_mapping_change()

    def _close_tree_editor(self) -> None:
        if self.mapping_editor is not None:
            try:
                self.mapping_editor.destroy()
            except Exception:
                pass
        self.mapping_editor = None
        self.mapping_editor_item = None
        self.mapping_editor_column = None

    def toggle_selected_mapping_entries(self) -> None:
        entries = self._mapping_entries()
        selected = self.mapping_tree.selection()
        if not entries or not selected:
            return
        if not self._confirm_edit_after_apply():
            return
        self._save_mapping_undo_snapshot()
        for item_id in selected:
            idx = int(item_id)
            if 0 <= idx < len(entries):
                entries[idx]["enabled"] = not bool(entries[idx].get("enabled", True))
        self._finish_mapping_change()

    def remove_selected_mapping_entries(self) -> None:
        entries = self._mapping_entries()
        selected = sorted((int(item_id) for item_id in self.mapping_tree.selection()), reverse=True)
        if not entries or not selected:
            return
        if not self._confirm_edit_after_apply():
            return
        self._save_mapping_undo_snapshot()
        for idx in selected:
            if 0 <= idx < len(entries):
                entries.pop(idx)
        if not entries:
            self.current_mapping_data = None
            self.scan_ready = False
            self._refresh_mapping_tree()
            self.mapping_summary_var.set("尚未识别候选映射。")
            self.sanitize_status_var.set("等待识别")
            self._update_sanitize_action_states()
            return
        self._compact_mapping_placeholders(log_changes=True)
        self._finish_mapping_change()

    def add_manual_mapping_entry(self) -> None:
        sensitive = self.manual_sensitive_var.get().strip()
        replacement = self.manual_placeholder_var.get().strip()
        if self.manual_sensitive_entry.cget("fg") == "#9aa8b6":
            sensitive = ""
        if self.manual_placeholder_entry.cget("fg") == "#9aa8b6":
            replacement = ""
        if not sensitive:
            messagebox.showwarning("缺少参数", "请先填写敏感词。")
            return
        if not self._confirm_edit_after_apply():
            return
        if not self.current_mapping_data:
            self.current_mapping_data = {"version": 2, "source_file": "", "sanitized_file": "", "entries": []}
        self._save_mapping_undo_snapshot()
        entries = self._mapping_entries()
        if any(str(item.get("original", "")).strip() == sensitive for item in entries):
            messagebox.showwarning("重复条目", "当前映射中已存在相同敏感词。")
            return
        entries.append(SanitizeMappingService.manual_entry(sensitive, replacement, entries))
        self._finish_mapping_change()
        self.manual_sensitive_var.set("")
        self.manual_placeholder_var.set("")

    def add_manual_mapping_batch(self) -> None:
        raw = self.batch_add_text.get("1.0", tk.END)
        if self.batch_add_text.cget("fg") == "#9aa8b6":
            raw = ""
        lines = [line.strip() for line in raw.splitlines() if line.strip()]
        if not lines:
            messagebox.showwarning("缺少参数", "请先输入要批量添加的敏感词。")
            return
        if not self._confirm_edit_after_apply():
            return
        if not self.current_mapping_data:
            self.current_mapping_data = {"version": 2, "source_file": "", "sanitized_file": "", "entries": []}
        self._save_mapping_undo_snapshot()
        entries = self._mapping_entries()
        added = 0
        for line in lines:
            sensitive, category_hint, placeholder_hint = SanitizeMappingService.parse_batch_line(line)
            if not sensitive:
                continue
            if any(str(item.get("original", "")).strip() == sensitive for item in entries):
                continue
            entries.append(SanitizeMappingService.manual_entry(sensitive, placeholder_hint or category_hint, entries))
            added += 1
        self._finish_mapping_change()
        self.batch_add_text.delete("1.0", tk.END)
        self.log_queue.put(("sanitize", f"[INFO] 批量添加敏感词：新增 {added} 条"))

    def _save_mapping_undo_snapshot(self) -> None:
        self.mapping_undo_snapshot = copy.deepcopy(self.current_mapping_data) if self.current_mapping_data else None

    def undo_mapping_change(self, event=None):
        if not self.mapping_undo_snapshot:
            self.log_queue.put(("sanitize", "[INFO] 当前没有可撤销的映射变更。"))
            return "break"
        self.current_mapping_data = copy.deepcopy(self.mapping_undo_snapshot)
        self.mapping_undo_snapshot = None
        self.scan_ready = True
        self.mapping_applied = bool(str(self.current_mapping_data.get("sanitized_file", "")).strip()) if self.current_mapping_data else False
        self._finish_mapping_change()
        self.sanitize_status_var.set("已撤销，需重新生成")
        self.log_queue.put(("sanitize", "[INFO] 已撤销最近一次映射变更。"))
        return "break"

    def select_all_visible_mapping_entries(self, event=None):
        children = self.mapping_tree.get_children()
        if children:
            self.mapping_tree.selection_set(children)
        return "break"

    def _compact_mapping_placeholders(self, log_changes: bool = False) -> dict[str, str]:
        entries = self._mapping_entries()
        if not entries:
            return {}
        changes = SanitizeMappingService.compact_placeholders(entries)
        if log_changes and changes:
            preview = "，".join(f"{old}->{new}" for old, new in list(changes.items())[:12])
            suffix = f"，其余 {len(changes) - 12} 项" if len(changes) > 12 else ""
            self.log_queue.put(("sanitize", f"[INFO] 已整理映射编号 {len(changes)} 项：{preview}{suffix}"))
        return changes

    def _confirm_edit_after_apply(self) -> bool:
        if not getattr(self, "mapping_applied", False):
            return True
        confirmed = messagebox.askyesno(
            "已生成脱敏文档",
            "当前映射已用于生成脱敏文档。\n\n"
            "如果继续修改分类、编号、启用状态或条目，之前生成的脱敏文档和映射将不再可靠。\n"
            "请放弃之前生成的文件，并重新生成脱敏文档。\n\n"
            "是否继续编辑？",
        )
        if not confirmed:
            return False
        self.mapping_applied = False
        self.sanitize_status_var.set("已修改，需重新生成")
        self.log_queue.put(("sanitize", "[WARN] 已修改已生成映射，请重新生成脱敏文档；旧输出文件不应再用于外部 AI 或还原。"))
        return True

    def _finish_mapping_change(self) -> None:
        self._rebuild_mapping_metadata()
        self._refresh_mapping_tree()
        self.mapping_summary_var.set(self._mapping_summary_text())
        self._update_sanitize_action_states()

    def _parse_batch_line(self, line: str) -> tuple[str, str, str]:
        return SanitizeMappingService.parse_batch_line(line)

    def _looks_like_category_token(self, text: str) -> bool:
        return SanitizeMappingService.looks_like_category_token(text)

    def _looks_like_placeholder_token(self, text: str) -> bool:
        return SanitizeMappingService.looks_like_placeholder_token(text)

    def _next_manual_placeholder(self, entries: list[dict[str, object]], category: str = "MANUAL", exclude_index: int | None = None) -> str:
        return SanitizeMappingService.next_placeholder(entries, category, exclude_index=exclude_index)

    def _normalize_placeholder_input(
        self,
        raw_value: str,
        entries: list[dict[str, object]],
        preferred_category: str,
        exclude_index: int | None = None,
    ) -> tuple[str, str]:
        return SanitizeMappingService.normalize_placeholder_input(raw_value, entries, preferred_category, exclude_index=exclude_index)

    def _tail_placeholder(self, entries: list[dict[str, object]], category: str, exclude_index: int | None = None) -> str:
        return SanitizeMappingService.tail_placeholder(entries, category, exclude_index=exclude_index)

    def _infer_manual_category(self, placeholder: str, sensitive: str = "") -> str:
        return SanitizeMappingService.infer_manual_category(placeholder, sensitive)

    def _infer_sensitive_category_from_text(self, sensitive: str, placeholder: str = "") -> str:
        return SanitizeMappingService.infer_sensitive_category(sensitive, placeholder)

    def _rebuild_mapping_metadata(self) -> None:
        SanitizeMappingService.rebuild_metadata(self.current_mapping_data)

    def _update_sanitize_action_states(self) -> None:
        entries = self._mapping_entries()
        valid_entries = [
            entry
            for entry in entries
            if str(entry.get("original", "")).strip() and str(entry.get("placeholder", "")).strip()
        ]
        has_mapping = len(valid_entries) > 0
        self.initial_scan_button.configure(state=("disabled" if has_mapping else "normal"))
        self.rescan_button.configure(state=("normal" if has_mapping else "disabled"))
        self.apply_mapping_button.configure(state=("normal" if has_mapping else "disabled"))
