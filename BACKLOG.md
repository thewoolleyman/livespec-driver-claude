# Backlog — lives in the beads tenant

This repo's work-item backlog lives in its beads tenant
(`livespec-driver-claude` on the shared dolt-server; connection block in
`.beads/config.yaml`, tenant password supplied via `BEADS_DOLT_PASSWORD`
at bd-call time). Query it with `bd list` from the repo root.

The two founding items, relocated from the livespec tenant (provenance:
livespec master `02ef5ccca178335da2aec690220fb2efe52bb879`):

| Tenant item | Origin (livespec tenant) | Summary |
|---|---|---|
| `livespec-driver-claude-4jp` | `livespec-c1nf` | Stop hook for plan-artifact persistence detection |
| `livespec-driver-claude-e1s` | `livespec-hookimpl` | PreToolUse hook redirecting auto-memory writes to capture-memo |

Full descriptions (including lineage and provenance notes) are carried
in the tenant items themselves.
