from dataclasses import dataclass


@dataclass
class TemplateSlide:
    slide_index: int
    title: str
    has_table: bool


@dataclass
class SlideDraft:
    slide_index: int
    bullets: list[str]
