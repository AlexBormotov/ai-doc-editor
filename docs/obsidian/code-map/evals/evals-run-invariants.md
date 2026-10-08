---
title: evals/run_invariants.py
tags:
  - code-map
  - evals
---

# `evals/run_invariants.py`

Section: [[Evals]]

## Purpose

Deterministic eval: every fixture through the full pipeline with a scripted provider.

## Functions

- `def main() -> int` — Runs every fixture (tracked and direct for Word) with the scripted provider; prints a table, exit 1 on any failure.

## Related

- [[editor]]
- [[llm-scripted]]
- [[models]]
- [[soffice]]
