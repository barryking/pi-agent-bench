import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]


def _validate(document: Path, schema_name: str) -> None:
    schema = json.loads(
        (ROOT / "configs" / "schemas" / schema_name).read_text(encoding="utf-8")
    )
    value = json.loads(document.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(value)


def test_starter_profile_templates_match_their_editor_schemas():
    _validate(ROOT / "configs" / "agent-profiles.json", "agent-profiles.schema.json")
    _validate(
        ROOT / "configs" / "model-baselines.example.json",
        "model-profiles.schema.json",
    )
    _validate(ROOT / "configs" / "pi-profiles.json", "pi-profiles.schema.json")


def test_integration_profile_examples_match_their_editor_schemas():
    example = ROOT / "examples" / "agent-profiles"
    _validate(
        example / "agent-profiles.example.json",
        "agent-profiles.schema.json",
    )
    _validate(
        example / "model-profiles.example.json",
        "model-profiles.schema.json",
    )
    _validate(
        example / "pi-profiles.example.json",
        "pi-profiles.schema.json",
    )
