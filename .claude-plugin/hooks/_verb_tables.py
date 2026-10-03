#!/usr/bin/env python3
"""
The verb tables `_mutation_verbs` judges by — data only, no logic.

Every set here answers one question for one command head: which of its verbs
or flags READ the host, which WRITE it. The logic that applies them lives in
`_mutation_verbs`; keeping the tables apart keeps both readable and keeps
each file under the repository's LLOC ceiling as the tables grow.

Conventions:

  - `READ_ONLY_HEADS`: a head that is a read whatever its arguments (unless a
    `FLAG_MUTATIONS` / special rule says otherwise for a specific flag).
  - `READ_ONLY_SUBCOMMANDS`: INVERTED heads — the first positional after the
    tool's global flags is the verb; only the listed verbs read, every other
    verb convicts. A newly learned verb is denied rather than missed.
  - `READ_ONLY_SECOND_LEVEL`: for a (head, verb) pair, the nested verbs that
    read (`docker container ls`, `k3s certificate check`); `""` means the bare
    pair reads (`crictl image` alone lists images).
  - `VALUE_FLAGS`: a tool's flags that consume the next token, so the verb or
    operand is found in the right place (`kubectl -n apply logs x` reads,
    `mount -t nfs` lists).
  - `FLAG_MUTATIONS`: heads that read by default but write under a flag
    (`dpkg -i`, `iptables -A`, `dmesg -C`); `FLAG_PREFIX_MUTATIONS` the same
    by prefix (`journalctl --vacuum-time=…`).
  - `PATH_SCOPED`: heads judged by the tree their operands touch — a write
    under a `PROTECTED_PREFIXES` tree, or under a home's `HOME_PROTECTED_*`
    sub-trees, is host configuration; the same write under `/tmp` or the rest
    of `$HOME` is scratch and is NOT this guard's concern. `tee`,
    `chmod`, `chown` and `chgrp` are scoped the same way; `install` is not —
    it is a configuration write by construction.
  - `ALWAYS_MUTATING`: the head IS the verb.

Self-contained by contract: the plugin installer ships this file under bare
system `python3` with no virtualenv and no third-party packages, so every
import here is standard library.
"""

from __future__ import annotations

__all__: list[str] = [
    "ALWAYS_MUTATING",
    "ANSIBLE_MUTATING_MODULES",
    "CHECK_FLAGS",
    "CLUSTERED_FLAG_HEADS",
    "FLAG_MUTATIONS",
    "FLAG_PREFIX_MUTATIONS",
    "GIT_CONFIG_READ_FLAGS",
    "HOME_PROTECTED_NAME_PREFIXES",
    "HOME_PROTECTED_TREES",
    "MUTATING_KUBECTL_VERBS",
    "PATH_SCOPED",
    "PROTECTED_PREFIXES",
    "READ_ONLY_HEADS",
    "READ_ONLY_SECOND_LEVEL",
    "READ_ONLY_SUBCOMMANDS",
    "VALUE_FLAGS",
]


def _words(*, text: str) -> frozenset[str]:
    return frozenset(text.split())


PROTECTED_PREFIXES = ("/etc", "/usr", "/opt", "/var/lib", "/srv", "/boot")
# Inside a HOME (`~/`, `$HOME/`, `/home/<user>/`, `/root/`) only three configuration
# sub-trees are policed: access control, user units, and the Ansible-managed Fabro
# server state (`.fabro`, `.fabro-<instance>` — matched by name prefix). Repos,
# worktrees and scratch under a home stay unpoliced.
HOME_PROTECTED_TREES = (".ssh", ".config/systemd")
HOME_PROTECTED_NAME_PREFIXES = (".fabro",)

ALWAYS_MUTATING = _words(
    text="install dd mkfs fdisk parted umount useradd usermod userdel groupadd "
    "groupdel passwd reboot shutdown poweroff halt modprobe rmmod ufw iptables-restore "
    "ip6tables-restore nft-restore swapoff swapon k3s-uninstall.sh k3s-agent-uninstall.sh "
    "k3s-killall.sh"
)

# Writes only when an operand lies under a protected tree.
PATH_SCOPED = _words(text="cp mv rm rmdir mkdir touch ln truncate tee chmod chown chgrp")

