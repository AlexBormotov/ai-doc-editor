---
title: evals/run_models.py
tags:
  - code-map
  - evals
---

# `evals/run_models.py`

Section: [[Evals]]

## Purpose

Measure real models on evals/tasks.yaml.

## Functions

- `def output_text(path: Path) -> str` — Plain text of an output document (PDF pages or DOCX segments).
- `def run_checks(text: str, changed: int, checks: dict) -> list[str]` — Deterministic task checks: absent/present strings, regexes, Cyrillic ratio, min/max changed segments.
- `def eval_model(provider_key: str, model: str, tasks: list[dict]) -> dict` — Runs all tasks with one provider/model and summarises pass rate, invalid JSON, invented IDs, time.
- `def write_summary() -> None` — Writes `evals/results/summary.md` from all result files.
- `def main() -> int` — CLI: one `--model` per `--provider`, optional `--task` filter.

## Related

- [[docx-reader]]
- [[editor]]
- [[llm-base]]
- [[llm-registry]]
- [[models]]
- [[presets]]
