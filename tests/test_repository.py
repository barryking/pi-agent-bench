from pathlib import Path

import pytest

from pi_agent_bench.repository import repository_root


def test_repository_root_finds_the_checkout_from_a_child():
    expected = Path(__file__).resolve().parents[1]

    assert repository_root(expected / "src" / "pi_agent_bench") == expected


def test_repository_root_explains_clone_requirement(tmp_path):
    with pytest.raises(RuntimeError, match="needs a cloned repository"):
        repository_root(tmp_path)
