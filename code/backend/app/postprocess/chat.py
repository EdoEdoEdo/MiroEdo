"""
Chat module: answers user questions grounded in a generated report.

Hardening (M6):
- Markdown sections are indexed with stable IDs (S1, S1.1, S2 ...) so the LLM
  can cite the precise origin of each datum.
- Output is requested as strict JSON: {answer, citations[], confidence,
  out_of_scope}. If parsing fails we fall back to plain text and synthesize a
  structured envelope so callers always receive a ChatAnswer.
- Multi-turn history is kept short (last N exchanges) to limit token cost.
- If the LLM client is not configured, raises ChatError (callers -> 503).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Iterator, List, Literal, Optional, Tuple

from app.llm.mistral import LLMError, MistralClient

Role = Literal["user", "assistant"]
Confidence = Literal["low", "medium", "high"]

MAX_REPORT_CHARS = 18_000  # safety cap; truncates from the end if exceeded
MAX_HISTORY_TURNS = 8  # last N (user, assistant) turns kept

SYSTEM_TEMPLATE = """Sei l'assistente conversazionale di MiroEdo, esperto di brand intelligence.

Rispondi sempre in italiano, in modo conciso (massimo 6 frasi), citando dati e
percentuali presenti nel report. NON inventare numeri o fatti non presenti nel
report. Se la domanda è fuori dallo scope del report, dichiaralo apertamente.

Brand: {brand}
Modalità della run: {mode}

=== SEZIONI DISPONIBILI ===
{sections_list}
=== REPORT (markdown con id sezione) ===
{report}
=== FINE REPORT ===

REGOLE DI OUTPUT (rigorose):
- Devi rispondere con UN SOLO oggetto JSON valido, senza testo prima o dopo.
- Schema:
  {{
    "answer": string,                // risposta in italiano, max 6 frasi
    "citations": [string],            // array di id sezione presi SOLO da SEZIONI DISPONIBILI (es. ["S2", "S2.1"]). Vuoto se nessuna è applicabile.
    "confidence": "low" | "medium" | "high",
    "out_of_scope": boolean           // true se il dato non è nel report
  }}
