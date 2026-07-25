from dgx_agent_evals.pi_runner import PiRunConfig, build_command


def test_builds_ephemeral_json_command():
    command = build_command(
        PiRunConfig(
            provider="dgx-spark",
            model="qwen-coder",
            timeout_seconds=60,
            trust_mode="no-approve",
        ),
        "Inspect the repository.",
    )

    assert command == (
        "pi",
        "--mode",
        "json",
        "--no-session",
        "--no-approve",
        "--provider",
        "dgx-spark",
        "--model",
        "qwen-coder",
        "Inspect the repository.",
    )
