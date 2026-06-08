"""Ontology generation LLM-driven per arricchire entità/relazioni brand-centriche.

Ispirato a MiroFish/services/ontology_generator.py ma adattato a brand monitoring
(no public-opinion focus, ma stakeholder mapping per simulazione audience).

L'ontologia generata:
- Definisce 6-10 tipi di entità (sia "concrete" — Brand, Competitor, MediaOutlet — sia
  ruoli sociali — Customer, Activist, Regulator) che possono "parlare" sui social.
- Definisce 4-8 tipi di relazione tra queste entità (COMPETES_WITH, COMPLAINS_ABOUT, ...).
- Ritorna un summary in italiano per il report markdown.

Usata da pipeline.py per:
1. Arricchire knowledge_graph anche per source NON-tabular (document/manual/PDF).
2. Guidare la generazione personas in OASIS simulazione.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.llm.mistral import MistralClient

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """Sei un esperto di knowledge graph e modellazione di stakeholder per brand monitoring.

Il tuo compito: data una descrizione di brand e contesto di business, progetta una **ontologia di entità e relazioni** che rappresenti gli attori reali che parlano del brand sui social media.

**Output: SOLO JSON valido, nessun altro testo.**

## Cosa è un'entità

Un'entità è un attore REALE che può pubblicare sui social media, non un concetto astratto.

✅ Esempi validi:
- Specifici tipi di consumatori (Famiglia, GenZ, MillennialSalutista, PMI, ClienteRetail)
- Brand stesso e competitor (Brand, Competitor)
- Media e creator (MediaOutlet, Influencer, Giornalista)
- Organizzazioni di pressione (NGO, AssociazioneConsumatori, Regulator)
- Partner/distributori (Retailer, Distributor)

❌ NON entità:
- Topic/concetti ("Sostenibilità", "Prezzo") — questi sono già nei topics del seed
- Sentimenti ("Insoddisfazione")
- Eventi ("Lancio prodotto")

## Output format

```json
{
  "entity_types": [
    {
      "name": "PascalCase",
      "description": "Breve descrizione in italiano (max 120 char)",
      "role_in_simulation": "Come questa entità interagisce coi social (max 80 char)",
      "examples": ["esempio1", "esempio2"]
    }
  ],
  "edge_types": [
    {
      "name": "UPPER_SNAKE_CASE",
      "description": "Breve descrizione in italiano (max 100 char)",
      "source_targets": [
        {"source": "EntityTypeA", "target": "EntityTypeB"}
      ]
    }
  ],
  "analysis_summary": "Sintesi in italiano (3-5 frasi) della scelta ontologica e di come riflette il contesto del brand."
}
```

## Regole stringenti

1. **Esattamente 8 entity_types**. Le ultime 2 DEVONO essere `Person` (catch-all individuo) e `Organization` (catch-all organizzazione).
2. Le prime 6 entity_types DEVONO essere specifiche per il dominio del brand (NON generiche).
3. **Da 4 a 8 edge_types**. Ogni edge deve referenziare entity_types definiti.
4. Nomi entità SEMPRE in inglese PascalCase. Nomi relazioni SEMPRE in inglese UPPER_SNAKE_CASE.
5. `description`, `role_in_simulation`, `analysis_summary` in ITALIANO.
6. `examples`: 2-4 esempi concreti di nomi/casi reali (in italiano).
"""


USER_TEMPLATE = """## Brand

Nome: {brand}
Mercato: {market}
Lingua: {language}

## Contesto utente (richiesta strategica)

{scenario_brief}

## Topic principali emersi dal dataset

{topics_block}

## Segmenti audience identificati

{segments_block}

---

Progetta un'ontologia di 8 entity_types (di cui 6 specifici al dominio + Person + Organization come catch-all) e 4-8 edge_types.
Le entità specifiche DEVONO riflettere gli attori che parlano realmente di questo brand: tipi di consumatore, competitor, media, organizzazioni di pressione, partner. NON topic astratti.

