# Beads Tenant Operations

Use this note before running live `bd` or
livespec-orchestrator-beads-fabro commands against the
`livespec-driver-claude` beads tenant.

The tenant password is supplied at command time, not committed. Use the
repo-declared credential wrapper from `.livespec.jsonc` when reading or
writing live tenant state:

```bash
/usr/local/bin/with-livespec-env.sh -- bd -C /data/projects/livespec-driver-claude list --status all
```

Never print `BEADS_DOLT_PASSWORD`; use probe-only checks such as a byte
count if credential presence must be diagnosed. Pass `-C <repo-path>` as
a literal command argument so the wrapper and `bd` select this repo's
committed `.beads/config.yaml` tenant connection.

The historical `plan/work-item-state-machine/` L2 migration thread is
terminal. The tenant migration task
`livespec-driver-claude-3sunx4` closed via PR 69
(`2bf1cf47f8b5a50ead5776fde00c6de4802c93d4`), and the parent epic
`livespec-driver-claude-wqyfbj` later closed at the fleet exit gate. If
old handoff prose conflicts with live tenant state, treat the live tenant
as authoritative and the plan thread as historical record.
