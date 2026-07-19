#!/usr/bin/env python3
"""
tmux fleet-kill hazard classification for `tmux_fleet_guard`.

Claude Code agents share the user's default tmux socket namespace, so any
command that reaches `/tmp/tmux-<uid>/default` with a `kill-server` — or that
`pkill`s the tmux binary — destroys every unrelated agent session on the host.
This module owns the single question "must this command be denied?", so
`tmux_fleet_guard.py` keeps only the stdin/stdout boundary and the deny
emission.

Classification is TOKEN based and evasion-aware. Three whole families of bypass
exist against a naive "does the segment start with `tmux`?" test, and each is
closed here:

  - **Wrapper prefixes.** `exec` / `command` / `nice` / `timeout` / `env -i` /
    `sudo` / `mise exec --` and friends all re-exec the real command under a
    different leading token. Each is peeled and what remains is RE-EXAMINED, so
    the wrapper cannot launder the invocation. `env -i` in particular must
    never read as safe: clearing the environment also clears any TMUX_TMPDIR
    scoping, making it strictly MORE dangerous than the bare form.
  - **Socket-path spellings.** `/tmp/tmux-1000//default`,
    `/tmp/tmux-1000/../tmux-1000/default`, and `/tmp/tmux-1000/default/` all
    name the fleet socket. `-S` values are normalized LEXICALLY (never
    `realpath`, which would touch the filesystem from a hook) before judging.
  - **Nested payloads.** `sh -lc '<payload>'`, `bash -c "<payload>"`,
    `zsh -ic '<payload>'`, and `xargs tmux` move the hazard one level down.
    Each is unwrapped and re-classified to a bounded depth.

A `kill-server` reached through a command substitution the guard cannot
evaluate fails CLOSED. Only an EXPLICIT, non-default `-L`/`-S` scope permits a
`kill-server`, so `tmux -L <scratch> kill-server` and
`tmux -S /tmp/scratch-x/sock kill-server` stay allowed.

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
_DURATION = re.compile(r"^[0-9]+(?:\.[0-9]+)?[smhd]?$")
_ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_HEREDOC = re.compile(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?")
_KILL_SERVER = re.compile(r"\bkill-server\b")
_MAX_DEPTH = 4
_PROCESS_KILLERS = frozenset({"pkill", "killall"})
_RAW_SEGMENT_SPLIT = re.compile(r"&&|\|\||;|\||\n")
_SHELLS = frozenset({"bash", "sh", "zsh", "dash", "ksh"})
# `-c`, `-lc`, `-ic`, `-lic` — any clustered shell flag ending in `c`.
_SHELL_COMMAND_FLAG = re.compile(r"^-[a-zA-Z]*c$")
_SHELL_OPERATORS = frozenset({";", "&", "&&", "|", "||"})
_TMUX_PROCESS = re.compile(r"(?:^|[\s/])tmux(?:$|[\s/])")
# Wrappers that merely re-exec another command, mapped to the flags of THEIRS
# that consume a following argument.
_WRAPPER_FLAGS_WITH_ARG: dict[str, tuple[str, ...]] = {
    "command": (),
    "env": ("-u", "-C", "--unset", "--chdir"),
    "exec": ("-a",),
    "ionice": ("-c", "-n", "-p", "-P", "-u"),
    "nice": ("-n", "--adjustment"),
    "nohup": (),
    "setsid": (),
    "stdbuf": ("-i", "-o", "-e", "--input", "--output", "--error"),
    "sudo": ("-u", "-g", "-U", "-C", "-p", "-r", "-t", "-T", "--user", "--group", "--prompt"),
    "time": ("-o", "-f", "--output", "--format"),
    "timeout": ("-s", "-k", "--signal", "--kill-after"),
}
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


def _tokens_by_segment(*, command: str) -> list[list[str]]:
    """Tokenize once, then split shell command segments without re-lexing."""
    cleaned = _strip_heredoc_bodies(command=command).replace("\n", " ; ")
    lexer = shlex.shlex(cleaned, posix=True, punctuation_chars=";&|")
    lexer.whitespace_split = True
    segments: list[list[str]] = []
    current: list[str] = []
    for token in lexer:
        if token in _SHELL_OPERATORS:
            if current:
                segments.append(current)
                current = []
            continue
        current.append(token)
    if current:
        segments.append(current)
    return segments


def _skip_wrapper_arguments(*, tokens: list[str], start: int, base: str) -> int:
    """Index of the first token AFTER a wrapper's own flags and arguments."""
    flags_with_arg = _WRAPPER_FLAGS_WITH_ARG[base]
    index = start
    total = len(tokens)
    while index < total:
        token = tokens[index]
        if _ENV_ASSIGN.match(token):
            index += 1
            continue
        if token == "--":
            index += 1
            break
        if not token.startswith("-") or token == "-":
            break
        index += 2 if token in flags_with_arg else 1
    # `timeout` alone carries a bare positional DURATION before its command.
    if base == "timeout" and index < total and _DURATION.match(tokens[index]):
        index += 1
    return index


def _skip_mise_wrapper(*, tokens: list[str], start: int) -> int:
    """Index of the first token after a `mise exec [flags] [--]` prefix."""
    index = start + 1
    total = len(tokens)
    # `--` starts with `-`, so the terminator is consumed by this loop too.
    while index < total and (tokens[index] in ("exec", "x") or tokens[index].startswith("-")):
        index += 1
    return index


