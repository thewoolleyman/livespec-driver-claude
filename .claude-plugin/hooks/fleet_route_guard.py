#!/usr/bin/env python3
"""Advisory PreToolUse guard for documented fleet SSH routes.

The tailnet record is deliberately read at decision time from a sibling
``tailscale-admin`` clone.  This keeps machine names, accounts, server types,
and the tailnet suffix out of the bundle, where they would immediately drift.
Unreadable records and commands the small shell reader cannot understand are
allows: this guard teaches a known bad route; it never blocks on uncertainty.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from _guard_telemetry import emit_guard_verdict

__all__: list[str] = []

_PROJECT_DIR_ENV = "CLAUDE_PROJECT_DIR"
_TABLE_DIVIDER = re.compile(r"^\s*\|?(?:\s*:?-+:?\s*\|)+\s*$")
_WRAPPERS = frozenset({"env", "timeout", "command", "sudo"})


@dataclass(frozen=True, kw_only=True)
class MachineRoute:
    """The route-relevant fields of one row in tailscale-admin's machine table."""

    machine: str
    account: str | None
    openssh: bool
    tailscale_ssh: bool


@dataclass(frozen=True, kw_only=True)
class TailnetRecord:
    """A parsed record; ``answered`` distinguishes an empty table from no record."""

    machines: dict[str, MachineRoute]
    answered: bool


def _project_dir() -> str:
    return os.environ.get(_PROJECT_DIR_ENV, "").strip()


def _read(*, path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _primary_checkout(*, root: Path) -> Path | None:
    pointer = root / ".git"
    text = _read(path=pointer) if pointer.is_file() else None
    if not text:
        return None
    gitdir = text.partition("gitdir:")[2].strip()
    marker = "/.git/worktrees/"
    return Path(gitdir.split(marker, 1)[0]) if marker in gitdir else None


def _record_path(*, project_dir: str) -> Path | None:
    if not project_dir:
        return None
    root = Path(project_dir)
    primary = _primary_checkout(root=root)
    peer = (primary or root).parent / "tailscale-admin" / "README.md"
    return peer


def _cell(*, value: str) -> str:
    return re.sub(r"[*`_]", "", value).strip()


def _servers(*, value: str) -> tuple[bool, bool]:
    lowered = _cell(value=value).lower()
    return "openssh" in lowered, "tailscale ssh" in lowered


def _table_record(*, text: str) -> TailnetRecord:
    lines = text.splitlines()
    for index, line in enumerate(lines[:-1]):
        headings = [_cell(value=part).lower() for part in line.strip().strip("|").split("|")]
        if not {"machine", "ssh account", "ssh server"} <= set(headings):
            continue
        if not _TABLE_DIVIDER.match(lines[index + 1]):
            continue
        machine_index = headings.index("machine")
        account_index = headings.index("ssh account")
        server_index = headings.index("ssh server")
        needed = max(machine_index, account_index, server_index)
        machines: dict[str, MachineRoute] = {}
        for row in lines[index + 2 :]:
            if "|" not in row:
                break
            values = [_cell(value=part) for part in row.strip().strip("|").split("|")]
            if len(values) <= needed:
                continue
            machine = values[machine_index].lower().rstrip(".")
            account = values[account_index] or None
            if not machine:
                continue
            openssh, tailscale_ssh = _servers(value=values[server_index])
            machines[machine] = MachineRoute(
                machine=machine,
                account=account,
                openssh=openssh,
                tailscale_ssh=tailscale_ssh,
            )
        return TailnetRecord(machines=machines, answered=True)
    return TailnetRecord(machines={}, answered=False)


def resolve_tailnet_record(*, project_dir: str) -> TailnetRecord:
    """Read the sibling tailnet table, or report that no record answered."""
    path = _record_path(project_dir=project_dir)
    text = _read(path=path) if path else None
    if text is None:
        return TailnetRecord(machines={}, answered=False)
    return _table_record(text=text)


def tailnet_domain() -> str | None:
    """Read the local client's DNS suffix without contacting a peer."""
    try:
        result = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True,
            text=True,
            check=False,
            timeout=2,
        )
        payload = json.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    self_row = payload.get("Self")
    if not isinstance(self_row, dict):
        return None
    dns_name = self_row.get("DNSName")
    if not isinstance(dns_name, str):
        return None
    parts = dns_name.rstrip(".").split(".", 1)
    return parts[1].lower() if len(parts) == 2 and parts[1] else None


def _segments(*, command: str) -> list[list[str]] | None:
    try:
        return [
            shlex.split(piece) for piece in re.split(r"(?:;|&&|\|\|)", command) if piece.strip()
        ]
    except ValueError:
        return None


