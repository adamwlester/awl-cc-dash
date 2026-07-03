# RESEARCH PROMPT — Adopting a push-based Claude Code HTTP-hook event stream as the primary run-state signal

> Paste this entire message into a fresh ChatGPT or Claude web session. It is fully self-contained — you do not need any repository or local file.

> **Additional research candidate (not a required core item).** This is an optional deep-dive on a cross-cutting architectural question. The framing note above is internal — no action needed from you; just treat this as a standalone question and answer it on its merits.

## Standing note (read first)
You have NO access to the awl-cc-dash repository or any of its files. Answer from general knowledge, official Claude Code / WSL2 / tmux documentation, and the web. Cite your sources inline. Tag every finding with a confidence level — **confirmed** (documented, or you verified it), **plausible** (reasonable inference, untested), or **speculative** (educated guess). Explicitly flag any claim that would need to be verified against the actual repo or a live spike before we rely on it. Everything you need is embedded below; do not ask for files.

## System context
awl-cc-dash is a single-window Electron desktop app (Windows, one operator) that talks to a FastAPI "sidecar" service on `127.0.0.1:7690` over HTTP + Server-Sent Events. The sidecar is the brain: it owns all cross-agent coordination state. The sidecar drives Claude Code coding-agent sessions as DETACHED tmux sessions running inside WSL2 (Windows Subsystem for Linux 2, Ubuntu) — one real `claude` CLI process per agent — and reads each agent through two channels: `tmux capture-pane` (a ~1s poll of the terminal screen, classified into idle / generating / permission-prompt) and the agent's JSONL (JSON-Lines; one JSON object per line) transcript file on disk. The primary control path is this tmux / terminal-UI (TUI) bridge — **NOT** the Claude Agent SDK. (A second, limited-use in-process Agent-SDK driver exists only for non-interactive utility passes like a "Revise/Summarize" text rewrite; it never drives the interactive coding agents and is not the main path.) A third inbound channel exists: each WSL agent's Claude Code hooks POST back to the sidecar over HTTP (the sidecar resolves the WSL2 default-gateway IP, because `localhost` from inside WSL2 does not reach the Windows host).

Question-specific detail:
- **Today the primary run-state signal is screen-polling.** `capture-pane` is sampled ~1s and classified into idle / generating / permission-prompt / unknown. This works and is the current floor.
- **The sidecar already runs an HTTP server and already ingests SOME hooks — but NOT for run-state.** Specifically: `PostToolUse` and `Stop` (used to deliver queued "inject" context to a running agent at a safe tool boundary — this path is proven live) and `PreToolUse(ExitPlanMode | AskUserQuestion)` (intended to raise plan/decision cards in the UI — this path is wired but spike-gated and unproven under the bridge). Run-state itself is still derived by polling the screen, not pushed by hooks.
- **The WSL2→Windows networking is already solved for those existing hooks.** WSL2's NAT means `localhost` from inside WSL2 does not reach the Windows host, so the sidecar runs `ip route show default` to resolve the WSL2 default-gateway IP (cached, re-resolved per launch because it changes across WSL restarts) and hands each agent a hook URL of the form `http://<gateway-ip>:7690/internal/hooks/...`. Hooks are best-effort: if the gateway can't be resolved, the agent still launches — without hooks.

## The question
Should the dashboard adopt a **PUSH-BASED Claude Code HTTP-hook event stream** — every agent's hooks POSTing each lifecycle event (candidates: PreToolUse / PostToolUse / PermissionRequest / Stop / Notification / UserPromptSubmit / SubagentStart / SubagentStop / StopFailure) to the sidecar — as the **PRIMARY run-state signal**, replacing or augmenting the current ~1s screen-polling? And if so, how should it be engineered — the exact event set worth registering, the HTTP-hook config shape, latency/ordering/dedup under many concurrent agents, the WSL2→Windows gateway networking, and the fallback for hookless sessions?

## Constraints on a valid answer
- The control surface is **TUI-over-tmux**; the WSL2→Windows default-gateway HTTP hop is the transport (already working best-effort for the existing hooks). Any design must live within that transport.
- The screen heuristic **must remain a FALLBACK** for hookless sessions. An agent may launch without hooks (if the gateway can't resolve, or if hooks are disabled), so run-state must still degrade gracefully to polling. Do not assume hooks are always present.
- **No dependence on unshipped, experimental, or undocumented Claude Code features.** Several event names above (e.g. `PermissionRequest`, `SubagentStart`, `StopFailure`) are candidates that may not be real, documented hook events — for each event you rely on, confirm it exists in the official Claude Code hooks documentation and mark any uncertain one for spike verification.
- Address the hard engineering questions concretely, not in the abstract:
  - **Latency & event ORDERING** under many concurrent agents, given async fire-and-forget hooks with short timeouts.
  - **Dedup / merge** of per-session state — sequence numbers? a per-agent state arbiter? how to reconcile out-of-order arrivals?
  - **Which exact event set** is worth registering (cost/benefit per event; which ones actually move run-state vs. which are noise).
  - **Replace vs. run-alongside** — should hooks REPLACE screen-polling for run-state, or run as the authoritative-when-present layer over polling as the floor?

## What is already known / assumed (do not re-derive)
- **This is an extension, not a greenfield build.** The sidecar already ingests a subset of hooks over a working WSL2-gateway HTTP path; adding more events to that path is incremental.
- **Screen-polling is the current, working floor** and is the intended fallback — not something to remove blindly.
- **A deterministic transcript overlay** — a `tool_use` id in the JSONL transcript with no matching `tool_result` implies the agent is still working — is a documented-in-general technique that can cross-check pushed state and harden generating-vs-idle against screen flicker.
- **Design pattern to evaluate on its merits** (drawn from prior art; assess soundness, do not treat as verified): a hook-based monitoring pattern that is entirely push-based — an async hook on PreToolUse / PostToolUse / PermissionRequest writes per-session `state` + `permission_mode` + `current_tool`, with a sequence number (`report_seq`) and a per-session state-arbiter to de-duplicate and merge under concurrency. The reported HTTP-hook config shape is `{"type":"http","url":"http://HOST:PORT/hooks/...","timeout":N}`. Confirm this shape and behavior against official docs.
- **Verify before relying (do NOT assume):** whether an HTTP-hook payload actually carries `permission_mode` and the current tool on every tool/turn event ("authoritative live mode-reading for free") is a *plausible, prior-art-observed* claim, not confirmed against official hook-payload documentation. Tag it plausible and flag it for spike confirmation on the installed CLI build.

## Deliver a structured report
Produce a single structured report the operator can paste straight into their research notes. Use exactly these sections:
1. **Restated question** — the question in your own words, to confirm framing.
2. **Options considered** — each distinct approach, described concretely.
3. **Trade-offs** — for each option: what it costs, where it breaks, what it assumes.
4. **Per-finding confidence** — tag each material claim confirmed / plausible / speculative (inline tags are fine).
5. **Sources & citations** — links/titles for every non-obvious claim.
6. **Recommendation + fallback** — one concrete recommended path, AND the honest fallback if the recommendation proves infeasible.
