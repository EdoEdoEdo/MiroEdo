"""Client Mistral minimale (chat completions, sync, 1 retry)."""

from __future__ import annotations

import json
import time
from typing import Iterator, Optional

import httpx

from app.config import LLMConfig, load_llm_config


class LLMError(RuntimeError):
    """Errore generico durante la chiamata LLM."""


class MistralClient:
    """Wrapper sincrono attorno all'API Mistral (compatibile OpenAI chat-completions)."""

    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        self.config = config or load_llm_config()
        if not self.config.api_key:
            raise LLMError("LLM_API_KEY non configurata")

    def chat(
        self,
        system: str,
        user: str,
        *,
        temperature: float = 0.3,
        response_format_json: bool = False,
    ) -> str:
        """Esegue una chat completion single-turn e ritorna il contenuto testuale."""
        return self.chat_messages(
            [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=temperature,
            response_format_json=response_format_json,
        )

    def chat_messages(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.3,
        response_format_json: bool = False,
    ) -> str:
        """Multi-turn chat completion: passa la lista completa di messages."""
        payload: dict = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
        }
        if response_format_json:
            payload["response_format"] = {"type": "json_object"}

        url = f"{self.config.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        last_err: Optional[Exception] = None
        for attempt in range(self.config.max_retries + 1):
            try:
                with httpx.Client(timeout=self.config.timeout_s) as client:
                    resp = client.post(url, json=payload, headers=headers)
                    resp.raise_for_status()
                    data = resp.json()
                    return data["choices"][0]["message"]["content"].strip()
            except (httpx.HTTPError, KeyError, IndexError) as exc:
                last_err = exc
                if attempt < self.config.max_retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise LLMError(f"Chiamata LLM fallita: {exc}") from exc

        raise LLMError(f"Chiamata LLM fallita: {last_err}")

    def chat_messages_stream(
        self,
        messages: list[dict],
        *,
        temperature: float = 0.3,
        response_format_json: bool = False,
    ) -> Iterator[str]:
        """Stream chat completion deltas. Yields text chunks as they arrive.

        Network errors raise LLMError after exhausting retries. The generator
        must be fully consumed (or closed) so the HTTP connection is released.
        """
        payload: dict = {
            "model": self.config.model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if response_format_json:
            payload["response_format"] = {"type": "json_object"}

        url = f"{self.config.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream",
        }

        last_err: Optional[Exception] = None
        for attempt in range(self.config.max_retries + 1):
            try:
                with httpx.stream(
                    "POST",
                    url,
                    json=payload,
                    headers=headers,
                    timeout=self.config.timeout_s,
                ) as resp:
                    resp.raise_for_status()
                    for raw in resp.iter_lines():
                        line = raw if isinstance(raw, str) else raw.decode("utf-8")
                        line = line.strip()
                        if not line or not line.startswith("data: "):
                            continue
                        data_part = line[6:]
                        if data_part == "[DONE]":
                            return
                        try:
                            obj = json.loads(data_part)
                            delta = (
                                obj.get("choices", [{}])[0]
                                .get("delta", {})
                                .get("content")
                            )
                            if delta:
                                yield delta
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
                    return
            except httpx.HTTPError as exc:
                last_err = exc
                if attempt < self.config.max_retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise LLMError(f"Streaming LLM call failed: {exc}") from exc

        raise LLMError(f"Streaming LLM call failed: {last_err}")

    def chat_json(self, system: str, user: str, *, temperature: float = 0.2) -> dict:
        """Variante che richiede JSON e parsa il risultato (con fallback)."""
        raw = self.chat(system, user, temperature=temperature, response_format_json=True)
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            # Strip eventuali code fence ```json ... ```
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.strip("`")
                if cleaned.lower().startswith("json"):
                    cleaned = cleaned[4:].strip()
            try:
                return json.loads(cleaned)
            except json.JSONDecodeError as exc:
                raise LLMError(f"Risposta LLM non è JSON valido: {raw[:200]}") from exc
