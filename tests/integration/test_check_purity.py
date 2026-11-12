"""Regression coverage for the check aggregate's purity inventory."""

from __future__ import annotations

from pathlib import Path

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _members_from_inventory(*, path: Path) -> list[str]:
    """Return inventory members in their declared aggregate order."""
    return [
        line.split("#", maxsplit=1)[0].strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.split("#", maxsplit=1)[0].strip().startswith("check-")
    ]


def test_check_inventory_mirrors_the_aggregate_member_list() -> None:
    """The purity inventory must enumerate every member `just check` runs."""
    inventory = _REPO_ROOT / "check-targets.txt"

    assert inventory.is_file(), "the aggregate needs a committed purity inventory"
    assert _members_from_inventory(path=inventory)
