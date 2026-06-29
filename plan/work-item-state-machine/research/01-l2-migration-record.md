# L2 tenant migration — record & reasoning (livespec-driver-claude)

This repo's slice of the fleet **work-item-state-machine** epic. It is a
**thin, migration-only** track: per slice-plan decisions 42 and 46, a
Driver has **zero deps** on the orchestrator and its spec carries no
work-item schema, so there is **no repo code or spec change** — only the
**data migration of this repo's beads tenant**, formalized here so it is
captured in repo history.

Authority: `livespec/plan/work-item-state-machine/research/04-slice-plan.md`
(§"L2 — migration") and `03-decision-log.md` (decisions 36, 38, 39, 46).
Fleet anchor: **`livespec-35s3zo`** (livespec core tenant) — referenced as a
**prose link only**, never a typed cross-tenant `depends_on` (decision 45:
a cross-tenant id would dangle and pollute the `blocked:dependency`
derivation).

## What L1 shipped (the dependency this gated on)

`livespec-orchestrator-beads-fabro` **v0.3.0** released the schema + tooling
this migration consumes: the 7-state lifecycle + required `rank` field,
`store.register_custom_statuses()`, and the `rebalance-ranks`
`legacy_seed` backfill primitive (orders pre-migration rows by
`priority → captured_at → id` and assigns evenly-spaced fractional keys,
decision 39). No committed orchestrator version pin exists in this repo
(the marketplace ref is untagged); the migration was driven directly
against the v0.3.0 source tooling.

## The two migration steps (decision 36 + decision 39)

1. **Register the 5 custom livespec statuses** (idempotent, per-tenant) via
   the orchestrator's `register_custom_statuses` →
   `bd config set status.custom "backlog,pending-approval,ready:active,active:wip,acceptance:wip"`.
   Encoding per decision 36: `backlog` / `pending-approval` / `ready` /
   `active` / `acceptance` are custom; `blocked` reuses the built-in
   name; `done` maps to the built-in `closed`.

2. **Backfill the required `rank` field** across the pre-migration items
   via the orchestrator `rebalance-ranks` **legacy-seed** path. This
   tenant held **6 items, all `closed`** (priorities P1–P4). Seeded by
   the legacy `priority → captured_at → id` order, `legacy_seed` assigned
   evenly-spaced base-62 keys:

   | rank | id | legacy priority | captured_at |
   |---|---|---|---|
   | `a0` | livespec-driver-claude-3bk | P1 | 2026-06-13T01:13:17Z |
   | `a1` | livespec-driver-claude-dit | P2 | 2026-06-11T01:08:35Z |
   | `a2` | livespec-driver-claude-4jp | P3 | 2026-06-10T23:29:20Z |
   | `a3` | livespec-driver-claude-e1s | P3 | 2026-06-10T23:29:28Z |
   | `a4` | livespec-driver-claude-o3p | P3 | 2026-06-20T08:32:33Z |
   | `a5` | livespec-driver-claude-26c | P4 | 2026-06-20T08:32:33Z |

   Written per-backend as `metadata.rank` (decision 36 field map). The
   native `priority` column survives harmlessly in beads but is no longer
   read into the materialized record. **No live head carries the
   bottom-sentinel** (`~`) after the backfill (decision 39 invariant).

## The plan-thread anchors (this track's ledger capture)

Filed through the orchestrator's consented store-writer (`append_work_item`)
against the **actual v0.3.0 `WorkItem` schema** — the shipped
`capture-work-item`/`plan` prose still shows the pre-v0.3.0 shape
(`status="open"`, `priority=…`, no `rank`), so the writes were driven
directly against the schema (the console-repo precedent, decision 41:
"epic via the same consented store-writer"):

- **Epic** `livespec-driver-claude-wqyfbj` — type `epic`, status `backlog`,
  rank `a6`. The thread's status anchor; prose-linked to `livespec-35s3zo`.
- **Work-item** `livespec-driver-claude-3sunx4` — type `task`, status
  `backlog`, rank `a7`, **typed `--parent` child** of the epic (a clean
  parent-child link, NOT a `blocks` edge, so no spurious
  `blocked:dependency` lane). Captures the migration itself.

## Verification

- `bd config get status.custom` → `backlog,pending-approval,ready:active,active:wip,acceptance:wip`.
- All **8** tenant items carry a real, non-sentinel `rank` (`a0`–`a7`);
  `sentinel_violations: []` (decision 39 doctor invariant).
- `active ⟹ assignee` and `blocked ⟹ blocked_reason` invariants hold
  vacuously (no item is `active` or stored-`blocked`).

The data migration lives in the beads tenant (not in git); this thread is
its durable repo-history capture.
