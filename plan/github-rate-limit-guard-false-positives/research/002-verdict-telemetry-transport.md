# Verdict telemetry — transport decision, and the query it makes possible

Opened 2026-08-26. Work-item `livespec-driver-claude-mbg4zg.5`. Companion to
`001-measurement-and-architecture.md`, which measured the guard's false-positive
rate by replay and thereby proved the rate was not observable.

## 1. Why the 40.5% figure needed a replay at all

`github_rate_limit_guard.py`'s `_log_event` already writes structured JSON with a
`check_id` — but only on DENY, and only to stderr, which the harness discards on
a PreToolUse exit 0. The `agent-activity` / `claude-code` dataset carries
`hook_name` and `num_blocking` and no per-guard verdict. So the only way to ask
"how often does this guard convict a command that never ran `gh`" was to pull a
week of local transcripts and re-run the live `_deny_reason` over them.

## 2. The candidates, and why OTLP traces won

| Candidate | Verdict |
| --- | --- |
| PreToolUse stderr | **Rejected.** Discarded on exit 0, which is exactly the ALLOW half being added. It cannot carry the signal at all. |
| A local JSONL the otel collector tails | **Rejected.** Needs a `filelog` receiver in the host collector's pipeline. That config is host infrastructure no change in this repo can reach, so the records would accrue in a file nothing reads — the acceptance condition "the records reach Honeycomb" would be unmet by anything in this changeset. It also brings a path convention, rotation and cleanup along with it. |
| OTLP over HTTP to the host receiver | **Chosen.** |

Two facts decided it, both checked against the live receiver rather than assumed:

- The mechanism already exists for exactly this shape of caller.
  `livespec-step-timer` (`livespec_dev_tooling.otel_step_timer`) exports from
  stdlib-only, no-virtualenv code to `$LIVESPEC_SANDBOX_OTEL_ENDPOINT`
  (default `http://172.17.0.1:4318`), and the receiver routes a payload to its
  Honeycomb dataset by `service.name` — so a new emitter needs no provisioning.
- The receiver picks the SIGNAL. `POST /v1/traces` answers `200`;
  `POST /v1/logs` answers `404`. There is no logs pipeline, so an OTLP *log*
  record — the shape a verdict event would otherwise take — has nowhere to
  land. A verdict therefore rides as a zero-duration SPAN.

Dataset: `agent-hooks`, kept separate from `agent-activity` (which is the
harness's own export and not this hook's to shape).

## 3. What the record carries — and what it deliberately does not

Per verdict, on BOTH paths:

| Attribute | Values |
| --- | --- |
| `verdict` | `rate_limited` \| `allowed` |
| `matched_rule` | `loop+read` \| `sleep+read` \| `loop+mutation` \| `none` |
| `gh_cached` | whether any `gh api --cache <duration>` is present |
| `gh_at_command_position` | whether a `gh api`/`run`/`pr` invocation sits where the shell would execute it |
| `check_id`, `session_id` | join keys back to the stderr deny record and the harness session |

`matched_rule` is `"none"` on the allow path rather than absent: an absent
attribute is an absent column, and a column that exists only on denials cannot
carry a `GROUP BY` across the whole population.

**No command text.** A Bash command line routinely holds tokens, hostnames and
private paths — the replay corpus beside the tests is scrubbed for exactly those
and has a test that scans for leaks. The classification is what the query needs,
so shipping the text would buy triage detail at the price of exporting secrets to
a shared surface. The record's attribute set is pinned closed by a test so a
later "just add the command for triage" cannot land quietly.

## 4. The query

A `rate_limited` verdict that found no `gh` at command position IS a false
positive, by definition. So, over the `agent-hooks` dataset:

```
COUNT WHERE verdict = "rate_limited" AND gh_at_command_position = false
  / COUNT WHERE verdict = "rate_limited"
```

and `GROUP BY matched_rule` splits it by which conjunction convicted.
`gh_cached = true` on a `rate_limited` row reproduces bucket b1 of the replay
corpus — the "denied for obeying the instruction it was just given" family —
directly, with no replay.

## 5. Fail-open

Emission cannot move a verdict. The guard computes its exit code before calling
the exporter, so the exporter cannot change one by returning; and it cannot
change one by raising, because every input is an already-typed primitive (the
payload shaping has no failure mode) and the single surface that can fail — the
network — is narrowly suppressed. A host with no receiver refuses the connection
immediately and the guard proceeds unchanged.

The POST timeout is 0.5s, well under the step timer's 2s, because this runs on
the critical path of EVERY Bash tool call rather than once per sandbox prepare
step: the ceiling is what an operator would tolerate as added latency when a
receiver goes silent, not what a generous export would like.

The hook test suite pins `LIVESPEC_SANDBOX_OTEL_ENDPOINT` at a port nothing
listens on (`tests/hooks/conftest.py`), so fixture commands that never ran cannot
publish synthetic verdicts — and every test in that tree exercises the same
fail-open path an operator gets on a receiver-less host.
