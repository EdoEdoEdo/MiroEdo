"""
Per-platform action logger and unified simulation log manager.

Adapted from MiroFish's `backend/scripts/action_logger.py` — was already
Flask-independent. Cleaned up: dropped legacy `ActionLogger` and `get_logger`
globals (use `SimulationLogManager` directly).

Output layout (per simulation):
    sim_xxx/
    ├── twitter/actions.jsonl
    ├── reddit/actions.jsonl
    └── simulation.log
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional


class PlatformActionLogger:
    """Single-platform action logger (writes JSONL)."""

    def __init__(self, platform: str, base_dir: str) -> None:
        self.platform = platform
        self.base_dir = base_dir
        self.log_dir = os.path.join(base_dir, platform)
        self.log_path = os.path.join(self.log_dir, "actions.jsonl")
        os.makedirs(self.log_dir, exist_ok=True)

    def _append(self, entry: Dict[str, Any]) -> None:
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def log_action(
        self,
        round_num: int,
        agent_id: int,
        agent_name: str,
        action_type: str,
        action_args: Optional[Dict[str, Any]] = None,
        result: Optional[str] = None,
        success: bool = True,
    ) -> None:
        self._append(
            {
                "round": round_num,
                "timestamp": datetime.now().isoformat(),
                "agent_id": agent_id,
                "agent_name": agent_name,
                "action_type": action_type,
                "action_args": action_args or {},
                "result": result,
                "success": success,
            }
        )

    def log_round_start(self, round_num: int, simulated_hour: int) -> None:
        self._append(
            {
                "round": round_num,
                "timestamp": datetime.now().isoformat(),
                "event_type": "round_start",
                "simulated_hour": simulated_hour,
            }
        )

    def log_round_end(self, round_num: int, actions_count: int) -> None:
        self._append(
            {
                "round": round_num,
                "timestamp": datetime.now().isoformat(),
                "event_type": "round_end",
                "actions_count": actions_count,
            }
        )

    def log_simulation_start(self, config: Dict[str, Any]) -> None:
        self._append(
            {
                "timestamp": datetime.now().isoformat(),
                "event_type": "simulation_start",
                "platform": self.platform,
                "total_rounds": config.get("time_config", {}).get("total_simulation_hours", 72) * 2,
                "agents_count": len(config.get("agent_configs", [])),
            }
        )

    def log_simulation_end(self, total_rounds: int, total_actions: int) -> None:
        self._append(
            {
                "timestamp": datetime.now().isoformat(),
                "event_type": "simulation_end",
                "platform": self.platform,
                "total_rounds": total_rounds,
                "total_actions": total_actions,
            }
        )


class SimulationLogManager:
    """Unified log manager for a simulation directory."""

    def __init__(self, simulation_dir: str) -> None:
        self.simulation_dir = simulation_dir
        os.makedirs(simulation_dir, exist_ok=True)
        self.twitter_logger: Optional[PlatformActionLogger] = None
        self.reddit_logger: Optional[PlatformActionLogger] = None
        self._main_logger = self._setup_main_logger()

    def _setup_main_logger(self) -> logging.Logger:
        log_path = os.path.join(self.simulation_dir, "simulation.log")
        logger = logging.getLogger(f"simulation.{os.path.basename(self.simulation_dir)}")
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        logger.propagate = False

        file_handler = logging.FileHandler(log_path, encoding="utf-8", mode="w")
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(
            logging.Formatter("[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
        )
        logger.addHandler(console_handler)
        return logger

    def get_twitter_logger(self) -> PlatformActionLogger:
        if self.twitter_logger is None:
            self.twitter_logger = PlatformActionLogger("twitter", self.simulation_dir)
        return self.twitter_logger

    def get_reddit_logger(self) -> PlatformActionLogger:
        if self.reddit_logger is None:
            self.reddit_logger = PlatformActionLogger("reddit", self.simulation_dir)
        return self.reddit_logger

    def info(self, msg: str) -> None:
        self._main_logger.info(msg)

    def warning(self, msg: str) -> None:
        self._main_logger.warning(msg)

    def error(self, msg: str) -> None:
        self._main_logger.error(msg)

    def debug(self, msg: str) -> None:
        self._main_logger.debug(msg)
