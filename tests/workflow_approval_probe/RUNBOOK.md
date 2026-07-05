# Workflow-approval-interception probe — RUNBOOK (the deal for a driver agent)

This package answers the question the 2026-07-04 workflow session ended on: **can the dashboard intercept a Claude Code workflow at its approval gate — read the full preview (name / description / phases / full script) — and round-trip an Approve/Reject decision back to the agent?** It is the plumbing spike for a future "review a workflow before it runs" card. It extends the open questions in [`dev/notes/research/claude-code-workflow-orchestration-report-2026-07-04.md`](../../dev/notes/research/claude-code-workflow-orchestration-report-2026-07-04.md).

**The good news: this one is (almost) fully self-driving.** Unlike the sibling [`tests/workflow_probe/`](../workflow_probe/) observer — which can't launch a workflow and needs a driver agent to start one — this spike drives its OWN tab-less WSL bridge Claude session, tells *that* session to issue a `Workflow` tool call, and intercepts it. So the pytest process is both the launcher (via the bridge) and the interceptor. **You run one command; no human, no separate launch step.**

| File | What it is |
|------|------------|
| `test_workflow_approval_intercept_live.py` | The probe. Stands up an in-test HTTP "capture/verdict" server (the stand-in dashboard), drives a bridge session to call `Workflow`, and observes: does a hook fire, does it carry the full preview, does deny abort / allow launch, does the on-screen dialog render. Writes findings to `tests/log/`. |
| `subject_workflow.js` | The tiny throwaway workflow whose approval gate gets intercepted — ONE trivial agent, so an Approve run launches almost nothing. Its distinctive `meta` is what the interceptor asserts it can read. |
| `RUNBOOK.md` | This file. |

---

## How to run (one command, live tier)

**Preconditions:** run from the repo root; the repo-root **`.venv` must exist** (`python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt`); and **WSL2 + the Ubuntu bridge + the Claude CLI inside WSL** must be available (this drives a real bridged Claude session). No sidecar is needed — the probe is self-contained.

```powershell
tests\run.ps1 -m integration tests/workflow_approval_probe
# or, directly:
.\.venv\Scripts\python.exe -m pytest tests/workflow_approval_probe -m integration -v
```

It runs four short live scenarios back-to-back (reject / approve / isolation / screen), each spinning up its own tab-less bridge session, and takes a few minutes. Then **read `tests/log/workflow_approval_findings_latest.txt`** — it states, in plain language, which channel fired, what preview fields were readable, and whether Approve/Reject round-tripped. Paste that back.

If a precondition is missing (no WSL, host gateway unreachable, or the agent never issues a `Workflow` call) the affected tests **skip with an actionable message** — they never fabricate green.

---

## What it actually does (so you can trust the result)

For each scenario the probe:
1. Starts a tiny HTTP server on an ephemeral port (this is the **stand-in dashboard** — it records every hook POST and answers with the Approve/Reject verdict under test).
2. Creates a **tab-less** (`show=False`) WSL bridge session named `wfgate-<uuid8>`, injecting a per-agent `--settings` file that (a) wires a `PreToolUse` hook on the `Workflow` tool (and a `.*` catch-all) pointing at the capture server via the WSL→Windows host gateway, and (b) sets `skipWorkflowUsageWarning` per-session.
3. Prompts that session to call the `Workflow` tool with `subject_workflow.js` verbatim.
4. Observes: the captured hook payload (does it carry `tool_input.script` with the full `meta`?), the WSL filesystem (did a `…/subagents/workflows/wf_*` run dir appear?), and the pane (did the built-in dialog render?).
5. Tears down: closes **only its own** session and removes its scratch dir. **Never** `kill-server`.

The four scenarios: **hook_deny** (verdict=deny, popup suppressed — should abort, launches nothing), **hook_allow** (verdict=allow, popup suppressed — should launch the one-agent subject), **preempt** (hook present with the popup switch left ON — isolates whether the hook verdict preempts the built-in dialog, so "hook is the sole gate" isn't confounded with the suppression switch), **screen** (no hook, popup forced on — should render the dialog to scrape/reject with a keystroke).

---

## Safety / isolation (why this is unattended-safe)

- **No global config is touched.** The bridge Claude runs inside WSL2 against its OWN `~/.claude`; the popup switch (`skipWorkflowUsageWarning`) is set per-session in the agent's `--settings`, never in your Windows `~/.claude/settings.json`. (Whether that per-session override is honored is itself one of the findings.)
- **Own bridge, non-destructive teardown.** Uses its own `TmuxBridge()`, unique session names, and closes only its own sessions — it never requests the shared `bridge`/`live_session` fixtures (those call `tmux kill-server` and would kill sibling agents) and never calls `shutdown()`.
- **Tab-less only.** `show=False` — no Windows Terminal tab is ever opened.
- **Cost-guarded.** The subject is one trivial agent (no fan-out). Worst case is a few single-agent launches (~40–80k tokens each): the reject run launches nothing when deny is honored; the approve and isolation runs each launch one cheap agent; the screen run launches nothing unless the built-in dialog fails to gate. Don't loop it needlessly.

---

## Hermetic-run safety

The module is `integration`+`slow` and stdlib-only, so the everyday hermetic run (`tests\run.ps1 -m "not integration and not slow"`) **deselects it** and collection stays clean even on a machine with no WSL. There is no second `conftest.py`; it uses the shared `tests/conftest.py`.
