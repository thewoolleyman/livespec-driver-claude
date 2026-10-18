"""Unit tests for `.claude-plugin/hooks/_memory_write.py`.

The classifier answers one question for the auto-memory redirect's Bash route:
does this command POSITIVELY write a file into an agent memory directory (the
Claude Code layout `~/.claude/projects/<slug>/memory/` or the Codex store
`~/.codex/memories/`)? The write forms below are the NON-EXHAUSTIVE minimum
livespec core `SPECIFICATION/contracts.md` (v225) lists; the passes are its
read and `rm` allowances plus the stated runtime-path limit.

Every command here is INERT DATA handed to a pure function; nothing executes it.
"""

from __future__ import annotations

import shlex
import sys
from pathlib import Path

import pytest

__all__: list[str] = []

_HOOKS_DIR = Path(__file__).resolve().parent.parent.parent / ".claude-plugin" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

from _memory_write import names_memory_dir, writes_memory  # noqa: E402 — path-dependent import.

_MEM = "~/.claude/projects/-data-projects-x/memory"
_CODEX = "~/.codex/memories"

_WRITES = [
    # Output redirection, every spelling.
    f"echo x > {_MEM}/a.md",
    f"echo x >> {_MEM}/a.md",
    f"echo x>{_MEM}/a.md",
    f"echo x 2>> {_MEM}/a.md",
    f"echo x &> {_MEM}/a.md",
    f"echo x >| {_MEM}/a.md",
    'echo x > "$HOME/.claude/projects/s/memory/a.md"',
    "echo x > ${CLAUDE_CONFIG_DIR}/projects/s/memory/a.md",
    f"echo x > {_CODEX}/a.md",
    "echo x > $CODEX_HOME/memories/a.md",
    f"cat <<'EOF' > {_MEM}/a.md\nbody\nEOF",
    f"cat > {_MEM}/a.md <<EOF\nbody\nEOF",
    # tee and the in-place editors.
    f"echo x | tee {_MEM}/a.md",
    f"tee -a {_CODEX}/a.md < /tmp/n",
    f"sed -i 's/a/b/' {_MEM}/a.md",
    f"sed -i.bak -e 's/a/b/' {_MEM}/a.md",
    f"sed --in-place 's/a/b/' {_MEM}/a.md",
    f"perl -pi -e 's/a/b/' {_MEM}/a.md",
    f"perl -i.bak -pe 's/a/b/' {_CODEX}/a.md",
    # Destination-writing file verbs.
    f"cp /tmp/a.md {_MEM}/",
    f"cp -r /tmp/notes {_MEM}",
    f"cp -t {_MEM} /tmp/a.md",
    f"cp --target-directory={_MEM} /tmp/a.md",
    f"cp -t{_MEM} /tmp/a.md",
    f"mv /tmp/a.md {_CODEX}/a.md 2>/dev/null",
    f"install -m 644 /tmp/a.md {_MEM}/a.md",
    f"ln -s /tmp/a.md {_MEM}/a.md",
    f"touch {_MEM}/a.md",
    f"truncate -s 0 {_MEM}/a.md",
    f"dd if=/tmp/a.md of={_MEM}/a.md",
    # Inline interpreter programs that name the path with a write-mode open.
    f"python3 -c \"open('{_MEM}/a.md', 'w').write('x')\"",
    f"python -c \"open('{_MEM}/a.md', mode='a')\"",
    f"python3.12 -c \"import pathlib; pathlib.Path('{_MEM}/a.md').write_text('x')\"",
    f"python3 - <<'EOF'\nopen('{_MEM}/a.md', 'a').write('x')\nEOF",
    f'perl -e \'open(my $f, ">>", "{_MEM}/a.md"); print $f 1\'',
    f"perl -e 'open(F, \">{_CODEX}/a.md\")'",
    f"node -e \"require('fs').appendFileSync('{_MEM}/a.md', 'x')\"",
    f"node --eval \"require('fs').createWriteStream('{_MEM}/a.md')\"",
    # Segments, wrappers and nesting.
    f"cd /tmp && echo x >> {_MEM}/a.md",
    f"false || echo x >> {_MEM}/a.md",
    f"ls; touch {_MEM}/a.md",
    f'for f in /tmp/*.md; do cp "$f" {_MEM}/; done',
    f"bash -c 'echo x >> {_MEM}/a.md'",
    f'sh -lc "tee {_MEM}/a.md < /tmp/n"',
    f"bash <<'EOF'\necho x >> {_MEM}/a.md\nEOF",
    f"env -u FOO BAR=1 tee {_MEM}/a.md",
    f"env -i sh -c 'touch {_MEM}/a.md'",
    f"sudo -u root tee {_MEM}/a.md",
    f"nohup cp /tmp/a.md {_MEM}/ &",
    f"X=1 touch {_MEM}/a.md",
    f"eval 'touch {_MEM}/a.md'",
    f"echo $(touch {_MEM}/a.md)",
]

