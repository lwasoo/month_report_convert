"""Fill metric tables in generated PowerPoint slides."""

from __future__ import annotations

from ..common import normalize_text


def fill_table_metrics(slide, metrics: dict[str, str]) -> None:
    alias_map = {
        "专利申请量": ["专利申请量", "其他知识产权申请", "BU10申请量", "BU11申请量", "BU16申请量"],
        "专利调查量": ["专利调查量", "专利调查量BU10", "专利调查量BU11", "专利调查量BU16"],
        "一般文件用印": ["一般文件用印"],
        "法律文件用印": ["法律文件用印"],
        "集团制式文件用印": ["集团制式文件用印"],
        "非制式文件-供应商": ["非制式文件-供应商"],
        "非制式文件-客户": ["非制式文件-客户"],
        "非制式文件-内部行政": ["非制式文件-内部行政"],
        "非制式文件-重要文件": ["非制式文件-重要文件"],
    }

    def resolve_metric(label: str) -> str:
        norm = normalize_text(label)
        if norm in metrics:
            return metrics.get(norm, "-")
        for key, cands in alias_map.items():
            if norm == key or norm in cands:
                for cand in cands:
                    val = metrics.get(cand)
                    if val and val != "-":
                        return val
        if "申请" in norm and "专利" in norm:
            return metrics.get("专利申请量") or metrics.get("其他知识产权申请") or "-"
        if "调查" in norm and "专利" in norm:
            return metrics.get("专利调查量") or metrics.get("专利调查量BU10") or "-"
        if "一般文件" in norm:
            return metrics.get("一般文件用印", "-")
        if "法律文件" in norm:
            return metrics.get("法律文件用印", "-")
        if "集团制式" in norm:
            return metrics.get("集团制式文件用印", "-")
        if "供应商" in norm and "非制式" in norm:
            return metrics.get("非制式文件-供应商", "-")
        return "-"

    for shp in slide.shapes:
        if not getattr(shp, "has_table", False):
            continue
        table = shp.table
        if len(table.columns) >= 3:
            header_apply = normalize_text(table.cell(0, 1).text)
            header_survey = normalize_text(table.cell(0, 2).text)
            for row_idx in range(1, len(table.rows)):
                row_label = normalize_text(table.cell(row_idx, 0).text).replace(" ", "").upper()
                if row_label in {"BU10", "BU11", "BU16"}:
                    table.cell(row_idx, 1).text = metrics.get(f"{row_label}申请量", metrics.get("专利申请量", "-")) if "申请" in header_apply else "-"
                    table.cell(row_idx, 2).text = metrics.get(f"专利调查量{row_label}", metrics.get("专利调查量", "-")) if "调查" in header_survey else "-"
            continue
        for row_idx in range(1, len(table.rows)):
            label = normalize_text(table.cell(row_idx, 0).text)
            table.cell(row_idx, 1).text = resolve_metric(label)


