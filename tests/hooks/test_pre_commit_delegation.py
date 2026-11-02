"""Consumer opt-in coverage for delegated pre-commit aggregates."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from livespec_dev_tooling.config import load_delegated_pre_commit

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "dev-tooling" / "just" / "check-pre-commit.sh"

_UV_STUB = """#!/bin/sh
echo "uv $*" >> "$STUB_LOG"
case "$4 $5" in
    "livespec_dev_tooling.pre_commit_delegate run") exit "$STUB_DELEGATE_EXIT" ;;
esac
exit 99
"""

_JUST_STUB = """#!/bin/sh
echo "just $*" >> "$STUB_LOG"
exit 0
"""


def test_repository_configuration_opts_in_to_delegated_pre_commit() -> None:
    assert load_delegated_pre_commit(repo_root=_REPO_ROOT) is True


@pytest.mark.parametrize(
    ("delegate_exit", "expected_local_calls", "expected_returncode"),
    [
        (0, [], 0),
        (75, ["just check-plugin-structure", "just check-lint", "just check-format"], 0),
        (1, [], 1),
    ],
)
def test_pre_commit_recipe_runs_local_aggregate_only_for_delegate_fallback(
    tmp_path: Path,
    delegate_exit: int,
    expected_local_calls: list[str],
    expected_returncode: int,
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in (("uv", _UV_STUB), ("just", _JUST_STUB)):
        stub = bin_dir / name
        stub.write_text(body, encoding="utf-8")
        stub.chmod(0o755)
    log = tmp_path / "stub.log"
    completed = subprocess.run(
        ["bash", str(_SCRIPT)],
        cwd=tmp_path,
        env={
            **os.environ,
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
            "STUB_DELEGATE_EXIT": str(delegate_exit),
            "STUB_LOG": str(log),
        },
        capture_output=True,
        check=False,
        text=True,
    )

    calls = log.read_text(encoding="utf-8").splitlines()

    assert calls[0] == "uv run python -m livespec_dev_tooling.pre_commit_delegate run"
    assert calls[1:] == expected_local_calls
    assert completed.returncode == expected_returncode
