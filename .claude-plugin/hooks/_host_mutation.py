#!/usr/bin/env python3
"""
Fleet-host mutation classification for `fleet_host_guard`.

THE FAILURE THIS ANSWERS. A session ssh'd into two fleet-managed k3s nodes and
reasoned imperatively about deploying to them by hand, while the repository it
had been editing states the provisioning model: the control node is `vps`,
`just ansible-drift <playbook>` reports and `just ansible-apply <playbook>`
converges, from committed source in `livespec-dev-tooling/ansible/`, and there
is deliberately no checkout on a target. "I would have to do this by hand on a
host" names a gap in the committed automation to FIX, never a task. This module
owns the single question "does this command change a fleet-managed host by
hand?", so `fleet_host_guard.py` keeps only the hook boundary. The host set it
judges against comes from `_fleet_inventory`; the argv grammars of the
remote-shell heads from `_remote_target`; the per-head verb tables from
`_mutation_verbs`; the lexing and stdin/payload plumbing from `_shell_lex`.

THE DENY MATRIX, every row a POSITIVE identification unless marked (†):

  - `ssh` whose target is a fleet host AND whose remote command (its operands,
    an `-o RemoteCommand=`, a here-doc, a here-string, or an `echo`/`printf`
    piped into it) carries a mutation: `sudo` escalating anything not provably
    read-only (†), or any head `_mutation_verbs` convicts — always-mutating
    heads, an inverted subcommand head with a non-read verb, a flag-judged head
    with a mutating flag, `cp`/`mv`/`>` into a protected tree, a shell reading
    a script from a non-`echo` pipe (`curl … | sh`). The remote command is shell
    text and is scanned exactly like the outer command, one level down.
  - `scp`/`rsync` whose DESTINATION is a fleet host (an upload) unless
    `rsync -n`/`--dry-run`; `rsync --remove-source-files` from a fleet host.
  - `sftp` to a fleet host whose readable batch carries a writing verb.
  - `kubectl`/`helm` with a non-read verb from anywhere — the cluster IS fleet
    state — unless `--dry-run=client|server`.
  - An ad hoc `ansible` run with `--become` or a mutating module; an
    `ansible-playbook` (or `just ansible-apply`) of a playbook outside the
    committed tree (an absolute or `~` path) without `--check`.
  - FAIL CLOSED (†) when the command LOOKS like a fleet-host mutation (a
    remote-shell word beside a fleet host name, or `kubectl`/`helm` beside a
    mutating verb) but cannot be read: a segment that will not tokenize, a
    `$(…)`/backtick substitution, a host or command head holding `$…` or an
    xargs `{}`, or nesting past the depth budget. Precedent: `_tmux_hazard`.

THE ALLOW LIST, stated so its members are proven rather than assumed: the
sanctioned apply and drift (`just ansible-apply`, `just ansible-drift`,
`ansible-playbook` of a committed playbook, with or without `--check`) when it
is the segment's actual command head; read-only reaches over ssh (`kubectl
get|describe|logs`, `cat`, `ls`, `stat`, `systemctl status|cat|is-active`,
`journalctl`, `grep`, `test`, `dmesg`, `ss`, `lsof`, `docker ps`, …, with or
without `sudo`; `sudo -l`; `sudo bash -c '<read-only script>'`); an ssh with
no remote command; any of these to a host that is NOT in the fleet set; every
mention that is quoted data (a commit message, a grep pattern, a here-doc
written to a file); and an `echo`/`printf` line, whose operands are data even
unquoted.

THE SCAN RULE, inherited from `_tmux_hazard` and sharpened: walk the tokens of
a segment until a RECOGNISED command head is met, judge it with the tokens
after it as ITS arguments, and stop there — the arguments of a recognised head
are data (`journalctl -u k3s` names a unit, not a `k3s` command). Tokens the
guard does not recognise (`timeout 30`, `env -i`, `mise exec --`, `nohup`) are
walked past, so a wrapper is defeated by the walk rather than by an allowlist.
Heads are matched case-insensitively. Payloads handed to another interpreter
are re-classified one level down: `sh -c`, `bash <<<`, `eval`, `script -c`,
`watch`, and tmux `new-session`/`send-keys` operands.

KNOWN LIMITS, documented rather than pretended: a script assembled inside
another language (`python3 -c "subprocess.run(['ssh', …])"`), a `-b <file>`
sftp batch, `sudo bash -s < script.sh` (denied as a root shell, never read),
and a remote `curl | sh` whose script the guard cannot fetch (denied as a
piped shell). An unquoted mention in the arguments of an unrecognised head
(`cat notes ssh host sudo …`) is judged as if it ran — the accepted deny bias;
`echo`/`printf` operands are the one exception.

Self-contained by contract: the plugin installer ships this file under bare
system `python3` with no virtualenv and no third-party packages, so every
import here is the standard library or a sibling module shipped beside it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, replace

from _mutation_verbs import MUTATING_KUBECTL_VERBS, mutation_of, read_only, redirect_rule
from _remote_target import is_fleet_host, parse_sftp, parse_ssh, parse_transfer, sftp_batch_mutates
from _shell_lex import (
    DATA_HEADS,
    PAYLOAD_HEADS,
    SCRIPT_HEADS,
    basename,
    first_command_index,
    operands,
    payload_of,
    produced_text,
    shell_payload,
    split_heredocs,
    split_segments_with_separators,
    stdin_text,
    tokens_or_none,
    without_continuations,
    without_stdin_redirects,
)

__all__: list[str] = ["classify", "hazard_hint", "in_scope"]

_MAX_DEPTH = 4
_REMOTE_HEADS = frozenset({"ssh", "scp", "rsync", "sftp"})
_CLUSTER_HEADS = frozenset({"kubectl", "helm", "ansible"})
_SCOPE_HEADS = _REMOTE_HEADS | _CLUSTER_HEADS | {"ansible-playbook"}
_SANCTIONED_RECIPES = frozenset({"ansible-apply", "ansible-drift"})
_KNOWN_HEADS = _SCOPE_HEADS | SCRIPT_HEADS | PAYLOAD_HEADS | {"just"}
_SUBSTITUTION = re.compile(r"\$\(|`")
_REMOTE_WORD = re.compile(r"\b(?:ssh|scp|rsync|sftp)\b")
_CLUSTER_WORD = re.compile(r"\b(?:kubectl|helm)\b")
_CLUSTER_MUTATION_WORD = re.compile(
    r"\b(?:"
    + "|".join(sorted(MUTATING_KUBECTL_VERBS | {"upgrade", "install", "uninstall", "rollback"}))
    + r")\b"
)
_SUDO_VALUE_FLAGS = frozenset(
    "-u -g -h -p -C -r -t -T -U -D --user --group --host --prompt --chdir".split()
)
_SUDO_SHELL_FLAGS = frozenset({"-i", "-s", "--login", "--shell"})


@dataclass(frozen=True, kw_only=True)
class _Scan:
    """One scan's fixed context: the host set, whether text looks hazardous, where it runs."""

    hosts: frozenset[str]
    hinted: bool
    remote: bool
    depth: int


