# justfile — livespec-driver-claude task runner.
#
# Family conventions, scaled to this repo's content (thin SKILL.md
# bindings + plugin manifests + the e2e-cli harness consumer):
#
# Authority: livespec/SPECIFICATION/non-functional-requirements.md
#   §"Enforcement-suite invocation" — `just` is the canonical entry
#   point for every dev-tooling invocation. Lefthook and CI MUST
#   delegate to `just <target>`; direct tool invocations in hook/CI
#   configs are banned.
#
# Authority: livespec/SPECIFICATION/contracts.md
#   §"Pre-commit step ordering" — the gates wired here mirror the
#   spec-required ordering: 00-lint-autofix-staged, 01-commit-pairs-
#   source-and-test, 02-check-pre-commit at pre-commit;
#   no-commit-on-master + red-green-replay at commit-msg.
#
# Red-green-replay is ENFORCED here per epic livespec-gcp2 (maintainer
# directive 2026-06-25): red-green-replay is enforced fleet+adopter-
# wide regardless of any "no product Python" self-classification. A
# feat:/fix: commit with staged `.py` (the repo-local structural check
# plus the test suite) follows the Red->Green ritual; the gate is a
# no-op on commits with no staged `.py`, so a `ci:`/`docs:`/`chore:`
# commit passes it freely.

# Default to listing targets when no recipe is invoked.
default:
    @just --list

# ---------------------------------------------------------------
# First-time setup.
# ---------------------------------------------------------------

# Worktree-discipline pack recipe fragments — OPTIONAL imports (`import?`, NOT
# plain `import`): the fragments are gitignored-and-installed by
# `just install-worktree-pack` (run from the `worktree-pack` LOCAL obligation
# row that `bootstrap` walks), so they are ABSENT in a fresh clone until then. A
# plain `import` of a missing file makes `just` fail to parse the ENTIRE
# justfile, which would brick `just bootstrap` on a fresh clone; the optional
# `import?` silently no-ops while the file is absent — the `worktree-*` and
# `branch-protection-*` recipes simply are not available until the fragments are
# materialized — and resolves once installed. Without these two lines a
# byte-perfect installed pack is INVISIBLE to `just --list`, which is the
# discoverability hole that let a session fall back to a raw `git worktree add`.
import? 'dev-tooling/worktree.just'
import? 'dev-tooling/branch-protection.just'

# First-touch setup — a THIN delegator to the shipped LOCAL first-touch
# reconcile verb (`livespec_dev_tooling.fleet.local_reconcile`), the
# generalized successor to this recipe's former inline steps (livespec-zs22.8
# M5). Reuse-first: NO copied logic — the verb walks the LOCAL obligation
# partition (`contract.LOCAL_OBLIGATION_ROWS`): mise trust/install, uv sync,
# the canonical worktree-discipline pack, the structural commit-refuse hooks
# (subsuming `lefthook install` — the
# canonical hook overwrites the lefthook stubs and delegates to `lefthook
# run`), the advisory `refs/notes/*` refspec, the worktree-root mise-trust
# entry, the beads tenant-dir hardening, the beads-runtime detect-and-guide
# probes, and project-scoped Claude/Codex plugin registration. The two plugin
# rows delegate back to THIS repo's own `ensure-plugins` / `ensure-codex-plugins`
# recipes below (the plugin set is repo-specific, so each governed repo's recipe
# stays the single source; a member lacking either recipe SKIPs that row). The
# verb resolves shared-state rows worktree-safely via `git rev-parse
# --git-common-dir`, so invoking from a linked worktree still provisions the
# primary checkout's shared state. The `worktree-pack` row is the ONE exception:
# the pack lives in each checkout's own `dev-tooling/` and the `import?` lines
# above resolve relative to the worktree you stand in, so that row targets the
# INVOKED worktree — otherwise every linked worktree would show no
# `worktree-create` in `just --list`. Mirrors the `install-commit-refuse-hooks`
# recipe's `uv run python -m ...` from-package invocation.
bootstrap:
    uv run python -m livespec_dev_tooling.fleet.local_reconcile

