#!/usr/bin/env python3
"""
What counts as a MUTATION of a host, and what counts as a READ, per command head.

`_host_mutation` walks a remote command's tokens and asks this module two
questions about each head it meets, with that head's own argument run:

  - `mutation_of(head, arguments)` — is this POSITIVELY a mutation? Returns the
    rule name that convicts, else None. Used at every token position.
  - `read_only(head, arguments)` — is this POSITIVELY a read? Used only to
    decide what `sudo` may escalate without convicting on its own: `sudo`
    followed by anything that is not provably read-only IS the mutation
    (`sudo reboot`, `sudo /usr/local/bin/k3s-uninstall.sh`, `sudo some-tool`),
    because root is exactly the capability the discipline withholds from a
    hand. That default-convict is deliberate and is the one place the guard
    prefers the deny direction over positive identification.

The tables live in `_verb_tables`; this module applies them, in four shapes:

  - **Always mutating**: `install`, `tee`, `chmod`, `dd`, `useradd`, `reboot`,
    … — the head IS the verb.
  - **Path-scoped**: `cp`, `mv`, `rm`, `mkdir`, `touch`, `ln`, … write the host
    only when an operand lies under a protected tree (`/etc`, `/usr`, `/opt`,
    `/var/lib`, `/srv`, `/boot`); the same verb under `/tmp` or `$HOME` is
    scratch, which this guard does not police (a deliberate scoping: it
    guards host CONFIGURATION). A `>`-family redirection into a protected
    tree is the same write spelt differently.
  - **Inverted subcommand heads**: `systemctl`, `git`, `k3s`, `kubectl`,
    `helm`, `crictl`, `ctr`, `docker`, `tailscale`, `apt`, `snap`, `pip`,
    `npm`, `nft`. Their READ-ONLY verbs are enumerated and every other verb
    convicts, so a newly learned verb is denied rather than missed. The verb
    is the FIRST positional after the tool's global flags, so `kubectl -n
    apply logs x` reads and `kubectl get pods delete` reads; noun-verb tools
    (`docker container ls`, `k3s etcd-snapshot ls`, `kubectl auth can-i`) are
    judged at the second level. `kubectl`/`helm --dry-run=client|server`
    makes a verb a read; the LAST `--dry-run` wins. `git config` reads only
    with a `--get*`/`--list`/`--show-*` flag.
  - **Flag-judged heads**: reads by default that write under a flag —
    `find -delete|-exec`, `journalctl --vacuum*|--rotate`, `sed -i`,
    `yq -i`, `awk -i inplace`, `iptables -A|-D|-F|…`, `ip … add|del|set|
    exec`, `dmesg -c|-C`, `sysctl -w|--system|key=value`, `date -s`,
    `dpkg -i|-r|-P|…`, `hostname <name>`, `mount <operands>`, and an ad hoc
    `ansible` run with `--become` or a mutating module.

Anything not listed is UNKNOWN: not a mutation on its own, not a read under
`sudo`.

Self-contained by contract: the plugin installer ships this file under bare
system `python3` with no virtualenv and no third-party packages, so every
import here is the standard library or a sibling module shipped beside it.
"""

from __future__ import annotations

import re

from _shell_lex import basename, operands
from _verb_tables import (
    ALWAYS_MUTATING,
    ANSIBLE_MUTATING_MODULES,
    FLAG_MUTATIONS,
    FLAG_PREFIX_MUTATIONS,
    GIT_CONFIG_READ_FLAGS,
    MUTATING_KUBECTL_VERBS,
    PATH_SCOPED,
    PROTECTED_PREFIXES,
    READ_ONLY_HEADS,
    READ_ONLY_SECOND_LEVEL,
    READ_ONLY_SUBCOMMANDS,
    VALUE_FLAGS,
)

__all__: list[str] = ["MUTATING_KUBECTL_VERBS", "mutation_of", "read_only", "redirect_rule"]

# A subcommand is a lower-case word; `journalctl -u k3s -n 50` hands `k3s` a
# `50`, which is a value, not a verb, and so convicts nothing.
_SUBCOMMAND_WORD = re.compile(r"^[a-z][a-z0-9-]*$")
_DELEGATED_K3S_TOOLS = frozenset({"kubectl", "crictl", "ctr"})
_DRY_RUN_HEADS = frozenset({"kubectl", "helm"})
_DRY_RUN_OFF = frozenset({"none", "false"})
# `>`, `>>`, `1>`, `2>>`, `&>`, `>|` — every output redirection spelling.
_REDIRECT = re.compile(r"^(?:\d*|&)>{1,2}\|?")
_DESTINATION_ONLY = frozenset({"cp", "mv"})


def _positionals(*, head: str, arguments: list[str]) -> list[str]:
    """Operands with the tool's global flags (and their values) removed."""
    value_flags = VALUE_FLAGS.get(head, frozenset())
    out: list[str] = []
    index = 0
    total = len(arguments)
    while index < total:
        token = arguments[index]
        if token == "--":
            out.extend(arguments[index + 1 :])
            break
        if token.startswith("-") and token != "-":
            index += 2 if "=" not in token and token in value_flags else 1
            continue
        out.append(token)
        index += 1
    return out


