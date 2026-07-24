#!/usr/bin/env python3
"""
tmux fleet-kill hazard classification for `tmux_fleet_guard`.

Claude Code agents share the user's default tmux socket namespace, so any
command that reaches `/tmp/tmux-<uid>/default` with a `kill-server` — or that
`pkill`s the tmux binary — destroys every unrelated agent session on the host.
This module owns the single question "must this command be denied?", so
`tmux_fleet_guard.py` keeps only the stdin/stdout boundary and the deny
emission.

THE DESIGN RULE: scan EVERY token position for a command head, never just
position 0.

An earlier guard peeled a closed allowlist of wrapper prefixes (`env`, `sudo`,
`nice`, `timeout`, …) and then inspected `tokens[0]`. That shape is unfixable by
extension: anything that displaces `tmux` off position 0 passes, and the set of
things that can do so is open-ended — every prefix nobody thought of is a live
bypass. Scanning all positions inverts the burden. A wrapper no longer has to be
KNOWN to be defeated; it merely has to leave a recognizable `tmux` / `pkill` /
`killall` / `kill` token somewhere in the segment, which every wrapper does,
because leaving that token is what a wrapper is for.

Quoting is what keeps this from over-blocking. `echo 'tmux kill-server'` lexes
to ONE token whose value is the whole sentence, so no token's basename is
`tmux`; the same holds for a `git commit -m` message, a `grep` pattern, a
here-doc body, and a `python3 -c` string. The accepted cost is that an UNQUOTED
mention (`echo tmux kill-server`) denies — a bias toward the deny direction,
since the opposite bias is what killed the fleet.

Four further evasion routes are closed here:

  - **Grouping punctuation.** `(tmux kill-server)` and `{ tmux kill-server; }`
    fuse the paren or brace onto the adjacent token, so `(){}` is stripped from
    each token's edges before the basename test.
  - **Nested payloads.** `sh -lc '<payload>'`, `bash -ctmux' kill-server'`,
    `eval '<payload>'`, and `xargs tmux` move the hazard one level down. Each is
    unwrapped and re-classified, and exceeding the depth budget fails CLOSED —
    nothing legitimate nests five `bash -c` deep, so exhausting the budget is
    evidence of evasion rather than a reason to allow.
  - **Socket-path spellings.** `/tmp/tmux-1000//default`,
    `/tmp/tmux-1000/../tmux-1000/default`, `/tmp/./tmux-1000/./default`, and
    `/tmp/tmux-1000/default/` all name the fleet socket. `-S` values are
    normalized LEXICALLY (never `realpath`, which would touch the filesystem
    from a hook) before being judged.
  - **Scope-flag precedence.** tmux(1): "If -S is specified, the default socket
    directory is not used and any -L flag is ignored." So `-S` beats `-L` NO
    MATTER the order, and among repeats the last of a kind wins. A guard that
    stopped at the first scope flag it saw allowed
    `tmux -L scratch -S /tmp/tmux-1000/default kill-server`.

A `kill-server` reached through a command substitution the guard cannot
evaluate fails CLOSED, as does a hazard-shaped segment that will not tokenize.

Self-contained by contract: the plugin installer ships this file under bare
system `python3` with no virtualenv and no third-party packages, so every
import here is standard library.
"""

from __future__ import annotations

import os
import re
import shlex

__all__: list[str] = ["classify"]

