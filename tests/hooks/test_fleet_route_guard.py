"""Executable coverage for the advisory fleet SSH route guard."""

from __future__ import annotations

import importlib
import json
import sys
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import ModuleType

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HOOKS_DIR = _REPO_ROOT / ".claude-plugin" / "hooks"
_HOOK_PATH = _HOOKS_DIR / "fleet_route_guard.py"


def _load_hook() -> ModuleType:
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    sys.modules.pop("fleet_route_guard", None)
    return importlib.import_module("fleet_route_guard")


def _payload(*, command: str) -> str:
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})


def test_tailscale_ssh_without_a_tailscale_server_names_the_documented_openssh_route(
    monkeypatch,
) -> None:
    """A Mac-like row teaches the OpenSSH tailnet route before the command runs."""
    assert _HOOK_PATH.is_file()
    hook = _load_hook()

    def route_record(*, project_dir: str) -> object:
        _ = project_dir
        return hook.TailnetRecord(
            machines={
                "examplehost": hook.MachineRoute(
                    machine="examplehost",
                    account="opsuser",
                    openssh=True,
                    tailscale_ssh=False,
                )
            },
            answered=True,
        )

    monkeypatch.setattr(hook, "resolve_tailnet_record", route_record)
    monkeypatch.setattr(hook, "tailnet_domain", lambda: "example-tailnet.ts.net")
    monkeypatch.setattr(hook, "_project_dir", lambda: "/project")
    command = "tailscale ssh opsuser@examplehost true"
    monkeypatch.setattr(sys, "stdin", StringIO(_payload(command=command)))
    stdout = StringIO()
    with redirect_stdout(stdout):
        assert hook.main() == 0

    decision = json.loads(stdout.getvalue())["hookSpecificOutput"]
    assert decision["permissionDecision"] == "deny"
    assert "ssh opsuser@examplehost.example-tailnet.ts.net" in decision["permissionDecisionReason"]
    assert "tailscale-admin README machine table" in decision["permissionDecisionReason"]
