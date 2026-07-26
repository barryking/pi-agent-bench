from pathlib import Path

import pytest

from pi_agent_bench.cli_parser import build_parser


def test_report_defaults_to_the_selected_results_directory():
    args = build_parser().parse_args(
        ["report", "--results-dir", "results/example-campaign"]
    )

    assert args.results_dir == Path("results/example-campaign")
    assert args.output is None


def test_cli_exposes_final_command_name():
    assert build_parser().prog == "pi-bench"


def test_campaign_can_compare_agent_profiles_with_the_same_model():
    args = build_parser().parse_args(
        [
            "campaign",
            "coding",
            "--model-profile",
            "local-model",
            "--agent-profile",
            "vanilla",
            "--agent-profile",
            "team-tools",
            "--campaign",
            "agent-check",
        ]
    )

    assert args.model_profile == ["local-model"]
    assert args.agent_profile == ["vanilla", "team-tools"]


def test_doctor_uses_explicit_model_and_agent_profile_names():
    args = build_parser().parse_args(
        [
            "doctor",
            "--model-profile",
            "hosted-quality",
            "--model-profiles-file",
            "models.json",
            "--agent-profile",
            "team-agent",
            "--agent-profiles-file",
            "agents.json",
        ]
    )

    assert args.model_profile == "hosted-quality"
    assert args.model_profiles_file == Path("models.json")
    assert args.agent_profile == "team-agent"
    assert args.agent_profiles_file == Path("agents.json")


@pytest.mark.parametrize(
    "old_flag",
    ["--profile", "--profiles", "--run-profile", "--agent-profiles"],
)
def test_old_ambiguous_profile_flags_are_not_supported(old_flag):
    with pytest.raises(SystemExit):
        build_parser().parse_args(
            [
                "campaign",
                "coding",
                old_flag,
                "old-value",
                "--model-profile",
                "local-model",
                "--campaign",
                "old-flag-check",
            ]
        )


def test_old_generic_profiles_command_is_not_supported():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["profiles"])
