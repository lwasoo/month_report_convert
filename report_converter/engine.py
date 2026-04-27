from __future__ import annotations

import datetime as dt
import json
import random
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from docx import Document
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE
from pptx.enum.text import MSO_AUTO_SIZE, PP_ALIGN
from pptx.util import Inches, Pt

from .constants import ALL_METRIC_LABELS
from .models import SlideDraft, TemplateSlide


def log(message: str, level: str = "INFO") -> None:
    ts = dt.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] [{level}] {message}", flush=True)


def normalize_text(text: str) -> str:
    text = (text or "").replace("\xa0", " ").replace("\n", " ").strip()
    return re.sub(r"\s+", " ", text)


def short_line(text: str, max_len: int | None = None) -> str:
    text = normalize_text(text)
    text = re.sub(r"^[•●\-\d.、\s]+", "", text)
    if max_len is not None and len(text) > max_len:
        return text[:max_len]
    return text


def is_heading_candidate(text: str, style: str) -> bool:
    if style in {"Heading 1", "Heading 2", "Title"} and len(text) <= 40:
        return True
    patterns = [
        r"^[一二三四五六七八九十]+、",
        r"^\d+[、.．]",
        r"^[（(]?[一二三四五六七八九十]+[）)]",
    ]
    if any(re.search(p, text) for p in patterns):
        return True
    return len(text) <= 14 and (text.endswith("项") or text.endswith("专项") or text.endswith("工作"))


def extract_doc_payload(docx_path: Path) -> dict[str, Any]:
    log(f"读取 Word: {docx_path}")
    doc = Document(str(docx_path))

    paragraphs: list[dict[str, str]] = []
    for p in doc.paragraphs:
        text = normalize_text(p.text)
        if not text:
            continue
        style = p.style.name if p.style else ""
        paragraphs.append({"text": text, "style": style})

    if not paragraphs:
        raise ValueError("DOCX 中没有可用文本。")

    title = paragraphs[0]["text"]
    sections: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for row in paragraphs:
        text = row["text"]
        style = row["style"]
        if is_heading_candidate(text, style):
            current = {"heading": text, "items": []}
            sections.append(current)
        else:
            if current is None:
                current = {"heading": title, "items": []}
                sections.append(current)
            current["items"].append(text)

    log(f"Word 解析完成: {len(paragraphs)} 段, {len(sections)} 个章节")
    return {"title": title, "paragraphs": paragraphs, "sections": sections}


def detect_month_label(*sources: str) -> str:
    text = " ".join(filter(None, sources))
    m_cn = re.search(r"([一二三四五六七八九十]{1,3})月", text)
    if m_cn:
        return f"{m_cn.group(1)}月份"
    m_num = re.search(r"\b(1[0-2]|[1-9])月", text)
    if m_num:
        return f"{m_num.group(1)}月份"
    month_map = {
        "january": "1",
        "february": "2",
        "march": "3",
        "april": "4",
        "may": "5",
        "june": "6",
        "july": "7",
        "august": "8",
        "september": "9",
        "october": "10",
        "november": "11",
        "december": "12",
    }
    lower = text.lower()
    for eng, val in month_map.items():
        if eng in lower:
            return f"{val}月份"
    return "本月"


def extract_template_slides(prs: Presentation) -> list[TemplateSlide]:
    log("读取 PPT 模板结构")
    slides: list[TemplateSlide] = []
    for idx, slide in enumerate(prs.slides, start=1):
        if idx == 1 or idx == len(prs.slides):
            continue
        title = ""
        for shp in slide.shapes:
            if getattr(shp, "has_text_frame", False):
                text = normalize_text(shp.text)
                if text:
                    title = text
                    break
        has_table = any(getattr(shp, "has_table", False) for shp in slide.shapes)
        slides.append(TemplateSlide(idx, title or f"第{idx}页", has_table))
    log(f"PPT 模板解析完成: 需要填充 {len(slides)} 页")
    return slides


def keywords_for_title(title: str) -> list[str]:
    mapping = {
        "概述": ["概述", "重点", "风险", "提示", "总体"],
        "337": ["337", "TA1484", "调查", "项目", "进度"],
        "劳动诉讼": ["劳动", "仲裁", "诉讼", "开庭", "解除"],
        "基础运作流程数据": ["基础数据", "一般文件", "法律文件", "专利", "统计", "累计"],
        "典型协议与合同管理": ["协议", "合同", "审核", "评审", "起草", "补充协议"],
        "知识产权": ["知识产权", "专利", "商标", "IP", "无效", "调查"],
        "仲裁与诉讼": ["仲裁", "诉讼", "案件", "开庭", "判决", "风险"],
        "合规事务": ["合规", "出口管制", "数据安全", "保密", "培训"],
        "法律法规政策": ["最高法", "政策", "法规", "指导意见", "解释"],
        "内部学习成长": ["学习", "培训", "课程", "新员工", "成长"],
    }
    for key, vals in mapping.items():
        if key in title:
            return vals
    tokens = re.split(r"[、，,\-—\s]+", title)
    tokens = [t for t in tokens if len(t) >= 2]
    return tokens[:6] or [title[:8]]


def preferred_heading_keywords(title: str) -> list[str]:
    if "知识产权" in title:
        return ["知识产权", "专利", "IP", "商标"]
    if "典型协议与合同管理" in title:
        return ["专案性工作", "合同", "协议", "评审", "审核"]
    if "仲裁与诉讼" in title:
        return ["诉讼个案", "仲裁", "诉讼"]
    if "合规事务" in title:
        return ["合规", "风险", "出口管制", "政府项目"]
    if "法律法规政策" in title:
        return ["政策", "解释", "指导意见", "最高人民法院"]
    return []


