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
    (`sudo reboot`, `sudo /usr/local/bin/k3s-uninstall.sh`, `sudo cp x /tmp`),
    because root is exactly the capability the discipline withholds from a
    hand. That default-convict is deliberate and is the one place the guard
    prefers the deny direction over positive identification.

Three shapes of head, each judged its own way:

  - **Always mutating**: `install`, `tee`, `rm`, `chmod`, `apt`, `mkdir`, `dd`,
    `useradd`, `reboot`, … — the head IS the verb.
  - **Inverted subcommand heads**: `systemctl`, `git`, `k3s`, `kubectl`, `helm`,
    `crictl`, `ctr`, `docker`, `tailscale`. Their READ-ONLY subcommands are
    enumerated (`systemctl status|show|cat|list-*|is-*`, `git status|log|
    diff|show|…`, `kubectl get|describe|logs|top|…`) and every other verb
    convicts, so a newly learned verb (`systemctl kexec`, `kubectl certificate
    approve`) is denied rather than missed. The verb is the FIRST positional
    after the tool's global flags, so `kubectl -n apply logs x` reads and
    `kubectl get pods delete` reads. `kubectl --dry-run=client|server` makes
    a verb a read; the LAST `--dry-run` wins, as it does in kubectl.
  - **Flag-judged heads**: `find -delete|-exec`, `journalctl --vacuum*|--rotate`,
    `sed -i`, `iptables -A|-D|-F|…`, `ip … add|del|set|flush`, `dmesg -c|-C`,
    `sysctl -w|key=value`, `cp`/`mv` into a protected tree (`/etc`, `/usr`,
    `/boot`, `/var/lib`), a `>`/`>>` redirection into one, and an ad hoc
    `ansible` run with `--become` or a mutating module.

Anything not listed is UNKNOWN: not a mutation on its own, not a read under
`sudo`.

