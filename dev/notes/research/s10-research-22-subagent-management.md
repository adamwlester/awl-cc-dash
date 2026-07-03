# s10-research-22-subagent-management

Date: 2026-07-02

## 1. Restated question

Can the awl-cc-dash dashboard, whose main control path is an Electron/FastAPI sidecar driving one interactive `claude` CLI process per top-level agent through detached tmux panes, **create**, **steer**, and **stop** Claude Code subagents from outside the TUI, using only tmux keystrokes, JSONL transcripts, launch-time configuration, and hook callbacks?

This report treats “subagent” narrowly as a child agent inside a parent Claude Code session, spawned by the parent’s `Agent`/legacy `Task` tool or related native subagent surfaces. It does **not** treat two independent tmux-backed Claude Code sessions as subagents. Those top-level sessions are easier to steer and kill because the sidecar owns a pane/process per session; a subagent normally lives inside the parent session and does not give the sidecar its own pane or OS process to target.

Assumptions carried from the prompt:

- The dashboard already observes subagents from the parent JSONL transcript.
- It currently cannot distinguish pending from active subagents over the tmux bridge.
- The main path is TUI-over-tmux, not the Claude Agent SDK.
- No awl-cc-dash repo or live Claude Code process was available for this report, so every implementation detail that depends on current local Claude Code behavior needs a live spike before it is shipped.

## 2. Options considered

### A. CREATE by prompting the parent to spawn a named subagent

**Mechanism.** Send a normal user prompt into the parent tmux pane, but use the documented subagent invocation syntax. Claude Code now documents three escalation levels for invoking subagents from an interactive session: natural language naming, `@`-mention, and session-wide `--agent`/`agent` settings. The important distinction is that natural language still leaves delegation to Claude, while an `@`-mention “guarantees the subagent runs for one task.” The docs also say the mention can be typed manually as `@agent-<name>` for local subagents, or `@agent-<plugin-scoped-name>` for plugin agents. [S1]

**Concrete tmux path.** When the parent prompt is idle, the sidecar can submit something like:

```text
@agent-code-reviewer Review the authentication changes. Run in the background. Return a concise summary and include any blocking issues.
```

or, for plugin-scoped agents:

```text
@agent-my-plugin:code-reviewer Review the auth module. Run this in the background.
```

Use `tmux send-keys -l` or a paste-buffer path for the literal text, then `Enter`. tmux’s manual confirms `send-keys` sends named keys or literal character strings to a target pane, and `capture-pane` captures pane contents for screen polling. [S9]

**Drivability.** Confirmed for “induce a specific subagent through the parent” if the installed Claude Code version supports the documented manual `@agent-...` mention. Natural language alone is best-effort; `@`-mention is the more deterministic path. This is still not a direct out-of-process subagent API: the parent session receives the message, and Claude writes the actual subagent task prompt. [S1]

**Observability.** Confirmed and better than the prompt’s baseline if hooks are enabled: `SubagentStart` hooks include `agent_id` and `agent_type`; `SubagentStop` hooks include `agent_id`, `agent_type`, `agent_transcript_path`, and `last_assistant_message`. The existing transcript-derived roster remains useful, but hook callbacks should be the canonical low-latency way to mark “spawned/started” and “completed.” The known pending-vs-active gap remains unless the dashboard consumes `SubagentStart` and possibly each subagent’s own transcript. [S2]

### B. CREATE by defining subagents at launch or on disk

**Mechanism.** Subagent definitions can be project/user Markdown files, organization-managed settings, plugin agents, or CLI-defined agents passed with `--agents`. Disk-defined agents are loaded at session start; files added directly after launch require a session restart, while the `/agents` TUI can create agents immediately. [S1]

**Drivability.** Confirmed for **definition**, not for **runtime spawn**. The sidecar can prepare `.claude/agents/*.md` or launch with `--agents`/settings, but that only makes the subagent available. It does not start a child until the parent uses the `Agent` tool or an `@`-mention prompt induces it. [S1]

