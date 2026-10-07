"""Provider interface and response validation (spec.md 4.1, 4.5)."""

from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel, ValidationError

T = TypeVar("T", bound=BaseModel)


class LLMError(RuntimeError):
    """The backend failed (network, auth, process exit)."""


class InvalidResponseError(LLMError):
    """The backend answered, but not with valid JSON for the schema, even after a retry."""


_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def extract_json(text: str) -> str:
    """The JSON object inside a reply that may carry code fences or stray prose."""
    m = _FENCE.search(text)
    if m:
        text = m.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise ValueError("no JSON object in response")
    return text[start : end + 1]


def strict_schema(model: type[BaseModel]) -> dict:
    """JSON schema with `$defs` inlined and `additionalProperties: false` (strict-mode safe)."""
    schema = model.model_json_schema()
    defs = schema.pop("$defs", {})

    def walk(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return walk(defs[node["$ref"].split("/")[-1]])
            out = {k: walk(v) for k, v in node.items() if k not in ("title", "default")}
            if out.get("type") == "object":
                out["additionalProperties"] = False
                out["required"] = list(out.get("properties", {}))
            return out
        if isinstance(node, list):
            return [walk(x) for x in node]
        return node

    return walk(schema)


class LLMProvider(ABC):
    """One LLM backend. Subclasses implement `complete_text`; validation lives here."""

    key: str

    def __init__(self, model: str):
        self.model = model

    @abstractmethod
    def complete_text(self, system: str, user: str, schema: dict) -> str:
        """Return the raw text reply. `schema` is a hint for backends that can enforce it."""

    def complete_json(self, system: str, user: str, schema: type[T], retries: int = 1) -> T:
        """Call the backend and validate the reply; on failure retry with the error appended."""
        json_schema = strict_schema(schema)
        prompt = user
        last_error = ""
        for _ in range(retries + 1):
            raw = self.complete_text(system, prompt, json_schema)
            try:
                return schema.model_validate(json.loads(extract_json(raw)))
            except (ValueError, ValidationError) as e:
                last_error = str(e)[:500]
                prompt = (
                    f"{user}\n\nYour previous reply was not valid: {last_error}\n"
                    "Reply again with only the JSON object."
                )
        raise InvalidResponseError(last_error)
