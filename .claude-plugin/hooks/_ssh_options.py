"""Read SSH-family command lines for fleet route resolution.

The clients differ subtly in which flags consume values and which of those
values affect the account resolved by ``ssh -G``.  This module keeps that
grammar separate from route policy so the guard stays focused on decisions.
"""

from __future__ import annotations

import shlex
from pathlib import Path

from _remote_target import host_of_target

__all__: list[str] = ["sftp_target", "target", "transfer_target"]

_SSH_VALUE_OPTIONS = frozenset("BbcDEeFIiJLlmOopQRSWw")
_SFTP_VALUE_OPTIONS = frozenset("BbcDFiJloPRSs")
_SCP_VALUE_OPTIONS = frozenset("cDFiJloPS")
_RSYNC_VALUE_OPTIONS = frozenset("eBfMT@")
_SSH_RESOLUTION_OPTIONS = {flag: flag for flag in "FiJlop"}
_SFTP_RESOLUTION_OPTIONS = {"F": "F", "i": "i", "J": "J", "o": "o", "P": "p"}
_SCP_RESOLUTION_OPTIONS = _SFTP_RESOLUTION_OPTIONS
_RSYNC_RESOLUTION_OPTIONS = {"e": "e"}


def _short_options(
    *,
    cluster: str,
    following: list[str],
    value_options: frozenset[str],
    resolution_options: dict[str, str],
) -> tuple[list[str], int] | None:
    """Relevant options in one short-option cluster and following tokens consumed."""
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
            value, consumed = following[0], 1
        if flag in resolution_options:
            options.extend([f"-{resolution_options[flag]}", value])
        return options, consumed
    return options, 0


def _long_option(*, cluster: str, following: list[str]) -> tuple[list[str], int] | None:
    """Read rsync's ``--rsh`` option as its equivalent ``-e`` form."""
    name, equals, inline = cluster.partition("=")
    if name != "--rsh":
        return [], 0
    if equals:
        return ["-e", inline], 0
    return (["-e", following[0]], 1) if following else None


def _scan(
    *,
    arguments: list[str],
    value_options: frozenset[str],
    resolution_options: dict[str, str],
    permute: bool = False,
) -> tuple[list[str], list[str]] | None:
    """Return operands plus options relevant to ``ssh -G``, if parseable."""
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
        found = (
            _long_option(cluster=cluster, following=following)
            if cluster.startswith("--")
            else _short_options(
                cluster=cluster,
                following=following,
                value_options=value_options,
                resolution_options=resolution_options,
            )
        )
        if found is None:
            return None
        options.extend(found[0])
        index += found[1]
    return operands, options


def _target(
    *,
    arguments: list[str],
    value_options: frozenset[str],
    resolution_options: dict[str, str],
) -> tuple[str | None, str | None, list[str]]:
    scanned = _scan(
        arguments=arguments, value_options=value_options, resolution_options=resolution_options
    )
    if scanned is None or not scanned[0]:
        return None, None, [] if scanned is None else scanned[1]
    target_value = scanned[0][0]
    if "@" in target_value:
        account, host = target_value.rsplit("@", 1)
        return host, account or None, scanned[1]
    return target_value, None, scanned[1]


def target(*, arguments: list[str]) -> tuple[str | None, str | None, list[str]]:
    """Read an SSH target and the options that determine its resolved account."""
    return _target(
        arguments=arguments,
        value_options=_SSH_VALUE_OPTIONS,
        resolution_options=_SSH_RESOLUTION_OPTIONS,
    )


def sftp_target(*, arguments: list[str]) -> tuple[str | None, str | None, list[str]]:
    """Read an SFTP target using its distinct option grammar."""
    return _target(
        arguments=arguments,
        value_options=_SFTP_VALUE_OPTIONS,
        resolution_options=_SFTP_RESOLUTION_OPTIONS,
    )


def _rsh_options(*, command: str) -> list[str]:
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


def transfer_target(*, head: str, arguments: list[str]) -> tuple[str | None, str | None, list[str]]:
    """Read the final scp or rsync remote operand and its SSH account options."""
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
    remote = operands[-1]
    authority = remote.split(":", 1)[0].removeprefix("scp://").removeprefix("sftp://")
    account = authority.rsplit("@", 1)[0] if "@" in authority else None
    return host_of_target(target=remote), account or None, options