# Install the canonical livespec commit-refuse hook by REUSING the shared
# livespec-dev-tooling installer module (the SINGLE source of the structural
# hook body; pinned in pyproject.toml). NOT re-implemented in this Driver repo.
# Idempotent; worktree-safe (resolves the primary's shared .git/hooks).
install-commit-refuse-hooks:
    uv run python -m livespec_dev_tooling.install_commit_refuse_hooks

# Install (or idempotently re-install) the canonical worktree-discipline pack —
# FOUR files: `worktree-lib.sh` + `branch-protection.sh` (executable) and
# `worktree.just` + `branch-protection.just` (imported above, not executable) —
# into the current checkout's `dev-tooling/` directory. The livespec-dev-tooling
# installer module is the single canonical-body carrier. The pack files are
# GITIGNORED-AND-MATERIALIZED, never tracked: nothing is committed, and each
# checkout re-materializes them. `bootstrap` covers this automatically via the
# `worktree-pack` LOCAL obligation row, so this recipe is the standalone repair
# path rather than a step `bootstrap` must duplicate. The
# `check-primary-checkout-commit-refuse-hook-installed` verifier guards the
# installed bytes against drift.
install-worktree-pack:
    uv run python -m livespec_dev_tooling.install_worktree_pack

# The standard shared derive-from-settings wrapper: it reads the committed
# `.claude/settings.json` (`extraKnownMarketplaces`, including each source's
# `ref`, and `enabledPlugins`) at runtime and issues the `claude plugin
# marketplace add` / `install` / `update` commands for exactly the
# marketplaces and plugins it finds there — one source of truth, so
# recipe-content drift is structurally impossible. Idempotent: the underlying
# `add` / `install` / `update` all exit 0 when the target is already present.
# Core MUST be installed alongside this Driver — the bindings resolve core's
# prose/ and scripts/ from the installed livespec@livespec cache — which the
# committed settings guarantee by enabling both plugins.
ensure-plugins:
    mise exec -- uv run --no-sync python -m livespec_dev_tooling.fleet.ensure_plugins

# Idempotent host-wide Codex plugin provisioning. Codex does not support
# project-scoped plugin enablement, so these registrations intentionally land in
# the user's default CODEX_HOME and are visible to every repo on the host. Codex
# is an optional dogfooding runtime; bootstrap skips this target when the CLI is
# absent but fails on real install errors when Codex is present.
ensure-codex-plugins:
    bash dev-tooling/just/ensure-codex-plugins.sh

# Confirm the shipped `github_rate_limit_guard.py` is IN FORCE — not merely
# released — in every governed repo this host installed the Driver into.
# Reads `~/.claude/plugins/installed_plugins.json` (the install RECORD, never a
# provisioning command's exit status, per livespec contracts.md "Install
# verification") and replays the committed regression corpus through the hook
# body each record's `installPath` actually carries. Deliberately NOT in the
# `check` aggregate: its subject is host install state, which CI does not have,
# and it fails closed when there is no record to read.
[positional-arguments]
verify-guard-rollout *args:
    python3 dev-tooling/bin/verify_guard_rollout.py "$@"

# ---------------------------------------------------------------
# Enforcement aggregate.
# ---------------------------------------------------------------

