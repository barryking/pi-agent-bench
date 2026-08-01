import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

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


def test_model_editor_schema_rejects_secret_like_public_fields():
    schema = json.loads(
        (ROOT / "configs" / "schemas" / "model-profiles.schema.json").read_text(
            encoding="utf-8"
        )
    )
    document = json.loads(
        (ROOT / "configs" / "model-baselines.example.json").read_text(
            encoding="utf-8"
        )
    )
    document["profiles"]["local-candidate"]["configuration"]["api_key"] = (
        "must-not-be-public"
    )

    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(document)


@pytest.mark.parametrize(
    ("field", "value"),
    [("name", "Invalid Name"), ("tools", [])],
)
def test_pi_editor_schema_matches_mcp_loader_constraints(field, value):
    schema = json.loads(
        (ROOT / "configs" / "schemas" / "pi-profiles.schema.json").read_text(
            encoding="utf-8"
        )
    )
    document = json.loads(
        (
            ROOT
            / "examples"
            / "agent-profiles"
            / "pi-profiles.example.json"
        ).read_text(encoding="utf-8")
    )
    document["profiles"]["example-mcp"]["mcp_servers"][0][field] = value

    with pytest.raises(ValidationError):
        Draft202012Validator(schema).validate(document)