READ_ONLY_HEADS = _words(
    text="cat ls stat grep egrep fgrep rg test [ head tail wc find df du id hostname uname uptime "
    "ps which pgrep true false echo printf less more dmesg ss lsof lsblk nvidia-smi ip free "
    "top htop w who last date printenv file readlink realpath md5sum sha256sum awk sed sort "
    "uniq cut tr diff cmp strings xxd hexdump journalctl iptables ip6tables iptables-save "
    "ip6tables-save sysctl getent nproc lscpu lsmod lspci lsusb numfmt column jq yq dpkg mount "
    "dig nslookup host ping traceroute curl wget"
)

READ_ONLY_SUBCOMMANDS: dict[str, frozenset[str]] = {
    "systemctl": _words(
        text="status show cat list-units list-timers list-unit-files list-dependencies "
        "list-sockets list-jobs list-machines list-paths list-automounts is-active is-enabled "
        "is-failed is-system-running get-default show-environment help --version"
    ),
    "git": _words(
        text="status log diff show rev-parse ls-files ls-remote ls-tree describe blame shortlog "
        "rev-list cat-file name-rev grep show-ref config var help version --version"
    ),
    "k3s": _words(
        text="check-config certificate kubectl crictl ctr secrets-encrypt etcd-snapshot token "
        "version --version -v help"
    ),
    "kubectl": _words(
        text="get describe logs top version explain auth api-resources api-versions diff "
        "cluster-info config wait events options completion plugin proxy port-forward attach "
        "help kustomize"
    ),
    "helm": _words(
        text="list ls status get history show search version env template lint verify pull "
        "dependency repo registry completion help plugin diff"
    ),
    "crictl": _words(
        text="ps images image img pods inspect inspecti inspectp logs stats statsp info version "
        "imagefsinfo completion help"
    ),
    "docker": _words(
        text="ps images image logs inspect version info stats top port diff history events search "
        "context help container compose system network volume node service stack"
    ),
    "tailscale": _words(text="status ip netcheck ping version whois bugreport metrics help"),
    "ctr": _words(text="ls list info check tree usage ps version plugins"),
    "apt": _words(
        text="list show search policy depends rdepends showpkg showsrc changelog download source "
        "madison stats check help --version"
    ),
    "apt-get": _words(text="check download source changelog help --version"),
    "apt-cache": _words(
        text="show search policy depends rdepends showpkg showsrc stats madison pkgnames"
    ),
    "snap": _words(
        text="list info find version known connections services logs changes tasks get help"
    ),
    "pip": _words(
        text="list show freeze check download index search inspect debug config help --version"
    ),
    "pip3": _words(
        text="list show freeze check download index search inspect debug config help --version"
    ),
    "npm": _words(text="ls list view info outdated audit help --version -v"),
    "nft": _words(text="list monitor describe --version -v help"),
}

# Nested verbs that read under a verb that is otherwise a write; `""` = bare pair reads.
READ_ONLY_SECOND_LEVEL: dict[tuple[str, str], frozenset[str]] = {
    ("k3s", "certificate"): _words(text="check"),
    ("k3s", "secrets-encrypt"): _words(text="status"),
    ("k3s", "etcd-snapshot"): _words(text="ls list"),
    ("k3s", "token"): _words(text="list"),
    ("kubectl", "auth"): _words(text="can-i whoami"),
    ("docker", "image"): _words(text="ls list inspect history"),
    ("docker", "container"): _words(text="ls list inspect logs stats top port diff"),
    ("docker", "compose"): _words(text="ps ls logs config version images top events port"),
    ("docker", "system"): _words(text="df info events"),
    ("docker", "network"): _words(text="ls list inspect"),
    ("docker", "volume"): _words(text="ls list inspect"),
    ("docker", "node"): _words(text="ls list inspect ps"),
    ("docker", "service"): _words(text="ls list ps logs inspect"),
    ("docker", "stack"): _words(text="ls list ps services"),
    ("crictl", "image"): frozenset({"", "ls", "list", "inspect"}),
}

