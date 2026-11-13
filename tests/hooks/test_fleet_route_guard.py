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
_RECORD_PATH = _HOOKS_DIR / "_tailnet_record.py"


def _load_hook() -> ModuleType:
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    sys.modules.pop("fleet_route_guard", None)
    return importlib.import_module("fleet_route_guard")


def _payload(*, command: str) -> str:
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})


def test_tailnet_record_reading_is_a_cohesive_sibling_module() -> None:
    """Route policy consumes a public record reader instead of owning table parsing."""
    assert _RECORD_PATH.is_file()
    if str(_HOOKS_DIR) not in sys.path:
        sys.path.insert(0, str(_HOOKS_DIR))
    record_reader = importlib.import_module("_tailnet_record")
    record = record_reader._table_record(
        text=(
            "| Machine | SSH account | SSH server |\n"
            "| --- | --- | --- |\n"
            "| Example | ops | OpenSSH only |\n"
        )
    )
    assert record.machines["example"].account == "ops"
    assert hasattr(record_reader, "parse_tailnet_table")


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


def test_transfer_to_a_recorded_machine_under_the_wrong_account_is_denied(
    monkeypatch,
) -> None:
    """The destination account matters for scp, rsync and sftp as well as ssh."""
    hook = _load_hook()
    record = hook.TailnetRecord(
        machines={
            "examplehost": hook.MachineRoute(
                machine="examplehost", account="opsuser", openssh=True, tailscale_ssh=False
            )
        },
        answered=True,
    )

    def wrong_account(*, host: str, options: list[str]) -> str:
        _ = (host, options)
        return "wronguser"

    monkeypatch.setattr(hook, "_resolved_account", wrong_account)

    reason = hook._decide_segment(
        tokens=["scp", "./report", "wronguser@examplehost:/tmp/report"],
        record=record,
        domain="example-tailnet.ts.net",
    )

    assert reason is not None
    assert "documented account `opsuser`" in reason


def test_non_livespec_project_passes_through_even_when_a_record_is_available(
    monkeypatch, tmp_path: Path
) -> None:
    """The bundle may be installed broadly, but this guard is scoped to governed projects."""
    hook = _load_hook()
    monkeypatch.setattr(hook, "_project_dir", lambda: str(tmp_path))

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

    monkeypatch.setattr(
        hook,
        "resolve_tailnet_record",
        route_record,
    )
    monkeypatch.setattr(hook, "tailnet_domain", lambda: "example-tailnet.ts.net")
    monkeypatch.setattr(
        sys, "stdin", StringIO(_payload(command="tailscale ssh opsuser@examplehost"))
    )
    stdout = StringIO()
    with redirect_stdout(stdout):
        assert hook.main() == 0

    assert stdout.getvalue() == ""


def test_non_object_hook_payload_is_an_advisory_allow(monkeypatch) -> None:
    """Malformed hook input must not turn a typed decoding boundary into a denial."""
    hook = _load_hook()
    monkeypatch.setattr(sys, "stdin", StringIO("[]"))
    stdout = StringIO()
    with redirect_stdout(stdout):
        assert hook.main() == 0

    assert stdout.getvalue() == ""


def test_value_taking_ssh_options_do_not_hide_the_target_host(monkeypatch) -> None:
    """`ssh -p 2222 user@host` still resolves the host, and -p/-i reach `ssh -G`."""
    hook = _load_hook()
    record = hook.TailnetRecord(
        machines={
            "examplehost": hook.MachineRoute(
                machine="examplehost", account="opsuser", openssh=True, tailscale_ssh=False
            )
        },
        answered=True,
    )
    seen: list[list[str]] = []

    def resolved(*, host: str, options: list[str]) -> str:
        _ = host
        seen.append(options)
        return "wronguser"

    monkeypatch.setattr(hook, "_resolved_account", resolved)

    for arguments in (
        ["-p", "2222", "wronguser@examplehost.example-tailnet.ts.net", "true"],
        ["-i", "/tmp/key", "-p", "2222", "examplehost", "true"],
        ["-J", "jump", "-F", "/tmp/cfg", "examplehost"],
        ["-4A", "-p2222", "examplehost"],
        ["-vp", "2222", "examplehost"],
    ):
        reason = hook._decide_segment(
            tokens=["ssh", *arguments], record=record, domain="example-tailnet.ts.net"
        )
        assert reason is not None, arguments
        assert "documented account `opsuser`" in reason

    assert ["-p", "2222"] in [options[-2:] for options in seen if "-i" not in options]
    assert any("-i" in options and "/tmp/key" in options for options in seen)
    assert any("-F" in options and "/tmp/cfg" in options for options in seen)