**Observability.** Same as option A after the subagent actually starts.

### C. CREATE a direct subagent without the parent

**Mechanism considered.** Call some external CLI/API to create a subagent under an existing parent by ID, without asking the parent turn to do it.

**Finding.** No documented non-SDK out-of-process primitive was found for “spawn child subagent under this existing interactive parent session” directly from the sidecar. Claude Code’s documented non-SDK paths are parent-mediated `Agent`/`@`-mention, `/fork`, `/agents`, workflows, or separate background sessions. The CLI `--agent <name>` starts the **main thread itself** as that agent persona; it does not inject a child subagent into an existing parent. `claude --bg --agent ...` similarly creates a separate background session using an agent persona, not a child inside the parent. [S1], [S10]

### D. STEER by asking the parent to resume/message an existing subagent

**Mechanism.** Claude Code documents subagent resumption. Completed subagents can be resumed with their previous context; custom and `general-purpose` agents return or expose an agent ID, while Explore and Plan are one-shot and do not return an agent ID. The docs state that Claude uses `SendMessage` with the agent ID as `to`, and that `SendMessage` is always available for resuming subagents by ID or name. If a stopped subagent receives a `SendMessage`, it auto-resumes in the background. [S1]

**Concrete tmux path.** Submit a prompt to the parent such as:

```text
Send this follow-up to subagent agent-abc123 using SendMessage: now also inspect the authorization paths and append only new findings.
```

or, when the dashboard only knows a name/status from the transcript:

```text
Resume the code-reviewer subagent from earlier and ask it to check authorization logic next.
```

**Drivability.** Confirmed for parent-mediated **resume/follow-up after stop/completion**. It is not a sidecar-direct API; the dashboard cannot itself call `SendMessage` through tmux except by inducing the parent model to call the tool. It is also not a strong answer for real-time steering of a currently executing subagent. The docs clearly document stopped-subagent resume; they do not clearly guarantee immediate mid-turn delivery to a busy named subagent. Treat live steering of an active subagent as a live-spike item. [S1], [S3]

**Observability.** Usable if the sidecar stores `agent_id` from hooks or parses it from the parent/subagent transcript. The docs place subagent transcript files under `~/.claude/projects/{project}/{sessionId}/subagents/agent-{agentId}.jsonl`; ingesting those files would substantially improve follow-up UX and status accuracy. [S1], [S2]

### E. STEER by opening the native `/agents` Running tab or subagent/fork panel

**Mechanism.** The `/agents` command opens a TUI manager whose Running tab lists live/recently finished subagents and lets the operator open or stop them. Forked subagents have a panel below the prompt; selecting a fork and pressing `Enter` opens its transcript and lets the operator send follow-up messages. [S1], [S4]

**Drivability.** Plausible but brittle over tmux. The sidecar can send `/agents`, arrow keys, `Enter`, `x`, and `Esc`, but this becomes screen scraping and focus choreography rather than a stable backend primitive. It is likely acceptable for a manual “remote control the TUI” experiment, not for a robust dashboard backend.

**Observability.** The panel is visible via `capture-pane`, but it is not structured. Hooks/transcripts are better for structured state.

### F. STEER by hook callback

**Mechanism.** Hooks can run as command or HTTP callbacks and can add context or make decisions at specific lifecycle events. `SubagentStart` can inject `additionalContext` into the subagent before its first prompt. `SubagentStop` can block stop and deliver a reason as the subagent’s next instruction, keeping it running. [S2]

**Drivability.** Confirmed, but only at event boundaries. Hooks are excellent for deterministic guardrails: “when this subagent starts, include these dashboard-supplied constraints” or “when it tries to finish, require extra checks.” They are not a general mailbox to push arbitrary operator instructions into an already-running subagent at any time.

**Observability.** Excellent for lifecycle and policy enforcement; not sufficient as a live command bus.

### G. STOP by interrupting the parent turn

