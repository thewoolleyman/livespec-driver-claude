# Handoff — work-item-state-machine L2 (livespec-driver-claude)

**Read-first chain:** this file → `research/01-l2-migration-record.md`
(the full migration record) → the live ledger (`bd -C <repo> list
--status all`). Nothing else is needed.

**Track:** L2 thin migration-only slice of the fleet
`work-item-state-machine` epic. Driver → orchestrator zero-deps, so **no
repo code/spec change** — only this repo's beads-tenant data migration,
captured here. Fleet anchor **`livespec-35s3zo`** (prose link only).

## Status (derive from the ledger — never stored here)

Read live state first: `bd -C <this-repo> list --status all` and
`bd -C <this-repo> config get status.custom` (via the fleet 1Password env
wrapper). The migration was completed and verified:

- **Custom statuses registered:**
  `backlog,pending-approval,ready:active,active:wip,acceptance:wip`.
- **`rank` backfilled** across all pre-migration items (legacy-seeded by
  `priority → captured_at → id`); every live head carries a real,
  non-sentinel rank (`a0`–`a7`); zero sentinel violations.
- **Ledger anchors:** epic **`livespec-driver-claude-wqyfbj`** (`epic`,
  `backlog`) ← typed-`--parent` child work-item
  **`livespec-driver-claude-3sunx4`** (`task`) capturing the migration.

## Next action (exactly one)

**Terminal close of the migration work-item.** Once this thread's PR is
merged, close `livespec-driver-claude-3sunx4` as `done` with the merge
audit, via the orchestrator's own store-writer (close-in-place). Run
under the fleet env wrapper from any checkout of this repo:

```python
# source /data/projects/.../with-livespec-env.sh python3 - <<'PY'
import sys; from dataclasses import replace; from pathlib import Path
S=Path("/data/projects/livespec-orchestrator-beads-fabro/.claude-plugin/scripts")
for p in (S, S/"_vendor"): sys.path.insert(0, str(p))
from livespec_orchestrator_beads_fabro.commands._config import resolve_store_config
from livespec_orchestrator_beads_fabro.store import append_work_item, read_work_items
from livespec_orchestrator_beads_fabro.types import AuditRecord
cfg=resolve_store_config(cwd=Path.cwd(), work_items_arg=None)
wi={w.id:w for w in read_work_items(path=cfg)}["livespec-driver-claude-3sunx4"]
audit=AuditRecord(verification_timestamp="<ISO8601>", commits=(), files_changed=(),
                  merge_sha="<MERGE_SHA>", pr_number=<PR_NUMBER>)
append_work_item(path=cfg, item=replace(wi, status="done", resolution="completed",
    reason="L2 tenant migration complete (statuses + rank backfill)", audit=audit))
PY
```

If that work-item already reads `done` (`closed`), this track is
**terminal** — nothing remains in this repo. The parent epic
`livespec-driver-claude-wqyfbj` is left **open**; closing it (and
archiving this thread) is a **fleet-level** action the overseer performs
at the epic's exit gate, not a per-repo step.

## Guardrails honored

worktree → PR → rebase-merge; `mise exec -- git`; never `--no-verify`;
the tenant password is sourced only via the fleet 1Password env wrapper
(probe-only, never echoed).
