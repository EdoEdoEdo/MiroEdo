"""
Zep Graph paging helpers.

Ported from MiroFish `app/utils/zep_paging.py`. Zep's node/edge list endpoints
use UUID cursor pagination; this module hides that detail.
"""

from __future__ import annotations

import time
from typing import Any, Callable, List, Optional

from app.engine.utils.logger import get_logger

logger = get_logger("miroedo.engine.zep_paging")

# Imported lazily — module is only loaded when zep_cloud is available
from zep_cloud import InternalServerError  # type: ignore
from zep_cloud.client import Zep  # type: ignore

_DEFAULT_PAGE_SIZE = 100
_MAX_NODES = 2000
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_RETRY_DELAY = 2.0


def _fetch_page_with_retry(
    api_call: Callable[..., List[Any]],
    *args: Any,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    retry_delay: float = _DEFAULT_RETRY_DELAY,
    page_description: str = "page",
    **kwargs: Any,
) -> List[Any]:
    if max_retries < 1:
        raise ValueError("max_retries must be >= 1")

    last_exc: Optional[Exception] = None
    delay = retry_delay
    for attempt in range(max_retries):
        try:
            return api_call(*args, **kwargs)
        except (ConnectionError, TimeoutError, OSError, InternalServerError) as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                logger.warning(
                    f"Zep {page_description} attempt {attempt + 1} failed: "
                    f"{str(exc)[:100]}, retrying in {delay:.1f}s..."
                )
                time.sleep(delay)
                delay *= 2
            else:
                logger.error(
                    f"Zep {page_description} failed after {max_retries} attempts: {exc}"
                )
    assert last_exc is not None
    raise last_exc


def fetch_all_nodes(
    client: Zep,
    graph_id: str,
    page_size: int = _DEFAULT_PAGE_SIZE,
    max_items: int = _MAX_NODES,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    retry_delay: float = _DEFAULT_RETRY_DELAY,
) -> List[Any]:
    all_nodes: List[Any] = []
    cursor: Optional[str] = None
    page = 0

    while True:
        kwargs: dict = {"limit": page_size}
        if cursor is not None:
            kwargs["uuid_cursor"] = cursor
        page += 1
        batch = _fetch_page_with_retry(
            client.graph.node.get_by_graph_id,
            graph_id,
            max_retries=max_retries,
            retry_delay=retry_delay,
            page_description=f"fetch nodes page {page} (graph={graph_id})",
            **kwargs,
        )
        if not batch:
            break
        all_nodes.extend(batch)
        if len(all_nodes) >= max_items:
            all_nodes = all_nodes[:max_items]
            logger.warning(f"Node count limit reached ({max_items}) for graph {graph_id}")
            break
        if len(batch) < page_size:
            break
        cursor = getattr(batch[-1], "uuid_", None) or getattr(batch[-1], "uuid", None)
        if cursor is None:
            logger.warning(f"Node missing uuid; stopping pagination at {len(all_nodes)}")
            break
    return all_nodes


def fetch_all_edges(
    client: Zep,
    graph_id: str,
    page_size: int = _DEFAULT_PAGE_SIZE,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    retry_delay: float = _DEFAULT_RETRY_DELAY,
) -> List[Any]:
    all_edges: List[Any] = []
    cursor: Optional[str] = None
    page = 0

    while True:
        kwargs: dict = {"limit": page_size}
        if cursor is not None:
            kwargs["uuid_cursor"] = cursor
        page += 1
        batch = _fetch_page_with_retry(
            client.graph.edge.get_by_graph_id,
            graph_id,
            max_retries=max_retries,
            retry_delay=retry_delay,
            page_description=f"fetch edges page {page} (graph={graph_id})",
            **kwargs,
        )
        if not batch:
            break
        all_edges.extend(batch)
        if len(batch) < page_size:
            break
        cursor = getattr(batch[-1], "uuid_", None) or getattr(batch[-1], "uuid", None)
        if cursor is None:
            logger.warning(f"Edge missing uuid; stopping pagination at {len(all_edges)}")
            break
    return all_edges
