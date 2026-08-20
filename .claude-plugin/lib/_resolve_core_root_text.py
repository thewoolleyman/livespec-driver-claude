"""Operator-facing text for core-root resolution.

Extracted from `resolve_core_root.py` so that module stays inside this repo's
ARMED 250 LLOC hard ceiling once rule 2 gains its three-way predicate. This file
holds the install instructions and the mismatch narrative: no resolution logic
lives here, and nothing here imports the resolver, so the dependency runs one
way.

`_diagnostic` deliberately did NOT move. It dispatches over `UnresolvedKind` and
closes with `assert_never`, which is the resolver's exhaustiveness guard; moving
it would either duplicate that helper or make the two modules import each other.

Standard library only, for the same reason the resolver is: the Claude Code
plugin installer copies `.claude-plugin/` into the install cache with no
virtualenv, so both files run under bare system `python3`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

__all__: list[str] = ["INSTALL_INSTRUCTIONS", "mismatch_detail"]

INSTALL_INSTRUCTIONS = (
    "  claude plugin marketplace add thewoolleyman/livespec\n"
    "  claude plugin install livespec@livespec --scope project\n"
)


def mismatch_detail(*, project_root: Path, installed_for: list[str]) -> str:
    listed = "\n".join(f"    {other}" for other in installed_for)
    return (
        f"livespec core is installed on this host, but NOT for this project.\n"
        f"  this project root : {project_root}\n"
        f"  records exist for :\n{listed}\n"
        "This is a provisioning defect, NOT a stale plugin -- do not run "
        "`claude plugin update`, which would rewrite a record this project does "
        "not have. Install core for THIS project:\n" + INSTALL_INSTRUCTIONS
    )
