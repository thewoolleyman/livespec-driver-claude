"""Integration-tier realization of the delegated pre-push gate scenario.

Drives the real `dev-tooling/just/check-pre-push.sh` as a subprocess against a
fixture project. `uv` and `just` are stubbed on PATH so the recipe's branching
is observable without a cluster: the stub forwards the real shared delegation
client's `enabled` probe to this interpreter, and records `run` and `just check`
invocations instead of executing them.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from livespec_dev_tooling.config import load_delegated_gate

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPT = _REPO_ROOT / "dev-tooling" / "just" / "check-pre-push.sh"
_OPT_IN = "[tool.livespec_dev_tooling]\ndelegated_gate = true\n"

_UV_STUB = """#!/bin/sh
# argv: run python -m <module> <command>
echo "uv $*" >> "$STUB_LOG"
case "$4 $5" in
    "livespec_dev_tooling.green_token check") exit 1 ;;
    "livespec_dev_tooling.gate_remote_delegate enabled")
        exec "$STUB_PYTHON" -m livespec_dev_tooling.gate_remote_delegate enabled ;;
    "livespec_dev_tooling.gate_remote_delegate run") exit "$STUB_RUN_EXIT" ;;
esac
exit 99
"""

_JUST_STUB = """#!/bin/sh
echo "just $*" >> "$STUB_LOG"
exit 0
"""


def _run_recipe(
    *, tmp_path: Path, kubeconfig_readable: bool, run_exit: int
) -> tuple[subprocess.CompletedProcess[str], list[str]]:
    project = tmp_path / "project"
    project.mkdir()
    (project / "pyproject.toml").write_text(_OPT_IN, encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    for name, body in (("uv", _UV_STUB), ("just", _JUST_STUB)):
        stub = bin_dir / name
        stub.write_text(body, encoding="utf-8")
        stub.chmod(0o755)
    kubeconfig = tmp_path / "gates.kubeconfig"
    if kubeconfig_readable:
        kubeconfig.write_text("apiVersion: v1\n", encoding="utf-8")
    log = tmp_path / "stub.log"
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "STUB_LOG": str(log),
        "STUB_PYTHON": sys.executable,
        "STUB_RUN_EXIT": str(run_exit),
        "GATES_KUBECONFIG": str(kubeconfig),
    }
    completed = subprocess.run(
        ["bash", str(_SCRIPT)],
        cwd=project,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    return completed, calls


def test_repository_configuration_opts_in_to_the_delegated_gate() -> None:
    assert load_delegated_gate(repo_root=_REPO_ROOT) is True


@pytest.mark.integration
@pytest.mark.parametrize("run_exit", [0, 1, 2])
def test_delegating_host_runs_the_client_and_never_the_local_gate(
    tmp_path: Path, run_exit: int
) -> None:
    completed, calls = _run_recipe(tmp_path=tmp_path, kubeconfig_readable=True, run_exit=run_exit)

    assert "uv run python -m livespec_dev_tooling.gate_remote_delegate run" in calls
    assert not any(call.startswith("just ") for call in calls)
    assert completed.returncode == run_exit


def test_host_without_the_credential_gates_locally_and_says_so(tmp_path: Path) -> None:
    completed, calls = _run_recipe(tmp_path=tmp_path, kubeconfig_readable=False, run_exit=0)

    assert "just check" in calls
    assert not any(call.endswith("gate_remote_delegate run") for call in calls)
    assert "gating locally" in completed.stderr + completed.stdout
    assert completed.returncode == 0