def _unresolvable(*, token: str) -> bool:
    return not token or "$" in token or "`" in token or "{}" in token


def _head(*, token: str) -> str:
    return basename(token=token).lower()


def _playbook_rule(*, head: str, arguments: list[str]) -> str | None:
    """A committed playbook is sanctioned; one outside the tree is a hand deploy."""
    if "--check" in arguments:
        return None
    playbooks = [a for a in operands(arguments=arguments) if a.endswith((".yml", ".yaml"))]
    if any(p.startswith(("/", "~")) or ".." in p for p in playbooks):
        return f"{head}+uncommitted-playbook"
    return None


def _sanction(*, tokens: list[str]) -> tuple[bool, str | None]:
    """(sanctioned, rule) judged on the segment's FIRST known command head only."""
    for index, token in enumerate(tokens):
        head = _head(token=token)
        if head == "ansible-playbook":
            return True, _playbook_rule(head=head, arguments=tokens[index + 1 :])
        if head == "just" and index + 1 < len(tokens) and tokens[index + 1] in _SANCTIONED_RECIPES:
            recipe = tokens[index + 1]
            if recipe == "ansible-drift":
                return True, None
            return True, _playbook_rule(head=recipe, arguments=tokens[index + 2 :])
        if head in _KNOWN_HEADS:
            return False, None
    return False, None


