"""
M3.1 smoke: prova che OASIS si carica e che possiamo costruire un environment
minimo (1 agente, 1 azione manuale, niente LLM) dentro al container Docker.

Esegui:
    docker compose run --rm miroedo-backend python -m tests.smoke_oasis_hello

Esce con codice 0 se OASIS è funzionante, 1 altrimenti.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path


def _build_minimal_profile(tmp_dir: Path) -> Path:
    """Profilo Reddit a 1 agente compatibile con OASIS `generate_reddit_agent_graph`."""
    profile = [
        {
            "user_id": 0,
            "username": "smoke_user",
            "name": "Smoke User",
            "bio": "Hello-world agent for the OASIS smoke test.",
            "persona": "A neutral observer who occasionally comments.",
            "karma": 100,
            "created_at": "2026-05-21",
            "age": 30,
            "gender": "other",
            "mbti": "INTJ",
            "country": "Italy",
            "profession": "Tester",
            "interested_topics": ["General"],
        }
    ]
    path = tmp_dir / "smoke_profile.json"
    path.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
    return path


async def _run() -> None:
    print("[oasis-smoke] importing oasis ...")
    import oasis
    from oasis import ActionType, ManualAction, generate_reddit_agent_graph
    from camel.models import ModelFactory
    from camel.types import ModelPlatformType, ModelType

    print(f"[oasis-smoke] oasis OK (module={oasis.__name__})")

    with tempfile.TemporaryDirectory() as tmpd:
        tmp = Path(tmpd)
        profile_path = _build_minimal_profile(tmp)
        db_path = tmp / "smoke.db"

        # NOTE: nessuna LLMAction → niente chiamate a OpenAI in questo smoke.
        # Il modello è richiesto solo dalla firma di generate_reddit_agent_graph,
        # ma non viene invocato in fase di setup.
        api_key = os.environ.get("OPENAI_API_KEY")
        model = ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI,
            model_type=ModelType.GPT_4O_MINI,
            api_key=api_key or "sk-noop-for-setup",
        )

        print("[oasis-smoke] generating agent graph ...")
        agent_graph = await generate_reddit_agent_graph(
            profile_path=str(profile_path),
            model=model,
            available_actions=[ActionType.CREATE_POST, ActionType.DO_NOTHING],
        )

        print("[oasis-smoke] making environment ...")
        env = oasis.make(
            agent_graph=agent_graph,
            platform=oasis.DefaultPlatformType.REDDIT,
            database_path=str(db_path),
        )

        try:
            print("[oasis-smoke] env.reset() ...")
            await env.reset()

            print("[oasis-smoke] dispatching 1 manual CREATE_POST ...")
            actions = {
                env.agent_graph.get_agent(0): ManualAction(
                    action_type=ActionType.CREATE_POST,
                    action_args={"content": "Hello from MiroEdo M3.1 smoke."},
                )
            }
            await env.step(actions)
        finally:
            print("[oasis-smoke] env.close() ...")
            await env.close()

        # Verifica che il db sia stato popolato
        import sqlite3

        with sqlite3.connect(db_path) as conn:
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )]
            print(f"[oasis-smoke] sqlite tables: {tables}")
            post_count = conn.execute("SELECT COUNT(*) FROM post").fetchone()[0]
            print(f"[oasis-smoke] post rows: {post_count}")
            assert post_count >= 1, "Expected at least 1 post after CREATE_POST"

    print("[oasis-smoke] OK")


def main() -> int:
    try:
        asyncio.run(_run())
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"[oasis-smoke] FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