- "citations" deve contenere solo id elencati in SEZIONI DISPONIBILI. Mai inventare id.
- Se "out_of_scope" è true, "answer" deve spiegare che il dato non è nel report e "citations" deve essere [].
- Quando estrai un numero o un fatto, includi nelle "citations" la sezione da cui proviene.
"""


# === Section indexing ============================================


@dataclass
class Section:
    sid: str
    title: str
    level: int  # 2 for H2, 3 for H3


_H2_RE = re.compile(r"^##\s+(?!#)(.+?)\s*$")
_H3_RE = re.compile(r"^###\s+(?!#)(.+?)\s*$")


def index_report(markdown: str) -> Tuple[str, List[Section]]:
    """Return (indexed_markdown, sections).

    Each ``## Title`` line becomes ``## [S{n}] Title`` and each ``### Sub``
    underneath it becomes ``### [S{n}.{m}] Sub``. H1 lines are left untouched.
    """
    out_lines: list[str] = []
    sections: list[Section] = []
    h2_count = 0
    h3_count = 0
    current_h2: Optional[str] = None

    for line in (markdown or "").splitlines():
        m2 = _H2_RE.match(line)
        if m2:
            h2_count += 1
            h3_count = 0
            sid = f"S{h2_count}"
            current_h2 = sid
            title = m2.group(1).strip()
            sections.append(Section(sid=sid, title=title, level=2))
            out_lines.append(f"## [{sid}] {title}")
            continue

        m3 = _H3_RE.match(line)
        if m3 and current_h2 is not None:
            h3_count += 1
            sid = f"{current_h2}.{h3_count}"
            title = m3.group(1).strip()
            sections.append(Section(sid=sid, title=title, level=3))
            out_lines.append(f"### [{sid}] {title}")
            continue

        out_lines.append(line)

    return "\n".join(out_lines), sections


def _sections_to_prompt_list(sections: List[Section]) -> str:
    if not sections:
        return "(nessuna sezione: il report è vuoto)"
    parts = []
    for s in sections:
        indent = "  " if s.level == 3 else ""
        parts.append(f"{indent}- [{s.sid}] {s.title}")
    return "\n".join(parts)


# === Public API =================================================


class ChatError(RuntimeError):
    """Errore durante la chat con il report."""


@dataclass
class ChatMessage:
    role: Role
    content: str

    def to_dict(self) -> dict:
        return {"role": self.role, "content": self.content}


@dataclass
class ChatAnswer:
    answer: str
    citations: List[str] = field(default_factory=list)
    confidence: Confidence = "medium"
    out_of_scope: bool = False

    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "citations": list(self.citations),
            "confidence": self.confidence,
            "out_of_scope": self.out_of_scope,
        }


def chat_with_report(
    *,
    report_markdown: str,
    brand: str,
    mode: str,
    question: str,
    history: Optional[List[ChatMessage]] = None,
    client: Optional[MistralClient] = None,
    temperature: float = 0.2,
) -> ChatAnswer:
    """Run a grounded chat turn. Returns a ChatAnswer envelope."""
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

    system = SYSTEM_TEMPLATE.format(
        brand=brand or "Brand",
        mode=mode or "quick",
        sections_list=_sections_to_prompt_list(sections),
        report=indexed,
    )
    messages: list[dict] = [{"role": "system", "content": system}]

    trimmed = (history or [])[-MAX_HISTORY_TURNS * 2 :]
    for m in trimmed:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": question.strip()})

    try:
        raw = client.chat_messages(
            messages, temperature=temperature, response_format_json=True
        ).strip()
    except LLMError as exc:
        raise ChatError(str(exc)) from exc

    return _parse_answer(raw, valid_ids=valid_ids)


# === Streaming (M8) =============================================


class _JsonAnswerExtractor:
    """Stateful tokenizer that extracts the `answer` string field from a
    streamed JSON object, yielding decoded chunks as they become available.

    The extractor is tolerant: if the upstream emits anything other than the
    expected JSON shape, it simply yields nothing until the final ``meta``
    event surfaces the structured envelope.
    """

    _START_RE = re.compile(r'"answer"\s*:\s*"')

    def __init__(self) -> None:
        self.buf: str = ""
        self.answer_start_abs: int = -1
        self.cursor: int = -1  # absolute index of next byte to consume
        self.closed: bool = False

    def feed(self, chunk: str) -> str:
        """Append a chunk; return any new fully-decoded answer text."""
        if self.closed:
            self.buf += chunk
            return ""

        self.buf += chunk

        if self.answer_start_abs < 0:
            m = self._START_RE.search(self.buf)
            if not m:
                return ""
            self.answer_start_abs = m.end()
            self.cursor = self.answer_start_abs

        out: list[str] = []
        i = self.cursor
        while i < len(self.buf):
            c = self.buf[i]
            if c == "\\":
                if i + 1 >= len(self.buf):
                    break  # need more bytes
                nxt = self.buf[i + 1]
                if nxt == "n":
                    out.append("\n")
                elif nxt == "t":
                    out.append("\t")
                elif nxt == 'r':
                    out.append("\r")
                elif nxt == '"':
                    out.append('"')
                elif nxt == "\\":
                    out.append("\\")
                elif nxt == "/":
                    out.append("/")
                elif nxt == "u":
                    if i + 5 >= len(self.buf):
                        break  # need 4 hex digits
                    try:
                        out.append(chr(int(self.buf[i + 2 : i + 6], 16)))
                    except ValueError:
                        out.append(self.buf[i : i + 6])
                    i += 6
                    continue
                else:
                    out.append(nxt)
                i += 2
                continue
            if c == '"':
                self.closed = True
                i += 1
                break
            out.append(c)
            i += 1

        self.cursor = i
        return "".join(out)


def chat_with_report_stream(
    *,
    report_markdown: str,
    brand: str,
    mode: str,
    question: str,
    history: Optional[List[ChatMessage]] = None,
    client: Optional[MistralClient] = None,
    temperature: float = 0.2,
) -> Iterator[Tuple[str, object]]:
    """Streaming variant of :func:`chat_with_report`.

    Yields tuples ``("token", str)`` while the assistant is writing the
    ``answer`` field, then a final ``("meta", ChatAnswer)`` with citations
    and confidence parsed from the complete JSON object.
    """
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

    system = SYSTEM_TEMPLATE.format(
        brand=brand or "Brand",
        mode=mode or "quick",
        sections_list=_sections_to_prompt_list(sections),
        report=indexed,
    )
    messages: list[dict] = [{"role": "system", "content": system}]
    trimmed = (history or [])[-MAX_HISTORY_TURNS * 2 :]
    for m in trimmed:
        messages.append({"role": m.role, "content": m.content})
    messages.append({"role": "user", "content": question.strip()})

    extractor = _JsonAnswerExtractor()
    try:
        for chunk in client.chat_messages_stream(
            messages, temperature=temperature, response_format_json=True
        ):
            decoded = extractor.feed(chunk)
            if decoded:
                yield ("token", decoded)
    except LLMError as exc:
        raise ChatError(str(exc)) from exc

    final = _parse_answer(extractor.buf, valid_ids=valid_ids)
    yield ("meta", final)


# === Parsing / validation =======================================


def _parse_answer(raw: str, *, valid_ids: set[str]) -> ChatAnswer:
    """Tolerant JSON parse → ChatAnswer; fallback to plain-text envelope."""
    text = (raw or "").strip()
    # Strip eventual ```json fences
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    data: Optional[dict] = None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            data = parsed
    except json.JSONDecodeError:
        data = None

    if data is None:
        # Plain text fallback: synthesize a low-confidence envelope.
        return ChatAnswer(
            answer=raw.strip() or "(risposta vuota)",
            citations=[],
            confidence="low",
            out_of_scope=False,
        )

    answer = str(data.get("answer") or "").strip()
    if not answer:
        answer = "(risposta vuota)"

    raw_cits = data.get("citations") or []
    citations: list[str] = []
    if isinstance(raw_cits, list):
        for c in raw_cits:
            cid = str(c).strip()
            if cid in valid_ids and cid not in citations:
                citations.append(cid)

    conf_raw = str(data.get("confidence") or "medium").strip().lower()
    confidence: Confidence = conf_raw if conf_raw in ("low", "medium", "high") else "medium"  # type: ignore[assignment]

    out_of_scope = bool(data.get("out_of_scope"))
    if out_of_scope:
        citations = []  # forced consistency

    return ChatAnswer(
        answer=answer,
        citations=citations,
        confidence=confidence,
        out_of_scope=out_of_scope,
    )


def _safe_client() -> Optional[MistralClient]:
    try:
        return MistralClient()
    except LLMError:
        return None
