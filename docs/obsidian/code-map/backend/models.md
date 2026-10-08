---
title: src/ai_doc_editor/models.py
tags:
  - code-map
  - backend
---

# `src/ai_doc_editor/models.py`

Section: [[Backend]]

## Purpose

Core data types shared by readers, writers, providers and the report (spec.md section 1).

## Classes

### `Segment` (BaseModel)

The smallest unit of text the model may change.

Fields: `id`, `text`, `page`, `bbox`, `skip_reason`

- `def editable(self) -> bool` — True when the segment may be sent to the model.

### `Edit` (BaseModel)

The model's proposed replacement text for one segment.

Fields: `id`, `new_text`


### `EditBatch` (BaseModel)

Model response schema (spec.md 4.1).

Fields: `edits`


### `Scope` (BaseModel)

Which segments a free-form instruction applies to (scope resolution step).

Fields: `scope`, `ids`


### `ChangeStatus` (StrEnum)

applied / shortened / shrunk / rejected / skipped.


### `Change` (BaseModel)

An edit after a writer applied or refused it.

Fields: `id`, `old_text`, `new_text`, `status`, `reason`, `notes`, `page`


### `ChangeReport` (BaseModel)

Everything about one run: source, output, instruction, provider, counts, changes, violations, conversion, scope.

Fields: `source_name`, `output_name`, `instruction`, `provider`, `model`, `track_changes`, `segments_total`, `segments_sent`, `duration_s`, `changes`, `violations`, `conversion`, `scope`

- `def count(self, status: ChangeStatus) -> int` — Number of changes with a given status.