**Mechanism.** Send `Ctrl+C` to the parent pane. Claude Code’s interactive docs state that `Ctrl+C` interrupts a running operation. [S7]

**Drivability.** Confirmed as a parent-session interrupt, not a precise subagent cancel. For a foreground subagent blocking the parent turn, this may cancel the current operation, but it is not an addressable “cancel subagent X” primitive. For background subagents, it may interrupt the main turn or idle session rather than the child you mean.

**Observability.** The sidecar can see parent status changes and eventual transcript/hook events, but cannot infer precisely which subagent was cancelled without corroborating hook/transcript updates.

### H. STOP all running background subagents with keyboard shortcut

**Mechanism.** Claude Code documents `Ctrl+X Ctrl+K` as “Stop all running background subagents in this session,” with a double-press confirmation within three seconds. [S7]

**Drivability.** Confirmed as a native TUI control and likely drivable through tmux key sequences, but it is coarse-grained. It stops **all** running background subagents in the session, not one named subagent.

**Observability.** The sidecar should watch for `SubagentStop` hooks and parent transcript state after invoking it. It still needs a live spike for exact tmux key sequence behavior and confirmation handling in awl-cc-dash.

### I. STOP one subagent through native TUI selection

**Mechanism.** Use `/agents` Running tab, select the row, press stop key (`x` where documented for fork/workflow panels and agent-team panels; `/agents` docs state the Running tab lets the operator “open or stop” running subagents). Fork panels explicitly document `x` to stop a running fork. [S1]

**Drivability.** Plausible but not robust. This requires the sidecar to know panel focus, row ordering, filters, and whether the desired target is visible. It is a TUI automation script, not a stable external management API.

**Observability.** Possible via capture-pane, but structured hooks should still be the source of truth.

### J. STOP by `TaskStop`

**Mechanism considered.** Claude Code has a `TaskStop` tool that stops a running background task or shell by ID. [S3]

**Finding.** Do not rely on this for named subagent cancellation. The docs describe `TaskStop` for background tasks/shells; they do not document “stop subagent by agent ID.” It may affect some task-panel items, but using it as the dashboard’s subagent cancel API would be speculative without a live spike and transcript schema confirmation. [S3]

### K. Dynamic workflows

**Mechanism.** The `Workflow` tool and `/workflows` command run a JavaScript orchestration script that launches many subagents in the background; the workflow view can pause/resume, stop selected agents or the whole workflow, restart agents, and show progress. [S5]

**Drivability.** Confirmed as native and drivable from the TUI by asking for a workflow or invoking saved workflow commands. It is not a replacement for managing arbitrary parent-spawned subagents. It creates a separate workflow runtime with its own progress UI and limits; the docs explicitly say workflows have “no mid-run user input” except agent permission prompts. [S5]

**Observability.** Better than ad hoc subagents inside the workflow UI, but it is a different feature surface. Consider a separate “workflow runs” feature, not the answer to dashboard-level subagent steering.

### L. Agent teams / teammate spawning

**Mechanism.** Agent teams coordinate multiple independent Claude Code sessions with a lead, shared task list, and peer-to-peer messaging. In-process mode allows selecting a teammate and messaging/stopping it; split-pane mode gives each teammate its own pane. Agent-team teammates can use existing subagent definitions as role templates. [S6]

**Drivability.** Confirmed as a native feature, but it is experimental and disabled by default according to the glossary; it also changes the worker model from “subagent inside one parent session” to “teammate as independent Claude Code session.” This violates the prompt’s constraint not to depend on unshipped/experimental features as the primary answer. [S6], [S11]

**Observability.** Stronger than ordinary subagents because teammates are addressable sessions/panes in split-pane mode, but they are not the same primitive.

## 3. Trade-offs

### Parent-prompted `@agent-<name>` CREATE