# The check aggregate deliberately omits errexit so it reports every failure.
check:
    #!/usr/bin/env bash
    set -uo pipefail
    targets=(
        # Canonical check set (livespec_dev_tooling.canonical_checks), in
        # alphabetical + CONTIGUOUS order — check-aggregate-completeness
        # requires the full canonical set present, in order, with extras
        # only AFTER this block (full-parity decision 2026-07-13).
        check-agents-ai-references-resolve
        check-aggregate-completeness
        check-all-declared
        check-assert-never-exhaustiveness
        check-branch-protection-alignment
        check-canonical-recipe-fidelity
        check-check-coverage-incremental
        check-check-mutation
        check-check-tools
        check-ci-gate-parity
        check-ci-matrix-completeness
        check-claude-md-coverage
        check-comment-line-anchors
        check-commit-pairs-source-and-test
        check-file-lloc
        check-fleet-marketplace-relative-sources
        check-global-writes
        check-handoff-dispatch-routing
        check-heading-coverage
        check-hook-trees-not-io-exempt
        check-keyword-only-args
        check-local-memory-drift-audit
        check-main-guard
        check-master-ci-green
        check-match-keyword-only
        check-newtype-domain-primitives
        check-no-direct-destructive-cli
        check-no-direct-tool-invocation
        check-no-except-outside-io
        check-no-fmt-directives
        check-no-inheritance
        check-no-lloc-soft-warnings
        check-no-raise-outside-io
        check-no-shadow-ledger-body-identical
        check-no-shadow-ledger-body-typechecks
        check-no-todo-registry
        check-no-write-direct
        check-partition-completeness
        check-pbt-coverage-pure-modules
        check-per-file-coverage
        check-plan-anchor-declared
        check-plan-epic-parity
        check-plan-no-tombstone
        check-plugin-resolution
        check-primary-checkout-commit-refuse-hook-installed
        check-private-calls
        check-public-api-result-typed
        check-red-green-replay
        check-required-role-keys-declared
        check-rop-pipeline-shape
        check-self-hosted-routing
        check-self-hosted-uv-lane
        check-shell-quality
        check-skill-invocation-paths
        check-source-trees-scoped-to-consumer
        check-supervisor-discipline
        check-tests-mirror-pairing
        check-tests-no-subprocess-spawn
        check-tool-backed-check-completeness
        check-vendor-manifest
        check-wrapper-shape
        # Repo-private extras (NON-canonical) — MUST follow the canonical
        # block. The four tool-backed gates (lint / format / types /
        # coverage) live here AND in the CI matrix, per
        # check-tool-backed-check-completeness's both-surfaces invariant.
        check-plugin-structure
        check-lint
        check-format
        check-types
        check-coverage
        check-hooks
        check-e2e-cli
        check-doctor-static
        check-spec-governance-default-block
    )
    failed=()
    for target in "${targets[@]}"; do
        echo "=== just ${target} ==="
        if ! just "${target}"; then
            failed+=("${target}")
        fi
    done
    if [ "${#failed[@]}" -gt 0 ]; then
        echo "FAILED targets: ${failed[*]}" >&2
        exit 1
    fi
    # Advisory-local green token — keyed on the current HEAD tree-hash so
    # check-pre-push can skip the full aggregate on a clean, unchanged tree.
    # A write failure must never abort a successful check aggregate.
    # STRICTLY advisory-local; CI remains authoritative.
    uv run python -m livespec_dev_tooling.green_token write || true

# Structural gate for the plugin bundle: manifest validity, the
# 8-skill set, frontmatter names, and the fenced-invocation rules
# (must use $LIVESPEC_CORE_ROOT; never `uv run`, never a literal
# .claude-plugin/scripts path, never the Driver's own plugin-root
# placeholder). Consumed from the livespec-dev-tooling package
# (`livespec_dev_tooling.driver_checks.plugin_structure`, profile-auto-detecting).
check-plugin-structure:
    uv run python -m livespec_dev_tooling.driver_checks.plugin_structure

# Cross-harness plugin-resolution Verifier (shipped by
# livespec-dev-tooling; Conformance Pattern concern #2). Reads the
# `harnesses` declaration from .livespec.jsonc and validates it
# fail-closed (known harness keys; `status` supported/exempt; supported
# carries a `canonical_command`, exempt a `reason`). The always-on
# declaration-integrity gate runs under the default mock selector; the
# live resolve-and-run smoke is opt-in via LIVESPEC_E2E_HARNESS=real.
check-plugin-resolution:
    uv run python -m livespec_dev_tooling.checks.plugin_resolution

