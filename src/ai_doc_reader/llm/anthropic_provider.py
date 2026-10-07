"""Anthropic API through the official SDK, with structured output."""

from __future__ import annotations

import anthropic

from ai_doc_reader.llm.base import LLMError, LLMProvider


class AnthropicProvider(LLMProvider):
    key = "anthropic"

    def __init__(self, model: str, api_key: str, timeout: float):
        super().__init__(model)
        self.client = anthropic.Anthropic(api_key=api_key or None, timeout=timeout)

    def complete_text(self, system: str, user: str, schema: dict) -> str:
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=16000,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"format": {"type": "json_schema", "schema": schema}},
            )
        except anthropic.APIError as e:
            raise LLMError(f"anthropic: {e}") from e
        if resp.stop_reason == "refusal":
            raise LLMError("anthropic: request refused")
        return next((b.text for b in resp.content if b.type == "text"), "")

    def list_models(self) -> list[str]:
        try:
            return [m.id for m in self.client.models.list()]
        except anthropic.APIError:
            return []
