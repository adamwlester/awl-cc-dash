# Claude Code Workflows & Subagent Orchestration — how the `/workflows` engine actually works

Date: 2026-07-04
Author: research pass driven from real workflow runs (Claude Code v2.1.201)
Related: [s10-research-22-subagent-management.md](s10-research-22-subagent-management.md) · [research-subagent-architecture.md](research-subagent-architecture.md) · [`docs/ARCHITECTURE.md`](../../../docs/ARCHITECTURE.md)

> **Update 2026-07-04 — several open questions now answered empirically.** A repeatable observer probe was built and run live against fresh workflows: [`tests/workflow_probe/`](../../../tests/workflow_probe/) (driver protocol in [RUNBOOK.md](../../../tests/workflow_probe/RUNBOOK.md), spike in [test_workflow_orchestration_live.py](../../../tests/workflow_probe/test_workflow_orchestration_live.py)). Settled: **(#2) the manifest is written COMPLETION-ONLY — `journal.jsonl` is the live signal to tail**; **(#1) the approval gate is pre-authorizable** via the global setting `skipWorkflowUsageWarning: true`; and a new detail — **schema (structured-output) agents store their `result` as a native JSON object in `journal.jsonl`** (the manifest keeps a JSON-string preview). See §11 for the per-question detail.
>
> **Update 2026-07-04 (later) — the review-before-approve question is answered too.** A second, interception spike ([`tests/workflow_approval_probe/`](../../../tests/workflow_approval_probe/), 8/8 green live) proves the dashboard can **catch a workflow at its approval gate, read the full preview, and round-trip Approve/Reject to the agent** via a PreToolUse hook on the `Workflow` tool — a hook **deny aborts** / **allow launches** (A/B-proven the verdict alone controls launch), the hook **preempts** the built-in dialog so the dashboard can be the sole gate, and the on-pane dialog works as a fallback. See §10 E and §11 #6.

## 0. TL;DR (plain-language first)

Claude Code has a built-in **workflow engine**: a way for the assistant to write a small JavaScript "orchestration script" that spins up a fleet of throwaway helper agents (subagents), runs them in parallel or in stages, and gathers their answers back into one result. You saw it in your terminal test: Claude wrote a script, you got an **approval dialog** ("Run a dynamic workflow?"), you approved, three tiny agents ran, and `/workflows` showed a live progress tree.

Three things are worth internalizing, because they're what make this useful (or not) for our dashboard:

1. **The script is the brain; the agents are dumb hands.** Agents don't talk to each other. The *script* (plain JS) collects agent A's text output into a variable and pastes it into agent B's prompt. All coordination logic lives in the script, run inside the Claude Code process — not in the agents.
2. **It leaves a clean, structured paper trail on disk.** Every run writes a machine-readable **run manifest** (`<runId>.json`) plus an append-only **journal** (`journal.jsonl`) and a **full transcript per subagent**. This is exactly the kind of structured, file-based telemetry our sidecar already knows how to tail — and it's *far* cleaner than scraping subagent activity out of a tmux pane (the hard problem [s10-research-22-subagent-management.md](s10-research-22-subagent-management.md) wrestled with).
3. **It's a fan-out tool, not an interactive-agent tool.** Workflow subagents are headless, one-shot, and un-attachable — the opposite of the dashboard's "one interactive `claude` per agent" model. They're for deterministic burst parallelism (review N files, research M sources), not for long-lived steerable agents.

The rest of this doc is the detailed reference: the exact lifecycle, the approval gate, the script API, the subagent model, the on-disk file schemas, how the `/workflows` UI maps to those files, and a concrete read on how awl-cc-dash could use all of it.

## 1. Evidence base

This isn't from docs — it's reconstructed from two real runs on this machine, both Claude Code `2.1.201`, both fanning out three subagents on `claude-opus-4-8`:

| Run | Where | Workflow | Task ID / Run ID | Artifacts read |
|-----|-------|----------|------------------|----------------|
| **A** — your terminal test | CLI session `ed34df81` | `approval-demo` (crimson/teal/goldenrod color lines) | `wf4iqahwy` / `wf_84c4a659-449` | Full session transcript `ed34df81….jsonl` (the tool call + the launch result) |
| **B** — this VS Code session | session `5b035767` | `approval-prompt-demo` (fun facts about 7 + blue) | `wgbn5ybfu` / `wf_ae75e5d5-a0c` | Run manifest, journal, all three subagent transcripts + meta files, persisted script |

Run A gives us the **human-facing approval handshake** (the dialog you screenshotted, and the ~108-second blocking gap in the transcript while you decided). Run B gives us the **complete on-disk anatomy** of a finished run. Together they cover the whole thing.

Paths below that live under `C:\Users\lester\.claude\projects\…` are **outside the repo** (Claude Code's own session store), so they're written as inline code, not repo links.

## 2. The lifecycle, end to end

Here's the full arc of a workflow, with the observed evidence for each step.

**Step 1 — Claude authors a script and calls the `Workflow` tool.** In Run A the assistant emitted a normal `tool_use` block:

```json
{ "type":"tool_use", "name":"Workflow",
  "input": { "script":"export const meta = {…}\n\nphase('Write')\n…",
             "description":"Tiny 3-subagent demo to show the workflow approval prompt" },
  "caller": { "type":"direct" } }
```

Note the tool input has **two** description-like fields: `input.description` (a tool-call-level blurb) and, *inside the script*, `meta.description` (the one the approval dialog and `/workflows` actually show). There's also a `caller:{type:"direct"}` marker recording how the workflow was invoked.

**Step 2 — the harness shows a blocking approval dialog.** This is the gate you asked about. In Run A the `tool_use` was stamped `19:07:26Z` and its result didn't arrive until `19:09:14Z` — a **~108-second gap** that is exactly you sitting at the "Run a dynamic workflow?" dialog. Critically, that CLI session was in `acceptEdits` permission mode (recorded at the top of the transcript) and **still prompted** — so workflow approval is a *separate* gate from file-edit permissions. Details in §3.

**Step 3 — on approval, the workflow launches asynchronously and returns immediately.** The tool result is fire-and-return:

```json
{ "status":"async_launched", "taskId":"wf4iqahwy", "taskType":"local_workflow",
  "workflowName":"approval-demo", "runId":"wf_84c4a659-449",
  "transcriptDir":"…\\subagents\\workflows\\wf_84c4a659-449",
  "scriptPath":"…\\workflows\\scripts\\approval-demo-wf_84c4a659-449.js" }
```

The parent conversation is **not** blocked while the workflow runs — it gets a `taskId` and moves on. Two IDs are minted: a short **`taskId`** (`wf4iqahwy` / `wgbn5ybfu`) for the task/notification system, and a **`runId`** (`wf_…`) that names the on-disk directories and is what you pass back to *resume*.

**Step 4 — subagents run; disk fills in live.** Each `agent()` call becomes one sidechain subagent. The append-only `journal.jsonl` gets a `started` line when an agent launches and a `result` line when it returns (§6, §7). `/workflows` reads this live stream to animate the progress tree.

**Step 5 — completion fires a task notification back to the parent.** When the script's top-level `return` resolves, the parent conversation receives a `<task-notification>` carrying the final return value (the same object the script returned), plus usage stats. In Run B the notification carried `{facts:[…], summary:"…"}`, `agent_count:3`, `subagent_tokens:119287`, `duration_ms:7050`.

**Step 6 (optional) — resume.** Because every agent call is content-hashed (§7), re-invoking `Workflow` with `{scriptPath, resumeFromRunId}` replays unchanged agents from cache and only re-runs edited/new ones. This is the "edit the post-processing without paying for the agents again" path.

## 3. The approval gate (what you were testing)

**What triggers it.** Any `Workflow` tool call that runs an *ad-hoc* script — the harness calls this a **"dynamic workflow."** The dialog header in your screenshots was literally *"Run a dynamic workflow?"*. (Saved/named workflows — §8 — presumably have their own, lighter gating, but we have none on disk to confirm.)

**It is a genuine blocking gate, and it's independent of edit permissions.** The 108-second tool_use→result gap in Run A, under `acceptEdits` mode, is the proof: the workflow engine prompts the human and *waits*, regardless of how permissive the file-edit settings are. This matters enormously for autonomous/unattended dashboard runs (§9, §10).

**What the dialog shows** (reconstructed from your three screenshots):

- **Initial view** — title *"Run a dynamic workflow?"*, the `meta.description` line, the **phase list** rendered from `meta.phases` (each `title` + `detail`), and a yellow **cost warning**: *"Dynamic workflows can use a lot of tokens quickly by running many subagents in parallel — which counts against your usage limit. Stop a running workflow at any time with /workflows, or disable dynamic workflows in /config."* Options: **1. Yes, run it · 2. View raw script · 3. No**. Footer: *"Esc to cancel · Tab to amend · ctrl+g to edit script in $EDITOR"*.
- **"View raw script"** expands the entire script inline (syntax-highlighted) and swaps option 2 to *"View workflow summary"* to toggle back. So the human can read every line before approving — the script is never hidden.
- The **`ctrl+g` → `$EDITOR`** affordance means a human can *hand-edit the script* before it runs. **`Tab` to amend** is a lighter revise path.

**The single lever that controls the dialog's wording is `meta`.** The `name`, `description`, and `phases` at the top of the script are the entire human-readable surface. For any real (expensive) workflow, that block is the thing a human reads to decide yes/no — so it's worth writing honestly.

**Config kill-switch.** The warning names `/config` as the place to **disable dynamic workflows** entirely. That's a global on/off we should know about (and possibly want, per-profile, for locked-down runs).

## 4. The `Workflow` tool contract (the script API)

A workflow script is **plain JavaScript** (not TypeScript) executed inside the Claude Code process, in an async context. It must open with a pure-literal `export const meta = {…}` and then use a set of injected globals. Here's Run B's script annotated:

```js
export const meta = {                      // ── REQUIRED, pure literal (no vars/calls)
  name: 'approval-prompt-demo',            //    id-ish name
  description: '…demo the workflow approval prompt',  // shown in the dialog + /workflows
  phases: [                                //    one entry per phase() call (title + detail)
    { title: 'Fan out',  detail: 'two tiny agents each return a one-sentence fun fact in parallel' },
    { title: 'Summarize', detail: 'one agent stitches the two facts into a short note' },
  ],
}

phase('Fan out')                           // ── start a progress group
const answers = await parallel([           // ── BARRIER: run both, wait for both
  () => agent('…fun fact about the number 7…', { label: 'fact:seven', phase: 'Fan out' }),
  () => agent('…fun fact about the color blue…', { label: 'fact:blue',  phase: 'Fan out' }),
])

phase('Summarize')
const summary = await agent(               // ── a third agent, fed the two prior results
  `Combine these two facts…\n1) ${answers[0]}\n2) ${answers[1]}`,   // ← coordination happens HERE
  { label: 'summary', phase: 'Summarize' }
)

return { facts: answers, summary }         // ── becomes the task-notification payload
```

