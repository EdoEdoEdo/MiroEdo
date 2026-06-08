"""
Zep Entity Reader.

Ported from MiroFish `app/services/zep_entity_reader.py`. Reads all nodes
from a Zep graph and filters those whose `labels` contain at least one
non-default label (i.e. anything other than `Entity`/`Node`).

Differences vs source:
- Accepts a pre-built Zep client (injection-friendly, optional dep)
- `EntityNode` / `FilteredEntities` imported from `app.engine.types`
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional, TypeVar

from app.engine.types import EntityNode, FilteredEntities
from app.engine.utils.logger import get_logger
from app.engine.zep.paging import fetch_all_edges, fetch_all_nodes

logger = get_logger("miroedo.engine.zep_entity_reader")

T = TypeVar("T")


class ZepEntityReader:
    def __init__(self, zep_client: Any) -> None:
        """
        Args:
            zep_client: an instance of `zep_cloud.client.Zep`
        """
        if zep_client is None:
            raise ValueError("zep_client is required")
        self.client = zep_client

    def _call_with_retry(
        self,
        func: Callable[[], T],
        operation_name: str,
        max_retries: int = 3,
        initial_delay: float = 2.0,
    ) -> T:
        last_exc: Optional[Exception] = None
        delay = initial_delay
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as exc:
                last_exc = exc
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Zep {operation_name} attempt {attempt + 1} failed: "
                        f"{str(exc)[:100]}, retrying in {delay:.1f}s"
                    )
                    time.sleep(delay)
                    delay *= 2
                else:
                    logger.error(
                        f"Zep {operation_name} failed after {max_retries} attempts: {exc}"
                    )
        assert last_exc is not None
        raise last_exc

    def get_all_nodes(self, graph_id: str) -> List[Dict[str, Any]]:
        logger.info(f"Fetching all nodes for graph {graph_id}")
        nodes = fetch_all_nodes(self.client, graph_id)
        out = []
        for n in nodes:
            out.append(
                {
                    "uuid": getattr(n, "uuid_", None) or getattr(n, "uuid", ""),
                    "name": n.name or "",
                    "labels": n.labels or [],
                    "summary": n.summary or "",
                    "attributes": n.attributes or {},
                }
            )
        logger.info(f"Fetched {len(out)} nodes")
        return out

    def get_all_edges(self, graph_id: str) -> List[Dict[str, Any]]:
        logger.info(f"Fetching all edges for graph {graph_id}")
        edges = fetch_all_edges(self.client, graph_id)
        out = []
        for e in edges:
            out.append(
                {
                    "uuid": getattr(e, "uuid_", None) or getattr(e, "uuid", ""),
                    "name": e.name or "",
                    "fact": e.fact or "",
                    "source_node_uuid": e.source_node_uuid,
                    "target_node_uuid": e.target_node_uuid,
                    "attributes": e.attributes or {},
                }
            )
        logger.info(f"Fetched {len(out)} edges")
        return out

    def get_node_edges(self, node_uuid: str) -> List[Dict[str, Any]]:
        try:
            edges = self._call_with_retry(
                func=lambda: self.client.graph.node.get_entity_edges(node_uuid=node_uuid),
                operation_name=f"get node edges ({node_uuid[:8]}...)",
            )
            return [
                {
                    "uuid": getattr(e, "uuid_", None) or getattr(e, "uuid", ""),
                    "name": e.name or "",
                    "fact": e.fact or "",
                    "source_node_uuid": e.source_node_uuid,
                    "target_node_uuid": e.target_node_uuid,
                    "attributes": e.attributes or {},
                }
                for e in edges
            ]
        except Exception as exc:
            logger.warning(f"Get edges for {node_uuid} failed: {exc}")
            return []

    def filter_defined_entities(
        self,
        graph_id: str,
        defined_entity_types: Optional[List[str]] = None,
        enrich_with_edges: bool = True,
    ) -> FilteredEntities:
        logger.info(f"Filtering entities for graph {graph_id}")
        all_nodes = self.get_all_nodes(graph_id)
        total = len(all_nodes)
        all_edges = self.get_all_edges(graph_id) if enrich_with_edges else []
        node_map = {n["uuid"]: n for n in all_nodes}

        entities: List[EntityNode] = []
        types_found = set()

        for node in all_nodes:
            labels = node.get("labels", [])
            custom = [l for l in labels if l not in ("Entity", "Node")]
            if not custom:
                continue
            if defined_entity_types:
                matching = [l for l in custom if l in defined_entity_types]
                if not matching:
                    continue
                entity_type = matching[0]
            else:
                entity_type = custom[0]
            types_found.add(entity_type)

            entity = EntityNode(
                uuid=node["uuid"],
                name=node["name"],
                labels=labels,
                summary=node["summary"],
                attributes=node["attributes"],
            )

            if enrich_with_edges:
                related_edges: List[Dict[str, Any]] = []
                related_uuids = set()
                for edge in all_edges:
                    if edge["source_node_uuid"] == node["uuid"]:
                        related_edges.append(
                            {
                                "direction": "outgoing",
                                "edge_name": edge["name"],
                                "fact": edge["fact"],
                                "target_node_uuid": edge["target_node_uuid"],
                            }
                        )
                        related_uuids.add(edge["target_node_uuid"])
                    elif edge["target_node_uuid"] == node["uuid"]:
                        related_edges.append(
                            {
                                "direction": "incoming",
                                "edge_name": edge["name"],
                                "fact": edge["fact"],
                                "source_node_uuid": edge["source_node_uuid"],
                            }
                        )
                        related_uuids.add(edge["source_node_uuid"])
                entity.related_edges = related_edges

                related_nodes: List[Dict[str, Any]] = []
                for ru in related_uuids:
                    rn = node_map.get(ru)
                    if rn:
                        related_nodes.append(
                            {
                                "uuid": rn["uuid"],
                                "name": rn["name"],
                                "labels": rn["labels"],
                                "summary": rn.get("summary", ""),
                            }
                        )
                entity.related_nodes = related_nodes

            entities.append(entity)

        logger.info(
            f"Filtered: total={total}, kept={len(entities)}, types={types_found}"
        )
        return FilteredEntities(
            entities=entities,
            entity_types=types_found,
            total_count=total,
            filtered_count=len(entities),
        )

    def get_entities_by_type(
        self,
        graph_id: str,
        entity_type: str,
        enrich_with_edges: bool = True,
    ) -> List[EntityNode]:
        return self.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=[entity_type],
            enrich_with_edges=enrich_with_edges,
        ).entities
