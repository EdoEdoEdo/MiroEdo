"""LLM client wrappers (provider-agnostic, OpenAI chat-completions schema)."""

from app.llm.catalog import (
    CATALOG,
    LLMClient,
    ModelSpec,
    list_available_models,
    make_llm_client,
)
from app.llm.mistral import LLMError, MistralClient

__all__ = [
    "CATALOG",
    "LLMClient",
    "LLMError",
    "MistralClient",
    "ModelSpec",
    "list_available_models",
    "make_llm_client",
]
