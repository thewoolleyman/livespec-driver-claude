"""Unit tests for `.claude-plugin/hooks/_remote_target.py`.

The argv grammars of `ssh`, `scp`, `rsync`, and `sftp`, pinned one observable
property each: getopt clusters and value letters, `-o HostName=`/
`RemoteCommand=`, `--`, transfer operand spellings, popt permutation,
dry-run and remove-source flags, the stdin-batch rule, and the unresolvable
marker. Every argv here is inert data.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / ".claude-plugin" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from _remote_target import (  # noqa: E402 — path-dependent import after sys.path insert.
    SftpReach,
    SshReach,
    TransferReach,
    host_of_target,
    is_fleet_host,
    parse_sftp,
    parse_ssh,
    parse_transfer,
    sftp_batch_mutates,
)

__all__: list[str] = []

_HOSTS = frozenset({"vps", "poweredge-xubuntu"})


@pytest.mark.parametrize(
    ("target", "host"),
    [
        ("poweredge-xubuntu", "poweredge-xubuntu"),
        ("cwoolley@poweredge-xubuntu", "poweredge-xubuntu"),
        ("ssh://cwoolley@poweredge-xubuntu:22/", "poweredge-xubuntu"),
        ("scp://poweredge-xubuntu/etc/x", "poweredge-xubuntu"),
        ("rsync://poweredge-xubuntu/module/", "poweredge-xubuntu"),
        ("poweredge-xubuntu:/etc/x", "poweredge-xubuntu"),
    ],
)
def test_host_of_target_strips_user_scheme_port_and_path(target: str, host: str) -> None:
    assert host_of_target(target=target) == host


@pytest.mark.parametrize(
    ("name", "fleet"),
    [
        ("poweredge-xubuntu", True),
        ("POWEREDGE-XUBUNTU.", True),
        ("poweredge-xubuntu.tail1234.ts.net", True),
        ("otherhost", False),
        ("", False),
    ],
)
def test_is_fleet_host_is_case_insensitive_and_matches_the_first_label(
    name: str, fleet: bool
) -> None:
    assert is_fleet_host(name=name, hosts=_HOSTS) is fleet


@pytest.mark.parametrize(
    ("arguments", "reach"),
    [
        (["poweredge-xubuntu", "sudo", "x"], SshReach(host="poweredge-xubuntu", remote=["sudo x"])),
        (["-tp", "22", "poweredge-xubuntu", "x"], SshReach(host="poweredge-xubuntu", remote=["x"])),
        (["-p22", "-l", "u", "poweredge-xubuntu"], SshReach(host="poweredge-xubuntu")),
        (
            ["-i", "key", "poweredge-xubuntu", "--", "x"],
            SshReach(host="poweredge-xubuntu", remote=["-- x"]),
        ),
        (["--", "poweredge-xubuntu", "x"], SshReach(host="poweredge-xubuntu", remote=["x"])),
        (["-", "poweredge-xubuntu"], SshReach(host="-", remote=["poweredge-xubuntu"])),
        (
            ["-o", "RemoteCommand=sudo x", "poweredge-xubuntu"],
            SshReach(host="poweredge-xubuntu", remote=["sudo x"]),
        ),
        (
            ["-oHostName=poweredge-xubuntu", "alias", "x"],
            SshReach(host="poweredge-xubuntu", remote=["x"]),
        ),
        (
            ["-o", "Hostname poweredge-xubuntu", "alias"],
            SshReach(host="poweredge-xubuntu"),
        ),
        (["-o", "Compression", "poweredge-xubuntu"], SshReach(host="poweredge-xubuntu")),
        (["-o", "RemoteCommand=", "poweredge-xubuntu"], SshReach(host="poweredge-xubuntu")),
        (["$H", "x"], SshReach(host="$H", remote=["x"], unresolvable=True)),
        (["", "x"], SshReach(host="", remote=["x"], unresolvable=True)),
        (["-o", "HostName=$H", "alias"], SshReach(host="$H", unresolvable=True)),
    ],
)
def test_parse_ssh_finds_the_host_and_the_remote_command(
    arguments: list[str], reach: SshReach
) -> None:
    assert parse_ssh(arguments=arguments) == reach


@pytest.mark.parametrize("arguments", [[], ["-p"], ["-p", "22"], ["--"], ["-G"]])
def test_parse_ssh_without_an_operand_reaches_nothing(arguments: list[str]) -> None:
    assert parse_ssh(arguments=arguments) == SshReach(host=None)


@pytest.mark.parametrize(
    ("head", "arguments", "reach"),
    [
        (
            "scp",
            ["./x", "poweredge-xubuntu:/etc/x"],
            TransferReach(destination="poweredge-xubuntu"),
        ),
        (
            "scp",
            ["-P", "22", "./x", "u@poweredge-xubuntu:/x"],
            TransferReach(destination="poweredge-xubuntu"),
        ),
        (
            "scp",
            ["./x", "scp://poweredge-xubuntu/etc/x"],
            TransferReach(destination="poweredge-xubuntu"),
        ),
        (
            "scp",
            ["poweredge-xubuntu:/x", "./x"],
            TransferReach(destination=None, sources=["poweredge-xubuntu"]),
        ),
        ("scp", ["./a", "./b"], TransferReach(destination=None)),
        ("scp", ["./a", "./dir:with:colons/b"], TransferReach(destination=None)),
        ("scp", ["./a", ":/x"], TransferReach(destination=None, unresolvable=True)),
        ("scp", ["-r"], TransferReach(destination=None)),
        ("scp", ["./x", "{}:/etc/x"], TransferReach(destination="{}", unresolvable=True)),
        # glibc getopt permutes: an option after the operands is still an option.
        (
            "scp",
            ["./x", "poweredge-xubuntu:/etc/x", "-o", "StrictHostKeyChecking=no"],
            TransferReach(destination="poweredge-xubuntu"),
        ),
        (
            "scp",
            ["-3", "other:/x", "poweredge-xubuntu:/etc/x"],
            TransferReach(destination="poweredge-xubuntu", sources=["other"]),
        ),
        (
            "rsync",
            ["-avne", "ssh", "./x", "poweredge-xubuntu:/opt/x"],
            TransferReach(destination="poweredge-xubuntu", dry_run=True),
        ),
        (
            "rsync",
            ["-en", "./x", "poweredge-xubuntu:/opt/x"],
            TransferReach(destination="poweredge-xubuntu"),
        ),
        (
            "rsync",
            ["--rsh=ssh", "-av", "./x", "poweredge-xubuntu:/etc/x"],
            TransferReach(destination="poweredge-xubuntu"),
        ),
        (
            "rsync",
            ["-av", "./x", "poweredge-xubuntu::mod/"],
            TransferReach(destination="poweredge-xubuntu"),
        ),
        (
            "rsync",
            ["-av", "./x", "poweredge-xubuntu:/etc/x", "-e", "ssh -p 22"],
            TransferReach(destination="poweredge-xubuntu"),
        ),
        (
            "rsync",
            ["-av", "./x", "poweredge-xubuntu:/x", "--rsync-path", "sudo rsync"],
            TransferReach(destination="poweredge-xubuntu"),
        ),
        (
            "rsync",
            ["-av", "--rsync-path=sudo rsync", "./x", "poweredge-xubuntu:/x"],
            TransferReach(destination="poweredge-xubuntu"),
        ),
        (
            "rsync",
            ["-avn", "./x", "poweredge-xubuntu:/x"],
            TransferReach(destination="poweredge-xubuntu", dry_run=True),
        ),
        (
            "rsync",
            ["-av", "--dry-run", "./x", "poweredge-xubuntu:/x"],
            TransferReach(destination="poweredge-xubuntu", dry_run=True),
        ),
        (
            "rsync",
            ["-av", "--remove-source-files", "poweredge-xubuntu:/x", "./"],
            TransferReach(destination=None, sources=["poweredge-xubuntu"], remove_source=True),
        ),
        (
            "rsync",
            ["-e", "ssh", "./x", "poweredge-xubuntu:/x"],
            TransferReach(destination="poweredge-xubuntu"),
        ),
        (
            "rsync",
            ["-essh", "./x", "poweredge-xubuntu:/x"],
            TransferReach(destination="poweredge-xubuntu"),
        ),
        (
            "rsync",
            ["-av", "--", "./x", "poweredge-xubuntu:/x"],
            TransferReach(destination="poweredge-xubuntu"),
        ),
        (
            "rsync",
            ["-av", "-", "poweredge-xubuntu:/x"],
            TransferReach(destination="poweredge-xubuntu"),
        ),
        ("rsync", ["-av", "./x"], TransferReach(destination=None)),
    ],
)
def test_parse_transfer_finds_the_destination_through_permuted_options(
    head: str, arguments: list[str], reach: TransferReach
) -> None:
    assert parse_transfer(head=head, arguments=arguments) == reach


@pytest.mark.parametrize(
    ("arguments", "reach"),
    [
        (["poweredge-xubuntu"], SftpReach(host="poweredge-xubuntu", batch_from_stdin=True)),
        (
            ["-b", "-", "u@poweredge-xubuntu"],
            SftpReach(host="poweredge-xubuntu", batch_from_stdin=True),
        ),
        (
            ["-b", "batch.txt", "poweredge-xubuntu"],
            SftpReach(host="poweredge-xubuntu", batch_from_stdin=False),
        ),
        (["sftp://poweredge-xubuntu"], SftpReach(host="poweredge-xubuntu", batch_from_stdin=True)),
        ([], SftpReach(host=None, batch_from_stdin=False)),
        (["-v"], SftpReach(host=None, batch_from_stdin=False)),
    ],
)
def test_parse_sftp_reports_whether_the_batch_is_readable(
    arguments: list[str], reach: SftpReach
) -> None:
    assert parse_sftp(arguments=arguments) == reach


# --- Unreadable TARGETS: the operands the guard cannot resolve by reading -------
# The fleet-host-mutation-guard clause (livespec v223) stated two of these as a
# LIMIT: only an `scp`/`rsync` DESTINATION was treated as possibly unreadable and
# `parse_sftp` never reported one at all, so `sftp $h` and
# `rsync --remove-source-files $h:/opt/x ./` reached a host nobody could read and
# nothing said so. The field names asserted below are the classifier's contract.


@pytest.mark.parametrize(
    ("head", "arguments", "unreadable"),
    [
        ("rsync", ["-av", "--remove-source-files", "$h:/opt/x", "./"], True),
        ("scp", [":/x", "./"], True),
        ("rsync", ["-av", "rsync://$h/mod/", "./"], True),
        ("scp", ["{}:/opt/x", "./"], True),
        ("scp", ["poweredge-xubuntu:/x", "./x"], False),
        # A LOCAL path carrying a substitution is not a remote target: the lexer
        # splits `./syslog-$(date +%F)` in two and neither half names a host.
        ("scp", ["poweredge-xubuntu:/var/log/syslog", "./syslog-$(date", "+%F"], False),
    ],
)
def test_parse_transfer_flags_a_source_whose_host_cannot_be_read(
    head: str, arguments: list[str], unreadable: bool
) -> None:
    reach = parse_transfer(head=head, arguments=arguments)
    assert (
        "source_unresolvable" in reach.__dataclass_fields__
    ), "TransferReach must report an unreadable SOURCE, not only an unreadable destination"
    assert reach.source_unresolvable is unreadable


@pytest.mark.parametrize(
    ("arguments", "unreadable"),
    [
        (["$h"], True),
        (["-b", "-", "{}"], True),
        (["poweredge-xubuntu"], False),
        ([], False),
    ],
)
def test_parse_sftp_flags_a_host_operand_that_cannot_be_read(
    arguments: list[str], unreadable: bool
) -> None:
    reach = parse_sftp(arguments=arguments)
    assert (
        "unresolvable" in reach.__dataclass_fields__
    ), "SftpReach must report an sftp host operand the guard cannot resolve by reading"
    assert reach.unresolvable is unreadable


@pytest.mark.parametrize(
    ("batch", "mutates"),
    [
        ("put x /etc/y", True),
        ("-put x /etc/y", True),
        ("PUT x /etc/y", True),
        ("reput x", True),
        ("ls\nget x ./x\n\n", False),
        ("", False),
        ("  \n  ", False),
    ],
)
def test_sftp_batch_mutates_reads_verbs_case_insensitively(batch: str, mutates: bool) -> None:
    assert sftp_batch_mutates(batch=batch) is mutates