def required_terms_for_title(title: str) -> list[str]:
    terms: list[str] = []
    if "美国" in title:
        terms.extend(["美国", "北美", "US", "U.S."])
    return terms


def title_profile(title: str) -> dict[str, list[str]]:
    if "知识产权" in title:
        return {
            "required": ["专利", "IP", "商标", "无效", "权属", "侵权", "提案", "调查"],
            "forbidden": ["仲裁", "诉讼", "开庭", "违法解除", "劳动争议"],
        }
    if "典型协议与合同管理" in title:
        return {
            "required": ["合同", "协议", "评审", "审核", "起草", "签署", "条款"],
            "forbidden": ["仲裁", "诉讼", "违法解除", "开庭"],
        }
    if "仲裁与诉讼" in title:
        return {
            "required": ["仲裁", "诉讼", "开庭", "裁决", "判决", "违法解除"],
            "forbidden": [],
        }
    if "合规事务" in title:
        return {
            "required": ["合规", "出口管制", "ECCN", "保密", "数据安全", "BIS", "律师函"],
            "forbidden": ["仲裁", "诉讼", "开庭"],
        }
    if "法律法规政策" in title:
        return {
            "required": ["政策", "法规", "指导意见", "解释", "发布", "最高人民法院", "邮件发"],
            "forbidden": [],
        }
    if "基础运作流程数据" in title:
        return {
            "required": ["数量", "累计", "件", "一般文件", "法律文件", "申请", "调查", "数据"],
            "forbidden": ["仲裁", "诉讼", "开庭"],
        }
    return {"required": [], "forbidden": []}


def matches_title_profile(line: str, title: str) -> bool:
    profile = title_profile(title)
    required = profile["required"]
    forbidden = profile["forbidden"]
    if any(k in line for k in forbidden):
        return False
    if required:
        return any(k in line for k in required)
    return True


def apply_title_strict_filter(title: str, lines: list[str]) -> list[str]:
    filtered = lines
    if "美国劳动诉讼" in title:
        filtered = [
            x
            for x in filtered
            if any(t in x for t in ["美国", "北美", "US", "U.S."])
            and any(t in x for t in ["劳动", "诉讼", "仲裁", "开庭", "解除"])
        ]
    if "337" in title:
        filtered = [x for x in filtered if ("337" in x or "TA1484" in x)]
    filtered = [x for x in filtered if matches_title_profile(x, title)]
    return filtered


def score_line(line: str, keywords: list[str]) -> int:
    score = 0
    for kw in keywords:
        if kw and kw in line:
            score += 3
    if any(x in line for x in ["风险", "诉讼", "仲裁", "合规", "协议", "合同", "专利", "调查", "培训"]):
        score += 1
    return score


def select_source_lines(template_slides: list[TemplateSlide], sections: list[dict[str, Any]]) -> dict[int, list[str]]:
    corpus: list[str] = []
    heading_pairs: list[tuple[str, str]] = []
    for sec in sections:
        heading = normalize_text(sec.get("heading", ""))
        if heading:
            corpus.append(heading)
            heading_pairs.append((heading, heading))
        for item in sec.get("items", []):
            text = normalize_text(item)
            if text:
                corpus.append(text)
                heading_pairs.append((heading, text))

    selected: dict[int, list[str]] = {}
    for slide in template_slides:
        kws = keywords_for_title(slide.title)
        req_terms = required_terms_for_title(slide.title)
        preferred_heads = preferred_heading_keywords(slide.title)
        candidate_pairs = heading_pairs
        if preferred_heads:
            prioritized = [
                (h, line)
                for h, line in heading_pairs
                if any(k in h for k in preferred_heads)
            ]
            if prioritized:
                candidate_pairs = prioritized + [
                    (h, line)
                    for h, line in heading_pairs
                    if (h, line) not in prioritized
                ]
        ranked = sorted([line for _, line in candidate_pairs], key=lambda x: score_line(x, kws), reverse=True)
        lines = [x for x in ranked if score_line(x, kws) > 0]
        if req_terms:
            lines = [x for x in lines if any(t in x for t in req_terms)]
        lines = apply_title_strict_filter(slide.title, lines)
        lines = lines[:6]

        unique: list[str] = []
        seen: set[str] = set()
        for line in lines:
            sig = line[:24]
            if sig in seen:
                continue
            seen.add(sig)
            unique.append(line)
        selected[slide.slide_index] = unique[:6]
    return selected


def extract_json_object(text: str) -> str:
    payload = text.strip()
    if payload.startswith("{") and payload.endswith("}"):
        return payload
    m = re.search(r"\{[\s\S]*\}", payload)
    if m:
        return m.group(0)
    raise ValueError("LLM 返回中未找到 JSON。")


