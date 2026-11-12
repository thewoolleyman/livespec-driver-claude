"""Regression coverage for the aggregate purity refusal guard."""

from __future__ import annotations

from pathlib import Path

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parents[2]


def test_purity_guard_audits_the_inventory_before_the_aggregate_runs() -> None:
    """Undeclared members must be named before `just check` dispatches them."""
    guard = _REPO_ROOT / "dev-tooling" / "just" / "check-purity.sh"

    assert guard.is_file(), "the aggregate needs an inventory parity and purity guard"
    text = guard.read_text(encoding="utf-8")
    assert "check-targets.txt" in text
    assert "green_token undeclared" in text
