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
from pathlib import Path
from typing import cast

from _guard_telemetry import emit_guard_verdict
from _remote_target import host_of_target
from _tailnet_record import MachineRoute, TailnetRecord, resolve_tailnet_record, tailnet_domain

__all__: list[str] = []

_PROJECT_DIR_ENV = "CLAUDE_PROJECT_DIR"
_WRAPPERS = frozenset({"env", "timeout", "command", "sudo"})


def _project_dir() -> str:
    return os.environ.get(_PROJECT_DIR_ENV, "").strip()


def _governed(*, project_dir: str) -> bool:
    """A real project without the livespec config is outside this hook's scope.

    A non-existent path is retained as an allow-to-evaluate test seam: actual
    hook invocations always provide an existing working project.
    """
    root = Path(project_dir)
    return not root.exists() or (root / ".livespec.jsonc").is_file()


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


_SSH_VALUE_OPTIONS = frozenset("BbcDEeFIiJLlmOopQRSWw")
_SFTP_VALUE_OPTIONS = frozenset("BbcDFiJloPRSs")
_SCP_VALUE_OPTIONS = frozenset("cDFiJloPS")
_RSYNC_VALUE_OPTIONS = frozenset("eBfMT@")
# Option letters whose values change what ``ssh -G`` resolves, mapped to the ssh letter.
# ssh's ``-l`` is the login user; sftp's and scp's ``-l`` is a bandwidth limit, never forwarded.
_SSH_RESOLUTION_OPTIONS = {flag: flag for flag in "FiJlop"}
_SFTP_RESOLUTION_OPTIONS = {"F": "F", "i": "i", "J": "J", "o": "o", "P": "p"}
_SCP_RESOLUTION_OPTIONS = _SFTP_RESOLUTION_OPTIONS
# rsync's remote shell is chosen with ``-e``/``--rsh``; its argv is parsed as an ssh command line.
_RSYNC_RESOLUTION_OPTIONS = {"e": "e"}


def _short_options(
    *,
    cluster: str,
    following: list[str],
    value_options: frozenset[str],
    resolution_options: dict[str, str],
) -> tuple[list[str], int] | None:
    """Relevant options of one short-option cluster and the following tokens it consumed."""
    options: list[str] = []
    position = 1
    while position < len(cluster):
        flag = cluster[position]
        position += 1
        if flag not in value_options:
            continue
        value = cluster[position:]
        consumed = 0
        if not value:
            if not following:
                return None
            value = following[0]
            consumed = 1
        if flag in resolution_options:
            options.extend([f"-{resolution_options[flag]}", value])
        return options, consumed
    return options, 0


def _long_option(*, cluster: str, following: list[str]) -> tuple[list[str], int] | None:
    """The rsync ``--rsh`` remote shell, as an ``-e`` option, and the tokens it consumed."""
    name, equals, inline = cluster.partition("=")
    if name != "--rsh":
        return [], 0
    if equals:
        return ["-e", inline], 0
    if not following:
        return None
    return ["-e", following[0]], 1


def _scan(
    *,
    arguments: list[str],
    value_options: frozenset[str],
    resolution_options: dict[str, str],
    permute: bool = False,
) -> tuple[list[str], list[str]] | None:
    """Return operands and the options relevant to ``ssh -G``; None when an option lacks a value.

    ssh and sftp stop option parsing at the first operand; scp and rsync accept options after it.
    """
    index = 0
    options: list[str] = []
    operands: list[str] = []
    while index < len(arguments):
        cluster = arguments[index]
        index += 1
        if cluster == "--":
            operands.extend(arguments[index:])
            break
        if not cluster.startswith("-") or cluster == "-":
            operands.append(cluster)
            if permute:
                continue
            operands.extend(arguments[index:])
            break
        following = arguments[index:]
        if cluster.startswith("--"):
            found = _long_option(cluster=cluster, following=following)
        else:
            found = _short_options(
                cluster=cluster,
                following=following,
                value_options=value_options,
                resolution_options=resolution_options,
            )
        if found is None:
            return None
        options.extend(found[0])
        index += found[1]
    return operands, options


def _target(
    *,
    arguments: list[str],
    value_options: frozenset[str] = _SSH_VALUE_OPTIONS,
    resolution_options: dict[str, str] = _SSH_RESOLUTION_OPTIONS,
) -> tuple[str | None, str | None, list[str]]:
    """Return target host, explicit account, and ssh options relevant to ``ssh -G``."""
    scanned = _scan(
        arguments=arguments, value_options=value_options, resolution_options=resolution_options
    )
    if scanned is None or not scanned[0]:
        return None, None, [] if scanned is None else scanned[1]
    operands, options = scanned
    target = operands[0]
    if "@" in target:
        account, host = target.rsplit("@", 1)
        return host, account or None, options
    return target, None, options


def _rsh_options(*, command: str) -> list[str]:
    """The ssh options an rsync ``-e`` command carries; other remote shells forward nothing."""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return []
    if not tokens or Path(tokens[0]).name.lower() != "ssh":
        return []
    scanned = _scan(
        arguments=tokens[1:],
        value_options=_SSH_VALUE_OPTIONS,
        resolution_options=_SSH_RESOLUTION_OPTIONS,
    )
    return [] if scanned is None else scanned[1]


def _transfer_target(
    *, head: str, arguments: list[str]
) -> tuple[str | None, str | None, list[str]]:
    """The final transfer operand's host and explicit user, plus the ssh options it runs under."""
    rsync = head == "rsync"
    scanned = _scan(
        arguments=arguments,
        value_options=_RSYNC_VALUE_OPTIONS if rsync else _SCP_VALUE_OPTIONS,
        resolution_options=_RSYNC_RESOLUTION_OPTIONS if rsync else _SCP_RESOLUTION_OPTIONS,
        permute=True,
    )
    if scanned is None or not scanned[0]:
        return None, None, []
    operands, options = scanned
    if rsync:
        remote_shells = options[1::2]
        options = _rsh_options(command=remote_shells[-1]) if remote_shells else []
    target = operands[-1]
    authority = target.split(":", 1)[0].removeprefix("scp://").removeprefix("sftp://")
    account = authority.rsplit("@", 1)[0] if "@" in authority else None
    return host_of_target(target=target), account or None, options


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
    if head in {"scp", "rsync"}:
        host, explicit, options = _transfer_target(head=head, arguments=arguments)
    elif head == "sftp":
        host, explicit, options = _target(
            arguments=arguments,
            value_options=_SFTP_VALUE_OPTIONS,
            resolution_options=_SFTP_RESOLUTION_OPTIONS,
        )
    else:
        host, explicit, options = _target(arguments=arguments)
    route = _machine(target=host, record=record, domain=domain) if host else None
    if not route or not route.account or not host:
        return None
    account = explicit or _resolved_account(host=host, options=options)
    return _account_reason(route=route) if account and account != route.account else None


def _command(*, payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    input_data = cast(dict[str, object], payload).get("tool_input")
    if not isinstance(input_data, dict):
        return None
    command = cast(dict[str, object], input_data).get("command")
    return command if isinstance(command, str) else None


def main() -> int:
    """Emit a refusal only for a route the record positively identifies as wrong."""
    try:
        payload: object = json.load(sys.stdin)
        command = _command(payload=payload)
        if not command:
            return 0
        project_dir = _project_dir()
        if not _governed(project_dir=project_dir):
            return 0
        record = resolve_tailnet_record(project_dir=project_dir)
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
