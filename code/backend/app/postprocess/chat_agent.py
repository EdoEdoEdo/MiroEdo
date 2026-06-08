"""ReAct chat agent over a generated report.

Exposes 6 tools to a Mistral LLM via prompt-based tool calling (same pattern
as MiroFish `report_agent.py`):

Local (always available):
- `query_report_section(sid)`  -> raw markdown of a section
- `query_simulation_actions(filter, limit)` -> grep over the actions.jsonl log

Zep (degrades to "service unavailable" if no API key / no credit):
- `quick_search(query, limit)`
- `panorama_search(query)`
- `insight_forge(query)`

OASIS (degrades if the simulation env is not alive):
- `interview_agents(topic, max_agents)`

Loop: system prompt + history -> LLM emits either a final answer or
`<tool_call>{...}</tool_call>`; we execute, append the result, iterate.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from app.llm.mistral import LLMError, MistralClient
from app.postprocess.chat import (
    MAX_HISTORY_TURNS,
    MAX_REPORT_CHARS,
    ChatError,
    ChatMessage,
    Section,
    _safe_client,
    index_report,
)

logger = logging.getLogger(__name__)


MAX_TOOL_CALLS = 5

VALID_TOOL_NAMES = {
    "query_report_section",
    "query_simulation_actions",
    "quick_search",
    "panorama_search",
    "insight_forge",
    "interview_agents",
}


SYSTEM_TEMPLATE = """Sei l'agente ReAct di MiroEdo per il brand "{brand}".

Hai accesso a 6 tool. Per usarne uno emetti SOLO:
<tool_call>{{"name": "<tool>", "parameters": {{...}}}}</tool_call>

I tool disponibili:

1. query_report_section(sid: str)
   -> Restituisce il markdown grezzo della sezione del report con quel sid.
   Usalo quando devi citare letteralmente un passaggio.

2. query_simulation_actions(filter: str = "", limit: int = 20)
   -> Cerca nel log della simulazione OASIS le azioni che contengono `filter`.
   Restituisce le ultime N voci come JSON line.

3. quick_search(query: str, limit: int = 8)
   -> Ricerca semantica veloce sui fact del knowledge graph Zep.

4. panorama_search(query: str)
   -> Vista 360°: nodi + edge + fact rilevanti per la query.

5. insight_forge(query: str)
   -> Decompone la query in sub-domande, fa più ricerche Zep e sintetizza
   un insight strutturato con citazioni temporali. Più lento, più completo.

6. interview_agents(topic: str, max_agents: int = 3)
   -> Intervista REALE degli agenti OASIS della simulazione (solo se l'env è
   ancora viva). Restituisce risposte multi-agent.

REGOLE:
- Pensa prima quale tool serve. Massimo {max_calls} chiamate per turno.
- Se un tool ritorna "service unavailable" o errore, NON ripeterlo: cambia
  strategia o rispondi con i dati che hai.
- Quando hai dati sufficienti, rispondi in italiano (max 6 frasi) SENZA
  emettere altri <tool_call>. Cita gli sid del report tra parentesi quadre
  quando rilevante, es. [S2.1].
- Niente JSON envelope finale: rispondi in markdown discorsivo.

