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
judges against is resolved by the sibling `_fleet_inventory` module.

THE DENY MATRIX (every row is a POSITIVE identification; anything the classifier
cannot show to be a mutation of a fleet host passes through):

  - `ssh` whose target is a fleet host AND whose remote command carries a
    mutation verb: `sudo` (unless what it escalates is itself read-only),
    `install`, `tee`, `rm`, `chmod`, `chown`, `apt`/`apt-get`, `cp`/`mv` whose
    destination is under `/etc` or `/usr`, a `>`/`>>` redirection into those
    trees, `systemctl start|stop|restart|reload|enable|disable|mask|unmask|
    daemon-reload`, `git clone|pull`, a cluster-mutating `kubectl`, or a
    mutating `k3s` subcommand. The remote command is itself shell text (ssh
    joins its operands and the remote shell re-parses them), so it is split
    and scanned exactly like the outer command; a here-doc fed to the ssh
    segment is the remote script and is scanned as part of it.
  - `scp` / `rsync` whose DESTINATION is a fleet host: an upload writes the
    host's filesystem. A download (fleet host as the source) is read-only.
  - `sftp` to a fleet host whose inline batch (a here-doc) carries `put`, `rm`,
    `rename`, `mkdir`, `chmod`, … — the only form in which the batch is visible.
  - `kubectl apply|patch|taint|delete|cordon|drain|label|edit|scale` from
    anywhere — the cluster IS fleet state — unless `--dry-run` (other than
    `=none`) makes it a read.

THE ALLOW LIST, stated so its members are proven rather than assumed: the
sanctioned apply and drift (`just ansible-apply`, `just ansible-drift`,
`ansible-playbook` with or without `--check`); read-only reaches over ssh
(`kubectl get|describe|logs`, `cat`, `ls`, `stat`, `systemctl status|cat|
is-active`, `journalctl`, `grep`, `test`, …, with or without `sudo`); an ssh
with no remote command; any of these to a host that is NOT in the fleet set;
and every mention that is quoted data (a commit message, a grep pattern, an
`echo`, a here-doc written to a file).

THE DESIGN RULE, inherited from `_tmux_hazard`: scan EVERY token position for a
command head, never just position 0, so `timeout 30 ssh …`, `mise exec -- ssh
…` and `env -i kubectl …` are defeated by the scan rather than by an allowlist
of known wrappers. Quoting is what keeps this from over-blocking.

Fail-closed only on a hazard-hinted parse failure: a segment that names a
remote-shell head and a fleet host (or `kubectl` and a mutating verb) but will
not tokenize is denied; anything else that cannot be classified passes.

