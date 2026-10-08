---
title: src/ai_doc_editor/cli.py
tags:
  - code-map
  - backend
---

# `src/ai_doc_editor/cli.py`

Section: [[Backend]]

## Purpose

Command line: `ai-doc-editor edit FILE -i "..."` and `ai-doc-editor providers`.

## Functions

- `def _edit(args: argparse.Namespace) -> int` — `edit` subcommand: builds instruction and provider, runs `edit_document`, prints output, scope, gate and structure check; exit 2 on violations.
- `def _providers(_: argparse.Namespace) -> int` — `providers` subcommand: lists every provider key with its models.
- `def main(argv: list[str] | None=None) -> int` — Argparse entry point of the `ai-doc-editor` console script.

## Related

- [[editor]]
- [[llm-registry]]
- [[models]]
- [[presets]]
- [[settings]]
