"""Rule tables used by report converter selection and cleanup logic.

Keeping domain terms here makes the scoring algorithms easier to read and gives future rule
tuning a single place to edit.
"""

from __future__ import annotations

from ..models import TitleProfile

SECTION_BUCKET_KEYWORDS: dict[str, list[str]] = {
    "overview": ["概述", "总体", "重大风险", "风险提示", "月报"],
    "data": ["用印", "一般文件", "法律文件", "集团制式", "申请提案统计", "调查统计", "数量", "累计", "基础运作流程"],
    "contracts": ["专案性工作", "合同", "协议", "MPA", "担保", "审核", "保证函", "框架协议", "补充协议"],
    "ip": ["知识产权", "专利", "商标", "337", "OA", "无效", "调查", "申请提案", "Discovery"],
    "litigation": ["诉讼个案", "仲裁", "诉讼", "开庭", "判决", "劳动争议", "被迫解除", "人事争议"],
    "compliance": ["合规", "风险项", "出口管制", "黑名单", "欠款", "社保", "政府项目", "排查"],
}

TITLE_SECTION_KEYWORDS: list[tuple[tuple[str, ...], list[str]]] = [
    (("概述",), ["概述", "总体", "重大风险", "风险提示"]),
    (("基础运作流程数据", "用印|专利"), ["用印", "一般文件", "法律文件", "申请提案统计", "调查统计"]),
    (("典型协议与合同管理",), ["专案性工作", "合同", "协议"]),
    (("知识产权",), ["知识产权专项", "知识产权", "IP", "专利申请提案统计", "专利调查统计", "商标事务", "337调查"]),
    (("国内仲裁与诉讼个案管理", "仲裁与诉讼"), ["诉讼个案", "仲裁", "诉讼", "人事争议"]),
    (("合规事务",), ["合规与风险项", "合规", "风险项"]),
]

TITLE_KEYWORDS: dict[str, list[str]] = {
    "概述": ["风险", "货款", "诉讼", "合规", "出口管制", "项目", "整改"],
    "基础运作流程数据": ["用印", "申请", "调查", "统计", "数量", "累计"],
    "典型协议与合同管理": ["协议", "合同", "框架", "补充", "审核", "专案"],
    "知识产权": ["专利", "商标", "调查", "337", "无效", "OA", "申请"],
    "仲裁与诉讼": ["仲裁", "诉讼", "开庭", "判决", "调解", "劳动"],
    "合规": ["合规", "排查", "出口", "黑名单", "风险", "整改"],
}

PREFERRED_HEADING_KEYWORDS: list[tuple[tuple[str, ...], list[str]]] = [
    (("概述",), ["概述"]),
    (("典型协议", "合同管理"), ["专案性工作"]),
    (("知识产权",), ["知识产权专项", "知识产权"]),
    (("仲裁", "诉讼"), ["诉讼个案"]),
    (("合规",), ["合规与风险项", "合规"]),
]

TITLE_PROFILES: list[tuple[tuple[str, ...], TitleProfile]] = [
    (("概述",), {"must_any": ["风险", "货款", "项目", "整改", "排查", "诉讼", "合规"], "avoid": ["用印", "申请提案统计", "调查统计"]}),
    (("基础运作流程数据", "用印|专利"), {"must_any": ["用印", "申请", "调查", "统计", "数量"], "avoid": ["风险", "诉讼", "整改"]}),
    (("典型协议", "合同管理"), {"must_any": ["协议", "合同", "审核", "框架", "补充", "专案"], "avoid": ["诉讼", "专利调查", "用印"]}),
    (("知识产权",), {"must_any": ["专利", "商标", "调查", "337", "OA", "无效", "申请提案"], "avoid": ["用印", "劳动争议"]}),
    (("仲裁", "诉讼"), {"must_any": ["仲裁", "诉讼", "开庭", "判决", "调解", "劳动争议"], "avoid": ["用印", "专利申请提案统计"]}),
    (("合规",), {"must_any": ["合规", "排查", "出口", "黑名单", "风险", "整改"], "avoid": ["用印", "专利申请提案统计"]}),
]

DATA_METRIC_KEYWORDS = ["用印", "一般文件", "法律文件", "集团制式", "申请提案", "专利调查", "统计", "数量", "件", "累计"]
DATA_METRIC_EXCLUDE_KEYWORDS = ["逾期货款", "风险", "整改", "诉讼", "劳动争议", "排查", "黑名单", "出口管制"]
SPECIFIC_SIGNAL_KEYWORDS = ["项目", "案件", "协议", "合同", "仲裁", "诉讼", "专利", "商标", "风险"]
GENERIC_PHRASES = ["持续推进", "稳步推进", "按计划开展", "有序进行", "完成相关工作", "跟进处理"]

TEXT_METRIC_PATTERNS = {
    "general_seal": r"一般文件数量为\s*([0-9,]+)",
    "legal_seal": r"法律文件数量为\s*([0-9,]+)",
    "patent_apply": r"(?:申请提案总数|专利申请提案统计[：:]?)\s*([0-9,]+)\s*件",
    "patent_survey": r"(?:专利调查统计[：:]?\s*(?:总计)?|调查统计[：:]?)\s*([0-9,]+)\s*件",
}

OCR_METRIC_PATTERNS = {
    "patent_apply": [
        r"(?:专利)?申请(?:提案)?(?:统计)?[^0-9]{0,20}([0-9]{1,4})\s*件",
        r"([0-9]{1,4})\s*件[^。；\n]{0,20}(?:申请|提案)",
    ],
    "patent_survey": [
        r"(?:专利)?调查(?:统计)?[^0-9]{0,20}([0-9]{1,4})\s*件",
        r"([0-9]{1,4})\s*件[^。；\n]{0,20}(?:调查)",
    ],
}

BU_APPLY_CODE = "ZLSQ-TECH-"
BU_SURVEY_CODE = "ZLDC-TECH-"


def title_has(title: str, markers: tuple[str, ...]) -> bool:
    for marker in markers:
        if "|" in marker:
            parts = marker.split("|")
            if all(part in title for part in parts):
                return True
        elif marker in title:
            return True
    return False
