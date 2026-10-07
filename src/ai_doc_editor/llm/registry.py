"""Provider keys -> configured provider instances (spec.md 4.5)."""

from __future__ import annotations

from ai_doc_editor.llm.anthropic_provider import AnthropicProvider
from ai_doc_editor.llm.base import LLMError, LLMProvider
from ai_doc_editor.llm.cli_provider import CLIS, CliProvider
from ai_doc_editor.llm.openai_compatible import OpenAICompatibleProvider
from ai_doc_editor.settings import Settings, get_settings

GOOGLE_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

PROVIDERS = ["ollama", "lmstudio", "openai", "anthropic", "google", *[f"cli:{c}" for c in CLIS]]

# Shown when a backend cannot list its models (CLIs accept these aliases).
FALLBACK_MODELS = {
    "ollama": ["qwen3.5:9b", "qwen3.5:4b", "gemma4:12b"],
    "anthropic": ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-4-5"],
    "cli:claude": ["sonnet", "opus", "haiku"],
    "cli:codex": [""],
    "cli:agy": [""],
}


def get_provider(key: str, model: str, settings: Settings | None = None) -> LLMProvider:
    s = settings or get_settings()
    t = s.llm_timeout_s
    if key == "ollama":
        return OpenAICompatibleProvider(key, model, s.ollama_base_url, "", t)
    if key == "lmstudio":
        return OpenAICompatibleProvider(key, model, s.lmstudio_base_url, "", t)
    if key == "openai":
        return OpenAICompatibleProvider(key, model, None, s.openai_api_key, t)
    if key == "google":
        return OpenAICompatibleProvider(key, model, GOOGLE_BASE_URL, s.google_api_key, t)
    if key == "anthropic":
        return AnthropicProvider(model, s.anthropic_api_key, t)
    if key.startswith("cli:") and key[4:] in CLIS:
        return CliProvider(key[4:], model, t, s.cli_bridge_url, s.cli_bridge_token)
    raise LLMError(f"unknown provider {key!r}; choose one of {PROVIDERS}")


def list_models(key: str, settings: Settings | None = None) -> list[str]:
    """Models the backend reports (live for local servers and APIs), else a fallback list."""
    s = settings or get_settings()
    needs_key = {
        "openai": s.openai_api_key,
        "google": s.google_api_key,
        "anthropic": s.anthropic_api_key,
    }
    if key in needs_key and not needs_key[key]:
        return FALLBACK_MODELS.get(key, [])
    if key.startswith("cli:"):
        return FALLBACK_MODELS.get(key, [""])
    try:
        provider = get_provider(key, "", s)
        models = provider.list_models()  # type: ignore[attr-defined]
    except Exception:  # an unreachable backend must not break the UI
        models = []
    return models or FALLBACK_MODELS.get(key, [])
