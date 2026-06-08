"""Catalog of supported LLM providers + factory.

All providers must expose the OpenAI chat-completions schema. The default
client (`LLMClient` aka `MistralClient`) speaks that protocol natively, so
swapping providers requires only `base_url` + `api_key` + `model_name`.

Env vars (any of, used as fallback when the catalog entry has no key set):
- MISTRAL_API_KEY
- GROQ_API_KEY
- OPENAI_API_KEY
- OPENROUTER_API_KEY
- LLM_API_KEY (legacy generic)
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

from app.config import LLMConfig
from app.llm.mistral import MistralClient


@dataclass(frozen=True)
class ModelSpec:
    id: str  # stable id surfaced to UI, e.g. "groq/llama-3.3-70b"
    label: str  # human label, e.g. "Llama 3.3 70B (Groq, veloce)"
    provider: str  # "mistral" | "groq" | "openai" | "openrouter"
    base_url: str
    model_name: str  # actual model name passed to API
    env_key: str  # env var holding the API key
    notes: str = ""


CATALOG: list[ModelSpec] = [
    ModelSpec(
        id="mistral/nemo",
        label="Mistral Nemo (default, equilibrato)",
        provider="mistral",
        base_url="https://api.mistral.ai/v1",
        model_name="open-mistral-nemo",
        env_key="MISTRAL_API_KEY",
        notes="Buon equilibrio costo/qualità, default storico.",
    ),
    ModelSpec(
        id="mistral/large",
        label="Mistral Large (qualità alta)",
        provider="mistral",
        base_url="https://api.mistral.ai/v1",
        model_name="mistral-large-latest",
        env_key="MISTRAL_API_KEY",
        notes="Più costoso, migliore su ragionamento/sintesi.",
    ),
    ModelSpec(
        id="groq/llama-3.3-70b",
        label="Llama 3.3 70B (Groq, super veloce)",
        provider="groq",
        base_url="https://api.groq.com/openai/v1",
        model_name="llama-3.3-70b-versatile",
        env_key="GROQ_API_KEY",
        notes="Latenza bassissima, buono per chat e simulazioni rapide.",
    ),
    ModelSpec(
        id="groq/llama-3.1-8b",
        label="Llama 3.1 8B (Groq, ultra veloce)",
        provider="groq",
        base_url="https://api.groq.com/openai/v1",
        model_name="llama-3.1-8b-instant",
        env_key="GROQ_API_KEY",
        notes="Massima velocità, qualità ridotta. Adatto a task semplici.",
    ),
    ModelSpec(
        id="openai/gpt-4o-mini",
        label="GPT-4o mini (OpenAI)",
        provider="openai",
        base_url="https://api.openai.com/v1",
        model_name="gpt-4o-mini",
        env_key="OPENAI_API_KEY",
        notes="Economico, qualità alta, JSON mode affidabile.",
    ),
]


def list_available_models() -> list[dict]:
    """Return catalog entries that have an API key configured.

    Output is JSON-ready for the UI. Always includes the default Mistral
    entry, even if the key is missing (caller will get a clear error later).
    """
    out: list[dict] = []
    legacy = os.environ.get("LLM_API_KEY", "")
    for spec in CATALOG:
        key = os.environ.get(spec.env_key, "")
        if not key and spec.provider == "mistral":
            key = legacy  # backward compat
        out.append(
            {
                "id": spec.id,
                "label": spec.label,
                "provider": spec.provider,
                "model": spec.model_name,
                "available": bool(key),
                "notes": spec.notes,
            }
        )
    return out


def _resolve_api_key(spec: ModelSpec) -> str:
    key = os.environ.get(spec.env_key, "")
    if not key and spec.provider == "mistral":
        key = os.environ.get("LLM_API_KEY", "")
    return key


def make_llm_client(model_id: Optional[str] = None) -> MistralClient:
    """Build an LLM client for the given catalog id; falls back to env default.

    Raises LLMError if the resolved provider has no API key configured.
    """
    if not model_id:
        # default: whatever LLM_* env vars say
        return MistralClient()

    spec = next((m for m in CATALOG if m.id == model_id), None)
    if spec is None:
        # unknown id -> fall back silently to default rather than crash
        return MistralClient()

    api_key = _resolve_api_key(spec)
    if not api_key:
        from app.llm.mistral import LLMError

        raise LLMError(
            f"Model '{model_id}' requested but env var '{spec.env_key}' is not set."
        )

    cfg = LLMConfig(
        api_key=api_key,
        base_url=spec.base_url,
        model=spec.model_name,
        timeout_s=float(os.environ.get("LLM_TIMEOUT_S", "60")),
        max_retries=int(os.environ.get("LLM_MAX_RETRIES", "1")),
    )
    return MistralClient(config=cfg)


# Friendly alias: client class is provider-agnostic, name reflects that.
LLMClient = MistralClient
