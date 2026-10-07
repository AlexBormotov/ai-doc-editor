"""Ollama, LM Studio, OpenAI and Google Gemini through one OpenAI-compatible client."""

from __future__ import annotations

import openai

from ai_doc_editor.llm.base import LLMError, LLMProvider


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, key: str, model: str, base_url: str | None, api_key: str, timeout: float):
        super().__init__(model)
        self.key = key
        # Local servers ignore the key, but the SDK requires a non-empty one.
        self.client = openai.OpenAI(
            base_url=base_url, api_key=api_key or "not-needed", timeout=timeout, max_retries=1
        )
        self._use_schema = True

    def complete_text(self, system: str, user: str, schema: dict) -> str:
        kwargs = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": 0,
        }
        if self.key == "ollama":
            # Segment edits need no chain of thought; thinking models are 10x slower with it.
            kwargs["extra_body"] = {"reasoning_effort": "none"}
        if self._use_schema:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "edits", "schema": schema, "strict": True},
            }
        try:
            resp = self.client.chat.completions.create(**kwargs)
        except openai.BadRequestError as e:
            if not self._use_schema or "response_format" not in str(e):
                raise LLMError(f"{self.key}: {e}") from e
            self._use_schema = False  # backend without structured output: rely on the prompt
            return self.complete_text(system, user, schema)
        except openai.OpenAIError as e:
            raise LLMError(f"{self.key}: {e}") from e
        return resp.choices[0].message.content or ""

    def list_models(self) -> list[str]:
        try:
            return sorted(m.id for m in self.client.models.list())
        except openai.OpenAIError:
            return []
