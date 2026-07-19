"""Install-shaped verification that the plugin-shipped hooks actually run.

The repo's other hook tests import the hook bodies from the CHECKOUT under
`uv run`, where the repo-root `_vendor/` tree satisfies a `returns` import.
The Claude Code installer ships something narrower: it copies ONLY
`.claude-plugin/` (flattened to the plugin root), and ships NO
`pyproject.toml`, `uv.lock`, or virtualenv — so a shipped hook executes under
bare `python3` with no third-party packages importable. A module-scope
third-party import there raises `ModuleNotFoundError` BEFORE `main()`'s
try/except can fail open, the process exits non-zero, and the guard denies
nothing. That is exactly how a broken `tmux_fleet_guard.py` shipped while
every in-repo test stayed green.

These tests reproduce the install shape instead of the dev shape:

1. copy ONLY the packaged subtree into `tmp_path`, laid out as the install
   cache does (`<root>/livespec/<version>/hooks/...`);
2. run each hook as a SUBPROCESS with `PYTHONPATH` cleared, user site-packages
   disabled, and the working directory outside the repo — with a guard
   assertion proving that sandbox genuinely cannot import `returns`;
3. assert real VERDICTS on a hazard/benign corpus, not merely exit codes.

Every corpus command below is INERT DATA fed to the classifier on stdin. The
classifier reads a JSON payload and prints a verdict; nothing here executes a
tmux, pkill, or killall command, and nothing may be changed to do so.
"""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_PACKAGED_ROOT = _REPO_ROOT / ".claude-plugin"
# The install cache keys each plugin by an opaque version directory. The exact
# value is irrelevant to what is under test — only the SHAPE
# (`<root>/livespec/<version>/hooks/...`) is — so this is a fixed synthetic
# stand-in, deliberately not derived from any real installed version.
_SYNTHETIC_VERSION_DIR = "0000000000aa"

# Commands the fleet guard MUST deny: every one of them can destroy the
# maintainer's shared default-socket tmux server carrying live agent sessions.
_DENY_COMMANDS = (
    "timeout 5 tmux kill-server",
    "nohup tmux kill-server",
    "exec tmux kill-server",
    "command tmux kill-server",
    "nice -n 5 tmux kill-server",
    "sudo tmux kill-server",
    "mise exec -- tmux kill-server",
    "echo | xargs tmux kill-server",
    "stdbuf -o0 tmux kill-server",
    "tmux kill-server -L default",
    "tmux -Ldefault kill-server",
    "tmux -L=default kill-server",
    "tmux -S default kill-server",
    "tmux -S /tmp/tmux-1000//default kill-server",
    "tmux -S /tmp/tmux-1000/../tmux-1000/default kill-server",
    "tmux -S /tmp/./tmux-1000/./default kill-server",
    "tmux -S /tmp/tmux-1000/default/ kill-server",
    "tmux -L scratch -S /tmp/tmux-1000/default kill-server",
    "tmux -S /tmp/tmux-1000/default -L scratch kill-server",
    "tmux -S /tmp/tmux-agents-1000/default kill-server",
    "tmux -S/tmp/tmux-1000/default kill-server",
    "tmux -S /tmp/scratch/a -S /tmp/tmux-1000/default kill-server",
    "tmux -L scratch -L default kill-server",
    "tmux -S /tmp/tmux-1000/other kill-server",
    "tmux kill-server -S",
    "tmux kill-server -L",
    "bash -c 'bash -c \"tmux kill-server\"'",
    'bash -c "bash -c \'bash -c \\"bash -c \\\\\\"bash -c tmux kill-server\\\\\\"\\"\'"',
    "sh -lc 'tmux kill-server'",
    "bash -ctmux' kill-server'",
    "zsh -c 'tmux kill-server'",
    "zsh -ic 'tmux kill-server'",
    "sh -c 'cd /tmp && tmux kill-server'",
    "eval 'tmux kill-server'",
    "echo x | xargs sh -c 'tmux kill-server'",
    "echo x | xargs -n 1 tmux",
    "echo x | xargs -- tmux",
    "pkill -f '^tmux'",
    "pkill -ftmux",
    "pkill -x tmux",
    "killall -9 tmux",
    "pkill -f 'tmux: server'",
    "pkill tmux",
    "pkill -f /usr/bin/tmux",
    "killall tmux",
    "kill -9 $(pgrep tmux)",
    "cd /tmp\ntmux kill-server",
    "tmux kill-server &",
    "(tmux kill-server)",
    "$(echo tmux) kill-server",
    "{ tmux kill-server; }",
    "/usr/bin/tmux kill-server",
    "./tmux kill-server",
    "echo hi; tmux kill-server",
    "true | tmux kill-server",
    "false || tmux kill-server",
    "tmux \\\n kill-server",
    "nohup (tmux kill-server)",
    "env -i tmux kill-server",
    "env -u TMUX_TMPDIR tmux kill-server",
    "env TMUX_TMPDIR=/tmp tmux kill-server",
    "TMUX_TMPDIR=/tmp tmux kill-server",
    "sudo -u ubuntu tmux kill-server",
    "sudo env -i timeout 5 tmux kill-server",
    "setsid tmux kill-server",
    "ionice -c2 -n7 tmux kill-server",
    "time tmux kill-server",
    "cd /tmp && tmux kill-server",
    "tmux kill-server '",
)