_COMMAND_SUBSTITUTION = re.compile(r"\$\(|`")
_DEFAULT_NAMESPACE = re.compile(r"^/tmp/tmux-\d+(?:/.*)?$")
_GROUPING = "(){}"
_HEREDOC = re.compile(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?")
_KILL_SERVER = re.compile(r"\bkill-server\b")
_LINE_CONTINUATION = re.compile(r"\\\n")
_MAX_DEPTH = 4
_PROCESS_KILLERS = frozenset({"kill", "killall", "pkill"})
_PROCESS_KILLER_WORD = re.compile(r"\b(?:pkill|killall)\b")
_SHELLS = frozenset({"bash", "sh", "zsh", "dash", "ksh"})
# `-c`, `-lc`, `-ic`, `-lic` — any clustered shell flag ending in `c`.
_SHELL_COMMAND_FLAG = re.compile(r"^-[a-zA-Z]*c$")
_TMUX_WORD = re.compile(r"\btmux\b")
_XARGS_FLAGS_WITH_ARG = (
    "-a",
    "-d",
    "-E",
    "-I",
    "-i",
    "-L",
    "-l",
    "-n",
    "-P",
    "-s",
    "--arg-file",
    "--delimiter",
    "--eof",
    "--max-args",
    "--max-chars",
    "--max-lines",
    "--max-procs",
    "--replace",
)


def _basename(*, token: str) -> str:
    return token.rsplit("/", 1)[-1]


def _ungrouped(*, token: str) -> str:
    """Strip shell grouping punctuation fused onto a token's edges."""
    return token.strip(_GROUPING)


def _strip_heredoc_bodies(*, command: str) -> str:
    """Remove here-doc BODIES because they are stdin data, not executed shell."""
    lines = command.split("\n")
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        out.append(line)
        match = _HEREDOC.search(line)
        if match is None:
            i += 1
            continue
        terminator = match.group(1)
        i += 1
        while i < n and lines[i].strip() != terminator:
            i += 1
        if i < n:
            i += 1
    return "\n".join(out)


def _split_segments(*, command: str) -> list[str]:
    """Split into shell segments on unquoted `;` `&&` `||` `|` `&` and newline.

    QUOTING-AWARE by construction. A regex split cuts inside quoted strings, so
    `echo 'first; tmux kill-server'` would arrive as a segment beginning
    `tmux kill-server` — a false positive on text that is pure DATA.
    """
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


def _shell_payload(*, arguments: list[str]) -> str | None:
    """The inline script of a `sh -c` / `bash -lc` / `zsh -ic` invocation."""
    for index, token in enumerate(arguments):
        if _SHELL_COMMAND_FLAG.match(token):
            return arguments[index + 1] if index + 1 < len(arguments) else None
        if token.startswith("-c") and len(token) > 2:
            return token[2:]
    return None


def _socket_is_hazardous(*, socket: str) -> bool:
    """True when a `-S` value names the fleet socket or its namespace dir."""
    if not socket:
        return True
    if "/" not in socket:
        # A bare name resolves against the caller's cwd, which a hook cannot
        # know, so it can never be SHOWN to sit off the default namespace.
        return True
    # LEXICAL normalization only: collapses `//` and resolves `.`/`..` without
    # touching the filesystem, which a PreToolUse hook must never do.
    normalized = os.path.normpath(socket)
    if _basename(token=normalized) == "default":
        return True
    return bool(_DEFAULT_NAMESPACE.match(normalized))


def _label_is_hazardous(*, label: str) -> bool:
    if not label:
        return True
    return _basename(token=os.path.normpath(label)) == "default"


def _flag_values(*, arguments: list[str], flag: str) -> list[str]:
    """Every value given for `flag`, in `-S x`, `-Sx`, and `-S=x` spellings."""
    values: list[str] = []
    index = 0
    total = len(arguments)
    while index < total:
        token = arguments[index]
        if token == flag:
            values.append(arguments[index + 1] if index + 1 < total else "")
            index += 2
            continue
        if token.startswith(f"{flag}="):
            values.append(token[len(flag) + 1 :])
        elif token.startswith(flag):
            values.append(token[len(flag) :])
        index += 1
    return values


def _scope_permits_kill(*, arguments: list[str]) -> bool:
    """True ONLY when the EFFECTIVE tmux scope is explicit and non-default."""
    sockets = _flag_values(arguments=arguments, flag="-S")
    if sockets:
        return not _socket_is_hazardous(socket=sockets[-1])
    labels = _flag_values(arguments=arguments, flag="-L")
    if labels:
        return not _label_is_hazardous(label=labels[-1])
    return False


def _xargs_target(*, arguments: list[str]) -> list[str]:
    """The command `xargs` would run, with xargs' own flags consumed."""
    index = 0
    total = len(arguments)
    while index < total:
        token = arguments[index]
        if token == "--":
            index += 1
            break
        if not token.startswith("-") or token == "-":
            break
        index += 2 if token in _XARGS_FLAGS_WITH_ARG else 1
    return arguments[index:]


def _targets_tmux_process(*, arguments: list[str]) -> bool:
    """True when any argument mentions tmux at all.

    Deliberately a SUBSTRING test over every token, flags included. A word-
    boundary test that skipped flag-shaped arguments allowed `pkill -f '^tmux'`,
    `pkill -ftmux`, and `pkill -f 'tmux: server'` — every one of which matches
    the live server.
    """
    return any("tmux" in argument for argument in arguments)


def _nested_hazard(*, command: str, arguments: list[str], depth: int) -> bool:
    """Recurse into a payload this token hands to another interpreter."""
    if command in _SHELLS:
        payload = _shell_payload(arguments=arguments)
        if payload is not None:
            return classify(command=payload, depth=depth + 1)
    if command == "eval" and arguments:
        return classify(command=" ".join(arguments), depth=depth + 1)
    return False


def _direct_hazard(*, command: str, arguments: list[str]) -> bool:
    """Is THIS token a tmux/process-killer command head reaching the hazard?"""
    if command == "xargs":
        target = _xargs_target(arguments=arguments)
        if target and _basename(token=target[0]) == "tmux":
            return not _scope_permits_kill(arguments=target[1:])
    if command == "tmux" and "kill-server" in arguments:
        return not _scope_permits_kill(arguments=arguments)
    return command in _PROCESS_KILLERS and _targets_tmux_process(arguments=arguments)


def _tokens_are_hazard(*, tokens: list[str], depth: int) -> bool:
    """Scan EVERY position for a hazardous command head."""
    for index, token in enumerate(tokens):
        command = _basename(token=token)
        arguments = tokens[index + 1 :]
        if _nested_hazard(command=command, arguments=arguments, depth=depth):
            return True
        if _direct_hazard(command=command, arguments=arguments):
            return True
    return False


def _looks_like_tmux_kill_hazard(*, seg: str) -> bool:
    return bool(
        _TMUX_WORD.search(seg) and (_KILL_SERVER.search(seg) or _PROCESS_KILLER_WORD.search(seg))
    )


def _segment_is_hazard(*, seg: str, depth: int) -> bool:
    # A `kill-server` reached through a command substitution cannot be resolved
    # without executing it, so it fails CLOSED rather than tokenizing to a
    # harmless-looking leading word like `$(echo`.
    if _COMMAND_SUBSTITUTION.search(seg) and _KILL_SERVER.search(seg):
        return True
    try:
        tokens = shlex.split(seg, posix=True)
    except ValueError:
        return _looks_like_tmux_kill_hazard(seg=seg)
    return _tokens_are_hazard(tokens=[_ungrouped(token=token) for token in tokens], depth=depth)


def classify(*, command: str, depth: int = 0) -> bool:
    """Return True when a command must be denied."""
    if depth > _MAX_DEPTH:
        # Out of budget with content still unexamined. Nothing legitimate nests
        # this deep, so exhaustion is evidence of evasion: fail CLOSED.
        return True
    cleaned = _LINE_CONTINUATION.sub(" ", _strip_heredoc_bodies(command=command))
    return any(_segment_is_hazard(seg=seg, depth=depth) for seg in _split_segments(command=cleaned))
