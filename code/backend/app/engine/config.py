"""
EngineConfig: replaces MiroFish's Flask `Config` class.

Simple dataclass loaded from environment, with everything passable as
constructor params for tests / multiple instances.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class EngineConfig:
    # === LLM ===
    llm_api_key: str = ""
    llm_base_url: str = "https://api.mistral.ai/v1"
    llm_model: str = "open-mistral-nemo"

    # Optional boost LLM (per platform parallelism)
    llm_boost_api_key: str = ""
    llm_boost_base_url: str = ""
    llm_boost_model: str = ""

    # === Zep (optional) ===
    zep_api_key: str = ""           # if empty → Zep disabled

    # === Locale ===
    locale: str = "it"               # it / en / zh

    # === Paths ===
    simulations_dir: str = ""        # where each simulation_xxx/ lives
    reports_dir: str = ""            # where final reports are stored

    # === OASIS / simulation ===
    oasis_default_max_rounds: int = 5
    oasis_semaphore: int = 30
    twitter_actions: list[str] = field(default_factory=lambda: [
        "CREATE_POST", "LIKE_POST", "REPOST", "FOLLOW", "DO_NOTHING", "QUOTE_POST",
    ])
    reddit_actions: list[str] = field(default_factory=lambda: [
        "LIKE_POST", "DISLIKE_POST", "CREATE_POST", "CREATE_COMMENT",
        "LIKE_COMMENT", "DISLIKE_COMMENT", "SEARCH_POSTS", "SEARCH_USER",
        "TREND", "REFRESH", "DO_NOTHING", "FOLLOW", "MUTE",
    ])

    # === Report agent ===
    report_max_tool_calls: int = 3
    report_max_reflection_rounds: int = 2
    report_temperature: float = 0.5
    report_panorama_limit: int = 15
    report_max_tool_calls_per_chat: int = 2

    # === Text processing ===
    default_chunk_size: int = 500
    default_chunk_overlap: int = 50

    @property
    def zep_enabled(self) -> bool:
        return bool(self.zep_api_key)

    @classmethod
    def from_env(cls, base_dir: Optional[str] = None) -> "EngineConfig":
        """Load from environment variables. `base_dir` overrides default storage roots."""
        base = base_dir or os.environ.get("MIROEDO_DATA_DIR", os.path.abspath("data"))
        return cls(
            llm_api_key=os.environ.get("LLM_API_KEY", ""),
            llm_base_url=os.environ.get("LLM_BASE_URL", "https://api.mistral.ai/v1").rstrip("/"),
            llm_model=os.environ.get("LLM_MODEL_NAME", "open-mistral-nemo"),
            llm_boost_api_key=os.environ.get("LLM_BOOST_API_KEY", ""),
            llm_boost_base_url=os.environ.get("LLM_BOOST_BASE_URL", "").rstrip("/"),
            llm_boost_model=os.environ.get("LLM_BOOST_MODEL_NAME", ""),
            zep_api_key=os.environ.get("ZEP_API_KEY", ""),
            locale=os.environ.get("LOCALE", "it"),
            simulations_dir=os.environ.get("SIMULATIONS_DIR", os.path.join(base, "simulations")),
            reports_dir=os.environ.get("REPORTS_DIR", os.path.join(base, "reports")),
            oasis_default_max_rounds=int(os.environ.get("OASIS_DEFAULT_MAX_ROUNDS", "5")),
            oasis_semaphore=int(os.environ.get("OASIS_SEMAPHORE", "30")),
            report_max_tool_calls=int(os.environ.get("REPORT_AGENT_MAX_TOOL_CALLS", "3")),
            report_max_reflection_rounds=int(os.environ.get("REPORT_AGENT_MAX_REFLECTION_ROUNDS", "2")),
            report_temperature=float(os.environ.get("REPORT_AGENT_TEMPERATURE", "0.5")),
            report_panorama_limit=int(os.environ.get("REPORT_AGENT_PANORAMA_LIMIT", "15")),
            report_max_tool_calls_per_chat=int(os.environ.get("REPORT_AGENT_MAX_TOOL_CALLS_PER_CHAT", "2")),
        )

    def ensure_dirs(self) -> None:
        for path in (self.simulations_dir, self.reports_dir):
            if path:
                os.makedirs(path, exist_ok=True)
