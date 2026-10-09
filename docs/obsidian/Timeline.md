---
title: Timeline
tags:
  - timeline
  - log
---

# Timeline — work log

Hub: [[INDEX]]. Newest entries on top, format: `YYYY-MM-DD HH:MM — what was done`.

<!-- NEW-ENTRIES-BELOW: add each new entry on the line right after this marker (newest on top). Replacing only this marker line keeps the edit cheap — the rest of the file is not rewritten. -->
- 2026-10-09 16:01 — Owner reorganised the markdown files: `intent.md`, `spec.md`, `plan.md` moved to `docs/`, `DESCRIPTION.md` removed (README supersedes it), private notes moved to the ignored `.claude/docs/`. Path references updated in `AGENTS.md`, README, [[INDEX]] and [[Planning]].
- 2026-10-08 16:36 — Vault moved from `.claude/docs/obsidian/` to `docs/obsidian/`; hooks point at the new path (`DOCS="docs/obsidian"`), and the track hook now normalises Windows slashes and ignores edits inside the vault so documenting does not re-trigger itself.

- 2026-10-08 15:40 — Documentation system set up: Obsidian vault in `docs/obsidian/` with code map for every source file, sections [[Backend]], [[Frontend]], [[Evals]], [[Planning]], and the obsidian-hooks (SessionStart / PostToolUse / Stop).
- 2026-10-07 08:42 — README: Russian contract screenshot removed; repository made public.
- 2026-10-07 08:38 — README: example of the Changes tab (word-level diff).
- 2026-10-07 08:26 — README example with a UI screenshot (local qwen3.5:9b rewrites the first paragraph of a real PDF); Changes tab made dark in the UI ([[ui]]).
- 2026-10-07 07:42 — PDF section reflow: an edited paragraph may change its line count, paragraphs below it in the same section move, the next heading never moves ([[pdf-writer]], [[invariants]]).
- 2026-10-07 07:27 — Renamed `ai-doc-reader` → `ai-doc-editor` (repository, package, CLI, UI, tracked-change author).
- 2026-10-07 06:29 — Fix after owner testing: PDF paragraphs across one-line blocks ([[pdf-reader]]), emptied segments rejected, scope step for targeted instructions ([[editor]], [[llm-prompts]]).
- 2026-10-07 05:22 — PDF→DOCX gate test requires the Cambria font (CI on Linux has a substitute).
- 2026-10-07 05:15 — Measured `gemma4:12b` after the owner updated Ollama to 0.40.0.
- 2026-10-07 04:43 — Plan step 11: README with measured results; AC trace in `plan.md`; Docker build fix.
- 2026-10-07 04:34 — Plan step 10: model evals with deterministic task checks ([[evals-run-models]]); invariant aligned with the word-level diff.
- 2026-10-07 04:19 — Plan step 9: HTTP API ([[api]]), Gradio UI ([[ui]]), Docker image and compose, host CLI bridge ([[scripts-cli-bridge]]).
- 2026-10-07 04:06 — Plan step 8: format conversion behind the layout gate ([[convert]]).
- 2026-10-07 04:03 — Plan step 7: orchestration ([[editor]]), presets, change report, CLI, invariant eval.
- 2026-10-07 03:57 — Plan step 6: LLM providers ([[llm-base]], [[llm-openai-compatible]], [[llm-anthropic-provider]], [[llm-cli-provider]], [[llm-scripted]]); invariants hardened after a security review.
- 2026-10-07 03:45 — Plan steps 4–5: PDF segment reader and in-place PDF writer with invariants.
- 2026-10-07 03:37 — Plan step 3: DOCX writer with run-preserving diff and tracked changes ([[docx-writer]], [[docx-redline]]).
- 2026-10-07 03:35 — Plan step 2: data models ([[models]]) and DOCX segment reader ([[docx-reader]]).
- 2026-10-07 03:33 — Plan step 1: fixture generator and committed fixtures ([[evals-make-fixtures]]).
- 2026-10-07 03:31 — Plan step 0: repository skeleton; `intent.md`, `spec.md`, `plan.md`, `AGENTS.md`, `CLAUDE.md`.
- 2026-10-06 — Grilling sessions with the owner; method: ai-factory-kit (intent → spec → plan).
