"""
MiroEdo CLI — quick entry points for the engine.

Usage:
    python -m app.engine.cli info
    python -m app.engine.cli extract-entities --csv data/mulino_bianco.csv --brand "Mulino Bianco" [--out entities.json]
    python -m app.engine.cli generate-profiles --csv data/mulino_bianco.csv --brand "Mulino Bianco" --out profiles.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List

from app.engine.config import EngineConfig
from app.engine.seeds_to_entities import seed_to_entities
from app.engine.types import EntityNode
from app.engine.utils.logger import get_logger

logger = get_logger("miroedo.cli")


def cmd_info(_args: argparse.Namespace) -> int:
    """Print engine status: modules available, Zep, OASIS."""
    print("=" * 60)
    print("MiroEdo Engine — status")
    print("=" * 60)

    cfg = EngineConfig.from_env()
    print(f"LLM model        : {cfg.llm_model}")
    print(f"LLM base URL     : {cfg.llm_base_url}")
    print(f"LLM API key set  : {'yes' if cfg.llm_api_key else 'NO'}")
    print(f"Zep enabled      : {'yes' if cfg.zep_enabled else 'no'}")
    print(f"Simulations dir  : {cfg.simulations_dir}")
    print(f"Reports dir      : {cfg.reports_dir}")
    print(f"Locale           : {cfg.locale}")

    # Module probes
    from app.engine.zep import is_zep_available

    print()
    print("Optional dependencies:")
    print(f"  zep_cloud      : {'INSTALLED' if is_zep_available() else 'missing'}")
    try:
        import oasis  # noqa: F401

        oasis_ok = True
    except Exception:
        oasis_ok = False
    print(f"  oasis-ai       : {'INSTALLED' if oasis_ok else 'missing'}")
    try:
        import camel  # noqa: F401

        camel_ok = True
    except Exception:
        camel_ok = False
    print(f"  camel-ai       : {'INSTALLED' if camel_ok else 'missing'}")

    print()
    print("Engine modules: ", end="")
    modules_ok = []
    for mod_name in (
        "app.engine.profile",
        "app.engine.simulation",
        "app.engine.logging_io.action_logger",
        "app.engine.ipc.simulation_ipc",
        "app.engine.report",
    ):
        try:
            __import__(mod_name)
            modules_ok.append(mod_name.split(".")[-1])
        except Exception as exc:
            print(f"\n  FAIL {mod_name}: {exc}")
    print(", ".join(modules_ok))
    return 0


def _load_seed(csv_path: str, brand: str) -> "BrandSeed":  # type: ignore[name-defined]
    from app.ingestion.tabular_adapter import parse_csv

    data = Path(csv_path).read_bytes()
    return parse_csv(data, brand=brand)


def cmd_extract_entities(args: argparse.Namespace) -> int:
    seed = _load_seed(args.csv, args.brand)
    entities = seed_to_entities(seed, total_consumers=args.consumers, top_topics=args.topics)
    payload = [e.to_dict() for e in entities]
    if args.out:
        Path(args.out).write_text(json.dumps(payload, indent=2, ensure_ascii=False))
        print(f"Wrote {len(payload)} entities → {args.out}")
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def cmd_generate_profiles(args: argparse.Namespace) -> int:
    seed = _load_seed(args.csv, args.brand)
    entities = seed_to_entities(seed, total_consumers=args.consumers, top_topics=args.topics)

    cfg = EngineConfig.from_env()
    if not cfg.llm_api_key:
        print("ERROR: LLM_API_KEY not set in environment", file=sys.stderr)
        return 2

    from app.engine.profile import OasisProfileGenerator

    gen = OasisProfileGenerator(config=cfg, zep_client=None)
    profiles = gen.generate_profiles_from_entities(
        entities,
        use_llm=not args.rule_based,
        parallel_count=args.parallel,
        output_platform=args.platform,
    )
    out_path = args.out or f"profiles_{args.platform}.{'csv' if args.platform == 'twitter' else 'json'}"
    gen.save_profiles(profiles, out_path, platform=args.platform)
    print(f"Generated {len(profiles)} profiles → {out_path}")
    return 0


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="miroedo", description="MiroEdo Engine CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    p_info = sub.add_parser("info", help="Print engine status")
    p_info.set_defaults(func=cmd_info)

    p_ee = sub.add_parser("extract-entities", help="Brandwatch CSV → EntityNode JSON")
    p_ee.add_argument("--csv", required=True)
    p_ee.add_argument("--brand", required=True)
    p_ee.add_argument("--consumers", type=int, default=20)
    p_ee.add_argument("--topics", type=int, default=5)
    p_ee.add_argument("--out", default=None)
    p_ee.set_defaults(func=cmd_extract_entities)

    p_gp = sub.add_parser("generate-profiles", help="Brandwatch CSV → OASIS profiles JSON/CSV")
    p_gp.add_argument("--csv", required=True)
    p_gp.add_argument("--brand", required=True)
    p_gp.add_argument("--platform", choices=["reddit", "twitter"], default="reddit")
    p_gp.add_argument("--consumers", type=int, default=10)
    p_gp.add_argument("--topics", type=int, default=3)
    p_gp.add_argument("--parallel", type=int, default=3)
    p_gp.add_argument("--rule-based", action="store_true", help="Skip LLM, use rule-based personas")
    p_gp.add_argument("--out", default=None)
    p_gp.set_defaults(func=cmd_generate_profiles)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