The injected script hooks (from the tool contract; `agent`/`parallel`/`phase`/`log` all directly observed in the two runs):

| Hook | What it does |
|------|--------------|
| `agent(prompt, opts?)` | Spawn one subagent. Returns its **final text** as a string. With `opts.schema` (a JSON Schema) it instead forces a structured `StructuredOutput` tool call and returns the validated object. `opts`: `label`, `phase`, `schema`, `model`, `effort`, `isolation:'worktree'`, `agentType`. Returns `null` if the agent is skipped or dies after retries. |
| `parallel(thunks)` | Run an array of `() => Promise` concurrently and **wait for all** (a barrier). A thrown/failed thunk resolves to `null` (call never rejects) — so you `.filter(Boolean)`. |
| `pipeline(items, …stages)` | Run each item through all stages independently with **no barrier between stages** — item A can be in stage 3 while item B is still in stage 1. The recommended default for multi-stage work. Each stage callback receives **`(prevResult, originalItem, index)`** — *empirically confirmed* by the probe's subject run (stage-2 labels `tighten#0..2` prove the `index` arg reaches later stages; the topic text in each stage-2 prompt proves `originalItem` is threaded through). For the first stage `prevResult === originalItem`. |
| `phase(title)` | Start a progress group; subsequent `agent()` calls are bucketed under it in `/workflows`. |
| `log(msg)` | Emit a narrator line above the progress tree (Run A's script called `log('Collected 3 of 3 lines')`). |
| `args`, `budget`, `workflow(...)` | `args` = the value passed to the tool's `args` input; `budget` = the turn's token target (`total`/`spent()`/`remaining()`); `workflow()` runs another (saved) workflow inline. None exercised in our two runs. |

Constraints worth remembering: `Date.now()`/`Math.random()`/argless `new Date()` **throw** inside scripts (they'd break deterministic resume); concurrency is capped at `min(16, cores−2)` with excess queued; a single `parallel`/`pipeline` takes ≤4096 items; lifetime cap 1000 agents.

## 5. How subagents are instructed and how they communicate

This is the part most likely to be misunderstood, so it's worth stating precisely — and our evidence nails it down.

**Each `agent()` call is an isolated, one-shot sidechain.** From Run B's subagent transcripts, every workflow subagent's session file (`agent-<id>.jsonl`) begins with `isSidechain:true` and a single user message whose content is **exactly the prompt string** passed to `agent()`:

```json
{ "isSidechain":true, "agentId":"a14da4af55f3df8b7", "type":"user",
  "message":{ "role":"user", "content":"Reply with a single short fun fact about the number 7. One sentence only, no preamble." } }
```

There is **no parent conversation history** carried in — the subagent sees only its prompt. Its `.meta.json` tags it `{"agentType":"workflow-subagent","spawnDepth":1}`, and its assistant messages are stamped `attributionAgent:"workflow-subagent"` for telemetry.

**The return value is the subagent's final assistant text.** No tool call, no wrapper — the last thing the model says *is* the string `agent()` resolves to. (The harness instructs the subagent that "your final message is the return value, not something a human reads," per the tool contract; that system framing is applied at the API layer and isn't itself logged as a transcript line — the transcript starts at the user prompt.) In Run B, subagent `a14da4af…` ended with the seven-fact sentence, and that identical string is what landed in `journal.jsonl` as its `result`.

**Agents do not talk to each other — the script is the message bus.** The only way one agent's output reaches another is the orchestrating JS collecting it into a variable and interpolating it into the next prompt. The manifest proves it: the "summarize" agent's recorded `promptPreview` literally contains the two prior facts, string-pasted in by the script. There is no agent-to-agent channel; there is only *script-mediated* data flow.

**Workflow subagents are still full-capability agents, just headless.** Their transcripts show they receive the **entire deferred-tools list** (all MCP tools via ToolSearch) and the **full skill listing** — they're not sandboxed to a tiny toolset. What makes them "lightweight" is that they're **one-shot, headless, and un-attachable**, not that they're weak. They also **skip the `using-superpowers` skill gate** (the skill's `<SUBAGENT-STOP>` clause tells dispatched subagents to skip it), so they get straight to the task. Our two demos happened to make `0` tool calls, but a workflow agent *can* use Bash, Read, MCP tools, etc.