- **Cost.** Requires careful prompt construction and readiness detection in the parent pane. If the pane is not idle, the sidecar may type into the wrong UI state.
- **Where it breaks.** Installed Claude Code version may predate manual `@agent-...` support; agent name may not be loaded; project/user agent definitions added after launch may require restart; plugin-scoped names require exact `@agent-` syntax.
- **Assumptions.** The parent prompt is idle and accepting input; Claude Code’s `@` mention parser works with literal text sent over tmux; the desired subagent type is loaded.
- **Drivability.** Good enough to adopt for CREATE. It is parent-mediated, not direct API-level spawn.
- **Observability.** Good with `SubagentStart`/`SubagentStop` hooks and parent transcript. Improve by ingesting `subagents/agent-{id}.jsonl`.
- **Confidence.** Confirmed for the documented mechanism; plausible for awl-cc-dash tmux automation until live-spiked.

### Natural-language CREATE

- **Cost.** Low implementation cost.
- **Where it breaks.** Claude may decide not to delegate, pick a different agent, run foreground rather than background, or rewrite the task unexpectedly.
- **Drivability.** Best-effort only.
- **Observability.** Same as any spawned subagent if it happens.
- **Confidence.** Confirmed as documented behavior; skip as the primary CREATE mechanism because `@agent-...` is stronger.

### Direct non-SDK CREATE

- **Cost.** Would be ideal, but no documented surface found.
- **Where it breaks.** There is no official stable command/API in the current docs to inject a child into an existing interactive parent from outside.
- **Drivability.** Not drivable.
- **Observability.** Not applicable.
- **Confidence.** Confirmed negative from current official docs; still verify against local build/changelog if Anthropic adds a CLI/API later.

### `SendMessage` STEER/resume

- **Cost.** Requires capturing and storing `agent_id`; requires prompting parent to call `SendMessage`; requires UX clarity that this is a resumed/follow-up turn, not guaranteed real-time interruption.
- **Where it breaks.** Built-in Explore/Plan are one-shot; active mid-turn delivery is not clearly documented; parent may not comply exactly unless prompted with a precise agent ID and instruction.
- **Drivability.** Adopt only for “resume stopped/completed subagent” and possibly “send follow-up to idle/background subagent” after live spike. Do not present it as deterministic real-time steering of a busy child.
- **Observability.** Good if subagent transcripts are ingested; otherwise the parent transcript/hook lifecycle gives only coarse state.
- **SDK-only?** No; `SendMessage` exists as a Claude Code tool. But the sidecar still cannot call the tool directly over tmux; it must ask the parent to call it.
- **Confidence.** Confirmed for stopped/resume; plausible/speculative for active mid-run steer.

### Hook-based management

- **Cost.** Need hook configuration and a sidecar HTTP endpoint reachable from WSL2. Need secure validation of hook payloads.
- **Where it breaks.** Hook events are not a general mailbox. HTTP hook status codes are non-blocking unless a 2xx JSON response uses the documented decision fields. `SubagentStart` cannot block creation, only inject context. [S2]
- **Drivability.** Strong for guardrails and lifecycle augmentation, weak for ad hoc running-subagent control.
- **Observability.** Strong. Hooks should be adopted for authoritative lifecycle events.
- **Confidence.** Confirmed.

### TUI panel automation (`/agents`, fork panel, `/workflows`)

- **Cost.** Significant brittleness: focus, row order, renderer changes, terminal size, accessibility output, and concurrent status updates.
- **Where it breaks.** Any Claude Code UI change can break row selection. Dashboard screen polling is already approximate.
- **Drivability.** Possible for manual/experimental remote-control features. Not recommended as backend infrastructure for targeted subagent management.
- **Observability.** Screen-visible only unless backed by hooks/transcripts.
- **Confidence.** Confirmed that panels exist; plausible that awl-cc-dash can automate them; needs live spike.

### `Ctrl+X Ctrl+K` all-background-subagent stop

