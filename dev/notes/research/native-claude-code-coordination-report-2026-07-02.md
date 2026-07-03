# Native Claude Code coordination primitives over tmux: adopt vs. keep the custom spine

**Date:** 2026-07-02  
**Scope:** awl-cc-dash / Claude Code Dashboard, driven as TUI-over-tmux from a Windows Electron app + FastAPI sidecar.  
**Primary conclusion:** keep the sidecar-owned custom coordination spine as canonical. Adopt only the native primitives that are reachable and observable from the outside TUI path in narrow roles; treat the rest as observation sources or spike-only features.

---

## 1. Restated question

The dashboard already owns a custom coordination spine: **INBOX** typed cards, **LINKS** between independently spawned agents, and a shared **SCRATCHPAD**, all managed by the FastAPI sidecar. The sidecar drives real `claude` CLI processes in detached tmux sessions, sees them through `tmux capture-pane`, Claude Code JSONL transcripts, and HTTP hooks, and drives them through `tmux send-keys`, launch configuration, and hook responses.

The decision is whether to replace or absorb parts of that spine using native Claude Code concepts: `Task`, `TodoWrite`, `Workflow`, `SendMessage`, and agent-teams / teammate spawning. The settling axis is not whether the concepts are useful inside Claude Code. It is whether the sidecar can **observe** and **drive** them reliably while remaining on the main TUI-over-tmux path, without moving the interactive coding agents into the Agent SDK.

---

## 2. Options considered

### Option A — Keep the sidecar custom spine as canonical

Keep INBOX, LINKS, SCRATCHPAD, event envelopes, recipient addressing, prompt queues, read-watermarks, and hook/capture/transcript ingestion as the durable coordination layer. Native Claude Code features become inputs, run modes, or context sources rather than the source of truth.

**Verdict:** recommended.

### Option B — Adopt native subagents where they are already visible

The current native subagent-spawning tool is **`Agent`**. The older **`Task`** name is documented as renamed to `Agent` in Claude Code v2.1.63, with existing `Task(...)` references still working as aliases. [S1], [S2]

**Verdict:** adopt narrowly for parent-local delegation and improve observability with hooks and optional subagent-transcript ingestion. Do not use subagents as the top-level cross-agent bus.

### Option C — Adopt native workflow runs as an optional run type

Dynamic workflows are a native Claude Code feature that can orchestrate many subagents from a script, are available in the CLI, Desktop, IDE, non-interactive `claude -p`, and SDK, and can run in the background while the main session remains responsive. [S3]

**Verdict:** adopt narrowly for optional bulk orchestration / deep-research style runs. Do not replace INBOX, LINKS, or SCRATCHPAD with workflows.

### Option D — Use native task-list tooling instead of the dashboard progress model

`TodoWrite` exists in the tools reference, but current docs say it is **disabled by default** in favor of `TaskCreate`, `TaskGet`, `TaskList`, and `TaskUpdate`; the structured Task tools are default as of Claude Code v2.1.142 unless `CLAUDE_CODE_ENABLE_TASKS=0` reverts to legacy `TodoWrite`. [S1], [S7]

**Verdict:** skip `TodoWrite` as the adoption target. If the dashboard wants native task progress later, integrate the current task-list tools as a new observer, not the legacy `TodoWrite` tool.

### Option E — Replace custom LINKS with `SendMessage` or agent-teams

`SendMessage` exists as a native tool. It can message a teammate in agent teams, and it is always available for resuming subagents by agent ID or name. Structured team messaging requires agent teams. [S1], [S5]

Agent teams exist natively, but they are experimental, disabled by default, require `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`, and are explicitly documented with limitations. [S6]

**Verdict:** do not replace LINKS. Treat `SendMessage` as observe-only for the tmux-sidecar path. Treat agent-teams as spike-only, not production load-bearing.

### Per-primitive verdict table

