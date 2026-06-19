#!/usr/bin/env python3
"""CLI — Agent Generation Loop v1 (controlled)."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Agent Generation Loop v1")
    parser.add_argument("--discipline", help="Disciplina alvo (ex: ESTRUTURAL)")
    parser.add_argument("--runs", type=int, default=30, help="Execuções sandbox (20-50)")
    parser.add_argument("--use-llm", action="store_true", help="Usar LLM leve + RAG read-only")
    parser.add_argument("--list-candidates", action="store_true", help="Listar candidatos")
    args = parser.parse_args()

    if not settings.USE_AGENT_GENERATION:
        print("USE_AGENT_GENERATION=false — ative a flag para executar.")
        return 1

    from core.agent_generation.agent_generation_engine import get_agent_generation_engine
    from core.agent_generation.agent_registry_candidate import get_candidate_registry

    if args.list_candidates:
        registry = get_candidate_registry()
        for c in registry.list_candidates():
            print(json.dumps(c.to_dict(), ensure_ascii=False, indent=2))
        return 0

    engine = get_agent_generation_engine()
    result = engine.propose_and_pipeline(
        discipline=args.discipline,
        n_runs=args.runs,
        use_llm=args.use_llm,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
