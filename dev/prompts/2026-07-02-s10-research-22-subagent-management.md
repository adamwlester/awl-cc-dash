# RESEARCH PROMPT — Can a dashboard CREATE and MANAGE (steer/stop) Claude Code subagents from outside the TUI, over tmux?

> Paste this entire message into a fresh ChatGPT or Claude web session. It is fully self-contained — you do not need any repository or local file.

> **Operator framing note (internal — not for the chat to action).** This overlaps §10-13 "native coordination primitives" and its research prompt `dev/prompts/2026-07-02-s10-research-13-native-coordination.md`, and the internal note `dev/notes/research/research-subagent-architecture.md`. Where #13 asks the broad *adopt-vs-keep-custom-spine* question across all primitives, **this prompt is narrower and deeper on one axis: the CREATE / MANAGE (drivability) of subagents specifically.** Run this alongside #13 and read the two reports together; they should agree on the subagent verdict. (The note above is context for the human — chat, just answer the question below on its merits.)

## Standing note (read first)
You have NO access to the awl-cc-dash repository or any of its files. Answer from general knowledge, official Claude Code / Claude Agent SDK / tmux documentation, and the web. Cite your sources inline. Tag every finding with a confidence level — **confirmed** (documented, or you verified it), **plausible** (reasonable inference, untested), or **speculative** (educated guess). Explicitly flag any claim that would need to be verified against the actual repo or a live spike before we rely on it. Everything you need is embedded below; do not ask for files.

## System context
awl-cc-dash is a single-window Electron desktop app (Windows, one operator) that talks to a FastAPI "sidecar" service on `127.0.0.1:7690` over HTTP + Server-Sent Events. The sidecar drives Claude Code coding-agent sessions as **DETACHED tmux sessions inside WSL2** — one real `claude` CLI process per agent — and reads each agent through `tmux capture-pane` (a ~1s screen poll) + the agent's JSONL transcript file. The primary control path is this **tmux / terminal-UI (TUI) bridge — NOT the Claude Agent SDK.** (A limited in-process Agent-SDK driver exists only for non-interactive utility passes; it does not drive the interactive coding agents, and pulling it in for a capability is a deliberate, costed exception, not the main path.) The sidecar can also receive HTTP **hook** callbacks from each agent (over the WSL2→Windows gateway).

Subagent-specific context you need:
- A **subagent** is a sub-identity spawned by a parent Claude Code session (via the parent calling a `Task` / `Agent` tool from the inside).
- **Today the dashboard already OBSERVES subagents** — it derives the subagent roster (identity / status / usage) from the **parent agent's own transcript**, by pairing each subagent-spawn tool call with its matching tool-result. (Ingesting each subagent's *own* separate transcript file — the `<parent>/subagents/` directory Claude Code writes — is a deferred follow-on, not built.)
- **A known limit:** over tmux, the bridge **cannot distinguish a *pending* subagent from an *active* one** (this is tracked separately).
- **What is NOT built and is the subject of this question:** the ability for the operator, from the dashboard, to **CREATE** a subagent (spawn one on demand) and **MANAGE** it (steer it — send it a follow-up instruction — or stop/cancel it), as opposed to only watching subagents the parent spawned on its own.

## The question
**From outside the TUI — driving Claude Code only via tmux keystrokes (`send-keys`), the JSONL transcript, launch config, and HTTP hook callbacks (NOT the Agent SDK) — can the dashboard CREATE a subagent on demand and MANAGE it (steer / stop) once running? And through which concrete mechanism?**