def _peel_wrappers(*, tokens: list[str]) -> list[str]:
    """Peel VAR=VAL assignments and re-exec wrappers, RE-EXAMINING each time."""
    index = 0
    total = len(tokens)
    changed = True
    while changed and index < total:
        changed = False
        while index < total and _ENV_ASSIGN.match(tokens[index]):
            index += 1
            changed = True
        if index >= total:
            break
        base = _basename(token=tokens[index])
        if base in _WRAPPER_FLAGS_WITH_ARG:
            index = _skip_wrapper_arguments(tokens=tokens, start=index + 1, base=base)
            changed = True
            continue
        if base == "mise":
            index = _skip_mise_wrapper(tokens=tokens, start=index)
            changed = True
    return tokens[index:]


def _shell_payload(*, tokens: list[str]) -> str | None:
    """The inline script of a `sh -c` / `bash -lc` / `zsh -ic` invocation."""
    if not tokens or _basename(token=tokens[0]) not in _SHELLS:
        return None
    for index in range(1, len(tokens)):
        token = tokens[index]
        if _SHELL_COMMAND_FLAG.match(token):
            return tokens[index + 1] if index + 1 < len(tokens) else None
        if token.startswith("-c") and len(token) > 2:
            return token[2:]
    return None


def _flag_values(*, tokens: list[str], flag: str) -> list[str]:
    """Every value given for `flag`, in `-S x`, `-Sx`, and `-S=x` spellings."""
    values: list[str] = []
    index = 0
    total = len(tokens)
    while index < total:
        token = tokens[index]
        if token == flag:
            values.append(tokens[index + 1] if index + 1 < total else "")
            index += 2
            continue
        if token.startswith(f"{flag}="):
            values.append(token[len(flag) + 1 :])
        elif token.startswith(flag):
            values.append(token[len(flag) :])
        index += 1
    return values


def _socket_is_hazardous(*, socket: str) -> bool:
    """True when a `-S` value names the fleet socket or its namespace dir."""
    if not socket:
        return True
    # LEXICAL normalization only: collapses `//` and resolves `.`/`..` without
    # touching the filesystem, which a PreToolUse hook must never do.
    normalized = os.path.normpath(socket)
    if _basename(token=normalized) == "default":
        return True
    if "fleet" in normalized:
        return True
    return bool(_DEFAULT_NAMESPACE.match(normalized))


def _label_is_hazardous(*, label: str) -> bool:
    if not label:
        return True
    return _basename(token=os.path.normpath(label)) == "default"


def _scope_permits_kill(*, tokens: list[str]) -> bool:
    """True ONLY when an explicit, non-default `-L`/`-S` scope is named."""
    arguments = tokens[1:]
    labels = _flag_values(tokens=arguments, flag="-L")
    sockets = _flag_values(tokens=arguments, flag="-S")
    if any(_label_is_hazardous(label=label) for label in labels):
        return False
    if any(_socket_is_hazardous(socket=socket) for socket in sockets):
        return False
    return bool(labels or sockets)


def _xargs_target(*, tokens: list[str]) -> list[str] | None:
    """The command `xargs` would run, or None when this is not an xargs call."""
    if not tokens or _basename(token=tokens[0]) != "xargs":
        return None
    index = 1
    total = len(tokens)
    while index < total:
        token = tokens[index]
        if token == "--":
            index += 1
            break
        if not token.startswith("-") or token == "-":
            break
        index += 2 if token in _XARGS_FLAGS_WITH_ARG else 1
    return tokens[index:]


def _segment_is_hazard(*, tokens: list[str], depth: int) -> bool:
    core = _peel_wrappers(tokens=tokens)
    if not core:
        return False
    inner = _shell_payload(tokens=core)
    if inner is not None:
        return classify(command=inner, depth=depth + 1)
    target = _xargs_target(tokens=core)
    if target is not None:
        # `echo kill-server | xargs tmux` never carries `kill-server` in the
        # xargs segment itself, so an xargs call whose TARGET is tmux is a
        # hazard on its own unless it names an explicit non-default scope.
        if target and _basename(token=target[0]) == "tmux":
            return not _scope_permits_kill(tokens=target)
        return _segment_is_hazard(tokens=target, depth=depth + 1)
    base = _basename(token=core[0])
    if base == "tmux" and "kill-server" in core[1:]:
        return not _scope_permits_kill(tokens=core)
    if base in _PROCESS_KILLERS:
        return any(_TMUX_PROCESS.search(token) for token in core[1:])
    return False


def classify(*, command: str, depth: int = 0) -> bool:
    """Return True when a command must be denied."""
    if depth > _MAX_DEPTH:
        return False
    # A `kill-server` reached through a command substitution cannot be resolved
    # without executing it, so it fails CLOSED rather than tokenizing to a
    # harmless-looking leading word like `$(echo`.
    for raw in _RAW_SEGMENT_SPLIT.split(_strip_heredoc_bodies(command=command)):
        if _COMMAND_SUBSTITUTION.search(raw) and _KILL_SERVER.search(raw):
            return True
    for segment in _tokens_by_segment(command=command):
        if _segment_is_hazard(tokens=segment, depth=depth):
            return True
    return False