| Primitive candidate | Exists natively, non-SDK? | Observable from tmux sidecar? | Drivable over tmux? | Verdict | Reasoning |
|---|---:|---:|---:|---|---|
| `Task` / subagent spawning | **Yes, with naming caveat.** Current native tool is `Agent`; `Task(...)` remains a legacy alias. **[confirmed]** | **Yes.** Parent transcript contains the tool call/result; `SubagentStart` and `SubagentStop` hooks expose IDs, type, transcript path, and final message; `capture-pane` gives only coarse UI state. **[confirmed]** | **Partially.** Sidecar can send natural-language prompts or `@subagent` mentions and configure allowed subagents/tools at launch, but cannot deterministically invoke the internal tool as an external API over tmux. **[confirmed/plausible]** | **Adopt narrowly.** | Good fit for parent-local delegation and subagent roster/status enrichment. Not a replacement for sidecar-owned INBOX/LINKS/SCRATCHPAD because subagents are children of one parent session, not independent OS processes sharing a bus. |
| `TodoWrite` | **Yes, but legacy/disabled by default.** Docs say it is disabled by default in favor of Task tools as of v2.1.142. **[confirmed]** | **Yes if enabled, mainly through transcript/tool output.** Hook-specific behavior should be spiked before relying on it. **[confirmed/plausible]** | **Weak.** Sidecar can influence via prompt and launch env, but cannot update the todo list directly through the TUI without Claude choosing the tool. **[confirmed]** | **Skip.** | The dashboard’s current progress bar is markdown-checklist based, not TodoWrite-based. Adopting TodoWrite would be net-new work and would target a legacy path. If native task progress is wanted, target `TaskCreate/Get/List/Update` instead. |
| `Workflow` | **Yes.** Dynamic workflows are native across CLI/Desktop/IDE/`claude -p`/SDK. **[confirmed]** | **Yes, but coarse.** `/workflows` UI, terminal screen, transcript, and `Stop` hook background-task metadata can show workflow state. Intermediate script variables are not automatically an external coordination board. **[confirmed]** | **Partially/Coarsely.** Sidecar can send prompts like “use a workflow,” slash commands such as `/deep-research`, or configure workflow enablement; mid-run control is limited, and workflows do not accept arbitrary user input during execution except permission prompts. **[confirmed]** | **Adopt narrowly.** | Useful as an optional high-throughput run mode, not as a replacement for custom routing, cards, links, or scratchpad. |
| `SendMessage` | **Yes.** Native tool for messaging agent-team teammates and resuming subagents by ID/name. **[confirmed]** | **Partially.** Tool use/results and subagent transcripts are observable; teammate messaging is observable only if agent teams are enabled and instrumented. **[confirmed/plausible]** | **No for arbitrary dashboard agents.** The sidecar cannot use it as a stable external bus between independently spawned tmux `claude` processes. It can only ask a session to use the tool, or rely on native subagent/team contexts. **[confirmed]** | **Observe-only.** | Does not replace LINKS. Custom links remain necessary for cross-process routing among hand-spawned agents. |
| Agent-teams / teammate spawning | **Yes, but experimental and disabled by default.** **[confirmed]** | **Yes in principle.** Lead UI/panel, split panes, task files, team config, task hooks, teammate hooks, transcript/state artifacts are available, but dashboard-specific behavior needs a live spike. **[confirmed/plausible]** | **Partially.** Enable with env/settings and prompt the lead to spawn teammates; direct routing depends on experimental in-session team machinery, not a stable sidecar API. **[confirmed]** | **Skip for production; spike-only.** | Not load-bearing: experimental flag, documented limitations, session-scoped architecture, one team per session, no nested teams, fixed lead, permissions set at spawn, possible task lag/shutdown issues. |

---

## 3. Trade-offs

### Cross-cutting tmux/TUI control-surface reality

`tmux send-keys` can send keystrokes or literal strings to a pane, and `tmux capture-pane` can capture pane contents to stdout. [S13] That gives the sidecar a strong terminal-control bridge, but not an internal Claude Code tool-call API. **[confirmed]**

