"""Consumer opt-in coverage for delegated pre-commit aggregates."""

from __future__ import annotations

from pathlib import Path

from livespec_dev_tooling.config import load_delegated_pre_commit

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_repository_configuration_opts_in_to_delegated_pre_commit() -> None:
    assert load_delegated_pre_commit(repo_root=_REPO_ROOT) is True
