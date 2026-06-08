"""
File-based IPC between MiroEdo backend and OASIS simulation subprocess.

Adapted from MiroFish's `app/services/simulation_ipc.py`. Only change:
import path for logger (now `app.engine.utils.logger`).

Design pattern: command/response via JSON files.
- Client writes commands to `{sim_dir}/ipc_commands/{uuid}.json`
- Server polls, processes, writes response to `{sim_dir}/ipc_responses/{uuid}.json`
- Client polls responses, parses, deletes
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from app.engine.utils.logger import get_logger

logger = get_logger("miroedo.engine.ipc")


class CommandType(str, Enum):
    INTERVIEW = "interview"
    BATCH_INTERVIEW = "batch_interview"
    CLOSE_ENV = "close_env"


class CommandStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class IPCCommand:
    command_id: str
    command_type: CommandType
    args: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "command_type": self.command_type.value,
            "args": self.args,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IPCCommand":
        return cls(
            command_id=data["command_id"],
            command_type=CommandType(data["command_type"]),
            args=data.get("args", {}),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )


@dataclass
class IPCResponse:
    command_id: str
    status: CommandStatus
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command_id": self.command_id,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IPCResponse":
        return cls(
            command_id=data["command_id"],
            status=CommandStatus(data["status"]),
            result=data.get("result"),
            error=data.get("error"),
            timestamp=data.get("timestamp", datetime.now().isoformat()),
        )


class SimulationIPCClient:
    """Used by MiroEdo backend to send commands to running simulation."""

    def __init__(self, simulation_dir: str) -> None:
        self.simulation_dir = simulation_dir
        self.commands_dir = os.path.join(simulation_dir, "ipc_commands")
        self.responses_dir = os.path.join(simulation_dir, "ipc_responses")
        os.makedirs(self.commands_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)

    def send_command(
        self,
        command_type: CommandType,
        args: Dict[str, Any],
        timeout: float = 60.0,
        poll_interval: float = 0.5,
    ) -> IPCResponse:
        command_id = str(uuid.uuid4())
        command = IPCCommand(command_id=command_id, command_type=command_type, args=args)

        command_file = os.path.join(self.commands_dir, f"{command_id}.json")
        with open(command_file, "w", encoding="utf-8") as f:
            json.dump(command.to_dict(), f, ensure_ascii=False, indent=2)

        logger.info(f"IPC command sent: {command_type.value}, id={command_id}")

        response_file = os.path.join(self.responses_dir, f"{command_id}.json")
        start = time.time()
        while time.time() - start < timeout:
            if os.path.exists(response_file):
                try:
                    with open(response_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    response = IPCResponse.from_dict(data)
                    for path in (command_file, response_file):
                        try:
                            os.remove(path)
                        except OSError:
                            pass
                    logger.info(f"IPC response: id={command_id}, status={response.status.value}")
                    return response
                except (json.JSONDecodeError, KeyError) as exc:
                    logger.warning(f"Response parse failed: {exc}")
            time.sleep(poll_interval)

        logger.error(f"IPC timeout: id={command_id}")
        try:
            os.remove(command_file)
        except OSError:
            pass
        raise TimeoutError(f"IPC response timeout after {timeout}s")

    def send_interview(
        self,
        agent_id: int,
        prompt: str,
        platform: Optional[str] = None,
        timeout: float = 60.0,
    ) -> IPCResponse:
        args: Dict[str, Any] = {"agent_id": agent_id, "prompt": prompt}
        if platform:
            args["platform"] = platform
        return self.send_command(CommandType.INTERVIEW, args, timeout=timeout)

    def send_batch_interview(
        self,
        interviews: List[Dict[str, Any]],
        platform: Optional[str] = None,
        timeout: float = 120.0,
    ) -> IPCResponse:
        args: Dict[str, Any] = {"interviews": interviews}
        if platform:
            args["platform"] = platform
        return self.send_command(CommandType.BATCH_INTERVIEW, args, timeout=timeout)

    def send_close_env(self, timeout: float = 30.0) -> IPCResponse:
        return self.send_command(CommandType.CLOSE_ENV, {}, timeout=timeout)

    def check_env_alive(self) -> bool:
        status_file = os.path.join(self.simulation_dir, "env_status.json")
        if not os.path.exists(status_file):
            return False
        try:
            with open(status_file, "r", encoding="utf-8") as f:
                status = json.load(f)
            return status.get("status") == "alive"
        except (json.JSONDecodeError, OSError):
            return False


class SimulationIPCServer:
    """Used inside the OASIS subprocess to poll and respond to commands."""

    def __init__(self, simulation_dir: str) -> None:
        self.simulation_dir = simulation_dir
        self.commands_dir = os.path.join(simulation_dir, "ipc_commands")
        self.responses_dir = os.path.join(simulation_dir, "ipc_responses")
        os.makedirs(self.commands_dir, exist_ok=True)
        os.makedirs(self.responses_dir, exist_ok=True)
        self._running = False

    def start(self) -> None:
        self._running = True
        self._update_env_status("alive")

    def stop(self) -> None:
        self._running = False
        self._update_env_status("stopped")

    def _update_env_status(self, status: str) -> None:
        status_file = os.path.join(self.simulation_dir, "env_status.json")
        with open(status_file, "w", encoding="utf-8") as f:
            json.dump(
                {"status": status, "timestamp": datetime.now().isoformat()},
                f,
                ensure_ascii=False,
                indent=2,
            )

    def poll_commands(self) -> Optional[IPCCommand]:
        if not os.path.exists(self.commands_dir):
            return None
        files = []
        for fname in os.listdir(self.commands_dir):
            if fname.endswith(".json"):
                fpath = os.path.join(self.commands_dir, fname)
                files.append((fpath, os.path.getmtime(fpath)))
        files.sort(key=lambda x: x[1])

        for fpath, _ in files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    return IPCCommand.from_dict(json.load(f))
            except (json.JSONDecodeError, KeyError, OSError) as exc:
                logger.warning(f"Bad command file {fpath}: {exc}")
        return None

    def send_response(self, response: IPCResponse) -> None:
        rpath = os.path.join(self.responses_dir, f"{response.command_id}.json")
        with open(rpath, "w", encoding="utf-8") as f:
            json.dump(response.to_dict(), f, ensure_ascii=False, indent=2)
        cmd_path = os.path.join(self.commands_dir, f"{response.command_id}.json")
        try:
            os.remove(cmd_path)
        except OSError:
            pass

    def send_success(self, command_id: str, result: Dict[str, Any]) -> None:
        self.send_response(
            IPCResponse(command_id=command_id, status=CommandStatus.COMPLETED, result=result)
        )

    def send_error(self, command_id: str, error: str) -> None:
        self.send_response(
            IPCResponse(command_id=command_id, status=CommandStatus.FAILED, error=error)
        )
