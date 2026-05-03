from __future__ import annotations

import unittest

from doc_sanitizer.llm_assist import (
    build_llm_candidate_contexts,
    chunk_texts_for_llm,
    count_texts_with_existing_terms,
    select_texts_for_llm,
    stable_text_hash,
)


class LlmAssistPerformanceTests(unittest.TestCase):
    def test_llm_text_selection_filters_low_signal_texts_and_caps_chunks(self) -> None:
        # 性能回归用例：全文 XML 扫描会带来很多低价值碎片，
        # 这些碎片不应全部送给 Ollama，避免模型调用次数暴涨。
        texts = [f"普通说明文字 {idx}" for idx in range(120)]
        texts.extend(
            [
                "客户：Acme Technology Co Ltd",
                "项目：Project Phoenix",
                "合同编号：TECH-2026-001",
            ]
        )

        selected = select_texts_for_llm(texts, max_texts=20)
        chunks = chunk_texts_for_llm(selected, max_chars=30, max_items=2, max_chunks=3)

        self.assertLess(len(selected), len(texts))
        self.assertIn("客户：Acme Technology Co Ltd", selected)
        self.assertLessEqual(len(chunks), 3)

    def test_llm_candidate_contexts_skip_existing_mapping_terms(self) -> None:
        # 性能/精度用例：已有映射中的原词不需要再次交给模型判断；
        # 模型只审核规则候选和上下文，减少重复调用。
        texts = [
            "客户 Acme Technology Co Ltd 与 Project Phoenix 沟通。",
            "客户 Acme Technology Co Ltd 与 Project Phoenix 沟通。",
        ]
        rule_candidates = [
            ("COMPANY", "Acme Technology Co Ltd", "auto"),
            ("PROJECT", "Project Phoenix", "auto"),
        ]

        contexts = build_llm_candidate_contexts(texts, rule_candidates, existing_terms={"Acme Technology Co Ltd"})

        self.assertEqual(len(contexts), 1)
        self.assertNotIn("Acme Technology Co Ltd", contexts[0].split("\n", 1)[0])
        self.assertIn("Project Phoenix", contexts[0])
        self.assertEqual(stable_text_hash(contexts[0]), stable_text_hash(contexts[0]))

    def test_llm_text_selection_keeps_free_extraction_for_new_entities(self) -> None:
        # 精度回归用例：初筛必须保留原文自由抽取能力；
        # 规则没抓到的新实体仍应能进入模型输入。
        selected = select_texts_for_llm(["新出现的 Alpha Beta Legal 需要模型自由识别。"], max_texts=10)

        self.assertIn("新出现的 Alpha Beta Legal 需要模型自由识别。", selected)

    def test_existing_mapping_terms_are_counted_for_gui_logging(self) -> None:
        # GUI 日志用例：继续识别时应能看到已有映射排除了多少相关段落。
        count = count_texts_with_existing_terms(
            ["Acme 已在映射里。", "Project Phoenix 是新项目。", "Acme 再次出现。"],
            {"Acme"},
        )

        self.assertEqual(count, 2)


if __name__ == "__main__":
    unittest.main()
