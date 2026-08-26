#!/usr/bin/env python3
"""PreToolUse guard for GitHub CLI polling and mutation bursts.

Declared in hooks.json on the `Bash` tool. This hook denies only the
load-bearing conjunctions that exhaust GitHub budgets quickly:

- `gh run`, `gh pr`, or UNCACHED read-only `gh api` calls driven by a loop
  whose iteration count is NOT readable off the command text, or by a loop
  that sleeps between iterations (a `gh api --cache <duration>` read is the
  remedy this hook prescribes, so it is exempt);
- shell loops or `xargs` combined with mutating `gh api` calls.

Both verdicts read a MASKED copy of the command in which quoted spans and
heredoc bodies have been removed, so a token that is data rather than a
command cannot convict. See `_mask_command` for what survives masking and why.

The read verdict EXEMPTS a bounded literal loop: a `for NAME in <items>` whose
items are plain literal words -- no parameter expansion, no command
substitution, no glob, no brace expansion -- and which lists at most 10 of
them. `for id in 1 2 3 4 5 6` is six calls, and a read costs one point against
the same 900-point-per-minute primary ceiling the mutation verdict cites, so
ten reads spend about one percent of it even when the shell issues them all in
the same second. Ten is the threshold because it sits far below the point
where the count could matter AND about where a hand-typed list stops: past it
an author reaches for `$(seq ...)`, a glob, or a variable, whose sizes are NOT
readable from the text and which therefore stay denied at any apparent size.
The load-bearing property is that the iteration count is LEGIBLE, not the
exact number, so the threshold is a judgement call rather than a derived
constant.

The exemption covers ENUMERATION, not POLLING. A `sleep` inside a loop body
means the loop is waiting for state to change rather than fetching a known
list, so it denies at any size. Conversely a `sleep` OUTSIDE every loop body
-- `sleep 30; gh api ...`, one polite poll -- no longer denies at all: 44 of
615 denials over the 7 days to 2026-08-26 were exactly that shape. `while`,
`until` and `select` carry no readable bound and are denied unchanged, as is
the whole mutation verdict -- a mutation costs five points, so even a
two-iteration literal loop over mutations stays denied.

Hook protocol: hook-input JSON on stdin (`tool_name`, `tool_input.command`).
Exit 2 denies the tool call and puts the reason on stderr. Exit 0 allows it.
Every error path returns 0 (fail-open), including crashes and unparseable
input, because a failing plugin-shipped hook can wedge every governed repo.

Self-contained by contract: the plugin installer ships this file under bare
system `python3` with no virtualenv and no third-party packages, so every
import here is from the standard library.
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from typing import cast

__all__: list[str] = []

_READ_DENY_REASON = (
    "DENIED by github_rate_limit_guard.py: GitHub reads driven by a loop with "
    "no readable iteration bound, or by a loop that sleeps between iterations, "
    "must use the cached alternative `gh api --cache <duration>`; a 304 "
    "response costs no primary rate-limit budget. A loop over a literal list of "
    "at most ten items, with no sleep in its body, needs no change."
)
_MUTATION_DENY_REASON = (
    "DENIED by github_rate_limit_guard.py: looped or xargs-fed mutating "
    "GitHub API calls are rate-limit hazards. GitHub API mutations cost five "
    "points against a nine-hundred-point-per-minute ceiling, so more than "
    "about one hundred eighty per minute trips it regardless of hourly budget; "
    "at least one second between mutations is required."
)

# A loop keyword only starts a loop in COMMAND POSITION: at the beginning of
# a line, after a `;`/`&`/`|` separator, or after `do`/`then`. Matching the
# bare word anywhere denied any `gh pr`/`gh run` command whose text merely
# contained "for", "while", "until" or "sleep" -- ordinary English that turns
# up constantly in PR titles, paths and jq filters.
#
# MULTILINE is load-bearing rather than incidental: requiring command position
# without it would stop matching a real loop that begins on any line after the
# first, which is the common shape for a multi-line command.
_CMD_POS = r"(?:^|[;&|]\s*|\bdo\s+|\bthen\s+)"
_SHELL_SELECT = rf"{_CMD_POS}select\s+[A-Z_][A-Z0-9_]*(?=\s+(?:in|do)\b|\s*;)"
_SHELL_LOOP = rf"{_CMD_POS}(?:for|while|until)\b"
_SHELL_SLEEP = rf"{_CMD_POS}sleep\b"
_LOOP_OR_XARGS = re.compile(
    rf"{_SHELL_LOOP}|{_CMD_POS}xargs\b|{_SHELL_SELECT}",
    re.IGNORECASE | re.MULTILINE,
)
# A loop whose iteration count cannot be read off the command text at all:
# `while` and `until` run until a condition flips, and `select` re-prompts
# until the user breaks out. No apparent size makes any of them bounded.
_UNBOUNDED_LOOP = re.compile(
    rf"{_CMD_POS}(?:while|until)\b|{_SHELL_SELECT}",
    re.IGNORECASE | re.MULTILINE,
)
# A `for` loop and the header text between the keyword and the `do`.
_FOR_LOOP = re.compile(rf"{_CMD_POS}for\b(?P<header>[^\n;]*)", re.IGNORECASE | re.MULTILINE)
# `for NAME in <items>` is the ONE loop header that writes its own iteration
# count out in full. A C-style `for ((...))` header and the argument-less
# `for NAME; do` (which iterates the positional parameters) both fail to match.
_FOR_IN_HEADER = re.compile(r"^\s+[A-Za-z_][A-Za-z0-9_]*\s+in\s+(?P<items>\S.*?)\s*$")
# One item of a literal list. A `$`, a backtick, a glob metacharacter or a
# brace makes the shell expand the word into an unknown number of words, so it
# disqualifies the whole list.
_LITERAL_ITEM = re.compile(r"^[A-Za-z0-9_@%+=:,./^-]+$")
_SLEEP = re.compile(_SHELL_SLEEP, re.IGNORECASE | re.MULTILINE)
_DO_OR_DONE = re.compile(rf"{_CMD_POS}(?P<word>do|done)\b", re.IGNORECASE | re.MULTILINE)
_MAX_LITERAL_ITERATIONS = 10
_GH_READ = re.compile(r"\bgh\s+(?:run|pr)\b", re.IGNORECASE)
_GH_API = re.compile(r"\bgh\s+api\b(?P<args>[^\n;&|]*)", re.IGNORECASE)
_MUTATING_METHOD = re.compile(
    r"(?:\s|^)(?:-X|--method)(?:=|\s+)(?P<method>delete|post|patch|put)\b",
    re.IGNORECASE,
)
# `gh api --cache <duration>` is the very remedy _READ_DENY_REASON prescribes:
# a cache hit answers 304, which spends no primary rate-limit budget. Counting
# it as a rate-limited read denied the agent for obeying the instruction it was
# just given -- 96 of 615 denials over the 7 days to 2026-08-26 were commands
# already in the sanctioned cached form.
#
# The duration is REQUIRED, not optional: a bare `--cache` is not valid `gh`,
# so a value that is absent or is the next flag buys no exemption.
_CACHED_READ = re.compile(r"(?:\s|^)--cache(?:=|\s+)(?!-)(?P<duration>[^\s]+)", re.IGNORECASE)

# A heredoc redirection: `<<EOF`, `<<-EOF`, `<<'PY'`, `<<"PY"`. `<<<` is a
# HERE-STRING, not a heredoc, and is excluded for free -- its third `<` cannot
# start the delimiter word.
_HEREDOC_START = re.compile(
    r"<<-?\s*(?P<quote>['\"]?)(?P<delimiter>[A-Za-z_][A-Za-z0-9_]*)(?P=quote)"
)
# The text immediately before a quoted span, when that span is the script
# argument of a SHELL interpreter (`sh`, `bash`, `dash`, `ksh`, `zsh`, by bare
# name or by path) reached through `-c` or a combined form such as `-lc`.
_SHELL_C_PAYLOAD = re.compile(
    r"(?:^|[\s;&|(])(?:[\w./-]*/)?(?:ba|da|k|z)?sh\s+(?:-\w+\s+)*-\w*c\s*$",
    re.IGNORECASE,
)
_QUOTES = "'\""
# A masked span collapses to one WORD character rather than to nothing or to a
# space. Nothing would JOIN the neighbouring text into a token the author never
# wrote; a space would erase the fact that an argument stood there at all, so
# `gh api --cache "10m"` would read as a bare `--cache` -- an UNCACHED read,
# denied for using the very form the deny message prescribes.
_MASKED_SPAN = "_"


def _utc_timestamp() -> str:
    return datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _log_event(*, level: str, event: str, check_id: str, command: object = None) -> None:
    payload: dict[str, object] = {
        "level": level,
        "timestamp": _utc_timestamp(),
        "check_id": check_id,
        "event": event,
    }
    if command is not None:
        payload["command"] = command
    _ = sys.stderr.write(json.dumps(payload, sort_keys=True) + "\n")


def _as_object_dict(*, value: object) -> dict[str, object] | None:
    if isinstance(value, dict):
        return cast("dict[str, object]", value)
    return None


def _load_hook_input(*, raw: str) -> dict[str, object] | None:
    try:
        return _as_object_dict(value=json.loads(raw))
    except json.JSONDecodeError:
        return None


def _strip_heredoc_bodies(*, command: str) -> str:
    """Drop every heredoc body, and its terminator, from the command text.

    A body runs from the line after the redirection to the line whose stripped
    content is the delimiter. An UNTERMINATED heredoc runs to the end, which is
    how the shell itself reads it.
    """
    lines = command.split("\n")
    kept: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        kept.append(line)
        index += 1
        for match in _HEREDOC_START.finditer(line):
            delimiter = match.group("delimiter")
            while index < len(lines) and lines[index].strip() != delimiter:
                index += 1
            index += 1
    return "\n".join(kept)


def _closing_quote_index(*, text: str, quote: str, start: int) -> int:
    """Index of the quote closing this span, or -1 when the span is unterminated.

    A single-quoted span has no escapes; inside a double-quoted span a
    backslash escapes the character after it, `"` included.
    """
    if quote == "'":
        return text.find(quote, start)
    index = start
    while index < len(text):
        if text[index] == "\\":
            index += 2
            continue
        if text[index] == quote:
            return index
        index += 1
    return -1


def _mask_quoted_spans(*, text: str) -> str:
    """Replace each quoted span with `_MASKED_SPAN`, keeping shell `-c` payloads."""
    masked: list[str] = []
    index = 0
    while index < len(text):
        character = text[index]
        if character == "\\":
            masked.append(text[index : index + 2])
            index += 2
            continue
        if character not in _QUOTES:
            masked.append(character)
            index += 1
            continue
        end = _closing_quote_index(text=text, quote=character, start=index + 1)
        body = text[index + 1 :] if end < 0 else text[index + 1 : end]
        if _SHELL_C_PAYLOAD.search("".join(masked)):
            masked.append(f"\n{_mask_command(command=body)}\n")
        else:
            masked.append(_MASKED_SPAN)
        index = len(text) if end < 0 else end + 1
    return "".join(masked)


def _mask_command(*, command: str) -> str:
    """Reduce the command to the text the SHELL will execute.

    `_CMD_POS` anchors a loop keyword to command position, but under MULTILINE
    every line of a heredoc body and every line of a quoted interpreter script
    begins a line, so the whole body reads as command position. The guard could
    not tell a shell loop from a Python loop, nor a command from a quoted
    argument: 109 of 615 denials over the 7 days to 2026-08-26 carried NO `gh`
    invocation at command position at all -- `gh` appeared only inside a string,
    a path or a regex -- and 31 of those were heredoc or quoted-script bodies.
    A `grep` whose SEARCH PATTERN spelled `gh api|for loop` was denied for the
    pattern it was searching FOR.

    The ONE quoted span that survives is a shell interpreter's `-c` payload:
    `cat ids | xargs -I{} bash -c 'gh api -X PATCH ...'` is a genuine mutation
    burst hiding one quoting level down, so that body is masked recursively and
    spliced back between newlines, where its own command positions read
    normally. A heredoc fed to a shell is NOT re-read: the measured population
    is Python, jq and Markdown bodies, and treating a heredoc body as data is
    the contract this guard is held to.
    """
    return _mask_quoted_spans(text=_strip_heredoc_bodies(command=command))


def _is_bounded_literal_for(*, header: str) -> bool:
    """Whether a `for` header enumerates a short, fully literal word list.

    A masked span is rejected outright: `"$@"` and `"${refs[@]}"` mask to the
    same single token as `"main"` yet expand to as many words as the caller
    supplied, so the guard cannot count what it deliberately cannot see.
    """
    match = _FOR_IN_HEADER.match(header)
    if match is None:
        return False
    items = match.group("items").split()
    return len(items) <= _MAX_LITERAL_ITERATIONS and all(
        item != _MASKED_SPAN and _LITERAL_ITEM.match(item) for item in items
    )


def _loop_body_spans(*, command: str) -> list[tuple[int, int]]:
    """Character ranges of every `do ... done` body, innermost range first.

    An unterminated `do` runs to the end of the command, which is how far the
    shell would read it. A `done` with no open `do` is a shell syntax error; it
    closes nothing, so it is skipped rather than opening a range backwards.
    """
    opened: list[int] = []
    spans: list[tuple[int, int]] = []
    for match in _DO_OR_DONE.finditer(command):
        if match.group("word").lower() == "do":
            opened.append(match.end())
        elif opened:
            spans.append((opened.pop(), match.start()))
    spans.extend([(start, len(command)) for start in opened])
    return spans


def _has_sleep_in_loop_body(*, command: str) -> bool:
    spans = _loop_body_spans(command=command)
    return any(
        any(start <= match.start() < end for start, end in spans)
        for match in _SLEEP.finditer(command)
    )


def _has_read_hazard(*, command: str) -> bool:
    """Whether the command drives GitHub reads at a rate the guard denies."""
    if _UNBOUNDED_LOOP.search(command):
        return True
    if any(
        not _is_bounded_literal_for(header=match.group("header"))
        for match in _FOR_LOOP.finditer(command)
    ):
        return True
    return _has_sleep_in_loop_body(command=command)


def _has_loop_or_xargs(*, command: str) -> bool:
    return bool(_LOOP_OR_XARGS.search(command))


def _has_mutating_gh_api(*, command: str) -> bool:
    return any(_MUTATING_METHOD.search(match.group("args")) for match in _GH_API.finditer(command))


def _has_read_gh_call(*, command: str) -> bool:
    # `gh run` / `gh pr` have no response cache, so no flag exempts them.
    if _GH_READ.search(command):
        return True
    for match in _GH_API.finditer(command):
        args = match.group("args")
        if _MUTATING_METHOD.search(args) or _CACHED_READ.search(args):
            continue
        return True
    return False


def _deny_reason(*, command: str) -> str | None:
    masked = _mask_command(command=command)
    if _has_loop_or_xargs(command=masked) and _has_mutating_gh_api(command=masked):
        return _MUTATION_DENY_REASON
    if _has_read_hazard(command=masked) and _has_read_gh_call(command=masked):
        return _READ_DENY_REASON
    return None


def _guard(*, raw_input: str) -> int:
    hook_input = _load_hook_input(raw=raw_input)
    if hook_input is None:
        _log_event(
            level="warning",
            check_id="github-rate-limit-guard-unparseable",
            event="unparseable hook input; failing open",
        )
        return 0
    if hook_input.get("tool_name") != "Bash":
        return 0
    tool_input = _as_object_dict(value=hook_input.get("tool_input"))
    if tool_input is None:
        return 0
    command = tool_input.get("command")
    if not isinstance(command, str):
        return 0
    reason = _deny_reason(command=command)
    if reason is None:
        return 0
    _log_event(
        level="error",
        check_id="github-rate-limit-guard-deny",
        event=reason,
        command=command,
    )
    return 2


def main() -> int:
    try:
        return _guard(raw_input=sys.stdin.read())
    except Exception as exc:  # noqa: BLE001 — sole fail-open hook boundary: silent pass-through, exit 0
        _log_event(
            level="warning",
            check_id="github-rate-limit-guard-crash",
            event="github_rate_limit_guard crashed; failing open",
            command=repr(exc),
        )
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
