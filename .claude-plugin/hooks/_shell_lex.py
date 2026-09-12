#!/usr/bin/env python3
"""
Shell-lexing helpers shared by the Bash-inspecting PreToolUse classifiers.

`_tmux_hazard` (tmux fleet kills) and `_host_mutation` (hand mutation of
fleet-managed hosts) answer different questions over the same raw material: a
Bash command string the agent is about to run. Both need the same lexical
preparation before any judgement is possible, and that preparation is where
the false-positive traps live, so it is written ONCE here:

  - **Quote-aware segment splitting.** `echo 'first; tmux kill-server'` must
    arrive as ONE segment whose second token is data, never as a segment that
    begins `tmux kill-server`. A regex split on `;` cuts inside quotes; the
    scanner here tracks quote state and backslash escapes character by
    character, splitting only on UNQUOTED `;` `&&` `||` `|` `&` and newline,
    and reports WHICH separator preceded each segment so a classifier can
    tell `echo x | sftp host` (a pipe feeding stdin) from `echo x; sftp host`.
  - **Comments are stripped the way bash strips them.** A `#` starts a comment
    only at the START of a word, outside quotes. `shlex`'s own `comments=True`
    cuts `a#b` to `a`, which bash never does, so a guard using it would drop
    real executed words (`env x#y=1 ssh …` runs ssh).
  - **Here-doc bodies are stdin data, not executed shell.** `cat > x <<'EOF'`
    followed by a body that mentions a hazard is a file write, not a hazard, so
    bodies are removed before tokenizing. The `<<` operator is recognised only
    OUTSIDE quotes (`echo '<<EOF'` is a string, not a here-doc that would
    swallow the next line), `<<<` is a here-string and not a here-doc, and a
    terminator may carry a dash (`END-X`). Bodies are also RETURNED, because a
    classifier may need to read a body as the payload of the command it feeds
    (`ssh host bash -s <<'EOF'` runs the body on the remote host).
  - **Nested interpreter payloads.** `sh -lc '<payload>'`, `bash -ctmux …`
    hand a whole script to another shell as one token; `shell_payload` finds
    it so the caller can re-classify one level down.
  - **Grouping punctuation.** `(tmux kill-server)` and `{ ssh host x; }` fuse
    a paren or brace onto the adjacent token; `ungrouped` strips them so the
    basename test sees the real command word.

Self-contained by contract: the plugin installer ships this file under bare
system `python3` with no virtualenv and no third-party packages, so every
import here is standard library.
"""

from __future__ import annotations

import re
import shlex

__all__: list[str] = [
    "SHELLS",
    "SHELL_KEYWORDS_DATA",
    "SHELL_KEYWORDS_PASS",
    "basename",
    "first_command_index",
    "heredoc_count",
    "operands",
    "shell_payload",
    "split_heredocs",
    "split_segments",
    "split_segments_with_separators",
    "strip_heredoc_bodies",
    "substitutions",
    "tokens_or_none",
    "ungrouped",
    "without_continuations",
]

SHELLS = frozenset({"bash", "sh", "zsh", "dash", "ksh"})
# `for x in a b c`, `select`, `case x in` name WORDS, not commands: the whole
# segment is data. `if`, `do`, `then`, … merely precede a command.
SHELL_KEYWORDS_DATA = frozenset({"for", "select", "case"})
SHELL_KEYWORDS_PASS = frozenset(
    "if then else elif fi while until do done esac ! time coproc".split()
)
_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_GROUPING = "(){}"
_XARGS_PLACEHOLDER = "{}"
_COMMENT_PRECEDERS = " \t\n;|&({"
_LINE_CONTINUATION = re.compile(r"\\\n")
# `-c`, `-lc`, `-ic`, `-lic` — any clustered shell flag ending in `c`.
_SHELL_COMMAND_FLAG = re.compile(r"^-[a-zA-Z]*c$")
_TERMINATOR = re.compile(r"-?\s*['\"]?([\w-]+)['\"]?")


def basename(*, token: str) -> str:
    return token.rsplit("/", 1)[-1]


def ungrouped(*, token: str) -> str:
    """Strip shell grouping punctuation fused onto a token's edges; `{}` (xargs) stays."""
    return token if token == _XARGS_PLACEHOLDER else token.strip(_GROUPING)


def without_continuations(*, command: str) -> str:
    """Join backslash-newline continuations into one logical line."""
    return _LINE_CONTINUATION.sub(" ", command)


def tokens_or_none(*, seg: str) -> list[str] | None:
    """The segment's words, grouping punctuation stripped, or None if unlexable.

    A token that IS grouping punctuation (`{`, `}`, `(`, `)`) is dropped — it
    was never a word. An empty token from `''` is kept: it is a word, and an
    empty command head is one the guard cannot resolve.
    """
    try:
        raw = shlex.split(seg, posix=True)
    except ValueError:
        return None
    return [
        ungrouped(token=token)
        for token in raw
        if not token or token == _XARGS_PLACEHOLDER or token.strip(_GROUPING)
    ]


def heredoc_count(*, tokens: list[str]) -> int:
    """How many here-doc bodies this segment consumes (`<<EOF`, not `<<<`)."""
    return sum(1 for t in tokens if t.startswith("<<") and not t.startswith("<<<"))


