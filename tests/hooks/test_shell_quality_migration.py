"""Positive controls for the justfile shell-quality migration."""

from __future__ import annotations

import re
from pathlib import Path

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parents[2]
_INTERPOLATION_SENTINEL = "__JUST_INTERPOLATION__"


def _justfile_text() -> str:
    return (_REPO_ROOT / "justfile").read_text(encoding="utf-8")


def _flatten_body_line(*, parts: list[object]) -> tuple[str, bool]:
    text = ""
    interpolated = False
    for part in parts:
        if isinstance(part, str):
            text += part
        else:
            interpolated = True
            text += _INTERPOLATION_SENTINEL
    return text.strip(), interpolated


def test_migrated_recipes_are_thin_non_interpolated_delegators() -> None:
    justfile = _justfile_text()
    migrated_recipes = {
        "check-coverage",
        "check-doctor-static",
        "check-no-workflow-edits",
        "check-pre-commit",
        "check-pre-push",
        "check-red-green-replay",
        "ensure-codex-plugins",
        "lint-autofix-staged",
    }

    for recipe_name in migrated_recipes:
        match = re.search(
            rf"(?m)^(?:\[positional-arguments\]\n)?{re.escape(recipe_name)}[^\n]*:\n"
            r"(?P<body>(?:    .*\n)+)",
            justfile,
        )
        assert match is not None
        body = match.group("body")
        executable_lines = [
            line.strip()
            for line in body.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

        assert len(executable_lines) == 1
        assert "{{" not in body
        assert "}}" not in body


def test_documented_deviations_name_errexit() -> None:
    lines = _justfile_text().splitlines()
    documented_deviation_recipes = {
        "check",
        "check-per-file-coverage",
    }

    for recipe_name in documented_deviation_recipes:
        recipe_line = next(
            index for index, line in enumerate(lines) if line.startswith(f"{recipe_name}:")
        )
        assert "errexit" in lines[recipe_line - 1].lower()
        assert lines[recipe_line + 2].strip() == "set -uo pipefail"


def test_rejected_interpolation_control_is_detectable() -> None:
    line: list[object] = [
        "uv run python -m livespec_dev_tooling.checks.red_green_replay ",
        {"variable": "args"},
    ]

    rendered, interpolated = _flatten_body_line(parts=line)

    assert interpolated
    assert _INTERPOLATION_SENTINEL in rendered


def test_clean_surface_control_is_non_interpolated() -> None:
    rendered, interpolated = _flatten_body_line(
        parts=['uv run python -m livespec_dev_tooling.checks.red_green_replay "$@"']
    )

    assert rendered == 'uv run python -m livespec_dev_tooling.checks.red_green_replay "$@"'
    assert not interpolated
