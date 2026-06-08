"""Configurazione runtime (env vars)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LLMConfig:
    api_key: str
    base_url: str
    model: str
    timeout_s: float
    max_retries: int


def load_llm_config() -> LLMConfig:
    """Legge env vars. Default: Mistral nemo."""
    return LLMConfig(
        api_key=os.environ.get("LLM_API_KEY", ""),
        base_url=os.environ.get("LLM_BASE_URL", "https://api.mistral.ai/v1").rstrip("/"),
        model=os.environ.get("LLM_MODEL_NAME", "open-mistral-nemo"),
        timeout_s=float(os.environ.get("LLM_TIMEOUT_S", "60")),
        max_retries=int(os.environ.get("LLM_MAX_RETRIES", "1")),
    )
