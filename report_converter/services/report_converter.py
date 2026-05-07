"""Object-oriented entry point for Word-to-PPT report conversion."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ..engine import convert


@dataclass
class ReportConverter:
    """Coordinate Word report conversion into a PowerPoint deck."""

    model: str
    ollama_url: str
    timeout_sec: int
    retries: int
    use_llm: bool
    layout_mode: str = "classic"
    theme: str = "formal_blue"
    diversity: str = "medium"
    seed: int = 0

    def convert(self, docx_path: Path, template_pptx: Path, output_pptx: Path) -> None:
        convert(
            docx_path=docx_path,
            template_pptx=template_pptx,
            output_pptx=output_pptx,
            model=self.model,
            ollama_url=self.ollama_url,
            timeout_sec=self.timeout_sec,
            retries=self.retries,
            use_llm=self.use_llm,
            layout_mode=self.layout_mode,
            theme=self.theme,
            diversity=self.diversity,
            seed=self.seed,
        )
