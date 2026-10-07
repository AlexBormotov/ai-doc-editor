"""Core data types shared by readers, writers, providers and the report (spec.md section 1)."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class Segment(BaseModel):
    """The smallest unit of text the model may change."""

    id: str
    text: str
    page: int | None = None  # 0-based, PDF only
    bbox: tuple[float, float, float, float] | None = None  # PDF only
    skip_reason: str | None = None  # set when the segment must not be sent to the model

    @property
    def editable(self) -> bool:
        return self.skip_reason is None


class Edit(BaseModel):
    """The model's proposed replacement text for one segment."""

    id: str
    new_text: str


class EditBatch(BaseModel):
    """Model response schema (spec.md 4.1)."""

    edits: list[Edit] = Field(default_factory=list)


class Scope(BaseModel):
    """Which segments a free-form instruction applies to (scope resolution step)."""

    scope: Literal["all", "ids"]
    ids: list[str] = Field(default_factory=list)


class ChangeStatus(StrEnum):
    APPLIED = "applied"
    SHORTENED = "shortened"  # model was asked to shorten to fit (PDF)
    SHRUNK = "shrunk"  # font was scaled down to fit (PDF)
    REJECTED = "rejected"
    SKIPPED = "skipped"


class Change(BaseModel):
    """An edit after a writer applied or refused it."""

    id: str
    old_text: str
    new_text: str | None = None
    status: ChangeStatus
    reason: str | None = None
    notes: list[str] = Field(default_factory=list)
    page: int | None = None


class ChangeReport(BaseModel):
    source_name: str
    output_name: str | None = None
    instruction: str
    provider: str
    model: str
    track_changes: bool | None = None
    segments_total: int = 0
    segments_sent: int = 0
    duration_s: float = 0.0
    changes: list[Change] = Field(default_factory=list)
    violations: list[str] = Field(default_factory=list)  # structure invariant failures
    conversion: dict | None = None  # layout gate result when a conversion was requested
    scope: list[str] | None = None  # segment ids the instruction was limited to, if any

    def count(self, status: ChangeStatus) -> int:
        return sum(1 for c in self.changes if c.status == status)
