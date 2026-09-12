"""Structural tests for `.claude-plugin/hooks/_verb_tables.py`.

The tables are data; what can rot is their SHAPE: a verb spelt with a capital
that the lower-case matcher never sees, a second-level entry whose head is
not an inverted head, a value-flag table for a head nobody judges, a
protected prefix with a trailing slash that `startswith(prefix + "/")` would
never match. These pin those shapes so a table edit fails here by name.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / ".claude-plugin" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from _verb_tables import (  # noqa: E402 — path-dependent import after sys.path insert.
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

__all__: list[str] = []

_LOWER_WORD = re.compile(r"^[a-z0-9][a-z0-9._+-]*$|^--?[a-z][a-z-]*$|^\[$|^!$")


def test_every_head_and_verb_is_spelt_in_lower_case() -> None:
    """Heads are matched after `.lower()`, so a capital in a table is unreachable."""
    words = set(ALWAYS_MUTATING) | set(PATH_SCOPED) | set(READ_ONLY_HEADS)
    for head, verbs in READ_ONLY_SUBCOMMANDS.items():
        words.add(head)
        words.update(verbs)
    for (head, verb), nested in READ_ONLY_SECOND_LEVEL.items():
        words.update({head, verb, *(n for n in nested if n)})
    words.update(MUTATING_KUBECTL_VERBS, ANSIBLE_MUTATING_MODULES)
    assert all(_LOWER_WORD.match(word) for word in words), sorted(
        w for w in words if not _LOWER_WORD.match(w)
    )


def test_second_level_entries_hang_off_inverted_heads() -> None:
    for head, verb in READ_ONLY_SECOND_LEVEL:
        assert head in READ_ONLY_SUBCOMMANDS, (head, verb)
        assert verb in READ_ONLY_SUBCOMMANDS[head], (head, verb)


def test_value_flags_belong_to_heads_that_are_judged_by_verb() -> None:
    assert set(VALUE_FLAGS) <= set(READ_ONLY_SUBCOMMANDS)


def test_flag_judged_heads_are_reads_by_default() -> None:
    for head in set(FLAG_MUTATIONS) | set(FLAG_PREFIX_MUTATIONS):
        assert head in READ_ONLY_HEADS, head


def test_protected_prefixes_are_absolute_and_unslashed() -> None:
    for prefix in PROTECTED_PREFIXES:
        assert prefix.startswith("/"), prefix
        assert not prefix.endswith("/"), prefix
    assert {"/etc", "/usr", "/opt", "/var/lib", "/srv", "/boot"} == set(PROTECTED_PREFIXES)


def test_the_shapes_do_not_overlap() -> None:
    """A head in two tables would be judged twice by different rules."""
    assert not ALWAYS_MUTATING & READ_ONLY_HEADS
    assert not ALWAYS_MUTATING & set(READ_ONLY_SUBCOMMANDS)
    assert not ALWAYS_MUTATING & PATH_SCOPED
    assert not PATH_SCOPED & READ_ONLY_HEADS
    assert not set(READ_ONLY_SUBCOMMANDS) & READ_ONLY_HEADS


def test_the_scoping_decision_is_recorded_in_the_tables() -> None:
    """Scratch writes (`mkdir /tmp/x`) are not mutations; configuration writes are."""
    assert {"rm", "mkdir", "touch", "ln", "cp", "mv"} <= PATH_SCOPED
    assert "tee" in ALWAYS_MUTATING
    assert "install" in ALWAYS_MUTATING


def test_git_config_reads_only_through_query_flags() -> None:
    assert {"--get", "--list", "-l", "--show-origin"} <= GIT_CONFIG_READ_FLAGS


def test_every_inverted_head_lists_at_least_one_read_verb() -> None:
    """An inverted head with an empty read set would convict EVERY invocation of the tool."""
    for head, verbs in READ_ONLY_SUBCOMMANDS.items():
        assert verbs, head
