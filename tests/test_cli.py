from pathlib import Path

import pytest

from pi_agent_bench.cli_parser import build_parser


def test_report_defaults_to_the_selected_results_directory():
    args = build_parser().parse_args(["report", "--results-dir", "results/example-run"])

    assert args.results_dir == Path("results/example-run")
    assert args.output is None


def test_cli_exposes_final_command_name():
    assert build_parser().prog == "pi-bench"


def test_benchmark_compares_complete_agent_profiles():
    args = build_parser().parse_args(
        [
            "benchmark",
            "--agent-profile",
            "local-agent",
            "--agent-profile",
            "team-tools",
            "--run-name",
            "agent-check",
        ]
    )

    assert args.agent_profile == ["local-agent", "team-tools"]


def test_doctor_uses_profile_first_component_files():
    args = build_parser().parse_args(
        [
            "doctor",
            "--model-profiles-file",
            "models.json",
            "--agent-profile",
            "team-agent",
            "--agent-profiles-file",
            "agents.json",
            "--pi-profiles-file",
            "pi.json",
        ]
    )

    assert args.model_profiles_file == Path("models.json")
    assert args.agent_profile == "team-agent"
    assert args.agent_profiles_file == Path("agents.json")
    assert args.pi_profiles_file == Path("pi.json")


def test_profile_commands_default_to_initialized_local_files():
    doctor = build_parser().parse_args(["doctor", "--agent-profile", "team-agent"])
    run = build_parser().parse_args(["run", "--agent-profile", "team-agent"])
    listed = build_parser().parse_args(["agent-profiles"])

    for args in (doctor, run, listed):
        assert args.model_profiles_file == Path("configs/model-baselines.local.json")
    assert doctor.env_file == Path(".env.local")
    assert run.env_file == Path(".env.local")


@pytest.mark.parametrize(
    "old_flag",
    ["--profile", "--profiles", "--run-profile", "--model-profile"],
)
def test_old_ambiguous_profile_flags_are_not_supported(old_flag):
    with pytest.raises(SystemExit):
        build_parser().parse_args(
            [
                "benchmark",
                old_flag,
                "old-value",
                "--agent-profile",
                "local-agent",
                "--run-name",
                "old-flag-check",
            ]
        )


def test_old_generic_profiles_command_is_not_supported():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["profiles"])


@pytest.mark.parametrize("old_command", ["campaign", "demo-data"])
def test_removed_commands_are_not_supported(old_command):
    with pytest.raises(SystemExit):
        build_parser().parse_args([old_command])