_PASSES = [
    # Reads, and the rm that discharges a migrated note.
    f"cat {_MEM}/a.md",
    f"grep -rn x {_MEM}/",
    f"ls -la {_MEM}",
    f"head -5 {_MEM}/a.md",
    f"find {_MEM} -name '*.md'",
    f"rm {_MEM}/a.md",
    f"rm -f {_CODEX}/a.md",
    f"cat {_MEM}/a.md > /tmp/copy.md",
    f"cp {_MEM}/a.md /tmp/",
    f"ln -s {_MEM}/a.md /tmp/link",
    f"sed -n 1p {_MEM}/a.md",
    f"perl -ne 'print' {_MEM}/a.md",
    f"python3 -c \"print(open('{_MEM}/a.md').read())\"",
    f"python3 {_MEM}/script.py",
    f"node -e \"require('fs').readFileSync('{_MEM}/a.md')\"",
    f"echo 'cp x {_MEM}/'",
    f"echo x >> /tmp/log; cat {_MEM}/a.md",
    f"cat <<'EOF' > /tmp/x\necho y >> {_MEM}/a.md\nEOF",
    # Not a memory directory at all.
    "echo x >> docs/memory/a.md",
    "echo x >> /tmp/memory-notes.md",
    "touch /tmp/memories/a.md",
    # Stated limits and fail-open shapes.
    f"cd {_MEM} && echo x >> a.md",
    'cp /tmp/a.md "$DEST"',
    f"echo 'unterminated > {_MEM}/a.md",
    f"env -u {_MEM}",
    f"MEMORY={_MEM}/a.md",
    "cp",
    "mv -- ",
    f"echo {_MEM} >",
    f"python3 -c  # {_MEM}",
    "perl -e 'my $memory = 1'",
    f"bash -c  # {_MEM}",
    "git status",
    f'bash -c "bash -c \'bash -c \\"bash -c bash\\"\'" {_MEM}',
]


@pytest.mark.parametrize("command", _WRITES)
def test_identifies_a_write_into_a_memory_directory(command: str) -> None:
    assert writes_memory(command=command) is True


@pytest.mark.parametrize("command", _PASSES)
def test_lets_a_read_rm_or_unidentifiable_command_through(command: str) -> None:
    assert writes_memory(command=command) is False


def test_depth_budget_exhaustion_is_not_a_positive_identification() -> None:
    nested = f"touch {_MEM}/a.md"
    assert writes_memory(command=nested) is True
    for _ in range(8):
        nested = f"bash -c {shlex.quote(nested)}"
    assert writes_memory(command=nested) is False


def test_names_memory_dir_matches_both_layouts_only() -> None:
    assert names_memory_dir(text=f"{_MEM}/a.md")
    assert names_memory_dir(text=f"{_MEM}")
    assert names_memory_dir(text=f"{_CODEX}/sub/a.md")
    assert not names_memory_dir(text="~/.claude/projects/x/memoryish/a.md")
    assert not names_memory_dir(text="~/.codex/memories-old/a.md")
    assert not names_memory_dir(text="/srv/memory/a.md")