def substitutions(*, text: str) -> list[str]:
    """The command text inside every `$(…)` and backtick pair, outside single quotes.

    A substitution is EXECUTED shell, so a classifier must read it as a
    command in its own right — `$(ssh host 'sudo x')` hidden in an `echo` or a
    playbook extra-var is a mutation; `$(date +%s)` in a file name is not.
    """
    found: list[str] = []
    quote = ""
    index = 0
    total = len(text)
    while index < total:
        char = text[index]
        if quote == "'":
            quote = "" if char == "'" else quote
            index += 1
            continue
        if char == "\\":
            index += 2
            continue
        if char in "'\"":
            if not quote:
                quote = char
            elif quote == char:
                quote = ""
            index += 1
            continue
        if text.startswith("$(", index):
            depth = 1
            end = index + 2
            while end < total and depth:
                depth += (text[end] == "(") - (text[end] == ")")
                end += 1
            found.append(text[index + 2 : end - 1 if depth == 0 else end])
            index = end
            continue
        if char == "`":
            end = text.find("`", index + 1)
            found.append(text[index + 1 : end if end >= 0 else total])
            index = (end if end >= 0 else total) + 1
            continue
        index += 1
    return [s for s in found if s.strip()]


def _heredoc_terminator(*, line: str) -> str | None:
    """The terminator word of an UNQUOTED `<<` on this line, else None."""
    quote = ""
    index = 0
    total = len(line)
    while index < total:
        char = line[index]
        if quote:
            if char == quote:
                quote = ""
            index += 1
            continue
        if char in "'\"":
            quote = char
            index += 1
            continue
        if char == "\\":
            index += 2
            continue
        if line.startswith("<<<", index):
            index += 3
            continue
        if line.startswith("<<", index):
            match = _TERMINATOR.match(line, index + 2)
            if match is not None:
                return match.group(1)
        index += 1
    return None


def split_heredocs(*, command: str) -> tuple[str, list[str]]:
    """Separate here-doc BODIES from the shell that feeds them.

    Returns the command with every body removed, plus the bodies themselves in
    order. An unterminated body runs to the end of the command.
    """
    lines = command.split("\n")
    kept: list[str] = []
    bodies: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        kept.append(line)
        terminator = _heredoc_terminator(line=line)
        i += 1
        if terminator is None:
            continue
        body: list[str] = []
        while i < n and lines[i].strip() != terminator:
            body.append(lines[i])
            i += 1
        bodies.append("\n".join(body))
        if i < n:
            i += 1
    return "\n".join(kept), bodies


def strip_heredoc_bodies(*, command: str) -> str:
    """Remove here-doc BODIES because they are stdin data, not executed shell."""
    return split_heredocs(command=command)[0]


def _starts_comment(*, command: str, index: int) -> bool:
    """A `#` at a word start (bash); `${#x}` and `$#` are expansions, not comments."""
    if index == 0:
        return True
    previous = command[index - 1]
    if previous not in _COMMENT_PRECEDERS:
        return False
    return not (previous == "{" and index >= 2 and command[index - 2] == "$")


def split_segments_with_separators(*, command: str) -> list[tuple[str, str]]:
    """Segments paired with the unquoted separator that PRECEDED each one.

    The first segment's separator is the empty string; the others carry one of
    `;`, `&&`, `||`, `|`, `&`, or a newline. Word-initial `#` comments are
    dropped as bash drops them.
    """
    found: list[tuple[str, str]] = []
    current: list[str] = []
    separator = ""
    quote = ""
    index = 0
    total = len(command)
    while index < total:
        char = command[index]
        if quote:
            current.append(char)
            if char == quote:
                quote = ""
            index += 1
            continue
        if char in "'\"":
            quote = char
            current.append(char)
            index += 1
            continue
        if char == "\\" and index + 1 < total:
            current.append(char)
            current.append(command[index + 1])
            index += 2
            continue
        if char == "#" and _starts_comment(command=command, index=index):
            while index < total and command[index] != "\n":
                index += 1
            continue
        pair = command[index : index + 2]
        if pair in ("&&", "||"):
            found.append((separator, "".join(current)))
            current = []
            separator = pair
            index += 2
            continue
        if char in ";|&\n" and not (char == "|" and current and current[-1] == ">"):
            found.append((separator, "".join(current)))
            current = []
            separator = char
            index += 1
            continue
        current.append(char)
        index += 1
    found.append((separator, "".join(current)))
    return [(sep, seg.strip()) for sep, seg in found if seg.strip()]


def split_segments(*, command: str) -> list[str]:
    """Split into shell segments on unquoted `;` `&&` `||` `|` `&` and newline."""
    return [seg for _, seg in split_segments_with_separators(command=command)]


def shell_payload(*, arguments: list[str]) -> str | None:
    """The inline script of a `sh -c` / `bash -lc` / `zsh -ic` invocation."""
    for index, token in enumerate(arguments):
        if _SHELL_COMMAND_FLAG.match(token):
            return arguments[index + 1] if index + 1 < len(arguments) else None
        if token.startswith("-c") and len(token) > 2:
            return token[2:]
    return None


def first_command_index(*, tokens: list[str]) -> int | None:
    """The index of the first token that is not a leading `NAME=value` assignment."""
    return next((i for i, token in enumerate(tokens) if not _ASSIGNMENT.match(token)), None)


def operands(*, arguments: list[str]) -> list[str]:
    return [argument for argument in arguments if not argument.startswith("-")]
