"""Witnesses for this Driver's delegated pre-commit aggregate wiring."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

from livespec_dev_tooling.config import load_delegated_pre_commit, load_gate_check_suite

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PRE_COMMIT_SCRIPT = _REPO_ROOT / "dev-tooling" / "just" / "check-pre-commit.sh"


def test_repository_configuration_opts_in_to_delegated_pre_commit() -> None:
    """The released delegated pre-commit route is enabled for this Driver."""
    assert load_delegated_pre_commit(repo_root=_REPO_ROOT) is True


def test_gate_suite_preserves_the_bootstrap_before_the_pre_commit_gate() -> None:
    """The delegate can replace only the final aggregate with the gated-tree recipe."""
    assert load_gate_check_suite(repo_root=_REPO_ROOT) == (
        "install-worktree-pack",
        "check-pre-commit",
    )


def _run_pre_commit(*, tmp_path: Path, delegate_status: int) -> tuple[int, list[str]]:
    """Run the wrapper with logged stand-ins for the delegate and aggregate."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True)
    tools = {
        "uv": """#!/usr/bin/env bash
printf 'uv %s\\n' "$*" >> "$FAKE_LOG"
case "$*" in
  *"pre_commit_delegate run"*) exit "$FAKE_DELEGATE_STATUS" ;;
esac
exit 99
""",
        "just": """#!/usr/bin/env bash
printf 'just %s\\n' "$*" >> "$FAKE_LOG"
exit 0
""",
    }
    for name, body in tools.items():
        tool = bin_dir / name
        tool.write_text(body, encoding="utf-8")
        tool.chmod(tool.stat().st_mode | stat.S_IXUSR)
    log = tmp_path / "calls.log"
    log.touch()
    environment = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "FAKE_DELEGATE_STATUS": str(delegate_status),
        "FAKE_LOG": str(log),
        "LIVESPEC_GATE_CONTEXT": "1",
    }
    environment.pop("LIVESPEC_GATE_CONTEXT")
    completed = subprocess.run(
        ["bash", str(_PRE_COMMIT_SCRIPT)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode, log.read_text(encoding="utf-8").splitlines()


def test_pre_commit_delegates_before_running_the_local_aggregate(tmp_path: Path) -> None:
    """Only the delegate's local-fallback result invokes the local aggregate."""
    assert _PRE_COMMIT_SCRIPT.is_file()

    passed_rc, passed_calls = _run_pre_commit(tmp_path=tmp_path / "passed", delegate_status=0)
    failed_rc, failed_calls = _run_pre_commit(tmp_path=tmp_path / "failed", delegate_status=1)
    local_rc, local_calls = _run_pre_commit(tmp_path=tmp_path / "local", delegate_status=75)

    assert passed_rc == 0
    assert failed_rc == 1
    assert local_rc == 0
    assert any("pre_commit_delegate run" in call for call in passed_calls)
    assert any("pre_commit_delegate run" in call for call in failed_calls)
    assert any("pre_commit_delegate run" in call for call in local_calls)
    assert not any(call.startswith("just") for call in passed_calls)
    assert not any(call.startswith("just") for call in failed_calls)
    assert local_calls[-1] == "just check-pre-commit-local"
