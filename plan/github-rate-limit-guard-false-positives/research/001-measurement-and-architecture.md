# github_rate_limit_guard — measured false-positive rate, and where the guard belongs

Opened 2026-08-26. Measurement and architecture finding that motivates this plan.

## 1. The defect, measured

`livespec-driver-claude/.claude-plugin/hooks/github_rate_limit_guard.py` is a
PreToolUse hook on `Bash` that denies loop/sleep + `gh` conjunctions. It denies
far more than it should.

Method: Honeycomb (`agent-activity` / `claude-code`) supplies the trip counts;
command text lives on a different span than the hook event, so the 7-day Bash
corpus was taken from local transcripts and the real `_deny_reason` was replayed
over it. The populations match to 4 events (Honeycomb 73,158 `PreToolUse:Bash`
tool calls; corpus 73,162), so the replay measures the same traffic.

Window: 2026-08-19 .. 2026-08-26.

| | 7 days |
| --- | --- |
| Bash commands | 73,162 |
| Guard denials | 615 (0.84%) |
| Sessions hitting >=1 denial | 255 |
| Sessions hitting >=1 FALSE denial | 120 |

Denial breakdown:

| Verdict | n | % |
| --- | --- | --- |
| TRUE — real loop/xargs + real `gh` | 366 | 59.5% |
| FALSE — no `gh` invocation anywhere; `gh` only inside a string, path, or regex | 109 | 17.7% |
| FALSE — already uses the sanctioned `gh api --cache` | 96 | 15.6% |
| FALSE? — one `sleep`, no loop: a single poll, not a burst | 44 | 7.2% |

**249/615 = 40.5% false**, counting only the first two buckets (47.6% including
the sleep-only cases). Peak day 2026-08-22: 166 denials, 53 of them false.

## 2. Two root causes

**(a) The prescribed remedy is unreachable.** The deny message says looped reads
"must use the cached alternative `gh api --cache <duration>`". But
`_has_read_gh_call` (lines 114-120) returns True for ANY non-mutating `gh api`,
`--cache` included. Probing the live hook:

| Command shape | Guard |
| --- | --- |
| `for r in a b c; do gh api --cache 10m ...; done` — the prescribed fix | DENY |
| `sleep 30; gh api --cache 5m ...` — one cached read | DENY |
| `grep -rnE "gh api\|for loop" .` — no `gh` at all | DENY |
| `for p in $(seq 1 50); do gh pr view $p; done` | DENY (correct) |
| `cat ids \| xargs -I{} gh api -X PATCH ...` | DENY (correct) |

An agent that follows the instruction it is given is denied for following it.

**(b) No shell awareness.** `_CMD_POS` correctly anchors loop keywords to command
position, but under `re.MULTILINE` a heredoc body, a quoted Python script, or a
`grep` pattern all look like command position. 31 of the 109 no-`gh` false
positives are heredoc/quoted-script bodies. Both denials hit while writing this
note were of this shape.

This is the same defect `livespec-driver-claude-mu5` recorded on 2026-08-05. That
item's regex quotes are now stale — command-position anchoring has since landed —
but its `--cache` and quoted-region findings stand, and its acceptance criteria
remain correct.

## 3. Where the guard belongs

**Not `livespec-runtime`.** The hook's own contract forbids it (lines 16-18):
self-contained under bare system `python3`, no virtualenv, stdlib only.
`livespec-driver-claude` vendors nothing — no `_vendor/`, no `.vendor.jsonc`. A
hook fires before any venv exists; importing `livespec_runtime` would break every
governed repo on the next `ensure-plugins`.

**Core `livespec` carries the contract, not the body.**
`livespec/SPECIFICATION/contracts.md` §"Driver-shipped hooks": *"this section
states the required hook surfaces and their behavioral disciplines; the script
implementations and their tests live in the Driver repo."* Each Driver ships hooks
in its runtime's native mechanism.

**The decision function should be shared; the adapter should not.**
`_deny_reason(command: str) -> str | None` is pure, stdlib-only, and
harness-agnostic. Core already names the mechanism: a canonical body single-sourced
from `livespec-dev-tooling`, asserted byte-identical in each Driver bundle. That
precedent is built — `install_no_shadow_ledger.py`,
`checks/no_shadow_ledger_body_identical.py`, `checks/no_shadow_ledger_body_typechecks.py`.

Reach, by runtime:

| Driver | Hook mechanism | Language | Can share the Python body? |
| --- | --- | --- | --- |
| `livespec-driver-claude` | `.claude-plugin/hooks/` + `hooks.json` | Python | yes |
| `livespec-driver-codex` | `livespec/hooks/` `pre_tool_use` | Python | yes |
| `livespec-driver-pi` | `extensions/*.ts` `tool_call` | TypeScript | **no — behavioral port** |

pi needs a TypeScript port, anti-drift enforced by a shared test-vector corpus
rather than byte-identity. This is exactly the footgun-guard pattern core already
uses (Claude Python, Codex `livespec_footgun_guard.py`, pi `livespec-footgun-guard.ts`
— three ports, one contract).

## 4. The gap this surfaced

`github_rate_limit_guard.py` **is not in core's spec at all.** §"Driver-shipped
hooks" says "The bundle carries four hooks" and lists the auto-memory redirect, the
Playwright guard, and the two Stop WARN hooks. The rate-limit guard is not among
them (neither is `tmux_fleet_guard.py`). It ships to every adopter — the Driver
enables at project scope — as an unspecified, uncontracted deny surface.

Core does already carry the policy rationale, in
`non-functional-requirements.md` §"GitHub App request budget" (budget is a finite
shared resource; automated paths MUST distinguish primary exhaustion from secondary
limits). The guard is an unlinked enforcement of a rule core already states.

## 5. Sequencing — why the fix precedes the reach

The 40.5% figure is **Claude-only**. Codex and pi have no rate-limit guard today.
Extending the guard fleet-wide now would ship a known-40%-false deny surface to two
runtimes that currently have none.

That is the failure this repo already paid for: the Railway decoupling landed in
`46c5dab`, turned five repos red, and was reverted in `f4247110`; the standing
constraint from that episode is adoption first, then arming. So:

1. Fix and ship in `livespec-driver-claude`. Measurable: FP rate drops from 40.5%
   toward zero against this same replay corpus, with the 366 true positives still
   denying.
2. Hoist the proven decision function to `livespec-dev-tooling` as the canonical body.
3. Contract the surface in core via `/livespec:propose-change`.
4. Port to Codex (Python adapter) and pi (TypeScript behavioral port).

Doing 3 before 1 spreads a defect. Doing 1 before 2 means one refactor, not two.

## 6. Reproducing the measurement

The replay harness is session scratch, not committed. It: reads `tool_use` blocks
where `name == "Bash"` from `~/.claude/projects/*/*.jsonl` modified within 7 days,
imports `_deny_reason` from the live hook by file path, and buckets each denial by
whether a `gh` invocation appears at command position and whether `--cache` is
present. Work-item `W4` promotes this into a committed fixture.