Self-contained by contract: the plugin installer ships this file under bare
system `python3` with no virtualenv and no third-party packages, so every
import here is standard library.
"""

from __future__ import annotations

import re

from _shell_lex import basename

__all__: list[str] = ["MUTATING_KUBECTL_VERBS", "mutation_of", "read_only", "redirect_rule"]

# A subcommand is a lower-case word; `journalctl -u k3s -n 50` hands `k3s` a
# `50`, which is a value, not a verb, and so convicts nothing.
_SUBCOMMAND_WORD = re.compile(r"^[a-z][a-z0-9-]*$")
_DELEGATED_K3S_TOOLS = frozenset({"kubectl", "crictl", "ctr"})

_PROTECTED_PREFIXES = ("/etc", "/usr", "/boot", "/var/lib")
_ALWAYS_MUTATING = frozenset(
    "install tee rm rmdir chmod chown chgrp apt apt-get dpkg snap mkdir touch truncate dd "
    "mkfs fdisk parted mount umount useradd usermod userdel groupadd groupdel passwd reboot "
    "shutdown poweroff halt modprobe rmmod ln ufw iptables-restore nft swapoff swapon pip "
    "pip3 npm".split()
)
_READ_ONLY_HEADS = frozenset(
    "cat ls stat grep egrep fgrep rg test [ head tail wc find df du id hostname uname uptime "
    "ps which pgrep true false echo printf less more dmesg ss lsof lsblk nvidia-smi ip free "
    "top htop w who last date printenv file readlink realpath md5sum sha256sum awk sed sort "
    "uniq cut tr diff cmp strings xxd hexdump journalctl iptables ip6tables sysctl getent "
    "nproc lscpu lsmod lspci lsusb numfmt column jq yq".split()
)
_READ_ONLY_SUBCOMMANDS: dict[str, frozenset[str]] = {
    "systemctl": frozenset(
        "status show cat list-units list-timers list-unit-files list-dependencies "
        "list-sockets list-jobs list-machines list-paths list-automounts is-active is-enabled "
        "is-failed is-system-running get-default show-environment help --version".split()
    ),
    "git": frozenset(
        "status log diff show rev-parse ls-files ls-remote ls-tree describe blame shortlog "
        "rev-list cat-file name-rev grep show-ref config var help version --version".split()
    ),
    "k3s": frozenset(
        "check-config certificate kubectl crictl ctr version --version -v help".split()
    ),
    "kubectl": frozenset(
        "get describe logs top version explain auth api-resources api-versions diff "
        "cluster-info config wait events options completion plugin proxy port-forward attach "
        "help kustomize".split()
    ),
    "helm": frozenset(
        "list ls status get history show search version env template lint verify pull "
        "dependency repo registry completion help plugin".split()
    ),
    "crictl": frozenset(
        "ps images image img pods inspect inspecti inspectp logs stats statsp info version "
        "imagefsinfo completion help".split()
    ),
    "docker": frozenset(
        "ps images image logs inspect version info stats top port diff history events search "
        "context help".split()
    ),
    "tailscale": frozenset("status ip netcheck ping version whois bugreport metrics help".split()),
    "ctr": frozenset("ls list info check tree usage ps version plugins".split()),
}
# Read-only sub-subcommands of a verb that is otherwise mutating.
_READ_ONLY_SECOND_LEVEL: dict[tuple[str, str], frozenset[str]] = {
    ("k3s", "certificate"): frozenset({"check"}),
    ("docker", "image"): frozenset({"ls", "list", "inspect", "history"}),
    ("crictl", "image"): frozenset({"ls", "list", "inspect"}),
}
# Global flags that consume the next token, per tool, so the verb is found.
_VALUE_FLAGS: dict[str, frozenset[str]] = {
    "kubectl": frozenset(
        "-n --namespace --context --kubeconfig --cluster --user -s --server --token --as "
        "--as-group --as-uid --cache-dir --certificate-authority --client-certificate "
        "--client-key --request-timeout --tls-server-name -v --v --profile --profile-output "
        "--log-flush-frequency --password --username --vmodule".split()
    ),
    "helm": frozenset(
        "-n --namespace --kube-context --kubeconfig --kube-apiserver --kube-token "
        "--registry-config --repository-cache --repository-config".split()
    ),
    "systemctl": frozenset(
        "-p --property -t --type --state -M --machine -H --host -n --lines -o --output "
        "--root".split()
    ),
    "git": frozenset("-C -c --git-dir --work-tree --namespace --exec-path".split()),
    "crictl": frozenset(
        "-r --runtime-endpoint -i --image-endpoint -t --timeout -c --config".split()
    ),
    "ctr": frozenset("-n --namespace -a --address -t --timeout".split()),
    "docker": frozenset("-H --host --context -l --log-level -c".split()),
    "tailscale": frozenset({"--socket"}),
    "k3s": frozenset(),
}
MUTATING_KUBECTL_VERBS = frozenset(
    "apply patch taint delete cordon drain label edit scale create replace annotate set "
    "rollout exec uncordon run expose certificate cp debug".split()
)
_FIND_MUTATIONS = frozenset("-delete -exec -execdir -ok -okdir".split())
_JOURNALCTL_MUTATIONS = (
    "--vacuum",
    "--rotate",
    "--flush",
    "--relinquish-var",
    "--sync",
    "--setup-keys",
)
_IPTABLES_MUTATIONS = frozenset(
    "-A -D -I -R -F -X -N -P -E -Z --append --delete --insert --replace --flush "
    "--delete-chain --new-chain --policy --rename-chain --zero".split()
)
_IP_MUTATIONS = frozenset("add del delete set change replace flush".split())
_ANSIBLE_MUTATING_MODULES = frozenset(
    "shell command raw script apt copy file systemd service lineinfile template user group "
    "cron mount reboot package pip git synchronize unarchive get_url".split()
)


def _positionals(*, head: str, arguments: list[str]) -> list[str]:
    """Operands with the tool's global flags (and their values) removed."""
    value_flags = _VALUE_FLAGS.get(head, frozenset())
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
    return any(path == prefix or path.startswith(prefix + "/") for prefix in _PROTECTED_PREFIXES)


def _kubectl_dry_run(*, arguments: list[str]) -> bool:
    """True when the LAST `--dry-run` is `client`/`server` (kubectl: last flag wins)."""
    mode = ""
    for index, token in enumerate(arguments):
        if token.startswith("--dry-run="):
            mode = token.split("=", 1)[1]
        elif token == "--dry-run":
            following = arguments[index + 1] if index + 1 < len(arguments) else ""
            mode = following if following and not following.startswith("-") else "client"
    return mode in {"client", "server"}


