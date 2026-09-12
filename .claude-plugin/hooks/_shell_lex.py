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
    character, splitting only on UNQUOTED `;` `&&` `||` `|` `&` and newline.
  - **Here-doc bodies are stdin data, not executed shell.** `cat > x <<'EOF'`
    followed by a body that mentions a hazard is a file write, not a hazard, so
    bodies are removed before tokenizing. They are also RETURNED, because a
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

__all__: list[str] = [
    "SHELLS",
    "basename",
    "shell_payload",
    "split_heredocs",
    "split_segments",
    "strip_heredoc_bodies",
    "ungrouped",
    "without_continuations",
]

SHELLS = frozenset({"bash", "sh", "zsh", "dash", "ksh"})
_GROUPING = "(){}"
_HEREDOC = re.compile(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?")
_LINE_CONTINUATION = re.compile(r"\\\n")
# `-c`, `-lc`, `-ic`, `-lic` — any clustered shell flag ending in `c`.
_SHELL_COMMAND_FLAG = re.compile(r"^-[a-zA-Z]*c$")


def basename(*, token: str) -> str:
    return token.rsplit("/", 1)[-1]


def ungrouped(*, token: str) -> str:
    """Strip shell grouping punctuation fused onto a token's edges."""
    return token.strip(_GROUPING)


def without_continuations(*, command: str) -> str:
    """Join backslash-newline continuations into one logical line."""
    return _LINE_CONTINUATION.sub(" ", command)


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
        match = _HEREDOC.search(line)
        if match is None:
            i += 1
            continue
        terminator = match.group(1)
        i += 1
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


def split_segments(*, command: str) -> list[str]:
    """Split into shell segments on unquoted `;` `&&` `||` `|` `&` and newline."""
    found: list[str] = []
    current: list[str] = []
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
        if command[index : index + 2] in ("&&", "||"):
            found.append("".join(current))
            current = []
            index += 2
            continue
        if char in ";|&\n":
            found.append("".join(current))
            current = []
            index += 1
            continue
        current.append(char)
        index += 1
    found.append("".join(current))
    return [segment.strip() for segment in found if segment.strip()]


def shell_payload(*, arguments: list[str]) -> str | None:
    """The inline script of a `sh -c` / `bash -lc` / `zsh -ic` invocation."""
    for index, token in enumerate(arguments):
        if _SHELL_COMMAND_FLAG.match(token):
            return arguments[index + 1] if index + 1 < len(arguments) else None
        if token.startswith("-c") and len(token) > 2:
            return token[2:]
    return None