Judge each capability on the two axes that decide feasibility for this dashboard:
- **DRIVABILITY** — can the sidecar *initiate* the operation from outside? (e.g. type a prompt into the parent's pane that induces a `Task` spawn; is there any way to *target* an already-running subagent with a follow-up or a cancel?)
- **OBSERVABILITY** — can the sidecar *see* the result well enough to manage it? (Given the known pending-vs-active limit and transcript-derived roster.)

Concretely address:
1. **CREATE** — Is spawning a subagent only ever the parent model's *own* decision (it calls `Task` when it wants to), or can the operator reliably induce a specific subagent spawn from outside — e.g. by sending the parent a prompt that instructs it to spawn one? How reliable/steerable is that (does the model comply deterministically, or is it best-effort)? Is there any non-SDK way to spawn a subagent *directly* (not via the parent's tool call)?
2. **STEER** — Once a subagent is running, is there any way from outside to send *it* (not the parent) a follow-up instruction? Subagents are typically not independently addressable over tmux (they run inside the parent process, not as separate panes). Confirm whether any native mechanism (a `SendMessage`-style primitive, an addressable id, a hook response) can target a running subagent — or whether steering is only possible via the parent.
3. **STOP** — Can a running subagent be cancelled/stopped from outside without killing the parent? (e.g. an interrupt that targets the subagent, or is the only lever interrupting the parent turn?)
4. **Native primitives that might change the answer** — evaluate whether `Task`, `SendMessage`, `Workflow`, agent-teams / teammate-spawning, or any documented subagent-management surface is reachable **natively over the TUI** (vs SDK-only / experimental). For each, tag whether it exists natively and whether it's drivable over tmux.

## Constraints on a valid answer
- **TUI-over-tmux is the control surface, NOT the Agent SDK.** A mechanism reachable only via the SDK is a costed exception — call it out explicitly and don't make it the load-bearing recommendation.
- **No dependence on unshipped / experimental features** (e.g. agent-teams) as the primary answer; evaluate them but keep the recommendation robust if they don't ship.
- **Respect the known limits:** subagents aren't separate tmux panes; the bridge can't tell pending from active today. Any create/manage story must work within (or explicitly overcome) those.
- **Degrade to an honest fallback:** if create/manage isn't drivable from outside, say so plainly — the fallback is that subagents stay **observe-only** (as today) and "creation/management" stays a backlog item.

## What is already known / assumed (do not re-derive)
- Subagents are **observable today** — roster/status/usage derived from the parent's transcript; the only observability gap is pending-vs-active.
- The dashboard does **not** use the Agent SDK for the main path.
- Two independently-spawned tmux agents are separate OS processes with **no shared in-process bus**; all cross-agent routing goes through the sidecar. A subagent, by contrast, lives *inside* its parent — so it is not independently addressable the way two top-level agents are.
- The hook channel can deliver `SubagentStart` / `SubagentStop`-style events (candidate events — confirm they exist on the current build) which would improve *observability*, but observability ≠ drivability.

## Deliver a structured report
Produce a single, self-contained report the operator can retrieve in **one action**. Return it as **one downloadable Markdown file if your tool supports it**, otherwise as the entire report inside **one fenced code block / canvas / artifact** (never scattered across the chat), and give a **suggested filename: `s10-research-22-subagent-management.md`** so it drops straight into `dev/notes/research/`. Use exactly these sections:
1. **Restated question** — create / steer / stop of subagents from outside the TUI, in your own words.
2. **Options considered** — each candidate mechanism for CREATE, STEER, and STOP, described concretely.
3. **Trade-offs** — for each: what it costs, where it breaks, what it assumes; cover drivability AND observability over tmux, and flag any SDK-only path.
4. **Per-capability verdict table** — rows CREATE / STEER / STOP (and per native primitive: `Task` / `SendMessage` / `Workflow` / agent-teams), columns: *exists natively (non-SDK)?* / *observable?* / *drivable-over-tmux?* / verdict **adopt / observe-only / skip**.
5. **Per-finding confidence** — tag each material claim confirmed / plausible / speculative; flag every claim needing a live spike or in-repo check.
6. **Sources & citations** — links/titles for every non-obvious claim.
7. **Recommendation + fallback** — a concrete path (what, if anything, to build for subagent create/manage, and via which mechanism), AND the honest fallback (subagents stay observe-only; creation/management stays backlog). Note explicitly where this agrees or disagrees with the broader §10-13 native-primitives finding.