- **Cost.** Simple emergency command but destructive/coarse.
- **Where it breaks.** Stops all running background subagents, not one. Requires exact key-sequence behavior under tmux and confirmation timing.
- **Drivability.** Adopt as “panic stop all background subagents in this parent session,” not as targeted stop.
- **Observability.** Use hooks/transcripts to reconcile final state.
- **Confidence.** Confirmed in docs; needs live key-sequence spike in the dashboard.

### Agent teams as an alternative

- **Cost.** New conceptual model, experimental flag, coordination directories, possibly split panes, and different lifecycle/observability. It is not the dashboard’s current main path.
- **Where it breaks.** Feature may change; disabled by default; teammates are not ordinary parent-spawned subagents.
- **Drivability.** Good if adopted as a separate experimental feature; not the answer to this prompt’s subagent question.
- **Observability.** Good, especially in split-pane mode.
- **Confidence.** Confirmed as documented; skip for primary recommendation.

## 4. Per-capability verdict table

| Row | Exists natively (non-SDK)? | Observable? | Drivable over tmux? | Verdict |
|---|---:|---:|---:|---|
| **CREATE: named subagent for one task** | Yes: `Agent` tool via `@agent-<name>` mention; natural language also works best-effort. [S1] | Yes: parent transcript plus `SubagentStart`/`SubagentStop` hooks. [S2] | Yes, by typing prompt into parent pane; must wait for idle input. | **adopt** |
| **CREATE: direct child spawn outside parent** | No documented non-SDK surface found. | N/A | No. | **skip** |
| **CREATE: define custom subagent** | Yes: files, `--agents`, `/agents`, settings/plugins. [S1] | Definition visibility via `/agents`; actual spawn via hooks/transcript. | Launch-time `--agents` is drivable; direct disk edits require restart unless using `/agents`. | **adopt** for definitions, not spawn |
| **STEER: stopped/completed subagent follow-up** | Yes: parent can use `SendMessage` by `agent_id` or name to resume; stopped subagents auto-resume. [S1], [S3] | Yes if `agent_id` and subagent transcript path are captured. [S1], [S2] | Partially: sidecar must prompt parent to use `SendMessage`; no direct sidecar tool call over tmux. | **adopt** as limited resume |
| **STEER: active/running named subagent mid-turn** | Not clearly documented as immediate/targeted for ordinary subagents. | Partial; current dashboard cannot distinguish pending vs active without more signals. | Plausible only through parent prompt, TUI panel, or queued `SendMessage`; needs live spike. | **observe-only** |
| **STEER: forked subagent** | Yes: `/fork` panel supports opening transcript and follow-up messages. [S1] | Visible in panel; should also appear in transcripts/hooks as subagent/fork activity. | Plausible by TUI key automation; brittle. | **skip** as primary, optional experiment |
| **STOP: foreground/current operation** | Yes: `Ctrl+C` interrupts a running operation. [S7] | Parent transcript/hook effects only. | Yes. | **adopt** as parent interrupt, not child-specific stop |
| **STOP: all running background subagents** | Yes: `Ctrl+X Ctrl+K`, confirmed twice, stops all running background subagents. [S7] | Yes with hooks/transcripts. | Yes in principle; live-spike key sequence. | **adopt** as emergency all-stop |
| **STOP: one named running subagent by ID** | `/agents` Running tab can open/stop; fork panel has `x`; no stable documented external API by `agent_id`. [S1] | Partial. | Plausible but screen-state-driven; not robust. | **observe-only** / experimental |
| **Primitive: `Task` / `Agent`** | Yes. `Task` was renamed to `Agent`; existing `Task(...)` settings references still work as aliases. [S1], [S3] | Yes via tool-use transcript and hooks. | Yes indirectly through prompt/`@agent-...`; not direct tool call from sidecar. | **adopt** for CREATE |
| **Primitive: `SendMessage`** | Yes. Tool sends to agent-team teammate or resumes subagent by ID/name. [S1], [S3] | Yes if IDs/transcripts are captured. | Parent-mediated over tmux; no sidecar-direct tool call. | **adopt** for resume, **observe-only** for live steer |
| **Primitive: `Workflow`** | Yes. Dynamic workflows run scripts that orchestrate many subagents; `/workflows` manages runs. [S5] | Workflow UI exposes phases/agents/tokens/results. | Yes via prompt/commands, but management is workflow-specific. | **skip** for ordinary subagent management; separate feature |
| **Primitive: agent teams / teammate spawning** | Yes but experimental/disabled by default; teammates are independent sessions with messaging/tasks. [S6], [S11] | Stronger than subagents; shared task list and teammate state. | Yes through team UI/panes, but different architecture. | **skip** as primary; potential future alternative |
| **Primitive: hooks** | Yes: HTTP/command/prompt hooks; `SubagentStart`/`SubagentStop` documented. [S2] | Strong for lifecycle; structured fields include IDs and transcript paths. | Hooks are callback/control points, not tmux keystrokes. | **adopt** for observability and guardrails |

