# livespec-driver-claude — repo orientation

This repo is the **Claude Code Driver** for the livespec family: the
thin, agent-runtime-specific SKILL.md bindings through which a human
drives the livespec spec lifecycle interactively (per livespec
`SPECIFICATION/spec.md` §"Contract + reference implementations
architecture"). It is deliberately small. Everything substantive —
the harness-neutral driving prose, the reference spec-side CLIs, the
schemas, the templates — ships with livespec core
(`thewoolleyman/livespec`); this repo only binds that material to the
Claude Code runtime.

## Repo layout

| Path | Purpose |
|---|---|
| `.claude-plugin/plugin.json` | Plugin manifest. The plugin is NAMED `livespec` (not `livespec-driver-claude`) so the established `/livespec:*` command surface is preserved. |
| `.claude-plugin/marketplace.json` | Marketplace catalog (`livespec-driver-claude`) listing the single `livespec` Driver plugin. |
| `.claude-plugin/skills/<name>/SKILL.md` | The eight thin Claude Code bindings: seed, propose-change, critique, revise, doctor, prune-history, next, help. |
| `dev-tooling/` | Repo-local enforcement scripts (manifest/skill structural checks) + the family commit-refuse hook scripts. |
| `tests/e2e-cli/` | The CLI end-to-end harness consumer (relocated from livespec core with the bindings): mock-tier skill discovery + fail-closed fixture coverage gate, harness imported from livespec-dev-tooling. |
| `BACKLOG.md` | Initial backlog relocated from the livespec tenant (pending this repo's own work-item tenant). |
| `justfile`, `lefthook.yml`, `.mise.toml`, `.python-version`, `pyproject.toml` | Family-standard toolchain configuration, scaled to this repo's content. |

## The one design rule that matters here

Each SKILL.md is self-contained and follows the same three-part shape:

1. **Resolve `<core-root>`** — the livespec CORE plugin root. The
   Driver's own plugin root carries no `prose/` and no `scripts/`;
   the bindings resolve core via (a) the `LIVESPEC_CORE_PLUGIN_ROOT`
   env override, (b) `<project-root>/.claude-plugin/prose/` when the
   governed project IS the livespec core repo (dev mode /
   dogfooding), then (c) the installed `livespec@livespec` cache root
   from `~/.claude/plugins/installed_plugins.json`.
2. **Read the prose** — `<core-root>/prose/<name>.md` is the complete
   harness-neutral driving prose; the binding executes it.
3. **Dispatch the config-named CLI** — the governed project's
   `.livespec.jsonc` `spec_clis.<key>` argv (or core's reference
   default `python3 <core-root>/scripts/bin/<name>.py`), expanding
   the plugin-root substitution token in config values to
   `<core-root>` per livespec `contracts.md` §"Spec-side CLI
   contract".

Edit livespec core's `prose/<name>.md` for BEHAVIOR changes; edit the
SKILL.md files here only for Claude-runtime mechanics. Never vendor
prose or CLI logic into this repo.

Invocation-form rules for fenced commands in SKILL.md files (enforced
by `dev-tooling/check_plugin_structure.py`): use
`python3 "$LIVESPEC_CORE_ROOT/scripts/bin/<name>.py"`, never `uv run`,
never a literal `.claude-plugin/scripts` path, and never the Driver's
own plugin-root placeholder for core paths.

## Daily commands

- `just bootstrap` — one-time setup: sets `livespec.primaryPath`,
  installs the family commit-refuse hook at `.git/hooks/pre-commit` +
  `.git/hooks/pre-push` (direct commits at the primary checkout are
  refused — work in `git worktree add` secondaries), installs
  lefthook, installs/updates the required plugins.
- `just check` — full enforcement aggregate: plugin-structure checks,
  ruff lint/format over `tests/`, and the e2e-cli mock-tier harness.

ALL git operations via `mise exec -- git ...` so hooks fire;
`--no-verify` is banned. Commits use Conventional Commit subjects;
this repo has no product Python, so the red-green-replay ritual does
not apply (use `chore:`/`docs:`/`feat:` as appropriate).

## Relationship to the family

- `livespec` — core: contract, prose, reference CLIs, templates.
- `livespec-driver-claude` (this repo) — the Claude Code Driver.
  Future sibling Drivers (codex, opencode, pi) follow the same shape.
- `livespec-impl-*` — orchestrator plugins (work-item stores, gap and
  drift capture). The Driver has ZERO dependencies on them, and they
  have ZERO dependencies on the Driver (load-bearing invariant).
- `livespec-dev-tooling` — shared enforcement + testing library; this
  repo consumes its `testing.cli_e2e` harness via a pinned uv git
  dependency.
