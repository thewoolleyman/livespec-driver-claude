"""check_plugin_structure — structural gate for the Driver plugin bundle.

Stdlib-only (runs under bare python3; no venv required). Asserts:

1. `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`
   parse as JSON.
2. Plugin name is `livespec` (the `/livespec:*` surface contract);
   marketplace name is `livespec-driver-claude`; the single
   marketplace plugin entry's `source` is `./.claude-plugin` and its
   `description` duplicates `plugin.json`'s verbatim (plugin.json is
   the source of truth).
3. All eight operations ship a SKILL.md whose frontmatter `name`
   matches its directory, and no extra skill directories exist.
4. Fenced-invocation rules inside every SKILL.md: any fenced line
   invoking a `bin/<name>.py` wrapper MUST use the
   `$LIVESPEC_CORE_ROOT` resolution variable, MUST NOT use `uv run`,
   MUST NOT use a literal `.claude-plugin/scripts` path, and MUST NOT
   use the Driver's own plugin-root placeholder (`CLAUDE_PLUGIN_ROOT`
   would resolve to the Driver root, which carries no scripts).

Exit 0 when every assertion holds; exit 1 with one line per violation
on stderr otherwise.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

__all__: list[str] = []

_REPO_ROOT = Path(__file__).resolve().parent.parent
_PLUGIN_DIR = _REPO_ROOT / ".claude-plugin"
_SKILLS_DIR = _PLUGIN_DIR / "skills"

_EXPECTED_SKILLS = frozenset(
    {
        "seed",
        "propose-change",
        "critique",
        "revise",
        "doctor",
        "prune-history",
        "next",
        "help",
    }
)

_WRAPPER_INVOCATION_RE = re.compile(r"bin/[a-z_]+\.py\b")
_FRONTMATTER_NAME_RE = re.compile(r"^name:\s*(\S+)\s*$", re.MULTILINE)
# Assembled from parts so this checker file itself never contains the
# literal placeholder token it bans (the Claude Code loader textually
# substitutes the token anywhere it appears in plugin-shipped files).
_DRIVER_ROOT_TOKEN = "CLAUDE_PLUGIN" + "_ROOT"


def _manifest_violations() -> list[str]:
    out: list[str] = []
    try:
        plugin = json.loads((_PLUGIN_DIR / "plugin.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"plugin.json unreadable/invalid: {exc}"]
    try:
        marketplace = json.loads((_PLUGIN_DIR / "marketplace.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return [f"marketplace.json unreadable/invalid: {exc}"]
    if plugin.get("name") != "livespec":
        out.append(f"plugin.json name MUST be 'livespec'; got {plugin.get('name')!r}")
    if marketplace.get("name") != "livespec-driver-claude":
        out.append(
            "marketplace.json name MUST be 'livespec-driver-claude'; "
            f"got {marketplace.get('name')!r}"
        )
    entries = marketplace.get("plugins", [])
    if len(entries) != 1:
        out.append(f"marketplace.json MUST list exactly one plugin; got {len(entries)}")
        return out
    entry = entries[0]
    if entry.get("name") != "livespec":
        out.append(f"marketplace plugin entry name MUST be 'livespec'; got {entry.get('name')!r}")
    if entry.get("source") != "./.claude-plugin":
        out.append(
            f"marketplace plugin entry source MUST be './.claude-plugin'; "
            f"got {entry.get('source')!r}"
        )
    if entry.get("description") != plugin.get("description"):
        out.append(
            "marketplace plugin description MUST duplicate plugin.json's verbatim "
            "(plugin.json is the source of truth)"
        )
    return out


def _skill_set_violations() -> list[str]:
    out: list[str] = []
    found = {p.name for p in _SKILLS_DIR.iterdir() if p.is_dir()}
    for missing in sorted(_EXPECTED_SKILLS - found):
        out.append(f"missing skill directory: skills/{missing}/")
    for extra in sorted(found - _EXPECTED_SKILLS):
        out.append(f"unexpected skill directory: skills/{extra}/")
    for name in sorted(_EXPECTED_SKILLS & found):
        skill_md = _SKILLS_DIR / name / "SKILL.md"
        if not skill_md.is_file():
            out.append(f"missing skills/{name}/SKILL.md")
            continue
        match = _FRONTMATTER_NAME_RE.search(skill_md.read_text(encoding="utf-8"))
        if match is None or match.group(1) != name:
            got = None if match is None else match.group(1)
            out.append(f"skills/{name}/SKILL.md frontmatter name MUST be {name!r}; got {got!r}")
    return out


def _fenced_invocation_violations(*, skill_md: Path) -> list[str]:
    out: list[str] = []
    in_fence = False
    for line_no, raw in enumerate(skill_md.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence or _WRAPPER_INVOCATION_RE.search(stripped) is None:
            continue
        where = f"{skill_md.relative_to(_REPO_ROOT)}:{line_no}"
        if "uv run" in stripped:
            out.append(f"{where}: fenced wrapper invocation uses 'uv run'")
        if ".claude-plugin/scripts" in stripped:
            out.append(f"{where}: fenced wrapper invocation uses a literal .claude-plugin path")
        if _DRIVER_ROOT_TOKEN in stripped:
            out.append(
                f"{where}: fenced wrapper invocation uses the Driver's own plugin-root "
                "placeholder (resolves to the Driver root, which has no scripts/)"
            )
        if "$LIVESPEC_CORE_ROOT" not in stripped:
            out.append(f"{where}: fenced wrapper invocation MUST use $LIVESPEC_CORE_ROOT")
    return out


def main() -> int:
    violations = _manifest_violations()
    violations.extend(_skill_set_violations())
    for skill_md in sorted(_SKILLS_DIR.glob("*/SKILL.md")):
        violations.extend(_fenced_invocation_violations(skill_md=skill_md))
    for violation in violations:
        sys.stderr.write(f"check_plugin_structure: {violation}\n")
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main())
