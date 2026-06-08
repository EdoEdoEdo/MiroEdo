"""
Minimal OASIS runner — drives a tiny Reddit simulation from a list of profiles
and a list of seed posts, then returns aggregated metrics.

Why a "minimal" runner?
- The full MiroFish simulation runner (parallel_runner, multi-platform, IPC,
  Zep memory) is over-engineered for the "ReportPipeline full mode" use case.
- Here we only need: spin up agents → inject N seed posts → run K rounds →
  read the SQLite `trace` table → return a structured summary.
- The summary feeds the markdown report (M3.3).

Cost control:
- Uses `ManualAction` for seeding (no LLM cost).
- Uses `LLMAction` for reactions only if `enable_llm_reactions=True`.
- Total OpenAI cost for default config (10 agents × 2 rounds with
  gpt-4o-mini): a few cents.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import sqlite3
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class SimulationSummary:
    """Aggregate result of a minimal OASIS run."""

    profiles_count: int
    initial_posts_count: int
    rounds_executed: int
    total_actions: int
    actions_by_type: Dict[str, int]
    sample_posts: List[Dict[str, Any]] = field(default_factory=list)
    sample_comments: List[Dict[str, Any]] = field(default_factory=list)
    network_graph: Dict[str, Any] = field(default_factory=dict)
    sqlite_path: str = ""
    used_llm_reactions: bool = False
    # Cost telemetry (M7)
    llm_calls_made: int = 0
    llm_calls_capped: bool = False
    llm_sample_rate: float = 0.0
    llm_max_calls: int = 0
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def plan_llm_reactions(
    *,
    n_agents: int,
    sample_rate: float,
    budget_left: int,
    rng: random.Random,
) -> Dict[str, Any]:
    """Pure helper: decide how many agents this round talk to the LLM.

    Returns a dict with:
        sample_size: int  -- how many agents will use LLMAction this round
        capped: bool      -- True iff sample_size was reduced because of budget
        picked_indices: List[int]  -- the indices in [0..n_agents) sampled
    """
    sample_rate = max(0.0, min(1.0, sample_rate))
    n_agents = max(0, int(n_agents))
    budget_left = max(0, int(budget_left))
    if n_agents == 0 or budget_left == 0 or sample_rate == 0.0:
        return {"sample_size": 0, "capped": budget_left == 0, "picked_indices": []}
    target = max(1, int(round(n_agents * sample_rate)))
    sample_size = min(target, budget_left, n_agents)
    capped = sample_size < target
    picked = rng.sample(range(n_agents), k=sample_size)
    return {"sample_size": sample_size, "capped": capped, "picked_indices": picked}


def run_minimal_simulation(
    *,
    profiles: List[Dict[str, Any]],
    seed_posts: List[str],
    workspace_dir: Path | str,
    rounds: int = 1,
    enable_llm_reactions: bool = False,
    openai_api_key: Optional[str] = None,
    openai_model: str = "gpt-4o-mini",
    llm_sample_rate: float = 0.3,
    llm_max_calls: int = 100,
    rng_seed: Optional[int] = None,
    actions_log_path: Optional[Path | str] = None,
) -> SimulationSummary:
    """
    Synchronous wrapper around an async OASIS run.

    Cost governance (M7):
        - ``llm_sample_rate`` (0..1): per round, only this fraction of agents
          uses ``LLMAction``. The others use ``DO_NOTHING``. Defaults to 0.3.
        - ``llm_max_calls``: global cap on the total number of LLM-driven
          reactions across the whole run. When the cap is reached, every
          remaining agent falls back to ``DO_NOTHING``.
        - ``rng_seed``: optional integer for deterministic sampling in tests.

    Args:
        profiles: list of Reddit profile dicts (output of
            ``OasisProfileGenerator(...).to_reddit_format()``).
        seed_posts: text content for each seed post created at round 0.
        workspace_dir: where the SQLite DB and any artifacts are written.
        rounds: number of ``env.step()`` calls AFTER the initial seeding.
        enable_llm_reactions: master switch. When False, all agents
            ``DO_NOTHING`` and no OpenAI credits are spent.
        openai_api_key: required only if ``enable_llm_reactions=True``. If
            None, falls back to env var ``OPENAI_API_KEY``.
    """
    workspace = Path(workspace_dir)
    workspace.mkdir(parents=True, exist_ok=True)
    db_path = workspace / "oasis.db"
    if db_path.exists():
        db_path.unlink()
    profile_path = workspace / "profiles.json"
    profile_path.write_text(json.dumps(profiles, ensure_ascii=False), encoding="utf-8")

    log_path: Optional[Path] = None
    if actions_log_path is not None:
        log_path = Path(actions_log_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        # Truncate any previous file so the stream starts from offset 0.
        log_path.write_text("", encoding="utf-8")

    return asyncio.run(
        _run_async(
            profile_path=profile_path,
            profiles_count=len(profiles),
            seed_posts=seed_posts,
            db_path=db_path,
            rounds=rounds,
            enable_llm_reactions=enable_llm_reactions,
            openai_api_key=openai_api_key or os.environ.get("OPENAI_API_KEY"),
            openai_model=openai_model,
            llm_sample_rate=max(0.0, min(1.0, llm_sample_rate)),
            llm_max_calls=max(0, int(llm_max_calls)),
            rng_seed=rng_seed,
            actions_log_path=log_path,
        )
    )


async def _run_async(
    *,
    profile_path: Path,
    profiles_count: int,
    seed_posts: List[str],
    db_path: Path,
    rounds: int,
    enable_llm_reactions: bool,
    openai_api_key: Optional[str],
    openai_model: str,
    llm_sample_rate: float,
    llm_max_calls: int,
    rng_seed: Optional[int],
    actions_log_path: Optional[Path] = None,
) -> SimulationSummary:
    # Imports here so missing OASIS doesn't break the module on Python 3.9.
    import oasis
    from camel.models import ModelFactory
    from camel.types import ModelPlatformType, ModelType
    from oasis import ActionType, LLMAction, ManualAction, generate_reddit_agent_graph

    notes: List[str] = []
    rng = random.Random(rng_seed)

    if enable_llm_reactions and not openai_api_key:
        enable_llm_reactions = False
        notes.append("LLM reactions disabled: OPENAI_API_KEY not set")
    if enable_llm_reactions and llm_max_calls <= 0:
        enable_llm_reactions = False
        notes.append("LLM reactions disabled: llm_max_calls=0")

    model_type, model_platform = _resolve_model(openai_model, notes)
    model = ModelFactory.create(
        model_platform=model_platform,
        model_type=model_type,
        api_key=openai_api_key or "sk-noop-setup-only",
    )

    available_actions = [
        ActionType.CREATE_POST,
        ActionType.CREATE_COMMENT,
        ActionType.LIKE_POST,
        ActionType.DISLIKE_POST,
    ]

    agent_graph = await generate_reddit_agent_graph(
        profile_path=str(profile_path),
        model=model,
        available_actions=available_actions,
    )

    # Patch: alza max_iteration cos\u00ec ogni agente pu\u00f2 fare ReAct multi-step
    # (refresh interno + decisione + tool call). Con max_iteration=1 il LLM
    # spesso si ferma al primo "refresh" e non agisce mai.
    for _uid, agent in agent_graph.get_agents():
        agent.max_iteration = 5

    env = oasis.make(
        agent_graph=agent_graph,
        platform=oasis.DefaultPlatformType.REDDIT,
        database_path=str(db_path),
    )

    llm_calls_made = 0
    llm_calls_capped = False

    # JSONL streaming: append per-action rows after each env.step() so the UI
    # can tail them in real time (MiroFish-style).
    last_rowid = 0

    def _log_marker(event: str, **extra: Any) -> None:
        if actions_log_path is None:
            return
        rec = {"event": event, **extra}
        with actions_log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    def _flush_new_actions(round_num: int) -> int:
        nonlocal last_rowid
        if actions_log_path is None:
            return 0
        try:
            with sqlite3.connect(str(db_path)) as conn:
                conn.row_factory = sqlite3.Row
                rows = conn.execute(
                    "SELECT rowid, user_id, action, info, created_at "
                    "FROM trace WHERE rowid > ? ORDER BY rowid",
                    (last_rowid,),
                ).fetchall()
        except sqlite3.OperationalError:
            return 0
        if not rows:
            return 0
        with actions_log_path.open("a", encoding="utf-8") as fh:
            for r in rows:
                rec = {
                    "event": "action",
                    "round": round_num,
                    "rowid": int(r["rowid"]),
                    "agent_id": int(r["user_id"]) if r["user_id"] is not None else None,
                    "action": str(r["action"]),
                    "info": r["info"],
                    "created_at": r["created_at"],
                }
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                last_rowid = int(r["rowid"])
        return len(rows)

    try:
        await env.reset()
        _log_marker(
            "simulation_start",
            profiles=profiles_count,
            rounds=rounds,
            seed_posts=len(seed_posts),
        )

        # === Round 0: seed initial posts via ManualAction ===
        seed_actions: Dict[Any, List[ManualAction]] = {}
        for idx, content in enumerate(seed_posts):
            agent = env.agent_graph.get_agent(idx % max(profiles_count, 1))
            seed_actions.setdefault(agent, []).append(
                ManualAction(
                    action_type=ActionType.CREATE_POST,
                    action_args={"content": content},
                )
            )
        if seed_actions:
            seed_actions_flat = {
                a: (acts[0] if len(acts) == 1 else acts) for a, acts in seed_actions.items()
            }
            _log_marker("round_start", round=0, kind="seed")
            await env.step(seed_actions_flat)
            n_flushed = _flush_new_actions(round_num=0)
            _log_marker("round_end", round=0, actions_count=n_flushed)

        # === Bootstrap engagement (round 0.5) ===
        # Senza like iniziali, i seed post arrivano nel feed con engagement=0
        # e il LLM tende a do_nothing. Forziamo ogni agente non-seed a likare
        # un seed post random: il LLM vedr\u00e0 contenuto "vivo" e sar\u00e0 pi\u00f9
        # propenso a commentare/likare a sua volta.
        if seed_posts and profiles_count > len(seed_posts):
            n_seed = len(seed_posts)
            boot_actions: Dict[Any, ManualAction] = {}
            for idx in range(n_seed, profiles_count):
                agent = env.agent_graph.get_agent(idx)
                post_id = rng.randint(1, n_seed)
                boot_actions[agent] = ManualAction(
                    action_type=ActionType.LIKE_POST,
                    action_args={"post_id": post_id},
                )
            if boot_actions:
                _log_marker("round_start", round=0, kind="bootstrap")
                await env.step(boot_actions)
                n_flushed = _flush_new_actions(round_num=0)
                _log_marker("round_end", round=0, actions_count=n_flushed)

        # === Reaction rounds ===
        rounds_executed = 0
        for _r in range(rounds):
            agents = list(env.agent_graph.get_agents())  # [(uid, agent), ...]
            n = len(agents)

            if enable_llm_reactions and llm_calls_made < llm_max_calls:
                plan = plan_llm_reactions(
                    n_agents=n,
                    sample_rate=llm_sample_rate,
                    budget_left=llm_max_calls - llm_calls_made,
                    rng=rng,
                )
                if plan["capped"]:
                    llm_calls_capped = True
                chosen = set(plan["picked_indices"])
                actions = {}
                for idx, (_uid, agent) in enumerate(agents):
                    if idx in chosen:
                        actions[agent] = LLMAction()
                        llm_calls_made += 1
                    else:
                        actions[agent] = ManualAction(
                            action_type=ActionType.DO_NOTHING, action_args={}
                        )
            else:
                if enable_llm_reactions and llm_calls_made >= llm_max_calls:
                    llm_calls_capped = True
                actions = {
                    agent: ManualAction(
                        action_type=ActionType.DO_NOTHING, action_args={}
                    )
                    for _, agent in agents
                }
            _log_marker("round_start", round=rounds_executed + 1, kind="reaction")
            await env.step(actions)
            rounds_executed += 1
            n_flushed = _flush_new_actions(round_num=rounds_executed)
            _log_marker(
                "round_end", round=rounds_executed, actions_count=n_flushed
            )
    finally:
        _log_marker("simulation_end", rounds=rounds_executed)
        await env.close()

    if llm_calls_capped:
        notes.append(
            f"LLM reaction budget reached: {llm_calls_made}/{llm_max_calls} calls used"
        )

    summary = _summarize(db_path)
    summary.profiles_count = profiles_count
    summary.initial_posts_count = len(seed_posts)
    summary.rounds_executed = rounds_executed
    summary.used_llm_reactions = enable_llm_reactions and llm_calls_made > 0
    summary.llm_calls_made = llm_calls_made
    summary.llm_calls_capped = llm_calls_capped
    summary.llm_sample_rate = llm_sample_rate if enable_llm_reactions else 0.0
    summary.llm_max_calls = llm_max_calls if enable_llm_reactions else 0
    summary.sqlite_path = str(db_path)
    summary.notes.extend(notes)
    return summary


def _resolve_model(model_name: str, notes: List[str]):
    """Map a string id to (camel ModelType, camel ModelPlatformType).

    Supports OpenAI native + Groq native (camel-ai handles base_url
    routing per-platform internally, regardless of `OPENAI_BASE_URL`).
    """
    from camel.types import ModelPlatformType, ModelType

    openai_map = {
        "gpt-4o-mini": ModelType.GPT_4O_MINI,
        "gpt-4o": ModelType.GPT_4O,
        "gpt-4-turbo": ModelType.GPT_4_TURBO,
        "gpt-3.5-turbo": ModelType.GPT_3_5_TURBO,
    }
    groq_map = {
        "llama-3.1-8b-instant": ModelType.GROQ_LLAMA_3_1_8B,
        "llama-3.3-70b-versatile": ModelType.GROQ_LLAMA_3_3_70B,
    }
    if model_name in openai_map:
        return openai_map[model_name], ModelPlatformType.OPENAI
    if model_name in groq_map:
        return groq_map[model_name], ModelPlatformType.GROQ
    notes.append(f"Unknown model '{model_name}', defaulting to gpt-4o-mini")
    return ModelType.GPT_4O_MINI, ModelPlatformType.OPENAI


def _resolve_model_type(model_name: str, notes: List[str]):
    """Legacy helper kept for backward compatibility (OpenAI only)."""
    return _resolve_model(model_name, notes)[0]


def _extract_network_graph(conn: sqlite3.Connection) -> Dict[str, Any]:
    """Build a node/link graph from the OASIS SQLite DB for visualization.

    Nodes are agents (one per user_id that appears in any trace).
    Each node carries an aggregate `action_count` and a `top_action` label.

    Links are directed agent→agent interactions, weighted by repetition:
    - LIKE_POST / DISLIKE_POST / REPOST → source likes target (post author)
    - CREATE_COMMENT → source comments on target's post
    - FOLLOW → source follows target
    - CREATE_POST is reflected only as a node attribute, not a link
    """
    # Author map: post_id -> author user_id
    post_author: Dict[int, int] = {}
    try:
        for row in conn.execute("SELECT post_id, user_id FROM post"):
            post_author[int(row["post_id"])] = int(row["user_id"])
    except sqlite3.OperationalError:
        pass

    # Aggregate node action counts
    node_actions: Dict[int, Dict[str, int]] = {}
    try:
        rows = conn.execute(
            "SELECT user_id, action, COUNT(*) AS n FROM trace GROUP BY user_id, action"
        ).fetchall()
    except sqlite3.OperationalError:
        rows = []
    for r in rows:
        uid = int(r["user_id"])
        node_actions.setdefault(uid, {})[r["action"]] = int(r["n"])

    # Aggregate edges by (source, target, type)
    edge_counter: Dict[tuple, int] = {}

    def _bump(src: int, dst: int, kind: str) -> None:
        if src == dst or dst < 0:
            return
        key = (src, dst, kind)
        edge_counter[key] = edge_counter.get(key, 0) + 1

    # Walk trace rows that reference a post or another user via the info JSON.
    try:
        trace_rows = conn.execute(
            "SELECT user_id, action, info FROM trace WHERE action IN "
            "('LIKE_POST','DISLIKE_POST','REPOST','CREATE_COMMENT','FOLLOW','UNFOLLOW')"
        ).fetchall()
    except sqlite3.OperationalError:
        trace_rows = []

    import json as _json
    for r in trace_rows:
        src = int(r["user_id"])
        action = r["action"]
        info = r["info"] or "{}"
        try:
            payload = _json.loads(info) if isinstance(info, str) else dict(info)
        except (ValueError, TypeError):
            payload = {}
        if action in {"LIKE_POST", "DISLIKE_POST", "REPOST", "CREATE_COMMENT"}:
            pid = payload.get("post_id")
            if pid is None:
                continue
            try:
                dst = post_author.get(int(pid))
            except (TypeError, ValueError):
                dst = None
            if dst is None:
                continue
            _bump(src, dst, action)
        elif action in {"FOLLOW", "UNFOLLOW"}:
            dst = payload.get("followee_id") or payload.get("user_id")
            if dst is None:
                continue
            try:
                _bump(src, int(dst), action)
            except (TypeError, ValueError):
                continue

    # Compose final graph
    all_node_ids = set(node_actions) | {p[0] for p in edge_counter} | {p[1] for p in edge_counter} | set(post_author.values())
    nodes = []
    for uid in sorted(all_node_ids):
        actions = node_actions.get(uid, {})
        total = sum(actions.values())
        top_action = max(actions, key=actions.get) if actions else "idle"
        nodes.append(
            {
                "id": int(uid),
                "label": f"agent #{int(uid)}",
                "action_count": int(total),
                "top_action": str(top_action),
                "posts_authored": sum(1 for a in post_author.values() if a == uid),
            }
        )

    links = [
        {"source": int(s), "target": int(t), "type": str(k), "weight": int(w)}
        for (s, t, k), w in edge_counter.items()
    ]
    return {"nodes": nodes, "links": links}


def _summarize(db_path: Path) -> SimulationSummary:
    """Build a SimulationSummary by reading the OASIS SQLite DB."""
    with sqlite3.connect(str(db_path)) as conn:
        conn.row_factory = sqlite3.Row

        # Total actions and breakdown by type from the `trace` table.
        try:
            rows = conn.execute(
                "SELECT action, COUNT(*) AS n FROM trace GROUP BY action"
            ).fetchall()
        except sqlite3.OperationalError:
            rows = []
        actions_by_type = {r["action"]: r["n"] for r in rows}
        total_actions = sum(actions_by_type.values())

        # Sample posts (most recent 5)
        try:
            posts = conn.execute(
                "SELECT post_id, user_id, content, created_at FROM post "
                "ORDER BY post_id DESC LIMIT 5"
            ).fetchall()
        except sqlite3.OperationalError:
            posts = []
        sample_posts = [dict(p) for p in posts]

        # Sample comments (most recent 5)
        try:
            comments = conn.execute(
                "SELECT comment_id, post_id, user_id, content, created_at FROM comment "
                "ORDER BY comment_id DESC LIMIT 5"
            ).fetchall()
        except sqlite3.OperationalError:
            comments = []
        sample_comments = [dict(c) for c in comments]

        network_graph = _extract_network_graph(conn)

    return SimulationSummary(
        profiles_count=0,
        initial_posts_count=0,
        rounds_executed=0,
        total_actions=total_actions,
        actions_by_type=actions_by_type,
        sample_posts=sample_posts,
        sample_comments=sample_comments,
        network_graph=network_graph,
    )
