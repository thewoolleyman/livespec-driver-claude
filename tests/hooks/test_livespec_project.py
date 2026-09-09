"""Unit tests for `.claude-plugin/hooks/_livespec_project.py`.

The shared resolver both PreToolUse redirect hooks import to name the ACTIVE
impl-plugin's `/<plugin>:capture-work-item` operation. It is single-sourced
precisely so the namespace is read from `.livespec.jsonc` and never hardcoded
in a hook body, so what is pinned here is the rail: Success carries the
declared namespace, and every "this project is not identifiably governed"
answer — absent config, unparseable config, no `implementation.plugin` — comes
back as a Failure the calling hook collapses to a silent pass-through.
"""

from __future__ import annotations

import sys
from pathlib import Path

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HOOKS_DIR = _REPO_ROOT / ".claude-plugin" / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOKS_DIR))

import _livespec_project  # noqa: E402 — path-dependent hook import.

_PLUGIN = "livespec-orchestrator-beads-fabro"


def _write_config(*, root: Path, body: str) -> Path:
    _ = (root / ".livespec.jsonc").write_text(body, encoding="utf-8")
    return root


def test_resolves_the_declared_plugin_through_jsonc_comments(tmp_path: Path) -> None:
    project = _write_config(
        root=tmp_path,
        body=(
            "// Project-local livespec configuration.\n"
            "{\n"
            '  "spec_root": "SPECIFICATION", // trailing comment\n'
            "  /* block comment */\n"
            f'  "implementation": {{ "plugin": "  {_PLUGIN}  " }}\n'
            "}\n"
        ),
    )
    resolved = _livespec_project.resolve_impl_plugin(project_dir=str(project))
    assert resolved.unwrap() == _PLUGIN


def test_failure_when_config_is_absent(tmp_path: Path) -> None:
    resolved = _livespec_project.resolve_impl_plugin(project_dir=str(tmp_path / "missing"))
    assert isinstance(resolved.failure(), OSError)
    assert resolved.value_or(default=None) is None


def test_failure_when_config_is_unparseable(tmp_path: Path) -> None:
    project = _write_config(root=tmp_path, body="{ broken jsonc")
    resolved = _livespec_project.resolve_impl_plugin(project_dir=str(project))
    assert isinstance(resolved.failure(), ValueError)


def test_failure_for_every_shape_that_declares_no_plugin(tmp_path: Path) -> None:
    bodies = (
        "[]\n",  # config is not a mapping
        '{ "spec_root": "SPECIFICATION" }\n',  # no implementation block
        '{ "implementation": "beads" }\n',  # implementation is not a mapping
        '{ "implementation": { "plugin": 7 } }\n',  # plugin is not a string
        '{ "implementation": { "plugin": "   " } }\n',  # plugin is blank
    )
    for body in bodies:
        project = _write_config(root=tmp_path, body=body)
        resolved = _livespec_project.resolve_impl_plugin(project_dir=str(project))
        assert isinstance(resolved.failure(), LookupError), body


def test_strip_jsonc_comments_covers_string_escape_and_both_comment_forms() -> None:
    # Exercises every branch of the JSONC comment stripper: an in-string
    # escaped quote (`\"`) and escaped backslash, a closing then re-opening
    # string, a `//` line comment, and a `/* ... */` block comment.
    src = '{"a": "x\\"y\\\\z"} // line\n/* block\ncomment */ "tail"'
    stripped = _livespec_project._strip_jsonc_comments(text=src)
    assert '"x\\"y\\\\z"' in stripped
    assert "// line" not in stripped
    assert "block" not in stripped
    assert '"tail"' in stripped


def test_as_object_dict_narrows_only_mappings() -> None:
    assert _livespec_project._as_object_dict(value={"k": 1}) == {"k": 1}
    assert _livespec_project._as_object_dict(value=[1, 2]) is None
    assert _livespec_project._as_object_dict(value="str") is None
