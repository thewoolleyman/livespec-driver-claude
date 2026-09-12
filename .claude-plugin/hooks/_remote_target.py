#!/usr/bin/env python3
"""
Operand parsing for the remote-shell heads `ssh`, `scp`, `rsync`, `sftp`.

`_host_mutation` asks two questions of a remote-shell invocation — WHICH host
does it reach, and WHAT does it hand that host — and each tool answers them
in its own argv grammar. This module owns those grammars so the classifier
stays a policy, not a parser:

  - **ssh(1)** stops option parsing at the first operand (the host); every
    later token is the remote command, joined with spaces and re-parsed by the
    remote shell. Options are getopt-style: a letter that takes a value takes
    the REST of its cluster or the next token (`-p22`, `-p 22`, `-tp 22`), so
    `-tp 22 host` names `host`, never `22`. Two `-o` options can move the
    hazard: `HostName=<real host>` makes the operand an alias, and
    `RemoteCommand=<cmd>` is a remote command with no operand at all.
  - **scp(1)** is getopt-style too; the DESTINATION is the last operand, spelt
    `[user@]host:path` or `scp://host/path`. A host in a source position is a
    download, which reads the host and writes locally.
  - **rsync(1)** uses popt, which PERMUTES: options may follow operands, so
    `rsync -av ./x host:/etc/x -e 'ssh -p 22'` still names `host:/etc/x` as
    the destination and `ssh -p 22` as an option value, not the destination.
    `-n`/`--dry-run` makes an upload a read; `--remove-source-files` makes a
    DOWNLOAD delete on the source host.
  - **sftp(1)** takes its commands from stdin when no `-b <file>` is given
    (`-b -` says so explicitly; an interactive sftp with a non-tty stdin does
    the same silently), so the batch a classifier can read is whatever the
    shell feeds it: a here-doc or an `echo`/`printf` pipe. A `-b <file>` batch
    is unreadable from a hook and is not judged. Batch verbs are
    case-insensitive and a leading `-` (ignore errors) is not part of the verb.

A host operand that holds a `$…`, a backtick, or an xargs `{}` cannot be
resolved by reading; the reach records that so the classifier can fail closed
when the surrounding command looks like a fleet-host mutation.

Self-contained by contract: the plugin installer ships this file under bare
system `python3` with no virtualenv and no third-party packages, so every
import here is standard library.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

__all__: list[str] = [
    "SftpReach",
    "SshReach",
    "TransferReach",
    "host_of_target",
    "is_fleet_host",
    "parse_sftp",
    "parse_ssh",
    "parse_transfer",
    "sftp_batch_mutates",
]

# ssh(1) / scp(1) / sftp(1) option letters that consume a value.
_SSH_VALUE_FLAGS = frozenset("BbcDEeFIiJLlmOopQRSWw")
_SCP_VALUE_FLAGS = frozenset("cDFiJloPS")
_SFTP_VALUE_FLAGS = frozenset("BbcDFiJloPRSs")
# rsync(1) options that consume the NEXT token when not spelt `--name=value`.
_RSYNC_VALUE_SHORT = frozenset("eBfT")
_RSYNC_VALUE_LONG = frozenset(
    "rsh rsync-path files-from exclude include exclude-from include-from filter log-file "
    "log-file-format temp-dir partial-dir bwlimit timeout contimeout port sockopts "
    "password-file chmod chown backup-dir suffix block-size compare-dest copy-dest "
    "link-dest out-format max-size min-size max-delete modify-window checksum-choice "
    "compress-level skip-compress usermap groupmap address iconv write-batch read-batch "
    "only-write-batch outbuf info debug stderr max-alloc protocol config daemon-config "
    "remote-option".split()
)
_SFTP_MUTATIONS = frozenset("put reput rm rmdir mkdir rename chmod chown chgrp symlink ln".split())
_OPTION_VALUE = re.compile(r"[=\s]+")
_TRANSFER_SCHEMES = ("ssh://", "scp://", "sftp://", "rsync://")


@dataclass(frozen=True, kw_only=True)
class SshReach:
    """Where an `ssh` goes and what it runs there."""

    host: str | None
    remote: list[str] = field(default_factory=list)
    unresolvable: bool = False


@dataclass(frozen=True, kw_only=True)
class TransferReach:
    """The hosts an `scp`/`rsync` writes to and reads from, and the flags that matter."""

    destination: str | None
    sources: list[str] = field(default_factory=list)
    dry_run: bool = False
    remove_source: bool = False
    unresolvable: bool = False


@dataclass(frozen=True, kw_only=True)
class SftpReach:
    """The `sftp` target and whether its batch is readable from the command."""

    host: str | None
    batch_from_stdin: bool


def _unresolvable(*, token: str) -> bool:
    """A `$…`, a backtick, or an xargs `{}` — which the lexer strips, leaving `` or `:path`."""
    return not token or token.startswith(":") or "$" in token or "`" in token or "{}" in token


def host_of_target(*, target: str) -> str:
    """`user@host`, `ssh://user@host:port/`, `host:path`, `rsync://host/` → `host`."""
    rest = target
    for scheme in _TRANSFER_SCHEMES:
        if rest.startswith(scheme):
            rest = rest[len(scheme) :]
    rest = rest.rsplit("@", 1)[-1]
    return rest.split(":", 1)[0].split("/", 1)[0]


def is_fleet_host(*, name: str, hosts: frozenset[str]) -> bool:
    host = name.lower().rstrip(".")
    return host in hosts or host.split(".", 1)[0] in hosts


def _getopt(
    *, arguments: list[str], value_flags: frozenset[str]
) -> tuple[list[tuple[str, str]], int]:
    """Options as (letter, value) pairs and the index of the first operand.

    getopt-style: a cluster `-tp 22` is `-t` then `-p 22`; a value letter takes
    the rest of its cluster or the next token; `--` ends option parsing.
    """
    options: list[tuple[str, str]] = []
    index = 0
    total = len(arguments)
    while index < total:
        token = arguments[index]
        if token == "--":
            return options, index + 1
        if not token.startswith("-") or token == "-" or token.startswith("--"):
            break
        letters = token[1:]
        for position, letter in enumerate(letters):
            if letter not in value_flags:
                options.append((letter, ""))
                continue
            value = letters[position + 1 :]
            if not value:
                index += 1
                value = arguments[index] if index < total else ""
            options.append((letter, value))
            break
        index += 1
    return options, index


def parse_ssh(*, arguments: list[str]) -> SshReach:
    """The ssh host (honouring `-o HostName=`) and its remote command lines."""
    options, index = _getopt(arguments=arguments, value_flags=_SSH_VALUE_FLAGS)
    if index >= len(arguments):
        return SshReach(host=None)
    operand = arguments[index]
    host = host_of_target(target=operand)
    remote: list[str] = [" ".join(arguments[index + 1 :])]
    for letter, value in options:
        if letter != "o":
            continue
        parts = _OPTION_VALUE.split(value.strip(), maxsplit=1)
        key, setting = parts[0], (parts[1] if len(parts) > 1 else "")
        if key.lower() == "hostname" and setting:
            host = host_of_target(target=setting)
            operand = setting
        elif key.lower() == "remotecommand" and setting:
            remote.append(setting)
    return SshReach(
        host=host,
        remote=[line for line in remote if line.strip()],
        unresolvable=_unresolvable(token=operand),
    )


def _transfer_host(*, operand: str) -> str | None:
    """The host of a `[user@]host:path` or `scheme://host/path` operand, else None."""
    if operand.startswith(_TRANSFER_SCHEMES):
        return host_of_target(target=operand)
    head, separator, _ = operand.partition(":")
    if not separator or "/" in head or not head:
        return None
    return host_of_target(target=head)


def _rsync_operands(*, arguments: list[str]) -> tuple[list[str], bool, bool]:
    """rsync's operands with popt's permuted options removed, plus dry-run / remove-source."""
    operands: list[str] = []
    dry_run = False
    remove_source = False
    index = 0
    total = len(arguments)
    while index < total:
        token = arguments[index]
        if token == "--":
            operands.extend(arguments[index + 1 :])
            break
        if token.startswith("--"):
            name = token[2:].split("=", 1)[0]
            dry_run = dry_run or name == "dry-run"
            remove_source = remove_source or name == "remove-source-files"
            index += 2 if "=" not in token and name in _RSYNC_VALUE_LONG else 1
            continue
        if token.startswith("-") and token != "-":
            letters = token[1:]
            dry_run = dry_run or "n" in letters.split("e", 1)[0]
            taking = next(
                (i for i, letter in enumerate(letters) if letter in _RSYNC_VALUE_SHORT), None
            )
            index += 2 if taking is not None and taking == len(letters) - 1 else 1
            continue
        operands.append(token)
        index += 1
    return operands, dry_run, remove_source


def parse_transfer(*, head: str, arguments: list[str]) -> TransferReach:
    """Destination and source hosts of an `scp` or `rsync`."""
    if head == "rsync":
        operands, dry_run, remove_source = _rsync_operands(arguments=arguments)
    else:
        _, index = _getopt(arguments=arguments, value_flags=_SCP_VALUE_FLAGS)
        operands, dry_run, remove_source = arguments[index:], False, False
    if len(operands) < 2:
        return TransferReach(destination=None)
    destination = operands[-1]
    return TransferReach(
        destination=_transfer_host(operand=destination),
        sources=[host for host in map(lambda o: _transfer_host(operand=o), operands[:-1]) if host],
        dry_run=dry_run,
        remove_source=remove_source,
        unresolvable=_unresolvable(token=destination),
    )


def parse_sftp(*, arguments: list[str]) -> SftpReach:
    """The sftp host and whether its batch arrives on stdin (readable) or from a file."""
    options, index = _getopt(arguments=arguments, value_flags=_SFTP_VALUE_FLAGS)
    if index >= len(arguments):
        return SftpReach(host=None, batch_from_stdin=False)
    batch_files = [value for letter, value in options if letter == "b" and value != "-"]
    return SftpReach(
        host=host_of_target(target=arguments[index]),
        batch_from_stdin=not batch_files,
    )


def sftp_batch_mutates(*, batch: str) -> bool:
    """True when any batch line's verb writes the remote side (`put`, `rm`, `rename`, …)."""
    for line in batch.splitlines():
        words = line.split()
        if words and words[0].lstrip("-@").lower() in _SFTP_MUTATIONS:
            return True
    return False