check-lint:
    uv run ruff check .

check-format:
    uv run ruff format --check .

# Plugin-shipped Claude Code hook scripts (.claude-plugin/hooks/) —
# unit-tested as subprocesses with a mocked CLAUDE_PROJECT_DIR plus
# tmp_path fixture projects (work-item livespec-driver-claude-e1s).
check-hooks:
    uv run pytest tests/hooks/

# CLI end-to-end harness consumer (mock tier) — relocated from
# livespec core together with the bindings. Real structural skill
# discovery against .claude-plugin/, real fixture loading, the real
# fail-closed coverage gate; only the `claude -p` subprocess is
# mocked. Harness ships from livespec-dev-tooling per livespec/
# SPECIFICATION/contracts.md §"CLI end-to-end harness contract".
check-e2e-cli:
    LIVESPEC_E2E_HARNESS=mock uv run pytest tests/e2e-cli/

# Spec heading-coverage gate (shipped by livespec-dev-tooling): every
# `## ` H2 in each SPECIFICATION/ NLSpec file MUST have an entry in
# tests/heading-coverage.json. This keeps the coverage map in lockstep
# with the spec — adding or renaming a spec H2 without updating the
# registry fails the check. TODO entries (no per-heading test yet) warn
# locally and fail only when LIVESPEC_FAIL_IF_HEADING_COVERAGE_TODOS_EXIST
# is set; this binding repo leaves it UNSET (its H2s are guarded by
# check-plugin-structure / the hook tests / the e2e-cli harness rather
# than per-heading unit tests), so the gate enforces registration drift,
# not test-mapping completeness. The livespec doctor static phase is
# wired into `just check` / CI via `check-doctor-static` (below).
check-heading-coverage:
    uv run python -m livespec_dev_tooling.checks.heading_coverage

# livespec core's doctor STATIC phase (reference-discipline + out-of-band
# invariants) against THIS repo's SPECIFICATION/ tree, wired fleet-wide per
# livespec epic livespec-6jfq. core ships the checker: doctor_static.py is
# self-contained (vendored deps + bare python3), so it runs under plain
# python3 and NEVER `uv run`. Resolve core's plugin root via
# LIVESPEC_CORE_PLUGIN_ROOT (CI sets it to a livespec checkout at this repo's
# .livespec.jsonc compat.pinned tag) → else the installed livespec@livespec
# plugin cache (local dev). The two reference-discipline checks
# (no-cross-spec-reference, no-spec-section-citation-in-code) are pure reads;
# doctor-out-of-band-edits is self-healing — on a drifted tree it writes a
# history backfill into the worktree and fails, and committing that backfill
# heals the track; on a clean tree it never fires.
check-doctor-static:
    bash dev-tooling/just/check-doctor-static.sh

check-spec-governance-default-block:
    uv run --with 'livespec-runtime @ git+https://github.com/thewoolleyman/livespec-runtime.git@v0.19.0' python dev-tooling/bin/check_spec_governance_default_block.py

# ---------------------------------------------------------------
# Applies-to-all structural coverage checks (fleet-check-coverage,
# livespec epic livespec-i5ebqd). Each derives its file universe from
# the SAME root-anchored git index (`resolve_check_universe`), so this
# Driver's first-party hook `.py` (the three plugin-shipped hooks under
# .claude-plugin/hooks/ + the project-local .claude/hooks/
# livespec_footgun_guard.py) are structurally covered. `file_lloc` is
# armed to the hard gate for THIS repo via `file_lloc_hard_gate = true`
# in pyproject's [tool.livespec_dev_tooling]; the remaining checks stay
# Phase-0 WARN-only (exit 0) until a later fleet phase flips them.
# Full canonical parity: as of the 2026-07-13 full-parity decision this
# Driver DOES carry the complete canonical check set (wired above in the
# `check:` aggregate and mirrored into the CI matrix), so
# check-aggregate-completeness / check-ci-matrix-completeness /
# check-tool-backed-check-completeness are all in force here — reversing
# the earlier "Drivers stay outside universal-propagation" stance.
# ---------------------------------------------------------------