Self-contained by contract: the plugin installer ships this file under bare
system `python3` with no virtualenv and no third-party packages, so every
import here is the standard library or a sibling module shipped beside it.
"""

from __future__ import annotations

import re
import shlex

from _shell_lex import (
    SHELLS,
    basename,
    shell_payload,
    split_heredocs,
    split_segments,
    ungrouped,
    without_continuations,
)

__all__: list[str] = ["classify", "hazard_hint"]

_MAX_DEPTH = 4
_REMOTE_HEADS = frozenset({"ssh", "scp", "rsync", "sftp"})
_REMOTE_WORD = re.compile(r"\b(?:ssh|scp|rsync|sftp)\b")
_KUBECTL_WORD = re.compile(r"\bkubectl\b")
_KUBECTL_MUTATIONS = frozenset("apply patch taint delete cordon drain label edit scale".split())
_KUBECTL_MUTATION_WORD = re.compile(r"\b(?:" + "|".join(sorted(_KUBECTL_MUTATIONS)) + r")\b")
_SUBCOMMAND_MUTATIONS: dict[str, frozenset[str]] = {
    "systemctl": frozenset(
        "start stop restart reload try-restart reload-or-restart enable disable mask unmask "
        "daemon-reload".split()
    ),
    "git": frozenset({"clone", "pull"}),
    "k3s": frozenset("server agent etcd-snapshot secrets-encrypt certificate".split()),
}
_ALWAYS_MUTATING = frozenset("install tee rm chmod chown apt apt-get".split())
_COPIERS = frozenset({"cp", "mv"})
_PROTECTED_PREFIXES = ("/etc", "/usr")
_SFTP_MUTATIONS = frozenset("put rm rmdir mkdir rename chmod chown chgrp symlink ln".split())
# What `sudo` may escalate without convicting on its own: heads whose every
# subcommand is a read, plus heads judged by their own subcommand rule above.
_READ_ONLY_HEADS = frozenset(
    "cat ls stat journalctl grep test head tail wc find df du id hostname uname uptime ps "
    "which pgrep true echo kubectl systemctl git k3s crictl ctr".split()
)
_SANCTIONED_HEADS = frozenset({"ansible-playbook", "ansible"})
_SANCTIONED_RECIPES = frozenset({"ansible-apply", "ansible-drift"})
# ssh(1) options that consume the next token as their value.
_SSH_VALUE_FLAGS = frozenset("BbcDEeFIiJLlmOopQRSWw")
_SFTP_VALUE_FLAGS = frozenset("-b -B -c -D -F -i -J -l -o -P -R -S -s".split())
_SUDO_VALUE_FLAGS = frozenset("-u -g -h -p -C -r -t -T -U".split())
_SUDO_SHELL_FLAGS = frozenset({"-i", "-s"})


def _is_fleet_host(*, name: str, hosts: frozenset[str]) -> bool:
    host = name.lower().rstrip(".")
    return host in hosts or host.split(".", 1)[0] in hosts


def _host_of_target(*, target: str) -> str:
    """`user@host`, `ssh://user@host:port/`, `host:path`, `rsync://host/` → `host`."""
    rest = target
    for scheme in ("ssh://", "sftp://", "rsync://"):
        if rest.startswith(scheme):
            rest = rest[len(scheme) :]
    rest = rest.rsplit("@", 1)[-1]
    return rest.split(":", 1)[0].split("/", 1)[0]


def _operands(*, arguments: list[str]) -> list[str]:
    return [argument for argument in arguments if not argument.startswith("-")]


def _remote_destination_host(*, arguments: list[str]) -> str | None:
    """The host of an `scp`/`rsync` DESTINATION operand (`host:path`, `rsync://host/`)."""
    operands = _operands(arguments=arguments)
    if not operands:
        return None
    destination = operands[-1]
    if destination.startswith("rsync://") or (
        ":" in destination and not destination.startswith("/")
    ):
        return _host_of_target(target=destination)
    return None


def _ssh_target(*, arguments: list[str]) -> tuple[str | None, list[str]]:
    """ssh's host operand and the remote-command tokens after it, options consumed."""
    index = 0
    total = len(arguments)
    while index < total:
        token = arguments[index]
        if token == "--":
            index += 1
            break
        if not token.startswith("-") or token == "-":
            break
        index += 2 if len(token) == 2 and token[1] in _SSH_VALUE_FLAGS else 1
    if index >= total:
        return None, []
    return _host_of_target(target=arguments[index]), arguments[index + 1 :]


def _first_operand(*, arguments: list[str], value_flags: frozenset[str]) -> str | None:
    index = 0
    total = len(arguments)
    while index < total:
        token = arguments[index]
        if not token.startswith("-"):
            return token
        index += 2 if token in value_flags else 1
    return None


def _targets_protected_tree(*, path: str) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in _PROTECTED_PREFIXES)


def _kubectl_rule(*, arguments: list[str]) -> str | None:
    verbs = [argument for argument in arguments if argument in _KUBECTL_MUTATIONS]
    if not verbs:
        return None
    dry_run = any(a.startswith("--dry-run") and a != "--dry-run=none" for a in arguments)
    return None if dry_run else f"kubectl+{verbs[0]}"


def _sudo_rule(*, arguments: list[str]) -> str | None:
    """`sudo` convicts on its own unless what it escalates is positively read-only."""
    if any(argument in _SUDO_SHELL_FLAGS for argument in arguments):
        return "sudo+shell"
    escalated = _first_operand(arguments=arguments, value_flags=_SUDO_VALUE_FLAGS)
    if escalated is None:
        return "sudo+shell"
    head = basename(token=escalated)
    return None if head in _READ_ONLY_HEADS else f"sudo+{head}"


def _redirect_rule(*, tokens: list[str]) -> str | None:
    """A `>`/`>>` whose target is under a protected tree is a file write on the host."""
    for index, token in enumerate(tokens):
        if not token.startswith(">"):
            continue
        path = token.lstrip(">") or (tokens[index + 1] if index + 1 < len(tokens) else "")
        if _targets_protected_tree(path=path):
            return "redirect-into-protected-tree"
    return None


def _head_mutation(*, head: str, arguments: list[str], depth: int) -> str | None:
    """Is THIS token a mutation verb on the remote host?"""
    if head in SHELLS:
        payload = shell_payload(arguments=arguments)
        if payload is not None:
            return _mutation_rule(payload=payload, depth=depth + 1)
    if head == "sudo":
        return _sudo_rule(arguments=arguments)
    if head == "kubectl":
        return _kubectl_rule(arguments=arguments)
    if head in _ALWAYS_MUTATING:
        return head
    if head in _COPIERS:
        operands = _operands(arguments=arguments)
        return head if operands and _targets_protected_tree(path=operands[-1]) else None
    verbs = _SUBCOMMAND_MUTATIONS.get(head)
    if verbs is not None:
        subcommand = _first_operand(arguments=arguments, value_flags=frozenset())
        return f"{head}+{subcommand}" if subcommand in verbs else None
    return None