## 5. Per-finding confidence

1. **Subagents run in their own context window and return a final result to the parent; the parent does not see intermediate tool calls by default.** Confidence: **confirmed** from Tools reference. [S3]
2. **The legacy `Task` tool has been renamed to `Agent`, with old `Task(...)` references still accepted in settings/definitions.** Confidence: **confirmed**. [S1]
3. **Natural-language “use X subagent” is model-mediated; `@`-mention guarantees a specific subagent for one task; manual `@agent-<name>` is documented.** Confidence: **confirmed**. [S1]
4. **A sidecar can drive `@agent-<name>` over tmux by sending literal text and Enter.** Confidence: **plausible**. tmux can send keys/literal text, but this needs a live spike against Claude Code’s current TUI renderer and the dashboard’s focus/idle detection. [S9]
5. **There is no documented non-SDK direct API/CLI to create a child subagent inside an already-running interactive parent without the parent receiving a prompt/tool call.** Confidence: **confirmed from current official docs**, but re-check on upgrades.
6. **`--agent <name>` makes the main session use that agent’s prompt/tools/model; it is not a child subagent spawn.** Confidence: **confirmed**. [S1], [S10]
7. **`--agents`/agent files/settings define availability, not runtime execution; disk-added files require restart unless created through `/agents`.** Confidence: **confirmed**. [S1]
8. **`SubagentStart` and `SubagentStop` hooks exist and provide structured lifecycle data.** Confidence: **confirmed**. [S2]
9. **`SubagentStart` cannot block creation but can inject context; `SubagentStop` can block stop and feed a reason back to keep the subagent running.** Confidence: **confirmed**. [S2]
10. **Hooks improve observability but do not create a general operator-to-subagent command bus.** Confidence: **confirmed/plausible**. Confirmed for documented hook semantics; the product interpretation should be validated with a spike.
11. **`SendMessage` can resume stopped/completed subagents by ID or name, and stopped subagents auto-resume in the background.** Confidence: **confirmed**. [S1], [S3]
12. **`SendMessage` can reliably steer a currently busy named subagent mid-turn.** Confidence: **speculative**. The docs support resume/follow-up, not deterministic immediate interruption of active child work. Needs live spike.
13. **Explore and Plan are one-shot and do not return agent IDs, so they are poor candidates for dashboard-managed resume.** Confidence: **confirmed**. [S1]
14. **`/agents` Running tab can open or stop subagents.** Confidence: **confirmed**. [S1]
15. **Automating `/agents` row selection over tmux is robust enough for product-grade targeted stop.** Confidence: **speculative/likely no**. Needs spike; recommended only as experiment.
16. **`Ctrl+C` interrupts the current operation, but is not a targeted child-subagent cancel.** Confidence: **confirmed** for interrupt; **plausible** for non-targeting semantics. [S7]
17. **`Ctrl+X Ctrl+K` stops all running background subagents in the session.** Confidence: **confirmed**. Exact tmux sequence needs live spike. [S7]
18. **`TaskStop` should not be treated as “stop subagent by agent ID.”** Confidence: **plausible** from current docs; needs live spike if someone wants to explore it. [S3]
19. **Dynamic workflows can launch/manage many subagents, but are a separate workflow runtime, not arbitrary subagent management.** Confidence: **confirmed**. [S5]
20. **Agent teams provide direct teammate messaging/stop and can reuse subagent definitions, but are experimental and disabled by default; they are not ordinary subagents.** Confidence: **confirmed**. [S6], [S11]
21. **The dashboard’s known pending-vs-active gap remains unless it consumes `SubagentStart` and/or subagent transcript files.** Confidence: **plausible**, because the local dashboard was not inspected. Needs in-repo check.
22. **A high-quality implementation should treat hook events as lifecycle truth, parent JSONL as reconciliation, and subagent JSONL ingestion as the follow-on for deep status/tool visibility.** Confidence: **plausible** architecture recommendation; needs repo integration review.