=== SEZIONI DEL REPORT ===
{sections_list}
=== SIMULAZIONE ===
simulation_id: {simulation_id}
graph_id Zep: {graph_id}
"""


# ============================================================
# Tool implementations
# ============================================================


@dataclass
class ToolCall:
    name: str
    parameters: dict[str, Any]
    result_text: str = ""
    error: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "parameters": self.parameters,
            "result_excerpt": (self.result_text or "")[:400],
            "error": self.error,
        }


@dataclass
class ChatAgentAnswer:
    answer: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    sections: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "answer": self.answer,
            "tool_calls": [tc.to_dict() for tc in self.tool_calls],
            "sections": list(self.sections),
        }


def _exec_query_report_section(
    sid: str, indexed_markdown: str, valid_ids: set[str]
) -> str:
    if not sid or sid not in valid_ids:
        return f"Sezione '{sid}' non trovata. Sid validi: {sorted(valid_ids)[:10]}..."
    # crude extractor: from "## [SID]" or "### [SID]" to next heading of same/higher level
    pattern = re.compile(rf"^(#{{2,3}})\s+\[{re.escape(sid)}\]\s+(.+?)$", re.MULTILINE)
    m = pattern.search(indexed_markdown)
    if not m:
        return f"Sezione '{sid}' non localizzata nel markdown."
    start = m.start()
    level = len(m.group(1))
    # find next heading of <= level after start
    after = indexed_markdown[m.end() :]
    next_heading = re.search(
        rf"^#{{1,{level}}}\s+", after, re.MULTILINE
    )
    end = m.end() + (next_heading.start() if next_heading else len(after))
    chunk = indexed_markdown[start:end].strip()
    # safety cap
    if len(chunk) > 2500:
        chunk = chunk[:2500] + "\n…[truncated]"
    return chunk


def _exec_query_simulation_actions(
    actions_log_path: Optional[Path], filter_str: str, limit: int
) -> str:
    if not actions_log_path or not actions_log_path.exists():
        return "service unavailable: no actions log for this run"
    limit = max(1, min(int(limit or 20), 100))
    needle = (filter_str or "").lower().strip()
    matches: list[str] = []
    try:
        with actions_log_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                if not needle or needle in line.lower():
                    matches.append(line.strip())
    except OSError as exc:
        return f"error reading actions log: {exc}"
    tail = matches[-limit:]
    if not tail:
        return f"Nessuna azione corrisponde al filtro '{filter_str}'."
    return "\n".join(tail)


def _get_zep_tools_service():
    """Return ZepToolsService instance or None if unavailable."""
    if not os.environ.get("ZEP_API_KEY"):
        return None
    try:
        from app.engine.zep.tools import ZepToolsService

        return ZepToolsService()
    except Exception as exc:  # noqa: BLE001
        logger.warning("ZepToolsService unavailable: %s", exc)
        return None


def _exec_quick_search(graph_id: Optional[str], query: str, limit: int) -> str:
    if not graph_id:
        return "service unavailable: no Zep graph for this run"
    svc = _get_zep_tools_service()
    if svc is None:
        return "service unavailable: Zep not configured or no credit"
    try:
        result = svc.quick_search(graph_id=graph_id, query=query, limit=int(limit or 8))
        return result.to_text() if hasattr(result, "to_text") else str(result)
    except Exception as exc:  # noqa: BLE001
        return f"Zep error: {exc}"


def _exec_panorama_search(graph_id: Optional[str], query: str) -> str:
    if not graph_id:
        return "service unavailable: no Zep graph for this run"
    svc = _get_zep_tools_service()
    if svc is None:
        return "service unavailable: Zep not configured or no credit"
    try:
        result = svc.panorama_search(graph_id=graph_id, query=query)
        return result.to_text() if hasattr(result, "to_text") else str(result)
    except Exception as exc:  # noqa: BLE001
        return f"Zep error: {exc}"


def _exec_insight_forge(
    graph_id: Optional[str], query: str, simulation_requirement: str
) -> str:
    if not graph_id:
        return "service unavailable: no Zep graph for this run"
    svc = _get_zep_tools_service()
    if svc is None:
        return "service unavailable: Zep not configured or no credit"
    try:
        result = svc.insight_forge(
            graph_id=graph_id,
            query=query,
            simulation_requirement=simulation_requirement or "",
            report_context="",
        )
        return result.to_text() if hasattr(result, "to_text") else str(result)
    except Exception as exc:  # noqa: BLE001
        return f"Zep error: {exc}"


def _exec_interview_agents(
    simulation_id: Optional[str],
    topic: str,
    max_agents: int,
    simulation_requirement: str,
) -> str:
    if not simulation_id:
        return "service unavailable: no simulation_id for this run"
    # check env alive first
    try:
        from app.engine.simulation.runner import SimulationRunner

        if not SimulationRunner.check_env_alive(simulation_id):
            return (
                "service unavailable: OASIS env not alive for this simulation. "
                "Interviste in tempo reale richiedono una sim persistente."
            )
    except Exception as exc:  # noqa: BLE001
        return f"service unavailable: cannot reach SimulationRunner: {exc}"

    svc = _get_zep_tools_service()
    if svc is None:
        # interview_agents lives on ZepToolsService but doesn't need Zep API itself
        # try a partial construction
        try:
            from app.engine.zep.tools import ZepToolsService

            svc = ZepToolsService.__new__(ZepToolsService)
            svc.__init__()  # may raise; fallback below
        except Exception as exc:  # noqa: BLE001
            return f"interview_agents unavailable: {exc}"
    try:
        result = svc.interview_agents(
            simulation_id=simulation_id,
            interview_requirement=topic,
            simulation_requirement=simulation_requirement or "",
            max_agents=int(max_agents or 3),
        )
        return result.to_text() if hasattr(result, "to_text") else str(result)
    except Exception as exc:  # noqa: BLE001
        return f"interview error: {exc}"


def _dispatch_tool(
    *,
    name: str,
    parameters: dict[str, Any],
    indexed_markdown: str,
    valid_ids: set[str],
    actions_log_path: Optional[Path],
    graph_id: Optional[str],
    simulation_id: Optional[str],
    simulation_requirement: str,
) -> str:
    if name not in VALID_TOOL_NAMES:
        return f"unknown tool '{name}'. Valid: {sorted(VALID_TOOL_NAMES)}"
    try:
        if name == "query_report_section":
            return _exec_query_report_section(
                str(parameters.get("sid", "")), indexed_markdown, valid_ids
            )
        if name == "query_simulation_actions":
            return _exec_query_simulation_actions(
                actions_log_path,
                str(parameters.get("filter", "")),
                int(parameters.get("limit", 20)),
            )
        if name == "quick_search":
            return _exec_quick_search(
                graph_id,
                str(parameters.get("query", "")),
                int(parameters.get("limit", 8)),
            )
        if name == "panorama_search":
            return _exec_panorama_search(graph_id, str(parameters.get("query", "")))
        if name == "insight_forge":
            return _exec_insight_forge(
                graph_id,
                str(parameters.get("query", "")),
                simulation_requirement,
            )
        if name == "interview_agents":
            return _exec_interview_agents(
                simulation_id,
                str(parameters.get("topic", parameters.get("query", ""))),
                int(parameters.get("max_agents", 3)),
                simulation_requirement,
            )
    except Exception as exc:  # noqa: BLE001
        return f"tool '{name}' crashed: {exc}"
    return f"tool '{name}' returned no result"


# ============================================================
# Parsing
# ============================================================

_TOOL_CALL_RE = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL
)


def _parse_tool_call(response: str) -> Optional[dict[str, Any]]:
    """Return first tool call dict or None if response is a final answer."""
    m = _TOOL_CALL_RE.search(response or "")
    if not m:
        # tolerate a bare JSON object
        stripped = (response or "").strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                obj = json.loads(stripped)
                if isinstance(obj, dict) and obj.get("name") in VALID_TOOL_NAMES:
                    return obj
            except json.JSONDecodeError:
                return None
        return None
    try:
        obj = json.loads(m.group(1))
    except json.JSONDecodeError as exc:
        logger.warning("invalid tool_call JSON: %s", exc)
        return None
    if not isinstance(obj, dict) or obj.get("name") not in VALID_TOOL_NAMES:
        return None
    if "parameters" not in obj or not isinstance(obj["parameters"], dict):
        obj["parameters"] = {}
    return obj


def _strip_tool_calls(text: str) -> str:
    return _TOOL_CALL_RE.sub("", text or "").strip()


# ============================================================
# Public entry point
# ============================================================


def chat_agent_with_report(
    *,
    report_markdown: str,
    brand: str,
    mode: str,
    question: str,
    history: Optional[list[ChatMessage]] = None,
    client: Optional[MistralClient] = None,
    actions_log_path: Optional[Path] = None,
    graph_id: Optional[str] = None,
    simulation_id: Optional[str] = None,
    simulation_requirement: str = "",
    temperature: float = 0.2,
) -> ChatAgentAnswer:
    """Run a ReAct turn with 6 tools available to the LLM."""
    if not (question or "").strip():
        raise ChatError("question is empty")

    client = client or _safe_client()
    if client is None:
        raise ChatError("LLM client not configured")

    report = (report_markdown or "").strip()
    if len(report) > MAX_REPORT_CHARS:
        report = report[:MAX_REPORT_CHARS] + "\n…[truncated]"
    indexed, sections = index_report(report)
    valid_ids = {s.sid for s in sections}

    sections_list = "\n".join(
        f"{'  ' if s.level == 3 else ''}- [{s.sid}] {s.title}" for s in sections
    ) or "(nessuna sezione)"

    system = SYSTEM_TEMPLATE.format(
        brand=brand or "Brand",
        max_calls=MAX_TOOL_CALLS,
        sections_list=sections_list,
        simulation_id=simulation_id or "(non disponibile)",
        graph_id=graph_id or "(non disponibile)",
    )

    messages: list[dict] = [{"role": "system", "content": system}]
    trimmed = (history or [])[-MAX_HISTORY_TURNS * 2 :]
    for m in trimmed:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": question.strip()})

    tool_calls: list[ToolCall] = []

    for iteration in range(MAX_TOOL_CALLS + 1):
        try:
            raw = client.chat_messages(messages, temperature=temperature).strip()
        except LLMError as exc:
            raise ChatError(str(exc)) from exc

        call = _parse_tool_call(raw)
        if call is None or iteration == MAX_TOOL_CALLS:
            # final answer
            final_text = _strip_tool_calls(raw) or raw
            return ChatAgentAnswer(
                answer=final_text,
                tool_calls=tool_calls,
                sections=[
                    {"sid": s.sid, "title": s.title, "level": s.level}
                    for s in sections
                ],
            )

        # execute tool
        name = call["name"]
        params = call.get("parameters", {})
        result_text = _dispatch_tool(
            name=name,
            parameters=params,
            indexed_markdown=indexed,
            valid_ids=valid_ids,
            actions_log_path=actions_log_path,
            graph_id=graph_id,
            simulation_id=simulation_id,
            simulation_requirement=simulation_requirement,
        )
        tool_calls.append(
            ToolCall(name=name, parameters=params, result_text=result_text)
        )

        # feed back into the conversation
        messages.append({"role": "assistant", "content": raw})
        # cap large tool outputs to keep prompt size sane
        capped = (result_text or "")
        if len(capped) > 4000:
            capped = capped[:4000] + "\n…[truncated]"
        messages.append(
            {
                "role": "user",
                "content": f"<tool_result name=\"{name}\">\n{capped}\n</tool_result>",
            }
        )

    # safety net (should be unreachable)
    return ChatAgentAnswer(
        answer="(loop interrotto senza risposta)",
        tool_calls=tool_calls,
        sections=[
            {"sid": s.sid, "title": s.title, "level": s.level} for s in sections
        ],
    )
