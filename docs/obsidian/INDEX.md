---
title: Project Documentation Hub
tags:
  - index
---

# AI Doc Editor — documentation hub

Edit Word (`.docx`, `.doc`) and PDF documents with an LLM without breaking their layout. The
model only sees text segments and returns edits for them; writers put every edit back into the
object it came from; a structure check (the oracle) proves the rest is untouched.

Every section is connected via wikilinks — open Graph View in Obsidian to see the whole
structure. The approved design lives in `docs/`: `intent.md` (acceptance criteria AC-1…AC-12),
`spec.md` (contracts, decision records), `plan.md` (steps and every deviation).

## Sections

- [[Backend]] — the pipeline: readers, writers, LLM providers, orchestration, API, CLI
- [[Frontend]] — the Gradio UI mounted at `/ui`, page previews
- [[Evals]] — the oracle (structure invariants), tests, deterministic and model evals
- [[Planning]] — current stage, open limitations, roadmap
- [[Timeline]] — log: what was done and when

## Code map

Every source file is described by its own note under `code-map/`. Note name = path relative to
`src/ai_doc_editor/` (or to the repository for `scripts/` and `evals/`) with `/` and `_` → `-`:

- `code-map/backend/<name>.md` — e.g. `code-map/backend/pdf-writer.md` for
  `src/ai_doc_editor/pdf/writer.py`, `code-map/backend/scripts-cli-bridge.md` for
  `scripts/cli_bridge.py`
- `code-map/frontend/<name>.md` — `ui.py`, `preview.py`
- `code-map/evals/<name>.md` — e.g. `code-map/evals/evals-run-models.md`

A file note contains: the file's purpose, its classes and their methods, functions
(signature + one-line description), and links to related files via [[wikilinks]].

> [!important] Before writing new code
> Check the code map: a similar function or class may already exist. Adapt existing code
> instead of creating a duplicate and growing the codebase.

## Conventions

- Note filenames in ASCII (latin letters, dashes); content in any language
- Every section note links back to [[INDEX]]; code map notes link to their section
- New classes/methods are documented in the code map in the same session they are created
- Claude may create new sections when a topic doesn't fit existing ones — add the note and link
  it from [[INDEX]]
- [[Timeline]] gets a new entry after every working session (newest on top)
- Use the canonical terms of `spec.md` section 1: segment, edit, change, writer, provider,
  layout gate, section (PDF reflow)
