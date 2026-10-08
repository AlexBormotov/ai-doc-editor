---
title: src/ai_doc_editor/presets.py
tags:
  - code-map
  - backend
---

# `src/ai_doc_editor/presets.py`

Section: [[Backend]]

## Purpose

Named instruction templates. A user instruction, if given, is appended to the preset.

## Functions

- `def build_instruction(preset: str | None, instruction: str | None) -> str` — Preset text plus the user's instruction; error if both are empty.
