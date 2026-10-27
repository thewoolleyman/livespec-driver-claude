"""Behavioral coverage for the repository's delegated pre-push entrypoint."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PRE_PUSH_SCRIPT = _REPO_ROOT / "dev-tooling/just/check-pre-push.sh"


def _write_command(*, path: Path, body: str) -> None:
    """Write one executable command for the pre-push subprocess."""
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _pre_push_environment(
    *, tmp_path: Path, enabled_status: int, run_status: int
) -> tuple[dict[str, str], Path]:
    """Create isolated client commands and return their environment and event log."""
    events = tmp_path / "events.log"
    _write_command(
        path=tmp_path / "uv",
        body="""#!/usr/bin/env bash
set -eu
printf '%s\\n' "$*" >> "$PRE_PUSH_EVENTS"
case "$*" in
  "run python -m livespec_dev_tooling.green_token check") exit 1 ;;
  "run python -m livespec_dev_tooling.gate_remote_delegate enabled")
    exit "$DELEGATE_ENABLED_STATUS"
    ;;
  "run python -m livespec_dev_tooling.gate_remote_delegate run")
    exit "$DELEGATE_RUN_STATUS"
    ;;
  *) exit 99 ;;
esac
""",
    )
    _write_command(
        path=tmp_path / "just",
        body="""#!/usr/bin/env bash
set -eu
printf 'just %s\\n' "$*" >> "$PRE_PUSH_EVENTS"
exit 0
""",
    )
    environment = {
        **os.environ,
        "DELEGATE_ENABLED_STATUS": str(enabled_status),
        "DELEGATE_RUN_STATUS": str(run_status),
        "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
        "PRE_PUSH_EVENTS": str(events),
    }
    return environment, events


def _run_pre_push(
    *, tmp_path: Path, enabled_status: int, run_status: int
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    """Run the repository pre-push recipe against isolated client commands."""
    environment, events = _pre_push_environment(
        tmp_path=tmp_path,
        enabled_status=enabled_status,
        run_status=run_status,
    )
    result = subprocess.run(
        ["bash", str(_PRE_PUSH_SCRIPT)],
        capture_output=True,
        check=False,
        env=environment,
        text=True,
    )
    return result, events.read_text(encoding="utf-8").splitlines()


def test_repository_opted_in_to_the_delegated_gate_client() -> None:
    """The client is selected only by an explicit repository-level opt-in."""
    pyproject = (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "[tool.livespec_dev_tooling]\ndelegated_gate = true" in pyproject
    assert 'tag = "v1.134.2"' in pyproject


def test_delegating_host_executes_client_without_local_check(tmp_path: Path) -> None:
    """A selected delegate owns the outcome and cannot reach the local aggregate."""
    result, events = _run_pre_push(
        tmp_path=tmp_path,
        enabled_status=0,
        run_status=23,
    )

    assert result.returncode == 23
    assert events == [
        "run python -m livespec_dev_tooling.green_token check",
        "run python -m livespec_dev_tooling.gate_remote_delegate enabled",
        "run python -m livespec_dev_tooling.gate_remote_delegate run",
    ]
