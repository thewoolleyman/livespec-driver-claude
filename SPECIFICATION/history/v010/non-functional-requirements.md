# non-functional-requirements.md — livespec-driver-claude

Contributor-facing invariants: how this repo is structured, guarded,
built, tested, and evolved. Where `contracts.md` says *what must be true*
of the Driver seam, this file says *how it is guarded* and how the repo
is operated.

## Boundary

This file covers the operational disciplines of developing the Driver
plugin: the task runner, the repo layout, the enforcement suite that
guards the contracts, the build/release flow, test discipline, and
spec-evolution rules. It does not restate the seam contracts themselves
(`contracts.md`) or the architectural constraints (`constraints.md`).

## Inherited from livespec

The family-standard operational disciplines apply here unmodified and are
owned upstream:

- **Primary-checkout commit-refuse hook** — every change uses a worktree
  → PR → merge → cleanup path; the primary checkout refuses direct
  commits/pushes. The hook body and its doctor fingerprint invariant are
  owned by `livespec/SPECIFICATION/non-functional-requirements.md`
  and `livespec/SPECIFICATION/contracts.md`. This repo carries a
  copy of the canonical scaffold under `dev-tooling/`; it does not
  re-specify it.
- **Toolchain pinning** via `mise`; **`uv`** as the Python toolchain
  manager. Git operations that must fire lefthook are run through
  `mise exec -- git …`; `--no-verify` is never used.

## Task-runner discipline

`just` is the single source of truth for every dev-tooling invocation.
`lefthook` (pre-commit / pre-push) and CI delegate to `just <target>`;
neither invokes a tool binary directly. `just check` is the full
enforcement aggregate and is the load-bearing safety net — it runs
locally, in pre-push, and in CI.

## Repo layout

| Path | Purpose |
|---|---|
| `.claude-plugin/` | The Driver plugin: `plugin.json`, `marketplace.json`, the eight `skills/<name>/SKILL.md` bindings, and the `hooks/` bundle |
| `dev-tooling/` | `check_plugin_structure.py` (the structural gate) plus the family-standard git-hook scaffolds |
| `tests/e2e-cli/` | The CLI end-to-end harness consumer (mock-tier skill discovery + fail-closed fixture coverage gate) |
| `tests/hooks/` | Unit tests for the plugin-shipped hook scripts |
| `SPECIFICATION/` | This spec tree (dogfooded) |
| `justfile`, `lefthook.yml`, `.mise.toml`, `.python-version`, `pyproject.toml` | Family-standard toolchain configuration |

## Enforcement suite

`just check` aggregates the gates that guard the `contracts.md` seam:

- **`check-plugin-structure`** — runs `dev-tooling/check_plugin_structure.py`
  (stdlib-only, fail-closed) to enforce the manifest, skill-set, and
  fenced-invocation contracts in `contracts.md`. This is the mechanical
  teeth behind §"Plugin manifest and marketplace", §"Skill-binding set",
  and §"Fenced-invocation discipline".
- **`check-hooks`** — unit-tests the plugin-shipped hook scripts.
- **`check-e2e-cli`** — drives the CLI end-to-end harness.
- **`check-lint`** / **`check-format`** — `ruff` lint and format gates.

Every gate is wired into both pre-commit/pre-push (via lefthook) and CI
(via the shared `livespec-dev-tooling` reusable workflows), so the same
suite runs in every context.

## Build and release

The Driver ships as a Claude Code plugin. `plugin.json.version` is the
single source of truth for the shipped version and is auto-managed by
`release-please` from Conventional Commits (`contracts.md` §"Versioning").

## Test discipline

Two test surfaces back the enforcement suite: `tests/e2e-cli/` proves the
installed Driver bindings drive core's wrappers end-to-end (mock-tier
discovery + a fail-closed fixture-coverage gate), and `tests/hooks/`
unit-tests each hook script via subprocess invocation with a mocked
`CLAUDE_PROJECT_DIR` and `tmp_path` fixture projects.

## Spec evolution

This `SPECIFICATION/` tree dogfoods livespec. Every change lands through
`/livespec:propose-change` → `/livespec:revise`, which snapshots the
result under `history/vNNN/`. `/livespec:doctor`'s static phase flags
out-of-process drift. Wiring the doctor static phase and a heading-coverage
gate into `just check` / CI (so the spec gains the same mechanical teeth
the sibling libraries carry) is tracked as follow-up impl work in the
repo's beads tenant.
