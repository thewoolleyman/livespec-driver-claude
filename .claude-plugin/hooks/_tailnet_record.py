"""Read the fleet's sibling ``tailscale-admin`` machine table.

This module owns the record boundary for the fleet route guard: worktree-aware
sibling lookup, minimal Markdown-table parsing, and the local Tailscale DNS
suffix read.  It never embeds a machine, account, or tailnet name.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

__all__: list[str] = [
    "MachineRoute",
    "TailnetRecord",
    "parse_tailnet_table",
    "resolve_tailnet_record",
    "tailnet_domain",
]

_TABLE_DIVIDER = re.compile(r"^\s*\|?(?:\s*:?-+:?\s*\|)+\s*$")


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
    return (primary or root).parent / "tailscale-admin" / "README.md"


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


def parse_tailnet_table(*, text: str) -> TailnetRecord:
    """Read the route fields from a tailscale-admin README machine table."""
    return _table_record(text=text)


def resolve_tailnet_record(*, project_dir: str) -> TailnetRecord:
    """Read the sibling tailnet table, or report that no record answered."""
    path = _record_path(project_dir=project_dir)
    text = _read(path=path) if path else None
    if text is None:
        return TailnetRecord(machines={}, answered=False)
    return parse_tailnet_table(text=text)


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
