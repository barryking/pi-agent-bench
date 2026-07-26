import json

import pytest

from pi_agent_bench.demo_data import DEMO_CASES, DEMO_PROFILES, generate_demo_results
from pi_agent_bench.reporting import build_report, write_visualizer_exports


def test_demo_data_is_balanced_and_clearly_marked(tmp_path):
    paths = generate_demo_results(tmp_path, trials=3)

    assert len(paths) == len(DEMO_PROFILES) * len(DEMO_CASES) * 3
    records = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    assert all(record["synthetic"] is True for record in records)
    assert {record["model_configuration"]["kind"] for record in records} == {
        "local",
        "hosted",
    }

    report = build_report(tmp_path)
    for cohort in report["cohorts"].values():
        assert set(cohort["profiles"]) == set(DEMO_PROFILES)
        assert {values["runs"] for values in cohort["profiles"].values()} == {18}
        assert {values["cases"] for values in cohort["profiles"].values()} == {6}

    _, metrics_path = write_visualizer_exports(tmp_path)
    first_metric = json.loads(metrics_path.read_text(encoding="utf-8").splitlines()[0])
    assert first_metric["synthetic"] is True


def test_demo_data_refuses_to_mix_with_existing_results(tmp_path):
    (tmp_path / "existing.json").write_text("{}", encoding="utf-8")

    with pytest.raises(ValueError, match="choose an empty demo directory"):
        generate_demo_results(tmp_path)
