"""Pi Agent Bench setup and case scaffolding."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CASE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


def initialize_workspace(
    root: str | Path = REPOSITORY_ROOT,
) -> list[tuple[Path, str]]:
    """Create ignored local configuration files without overwriting user data."""
    destination = Path(root).expanduser().resolve()
    files = [
        (
            REPOSITORY_ROOT / ".env.example",
            destination / ".env.local",
        ),
        (
            REPOSITORY_ROOT / "configs" / "model-baselines.example.json",
            destination / "configs" / "model-baselines.local.json",
        ),
        (
            REPOSITORY_ROOT / "configs" / "agent-profiles.json",
            destination / "configs" / "agent-profiles.local.json",
        ),
    ]
    results: list[tuple[Path, str]] = []
    for source, target in files:
        if target.exists():
            results.append((target, "kept"))
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        results.append((target, "created"))
    for directory in ("logs", "results", "repos"):
        (destination / directory).mkdir(parents=True, exist_ok=True)
    return results


def scaffold_case(
    phase: str,
    case_id: str,
    dataset: str | Path,
    *,
    dataset_version: str = "draft-1",
    root: str | Path = REPOSITORY_ROOT,
) -> list[Path]:
    """Create a safe, failing-by-default planning or coding case scaffold."""
    if phase not in {"planning", "coding"}:
        raise ValueError("phase must be planning or coding")
    if not CASE_ID.fullmatch(case_id):
        raise ValueError(
            "case id must start with a lowercase letter or number and contain "
            "only lowercase letters, numbers, dots, underscores, or hyphens"
        )
    destination = Path(root).expanduser().resolve()
    dataset_path = Path(dataset).expanduser()
    if not dataset_path.is_absolute():
        dataset_path = destination / dataset_path
    dataset_path = dataset_path.resolve()
    if dataset_path.exists():
        raise ValueError(f"refusing to overwrite existing dataset: {dataset_path}")

    created: list[Path] = []
    if phase == "planning":
        case = _planning_case(case_id, dataset_version)
    else:
        fixture = destination / "fixtures" / case_id
        verifier = destination / "verifiers" / case_id / "verify.py"
        for path in (fixture / "README.md", verifier):
            if path.exists():
                raise ValueError(f"refusing to overwrite existing scaffold: {path}")
        fixture.mkdir(parents=True, exist_ok=True)
        verifier.parent.mkdir(parents=True, exist_ok=True)
        (fixture / "README.md").write_text(
            f"# {case_id}\n\nDescribe the reproducible starting state here.\n",
            encoding="utf-8",
        )
        verifier.write_text(_verifier_template(case_id), encoding="utf-8")
        created.extend([fixture / "README.md", verifier])
        case = _coding_case(case_id, dataset_version)

    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    dataset_path.write_text(
        json.dumps(case, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    created.insert(0, dataset_path)
    return created


def _planning_case(case_id: str, dataset_version: str) -> dict:
    return {
        "id": case_id,
        "phase": "planning",
        "instruction": "TODO: describe the planning task and required output.",
        "context_files": [],
        "tags": ["draft", "planning"],
        "limits": {
            "seconds": 900,
            "turns": 18,
            "context_tokens": 65536,
            "total_tokens": 65536,
        },
        "expected": {
            "required_concepts": ["TODO-required-concept"],
            "forbidden_concepts": [],
            "verifier_command": [],
            "success_threshold": 0.75,
            "rubric": [
                {
                    "id": "correctness",
                    "description": "TODO: define observable evidence of a correct plan.",
                    "weight": 2,
                },
                {
                    "id": "verification",
                    "description": "Defines concrete validation and regression checks.",
                    "weight": 1,
                },
                {
                    "id": "rollout",
                    "description": "Defines safe rollout, monitoring, and rollback.",
                    "weight": 1,
                },
            ],
        },
        "metadata": {
            "dataset_version": dataset_version,
            "synthetic": False,
            "draft": True,
        },
    }


def _coding_case(case_id: str, dataset_version: str) -> dict:
    return {
        "id": case_id,
        "phase": "coding",
        "instruction": "TODO: describe the required observable code change.",
        "context_files": [],
        "tags": ["draft", "coding"],
        "limits": {
            "seconds": 1800,
            "turns": 45,
            "context_tokens": 65536,
            "total_tokens": 150000,
        },
        "expected": {
            "required_concepts": [],
            "forbidden_concepts": [],
            "verifier_command": [
                "python3",
                f"/opt/verifiers/{case_id}/verify.py",
            ],
            "success_threshold": 1.0,
            "required_components": ["requirements"],
        },
        "metadata": {
            "dataset_version": dataset_version,
            "fixture": f"fixtures/{case_id}",
            "score_components": ["requirements"],
            "synthetic": False,
            "draft": True,
        },
    }


def _verifier_template(case_id: str) -> str:
    return f'''"""Protected verifier scaffold for {case_id}."""

import json


def main() -> int:
    # Replace this failing placeholder with deterministic checks of observable
    # behaviour. Keep component names aligned with metadata.score_components.
    print(json.dumps({{
        "score": 0.0,
        "components": {{"requirements": 0.0}},
        "explanation": "TODO: implement protected verification",
    }}, sort_keys=True))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
'''
