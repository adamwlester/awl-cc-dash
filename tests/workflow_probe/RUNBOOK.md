# Workflow-engine probe — RUNBOOK (the deal for a driver agent)

This package probes the Claude Code **workflow engine** (the `Workflow` tool / `/workflows` surface) from the outside, to prove the dashboard can render workflow runs from the files they drop on disk. It answers the open questions in [`dev/notes/research/claude-code-workflow-orchestration-report-2026-07-04.md`](../../dev/notes/research/claude-code-workflow-orchestration-report-2026-07-04.md).

**Read this first — the one constraint that shapes everything.** A workflow can only be launched by a Claude session issuing the `Workflow` tool call; there is no out-of-process launch API. So the pytest probe is a pure **observer** — it cannot start the thing it watches. **You, the driver agent, are the automation the human isn't.** You launch the subject workflow, point the probe at the run, and read back the findings. Any agent can follow these steps cold; no human in the loop.

Files in this package:

| File | What it is |
|------|------------|
| `test_workflow_orchestration_live.py` | The probe. Watches a run (live if in-flight), validates the manifest schema, reconciles manifest ↔ journal ↔ per-agent transcripts, and writes findings to `tests/log/`. |
| `subject_workflow.js` | The deterministic subject to launch — exercises `phase`/`parallel`/`pipeline`/`log`/`schema` and runs long enough (staggered) to be caught mid-flight. |
| `RUNBOOK.md` | This file. |

---

## Part 1 — the artifact/schema/timing probe (fully agent-driven)

**Preconditions:** run all commands **from the repo root**, and the repo-root **`.venv` must already exist** (create it once per [`../README.md`](../README.md): `python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt`). Or invoke via `tests\run.ps1 -m integration`, which resolves the local `.venv` for you.

Do these in order. Steps 1 and 2 should be back-to-back so the probe catches the run **live** (that's what settles the manifest-timing question).

**Step 1 — launch the subject workflow.** Call the `Workflow` tool with the fixture script by path (absolute path is safest):

```
Workflow({ scriptPath: "c:/Users/lester/MeDocuments/AppData/Anthropic/awl-cc-dash/tests/workflow_probe/subject_workflow.js" })
```

It returns **immediately** (the run is async) with a block that includes `Transcript dir: <...>\subagents\workflows\wf_XXXX`. **Copy that transcript dir.**

**Step 2 — immediately run the probe against that run, in live-watch mode.** Do this in your very next tool call so the run is still in flight:

```powershell
$env:AWLCC_WF_TRANSCRIPT_DIR = "<the Transcript dir from step 1>"; .\.venv\Scripts\python.exe -m pytest tests/workflow_probe -m integration -v
```

**`AWLCC_WF_TRANSCRIPT_DIR` is load-bearing — it is the only thing that binds the probe to the run you just launched.** Run the `$env:` assignment and the `pytest` call in a **single shell invocation** (as the one-line command above), because in many harnesses shell state does not persist between separate tool calls. If the var is lost, the probe silently falls back to auto-discovering the *newest* run under `~/.claude/projects` — usually the one you just launched, but a *wrong-run* risk if another workflow is newer. The probe logs `RESOLVED run_id=… workflowName=…` and the findings header echoes the run id + name — **eyeball that it says `wf-probe-subject`** to be sure it observed your launch.

The probe polls the run to completion (default up to 180s), validates everything, and writes `tests/log/workflow_probe_findings_latest.txt`. It blocks until the run finishes — that's expected.

**Step 3 — read the verdict.** Open `tests/log/workflow_probe_findings_latest.txt`. It states, in plain terms: whether `journal.jsonl` streams incrementally, whether the manifest is written **LIVE** or **COMPLETION-ONLY**, plus the schema/reconciliation outcome. Paste that back.

### Post-hoc mode (no launch — schema + reconciliation only)

To validate structure against an **existing** completed run (manifest-timing will read INCONCLUSIVE), just point the probe at any run dir:

```powershell
$env:AWLCC_WF_TRANSCRIPT_DIR = "C:\Users\lester\.claude\projects\<proj>\<sessionId>\subagents\workflows\wf_XXXX"
.\.venv\Scripts\python.exe -m pytest tests/workflow_probe -m integration -v
```

If you leave `AWLCC_WF_TRANSCRIPT_DIR` unset, the probe auto-discovers the most recently modified workflow run under `~/.claude/projects` (it logs which one). If there are none, it **skips** and prints these instructions.

### Knobs (env vars)

| Var | Default | Meaning |
|-----|---------|---------|
| `AWLCC_WF_TRANSCRIPT_DIR` | *(auto-discover)* | The `subagents/workflows/wf_XXXX` dir to observe. |
| `AWLCC_WF_WATCH_SECS` | `180` | Max seconds to watch a live run. |
| `AWLCC_WF_POLL_SECS` | `0.5` | Poll interval. |
| `AWLCC_WF_STABLE_SECS` | `12` | Stop early if the journal is stable this long and a manifest exists but never reached a terminal status. |

---

## Part 2 — the approval gate (SETTLED — confirmation optional)

**This question is answered (2026-07-04); you don't need to re-run the experiment unless you're confirming it.** Whether an approval dialog appears is an interactive-harness behavior a script can't assert, so this was settled by inspection + observed behavior, not by the probe.

**Answer — the gate is pre-authorizable via one setting.** The lever is the global user setting **`skipWorkflowUsageWarning`** in `~/.claude/settings.json` (a top-level boolean — NOT a `permissions` allow-entry for the `Workflow` tool; there is no such entry). With it `true` (as on this machine), dynamic workflows launch with **no** blocking dialog — every `Workflow` call in the VS Code session here ran instantly, unattended. With it absent/`false`, the terminal CLI shows the full "Run a dynamic workflow?" dialog and **blocks on a human** (a ~108 s tool-call→result gap was observed even under `acceptEdits`). So an autonomous dashboard agent can run dynamic workflows unattended by ensuring that setting is on.

**Optional confirmation experiment** (only if you want to prove causation — it flips global config, so back up and restore):
- Set `skipWorkflowUsageWarning: false` in `~/.claude/settings.json`, relaunch a dynamic workflow, and confirm the `Workflow` tool call now **blocks / delays** (in a terminal CLI you'll see the dialog; in VS Code, watch for a stall). Then **restore it to `true`.**
- Record the environment (terminal CLI vs VS Code vs SDK/headless) and whether the gate blocked, at the bottom of `tests/log/workflow_probe_findings_latest.txt`. That's the last piece of open question #1 in the research report.

---

## Notes

- **Read-only + self-cleaning.** The probe never mutates a workflow. Workflow artifacts live in Claude Code's own session store (`~/.claude/projects/...`), not the repo — nothing to clean up here. The probe's own outputs go to `tests/log/` (gitignored).
- **Cost.** Each workflow subagent carries ~40k tokens of fixed context overhead; the subject launches ~10 agents (~0.4–0.5M tokens). Don't loop it needlessly.
- **Markers.** The probe is `integration`+`slow` (it needs a real run), so the hermetic run (`-m "not integration and not slow"`) deselects it — it only imports the stdlib, so collection stays clean.