def call_ollama_json(ollama_url: str, model: str, prompt: str, timeout_sec: int, retries: int) -> dict[str, Any]:
    system_prompt = (
        "你是企业法务月报编辑。"
        "输出只能是严格 JSON。"
        "要写成 PPT 汇报语言，但必须保留关键细节：BU、项目名、案件名、日期、数字。"
    )
    endpoints = [
        (
            f"{ollama_url.rstrip('/')}/api/chat",
            {
                "model": model,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.2},
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
            },
            "chat",
        ),
        (
            f"{ollama_url.rstrip('/')}/api/generate",
            {
                "model": model,
                "stream": False,
                "format": "json",
                "options": {"temperature": 0.2},
                "system": system_prompt,
                "prompt": prompt,
            },
            "generate",
        ),
    ]

    last_error: Exception | None = None
    for attempt in range(1, max(retries, 1) + 1):
        for url, payload, mode in endpoints:
            log(f"调用 Ollama ({mode})，第 {attempt} 次: {url}")
            req = urllib.request.Request(
                url=url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                    raw = resp.read().decode("utf-8")
                parsed = json.loads(raw)
                if parsed.get("error"):
                    raise RuntimeError(str(parsed["error"]))
                content = (
                    parsed.get("message", {}).get("content", "").strip()
                    if mode == "chat"
                    else str(parsed.get("response", "")).strip()
                )
                obj = json.loads(extract_json_object(content))
                log("Ollama 返回成功")
                return obj
            except urllib.error.HTTPError as exc:
                last_error = exc
                if exc.code == 404:
                    log(f"端点不存在(404): {url}", level="WARN")
                    continue
                log(f"HTTP 错误: {exc}", level="WARN")
            except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
                last_error = exc
                log(f"Ollama 调用失败: {exc}", level="WARN")

    if last_error is None:
        raise RuntimeError("Ollama 调用失败。")
    raise RuntimeError(f"Ollama 调用失败: {last_error}") from last_error


def build_rewrite_prompt(
    report_title: str,
    month_label: str,
    template_slides: list[TemplateSlide],
    selected_sources: dict[int, list[str]],
) -> str:
    blocks: list[str] = []
    for s in template_slides:
        blocks.append(f"## slide_index={s.slide_index} | 标题={s.title}")
        for line in selected_sources.get(s.slide_index, []):
            blocks.append(f"- {line}")
    source_block = "\n".join(blocks)
    return f"""请将素材改写为 PPT 月报要点。

【报告】{report_title}
【月份】{month_label}

【规则】
1. 标题固定，不改标题。
2. 每页 bullets 3-5 条，第5页仅 2 条。
3. 用汇报语气，保留细节：BU、项目、案件、日期、数字。
4. 每条尽量 24-48 字，信息完整，不写口号句。
4. 不要输出省略号“…”。
5. 只输出 JSON。

【输出 JSON】
{{
  "slides":[
    {{"slide_index":2,"bullets":["...","...","..."]}}
  ],
  "metrics": {{
    "一般文件用印":"-",
    "法律文件用印":"-",
    "集团制式文件用印":"-",
    "非制式文件-供应商":"-",
    "非制式文件-客户":"-",
    "非制式文件-内部行政":"-",
    "非制式文件-重要文件":"-",
    "BU10申请量":"-",
    "BU11申请量":"-",
    "BU16申请量":"-",
    "专利调查量BU10":"-",
    "专利调查量BU11":"-",
    "专利调查量BU16":"-",
    "其他知识产权申请":"-"
  }}
}}

【素材池（按页）】
{source_block}
"""


def extract_detail_tokens(line: str) -> list[str]:
    line = normalize_text(line)
    tokens: list[str] = []
    patterns = [
        r"BU\d+",
        r"TA\d+",
        r"\d+\s*月\s*\d+\s*日",
        r"\d+/\d+",
        r"\d+(?:件|万|万元|亿|亿元|天)",
        r"[A-Z]{2,}(?:[-_][A-Z0-9]+)?",
        r"(?:[\u4e00-\u9fff]{2,10}案)",
        r"(?:[\u4e00-\u9fffA-Za-z0-9\-]{2,20}项目)",
    ]
    for p in patterns:
        tokens.extend(re.findall(p, line))
    out: list[str] = []
    seen: set[str] = set()
    for t in tokens:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out[:4]


def clean_generated_line(line: str) -> str:
    text = normalize_text(line)
    text = re.sub(r"^\d+[.、]\s*", "", text)
    text = re.sub(r"^[（(]\d+[)）]\s*", "", text)
    text = text.replace("IP掉擦汗", "IP")
    text = text.replace("Bipass", "Bypass")
    return text


def compress_for_ppt(line: str, title: str) -> str:
    text = clean_generated_line(line).replace("…", "")
    text = re.sub(r"^(本月|目前|新增|针对|其中|参与|支持|组织|开展|配合)\s*", "", text)
    if len(text) <= 64:
        return text

    clauses = [c.strip() for c in re.split(r"[，。；;]", text) if c.strip()]
    if not clauses:
        return short_line(text)

    main = clauses[0]
    node = ""
    if any(k in title for k in ["诉讼", "仲裁"]):
        for c in clauses[1:]:
            if re.search(r"\d+\s*月\s*\d+\s*日", c) or any(k in c for k in ["开庭", "仲裁", "裁决", "判决"]):
                node = c
                break
    else:
        for c in clauses[1:]:
            if re.search(r"\d", c) or any(k in c for k in ["评审", "审核", "起草", "排查", "调查", "培训", "发布"]):
                node = c
                break

    merged = f"{main}，{node}" if node else main
    merged = re.sub(r"\s+", " ", merged).strip("， ")
    return short_line(merged)


def detail_fallback_line(source: str, title: str) -> str:
    src = clean_generated_line(source)
    clauses = [c.strip() for c in re.split(r"[。；;]", src) if c.strip()]
    main = clauses[0] if clauses else src
    parts = [p.strip() for p in main.split("，") if p.strip()]
    if len(parts) >= 2:
        merged = f"{parts[0]}，{parts[1]}"
    else:
        merged = parts[0] if parts else main
    merged = re.sub(r"^(本月|目前|新增|针对|其中)\s*", "", merged)
    merged = compress_for_ppt(merged, title)
    if len(merged) < 12:
        return short_line(f"{merged}，节点跟进")
    return merged


def is_too_generic(line: str) -> bool:
    text = normalize_text(line)
    generic_words = ["持续推进", "持续跟进", "机制优化", "闭环推进", "按计划推进", "同步推进", "事项推进"]
    if bool(extract_detail_tokens(text)):
        return False
    if len(text) <= 12:
        return True
    return any(w in text for w in generic_words) and len(text) <= 24


def has_specific_signal(line: str, title: str) -> bool:
    text = normalize_text(line)
    if extract_detail_tokens(text):
        return True
    profile = title_profile(title)
    required = profile["required"]
    if not required:
        return len(text) >= 16
    hit = sum(1 for k in required if k in text)
    return hit >= 2


def is_near_copy(line: str, sources: list[str]) -> bool:
    clean = normalize_text(line).replace(" ", "")
    if len(clean) < 18:
        return False
    for src in sources:
        s = normalize_text(src).replace(" ", "")
        if clean in s and len(clean) / max(len(s), 1) > 0.78:
            return True
    return False


def canonical_line(text: str) -> str:
    s = normalize_text(text).lower()
    s = re.sub(r"[，。；;：:、（）()【】\[\]\-—_·\s]", "", s)
    return s


def is_duplicate_global(line: str, seen: list[str]) -> bool:
    key = canonical_line(line)
    if not key:
        return True
    for prev in seen:
        if key == prev:
            return True
        if len(key) >= 18 and (key in prev or prev in key):
            return True
    return False


def dedupe_drafts_across_slides(
    drafts: list[SlideDraft],
    template_slides: list[TemplateSlide],
    selected_sources: dict[int, list[str]],
) -> list[SlideDraft]:
    by_idx = {d.slide_index: d for d in drafts}
    seen: list[str] = []
    out: list[SlideDraft] = []

    for s in template_slides:
        draft = by_idx.get(s.slide_index, SlideDraft(s.slide_index, []))
        target_max = 2 if s.has_table else 5
        deduped: list[str] = []
        for line in draft.bullets:
            if is_duplicate_global(line, seen):
                continue
            deduped.append(line)
            seen.append(canonical_line(line))
            if len(deduped) >= target_max:
                break

        if len(deduped) < target_max:
            for src in selected_sources.get(s.slide_index, []):
                candidate = detail_fallback_line(src, s.title)
                if is_duplicate_global(candidate, seen):
                    continue
                deduped.append(candidate)
                seen.append(canonical_line(candidate))
                if len(deduped) >= target_max:
                    break

        out.append(SlideDraft(s.slide_index, deduped))
    return out


def clean_metrics(raw_metrics: Any) -> dict[str, str]:
    metrics = {k: "-" for k in ALL_METRIC_LABELS}
    if isinstance(raw_metrics, dict):
        for k in metrics:
            if k in raw_metrics:
                metrics[k] = normalize_text(str(raw_metrics[k])) or "-"
    return metrics


def extract_numeric_metrics(paragraphs: list[dict[str, str]], metrics: dict[str, str]) -> dict[str, str]:
    text = "\n".join(p["text"] for p in paragraphs)

    def find(pattern: str) -> str | None:
        m = re.search(pattern, text)
        return m.group(1) if m else None

    general = find(r"一般文件数量为\s*([0-9,]+)")
    legal = find(r"法律文件数量为\s*([0-9,]+)")
    patent_apply = find(r"申请提案总\s*([0-9,]+)\s*件")
    patent_survey = find(r"专利调查统计[:：]?\s*总\s*([0-9,]+)\s*件")

    if general and metrics["一般文件用印"] == "-":
        metrics["一般文件用印"] = general
    if legal and metrics["法律文件用印"] == "-":
        metrics["法律文件用印"] = legal
    if patent_apply and metrics["BU10申请量"] == "-":
        metrics["BU10申请量"] = f"总{patent_apply}(未拆分)"
    if patent_survey and metrics["专利调查量BU10"] == "-":
        metrics["专利调查量BU10"] = f"总{patent_survey}(未拆分)"
    if patent_apply and metrics["其他知识产权申请"] == "-":
        metrics["其他知识产权申请"] = patent_apply
    return metrics


def fallback_drafts(template_slides: list[TemplateSlide], selected_sources: dict[int, list[str]]) -> list[SlideDraft]:
    log("使用规则模式生成细节要点")
    drafts: list[SlideDraft] = []
    for s in template_slides:
        sources = selected_sources.get(s.slide_index, [])
        target_max = 2 if s.has_table else 5
        target_min = 2 if s.has_table else 3
        if not sources:
            drafts.append(SlideDraft(s.slide_index, []))
            continue
        lines: list[str] = []
        for src in sources:
            candidate = detail_fallback_line(src, s.title)
            if candidate not in lines:
                lines.append(candidate)
            if len(lines) >= target_max:
                break
        while len(lines) < target_min:
            lines.append(short_line(f"{s.title}重点事项跟进"))
        drafts.append(SlideDraft(s.slide_index, lines[:target_max]))
    return drafts


def build_drafts_and_metrics(
    use_llm: bool,
    ollama_url: str,
    model: str,
    timeout_sec: int,
    retries: int,
    report_title: str,
    month_label: str,
    template_slides: list[TemplateSlide],
    doc_payload: dict[str, Any],
) -> tuple[list[SlideDraft], dict[str, str]]:
    selected_sources = select_source_lines(template_slides, doc_payload["sections"])
    fallback = fallback_drafts(template_slides, selected_sources)
    fallback_map = {d.slide_index: d for d in fallback}

    if use_llm:
        try:
            prompt = build_rewrite_prompt(report_title, month_label, template_slides, selected_sources)
            raw = call_ollama_json(ollama_url, model, prompt, timeout_sec, retries)

            by_idx: dict[int, SlideDraft] = {}
            for row in raw.get("slides", []):
                try:
                    idx = int(row.get("slide_index"))
                except Exception:
                    continue
                bullets_raw = row.get("bullets", [])
                bullets: list[str] = []
                if isinstance(bullets_raw, list):
                    for item in bullets_raw:
                        line = short_line(clean_generated_line(str(item)))
                        if line and line not in bullets:
                            bullets.append(line)
                by_idx[idx] = SlideDraft(idx, bullets[:5])

            drafts: list[SlideDraft] = []
            for s in template_slides:
                draft = by_idx.get(s.slide_index, SlideDraft(s.slide_index, []))
                target_max = 2 if s.has_table else 5
                target_min = 2 if s.has_table else 3
                sources = selected_sources.get(s.slide_index, [])
                if not sources:
                    drafts.append(SlideDraft(s.slide_index, []))
                    continue

                cleaned: list[str] = []
                for b in draft.bullets:
                    line = b
                    if not matches_title_profile(line, s.title):
                        continue
                    if is_near_copy(line, sources):
                        line = detail_fallback_line(sources[0] if sources else line, s.title)
                    if is_too_generic(line):
                        line = detail_fallback_line(sources[0] if sources else line, s.title)
                    if not has_specific_signal(line, s.title):
                        line = detail_fallback_line(sources[0] if sources else line, s.title)
                    line = compress_for_ppt(line, s.title)
                    if line not in cleaned:
                        cleaned.append(line)
                    if len(cleaned) >= target_max:
                        break

                if len(cleaned) < target_min:
                    for b in fallback_map[s.slide_index].bullets:
                        if b not in cleaned:
                            cleaned.append(b)
                        if len(cleaned) >= target_max:
                            break

                drafts.append(SlideDraft(s.slide_index, cleaned[:target_max]))

            metrics = clean_metrics(raw.get("metrics", {}))
            metrics = extract_numeric_metrics(doc_payload["paragraphs"], metrics)
            drafts = dedupe_drafts_across_slides(drafts, template_slides, selected_sources)
            return drafts, metrics
        except Exception as exc:
            log(f"LLM 改写失败，回退规则模式: {exc}", level="WARN")

    metrics = extract_numeric_metrics(doc_payload["paragraphs"], clean_metrics({}))
    fallback = dedupe_drafts_across_slides(fallback, template_slides, selected_sources)
    return fallback, metrics


def remove_auto_shapes(slide) -> None:
    for shp in list(slide.shapes):
        if shp.name.startswith("AUTO_CONTENT_") or shp.name.startswith("AUTO_LAYOUT_"):
            slide.shapes._spTree.remove(shp._element)


def style_paragraph(paragraph, size: int) -> None:
    paragraph.font.name = "Microsoft YaHei"
    paragraph.font.size = Pt(size)
    paragraph.font.bold = False
    paragraph.alignment = PP_ALIGN.LEFT
    paragraph.line_spacing = 1.2


def get_theme_palette(theme: str) -> dict[str, RGBColor]:
    if theme == "corporate_gray":
        return {
            "accent": RGBColor(0x43, 0x4A, 0x54),
            "soft": RGBColor(0xEE, 0xF0, 0xF2),
            "text_dark": RGBColor(0x1F, 0x22, 0x28),
            "text_light": RGBColor(0xFF, 0xFF, 0xFF),
            "border": RGBColor(0xC8, 0xCD, 0xD2),
        }
    if theme == "legal_red":
        return {
            "accent": RGBColor(0x9E, 0x2A, 0x2B),
            "soft": RGBColor(0xFA, 0xED, 0xED),
            "text_dark": RGBColor(0x2A, 0x14, 0x14),
            "text_light": RGBColor(0xFF, 0xFF, 0xFF),
            "border": RGBColor(0xE0, 0xB9, 0xB9),
        }
    # formal_blue
    return {
        "accent": RGBColor(0x1F, 0x4E, 0x79),
        "soft": RGBColor(0xE9, 0xF1, 0xF8),
        "text_dark": RGBColor(0x0E, 0x2A, 0x43),
        "text_light": RGBColor(0xFF, 0xFF, 0xFF),
        "border": RGBColor(0xB7, 0xD0, 0xE4),
    }


def suggest_font_size(lines: list[str], base: int = 16) -> int:
    if not lines:
        return base
    longest = max(len(normalize_text(x)) for x in lines)
    if longest > 58:
        return max(base - 3, 12)
    if longest > 50:
        return max(base - 2, 13)
    if longest > 42:
        return max(base - 1, 14)
    return base


def split_balanced(lines: list[str]) -> tuple[list[str], list[str]]:
    if len(lines) <= 1:
        return lines, []
    mid = (len(lines) + 1) // 2
    return lines[:mid], lines[mid:]


def _write_lines_to_box(slide, name: str, left, top, width, height, rows: list[str], font_size: int, bullet: str) -> None:
    if not rows:
        return
    box = slide.shapes.add_textbox(left, top, width, height)
    box.name = name
    tf = box.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.auto_size = MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    for i, row in enumerate(rows):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = f"{bullet}{row}" if bullet else row
        style_paragraph(p, size=font_size)
        p.level = 0


def add_content_textbox(slide, draft: SlideDraft, has_table: bool) -> None:
    if not draft.bullets:
        return

    if has_table:
        left, top, width, height = Inches(0.5), Inches(4.95), Inches(8.9), Inches(0.6)
        max_rows, font_size = 2, 13
        rows = draft.bullets[:max_rows]
        _write_lines_to_box(
            slide,
            f"AUTO_CONTENT_{draft.slide_index}",
            left,
            top,
            width,
            height,
            rows,
            font_size,
            bullet="",
        )
        return

    left, top, width, height = Inches(0.55), Inches(1.12), Inches(8.9), Inches(4.5)
    max_rows = 5
    rows = draft.bullets[:max_rows]
    font_size = suggest_font_size(rows, base=16)
    _write_lines_to_box(
        slide,
        f"AUTO_CONTENT_{draft.slide_index}",
        left,
        top,
        width,
        height,
        rows,
        font_size,
        bullet="• ",
    )


def add_formal_layout_content(slide, draft: SlideDraft, has_table: bool) -> None:
    # legacy adapter kept for compatibility
    add_formal_layout_content_v2(
        slide=slide,
        draft=draft,
        has_table=has_table,
        title="",
        theme="formal_blue",
        diversity="medium",
        seed=0,
    )


def choose_formal_variant(title: str, bullets: list[str], diversity: str, seed: int, slide_index: int) -> str:
    t = title or ""
    if any(k in t for k in ["风险", "诉讼", "仲裁"]):
        base = ["risk_matrix", "timeline", "two_column"]
    elif any(k in t for k in ["数据", "统计", "流程"]):
        base = ["kpi_cards", "two_column", "single_column"]
    elif any(k in t for k in ["项目", "进度", "政策", "合规"]):
        base = ["timeline", "two_column", "single_column"]
    else:
        base = ["two_column", "single_column", "kpi_cards"]

    if len(bullets) <= 2:
        return "single_column"
    if len(bullets) >= 4 and diversity == "high":
        base = ["two_column", "timeline", "kpi_cards", "risk_matrix"]
    elif diversity == "low":
        base = [base[0]]

    if not base:
        return "single_column"
    rng = random.Random((seed or 0) * 131 + slide_index * 17 + len(bullets))
    return base[rng.randrange(len(base))]


def add_visual_accent(slide, slide_index: int, palette: dict[str, RGBColor]) -> None:
    accent = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.RECTANGLE,
        Inches(0.52),
        Inches(1.16),
        Inches(0.06),
        Inches(3.9),
    )
    accent.name = f"AUTO_LAYOUT_ACCENT_{slide_index}"
    accent.fill.solid()
    accent.fill.fore_color.rgb = palette["accent"]
    accent.line.fill.background()