def _tokens_or_none(*, seg: str) -> list[str] | None:
    try:
        return [ungrouped(token=token) for token in shlex.split(seg, posix=True)]
    except ValueError:
        return None


def _mutation_rule(*, payload: str, depth: int) -> str | None:
    """The mutation verb a remote shell payload carries, or None."""
    if depth > _MAX_DEPTH:
        return "nesting-depth"
    for seg in split_segments(command=without_continuations(command=payload)):
        tokens = _tokens_or_none(seg=seg)
        if tokens is None:
            return "unparseable-remote-command"
        rule = _redirect_rule(tokens=tokens)
        for index, token in enumerate(tokens):
            rule = rule or _head_mutation(
                head=basename(token=token), arguments=tokens[index + 1 :], depth=depth
            )
        if rule is not None:
            return rule
    return None


def _sftp_rule(*, arguments: list[str], hosts: frozenset[str], bodies: list[str]) -> str | None:
    target = _first_operand(arguments=arguments, value_flags=_SFTP_VALUE_FLAGS)
    if target is None or not _is_fleet_host(name=_host_of_target(target=target), hosts=hosts):
        return None
    lines = [line for body in bodies for line in body.splitlines() if line.strip()]
    return "sftp+batch" if any(line.split()[0] in _SFTP_MUTATIONS for line in lines) else None


def _remote_rule(
    *, head: str, arguments: list[str], hosts: frozenset[str], bodies: list[str], depth: int
) -> str | None:
    """Does this remote-shell head reach a fleet host with a mutation?"""
    if head in {"scp", "rsync"}:
        destination = _remote_destination_host(arguments=arguments)
        if destination is not None and _is_fleet_host(name=destination, hosts=hosts):
            return f"{head}+upload"
        return None
    if head == "sftp":
        return _sftp_rule(arguments=arguments, hosts=hosts, bodies=bodies)
    target, remote = _ssh_target(arguments=arguments)
    if target is None or not _is_fleet_host(name=target, hosts=hosts):
        return None
    rule = _mutation_rule(payload="\n".join([" ".join(remote), *bodies]), depth=depth + 1)
    return None if rule is None else f"ssh+{rule}"


def _is_sanctioned(*, tokens: list[str]) -> bool:
    """`just ansible-apply|ansible-drift …` and `ansible-playbook …` are THE deploy path."""
    for index, token in enumerate(tokens):
        head = basename(token=token)
        if head in _SANCTIONED_HEADS:
            return True
        if head == "just" and index + 1 < len(tokens) and tokens[index + 1] in _SANCTIONED_RECIPES:
            return True
    return False


def _position_rule(
    *, head: str, arguments: list[str], hosts: frozenset[str], bodies: list[str], depth: int
) -> str | None:
    if head in SHELLS:
        payload = shell_payload(arguments=arguments)
        return None if payload is None else classify(command=payload, hosts=hosts, depth=depth + 1)
    if head in _REMOTE_HEADS:
        return _remote_rule(head=head, arguments=arguments, hosts=hosts, bodies=bodies, depth=depth)
    return _kubectl_rule(arguments=arguments) if head == "kubectl" else None


def _segment_rule(*, seg: str, hosts: frozenset[str], bodies: list[str], depth: int) -> str | None:
    tokens = _tokens_or_none(seg=seg)
    if tokens is None:
        return "unparseable" if hazard_hint(command=seg, hosts=hosts) else None
    if _is_sanctioned(tokens=tokens):
        return None
    segment_bodies = bodies if "<<" in seg else []
    for index, token in enumerate(tokens):
        rule = _position_rule(
            head=basename(token=token),
            arguments=tokens[index + 1 :],
            hosts=hosts,
            bodies=segment_bodies,
            depth=depth,
        )
        if rule is not None:
            return rule
    return None


def hazard_hint(*, command: str, hosts: frozenset[str]) -> bool:
    """True when raw text LOOKS like a fleet-host mutation — the fail-closed trigger."""
    lowered = command.lower()
    remote = bool(_REMOTE_WORD.search(lowered)) and any(host in lowered for host in hosts)
    kube = bool(_KUBECTL_WORD.search(lowered)) and bool(_KUBECTL_MUTATION_WORD.search(lowered))
    return remote or kube


def classify(*, command: str, hosts: frozenset[str], depth: int = 0) -> str | None:
    """The rule that convicts this command of mutating a fleet host by hand, or None."""
    if depth > _MAX_DEPTH:
        # Out of budget with content still unexamined. Nothing legitimate nests
        # this deep, so exhaustion is evidence of evasion: fail CLOSED.
        return "nesting-depth"
    stripped, bodies = split_heredocs(command=command)
    for seg in split_segments(command=without_continuations(command=stripped)):
        rule = _segment_rule(seg=seg, hosts=hosts, bodies=bodies, depth=depth)
        if rule is not None:
            return rule
    return None