def _sudo_rule(*, arguments: list[str], scan: _Scan) -> str | None:
    """`sudo` convicts on its own unless what it escalates is positively read-only."""
    index = 0
    total = len(arguments)
    while index < total and (arguments[index].startswith("-") or "=" in arguments[index]):
        flag = arguments[index]
        if flag == "--":
            index += 1
            break
        if flag in _SUDO_SHELL_FLAGS:
            return "sudo+shell"
        index += 2 if flag in _SUDO_VALUE_FLAGS else 1
    if index >= total:
        return None
    head = _head(token=arguments[index])
    rest = arguments[index + 1 :]
    if head == "sudo":
        return _sudo_rule(arguments=rest, scan=scan)
    if head in SCRIPT_HEADS:
        payload = shell_payload(arguments=rest)
        return _scan(text=payload, scan=_deeper(scan=scan)) if payload else "sudo+shell"
    rule = mutation_of(head=head, arguments=rest)
    if rule is not None:
        return rule
    return None if read_only(head=head, arguments=rest) else f"sudo+{head}"


def _deeper(*, scan: _Scan) -> _Scan:
    return replace(scan, remote=True, hinted=True, depth=scan.depth + 1)


def _remote_rule(*, head: str, arguments: list[str], stdin: str | None, scan: _Scan) -> str | None:
    """Does this remote-shell head reach a fleet host with a mutation?"""
    hosts = scan.hosts
    if head == "ssh":
        reach = parse_ssh(arguments=without_stdin_redirects(tokens=arguments))
        if reach.host is None:
            return None
        if reach.unresolvable:
            return "unresolvable-target" if scan.hinted else None
        if not is_fleet_host(name=reach.host, hosts=hosts):
            return None
        lines = [*reach.remote, *([stdin] if stdin else [])]
        rule = _scan(text="\n".join(lines), scan=_deeper(scan=scan)) if lines else None
        return None if rule is None else f"ssh+{rule}"
    if head == "sftp":
        sftp = parse_sftp(arguments=arguments)
        if sftp.host is None or not is_fleet_host(name=sftp.host, hosts=hosts):
            return None
        return (
            "sftp+batch"
            if sftp.batch_from_stdin and stdin and sftp_batch_mutates(batch=stdin)
            else None
        )
    transfer = parse_transfer(head=head, arguments=arguments)
    if transfer.unresolvable:
        return "unresolvable-target" if scan.hinted else None
    if transfer.destination is not None and is_fleet_host(name=transfer.destination, hosts=hosts):
        return None if transfer.dry_run else f"{head}+upload"
    if transfer.remove_source and any(is_fleet_host(name=h, hosts=hosts) for h in transfer.sources):
        return "rsync+remove-source-files"
    return None


def _position(
    *, head: str, arguments: list[str], fed_by: str, stdin: str | None, scan: _Scan
) -> tuple[str | None, bool]:
    """(rule, terminal): this token judged as a head, and whether its arguments are data."""
    if head in SCRIPT_HEADS or head in PAYLOAD_HEADS:
        payload = payload_of(head=head, arguments=arguments, stdin=stdin)
        if payload:
            return _scan(text=payload, scan=replace(scan, depth=scan.depth + 1)), True
        return ("piped-shell" if scan.remote and fed_by == "pipe" else None), True
    if head in _REMOTE_HEADS:
        return _remote_rule(head=head, arguments=arguments, stdin=stdin, scan=scan), True
    if head in _CLUSTER_HEADS:
        return mutation_of(head=head, arguments=arguments), True
    if not scan.remote:
        return None, False
    if head == "sudo":
        return _sudo_rule(arguments=arguments, scan=scan), True
    rule = mutation_of(head=head, arguments=arguments)
    return rule, rule is not None or read_only(head=head, arguments=arguments)