# Global flags that consume the next token, per tool, so the verb is found.
VALUE_FLAGS: dict[str, frozenset[str]] = {
    "kubectl": _words(
        text="-n --namespace --context --kubeconfig --cluster --user -s --server --token --as "
        "--as-group --as-uid --cache-dir --certificate-authority --client-certificate "
        "--client-key --request-timeout --tls-server-name -v --v --profile --profile-output "
        "--log-flush-frequency --password --username --vmodule"
    ),
    "helm": _words(
        text="-n --namespace --kube-context --kubeconfig --kube-apiserver --kube-token "
        "--registry-config --repository-cache --repository-config"
    ),
    "systemctl": _words(
        text="-p --property -t --type --state -M --machine -H --host -n --lines -o --output --root"
    ),
    "git": _words(text="-C -c --git-dir --work-tree --namespace --exec-path"),
    "crictl": _words(text="-r --runtime-endpoint -i --image-endpoint -t --timeout -c --config"),
    "ctr": _words(text="-n --namespace -a --address -t --timeout"),
    "docker": _words(text="-H --host --context -l --log-level -c"),
    "tailscale": frozenset({"--socket"}),
    "nft": _words(text="-f --file -D --define -I --includepath"),
    "mount": _words(text="-t --types -L --label -U --uuid -N --namespace --source --target"),
}

# The verbs the fail-closed hazard hint treats as cluster mutations.
MUTATING_KUBECTL_VERBS = _words(
    text="apply patch taint delete cordon drain label edit scale create replace annotate set "
    "rollout exec uncordon run expose certificate cp debug"
)

# Heads that write under one of these flags: reads by default, or inverted heads
# whose ruleset-loading flags carry no verb (`nft -f file`, `mount -a`).
FLAG_MUTATIONS: dict[str, frozenset[str]] = {
    "nft": _words(text="-f --file -i --interactive"),
    "mount": _words(text="-a --all -o --options --source --target"),
    "find": _words(text="-delete -exec -execdir -ok -okdir"),
    "iptables": _words(
        text="-A -D -I -R -F -X -N -P -E -Z --append --delete --insert --replace --flush "
        "--delete-chain --new-chain --policy --rename-chain --zero"
    ),
    "ip6tables": _words(
        text="-A -D -I -R -F -X -N -P -E -Z --append --delete --insert --replace --flush "
        "--delete-chain --new-chain --policy --rename-chain --zero"
    ),
    "ip": _words(text="add del delete set change replace flush exec"),
    "dmesg": _words(text="-c -C --clear --read-clear"),
    "sysctl": _words(text="-w --write -p --load --system"),
    "date": _words(text="-s --set"),
    "yq": _words(text="-i --inplace"),
    "awk": _words(text="--inplace"),
    "dpkg": _words(
        text="-i --install --unpack --configure -r --remove -P --purge --set-selections "
        "--clear-selections --update-avail --merge-avail --clear-avail --forget-old-unavail "
        "--add-architecture --remove-architecture"
    ),
}
# A tool's own dry-run flag: the command reads even when a mutating flag is present.
CHECK_FLAGS: dict[str, frozenset[str]] = {"nft": _words(text="-c --check")}
# Heads whose single-letter flags cluster (`mount -av`): the cluster is split into
# letters before the FLAG_MUTATIONS lookup. Deliberately NOT `date` or `find`,
# whose `-Iseconds` / `-name` would otherwise read as `-s` / `-n -a -m -e`.
CLUSTERED_FLAG_HEADS = _words(text="mount dpkg iptables ip6tables dmesg nft yq")
FLAG_PREFIX_MUTATIONS: dict[str, tuple[str, ...]] = {
    "find": ("-fprint", "-fls"),
    "journalctl": ("--vacuum", "--rotate", "--flush", "--relinquish-var", "--sync", "--setup-keys"),
}

GIT_CONFIG_READ_FLAGS = _words(
    text="--get --get-all --get-regexp --get-urlmatch -l --list --show-origin --show-scope"
)

ANSIBLE_MUTATING_MODULES = _words(
    text="shell command raw script apt copy file systemd service lineinfile template user group "
    "cron mount reboot package pip git synchronize unarchive get_url"
)
