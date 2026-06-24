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
| `.claude-plugin/hooks/` | Plugin-shipped Claude Code hooks: `hooks.json` declares the events; each hook is a fail-open POSIX shell script resolved via the Driver's plugin root (this IS Driver-owned runtime surface, unlike prose/CLIs). |
| `dev-tooling/` | Repo-local enforcement scripts (manifest/skill structural checks) + the family commit-refuse hook scripts. |
| `tests/e2e-cli/` | The CLI end-to-end harness consumer (relocated from livespec core with the bindings): mock-tier skill discovery + fail-closed fixture coverage gate, harness imported from livespec-dev-tooling. |
| `tests/hooks/` | Unit tests for the plugin-shipped hook scripts (subprocess invocation, mocked `CLAUDE_PROJECT_DIR`, tmp_path fixture projects). |
| `SPECIFICATION/` | The live, dogfooded spec for the Driver seam (binding shape, core-root resolution, manifest/marketplace invariants, hook-bundle wiring). Defers to livespec core by citation; evolves via `/livespec:*`. |
| `.livespec.jsonc` | Project-local livespec config: `template`, `spec_root`, active impl-plugin, and the beads tenant connection block (mirrors `.beads/config.yaml`). |
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

## Codex dogfooding (OpenAI Codex CLI/TUI)

The same family spec-side and orchestrator surfaces can be dogfooded from
OpenAI Codex CLI/TUI. Unlike the Claude path (plugins enabled PER PROJECT via a
committed `.claude/settings.json`), Codex plugin enablement is **HOST-WIDE**:
each registration persists in `~/.codex/config.toml` and applies to every
project on the host. Codex offers no project-scoped plugin enablement, so there
is no committed-settings analogue for the Codex path.

Install the three family plugins host-wide: livespec CORE (the artifact carrier
that ships the spec-side prose and wrappers), the `livespec-driver-codex` Codex
Driver (which supplies the `/livespec:*` operation surface over core's prose),
and the selected orchestrator plugin:

```bash
# livespec CORE (spec-side prose + wrappers; no skills of its own):
codex plugin marketplace add thewoolleyman/livespec
codex plugin add livespec@livespec

# The Codex Driver (supplies the spec-side /livespec:* operation surface):
codex plugin marketplace add thewoolleyman/livespec-driver-codex
codex plugin add livespec@livespec-driver-codex

# The selected orchestrator plugin (ships its own Codex skills):
codex plugin marketplace add thewoolleyman/livespec-orchestrator-beads-fabro
codex plugin add livespec-orchestrator-beads-fabro@livespec-orchestrator-beads-fabro
```

Once installed, Codex operations are driven via `codex exec` and NAME-selected as
`<plugin>:<op>` (for example, `livespec:next`,
`livespec-orchestrator-beads-fabro:list-work-items`) rather than as
`/`-prefixed slash commands. The distributed Drivers resolve their prose at
runtime; no `AGENTS.md` skill-to-prose mapping is required. See
`livespec/SPECIFICATION/contracts.md` §"Plugin distribution" and
`livespec/SPECIFICATION/non-functional-requirements.md` §"Codex dogfooding
contracts" for the authoritative install and resolution contracts.

The Codex TUI picker displays skills by short name with the plugin as context.
In `/skills` → `List skills` (or the `@` picker), search the operation name,
for example `orchestrate`; the row renders as
`orchestrate (livespec-orchestrator-beads-fabro)` with kind `Skill`. The
colon-qualified form `livespec-orchestrator-beads-fabro:orchestrate` is still
valid for prompt / `codex exec` name selection and model-visible skill
references, but it is not the picker row operators should expect.

## Repository mutation protocol

Every repo change uses a worktree → PR → merge → cleanup path. Treat
leaving dirty state, committing on the primary checkout, or asking the
user whether to commit as failures of the workflow, not as acceptable
stopping points.

1. Confirm the primary checkout before editing:

   ```bash
   git -C /data/projects/livespec-driver-claude config --get livespec.primaryPath
   git -C /data/projects/livespec-driver-claude status --short --branch
   ```

2. If the change will modify tracked files, create a dedicated worktree
   from the primary checkout's `master` and do all edits there:

   ```bash
   mise exec -- git -C /data/projects/livespec-driver-claude worktree add -b <branch> "$HOME/.worktrees/livespec-driver-claude/<branch>" master
   ```

   `just bootstrap` registers `~/.worktrees` as one of mise's
   `trusted_config_paths`, so a freshly created worktree's `.mise.toml`
   is auto-trusted and the first `mise exec` inside it never stalls on a
   "config not trusted" prompt.

3. Use `mise exec -- git commit ...` and `mise exec -- git push ...` so
   the mise-managed lefthook hooks actually run. Never pass
   `--no-verify`; if a hook fails, fix the cause or halt with the
   failure.
4. Open a PR, wait for required checks, and merge through the PR using
   the repo's rebase-merge discipline.
5. After merge, refresh `/data/projects/livespec-driver-claude` to
   `origin/master`, remove the feature worktree, delete the local
   branch, and verify the primary checkout is clean on `master`.

Do not leave orphaned worktrees. If a session must stop before cleanup,
record the active worktree path, branch, PR, validation state, and next
action in the relevant handoff document.

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
