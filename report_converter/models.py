"""Small data models shared by report conversion stages."""

from dataclasses import dataclass, field
from typing import Any, TypedDict


@dataclass
class TemplateSlide:
    slide_index: int
    title: str
    has_table: bool


@dataclass
class SlideDraft:
    slide_index: int
    bullets: list[str]


@dataclass
class ReportParagraph:
    text: str
    style: str = ""
    has_drawing: bool = False
    image_blobs: list[bytes] = field(default_factory=list)


@dataclass
class ReportSection:
    heading: str
    items: list[str] = field(default_factory=list)
    image_count: int = 0
    images: list[bytes] = field(default_factory=list)
    ocr_text: str = ""


@dataclass
class ParsedReport:
    title: str
    paragraphs: list[ReportParagraph]
    sections: list[ReportSection]


class TitleProfile(TypedDict):
    must_any: list[str]
    avoid: list[str]


Metrics = dict[str, str]
SelectedSources = dict[int, list[str]]
LLMJson = dict[str, Any]
