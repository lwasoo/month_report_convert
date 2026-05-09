"""Restore tab dialogs for choosing placeholder repairs."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from doc_sanitizer.mapping import MappingPayload
from doc_sanitizer.placeholders.repair import PlaceholderRepair, closest_placeholder_for_token, placeholder_token_category


class RestoreDialogs:
    def _show_unknown_placeholder_dialog(self, tokens: list[str], payload: MappingPayload, items) -> dict[str, str] | None:
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
        return self._build_placeholder_choice_dialog(
            title="指定未知占位符",
            intro="发现映射表里不存在的占位符。请选择对应映射项，或直接输入要还原的原词；留空的项目会保留在文件中，并在日志里提示。",
            rows=rows,
            labels_by_category=labels_by_category,
            placeholder_by_label=placeholder_by_label,
        )

    def _show_placeholder_repair_dialog(self, repairs: list[PlaceholderRepair], payload: MappingPayload) -> dict[str, str] | None:
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

    def _placeholder_choice_labels(self, payload: MappingPayload) -> tuple[dict[str, list[str]], dict[str, str]]:
        entries = [entry for entry in payload.entries or [] if entry.placeholder and entry.original]
        labels_by_category: dict[str, list[str]] = {}
        placeholder_by_label: dict[str, str] = {}
        for entry in entries:
            placeholder = entry.placeholder
            original = entry.original
            category = entry.category or placeholder.strip("_").split("_", 1)[0].upper()
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