def _segment_rule(
    *, seg: str, tokens: list[str], fed_by: str, stdin: str | None, scan: _Scan
) -> str | None:
    if scan.hinted and _SUBSTITUTION.search(seg):
        return "command-substitution"
    if scan.remote and (rule := redirect_rule(tokens=tokens)) is not None:
        return rule
    start = first_command_index(tokens=tokens)
    if start is None or _head(token=tokens[start]) in DATA_HEADS:
        return None
    if scan.hinted and _unresolvable(token=tokens[start]):
        return "unresolvable-command"
    if not scan.remote:
        sanctioned, rule = _sanction(tokens=tokens[start:])
        if sanctioned:
            return rule
    for index in range(start, len(tokens)):
        rule, terminal = _position(
            head=_head(token=tokens[index]),
            arguments=tokens[index + 1 :],
            fed_by=fed_by,
            stdin=stdin,
            scan=scan,
        )
        if rule is not None or terminal:
            return rule
    return None


def _scan(*, text: str, scan: _Scan) -> str | None:
    """Scan shell text — the outer command, or a payload one level down — for a mutation."""
    if scan.depth > _MAX_DEPTH:
        # Out of budget with content still unexamined. Nothing legitimate nests
        # this deep, so exhaustion is evidence of evasion: fail CLOSED.
        return "nesting-depth"
    stripped, bodies = split_heredocs(command=text)
    piped: str | None = None
    for separator, seg in split_segments_with_separators(
        command=without_continuations(command=stripped)
    ):
        tokens = tokens_or_none(seg=seg)
        if tokens is None:
            if scan.hinted:
                return "unparseable-remote-command" if scan.remote else "unparseable"
            piped = None
            continue
        fed_by = "" if separator != "|" else ("data" if piped is not None else "pipe")
        stdin = stdin_text(
            seg=seg, tokens=tokens, bodies=bodies, piped=piped if fed_by == "data" else None
        )
        rule = _segment_rule(seg=seg, tokens=tokens, fed_by=fed_by, stdin=stdin, scan=scan)
        if rule is not None:
            return rule
        piped = produced_text(tokens=tokens)
    return None


def hazard_hint(*, command: str, hosts: frozenset[str]) -> bool:
    """True when raw text LOOKS like a fleet-host mutation — the fail-closed trigger."""
    lowered = command.lower()
    remote = bool(_REMOTE_WORD.search(lowered)) and any(host in lowered for host in hosts)
    cluster = bool(_CLUSTER_WORD.search(lowered)) and bool(_CLUSTER_MUTATION_WORD.search(lowered))
    return remote or cluster


def in_scope(*, command: str, hosts: frozenset[str]) -> bool:
    """True when the command carries a head this guard judges (or looks like one).

    Judged on the comment-stripped segments, so `git status # ssh host` is out
    of scope exactly as the scan sees it.
    """
    stripped, _ = split_heredocs(command=command)
    segments = split_segments_with_separators(command=without_continuations(command=stripped))
    if hazard_hint(command="\n".join(seg for _, seg in segments), hosts=hosts):
        return True
    for _, seg in segments:
        tokens = tokens_or_none(seg=seg)
        if tokens is not None and any(_head(token=token) in _SCOPE_HEADS for token in tokens):
            return True
    return False


def classify(*, command: str, hosts: frozenset[str], depth: int = 0) -> str | None:
    """The rule that convicts this command of mutating a fleet host by hand, or None."""
    scan = _Scan(
        hosts=hosts, hinted=hazard_hint(command=command, hosts=hosts), remote=False, depth=depth
    )
    return _scan(text=command, scan=scan)
