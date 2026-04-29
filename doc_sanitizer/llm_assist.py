from __future__ import annotations

import json
import re
from typing import Any
import urllib.error
import urllib.request

from report_converter.common import log, normalize_text
from .patterns import clean_candidate_value, is_valid_candidate

def collect_llm_candidates(
    texts: list[str],
    model: str,
    ollama_url: str,
    timeout_sec: int,
    retries: int,
) -> list[tuple[str, str, str]]:
    chunks = chunk_texts_for_llm(texts, max_chars=1800, max_items=16)
    candidates: list[tuple[str, str, str]] = []
    for idx, chunk in enumerate(chunks, start=1):
        log(f"AI 辅助识别分段 {idx}/{len(chunks)}")
        payload = call_ollama_candidate_json(
            ollama_url=ollama_url,
            model=model,
            prompt=build_llm_candidate_prompt(chunk),
            timeout_sec=timeout_sec,
            retries=retries,
        )
        for row in payload.get("candidates", []):
            if not isinstance(row, dict):
                continue
            category = normalize_text(str(row.get("category", "")).upper()) or "MANUAL"
            original = clean_candidate_value(normalize_text(str(row.get("text", ""))), category)
            if is_valid_candidate(original, category):
                candidates.append((category, original, "llm"))
    deduped: dict[str, tuple[str, str]] = {}
    for category, value, source in sorted(candidates, key=lambda item: len(item[1]), reverse=True):
        deduped.setdefault(normalize_text(value), (category, source))
    return [(category, original, source) for original, (category, source) in deduped.items()]

def chunk_texts_for_llm(texts: list[str], max_chars: int = 1800, max_items: int = 16) -> list[list[str]]:
    chunks: list[list[str]] = []
    current: list[str] = []
    current_len = 0
    for text in texts:
        line = normalize_text(text)
        if not line:
            continue
        line_len = len(line) + 1
        if current and (current_len + line_len > max_chars or len(current) >= max_items):
            chunks.append(current)
            current = []
            current_len = 0
        current.append(line)
        current_len += line_len
    if current:
        chunks.append(current)
    return chunks[:12]

def build_llm_candidate_prompt(chunk: list[str]) -> str:
    numbered = "\n".join(f"{idx + 1}. {line}" for idx, line in enumerate(chunk))
    return f"""请从下面文本中识别需要脱敏的敏感实体，并输出严格 JSON。

规则：
1. 只抽取文本中真实出现的原文，不改写，不杜撰。
2. 优先识别：公司主体、英文公司名、律所、人名、项目名、案号、合同编号、客户、供应商、代码、标题。
3. 只返回短实体，不要返回整句描述。
4. 如果不确定，不要返回。
5. category 只能是：COMPANY、PERSON、PROJECT、CASE、CODE、CUSTOMER、SUPPLIER、TITLE。
6. 像 Baker Botts、TransPerfect Legal、贝克博茨律所 这类律所或英文机构，也按 COMPANY 返回。
7. 不要把通用法律或合同术语当作敏感实体，例如 Effective Date、Commitment Period、State of Delaware、Memorandum of Understanding。
8. 纯数字、常见法务短语、州名/地名如果没有明确敏感含义，不要返回。

输出格式：
{{"candidates":[{{"text":"<原文中的敏感实体>","category":"COMPANY"}}]}}

注意：
1. 上面只是格式示意，不是候选内容。
2. 绝对不要返回示例词、占位符或你自己编造的实体。

待识别文本：
{numbered}
"""

def extract_json_object(text: str) -> str:
    payload = text.strip()
    if payload.startswith("{") and payload.endswith("}"):
        return payload
    match = re.search(r"\{[\s\S]*\}", payload)
    if match:
        return match.group(0)
    raise ValueError("LLM 返回中未找到 JSON。")

def call_ollama_candidate_json(
    ollama_url: str,
    model: str,
    prompt: str,
    timeout_sec: int,
    retries: int,
) -> dict[str, Any]:
    system_prompt = "你是企业文档脱敏助手。只能输出严格 JSON，只抽取明确敏感实体，禁止返回整句。"
    endpoints = [
        ("chat", f"{ollama_url.rstrip('/')}/api/chat"),
        ("generate", f"{ollama_url.rstrip('/')}/api/generate"),
    ]
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        for kind, url in endpoints:
            try:
                log(f"调用 Ollama 脱敏辅助 ({kind}) 第 {attempt} 次: {url}")
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
                log(f"Ollama 脱敏辅助失败: {exc}", level="WARN")
                continue
    if last_error is None:
        raise RuntimeError("Ollama 脱敏辅助失败。")
    raise RuntimeError(f"Ollama 脱敏辅助失败: {last_error}") from last_error

