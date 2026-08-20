"""The eight bindings' post-resolve core-root guard.

Until this file existed, that guard was exercised by NOTHING. It is bash inside
a fenced block in each `SKILL.md`, run by the agent at runtime; no test read it
and `check-plugin-structure` does not look at it -- that gate constrains only
fenced lines which INVOKE a `bin/<name>.py` wrapper. So a broken guard passed
`just check` exactly as cleanly as a correct one, which is how the previous
directory-only guard survived wrong in all eight copies for its whole existence.

Two disciplines this file is built around:

1. **The guard is extracted and RUN, not pattern-matched.** Asserting that the
   text contains some substring would pass on a guard that never executes. These
   tests bind `LIVESPEC_CORE_ROOT` to a fixture root and run the real block, so
   they assert behaviour.

2. **The negative fixtures are the point.** A core-shaped root passing proves
   almost nothing -- the previous guard passed that too. What separates the two
   guards is a non-core root that ships its own prose, and a core checkout with
   an incomplete set. Both are the cases the resolver's rule 2 now distinguishes,
   and the guard exists to catch them if resolution ever regresses.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SKILLS = _REPO_ROOT / ".claude-plugin" / "skills"
_FENCE = re.compile(r"```bash\n(.*?)```", re.DOTALL)

_CORE_OPS = (
    "critique",
    "doctor",
    "help",
    "next",
    "propose-change",
    "prune-history",
    "revise",
    "seed",
)


def _binding_names() -> list[str]:
    return sorted(path.parent.name for path in _SKILLS.glob("*/SKILL.md"))


def _guard_script(*, binding: str) -> str:
    """The binding's fenced guard, with the resolver call replaced by an argument.

    The resolver invocation is dropped rather than run: this file tests the GUARD,
    and the resolver has its own suite. What remains is the check that runs
    against whatever root resolution produced.
    """
    body = _SKILLS / binding / "SKILL.md"
    for block in _FENCE.findall(body.read_text()):
        if "LIVESPEC_CORE_ROOT" in block and (" -f " in block or " -d " in block):
            kept = [line for line in block.splitlines() if "resolve_core_root.py" not in line]
            return 'LIVESPEC_CORE_ROOT="$1"\n' + "\n".join(kept)
    msg = f"{binding}: no fenced guard block found"
    raise AssertionError(msg)


def _run(*, script: str, root: Path) -> int:
    completed = subprocess.run(
        ["/usr/bin/env", "bash", "-c", script, "_", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode


def _root(*, tmp_path: Path, name: str, ops: tuple[str, ...]) -> Path:
    root = tmp_path / name
    prose = root / "prose"
    prose.mkdir(parents=True)
    for op in ops:
        (prose / f"{op}.md").write_text("prose")
    return root


@pytest.mark.parametrize("binding", _binding_names())
def test_guard_accepts_a_core_shaped_root(binding: str, tmp_path: Path) -> None:
    root = _root(tmp_path=tmp_path, name="core", ops=_CORE_OPS)

    assert _run(script=_guard_script(binding=binding), root=root) == 0


@pytest.mark.parametrize("binding", _binding_names())
def test_guard_rejects_a_non_core_root_shipping_its_own_prose(binding: str, tmp_path: Path) -> None:
    """The case the directory-only guard passed, and the reason this item exists."""
    root = _root(
        tmp_path=tmp_path,
        name="consumer",
        ops=("foreman", "overseer", "supervise-plan"),
    )

    assert _run(script=_guard_script(binding=binding), root=root) != 0


@pytest.mark.parametrize("binding", _binding_names())
def test_guard_rejects_an_incomplete_core_root(binding: str, tmp_path: Path) -> None:
    """A stale or half-fetched cache entry, which the guard is the last line against."""
    partial = tuple(op for op in _CORE_OPS if op != "revise")
    root = _root(tmp_path=tmp_path, name="partial", ops=partial)

    assert _run(script=_guard_script(binding=binding), root=root) != 0


def test_every_binding_carries_a_byte_identical_guard() -> None:
    """Drift pin.

    Eight copies of one rule stay in agreement only by copying, and that is
    exactly how the resolution defect came to live in all eight bindings at once.
    Nothing else enforces that these stay the same.
    """
    scripts = {_guard_script(binding=name) for name in _binding_names()}

    assert len(_binding_names()) == 8
    assert len(scripts) == 1