**Model & effort.** Subagents inherit the workflow's `defaultModel` (`claude-opus-4-8` in both runs) unless a call overrides via `opts.model`/`opts.effort`. The manifest records the resolved `model` per agent.

## 6. Structured output (the schema option)

Not exercised in our two text-only demos, but central to real use: passing `opts.schema` (a JSON Schema) to `agent()` forces the subagent to emit through a `StructuredOutput` tool, and the call returns the **validated object** instead of a raw string. Validation happens at the tool-call layer, so the model is made to retry on a schema mismatch. This is how you get reliable typed data out of a fan-out (findings lists, verdicts, extracted fields) rather than parsing prose. For the dashboard this is the difference between "N agents returned paragraphs" and "N agents returned rows I can render in a table."

## 7. On-disk anatomy (the artifacts we can consume)

Every run materializes under the **session's own directory**. For Run B (session `5b035767…`, runId `wf_ae75e5d5-a0c`):

```
<session>/
├─ workflows/
│  ├─ scripts/
│  │  └─ approval-prompt-demo-wf_ae75e5d5-a0c.js   ← the script, persisted verbatim
│  └─ wf_ae75e5d5-a0c.json                          ← RUN MANIFEST (full state + result)
└─ subagents/workflows/wf_ae75e5d5-a0c/
   ├─ journal.jsonl                                 ← append-only live event log
   ├─ agent-a14da4af55f3df8b7.jsonl                 ← full transcript, subagent 1  (~37 KB)
   ├─ agent-a14da4af55f3df8b7.meta.json             ← {"agentType":"workflow-subagent","spawnDepth":1}
   ├─ agent-a8799e7a9403cd7cf.jsonl                 ← subagent 2
   ├─ agent-a8799e7a9403cd7cf.meta.json
   ├─ agent-af85bb4fa5443edfe.jsonl                 ← subagent 3
   └─ agent-af85bb4fa5443edfe.meta.json
```