check-all-declared:
    uv run python -m livespec_dev_tooling.checks.all_declared

check-assert-never-exhaustiveness:
    uv run python -m livespec_dev_tooling.checks.assert_never_exhaustiveness

check-comment-line-anchors:
    uv run python -m livespec_dev_tooling.checks.comment_line_anchors

check-file-lloc:
    uv run python -m livespec_dev_tooling.checks.file_lloc

check-global-writes:
    uv run python -m livespec_dev_tooling.checks.global_writes

check-keyword-only-args:
    uv run python -m livespec_dev_tooling.checks.keyword_only_args

check-main-guard:
    uv run python -m livespec_dev_tooling.checks.main_guard

check-match-keyword-only:
    uv run python -m livespec_dev_tooling.checks.match_keyword_only

check-no-inheritance:
    uv run python -m livespec_dev_tooling.checks.no_inheritance

check-no-lloc-soft-warnings:
    uv run python -m livespec_dev_tooling.checks.no_lloc_soft_warnings

check-no-write-direct:
    uv run python -m livespec_dev_tooling.checks.no_write_direct

check-partition-completeness:
    uv run python -m livespec_dev_tooling.checks.partition_completeness

check-private-calls:
    uv run python -m livespec_dev_tooling.checks.private_calls

check-rop-pipeline-shape:
    uv run python -m livespec_dev_tooling.checks.rop_pipeline_shape

# Commit-pair gate (shipped by livespec-dev-tooling): every commit
# touching source files also touches tests. Lefthook pre-commit is the
# load-bearing per-commit invocation (step 01); wired into the full
# aggregate too so the gate runs at pre-push + CI.
check-commit-pairs-source-and-test:
    uv run python -m livespec_dev_tooling.checks.commit_pairs_source_and_test

# Trailer-based Red->Green replay verification (hard gate; shipped by
# livespec-dev-tooling). Enforced here per epic livespec-gcp2. Invoked
# by the lefthook commit-msg stage with the commit-message file path as
# argv[1] (the load-bearing per-commit verifier). The canonical
# aggregate / `just check` invokes this with NO msg_path; the module
# then DERIVES the message from HEAD and validates the branch range.
[positional-arguments]
check-red-green-replay *args:
    uv run python -m livespec_dev_tooling.checks.red_green_replay "$@"

# Fast pre-commit subset (no test run; pre-push runs the full
# aggregate).
check-pre-commit:
    bash dev-tooling/just/check-pre-commit.sh

check-pre-push:
    bash dev-tooling/just/check-pre-push.sh

# ---------------------------------------------------------------
# Pre-commit auxiliary gates.
# ---------------------------------------------------------------

# Factory-branch boundary: implementation branches do not carry workflow
# changes. The dispatcher runs this before `check` so any accidental workflow
# diff is rejected with the maintainer-landable patch shown in the log.
check-no-workflow-edits:
    bash dev-tooling/just/check-no-workflow-edits.sh

# Ruff fix + format on staged .py files BEFORE the rest of the
# pre-commit gate runs. Non-blocking — unfixable issues fall through
# to check-lint / check-format inside `just check` later. Re-stages
# post-autofix bytes.
#
# `--force-exclude` is REQUIRED: ruff's `extend-exclude`
# (pyproject [tool.ruff]) only filters DIRECTORY-WALK discovery, so a
# path passed EXPLICITLY on the command line (which this recipe does via
# `xargs`) is fixed/formatted even when it matches an exclude. Without
# `--force-exclude` this step would reformat `.claude-plugin/hooks/**`
# (e.g. strip a `# noqa` ruff deems unused) and re-stage the mutated
# bytes — breaking the cross-Driver BYTE-IDENTITY contract for
# `no_shadow_ledger.py` (livespec core `contracts.md` §"Driver-shipped
# hooks" → cross-Driver single-sourcing). `--force-exclude` makes the
# explicit-arg invocations honor the same excludes as `just check`'s
# `ruff check .` directory walk, so excluded hook bodies are left
# untouched here too.
lint-autofix-staged:
    bash dev-tooling/just/lint-autofix-staged.sh

