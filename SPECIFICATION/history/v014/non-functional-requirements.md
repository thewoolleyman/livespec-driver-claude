# non-functional-requirements.md — livespec-driver-claude

Contributor-facing invariants: how this repo is structured, guarded,
built, tested, and evolved. Where `contracts.md` says *what must be true*
of the Driver seam, this file says *how it is guarded* and how the repo
is operated.

## Boundary

This file covers the operational disciplines of developing the Driver
plugin: the task runner, the repo layout, the enforcement suite that
guards the contracts, the build/release flow, test discipline,
spec-evolution rules, and how the repo's dispatches are routed to a
factory. It does not restate the seam contracts themselves
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

Where the repository has delegated its pre-push gate per the next paragraph, a pre-push from a delegating host obtains the same `just check` aggregate's verdict from the remote executor against the pushed tree instead of running it on the pushing host, save the checks the delegation contract places on the pushing host, and except where an explicit local run has already authorized the tree. This changes WHERE the aggregate runs and MUST NOT change WHAT it verifies.

The repository MAY delegate its pre-push gate to the remote executor of the fleet enforcement suite's delegation client (livespec-dev-tooling §"Delegated pre-push gate"). When it does, it MUST conform to the delegation contract livespec ratifies in §"Enforcement-suite invocation", clause **Delegated gate execution**. For this repository that means:

- Delegation MUST be opted in by the repository's version-controlled configuration. It MUST be withdrawn only by a change to that configuration, never per push or per host. The gate MUST remain runnable on the pushing host by an explicit act whether or not delegation is opted in.
- A push MUST delegate only from a host that holds the credential authorizing it to submit to the executor. A host that holds none, such as a factory sandbox, MUST run the repository's gate recipe on that host without delegation, and MUST report that it gated locally.
- The pre-push path for a delegating host MUST run the delegation client in place of the aggregate, and MUST have no branch from the client's result to a local run of the gate. An absent verdict MUST refuse the push.
- The check recipe MUST read the fleet's recognised skip variable, `SKIP_TARGETS`, so the members the delegation contract places on the pushing host are left out of the executor's run. A run that skipped any member MUST NOT write the green token.

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

## Factory routing

Every entry this repository commits in `.livespec.jsonc` under `dispatcher.factories` MUST be
registry-backed: it declares `"registry": true` and carries no `server` and no `docker_host`
value, so no committed factory entry names a machine. Which Fabro server answers to a factory
name is bound only in the fleet gitops inventory's factory registry (livespec-dev-tooling
`non-functional-requirements.md` §"Fabro factory registry"), which each dispatching host
renders as `/etc/livespec/fabro-factories.json`; a dispatch resolves a registry-backed entry
from that file by name. `dispatcher.default_factory` MUST name `petri`.