Claude Code tool names are used in permission rules, command-line flags, SDK options, subagent frontmatter, skills, and hook matchers; for the most part, Claude decides when to use tools. [S1] **[confirmed]** This is the key limitation: outside the TUI, the sidecar can prompt, configure, and observe, but cannot generally call `Agent`, `SendMessage`, `Workflow`, or task-list tools as deterministic RPC methods unless Claude Code exposes a specific CLI/slash-command/control path.

Hooks are the best bridge for reliable observability. Claude Code hooks can be command hooks or HTTP hooks, receive JSON input including session/transcript/cwd fields, and can be registered for tool and lifecycle events. [S8] **[confirmed]** For this dashboard, hooks are the right way to turn inside-session events into sidecar events, but they do not by themselves create a native inter-process bus among separate tmux-launched `claude` processes.

### `Task` / `Agent` subagents

**Benefits.** Subagents are already aligned with the dashboard’s existing subagent roster model. Current docs describe subagents as specialized assistants with separate context windows, started through the `Agent` tool. [S2] The dashboard can continue deriving roster/status/usage from the parent transcript and add higher-fidelity hook ingestion. `SubagentStart` exposes agent ID and type, while `SubagentStop` exposes agent ID, type, the subagent transcript path, and last assistant message. [S9] **[confirmed]**

**Costs and breakpoints.** A subagent is subordinate to one parent session. The parent receives a single result, and the parent does not see the subagent’s intermediate tool calls directly unless the dashboard separately ingests subagent transcript files or hook events. [S1], [S5] **[confirmed]** This matches the prompt’s known limit: pending vs. active state cannot be distinguished reliably over tmux capture alone. **[confirmed from project prompt]**

**Drivability.** Claude Code supports natural-language subagent invocation and `@subagent` mention syntax, which the sidecar can type through tmux. [S2] **[confirmed]** That is enough for an operator-facing “ask parent to delegate” workflow, but not enough to replace the sidecar’s explicit prompt queue or direct routing among independent agents. **[confirmed/plausible]**

**Repository/live-spike dependency.** Verify whether the dashboard parser currently keys on `Task` or `Agent`, and if it needs dual-name compatibility. **[needs repo/live spike]**

### `TodoWrite` and current task-list tools

**Benefits.** Native task-list state could eventually become a structured progress source. The interactive task list appears in Claude Code’s status area, can be toggled with `Ctrl+T`, can be shown/cleared through natural language, persists across compactions, and can be shared across sessions with `CLAUDE_CODE_TASK_LIST_ID`. [S7] **[confirmed]**

**Costs and breakpoints.** `TodoWrite` is the wrong adoption target because it is legacy/disabled by default in current Claude Code. [S1], [S7] **[confirmed]** The dashboard’s current progress bar intentionally parses markdown checklists from assistant text, not tool output. **[confirmed from project prompt]** A native task-list integration would be net-new ingestion, state mapping, UI conflict handling, and potentially migration from markdown checklist semantics to structured task IDs and statuses. **[confirmed/plausible]**

**Drivability.** The sidecar can set environment variables at launch and can prompt Claude to show/update tasks, but the model remains the actor deciding when to call task tools. **[confirmed/plausible]** That makes native tasks a useful observation layer, not a replacement for the sidecar’s deterministic prompt queue, link routing, or scratchpad deltas.

**Repository/live-spike dependency.** Confirm actual JSONL shape for `TaskCreate/Get/List/Update` in the CLI version used by the dashboard, including whether tool results contain enough stable IDs/status fields for the desired UI. **[needs live spike]**

### `Workflow`

**Benefits.** Workflows are a native high-throughput orchestration mode. The docs describe a workflow as a script that can orchestrate many subagents, with background execution and a `/workflows` progress view. [S3] Workflow execution is available in CLI and other surfaces, and can be disabled/enabled by configuration. [S4] **[confirmed]** This could complement the dashboard as an optional “single parent launches a large internal swarm” run type.