def render_single_column(slide, slide_index: int, rows: list[str], font_size: int) -> None:
    _write_lines_to_box(
        slide,
        f"AUTO_CONTENT_{slide_index}",
        Inches(0.72),
        Inches(1.15),
        Inches(8.55),
        Inches(4.35),
        rows,
        font_size,
        bullet="▪ ",
    )


def render_two_column(slide, slide_index: int, rows: list[str], font_size: int) -> None:
    left_rows, right_rows = split_balanced(rows)
    col_top = Inches(1.15)
    col_height = Inches(4.35)
    col_gap = Inches(0.28)
    col_width = Inches(4.18)
    _write_lines_to_box(
        slide,
        f"AUTO_CONTENT_{slide_index}_L",
        Inches(0.72),
        col_top,
        col_width,
        col_height,
        left_rows,
        font_size,
        bullet="▪ ",
    )
    _write_lines_to_box(
        slide,
        f"AUTO_CONTENT_{slide_index}_R",
        Inches(0.72) + col_width + col_gap,
        col_top,
        col_width,
        col_height,
        right_rows,
        font_size,
        bullet="▪ ",
    )


def render_timeline(slide, slide_index: int, rows: list[str], font_size: int, palette: dict[str, RGBColor]) -> None:
    line = slide.shapes.add_shape(
        MSO_AUTO_SHAPE_TYPE.RECTANGLE,
        Inches(1.02),
        Inches(1.2),
        Inches(0.05),
        Inches(4.15),
    )
    line.name = f"AUTO_LAYOUT_TIMELINE_LINE_{slide_index}"
    line.fill.solid()
    line.fill.fore_color.rgb = palette["border"]
    line.line.fill.background()

    max_rows = min(5, len(rows))
    spacing = 4.0 / max(max_rows, 1)
    for i, row in enumerate(rows[:max_rows]):
        y = 1.25 + i * spacing
        dot = slide.shapes.add_shape(
            MSO_AUTO_SHAPE_TYPE.OVAL,
            Inches(0.94),
            Inches(y),
            Inches(0.2),
            Inches(0.2),
        )
        dot.name = f"AUTO_LAYOUT_TIMELINE_DOT_{slide_index}_{i}"
        dot.fill.solid()
        dot.fill.fore_color.rgb = palette["accent"]
        dot.line.fill.background()
        _write_lines_to_box(
            slide,
            f"AUTO_CONTENT_{slide_index}_T_{i}",
            Inches(1.28),
            Inches(y - 0.02),
            Inches(7.95),
            Inches(0.8),
            [row],
            font_size,
            bullet="",
        )