def _head(*, tokens: list[str]) -> tuple[str, list[str]] | None:
    index = 0
    while index < len(tokens) and ("=" in tokens[index] or tokens[index] in _WRAPPERS):
        if tokens[index] == "timeout":
            index += 2
        else:
            index += 1
    if index >= len(tokens):
        return None
    return Path(tokens[index]).name.lower(), tokens[index + 1 :]


def _target(*, arguments: list[str]) -> tuple[str | None, str | None, list[str]]:
    """Return target host, explicit account, and ssh options relevant to ``ssh -G``."""
    index = 0
    options: list[str] = []
    while index < len(arguments) and arguments[index].startswith("-"):
        option = arguments[index]
        if option in {"-l", "-o"} and index + 1 < len(arguments):
            options.extend([option, arguments[index + 1]])
            index += 2
        else:
            index += 1
    if index >= len(arguments):
        return None, None, options
    target = arguments[index]
    if "@" in target:
        account, host = target.rsplit("@", 1)
        return host, account or None, options
    return target, None, options


def _machine(*, target: str, record: TailnetRecord, domain: str | None) -> MachineRoute | None:
    lowered = target.lower().rstrip(".")
    direct = record.machines.get(lowered)
    if direct:
        return direct
    if domain and lowered.endswith("." + domain):
        return record.machines.get(lowered[: -(len(domain) + 1)])
    return None


def _resolved_account(*, host: str, options: list[str]) -> str | None:
    try:
        result = subprocess.run(
            ["ssh", *options, "-G", host], capture_output=True, text=True, check=False, timeout=2
        )
    except (OSError, subprocess.SubprocessError):
        return None
    for line in result.stdout.splitlines():
        key, _, value = line.partition(" ")
        if key.lower() == "user" and value.strip():
            return value.strip()
    return None


def _deny(*, reason: str) -> str:
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        }
    )


def _route_reason(*, route: MachineRoute, domain: str | None) -> str:
    suffix = f".{domain}" if domain else ""
    unknown = " The tailnet domain could not be read locally." if not domain else ""
    return (
        "BLOCKED by fleet_route_guard.py: this machine does not run Tailscale SSH. "
        f"Use `ssh {route.account}@{route.machine}{suffix}` instead. "
        "The tailscale-admin README machine table documents each machine's SSH account "
        "and SSH server."
        f"{unknown}"
    )


def _account_reason(*, route: MachineRoute) -> str:
    return (
        "BLOCKED by fleet_route_guard.py: this route uses the wrong login account. "
        f"Use the documented account `{route.account}`. "
        "The tailscale-admin README machine table documents each machine's SSH account "
        "and SSH server."
    )


def _decide_segment(*, tokens: list[str], record: TailnetRecord, domain: str | None) -> str | None:
    parsed = _head(tokens=tokens)
    if parsed is None:
        return None
    head, arguments = parsed
    if head == "tailscale" and arguments[:1] == ["ssh"]:
        host, _, _ = _target(arguments=arguments[1:])
        route = _machine(target=host, record=record, domain=domain) if host else None
        if route and route.account and route.openssh and not route.tailscale_ssh:
            return _route_reason(route=route, domain=domain)
        return None
    if head not in {"ssh", "scp", "rsync", "sftp"}:
        return None
    host, explicit, options = _target(arguments=arguments)
    route = _machine(target=host, record=record, domain=domain) if host else None
    if not route or not route.account or not host:
        return None
    account = explicit or _resolved_account(host=host, options=options if head == "ssh" else [])
    return _account_reason(route=route) if account and account != route.account else None


def _command(*, payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    input_data = payload.get("tool_input")
    if not isinstance(input_data, dict):
        return None
    command = input_data.get("command")
    return command if isinstance(command, str) else None


def main() -> int:
    """Emit a refusal only for a route the record positively identifies as wrong."""
    try:
        command = _command(payload=json.load(sys.stdin))
        if not command:
            return 0
        record = resolve_tailnet_record(project_dir=_project_dir())
        domain = tailnet_domain()
        tokens_by_segment = _segments(command=command)
        reason = None
        if record.answered and tokens_by_segment is not None:
            for tokens in tokens_by_segment:
                reason = _decide_segment(tokens=tokens, record=record, domain=domain)
                if reason:
                    break
        if reason:
            _ = sys.stdout.write(_deny(reason=reason) + "\n")
        emit_guard_verdict(
            guard="fleet_route_guard",
            matched_rule="route" if reason else None,
            attributes={"record_answered": record.answered},
        )
    except (AttributeError, KeyError, OSError, TypeError, ValueError):
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