### 7a. `journal.jsonl` — the live signal

Append-only, one JSON object per line, two event types:

```json
{"type":"started","key":"v2:375d59…","agentId":"a14da4af55f3df8b7"}
{"type":"result", "key":"v2:945aa4…","agentId":"a8799e7a9403cd7cf","result":"Blue light scatters…"}
```

The **`key`** is a `v2:<sha256>` content hash of the agent's `(prompt, opts)` — this is the **resume/cache key**. On a `resumeFromRunId` replay, a matching key returns the cached `result` instantly instead of re-running the agent. Because it's append-only and written as agents start/finish, `journal.jsonl` is the **canonical live progress feed** — the thing to tail for real-time observation. **This is now confirmed empirically** (the probe watched a live run and saw the file stream `started`/`result` lines incrementally, with `started` count leading `result` count while agents were in flight), and it's the *only* live disk signal — see §7b on the manifest's completion-only timing.

One storage detail the probe surfaced: for a **schema (structured-output) agent**, the journal's `result` is a **native JSON object**, not a string — e.g. `{"type":"result","key":"v2:…","agentId":"…","result":{"headline":"…","sceneCount":3,"mood":"calm"}}`. Plain-text agents store `result` as a string. The manifest, by contrast, keeps a JSON-**string** preview in `resultPreview` for the same agent. A consumer must handle both shapes.