**Costs and breakpoints.** Workflow runtime is isolated from the conversation, intermediate results stay in script variables, and workflows do not pause for arbitrary user input during execution except permission prompts. [S4] **[confirmed]** That is the opposite of the dashboard’s custom spine, where the sidecar owns typed cards, routing choices, shared scratchpad delivery, and per-agent prompt dispositions. **[confirmed/plausible]**

**Drivability.** The sidecar can type a prompt asking Claude to use a workflow, send slash commands such as `/deep-research` where appropriate, or use effort/workflow configuration. [S3], [S4] **[confirmed]** It cannot externally steer every internal phase or treat workflow variables as a shared board unless it adds new observability hooks or transcript parsing. **[confirmed/plausible]**

**Repository/live-spike dependency.** Test how workflow approval prompts, `/workflows` UI, background tasks, and transcript artifacts appear under detached tmux in WSL2. **[needs live spike]**

### `SendMessage`

**Benefits.** `SendMessage` is a real native tool. It can send messages to a teammate in an agent team, and it can resume subagents by agent ID/name even outside agent teams. [S1], [S5] **[confirmed]** It may be useful to observe when a native parent resumes a background subagent or sends a team message.

**Costs and breakpoints.** It is not a general outside-process API. Two independently spawned tmux `claude` OS processes do not share a native in-process message bus. **[confirmed from project prompt]** `SendMessage` therefore cannot replace dashboard LINKS unless those agents are all inside one native agent-team/session graph. **[confirmed/plausible]**

**Drivability.** The sidecar can ask Claude to send a message, but over tmux it cannot directly invoke `SendMessage` as an RPC to an arbitrary target process. **[confirmed/plausible]** Hook responses can inject context, but they do not create arbitrary cross-session native delivery semantics. **[confirmed/plausible]**

**Repository/live-spike dependency.** Verify how `SendMessage` calls and results appear in the JSONL transcript and whether hook matchers fire as expected in the dashboard’s version. **[needs live spike]**

### Agent-teams / teammate spawning

**Benefits.** Agent teams are the closest native analogue to dashboard LINKS: a lead session can spawn teammates, teammates can communicate, and teams have a shared task list/mailbox/files coordination model. [S6] **[confirmed]** Split-pane display modes can use tmux or iTerm2, which makes this superficially compatible with a tmux-oriented architecture. [S6] **[confirmed]**

**Costs and breakpoints.** Agent teams are experimental and disabled by default. They require explicit opt-in and are documented with limitations including one team per session, no nested teams, a fixed lead, no session resumption with in-process teammates, task status lag, slow shutdown, and split-pane constraints. [S6] **[confirmed]** The docs also warn that team runtime state such as session IDs and tmux IDs is in internal config and should not be manually edited. [S6] **[confirmed]**

**Drivability.** The sidecar can launch with `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` and prompt the lead to spawn teammates. [S6], [S7] **[confirmed]** That remains a prompt/config-driven mode inside one native team, not the dashboard’s existing deterministic routing layer among separately launched processes. **[confirmed/plausible]**

**Repository/live-spike dependency.** A live spike is mandatory before using this even as an optional mode: test detached tmux behavior, split-pane compatibility inside WSL2, hook coverage, JSONL artifacts, cleanup, and failure recovery. **[needs live spike]**

---

## 4. Per-finding confidence

