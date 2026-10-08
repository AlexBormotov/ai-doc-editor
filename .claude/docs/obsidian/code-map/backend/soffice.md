---
title: src/ai_doc_editor/soffice.py
tags:
  - code-map
  - backend
---

# `src/ai_doc_editor/soffice.py`

Section: [[Backend]]

## Purpose

LibreOffice headless wrapper: locate `soffice` and convert files.

## Classes

### `SofficeError` (RuntimeError)

LibreOffice missing or a conversion failed.


## Functions

- `def find_soffice() -> str | None` — Return the soffice executable path, or None if LibreOffice is not installed.
- `def convert(src: Path, target_ext: str, out_dir: Path, timeout: int=300) -> Path` — Convert `src` to `target_ext` ("pdf", "docx", "doc") into `out_dir`; return the new path.
