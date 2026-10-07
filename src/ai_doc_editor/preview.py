"""Page images for the before/after preview in the UI."""

from __future__ import annotations

from pathlib import Path

import pymupdf

from ai_doc_editor.soffice import SofficeError, convert, find_soffice


def render_pages(
    doc: Path, out_dir: Path, tag: str, max_pages: int = 4, dpi: int = 80
) -> list[Path]:
    """PNG files of the first pages of a PDF or DOCX (DOCX is rendered by LibreOffice)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = doc
    if doc.suffix.lower() in (".docx", ".doc"):
        if find_soffice() is None:
            return []
        try:
            pdf = convert(doc, "pdf", out_dir / f"render-{tag}")
        except SofficeError:
            return []
    images = []
    with pymupdf.open(str(pdf)) as d:
        for i, page in enumerate(d):
            if i >= max_pages:
                break
            path = out_dir / f"{tag}-{i + 1}.png"
            page.get_pixmap(dpi=dpi).save(str(path))
            images.append(path)
    return images
