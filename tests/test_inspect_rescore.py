from pi_agent_bench.cli_execution import _eval_set_id


def test_eval_set_ids_are_safe_and_profile_specific():
    sol = _eval_set_id("pilot v1", "gpt-5.6-sol")
    luna = _eval_set_id("pilot v1", "gpt-5.6-luna")
    guided = _eval_set_id("pilot v1", "gpt-5.6-sol", "team tools")

    assert sol == "pilot-v1-gpt-5-6-sol"
    assert luna == "pilot-v1-gpt-5-6-luna"
    assert guided == "pilot-v1-gpt-5-6-sol-team-tools"
    assert sol != luna
