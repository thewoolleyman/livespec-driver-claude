#!/usr/bin/env python3
"""
The sanctioned deploy path: `just ansible-apply|ansible-drift` and `ansible-playbook`.

The discipline's positive statement is "a deploy is a git change plus the
committed apply, run from the control node over committed source". This module
recognises that apply so `_host_mutation` can let it through — and recognises
the one shape of it that is NOT the discipline: a playbook that positively is
not committed source.

  - The sanction applies only when the sanctioned head is the segment's FIRST
    recognised command head. A path operand that happens to be named
    `ansible`, or a trailing `ansible` word after a mutating `ssh`, sanctions
    nothing; bare `ansible` (ad hoc) is not sanctioned at all and is judged
    by `_mutation_verbs` like any other head.
  - `ansible-playbook <playbook>` / `just ansible-apply <playbook>` is a hand
    deploy when the playbook is positively outside committed source: under
    `~`, `/tmp`, `/var/tmp` or `/dev/shm`, or carrying `..` or a `$`. An
    absolute path INTO a checkout is not positively uncommitted and passes —
    the guard identifies, it does not guess. Option values (`-i <inventory>`,
    `-e <vars>`, `--vault-password-file <file>`, …) are never playbooks.
  - `--check` (and `just ansible-drift`, which IS `--check --diff`) reads.

Self-contained by contract: the plugin installer ships this file under bare
system `python3` with no virtualenv and no third-party packages, so every
import here is the standard library or a sibling module shipped beside it.
"""

from __future__ import annotations

from _shell_lex import basename

__all__: list[str] = ["sanction"]

_SANCTIONED_RECIPES = frozenset({"ansible-apply", "ansible-drift"})
# ansible-playbook options whose value is not a playbook.
_PLAYBOOK_VALUE_FLAGS = frozenset(
    "-i --inventory --inventory-file -e --extra-vars --vault-password-file --vault-id -l "
    "--limit -t --tags --skip-tags -u --user -c --connection -T --timeout --private-key "
    "--key-file -M --module-path --become-user --become-method -f --forks --ssh-common-args "
    "--ssh-extra-args --scp-extra-args --sftp-extra-args --start-at-task".split()
)
_UNCOMMITTED_PREFIXES = ("~", "/tmp", "/var/tmp", "/dev/shm")


def _playbook_rule(*, head: str, arguments: list[str]) -> str | None:
    """A playbook positively outside committed source is a hand deploy; `--check` reads."""
    if "--check" in arguments:
        return None
    playbooks: list[str] = []
    skip = False
    for argument in arguments:
        if skip or argument.startswith("-"):
            skip = argument in _PLAYBOOK_VALUE_FLAGS
            continue
        playbooks.append(argument)
    if any(p.startswith(_UNCOMMITTED_PREFIXES) or ".." in p or "$" in p for p in playbooks):
        return f"{head}+uncommitted-playbook"
    return None


def sanction(*, tokens: list[str], known_heads: frozenset[str]) -> tuple[bool, str | None]:
    """(sanctioned, rule), judged on the segment's FIRST known command head only.

    `known_heads` is the caller's set of heads it recognises; the walk stops at
    the first of them, so a sanctioned head found AFTER an `ssh` sanctions
    nothing.
    """
    for index, token in enumerate(tokens):
        head = basename(token=token).lower()
        if head == "ansible-playbook":
            return True, _playbook_rule(head=head, arguments=tokens[index + 1 :])
        if head == "just" and index + 1 < len(tokens) and tokens[index + 1] in _SANCTIONED_RECIPES:
            recipe = tokens[index + 1]
            if recipe == "ansible-drift":
                return True, None
            return True, _playbook_rule(head=recipe, arguments=tokens[index + 2 :])
        if head in known_heads:
            return False, None
    return False, None