def render_kpi_cards(slide, slide_index: int, rows: list[str], font_size: int, palette: dict[str, RGBColor]) -> None:
    max_rows = min(4, len(rows))
    card_w = Inches(4.18)
    card_h = Inches(2.0)
    gap_x = Inches(0.28)
    start_x = Inches(0.72)
    start_y = Inches(1.2)
    for i, row in enumerate(rows[:max_rows]):
        col = i % 2
        row_idx = i // 2
        left = start_x + (card_w + gap_x) * col
        top = start_y + Inches(2.12) * row_idx
        card = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE, left, top, card_w, card_h)
        card.name = f"AUTO_LAYOUT_CARD_{slide_index}_{i}"
        card.fill.solid()
        card.fill.fore_color.rgb = palette["soft"]
        card.line.color.rgb = palette["border"]
        _write_lines_to_box(
            slide,
            f"AUTO_CONTENT_{slide_index}_C_{i}",
            left + Inches(0.16),
            top + Inches(0.16),
            card_w - Inches(0.32),
            card_h - Inches(0.32),
            [row],
            max(font_size - 1, 12),
            bullet="",
        )


def render_risk_matrix(slide, slide_index: int, rows: list[str], font_size: int, palette: dict[str, RGBColor]) -> None:
    labels = ["高影响", "中高影响", "中影响", "一般影响"]
    max_rows = min(4, len(rows))
    cell_w = Inches(4.18)
    cell_h = Inches(2.02)
    gap_x = Inches(0.28)
    gap_y = Inches(0.22)
    start_x = Inches(0.72)
    start_y = Inches(1.2)
    for i in range(max_rows):
        col = i % 2
        row_idx = i // 2
        left = start_x + (cell_w + gap_x) * col
        top = start_y + (cell_h + gap_y) * row_idx
        cell = slide.shapes.add_shape(MSO_AUTO_SHAPE_TYPE.RECTANGLE, left, top, cell_w, cell_h)
        cell.name = f"AUTO_LAYOUT_RISK_{slide_index}_{i}"
        cell.fill.solid()
        cell.fill.fore_color.rgb = palette["soft"]
        cell.line.color.rgb = palette["border"]
        _write_lines_to_box(
            slide,
            f"AUTO_CONTENT_{slide_index}_RISK_TAG_{i}",
            left + Inches(0.08),
            top + Inches(0.06),
            Inches(1.18),
            Inches(0.35),
            [labels[i]],
            11,
            bullet="",
        )
        _write_lines_to_box(
            slide,
            f"AUTO_CONTENT_{slide_index}_RISK_{i}",
            left + Inches(0.08),
            top + Inches(0.44),
            cell_w - Inches(0.18),
            cell_h - Inches(0.52),
            [rows[i]],
            max(font_size - 2, 11),
            bullet="",
        )


