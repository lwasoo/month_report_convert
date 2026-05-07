"""Regression tests for fuzzy mapping, prompt, and placeholder repair behavior.

The implementation is split across narrower modules, but these tests intentionally keep using
the compatibility facade to protect older GUI and CLI imports.
"""

from __future__ import annotations

import json
import unittest

from doc_sanitizer.fuzzy_mapping import (
    build_external_ai_prompt_sections,
    closest_placeholder_for_token,
    find_placeholder_like_tokens,
    payload_from_json_text,
    placeholder_token_category,
    suggest_placeholder_repairs,
    unresolved_placeholder_tokens,
)
from doc_sanitizer.mapping import mapping_entries


class MappingAndPromptTests(unittest.TestCase):
    """Protect AI-facing prompt safety and placeholder repair scoring rules."""

    def test_prompt_copy_section_excludes_sensitive_originals(self) -> None:
        # 通过用例：外部 AI 可复制区只能包含占位符，不能泄露原始敏感词。
        # 内部审核区可以保留原始名称线索，供用户自己判断归组是否合理。
        payload = payload_from_json_text(
            json.dumps(
                {
                    "entries": [
                        {
                            "placeholder": "__COMPANY_001__",
                            "original": "Acme",
                            "category": "COMPANY",
                            "enabled": True,
                        },
                        {
                            "placeholder": "__COMPANY_002__",
                            "original": "Acme Technology Co Ltd",
                            "category": "COMPANY",
                            "enabled": True,
                        },
                    ]
                },
                ensure_ascii=False,
            )
        )

        prompt, audit = build_external_ai_prompt_sections(payload)

        self.assertIn("__COMPANY_002__ / __COMPANY_001__", prompt)
        self.assertIn("不得新增", prompt)
        self.assertNotIn("PROJECT_015", prompt)
        self.assertNotIn("Acme", prompt)
        self.assertNotIn("映射摘要", prompt)
        self.assertNotIn("人工确认", prompt)
        self.assertIn("Acme Technology Co Ltd", audit)

    def test_placeholder_repair_scores_split_auto_and_confirmation_cases(self) -> None:
        # 通过用例：轻微损坏的占位符应进入高置信自动修复；
        # 缺字/编号简写这类更可疑的写法只进入“需要用户确认”的分数段。
        payload = payload_from_json_text(
            json.dumps(
                {
                    "entries": [
                        {
                            "placeholder": "__COMPANY_001__",
                            "original": "Acme",
                            "category": "COMPANY",
                            "enabled": True,
                        }
                    ]
                },
                ensure_ascii=False,
            )
        )

        repairs = suggest_placeholder_repairs("Keep COMPANY_001 and maybe COMY_01.", mapping_entries(payload), min_score=0.70)
        scores = {repair.token: repair.score for repair in repairs}

        self.assertGreaterEqual(scores["COMPANY_001"], 0.90)
        self.assertGreaterEqual(scores["COMY_01"], 0.70)
        self.assertLess(scores["COMY_01"], 0.90)

    def test_placeholder_repair_prefers_matching_index_over_category_similarity(self) -> None:
        # 失败用例：历史问题是前缀很像时会把编号不同的占位符误配过去。
        # 这里要求编号优先：MPANY_007 应配 __COMPANY_007__，不能配 __COMPANY_001__。
        payload = payload_from_json_text(
            json.dumps(
                {
                    "entries": [
                        {
                            "placeholder": "__COMPANY_001__",
                            "original": "Acme",
                            "category": "COMPANY",
                            "enabled": True,
                        },
                        {
                            "placeholder": "__COMPANY_007__",
                            "original": "Example Holdings",
                            "category": "COMPANY",
                            "enabled": True,
                        },
                    ]
                },
                ensure_ascii=False,
            )
        )

        repairs = suggest_placeholder_repairs("MPANY_007", mapping_entries(payload), min_score=0.70)
        self.assertEqual(repairs[0].canonical, "__COMPANY_007__")
        self.assertGreaterEqual(repairs[0].score, 0.90)

    def test_placeholder_repair_rejects_different_index_with_same_category(self) -> None:
        # 失败用例：PROJECT_015 不能因为类别相同就被猜成 __PROJECT_005__。
        payload = payload_from_json_text(
            json.dumps(
                {
                    "entries": [
                        {
                            "placeholder": "__PROJECT_005__",
                            "original": "Project A",
                            "category": "PROJECT",
                            "enabled": True,
                        }
                    ]
                },
                ensure_ascii=False,
            )
        )

        repairs = suggest_placeholder_repairs("PROJECT_015", mapping_entries(payload), min_score=0.70)
        self.assertEqual(repairs, [])

    def test_placeholder_repair_confirms_extra_digit_but_does_not_auto_accept(self) -> None:
        # 失败/边界用例：_CODE_0077_ 和 __CODE_007__ 很像，但编号多了一位，
        # 应进入确认分数段，而不是自动修复。
        payload = payload_from_json_text(
            json.dumps(
                {
                    "entries": [
                        {
                            "placeholder": "__CODE_007__",
                            "original": "BU11",
                            "category": "CODE",
                            "enabled": True,
                        }
                    ]
                },
                ensure_ascii=False,
            )
        )

        repairs = suggest_placeholder_repairs("_CODE_0077_", mapping_entries(payload), min_score=0.70)
        self.assertEqual(repairs[0].canonical, "__CODE_007__")
        self.assertGreaterEqual(repairs[0].score, 0.70)
        self.assertLess(repairs[0].score, 0.90)

    def test_unresolved_placeholder_tokens_report_unknown_ai_ids(self) -> None:
        # 失败用例：外部 AI 可能生成映射表不存在的新编号；不能静默显示还原完成。
        payload = payload_from_json_text(
            json.dumps(
                {
                    "entries": [
                        {
                            "placeholder": "__CODE_007__",
                            "original": "BU11-1件",
                            "category": "CODE",
                            "enabled": True,
                        }
                    ]
                },
                ensure_ascii=False,
            )
        )

        tokens = unresolved_placeholder_tokens(
            "已还原 BU11-1件，但 _CODE_008_ 和 __SUPPLIER_004T__ 仍残留。",
            mapping_entries(payload),
        )

        self.assertEqual(tokens, ["_CODE_008_", "__SUPPLIER_004T__"])
        self.assertEqual(placeholder_token_category("__SUPPLIER_004T__"), "SUPPLIER")

    def test_unknown_placeholder_prefills_closest_numbered_candidate(self) -> None:
        # 通过用例：未知占位符也应先按类别和编号靠近程度给出预填建议。
        payload = payload_from_json_text(
            json.dumps(
                {
                    "entries": [
                        {
                            "placeholder": "__SUPPLIER_001__",
                            "original": "AmpLink",
                            "category": "SUPPLIER",
                            "enabled": True,
                        },
                        {
                            "placeholder": "__SUPPLIER_003__",
                            "original": "苏州立讯技术",
                            "category": "SUPPLIER",
                            "enabled": True,
                        },
                    ]
                },
                ensure_ascii=False,
            )
        )

        placeholder, score = closest_placeholder_for_token("__SUPPLIER_003T__", mapping_entries(payload), min_score=0.65)

        self.assertEqual(placeholder, "__SUPPLIER_003__")
        self.assertGreaterEqual(score, 0.90)

    def test_broken_placeholder_tail_is_detected_inside_joined_text(self) -> None:
        # 失败用例：外部 AI 可能把 __COMPANY_007__ 改成 QuantaMPANY_007 这种粘连残片。
        tokens = find_placeholder_like_tokens("客户CM厂QuantaMPANY_007")

        self.assertIn("MPANY_007", tokens)

    def test_repair_does_not_partially_replace_embedded_placeholder(self) -> None:
        # 失败用例：不能先把 __SUPPLIER_003T__ 的子串 __SUPPLIER_003 替换掉，
        # 否则会产生 __SUPPLIER_003__T__ 这种更坏的残留。
        payload = payload_from_json_text(
            json.dumps(
                {
                    "entries": [
                        {
                            "placeholder": "__SUPPLIER_003__",
                            "original": "苏州立讯技术",
                            "category": "SUPPLIER",
                            "enabled": True,
                        }
                    ]
                },
                ensure_ascii=False,
            )
        )

        repairs = suggest_placeholder_repairs("供应商 __SUPPLIER_003T__ 已签约", mapping_entries(payload), min_score=0.70)

        self.assertEqual(repairs, [])

    def test_repair_still_handles_placeholder_next_to_chinese_text(self) -> None:
        # 通过用例：中文前后缀不算英文粘连，仍应识别 _CODE_007_ 这类轻微损坏占位符。
        payload = payload_from_json_text(
            json.dumps(
                {
                    "entries": [
                        {
                            "placeholder": "__CODE_007__",
                            "original": "BU11-1件",
                            "category": "CODE",
                            "enabled": True,
                        }
                    ]
                },
                ensure_ascii=False,
            )
        )

        repairs = suggest_placeholder_repairs("其中_CODE_007_类", mapping_entries(payload), min_score=0.70)

        self.assertEqual(repairs[0].canonical, "__CODE_007__")

    def test_invalid_mapping_json_is_rejected(self) -> None:
        # 失败用例：外部输入不是映射对象时应直接报错，避免生成误导性的 Prompt。
        with self.assertRaises(ValueError):
            payload_from_json_text(json.dumps(["not", "a", "mapping"]))

        # 失败用例：JSON 结构存在但没有任何有效 entries/replacements，也应报错。
        with self.assertRaises(ValueError):
            payload_from_json_text(json.dumps({"entries": []}))

    def test_very_weak_placeholder_match_is_not_suggested(self) -> None:
        # 失败用例：太不像的 token 不应被猜测成某个占位符，避免错误还原。
        payload = payload_from_json_text(
            json.dumps(
                {
                    "entries": [
                        {
                            "placeholder": "__COMPANY_001__",
                            "original": "Acme",
                            "category": "COMPANY",
                            "enabled": True,
                        }
                    ]
                },
                ensure_ascii=False,
            )
        )

        repairs = suggest_placeholder_repairs("This token ABC_99 should not match.", mapping_entries(payload), min_score=0.70)
        self.assertEqual(repairs, [])


if __name__ == "__main__":
    unittest.main()