# Commands the fleet guard MUST allow: deliberately scoped scratch sockets,
# read-only tmux subcommands, hazard words appearing only as quoted data, and
# ordinary unrelated commands.
_ALLOW_COMMANDS = (
    "tmux -L lc_e2e_9 kill-server",
    "tmux -Lscratch kill-server",
    "tmux -S /tmp/scratch-abc/sock kill-server",
    "echo 'first; tmux kill-server'",
    "grep -r 'tmux kill-server' /data/projects",
    "git commit -m 'guard blocks tmux kill-server'",
    "cat > /tmp/x <<'EOF'\ntmux kill-server\nEOF",
    "tmux list-sessions",
    "python3 -c \"print('tmux kill-server')\"",
    "pkill -f myserver",
    "tmux -L scratch kill-session -t foo",
    "echo 'do not run pkill -f tmux'",
    "tmux -S /tmp/scratch/fleetwood kill-server",
    "tmux -S /tmp/fleet-sock kill-server",
    "tmux -L default -S /tmp/scratch/sock kill-server",
    "git log --grep='tmux kill-server'",
    "env -i tmux -L scratch9 kill-server",
    "exec tmux -L scratch9 kill-server",
    "echo kill-server | xargs tmux -L scratch9",
    "tmux -L scratch new -d -s probe",
    "kill -9 12345",
    "eval 'echo hi'",
    "pgrep tmux",
    "ls -la",
    "git status --short",
    "echo x | xargs -n 1",
    "eval",
    "echo 'unterminated",
    "mise exec --",
)

# Every shipped hook paired with a benign payload for its declared event. A
# hook that cannot even START on a benign payload is broken for every payload,
# so this is the cheapest possible detector for the packaging defect.
_BENIGN_PAYLOADS = (
    ("tmux_fleet_guard.py", {"tool_name": "Bash", "tool_input": {"command": "git status --short"}}),
    (
        "block_auto_memory.py",
        {"tool_name": "Write", "tool_input": {"file_path": "/tmp/notes.md", "content": "hi"}},
    ),
    ("warn_plan_persistence.py", {"transcript_path": "/nonexistent/transcript.jsonl"}),
    ("no_shadow_ledger.py", {"transcript_path": "/nonexistent/transcript.jsonl"}),
)


@dataclass(frozen=True, kw_only=True)
class HookRun:
    returncode: int
    stdout: str
    stderr: str


