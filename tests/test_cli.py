from pathlib import Path

from pi_agent_bench.cli_parser import build_parser


def test_report_defaults_to_the_selected_results_directory():
    args = build_parser().parse_args(
        ["report", "--results-dir", "results/example-campaign"]
    )

    assert args.results_dir == Path("results/example-campaign")
    assert args.output is None


def test_cli_exposes_final_command_name():
    assert build_parser().prog == "pi-bench"