## 6. Sources & citations

- **[S1] Claude Code Docs — Create custom subagents.** https://code.claude.com/docs/en/sub-agents
  - Used for: subagent definition/loading; `@`-mention; manual `@agent-<name>`; `--agent`; background/foreground; `/agents` Running tab; nested subagents; resume; `SendMessage`; subagent transcript paths; forks.
- **[S2] Claude Code Docs — Hooks reference.** https://code.claude.com/docs/en/hooks
  - Used for: HTTP hook behavior; hook decision control; `SubagentStart` and `SubagentStop` schemas; `additionalContext`; `SubagentStop` block semantics; task hooks.
- **[S3] Claude Code Docs — Tools reference.** https://code.claude.com/docs/en/tools-reference
  - Used for: `Agent` tool behavior; `SendMessage`; `TaskStop`; `Workflow`; background task/tool semantics.
- **[S4] Claude Code Docs — Run agents in parallel.** https://code.claude.com/docs/en/agents
  - Used for: comparison of subagents, agent view, agent teams, dynamic workflows; `/agents` vs `claude agents`; background work views.
- **[S5] Claude Code Docs — Orchestrate subagents at scale with dynamic workflows.** https://code.claude.com/docs/en/workflows
  - Used for: workflow runtime behavior, `/workflows` controls, no mid-run user input, pause/stop/restart controls, concurrency/agent caps.
- **[S6] Claude Code Docs — Orchestrate teams of Claude Code sessions.** https://code.claude.com/docs/en/agent-teams
  - Used for: team lead/teammate control, in-process and split-pane modes, direct teammate messaging, stop/shutdown, task list, using subagent definitions for teammates.
- **[S7] Claude Code Docs — Interactive mode.** https://code.claude.com/docs/en/interactive-mode
  - Used for: `Ctrl+C` interrupt; `Ctrl+X Ctrl+K` stop all background subagents; keyboard shortcuts.
- **[S8] Claude Code Docs — Subagents in the Agent SDK.** https://code.claude.com/docs/en/agent-sdk/subagents
  - Used only as a cross-check for SDK-only paths and subagent resumption details; not used as the primary recommendation because the dashboard’s main path is TUI-over-tmux.
- **[S9] tmux(1) manual page — man7.org.** https://man7.org/linux/man-pages/man1/tmux.1.html
  - Used for: detached tmux sessions, panes as pseudo terminals, `send-keys`, and `capture-pane`.
- **[S10] Claude Code Docs — CLI reference.** https://code.claude.com/docs/en/cli-reference
  - Used for: `--bg`, `--agent`, and `--agents` launch/config behavior.
- **[S11] Claude Code Docs — Glossary.** https://code.claude.com/docs/en/glossary
  - Used for: agent-teams definition and experimental/disabled-by-default status.

## 7. Recommendation + fallback

### Recommendation

Build **guarded CREATE** and **lifecycle observability** now; keep “live manage” constrained and explicit.

