"""High-level Word-to-PPT conversion pipeline."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from pptx import Presentation

from office_conversion import convert_from_ooxml, convert_to_ooxml
from .common import log
from .ppt.content_regions import add_content_textbox
from .drafting import build_drafts_and_metrics
from .ppt.formal_layout import add_formal_layout_content_v2
from .models import Metrics, SlideDraft, TemplateSlide
from .ppt.pagination import split_into_pages
from .parsing import detect_month_label, extract_doc_payload
from .ppt.slide_ops import extract_template_slides, insert_slide_after, remove_auto_shapes, set_slide_title_text
from .ppt.table_fill import fill_table_metrics


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
    if _needs_legacy_conversion(docx_path, template_pptx, output_pptx):
        _convert_legacy_inputs(
            docx_path=docx_path,
            template_pptx=template_pptx,
            output_pptx=output_pptx,
            model=model,
            ollama_url=ollama_url,
            timeout_sec=timeout_sec,
            retries=retries,
            use_llm=use_llm,
            layout_mode=layout_mode,
            theme=theme,
            diversity=diversity,
            seed=seed,
        )
        return

    doc_payload = extract_doc_payload(docx_path)
    month_label = detect_month_label(doc_payload.title, docx_path.name)
    log(f"报告月份: {month_label}")

    prs = Presentation(str(template_pptx))
    template_slides = extract_template_slides(prs)
    drafts, metrics = build_drafts_and_metrics(
        use_llm=use_llm,
        ollama_url=ollama_url,
        model=model,
        timeout_sec=timeout_sec,
        retries=retries,
        report_title=doc_payload.title,
        month_label=month_label,
        template_slides=template_slides,
        doc_payload=doc_payload,
    )

    _render_drafts_to_presentation(
        prs=prs,
        template_slides=template_slides,
        drafts=drafts,
        metrics=metrics,
        layout_mode=layout_mode,
        theme=theme,
        diversity=diversity,
        seed=seed,
    )
    output_pptx.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(output_pptx))
    log(f"输出文件: {output_pptx}")


def _needs_legacy_conversion(docx_path: Path, template_pptx: Path, output_pptx: Path) -> bool:
    return docx_path.suffix.lower() == ".doc" or template_pptx.suffix.lower() == ".ppt" or output_pptx.suffix.lower() == ".ppt"


def _convert_legacy_inputs(
    docx_path: Path,
    template_pptx: Path,
    output_pptx: Path,
    model: str,
    ollama_url: str,
    timeout_sec: int,
    retries: int,
    use_llm: bool,
    layout_mode: str,
    theme: str,
    diversity: str,
    seed: int,
) -> None:
    with TemporaryDirectory() as td:
        work_dir = Path(td)
        converted_docx = convert_to_ooxml(docx_path, work_dir)
        converted_template = convert_to_ooxml(template_pptx, work_dir)
        temp_output = work_dir / f"{output_pptx.stem}.pptx"
        convert(
            docx_path=converted_docx,
            template_pptx=converted_template,
            output_pptx=temp_output,
            model=model,
            ollama_url=ollama_url,
            timeout_sec=timeout_sec,
            retries=retries,
            use_llm=use_llm,
            layout_mode=layout_mode,
            theme=theme,
            diversity=diversity,
            seed=seed,
        )
        convert_from_ooxml(temp_output, output_pptx)


def _render_drafts_to_presentation(
    prs: Presentation,
    template_slides: list[TemplateSlide],
    drafts: list[SlideDraft],
    metrics: Metrics,
    layout_mode: str,
    theme: str,
    diversity: str,
    seed: int,
) -> None:
    log("开始生成 PPT 内容...")
    draft_map = {draft.slide_index: draft for draft in drafts}
    offset = 0

    for slide_meta in template_slides:
        slide_pos = slide_meta.slide_index - 1 + offset
        slide = prs.slides[slide_pos]
        remove_auto_shapes(slide)
        all_bullets = draft_map[slide_meta.slide_index].bullets
        pages = split_into_pages(all_bullets, slide_meta.title, has_table=slide_meta.has_table)
        first_chunk = pages[0] if pages else []
        first_draft = SlideDraft(slide_meta.slide_index, first_chunk)

        _render_single_slide_chunk(
            prs=prs,
            slide=slide,
            draft=first_draft,
            title=slide_meta.title,
            has_table=slide_meta.has_table,
            layout_mode=layout_mode,
            theme=theme,
            diversity=diversity,
            seed=seed,
        )
        if slide_meta.has_table:
            fill_table_metrics(slide, metrics)
        log(f"已生成第 {slide_meta.slide_index} 页: {slide_meta.title}")

        for n, chunk in enumerate(pages[1:], start=1):
            overflow = insert_slide_after(prs, slide_pos + n - 1, slide.slide_layout)
            set_slide_title_text(overflow, slide_meta.title)
            remove_auto_shapes(overflow)
            overflow_draft = SlideDraft(slide_meta.slide_index, chunk)
            _render_single_slide_chunk(
                prs=prs,
                slide=overflow,
                draft=overflow_draft,
                title=slide_meta.title,
                has_table=False,
                layout_mode=layout_mode,
                theme=theme,
                diversity=diversity,
                seed=seed + n,
            )
            log(f"已生成溢出页: {slide_meta.title} 第 {n} 页")

        offset += max(len(pages) - 1, 0)


def _render_single_slide_chunk(
    prs: Presentation,
    slide,
    draft: SlideDraft,
    title: str,
    has_table: bool,
    layout_mode: str,
    theme: str,
    diversity: str,
    seed: int,
) -> None:
    if layout_mode == "formal":
        add_formal_layout_content_v2(
            slide=slide,
            draft=draft,
            has_table=has_table,
            title=title,
            theme=theme,
            diversity=diversity,
            seed=seed,
            slide_width=int(prs.slide_width),
            slide_height=int(prs.slide_height),
        )
    else:
        add_content_textbox(slide, draft, has_table, int(prs.slide_width), int(prs.slide_height))
