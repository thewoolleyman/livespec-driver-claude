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

# First-touch setup — a THIN delegator to the shipped LOCAL first-touch
# reconcile verb (`livespec_dev_tooling.fleet.local_reconcile`), the
# generalized successor to this recipe's former inline steps (livespec-zs22.8
# M5). Reuse-first: NO copied logic — the verb walks the LOCAL obligation
# partition (`contract.LOCAL_OBLIGATION_ROWS`): mise trust/install, uv sync,
# the structural commit-refuse hooks (subsuming `lefthook install` — the
# canonical hook overwrites the lefthook stubs and delegates to `lefthook
# run`), the advisory `refs/notes/*` refspec, the worktree-root mise-trust
# entry, the beads tenant-dir hardening, the beads-runtime detect-and-guide
# probes, and project-scoped Claude/Codex plugin registration. The two plugin
# rows delegate back to THIS repo's own `ensure-plugins` / `ensure-codex-plugins`
# recipes below (the plugin set is repo-specific, so each governed repo's recipe
# stays the single source; a member lacking either recipe SKIPs that row). The
# verb resolves the target checkout worktree-safely via `git rev-parse
# --git-common-dir`, so invoking from a linked worktree still provisions the
# primary checkout's shared state. Mirrors the `install-commit-refuse-hooks`
# recipe's `uv run python -m ...` from-package invocation.
bootstrap:
    uv run python -m livespec_dev_tooling.fleet.local_reconcile

# Install the canonical livespec commit-refuse hook by REUSING the shared
# livespec-dev-tooling installer module (the SINGLE source of the structural
# hook body; pinned in pyproject.toml). NOT re-implemented in this Driver repo.
# Idempotent; worktree-safe (resolves the primary's shared .git/hooks).
install-commit-refuse-hooks:
    uv run python -m livespec_dev_tooling.install_commit_refuse_hooks

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
    #!/usr/bin/env bash
    set -euo pipefail
    if ! command -v codex >/dev/null 2>&1; then
        echo "codex CLI not found; skipping host-wide Codex plugin install." >&2
        exit 0
    fi
    codex plugin marketplace add thewoolleyman/livespec --ref release
    codex plugin marketplace add thewoolleyman/livespec-driver-codex --ref release
    codex plugin marketplace add thewoolleyman/livespec-orchestrator-beads-fabro --ref release
    codex plugin marketplace upgrade livespec
    codex plugin marketplace upgrade livespec-driver-codex
    codex plugin marketplace upgrade livespec-orchestrator-beads-fabro
    codex plugin add livespec@livespec
    codex plugin add livespec@livespec-driver-codex
    codex plugin add livespec-orchestrator-beads-fabro@livespec-orchestrator-beads-fabro

# ---------------------------------------------------------------
# Enforcement aggregate.
# ---------------------------------------------------------------

