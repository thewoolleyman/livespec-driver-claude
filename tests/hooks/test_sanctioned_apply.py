"""Unit tests for `.claude-plugin/hooks/_sanctioned_apply.py`.

The sanctioned deploy path, pinned by property: the sanction attaches only to
the segment's first recognised head; option values are never playbooks; only a
playbook positively outside committed source convicts; `--check` and
`ansible-drift` read. Every argv is inert data.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / ".claude-plugin" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from _sanctioned_apply import sanction  # noqa: E402 — path-dependent import after sys.path insert.

__all__: list[str] = []

_KNOWN = frozenset({"ssh", "scp", "kubectl", "bash", "just", "ansible", "ansible-playbook"})


@pytest.mark.parametrize(
    ("tokens", "expected"),
    [
        (["just", "ansible-apply", "ansible/ci-pool.yml"], (True, None)),
        (["just", "ansible-drift", "/tmp/adhoc.yml"], (True, None)),
        (["mise", "exec", "--", "just", "ansible-apply", "ansible/ci-pool.yml"], (True, None)),
        (["timeout", "900", "just", "ansible-apply", "x.yml"], (True, None)),
        (
            ["uvx", "--from", "ansible-core==2.21.4", "ansible-playbook", "-i", "inv", "x.yml"],
            (True, None),
        ),
        (["ansible-playbook", "--check", "-i", "inv", "/tmp/adhoc.yml"], (True, None)),
        (
            [
                "ansible-playbook",
                "-i",
                "/data/projects/livespec-dev-tooling/ansible/inventory/legacy.yml",
                "ansible/ci-pool.yml",
            ],
            (True, None),
        ),
        (
            ["ansible-playbook", "/data/projects/livespec-dev-tooling/ansible/ci-pool.yml"],
            (True, None),
        ),
        (["ansible-playbook", "-e", "x=$(hostname)", "ansible/ci-pool.yml"], (True, None)),
        (
            ["ansible-playbook", "-i", "inv", "/tmp/adhoc.yml"],
            (True, "ansible-playbook+uncommitted-playbook"),
        ),
        (["ansible-playbook", "/tmp/adhoc"], (True, "ansible-playbook+uncommitted-playbook")),
        (["ansible-playbook", "~/adhoc.yml"], (True, "ansible-playbook+uncommitted-playbook")),
        (["ansible-playbook", "/var/tmp/x.yml"], (True, "ansible-playbook+uncommitted-playbook")),
        (["ansible-playbook", "/dev/shm/x.yml"], (True, "ansible-playbook+uncommitted-playbook")),
        (["ansible-playbook", "./../x.yml"], (True, "ansible-playbook+uncommitted-playbook")),
        (["ansible-playbook", "$PWD/../x.yml"], (True, "ansible-playbook+uncommitted-playbook")),
        (["just", "ansible-apply", "~/adhoc.yml"], (True, "ansible-apply+uncommitted-playbook")),
        (["just", "ansible-apply"], (True, None)),
        (["just", "check"], (False, None)),
        (["just"], (False, None)),
        (["ansible", "all", "-m", "ping"], (False, None)),
        (["ssh", "host", "sudo x", "ansible-playbook"], (False, None)),
        (["rsync", "-av", "./ansible", "host:/opt/"], (False, None)),
        (["git", "status"], (False, None)),
        ([], (False, None)),
    ],
)
def test_sanction_judges_the_first_known_head_only(
    tokens: list[str], expected: tuple[bool, str | None]
) -> None:
    assert sanction(tokens=tokens, known_heads=_KNOWN) == expected