def _install_shaped_hooks_dir(*, root: Path) -> Path:
    """Copy ONLY `.claude-plugin/` into the install cache's flattened layout."""
    plugin_root = root / "cache" / "livespec" / _SYNTHETIC_VERSION_DIR
    shutil.copytree(
        _PACKAGED_ROOT,
        plugin_root,
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    hooks_dir = plugin_root / "hooks"
    assert hooks_dir.is_dir()
    return hooks_dir


def _bare_env() -> dict[str, str]:
    """Environment of an installed hook: no repo on the path, no user site."""
    env = dict(os.environ)
    for leaky in ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV"):
        env.pop(leaky, None)
    env["PYTHONNOUSERSITE"] = "1"
    return env


def _run_hook(*, script: Path, payload: str, cwd: Path) -> HookRun:
    completed = subprocess.run(
        [sys.executable, str(script)],
        input=payload,
        capture_output=True,
        text=True,
        env=_bare_env(),
        cwd=str(cwd),
        timeout=30,
        check=False,
    )
    return HookRun(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def _bash_payload(*, command: str) -> str:
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})


def _is_deny(*, stdout: str) -> bool:
    if not stdout.strip():
        return False
    decision = json.loads(stdout)
    specific = decision.get("hookSpecificOutput", {})
    return specific.get("permissionDecision") == "deny"


@pytest.fixture(name="installed_hooks")
def installed_hooks_fixture(tmp_path: Path) -> Path:
    return _install_shaped_hooks_dir(root=tmp_path)


def test_sandbox_cannot_import_returns(tmp_path: Path) -> None:
    """Guard the guard: prove the subprocess sandbox is genuinely bare.

    Without this, a host that happens to have `returns` installed would let the
    verdict tests pass against the very defect they exist to catch.
    """
    completed = subprocess.run(
        [sys.executable, "-c", "import returns"],
        capture_output=True,
        text=True,
        env=_bare_env(),
        cwd=str(tmp_path),
        timeout=30,
        check=False,
    )
    assert completed.returncode != 0
    assert "No module named 'returns'" in completed.stderr


@pytest.mark.parametrize(("script_name", "payload"), _BENIGN_PAYLOADS)
def test_every_shipped_hook_starts_cleanly(
    installed_hooks: Path, tmp_path: Path, script_name: str, payload: dict[str, object]
) -> None:
    run = _run_hook(
        script=installed_hooks / script_name,
        payload=json.dumps(payload),
        cwd=tmp_path,
    )
    assert run.returncode == 0, f"{script_name} failed to start: {run.stderr}"
    assert "ModuleNotFoundError" not in run.stderr
    assert run.stderr == ""


@pytest.mark.parametrize("command", _DENY_COMMANDS)
def test_installed_fleet_guard_denies_shared_socket_kills(
    installed_hooks: Path, tmp_path: Path, command: str
) -> None:
    run = _run_hook(
        script=installed_hooks / "tmux_fleet_guard.py",
        payload=_bash_payload(command=command),
        cwd=tmp_path,
    )
    assert run.returncode == 0, run.stderr
    assert _is_deny(stdout=run.stdout), f"install-shaped guard failed to deny: {command!r}"


@pytest.mark.parametrize("command", _ALLOW_COMMANDS)
def test_installed_fleet_guard_allows_scoped_and_benign_commands(
    installed_hooks: Path, tmp_path: Path, command: str
) -> None:
    run = _run_hook(
        script=installed_hooks / "tmux_fleet_guard.py",
        payload=_bash_payload(command=command),
        cwd=tmp_path,
    )
    assert run.returncode == 0, run.stderr
    assert not _is_deny(stdout=run.stdout), f"install-shaped guard wrongly denied: {command!r}"


def test_packaged_subtree_carries_every_import_the_hooks_need(installed_hooks: Path) -> None:
    """No shipped hook may import anything the install cache does not carry.

    The cache carries the standard library (bare `python3`) and whatever sits in
    the packaged subtree itself — nothing else. Read off the AST rather than the
    text so a docstring that DISCUSSES a third-party import cannot trip it.
    """
    assert (installed_hooks / "_result.py").is_file()
    shipped_modules = {script.stem for script in installed_hooks.glob("*.py")}
    allowed = set(sys.stdlib_module_names) | shipped_modules
    for script in sorted(installed_hooks.glob("*.py")):
        tree = ast.parse(script.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            roots: list[str] = []
            if isinstance(node, ast.Import):
                roots = [alias.name.split(".")[0] for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module is not None:
                roots = [node.module.split(".")[0]]
            for root in roots:
                assert root in allowed, f"{script.name} imports unshipped module {root!r}"
