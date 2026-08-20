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

_OVERRIDE_ENV = "LIVESPEC_CORE_PLUGIN_ROOT"

__all__: list[str] = [
    "INCOMPLETE_CORE_GUIDANCE",
    "INSTALL_INSTRUCTIONS",
    "mismatch_detail",
]

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


# Named here rather than inline because it is operator-facing text, and because
# its final sentence is a BINDING CONDITION from livespec core's review of this
# predicate: a rename of any operation is executed in a WORKTREE of core, which
# transits the incomplete state precisely while driving the propose-change and
# revise operations this predicate gates. Without naming the override, the error
# band would hard-block core's own ratified rename path.
INCOMPLETE_CORE_GUIDANCE = (
    "A partial core prose set is a checkout mid-rename or mid-fetch, NOT a "
    "consumer project -- so resolution stops here rather than falling through "
    "to the installed cache, which would serve the OLD released prose while "
    "you edit its replacement.\n"
    f"If this checkout IS the core you mean to drive, set {_OVERRIDE_ENV} to it "
    "and retry: that override is consulted BEFORE this check, so it recovers "
    "the rename path in one step.\n"
)