check-agents-ai-references-resolve:
    uv run python -m livespec_dev_tooling.checks.agents_ai_references_resolve

check-aggregate-completeness:
    uv run python -m livespec_dev_tooling.checks.aggregate_completeness

check-branch-protection-alignment:
    uv run python -m livespec_dev_tooling.checks.branch_protection_alignment

check-canonical-recipe-fidelity:
    uv run python -m livespec_dev_tooling.checks.canonical_recipe_fidelity

check-check-coverage-incremental:
    uv run python -m livespec_dev_tooling.checks.check_coverage_incremental

check-check-mutation:
    uv run python -m livespec_dev_tooling.checks.check_mutation

check-check-tools:
    uv run python -m livespec_dev_tooling.checks.check_tools

check-ci-matrix-completeness:
    uv run python -m livespec_dev_tooling.checks.ci_matrix_completeness

check-claude-md-coverage:
    uv run python -m livespec_dev_tooling.checks.claude_md_coverage

check-fleet-marketplace-relative-sources:
    uv run python -m livespec_dev_tooling.checks.fleet_marketplace_relative_sources

check-master-ci-green:
    uv run python -m livespec_dev_tooling.checks.master_ci_green

check-newtype-domain-primitives:
    uv run python -m livespec_dev_tooling.checks.newtype_domain_primitives

check-no-direct-destructive-cli:
    uv run python -m livespec_dev_tooling.checks.no_direct_destructive_cli

check-no-direct-tool-invocation:
    uv run python -m livespec_dev_tooling.checks.no_direct_tool_invocation

check-no-except-outside-io:
    uv run python -m livespec_dev_tooling.checks.no_except_outside_io

check-no-fmt-directives:
    uv run python -m livespec_dev_tooling.checks.no_fmt_directives

check-no-raise-outside-io:
    uv run python -m livespec_dev_tooling.checks.no_raise_outside_io

check-no-todo-registry:
    uv run python -m livespec_dev_tooling.checks.no_todo_registry

check-pbt-coverage-pure-modules:
    uv run python -m livespec_dev_tooling.checks.pbt_coverage_pure_modules

# Per-file 100% line+branch coverage of the plugin-shipped hook bodies.
# Runs `pytest --cov` over tests/hooks/ (the in-process main() suites supply
# the coverage; the retained subprocess smokes do not) to write `.coverage`,
# then the shared per_file_coverage gate reads it. This canonical recipe
# deliberately omits errexit; the pytest leg fail-closes explicitly.
check-per-file-coverage:
    #!/usr/bin/env bash
    set -uo pipefail
    # Clean-env producer (livespec-dev-tooling-yilyxr.8, dev-tooling PR #1462
    # design): COVERAGE_FILE unset so the measurement matches a clean CI job
    # by construction; the serial aggregate runs check-coverage after this,
    # consuming the repo-root .coverage once (consume-once, no stale reports).
    env -u COVERAGE_FILE uv run pytest tests/hooks/ --cov --cov-branch --cov-config=pyproject.toml --cov-report=term-missing || exit $?
    env -u COVERAGE_FILE uv run python -m livespec_dev_tooling.checks.per_file_coverage

# Pyright type gate (tool-backed; a literal member of BOTH the `just check`
# array AND the CI matrix per check-tool-backed-check-completeness). Scoped to
# the two Driver-authored plugin hooks via pyproject's [tool.pyright].
check-types:
    uv run pyright