def _subcommand_rule(*, head: str, arguments: list[str]) -> str | None:
    positionals = _positionals(head=head, arguments=arguments)
    if not positionals or not _SUBCOMMAND_WORD.match(positionals[0]):
        return None
    verb = positionals[0]
    if head == "kubectl" and _kubectl_dry_run(arguments=arguments):
        return None
    if head == "k3s" and verb in _DELEGATED_K3S_TOOLS:
        # `k3s kubectl …` / `k3s crictl …` / `k3s ctr …` are those tools; judge them as such.
        index = arguments.index(verb)
        return mutation_of(head=verb, arguments=arguments[index + 1 :])
    second = _READ_ONLY_SECOND_LEVEL.get((head, verb))
    if second is not None:
        nested = positionals[1] if len(positionals) > 1 else ""
        return None if nested in second else f"{head}+{verb}+{nested or 'none'}"
    if head == "ctr":
        nested = positionals[1] if len(positionals) > 1 else ""
        return (
            None
            if verb in _READ_ONLY_SUBCOMMANDS[head] or nested in _READ_ONLY_SUBCOMMANDS[head]
            else f"{head}+{verb}"
        )
    return None if verb in _READ_ONLY_SUBCOMMANDS[head] else f"{head}+{verb}"


def _flag_rule(*, head: str, arguments: list[str]) -> str | None:
    """Mutating flags of heads that are reads by default."""
    if head == "find":
        return next(
            (
                f"find+{a}"
                for a in arguments
                if a in _FIND_MUTATIONS or a.startswith(("-fprint", "-fls"))
            ),
            None,
        )
    if head == "journalctl":
        return next(
            (
                f"journalctl+{a.split('=')[0]}"
                for a in arguments
                if a.startswith(_JOURNALCTL_MUTATIONS)
            ),
            None,
        )
    if head == "sed":
        return (
            "sed+in-place"
            if any(
                a == "--in-place"
                or a.startswith("--in-place=")
                or (a.startswith("-") and not a.startswith("--") and "i" in a[1:])
                for a in arguments
            )
            else None
        )
    if head in {"iptables", "ip6tables"}:
        return next((f"{head}+{a}" for a in arguments if a in _IPTABLES_MUTATIONS), None)
    if head == "ip":
        return next((f"ip+{a}" for a in arguments if a in _IP_MUTATIONS), None)
    if head == "dmesg":
        return (
            "dmesg+clear"
            if any(a in {"-c", "-C", "--clear", "--read-clear"} for a in arguments)
            else None
        )
    if head == "sysctl":
        return (
            "sysctl+write"
            if any(
                a in {"-w", "--write", "-p", "--load"} or ("=" in a and not a.startswith("-"))
                for a in arguments
            )
            else None
        )
    if head in {"cp", "mv"}:
        operands = [a for a in arguments if not a.startswith("-")]
        return head if operands and _protected(path=operands[-1]) else None
    if head == "ansible":
        module = next(
            (
                arguments[i + 1]
                for i, a in enumerate(arguments)
                if a in {"-m", "--module-name"} and i + 1 < len(arguments)
            ),
            "",
        )
        become = any(
            a in {"-b", "--become"}
            or (a.startswith("-") and not a.startswith("--") and "b" in a[1:])
            for a in arguments
        )
        return "ansible+adhoc" if become or module in _ANSIBLE_MUTATING_MODULES else None
    return None


def redirect_rule(*, tokens: list[str]) -> str | None:
    """A `>`/`>>` whose target is under a protected tree is a file write on the host."""
    for index, token in enumerate(tokens):
        if not token.startswith(">"):
            continue
        path = token.lstrip(">") or (tokens[index + 1] if index + 1 < len(tokens) else "")
        if _protected(path=path):
            return "redirect-into-protected-tree"
    return None


def mutation_of(*, head: str, arguments: list[str]) -> str | None:
    """The rule that convicts this head of a host mutation, else None."""
    name = basename(token=head).lower()
    if name in _ALWAYS_MUTATING:
        return name
    if name in _READ_ONLY_SUBCOMMANDS:
        return _subcommand_rule(head=name, arguments=arguments)
    return _flag_rule(head=name, arguments=arguments)


def read_only(*, head: str, arguments: list[str]) -> bool:
    """True when this head is POSITIVELY a read — what `sudo` may escalate freely."""
    name = basename(token=head).lower()
    if mutation_of(head=name, arguments=arguments) is not None:
        return False
    return name in _READ_ONLY_HEADS or name in _READ_ONLY_SUBCOMMANDS