### 7b. `<runId>.json` — the run manifest (the rich one)

This single file is effectively the **entire data model behind `/workflows`**, and it's the most valuable artifact for us. Top-level fields observed: `runId`, `taskId`, `script`, `scriptPath`, `result`, `agentCount`, `logs`, `durationMs`, `summary`, `workflowName`, `status`, `startTime`, `phases`, `defaultModel`, `totalTokens`, `totalToolCalls`, and — the centerpiece — **`workflowProgress[]`**, an ordered array mixing two record types:

```jsonc
// phase markers:
{ "type":"workflow_phase", "index":1, "title":"Fan out" }

// per-agent records (one per agent() call), e.g.:
{ "type":"workflow_agent", "index":1, "label":"fact:seven",
  "phaseIndex":1, "phaseTitle":"Fan out",
  "agentId":"a14da4af55f3df8b7", "model":"claude-opus-4-8",
  "state":"done", "attempt":1,
  "queuedAt":…, "startedAt":…, "lastProgressAt":…, "durationMs":2576,
  "tokens":39737, "toolCalls":0,
  "promptPreview":"Reply with a single short fun fact about the number 7…",
  "resultPreview":"Seven is the only single-digit number…" }
```

That schema is a *ready-made* contract for a dashboard "Workflows" panel — phase grouping, per-agent state/model/tokens/duration, and prompt/result previews, all pre-computed. (Likely a completion snapshot; the *live* equivalent is `journal.jsonl` plus whatever in-memory stream `/workflows` reads — see §11 open questions.)