Ricorda: rispondi SOLO con un JSON valido.
"""


def _to_pascal_case(name: str) -> str:
    parts = re.split(r"[^a-zA-Z0-9]+", name)
    words: list[str] = []
    for part in parts:
        words.extend(re.sub(r"([a-z])([A-Z])", r"\1_\2", part).split("_"))
    return "".join(w.capitalize() for w in words if w) or "Unknown"


def _to_upper_snake(name: str) -> str:
    parts = re.split(r"[^a-zA-Z0-9]+", name)
    words: list[str] = []
    for part in parts:
        words.extend(re.sub(r"([a-z])([A-Z])", r"\1_\2", part).split("_"))
    return "_".join(w.upper() for w in words if w) or "UNKNOWN"


def _attr_or_key(obj: Any, key: str, default: Any) -> Any:
    """Read ``key`` from a Pydantic model (attribute) or a dict.

    Uses ``hasattr``/``isinstance`` instead of truthy fallback so that valid
    falsy values like ``0``, ``0.0`` and ``""`` do not trigger a dict lookup
    on objects that have no ``.get`` (which would raise ``AttributeError``).
    """
    if hasattr(obj, key):
        val = getattr(obj, key)
        return default if val is None else val
    if isinstance(obj, dict):
        val = obj.get(key, default)
        return default if val is None else val
    return default


def _format_topics(topics: list[Any]) -> str:
    if not topics:
        return "(nessuno)"
    rows = []
    for t in topics[:12]:
        name = _attr_or_key(t, "name", "—")
        mentions = _attr_or_key(t, "mentions", 0)
        sentiment = _attr_or_key(t, "sentiment_score", 0.0)
        rows.append(f"- {name} ({mentions} mention, sentiment {sentiment:+.2f})")
    return "\n".join(rows)


def _format_segments(segments: list[Any]) -> str:
    if not segments:
        return "(nessuno)"
    rows = []
    for s in segments[:8]:
        name = _attr_or_key(s, "name", "—")
        weight = _attr_or_key(s, "weight", 0.0)
        desc = _attr_or_key(s, "description", "")
        rows.append(f"- {name} ({weight:.0%}): {desc}")
    return "\n".join(rows)


def generate_ontology(
    *,
    brand: str,
    market: str,
    language: str,
    scenario_brief: str | None,
    topics: list[Any],
    segments: list[Any],
    client: MistralClient | None = None,
) -> dict[str, Any]:
    """Genera una ontologia per il brand. Fallisce gracefully restituendo {} su errore.

    Output shape:
        {
            "entity_types": [...],
            "edge_types": [...],
            "analysis_summary": "...",
            "model": "mistral-...",
            "status": "ok" | "skipped" | "error",
            "reason": "..."  # se non ok
        }
    """
    if client is None:
        try:
            client = MistralClient()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Ontology skipped: LLM client unavailable (%s)", exc)
            return {"status": "skipped", "reason": str(exc)}

    user_msg = USER_TEMPLATE.format(
        brand=brand,
        market=market,
        language=language,
        scenario_brief=(scenario_brief or "(nessuno specificato)").strip(),
        topics_block=_format_topics(topics),
        segments_block=_format_segments(segments),
    )

    try:
        raw = client.chat(
            system=SYSTEM_PROMPT,
            user=user_msg,
            temperature=0.3,
            response_format_json=True,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("Ontology generation failed: %s", exc)
        return {"status": "error", "reason": str(exc)}

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Ontology LLM output not JSON: %s", exc)
        return {"status": "error", "reason": "invalid_json"}

    return _validate_and_normalize(data, model=client.config.model)


def _validate_and_normalize(data: dict[str, Any], *, model: str) -> dict[str, Any]:
    entity_types = data.get("entity_types") or []
    edge_types = data.get("edge_types") or []

    # Normalizza nomi e attributi minimi.
    normalized_entities: list[dict[str, Any]] = []
    valid_names: set[str] = set()
    for e in entity_types:
        if not isinstance(e, dict) or "name" not in e:
            continue
        name = _to_pascal_case(str(e["name"]))
        valid_names.add(name)
        normalized_entities.append(
            {
                "name": name,
                "description": str(e.get("description", ""))[:200],
                "role_in_simulation": str(e.get("role_in_simulation", ""))[:160],
                "examples": [str(x)[:80] for x in (e.get("examples") or [])][:5],
            }
        )

    normalized_edges: list[dict[str, Any]] = []
    for ed in edge_types:
        if not isinstance(ed, dict) or "name" not in ed:
            continue
        st = ed.get("source_targets") or []
        valid_pairs = []
        for pair in st:
            if not isinstance(pair, dict):
                continue
            s = _to_pascal_case(str(pair.get("source", "")))
            t = _to_pascal_case(str(pair.get("target", "")))
            if s in valid_names and t in valid_names:
                valid_pairs.append({"source": s, "target": t})
        if not valid_pairs:
            continue
        normalized_edges.append(
            {
                "name": _to_upper_snake(str(ed["name"])),
                "description": str(ed.get("description", ""))[:200],
                "source_targets": valid_pairs,
            }
        )

    return {
        "status": "ok" if normalized_entities else "error",
        "entity_types": normalized_entities,
        "edge_types": normalized_edges,
        "analysis_summary": str(data.get("analysis_summary", ""))[:1000],
        "model": model,
        "reason": "" if normalized_entities else "no_entities",
    }


def ontology_to_graph_nodes(
    ontology: dict[str, Any], brand: str
) -> tuple[list[dict], list[dict]]:
    """Converte un'ontologia in nodi/link compatibili col KnowledgeGraph frontend.

    Crea: 1 nodo Brand + 1 nodo per ogni entity_type (con qualche esempio) +
    link basati sugli edge_types.
    Etichettati come `inferred: true` per chiarire che NON vengono dal dataset.
    """
    if ontology.get("status") != "ok":
        return [], []

    nodes: list[dict] = []
    brand_id = f"brand::{brand}"
    nodes.append(
        {
            "id": brand_id,
            "type": "Brand",
            "label": brand,
            "weight": 100,
            "sentiment": 0.0,
            "inferred": True,
        }
    )

    type_to_id: dict[str, str] = {"Brand": brand_id}
    for ent in ontology["entity_types"]:
        type_name = ent["name"]
        if type_name == "Brand":
            continue
        node_id = f"ontology::{type_name}"
        type_to_id[type_name] = node_id
        nodes.append(
            {
                "id": node_id,
                "type": type_name,
                "label": type_name,
                "weight": 10,
                "sentiment": 0.0,
                "inferred": True,
                "examples": ent.get("examples", []),
            }
        )

    links: list[dict] = []
    seen: set[tuple[str, str, str]] = set()
    for ed in ontology["edge_types"]:
        for pair in ed["source_targets"]:
            src = type_to_id.get(pair["source"])
            tgt = type_to_id.get(pair["target"])
            if not src or not tgt or src == tgt:
                continue
            key = (src, tgt, ed["name"])
            if key in seen:
                continue
            seen.add(key)
            links.append(
                {
                    "source": src,
                    "target": tgt,
                    "type": ed["name"],
                    "weight": 1,
                    "inferred": True,
                }
            )

    return nodes, links