def test_sftp_options_do_not_hide_the_target_host(monkeypatch) -> None:
    """`sftp -P 2222 user@host` resolves the host; -P is a port, -l is no login user."""
    hook = _load_hook()
    record = hook.TailnetRecord(
        machines={
            "examplehost": hook.MachineRoute(
                machine="examplehost", account="opsuser", openssh=True, tailscale_ssh=False
            )
        },
        answered=True,
    )
    seen: list[list[str]] = []

    def resolved(*, host: str, options: list[str]) -> str:
        _ = host
        seen.append(options)
        return "wronguser"

    monkeypatch.setattr(hook, "_resolved_account", resolved)

    for arguments in (
        ["-P", "2222", "wronguser@examplehost.example-tailnet.ts.net"],
        ["-P2222", "examplehost"],
        ["-vP", "2222", "examplehost"],
        ["-l", "100", "-i", "/tmp/key", "examplehost"],
        ["-b", "/tmp/batch", "-F", "/tmp/cfg", "examplehost"],
    ):
        reason = hook._decide_segment(
            tokens=["sftp", *arguments], record=record, domain="example-tailnet.ts.net"
        )
        assert reason is not None, arguments
        assert "documented account `opsuser`" in reason

    assert any(options == ["-p", "2222"] for options in seen)
    assert any("-i" in options and "/tmp/key" in options for options in seen)
    assert any("-F" in options and "/tmp/cfg" in options for options in seen)
    assert not any("-l" in options for options in seen)


def _config_default_user_resolver(seen: list[list[str]]):
    """A stand-in for `ssh -G` whose configuration maps the host to the documented account."""

    def resolved(*, host: str, options: list[str]) -> str:
        _ = host
        seen.append(options)
        for index, option in enumerate(options[:-1]):
            if option == "-o" and options[index + 1].lower().startswith("user="):
                return options[index + 1].split("=", 1)[1]
            if option == "-l":
                return options[index + 1]
        return "opsuser"

    return resolved


def test_scp_and_rsync_forward_their_ssh_options_to_the_resolver(monkeypatch) -> None:
    """`scp -o User=x` and `rsync -e 'ssh -o User=x'` change the login, not just the config."""
    hook = _load_hook()
    record = hook.TailnetRecord(
        machines={
            "examplehost": hook.MachineRoute(
                machine="examplehost", account="opsuser", openssh=True, tailscale_ssh=False
            )
        },
        answered=True,
    )
    seen: list[list[str]] = []
    monkeypatch.setattr(hook, "_resolved_account", _config_default_user_resolver(seen))

    for tokens in (
        ["scp", "-o", "User=wronguser", "f.txt", "examplehost:/tmp/"],
        ["scp", "-oUser=wronguser", "f.txt", "examplehost:/tmp/"],
        ["scp", "-P", "2222", "-o", "User=wronguser", "f.txt", "examplehost:/tmp/"],
        ["scp", "-i", "/tmp/key", "-l", "100", "-o", "User=wronguser", "f.txt", "examplehost:/"],
        ["rsync", "-av", "-e", "ssh -o User=wronguser", "./x", "examplehost:/tmp/x"],
        ["rsync", "-ave", "ssh -l wronguser -p 2222", "./x", "examplehost:/tmp/x"],
        ["rsync", "--rsh=ssh -o User=wronguser", "./x", "examplehost:/tmp/x"],
        ["rsync", "--rsh", "ssh -o User=wronguser", "./x", "examplehost:/tmp/x"],
        ["rsync", "./x", "examplehost:/tmp/x", "-e", "ssh -o User=wronguser"],
    ):
        reason = hook._decide_segment(tokens=tokens, record=record, domain="example-tailnet.ts.net")
        assert reason is not None, tokens
        assert "documented account `opsuser`" in reason

    assert any(options[:2] == ["-p", "2222"] for options in seen)
    assert any("-i" in options and "/tmp/key" in options for options in seen)
    assert not any("100" in options for options in seen)


def test_scp_and_rsync_with_the_configured_account_stay_allowed(monkeypatch) -> None:
    """A transfer whose resolved login is the documented account is not denied."""
    hook = _load_hook()
    record = hook.TailnetRecord(
        machines={
            "examplehost": hook.MachineRoute(
                machine="examplehost", account="opsuser", openssh=True, tailscale_ssh=False
            )
        },
        answered=True,
    )
    monkeypatch.setattr(hook, "_resolved_account", _config_default_user_resolver([]))

    for tokens in (
        ["scp", "-P", "2222", "f.txt", "examplehost:/tmp/"],
        ["scp", "-o", "User=opsuser", "f.txt", "examplehost:/tmp/"],
        ["rsync", "-av", "-e", "ssh -p 2222", "./x", "examplehost:/tmp/x"],
        ["rsync", "-av", "-e", "ssh -o User=opsuser", "./x", "examplehost:/tmp/x"],
        ["rsync", "-av", "-e", "custom-rsh", "./x", "examplehost:/tmp/x"],
    ):
        assert (
            hook._decide_segment(tokens=tokens, record=record, domain="example-tailnet.ts.net")
            is None
        ), tokens
