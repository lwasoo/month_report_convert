"""Placeholder repair planning for restore workflows."""

from __future__ import annotations

from pathlib import Path

from doc_sanitizer import read_mapping
from doc_sanitizer.io.text_collection import collect_texts_for_path
from doc_sanitizer.mapping import mapping_entries
from doc_sanitizer.placeholders.repair import PlaceholderRepair, suggest_placeholder_repairs, unresolved_placeholder_tokens


class RestoreRepairsMixin:
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