def collect_style_reference_layouts(style_pptx: Path | None) -> dict[int, list[dict[str, float]]]:
    if not style_pptx:
        return {}
    if not style_pptx.exists():
        log(f"参考样式 PPT 不存在，已忽略: {style_pptx}", level="WARN")
        return {}
    try:
        prs = Presentation(str(style_pptx))
    except Exception as exc:
        log(f"读取参考样式 PPT 失败，已忽略: {exc}", level="WARN")
        return {}

    layouts: dict[int, list[dict[str, float]]] = {}
    ref_w = max(int(prs.slide_width), 1)
    ref_h = max(int(prs.slide_height), 1)
    for idx, slide in enumerate(prs.slides, start=1):
        if idx == 1 or idx == len(prs.slides):
            continue
        slots: list[dict[str, float]] = []
        for shp in slide.shapes:
            if not getattr(shp, "has_text_frame", False):
                continue
            text = normalize_text(getattr(shp, "text", ""))
            if not text:
                continue
            if shp.top < Inches(0.95):
                # Skip likely title area
                continue
            if shp.width < Inches(1.5) or shp.height < Inches(0.35):
                continue
            area_ratio = (float(shp.width) * float(shp.height)) / float(ref_w * ref_h)
            if area_ratio > 0.70:
                continue

            size = 14
            try:
                p = shp.text_frame.paragraphs[0]
                if p.runs and p.runs[0].font.size:
                    size = int(p.runs[0].font.size.pt)
                elif p.font and p.font.size:
                    size = int(p.font.size.pt)
            except Exception:
                pass

            slots.append(
                {
                    "left_ratio": float(shp.left) / ref_w,
                    "top_ratio": float(shp.top) / ref_h,
                    "width_ratio": float(shp.width) / ref_w,
                    "height_ratio": float(shp.height) / ref_h,
                    "font_size": float(min(max(size, 11), 16)),
                }
            )

        slots = sorted(slots, key=lambda x: (x["top_ratio"], x["left_ratio"]))[:4]
        if slots:
            layouts[idx] = slots

    if layouts:
        log(f"参考样式布局已载入: {len(layouts)} 页")
    else:
        log("参考样式布局未提取到可用内容框，将使用内置布局", level="WARN")
    return layouts


