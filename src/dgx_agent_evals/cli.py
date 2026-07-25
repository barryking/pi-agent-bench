"""Command-line entry point."""

from __future__ import annotations

import argparse
from pathlib import Path

from .dataset import load_cases


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dgx-agent-evals")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate a golden JSONL dataset")
    validate.add_argument("dataset", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "validate":
        cases = load_cases(args.dataset)
        phases = sorted({case.phase for case in cases})
        print(f"valid: {len(cases)} case(s); phases={','.join(phases)}")