1. **Adopt parent-mediated CREATE via `@agent-<name>`.**
   - Add a sidecar action like `create_subagent(parent_agent_id, subagent_name, task, background=True)`.
   - Generate a parent prompt using manual mention syntax, for example `@agent-code-reviewer <task>`. Add “run in the background” when desired.
   - Send through the existing tmux input path only when the parent pane is idle.
   - Treat natural-language “use X subagent” as fallback only; it is less deterministic.
   - Verify the installed Claude Code version supports manual `@agent-<name>` and the exact agent names/scoped plugin names.

2. **Adopt hook-based lifecycle observability.**
   - Register HTTP hooks to the sidecar for `SubagentStart` and `SubagentStop`.
   - Store `agent_id`, `agent_type`, parent `session_id`, parent `transcript_path`, and, on stop, `agent_transcript_path` and `last_assistant_message`.
   - Use hooks as low-latency events and parent JSONL as reconciliation.
   - Prioritize ingesting each subagent’s own `subagents/agent-{agentId}.jsonl` transcript as the follow-on that closes the current pending-vs-active/status/detail gap.

3. **Adopt limited STEER only for stopped/completed subagent resume.**
   - If the dashboard has an `agent_id`, allow “send follow-up / resume” by prompting the parent to use `SendMessage` to that ID.
   - Label the UX as “resume/follow-up,” not “interrupt/redirect running subagent,” until a live spike proves active-subagent delivery semantics.
   - Do not route this through the Agent SDK unless the project deliberately accepts the SDK exception and its extra architecture cost.

4. **Adopt emergency STOP-all, not targeted STOP, as the first TUI control.**
   - Expose a clearly labeled panic action: “Stop all running background subagents in this parent session.” Implement with `Ctrl+X Ctrl+K` twice, after a live tmux key-sequence spike.
   - For foreground work, keep using `Ctrl+C` as a parent-operation interrupt.
   - Do **not** claim single-subagent targeted cancellation until a spike validates either a stable `/agents` TUI automation path or a documented ID-addressable stop primitive.

5. **Use hooks as guardrails, not an ad hoc control bus.**
   - `SubagentStart` can inject operator/project context at birth.
   - `SubagentStop` can enforce “do not finish until X” checks by blocking stop and feeding a reason back.
   - Neither replaces a real mailbox for arbitrary live instructions.

6. **Treat workflows and agent teams as separate product surfaces.**
   - Dynamic workflows are useful for “run many subagents with a script,” but not for managing arbitrary parent-spawned subagents.
   - Agent teams solve direct message/stop much better, especially with split panes, but they are experimental/disabled by default and use independent teammate sessions. Do not make them the primary answer to this prompt.

### Fallback

If the live spike shows that manual `@agent-<name>` is unreliable under tmux, `SendMessage` cannot be induced consistently, or `/agents` cannot be safely automated, keep subagents **observe-only** in the dashboard:

- Continue deriving roster/status/usage from the parent transcript.
- Add `SubagentStart`/`SubagentStop` hooks for better lifecycle observability.
- Show subagent IDs and transcript paths when available.
- Keep CREATE/MANAGE as backlog items.
- For operator-controllable parallel work, continue using top-level tmux-backed Claude Code agents or consider background sessions/agent view as a separate, explicit worker model.

### Agreement with broader §10-13 native-primitives finding

This should agree with the broader native-primitives report if that report’s thesis is: “use native primitives where they are stable and observable, but keep the custom tmux/sidecar spine for dashboard control.” On subagents specifically, the update is nuanced:

- **CREATE is now adoptable** over TUI via documented `@agent-<name>` mention, but still parent-mediated.
- **OBSERVABILITY should adopt hooks** and later subagent transcript ingestion.
- **STEER/STOP remain limited**: resume/follow-up is viable through parent-mediated `SendMessage`; true live targeted steering/stopping of one ordinary active subagent is not yet robust enough for the dashboard’s main path.
- **Fallback remains observe-only** for live management unless a live spike proves a stable ID-addressable control mechanism.