| Finding | Confidence | Notes |
|---|---:|---|
| The five candidates are not SDK-only in the current docs: `Agent`/legacy `Task`, `TodoWrite`, `Workflow`, `SendMessage`, and agent-teams all appear in Claude Code docs. | **confirmed** | Naming and maturity caveats matter. `Task` is now `Agent`; agent-teams are experimental; `TodoWrite` is legacy/disabled by default. |
| `Task` was renamed to `Agent`, with legacy `Task(...)` references still accepted as aliases. | **confirmed** | Source: subagents docs. |
| Subagents are observable through parent transcript/tool events and richer through `SubagentStart`/`SubagentStop` hooks. | **confirmed** | Exact parser integration still needs repo/live validation. |
| Subagents are only partially drivable over tmux: prompt, `@subagent`, config/permissions yes; deterministic external tool-call RPC no. | **confirmed/plausible** | Based on documented invocation methods and tmux limitations. |
| `TodoWrite` exists but is disabled by default in favor of current Task tools as of v2.1.142. | **confirmed** | Source: tools reference and env-vars docs. |
| A native task-list integration would be net-new for this dashboard and should target `TaskCreate/Get/List/Update`, not legacy `TodoWrite`. | **confirmed/plausible** | Confirmed by project prompt for current progress-bar behavior; exact implementation effort needs repo review. |
| Workflows are native and available outside SDK, including the CLI. | **confirmed** | Source: workflows docs. |
| Workflows are observable at coarse run/progress/background-task level, but not a direct replacement for scratchpad/link/card state. | **confirmed/plausible** | Confirmed for `/workflows` and background-task metadata; replacement analysis is architectural inference. |
| `SendMessage` exists natively and can resume subagents or message teammates. | **confirmed** | Source: tools reference and subagent resume docs. |
| `SendMessage` cannot be used as a native bus among independently spawned tmux `claude` processes. | **confirmed/plausible** | Confirmed by project prompt that such processes share no bus; inference that `SendMessage` is limited to native subagent/team contexts. |
| Agent-teams are native but experimental, disabled by default, and unsuitable as a production dependency today. | **confirmed** | Source: agent-teams docs. |
| Agent-teams may become an optional future dashboard mode after a live spike. | **plausible** | Needs direct validation under detached tmux in WSL2 and current dashboard recovery model. |
| The current custom spine should remain canonical even if native observability is expanded. | **plausible** | Architectural recommendation based on reachability/observability analysis; not a source fact. |

---

## 5. Sources & citations

[S1] **Claude Code tools reference** — documents `Agent`, `AskUserQuestion`, `ExitPlanMode`, `SendMessage`, `TaskCreate/Get/List/Update`, `TodoWrite`, `Workflow`, and notes tool names are used in permissions/flags/hooks:  
https://code.claude.com/docs/en/tools-reference

[S2] **Claude Code subagents documentation** — subagent concepts, `Agent` rename from `Task`, `@subagent` invocation, foreground/background behavior, and resume behavior:  
https://code.claude.com/docs/en/sub-agents

[S3] **Claude Code workflows documentation** — dynamic workflows overview, workflow-vs-subagent/team comparison, `/workflows` progress view, and trigger methods:  
https://code.claude.com/docs/en/workflows

[S4] **Claude Code workflows runtime details** — workflow isolation, no arbitrary mid-run user input, execution scale, and availability in CLI/Desktop/IDE/`claude -p`/SDK:  
https://code.claude.com/docs/en/workflows

[S5] **Claude Code subagent resume behavior** — `SendMessage` can resume subagents by ID/name; subagent transcripts are written under the session subagents directory:  
https://code.claude.com/docs/en/sub-agents

[S6] **Claude Code agent-teams documentation** — experimental flag, teammate architecture, communication, task list, hooks, configuration files, tmux split-pane display, and limitations:  
https://code.claude.com/docs/en/agent-teams

[S7] **Claude Code interactive mode and environment variables** — interactive task list, `CLAUDE_CODE_TASK_LIST_ID`, `CLAUDE_CODE_ENABLE_TASKS`, and `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`:  
https://code.claude.com/docs/en/interactive-mode  
https://code.claude.com/docs/en/env-vars

[S8] **Claude Code hooks reference** — HTTP/command hooks, common input fields, `PreToolUse`, `PostToolUse`, `UserPromptSubmit`, and lifecycle events:  
https://code.claude.com/docs/en/hooks

