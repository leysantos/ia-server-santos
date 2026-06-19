#!/usr/bin/env python3
"""
Learning Loop v2 — job manual de auto-tuning de prompts.

Uso:
  python scripts/run_auto_tune.py
  python scripts/run_auto_tune.py --discipline ESTRUTURAL
  python scripts/run_auto_tune.py --min-feedback 5 --limit 1000
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.learning_v2.auto_tuner import run_auto_tune


def main() -> int:
    parser = argparse.ArgumentParser(description="Learning Loop v2 — auto-tuning de prompts")
    parser.add_argument(
        "--discipline",
        help="Otimizar apenas uma disciplina (ex.: ESTRUTURAL)",
        default=None,
    )
    parser.add_argument(
        "--min-feedback",
        type=int,
        default=3,
        help="Mínimo de registros de feedback por disciplina (default: 3)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=500,
        help="Máximo de registros lidos do PostgreSQL (default: 500)",
    )
    args = parser.parse_args()

    report = run_auto_tune(
        discipline=args.discipline,
        min_feedback=args.min_feedback,
        limit=args.limit,
    )

    print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
    return 0 if report.tuned_count >= 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