### 7c. `agent-<id>.jsonl` — full per-subagent transcript

The complete sidechain conversation for each agent (~37 KB even for a one-sentence answer, because it includes the full injected tool/skill context). Useful for deep debugging of a specific agent; probably too heavy to ingest wholesale for a dashboard summary — the manifest's `promptPreview`/`resultPreview` are the lightweight substitute.

## 8. `/workflows` UI ↔ manifest mapping, and dynamic vs saved

Your third screenshot maps **one-to-one** onto the manifest:

| `/workflows` UI element | Manifest source |
|-------------------------|-----------------|
| Header `approval-demo` + description | `workflowName` + `meta.description` |
| `3/3 agents · 5s · done` | `agentCount` / `status` / `durationMs` |
| Left column phase tree (`Write 3/3`, `Gather`) | `workflow_phase` entries + child counts |
| Agent rows `write:crimson … Opus 4.8 … 40.8k tok · 1s` | `workflow_agent` `label` / `model` / `tokens` / `durationMs` |
| Footer `↑↓ select · f filter · esc back · s save` | interactive affordances (see below) |

The **`s save`** footer action is the bridge from *dynamic* to *saved* workflows: it promotes the current ad-hoc script into a **named, reusable workflow**. We confirmed there are **no saved workflows on disk yet** — both `~/.claude/workflows/` and the repo's `.claude/workflows/` are empty/absent — so everything we've seen is the "dynamic" (ad-hoc, must-approve) path. Saved workflows would be invocable by name and are the natural home for a curated library (§10).

## 9. What this is — and isn't — good for