def _protected(*, path: str) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in PROTECTED_PREFIXES)


def _dry_run(*, arguments: list[str]) -> bool:
    """True when the LAST `--dry-run` is on (kubectl and helm: last flag wins)."""
    mode = ""
    for index, token in enumerate(arguments):
        if token.startswith("--dry-run="):
            mode = token.split("=", 1)[1]
        elif token == "--dry-run":
            following = arguments[index + 1] if index + 1 < len(arguments) else ""
            mode = following if following and not following.startswith("-") else "client"
    return bool(mode) and mode not in _DRY_RUN_OFF


def _subcommand_rule(*, head: str, arguments: list[str]) -> str | None:
    positionals = _positionals(head=head, arguments=arguments)
    if not positionals or not _SUBCOMMAND_WORD.match(positionals[0]):
        return None
    verb = positionals[0]
    if head in _DRY_RUN_HEADS and _dry_run(arguments=arguments):
        return None
    if head == "k3s" and verb in _DELEGATED_K3S_TOOLS:
        # `k3s kubectl …` / `k3s crictl …` / `k3s ctr …` are those tools; judge them as such.
        return mutation_of(head=verb, arguments=arguments[arguments.index(verb) + 1 :])
    if head == "git" and verb == "config":
        return None if any(a in GIT_CONFIG_READ_FLAGS for a in arguments) else "git+config"
    nested = positionals[1] if len(positionals) > 1 else ""
    second = READ_ONLY_SECOND_LEVEL.get((head, verb))
    if second is not None:
        return None if nested in second else f"{head}+{verb}+{nested or 'none'}"
    reads = READ_ONLY_SUBCOMMANDS[head]
    if head == "ctr":
        return None if verb in reads or nested in reads else f"{head}+{verb}"
    return None if verb in reads else f"{head}+{verb}"


def _in_place_rule(*, head: str, arguments: list[str]) -> str | None:
    """`sed -i` / `sed -ni` / `--in-place`, and `awk -i inplace`."""
    if head == "sed" and any(
        a.startswith("--in-place")
        or (a.startswith("-") and not a.startswith("--") and "i" in a[1:])
        for a in arguments
    ):
        return "sed+in-place"
    if head == "awk" and any(
        a == "-i" and index + 1 < len(arguments) and arguments[index + 1] == "inplace"
        for index, a in enumerate(arguments)
    ):
        return "awk+inplace"
    return None


def _ansible_rule(*, arguments: list[str]) -> str | None:
    module = next(
        (
            arguments[i + 1]
            for i, a in enumerate(arguments)
            if a in {"-m", "--module-name"} and i + 1 < len(arguments)
        ),
        "",
    ).rsplit(".", 1)[-1]
    become = any(
        a == "--become" or (a.startswith("-") and not a.startswith("--") and "b" in a[1:])
        for a in arguments
    )
    return "ansible+adhoc" if become or module in ANSIBLE_MUTATING_MODULES else None


def _flag_rule(*, head: str, arguments: list[str]) -> str | None:
    """Mutating flags (or operands) of heads that are reads by default."""
    flags = FLAG_MUTATIONS.get(head, frozenset())
    prefixes = FLAG_PREFIX_MUTATIONS.get(head, ())
    for argument in arguments:
        if argument.split("=", 1)[0] in flags or (prefixes and argument.startswith(prefixes)):
            return f"{head}+{argument.split('=', 1)[0]}"
    if head == "sysctl" and any("=" in a and not a.startswith("-") for a in arguments):
        return "sysctl+write"
    if head in {"hostname", "mount"} and operands(arguments=arguments):
        return f"{head}+set"
    if head in PATH_SCOPED:
        paths = operands(arguments=arguments)
        touched = paths[-1:] if head in _DESTINATION_ONLY else paths
        return head if any(_protected(path=p) for p in touched) else None
    if head == "ansible":
        return _ansible_rule(arguments=arguments)
    return _in_place_rule(head=head, arguments=arguments)


def redirect_rule(*, tokens: list[str]) -> str | None:
    """An output redirection whose target is under a protected tree is a file write."""
    for index, token in enumerate(tokens):
        match = _REDIRECT.match(token)
        if match is None:
            continue
        path = token[match.end() :] or (tokens[index + 1] if index + 1 < len(tokens) else "")
        if _protected(path=path):
            return "redirect-into-protected-tree"
    return None


def mutation_of(*, head: str, arguments: list[str]) -> str | None:
    """The rule that convicts this head of a host mutation, else None."""
    name = basename(token=head).lower()
    if name in ALWAYS_MUTATING:
        return name
    if name in READ_ONLY_SUBCOMMANDS:
        return _subcommand_rule(head=name, arguments=arguments)
    return _flag_rule(head=name, arguments=arguments)


def read_only(*, head: str, arguments: list[str]) -> bool:
    """True when this head is POSITIVELY a read — what `sudo` may escalate freely."""
    name = basename(token=head).lower()
    if mutation_of(head=name, arguments=arguments) is not None:
        return False
    return name in READ_ONLY_HEADS or name in READ_ONLY_SUBCOMMANDS