check:
    #!/usr/bin/env bash
    set -uo pipefail
    targets=(
        check-plugin-structure
        check-agents-ai-references-resolve
        check-aggregate-completeness
        check-branch-protection-alignment
        check-canonical-recipe-fidelity
        check-check-coverage-incremental
        check-check-mutation
        check-check-tools
        check-ci-matrix-completeness
        check-claude-md-coverage
        check-commit-pairs-source-and-test
        check-fleet-marketplace-relative-sources
        check-master-ci-green
        check-newtype-domain-primitives
        check-no-direct-destructive-cli
        check-no-direct-tool-invocation
        check-no-except-outside-io
        check-no-fmt-directives
        check-no-raise-outside-io
        check-no-shadow-ledger-body-identical
        check-no-todo-registry
        check-pbt-coverage-pure-modules
        check-per-file-coverage
        check-plugin-resolution
        check-lint
        check-format
        check-hooks
        check-e2e-cli
        check-heading-coverage
        check-doctor-static
        check-all-declared
        check-assert-never-exhaustiveness
        check-comment-line-anchors
        check-file-lloc
        check-global-writes
        check-keyword-only-args
        check-main-guard
        check-match-keyword-only
        check-no-inheritance
        check-no-lloc-soft-warnings
        check-no-write-direct
        check-partition-completeness
        check-primary-checkout-commit-refuse-hook-installed
        check-private-calls
        check-public-api-result-typed
        check-red-green-replay
        check-rop-pipeline-shape
        check-skill-invocation-paths
        check-supervisor-discipline
        check-tests-mirror-pairing
        check-tests-no-subprocess-spawn
        check-tool-backed-check-completeness
        check-vendor-manifest
        check-wrapper-shape
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
    # || true: a write failure must never abort a successful check aggregate.
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
    #!/usr/bin/env bash
    set -euo pipefail
    core_root="${LIVESPEC_CORE_PLUGIN_ROOT:-}"
    if [ -z "$core_root" ]; then
      # Resolve the CURRENT released core build (== marketplace clone HEAD), NOT
      # installed_plugins.json[...]["livespec@livespec"][0] — that per-project list is
      # unordered and its first row can be a different, stale project on a mixed-build
      # host, which the c1k9 currency gate then correctly blocks (livespec-q2me).
      core_root="$(python3 -c 'import subprocess, pathlib; mk = pathlib.Path.home() / ".claude" / "plugins" / "marketplaces" / "livespec"; head = subprocess.run(["git", "-C", str(mk), "rev-parse", "--short=12", "HEAD"], capture_output=True, text=True).stdout.strip().lower(); cache = pathlib.Path.home() / ".claude" / "plugins" / "cache" / "livespec" / "livespec" / head; print(cache if head and (cache / "scripts" / "bin" / "doctor_static.py").is_file() else "")' 2>/dev/null || true)"
    fi
    if [ -z "$core_root" ] || [ ! -f "$core_root/scripts/bin/doctor_static.py" ]; then
      echo "livespec core not found. Set LIVESPEC_CORE_PLUGIN_ROOT to a livespec checkout's .claude-plugin, or install the livespec@livespec plugin (claude plugin install livespec@livespec)." >&2
      exit 1
    fi
    python3 "$core_root/scripts/bin/doctor_static.py" --project-root .

# ---------------------------------------------------------------
# Applies-to-all structural coverage checks (fleet-check-coverage,
# livespec epic livespec-i5ebqd). Each derives its file universe from
# the SAME root-anchored git index (`resolve_check_universe`), so this
# thin Driver's two first-party hook `.py`
# (.claude-plugin/hooks/no_shadow_ledger.py + .claude/hooks/
# livespec_footgun_guard.py) are now structurally covered. `file_lloc`
# is armed to the hard gate for THIS repo via `file_lloc_hard_gate =
# true` in pyproject's [tool.livespec_dev_tooling]; the remaining
# checks stay Phase-0 WARN-only (exit 0) until a later fleet phase
# flips them. `check-aggregate-completeness` is DELIBERATELY NOT wired:
# it is the universal-propagation gate that requires the full canonical
# spec/orchestrator/copier check set, which a thin per-runtime binding
# does not carry — Drivers stay OUTSIDE universal-propagation
# (maintainer decision 2026-07-12).
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
check-red-green-replay *args:
    uv run python -m livespec_dev_tooling.checks.red_green_replay {{args}}

# Fast pre-commit subset (no test run; pre-push runs the full
# aggregate).
check-pre-commit:
    just check-plugin-structure
    just check-lint
    just check-format

check-pre-push:
    #!/usr/bin/env bash
    set -uo pipefail
    # Advisory-local green-token short-circuit: if the current HEAD tree was
    # already verified clean by a successful full `just check` run, skip the
    # full aggregate. The token is invalidated by any new commit (tree-hash
    # change) or an uncommitted worktree modification. STRICTLY advisory-local;
    # CI is authoritative — a token match never bypasses the remote gate.
    if uv run python -m livespec_dev_tooling.green_token check 2>&1; then
        echo ":: pre-push: green token matched — tree byte-identical to last green check; skipping full aggregate (CI is authoritative)"
        exit 0
    fi
    just check

# ---------------------------------------------------------------
# Pre-commit auxiliary gates.
# ---------------------------------------------------------------

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
    #!/usr/bin/env bash
    set -uo pipefail
    staged=$(git diff --cached --name-only --diff-filter=AM | grep -E '\.py$' || true)
    if [[ -z "$staged" ]]; then
        exit 0
    fi
    echo "$staged" | xargs uv run ruff check --fix --exit-zero --force-exclude
    echo "$staged" | xargs uv run ruff format --force-exclude
    echo "$staged" | xargs git add

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

check-per-file-coverage:
    uv run python -m livespec_dev_tooling.checks.per_file_coverage

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