# Aggregate (total) coverage gate (tool-backed; both-surfaces per
# check-tool-backed-check-completeness). `fail_under = 100` lives in
# pyproject's [tool.coverage.report]. To avoid a DUPLICATE suite run inside
# `just check`, this gates off the EXISTING `.coverage` that the canonical
# check-per-file-coverage slug (which sorts alphabetically before this
# repo-private extra) already produced; a standalone CI check-coverage job
# with no prior pytest runs the suite itself. `-e` errexit for the same
# swallow-a-red-suite reason as check-per-file-coverage.
check-coverage:
    bash dev-tooling/just/check-coverage.sh

check-primary-checkout-commit-refuse-hook-installed:
    uv run python -m livespec_dev_tooling.checks.primary_checkout_commit_refuse_hook_installed

check-public-api-result-typed:
    uv run python -m livespec_dev_tooling.checks.public_api_result_typed

check-skill-invocation-paths:
    uv run python -m livespec_dev_tooling.checks.skill_invocation_paths

check-supervisor-discipline:
    uv run python -m livespec_dev_tooling.checks.supervisor_discipline

check-tests-mirror-pairing:
    uv run python -m livespec_dev_tooling.checks.tests_mirror_pairing

check-tests-no-subprocess-spawn:
    uv run python -m livespec_dev_tooling.checks.tests_no_subprocess_spawn

check-tool-backed-check-completeness:
    uv run python -m livespec_dev_tooling.checks.tool_backed_check_completeness

check-vendor-manifest:
    uv run python -m livespec_dev_tooling.checks.vendor_manifest

check-wrapper-shape:
    uv run python -m livespec_dev_tooling.checks.wrapper_shape

check-no-shadow-ledger-body-identical:
    uv run python -m livespec_dev_tooling.checks.no_shadow_ledger_body_identical

check-local-memory-drift-audit:
    uv run python -m livespec_dev_tooling.checks.local_memory_drift_audit

# Install the canonical no-shadow-ledger hook body (the single cross-Driver
# neutral shared body) into pyproject's `neutral_hook_body_path` by REUSING
# the shared livespec-dev-tooling installer — the SINGLE source of the body.
# NOT re-implemented here; idempotent. check-no-shadow-ledger-body-identical
# gates that the shipped copy is byte-identical to the packaged canonical.
install-no-shadow-ledger:
    uv run python -m livespec_dev_tooling.install_no_shadow_ledger

check-handoff-dispatch-routing:
    uv run python -m livespec_dev_tooling.checks.handoff_dispatch_routing

check-self-hosted-routing:
    uv run python -m livespec_dev_tooling.checks.self_hosted_routing

check-source-trees-scoped-to-consumer:
    uv run python -m livespec_dev_tooling.checks.source_trees_scoped_to_consumer

check-no-shadow-ledger-body-typechecks:
    uv run python -m livespec_dev_tooling.checks.no_shadow_ledger_body_typechecks

check-required-role-keys-declared:
    uv run python -m livespec_dev_tooling.checks.required_role_keys_declared

check-hook-trees-not-io-exempt:
    uv run python -m livespec_dev_tooling.checks.hook_trees_not_io_exempt

check-shell-quality:
    uv run python -m livespec_dev_tooling.checks.shell_quality

check-plan-anchor-declared:
    uv run python -m livespec_dev_tooling.checks.plan_anchor_declared

check-plan-epic-parity:
    uv run python -m livespec_dev_tooling.checks.plan_epic_parity

check-plan-no-tombstone:
    uv run python -m livespec_dev_tooling.checks.plan_no_tombstone

check-self-hosted-uv-lane:
    uv run python -m livespec_dev_tooling.checks.self_hosted_uv_lane

check-ci-gate-parity:
    uv run python -m livespec_dev_tooling.checks.ci_gate_parity