Strengths (why we'd want it): deterministic control flow (real loops/conditionals/fan-out in JS, not model-improvised), true parallelism with a sane concurrency cap, clean structured telemetry on disk, typed outputs via schemas, cheap resume via content-hashing, and a token **budget** primitive for scaling depth to a target.

Hard limits (why it's not a universal hammer):

- **Headless & one-shot.** No tmux tab, no attach, no mid-run keystrokes. You cannot turn a workflow subagent into a steerable interactive agent. (Regular, non-workflow subagents can be resumed via `SendMessage` per [s10-research-22-subagent-management.md](s10-research-22-subagent-management.md); workflow subagents are more locked down.)
- **Parent-mediated launch.** The JS runtime lives *inside* a Claude Code process. The sidecar can't call the workflow engine out-of-process; a workflow only starts because *some* `claude` session issued the `Workflow` tool call. Same structural constraint as subagents.
- **The approval gate blocks a human** in the terminal, even under `acceptEdits`. Unmanaged, that stalls any unattended run (§10, §11).
- **Token cost is real and front-loaded.** Our trivial 3-agent demo burned **119 k tokens** (~40 k/agent, almost all cache-creation overhead from injecting the full tool/skill context into each fresh sidechain). Fan-out is not free; the manifest's `totalTokens` should be surfaced anywhere we expose this.

## 10. How awl-cc-dash could use this

Framed against our architecture — Electron ↔ FastAPI sidecar `:7690` ↔ driver seam ↔ tmux/WSL2 bridge, "one interactive `claude` per top-level agent," observing agents from JSONL (see [`docs/ARCHITECTURE.md`](../../../docs/ARCHITECTURE.md)).

**A. Highest-value, lowest-effort: render workflows the sidecar's agents already run (read-only observer).** When any dashboard-driven `claude` session kicks off a workflow, it drops a `journal.jsonl` (live) and a `<runId>.json` manifest (rich) into that session's `subagents/workflows/` tree. The sidecar **already tails session JSONL** — pointing it at these files is a small extension, and it yields a structured "Workflow" view (phase tree + per-agent tokens/state/previews) with **zero tmux scraping**. This is the single cleanest answer to the observe-subagents problem that [s10-research-22-subagent-management.md](s10-research-22-subagent-management.md) found genuinely hard over the bridge: workflow runs hand us the structured stream for free. The `workflowProgress[]` schema (§7b) can basically *be* the event-bus payload for a `workflow` event type.

**B. Use workflows as a first-class fan-out primitive inside agent work.** For burst-parallel jobs a dashboard agent naturally hits — "review these 12 changed files," "research these 8 sources," "extract fields from these 30 docs" — a workflow with a `schema` gives typed results and a live progress tree, complementing the one-interactive-`claude`-per-agent model on a *second axis* (within-agent parallelism). The dashboard shows the parent agent as usual and nests its workflow fan-out beneath it.

**C. Ship a curated library of saved workflows.** Once we understand the saved-workflow format (`s save` / `.claude/workflows/`), we could bundle house workflows (a review sweep, a research sweep, a migration pass) that dashboard agents invoke by name — turning our orchestration know-how into reusable, one-approval building blocks.

**D. Feed the coordination spine.** The manifest's clean per-agent records (tokens, duration, state, model) are exactly the shape our event stream / usage-aggregate modules want. A workflow run becomes a well-typed burst of coordination events rather than opaque tmux churn.

**E. A "review a workflow before it runs" approval card (proven feasible, 2026-07-04).** When a dashboard agent is about to run a workflow, the dashboard can intercept that approval moment and surface a decision card — name, description, phase list, and full script — for the operator to Approve or Reject, exactly the shape of the existing Plan/Decision/Permission cards (ARCHITECTURE §7.8/§7.11). The mechanism is a **PreToolUse hook on the `Workflow` tool** wired the same way the bridge driver already wires `ExitPlanMode`/`AskUserQuestion`: it fires before the workflow runs, its payload carries the whole preview (`tool_input.script`), and — unlike the detect-only plan/decision hooks — its **allow/deny response round-trips the decision** (allow launches, deny aborts) and **preempts** the built-in dialog, so the dashboard becomes the single approval surface. Proven end-to-end by the [`tests/workflow_approval_probe/`](../../../tests/workflow_approval_probe/) spike (§11 #6). Building it means adding a `Workflow` matcher to `_build_hook_settings`, a `/internal/hooks/workflow/{agent}` endpoint that raises a `workflow` inbox card and **holds for the operator's verdict** (the one piece the current fire-and-return-`{}` hooks don't do), and a resolve path that returns allow/deny.

**What *not* to do:** don't try to make workflow subagents into the dashboard's steerable agents (they're headless/one-shot), and don't assume the sidecar can launch a workflow directly (it must go through a parent `claude` session, same as any subagent).

## 11. Open questions / spikes before we build on this

Of the five original questions, **two are answered** by the [`tests/workflow_probe/`](../../../tests/workflow_probe/) observer spike (2026-07-04) and three remain open; a sixth, follow-on question (workflow *review-before-approve*, #6) is now **answered** by the [`tests/workflow_approval_probe/`](../../../tests/workflow_approval_probe/) interception spike.

1. **✅ ANSWERED — the approval gate can be pre-authorized.** The lever is the global user setting **`skipWorkflowUsageWarning`** in `~/.claude/settings.json`. With it `true` (as on this machine), dynamic workflows launch with **no** blocking dialog — every `Workflow` call in the VS Code session ran unattended. With it absent/`false`, the terminal CLI shows the "Run a dynamic workflow?" dialog and blocks a human (the ~108 s gap in Run A, even under `acceptEdits`). So an autonomous dashboard agent can run dynamic workflows unattended by ensuring that setting is on. *(Strong-but-inferential: not A/B'd by flipping the global flag mid-run; the clean confirmation test is documented in the probe RUNBOOK §Gate. It is NOT surfaced in the local permissions/settings reference docs — found by inspection.)*
2. **✅ ANSWERED — the manifest is written COMPLETION-ONLY; `journal.jsonl` is the live signal.** The probe watched a live run poll-by-poll: `<runId>.json` did **not** appear until the run reached a terminal `status`, while `journal.jsonl` streamed `started`/`result` lines incrementally throughout (with `started` leading `result` mid-flight). So the sidecar's live-progress design should **tail `journal.jsonl`** (append-only, cheap) and treat the manifest as the final snapshot — not poll the manifest for live state.
3. **Does the SDK / headless path expose workflows at all?** The sidecar's `sdk` driver runs the Agent SDK in-process, not the interactive CLI. Is the `Workflow` tool a CLI/VS-Code-only surface, or available to headless SDK sessions too? Decides whether workflows compose with our non-bridge driver. *(Still open — the probe observes runs regardless of who launched them, but hasn't been pointed at an SDK-launched one.)*
4. **Saved-workflow format & discovery.** Capture what `s save` writes and where, so we can author and ship workflows as repo assets and let agents invoke them by name. *(Still open.)*
5. **Cost governance.** Given ~40 k tokens/agent of fixed overhead (the probe's 10-agent subject burned ~399 k tokens/run), decide where the dashboard surfaces `totalTokens` and whether we cap fan-out width per profile. *(Still open — now with a concrete cost data point.)*
6. **✅ ANSWERED — the dashboard can intercept the workflow approval gate and round-trip Approve/Reject (the review-before-approve card).** The [`tests/workflow_approval_probe/`](../../../tests/workflow_approval_probe/) spike drove a real bridge Claude session to issue a `Workflow` call, with a per-agent **PreToolUse hook** POSTing to a stand-in dashboard (8/8 green, live). Findings: a hook **fires for the `Workflow` tool** (`tool_name == 'Workflow'`) even though the hooks reference doesn't list it, and its `tool_input.script` carries the **full preview** (name/description/phases recovered); a hook **`deny` aborts** the workflow (no run dir; the `permissionDecisionReason` surfaces to the agent) and **`allow` launches** it, with an **A/B contrast** (same setup, opposite verdict) proving the verdict *alone* controls launch; the hook verdict **preempts** the built-in "Run a dynamic workflow?" dialog (isolated with the popup switch left on), so the dashboard can be the **sole** approval gate; and as a fallback the built-in dialog **renders in the pane** (with `skipWorkflowUsageWarning:false` set **per-session**, no global config touched) and is answerable by keystroke (Escape rejects). Build path in §10 E; the one net-new piece is a hold-for-verdict hook endpoint (today's plan/decision hooks only detect-and-return-`{}`). *(Open sub-question carried from #3: whether the SDK/headless path exposes the same `Workflow` hook.)*

## 12. Source map

- Run A transcript (approval handshake + tool call/result): `C:\Users\lester\.claude\projects\C--Users-lester-MeDocuments-AppData-Anthropic-awl-cc-dash\ed34df81-48c4-4eba-849a-904364ae66be.jsonl` (lines 19–20).
- Run B run manifest (full state model): `…\5b035767-…\workflows\wf_ae75e5d5-a0c.json`.
- Run B journal + subagent transcripts + meta: `…\5b035767-…\subagents\workflows\wf_ae75e5d5-a0c\`.
- Repeatable observer probe (the empirical follow-up, 2026-07-04): [`tests/workflow_probe/`](../../../tests/workflow_probe/) — [test_workflow_orchestration_live.py](../../../tests/workflow_probe/test_workflow_orchestration_live.py), [subject_workflow.js](../../../tests/workflow_probe/subject_workflow.js), [RUNBOOK.md](../../../tests/workflow_probe/RUNBOOK.md); live findings in `tests/log/workflow_probe_findings_latest.txt`. Runs observed: `wf_e03d4702-80f`, `wf_bc9c13b5-66d`.
- Prior art on subagent observation/steering limits over the bridge: [s10-research-22-subagent-management.md](s10-research-22-subagent-management.md).
