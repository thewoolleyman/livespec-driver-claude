"""Behavioral coverage for the repository's delegated pre-push entrypoint."""

from __future__ import annotations

from pathlib import Path

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_repository_opted_in_to_the_delegated_gate_client() -> None:
    """The client is selected only by an explicit repository-level opt-in."""
    pyproject = (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "[tool.livespec_dev_tooling]\ndelegated_gate = true" in pyproject
    assert 'tag = "v1.134.2"' in pyproject