[S9] **Claude Code subagent hooks** — `SubagentStart` and `SubagentStop` event payloads, including `agent_id`, `agent_type`, `agent_transcript_path`, and last assistant message:  
https://code.claude.com/docs/en/hooks

[S10] **Claude Code task and teammate hooks** — `TaskCreated`, `TaskCompleted`, and `TeammateIdle` hook payloads:  
https://code.claude.com/docs/en/hooks

[S11] **Claude Code stop/background-task hook metadata** — `Stop` hook `background_tasks` include types such as `subagent`, `workflow`, and `teammate`:  
https://code.claude.com/docs/en/hooks

[S12] **Claude Agent SDK docs** — SDK is a separate programmable interface for production agents and not the dashboard’s main TUI path:  
https://docs.anthropic.com/en/docs/claude-code/sdk/sdk-overview

[S13] **tmux manual** — `send-keys`, `capture-pane`, and detached session behavior:  
https://man7.org/linux/man-pages/man1/tmux.1.html

[S14] **Microsoft WSL networking documentation** — WSL2 networking can require Windows host/IP handling depending on mode:  
https://learn.microsoft.com/en-us/windows/wsl/networking

[S15] **Project prompt supplied for this research** — dashboard architecture, custom spine maturity, existing subagent observation, current progress-bar behavior, and constraints for this report.

---

## 6. Recommendation + fallback

### Recommendation

Keep **INBOX**, **LINKS**, **SCRATCHPAD**, event envelopes, addressing, prompt queues, hook handling, and read-watermarks as the dashboard’s canonical coordination spine. Native Claude Code primitives should be adopted only where they are reachable and observable without leaving the TUI-over-tmux main path.

Recommended implementation path:

1. **Subagents / `Agent`: adopt narrowly.**  
   Keep the existing parent-transcript-derived subagent roster. Add `SubagentStart` and `SubagentStop` hook ingestion. Optionally ingest subagent transcript files under the parent session’s `subagents/` directory. Update parser/tool-name handling to prefer `Agent` while accepting legacy `Task` aliases.

2. **Workflow: adopt narrowly as an optional run mode.**  
   Add a dashboard affordance such as “ask this agent to use workflow/deep-research mode,” then observe via transcript, `/workflows` screen state where visible, and `Stop` background-task metadata. Do not treat workflow internals as a routing layer or shared board.

3. **Todo/task progress: skip `TodoWrite`; optionally spike current Task tools.**  
   Keep the markdown-checklist progress parser as-is. If native task state becomes valuable, integrate `TaskCreate/Get/List/Update` as a new observer and reconcile it with the existing markdown progress model. Do not build new work around legacy `TodoWrite`.

4. **`SendMessage`: observe-only.**  
   Parse or hook it when it appears inside a native subagent/team context. Do not use it to replace custom LINKS, because it is not an external message bus among independently spawned tmux `claude` processes.

5. **Agent-teams: skip for production; run a contained spike only.**  
   A spike can test whether teams add useful UI signals or future run modes, but production behavior must not depend on an experimental feature flag or undocumented runtime files.

6. **Hooks to wire next, in priority order.**  
   `SubagentStart`, `SubagentStop`, `Notification`, `UserPromptSubmit`, `Stop` background-task metadata, and—only for task/team experiments—`TaskCreated`, `TaskCompleted`, and `TeammateIdle`. Keep the existing caveat: the plan/decision card hook path is wired but still spike-gated/unproven under the bridge.

### Honest fallback

If any native primitive proves flaky under detached tmux in WSL2, keep the current custom spine exactly as the coordination authority. Native primitives then become **observe-only telemetry**: useful for richer status, transcripts, and cards, but not trusted for routing, message delivery, end-after caps, scratchpad deltas, or operator decision flow.

The durable rule should be: **Claude Code can coordinate inside one session; the dashboard coordinates across sessions.**
