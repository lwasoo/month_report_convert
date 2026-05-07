"""Ollama JSON client and prompt construction for report drafting."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from ..common import log
from ..models import LLMJson, SelectedSources, TemplateSlide


def extract_json_object(text: str) -> str:
    payload = text.strip()
    if payload.startswith("{") and payload.endswith("}"):
        return payload
    m = re.search(r"\{[\s\S]*\}", payload)
    if m:
        return m.group(0)
    raise ValueError("LLM 返回中未找到 JSON。")


def call_ollama_json(ollama_url: str, model: str, prompt: str, timeout_sec: int, retries: int) -> LLMJson:
    system_prompt = (
        "你是企业法务月报编辑。"
        "输出只能是严格 JSON。"
        "要写成 PPT 汇报语言，但必须保留关键细节：BU、项目名、案件名、日期、数字。"
    )
    endpoints = [
        ("chat", f"{ollama_url.rstrip('/')}/api/chat"),
        ("generate", f"{ollama_url.rstrip('/')}/api/generate"),
    ]
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        for kind, url in endpoints:
            try:
                log(f"调用 Ollama ({kind}) 第 {attempt} 次: {url}")
                if kind == "chat":
                    body = json.dumps(
                        {
                            "model": model,
                            "format": "json",
                            "stream": False,
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": prompt},
                            ],
                        }
                    ).encode("utf-8")
                else:
                    body = json.dumps(
                        {
                            "model": model,
                            "format": "json",
                            "stream": False,
                            "prompt": f"{system_prompt}\n\n{prompt}",
                        }
                    ).encode("utf-8")
                req = urllib.request.Request(url=url, data=body, headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                text = payload.get("message", {}).get("content", "") if kind == "chat" else payload.get("response", "")
                return json.loads(extract_json_object(text))
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
                last_error = exc
                log(f"Ollama 调用失败: {exc}", level="WARN")
                continue
    if last_error is None:
        raise RuntimeError("Ollama 调用失败。")
    raise RuntimeError(f"Ollama 调用失败: {last_error}") from last_error


def build_rewrite_prompt(
    report_title: str,
    month_label: str,
    template_slides: list[TemplateSlide],
    selected_sources: SelectedSources,
) -> str:
    blocks: list[str] = []
    for slide in template_slides:
        blocks.append(f"## slide_index={slide.slide_index} | 标题={slide.title}")
        for line in selected_sources.get(slide.slide_index, []):
            blocks.append(f"- {line}")
    source_block = "\n".join(blocks)
    return f"""将素材改写成 PPT 月报要点。

【报告】{report_title}
【月份】{month_label}

【规则】
1. 标题固定，不改标题。
2. 用汇报语气，保留细节：BU、项目、案件、日期、数字。
3. 可缩写，但不得截断句子；不得丢失关键细节。
4. 优先多保留有效 point，单页放不下也继续输出，由程序自动续页。
5. 不要省略号，不要口号句，不要泛化总结。
6. 只输出 JSON。

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