def _calc_text_fit(
    rows: list[str],
    width_emu: int,
    height_emu: int,
    base_font_size: int,
    bullet_len: int,
) -> int | None:
    width_in = max(width_emu / 914400.0, 0.6)
    height_in = max(height_emu / 914400.0, 0.25)
    for size in range(min(base_font_size, 16), 10, -1):
        chars_per_line = max(int((width_in * 72) / (size * 1.02)), 8)
        used_lines = 0
        for row in rows:
            text_len = len(normalize_text(row)) + bullet_len
            used_lines += max((text_len + chars_per_line - 1) // chars_per_line, 1)
        max_lines = max(int((height_in * 72) / (size * 1.55)), 1)
        if used_lines <= max_lines:
            return size
    return None


def _merge_rows_for_reference(rows: list[str], slot_count: int) -> list[list[str]]:
    if slot_count <= 0:
        return []
    chunk = max((len(rows) + slot_count - 1) // slot_count, 1)
    out: list[list[str]] = []
    cursor = 0
    for i in range(slot_count):
        part = rows[cursor : cursor + chunk]
        cursor += chunk
        if i == slot_count - 1 and cursor < len(rows):
            part.extend(rows[cursor:])
        if not part:
            out.append([])
            continue
        # Merge multiple bullets into 1-2 compact lines to fit narrow reference slots.
        merged: list[str] = []
        buf = ""
        for line in part:
            piece = normalize_text(line)
            if not piece:
                continue
            if not buf:
                buf = piece
                continue
            if len(buf) + len(piece) + 1 <= 54:
                buf = f"{buf}；{piece}"
            else:
                merged.append(buf)
                buf = piece
        if buf:
            merged.append(buf)
        out.append(merged[:2])
    return out


def pick_reference_slots(
    slide_index: int,
    reference_layouts: dict[int, list[dict[str, float]]],
) -> list[dict[str, float]] | None:
    if not reference_layouts:
        return None
    if slide_index in reference_layouts:
        return reference_layouts[slide_index]
    keys = sorted(reference_layouts.keys())
    if not keys:
        return None
    # Reuse style pages cyclically so non-matching page numbers can still borrow reference layout.
    pos = (slide_index - 2) % len(keys)
    return reference_layouts[keys[pos]]


def render_reference_layout(
    slide,
    slide_index: int,
    rows: list[str],
    slots: list[dict[str, float]],
    target_slide_width: int,
    target_slide_height: int,
) -> bool:
    if not rows or not slots:
        return False
    if len(slots) == 1 and len(rows) >= 4:
        return False

    safe_slots = [s for s in slots if s.get("width_ratio", 0) >= 0.18 and s.get("height_ratio", 0) >= 0.10]
    if not safe_slots:
        return False

    slots = sorted(safe_slots, key=lambda x: (x.get("top_ratio", 0), x.get("left_ratio", 0)))[:4]
    slot_parts = _merge_rows_for_reference(rows, len(slots))
    for i, slot in enumerate(slots):
        part = slot_parts[i] if i < len(slot_parts) else []
        if not part:
            continue

        left = int(target_slide_width * float(slot.get("left_ratio", 0.1)))
        top = int(target_slide_height * float(slot.get("top_ratio", 0.2)))
        width = int(target_slide_width * float(slot.get("width_ratio", 0.7)))
        height = int(target_slide_height * float(slot.get("height_ratio", 0.2)))
        if width < int(Inches(1.2)) or height < int(Inches(0.35)):
            return False

        bullet = ""
        fit_size = _calc_text_fit(
            rows=part,
            width_emu=width,
            height_emu=height,
            base_font_size=int(slot.get("font_size", 14)),
            bullet_len=len(bullet),
        )
        if fit_size is None:
            return False

        _write_lines_to_box(
            slide,
            f"AUTO_CONTENT_{slide_index}_REF_{i}",
            left,
            top,
            width,
            height,
            part,
            fit_size,
            bullet=bullet,
        )
    return True


def add_formal_layout_content_v2(
    slide,
    draft: SlideDraft,
    has_table: bool,
    title: str,
    theme: str,
    diversity: str,
    seed: int,
) -> bool:
    if not draft.bullets:
        return False

    if has_table:
        left, top, width, height = Inches(0.5), Inches(4.95), Inches(8.9), Inches(0.6)
        rows = draft.bullets[:2]
        _write_lines_to_box(
            slide,
            f"AUTO_CONTENT_{draft.slide_index}",
            left,
            top,
            width,
            height,
            rows,
            13,
            bullet="",
        )
        return True

    palette = get_theme_palette(theme)
    rows = draft.bullets[:5]

    add_visual_accent(slide, draft.slide_index, palette)
    font_size = suggest_font_size(rows, base=15)
    variant = choose_formal_variant(title, rows, diversity, seed, draft.slide_index)

    if variant == "two_column":
        render_two_column(slide, draft.slide_index, rows, font_size)
    elif variant == "timeline":
        render_timeline(slide, draft.slide_index, rows, font_size, palette)
    elif variant == "kpi_cards":
        render_kpi_cards(slide, draft.slide_index, rows, font_size, palette)
    elif variant == "risk_matrix":
        render_risk_matrix(slide, draft.slide_index, rows, font_size, palette)
    else:
        render_single_column(slide, draft.slide_index, rows, font_size)
    return False


def fill_table_metrics(slide, metrics: dict[str, str]) -> None:
    for shp in slide.shapes:
        if not getattr(shp, "has_table", False):
            continue
        table = shp.table
        for r in range(1, len(table.rows)):
            label = normalize_text(table.cell(r, 0).text)
            table.cell(r, 1).text = metrics.get(label, "-")


def convert(
    docx_path: Path,
    template_pptx: Path,
    output_pptx: Path,
    model: str,
    ollama_url: str,
    timeout_sec: int,
    retries: int,
    use_llm: bool,
    layout_mode: str = "classic",
    theme: str = "formal_blue",
    diversity: str = "medium",
    seed: int = 0,
) -> None:
    doc_payload = extract_doc_payload(docx_path)
    month_label = detect_month_label(doc_payload["title"], docx_path.name)
    log(f"识别月份: {month_label}")

    prs = Presentation(str(template_pptx))
    template_slides = extract_template_slides(prs)

    drafts, metrics = build_drafts_and_metrics(
        use_llm=use_llm,
        ollama_url=ollama_url,
        model=model,
        timeout_sec=timeout_sec,
        retries=retries,
        report_title=doc_payload["title"],
        month_label=month_label,
        template_slides=template_slides,
        doc_payload=doc_payload,
    )

    log("开始写入 PPT（保留模板标题与版式）")
    draft_map = {d.slide_index: d for d in drafts}
    for s in template_slides:
        slide = prs.slides[s.slide_index - 1]
        remove_auto_shapes(slide)
        if layout_mode == "formal":
            add_formal_layout_content_v2(
                slide=slide,
                draft=draft_map[s.slide_index],
                has_table=s.has_table,
                title=s.title,
                theme=theme,
                diversity=diversity,
                seed=seed,
            )
        else:
            add_content_textbox(slide, draft_map[s.slide_index], s.has_table)
        if s.has_table:
            fill_table_metrics(slide, metrics)
        log(f"已写入第 {s.slide_index} 页: {s.title}")

    output_pptx.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(output_pptx))
    log(f"导出完成: {output_pptx}")
