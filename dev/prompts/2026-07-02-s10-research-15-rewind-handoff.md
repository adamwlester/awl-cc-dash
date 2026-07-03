# RESEARCH PROMPT — Does any mechanism exist to rewind (truncate-and-resume) or fork (branch-from-point) a Claude Code conversation?

> Paste this entire message into a fresh ChatGPT or Claude web session. It is fully self-contained — you do not need any repository or local file.

> **This is the gating research for a feature the product cannot build until this question is answered.** A downstream engineering spike is *blocked on your findings* and will be written from them. Be rigorous about the confirmed/plausible/speculative distinction — a false "yes, it's possible" would send the spike chasing a mechanism that doesn't exist.

## Standing note (read first)
You have NO access to the awl-cc-dash repository or any of its files. Answer from general knowledge, official Claude Code / Claude Agent SDK / WSL2 / tmux documentation, and the web. Cite your sources inline. Tag every finding with a confidence level — **confirmed** (documented, or you verified it), **plausible** (reasonable inference, untested), or **speculative** (educated guess). Explicitly flag any claim that would need to be verified against the actual repo or a live spike before we rely on it. Everything you need is embedded below; do not ask for files.

## System context
awl-cc-dash is a single-window Electron desktop app (Windows, one operator) that talks to a FastAPI "sidecar" service on `127.0.0.1:7690` over HTTP + Server-Sent Events. The sidecar drives Claude Code coding-agent sessions as **DETACHED tmux sessions running inside WSL2** (Windows Subsystem for Linux 2, Ubuntu) — one real `claude` CLI process per agent — and reads each agent through two channels: `tmux capture-pane` (a ~1s poll of the terminal screen) and the agent's **JSONL** (JSON-Lines; one JSON object per line) **transcript file on disk**. The primary control path is this tmux / terminal-UI (TUI) bridge — **NOT** the Claude Agent SDK. (A second, limited-use in-process Agent-SDK driver exists only for non-interactive utility passes like a "Revise/Summarize" text rewrite; it never drives the interactive coding agents. It *could*, in principle, be pressed into service for a specific non-interactive operation if — and only if — that turned out to be the sole path to some capability, but that would be a deliberate exception, not the main path.)

Two facts about how sessions are identified and stored (relevant to any transcript-surgery idea):
- Each agent is launched with a **pinned Claude session id**; its transcript file is named **`<session-id>.jsonl`**, which is how the sidecar resolves *this* agent's own transcript even when several agents share a working directory.
- Resuming today means `claude --resume <session-id>` — which reattaches / rebuilds **the same whole conversation from its transcript**. There is no known flag that resumes "the conversation up to message N."

## The feature this unblocks (why we're asking)
The dashboard's design presents two first-class Agent controls, both driven off a **Timeline** (the ordered list of messages sent to the model):
- **Rewind** — "roll *this* agent back to a chosen earlier point in its conversation and resume from there" (i.e. **truncate at message N and continue**, discarding everything after N).
- **Handoff** — "branch from a chosen point into a *new* agent" (i.e. **fork**: create a new session that inherits the conversation *prefix* up to point N, then diverges independently, leaving the original intact).

Neither is documented in our architecture, and we do not know whether the underlying engine can do either. That is exactly what you must determine.

## The question
**Does any mechanism exist — for a Claude Code session — to (A) truncate a conversation at an arbitrary earlier message N and resume from there, and/or (B) fork/branch a new session that carries the conversation prefix up to message N while leaving the original session intact?**

For each of (A) rewind and (B) fork, determine whether a viable mechanism exists, via any of these candidate paths (evaluate each; add others you know of):
1. **Transcript-file surgery + `--resume`** — physically edit/copy the `<session-id>.jsonl` file (truncate lines after N for rewind; copy-to-a-new-id and truncate for fork), then `claude --resume` the (new) id. Does `--resume` faithfully rebuild state from a *modified* transcript? Does it validate/repair/reject an edited transcript? Are there integrity checks, summary/compaction records, or tool-call/tool-result pairing constraints that break if you cut mid-pair?
2. **Native CLI resume/continue/fork semantics** — do `--resume`, `--continue`, `--fork-session` (if it exists), session-branching, or any documented checkpoint/rewind command support resuming at a point *other than* the end, or spawning a branch? (Claude Code has shipped a **checkpoint/rewind** capability at various times — determine precisely what it does: does it rewind *code/file* state, *conversation* state, or both? Is it drivable non-interactively / from outside the TUI?)
3. **Claude Agent SDK session forking** — does the SDK expose conversation forking, resuming-at-a-point, or message-history manipulation that the TUI does not? (If yes, note it clearly — it would be reachable only via our limited SDK driver, a deliberate exception to the tmux path, so flag that cost.)
4. **Reconstruct-and-replay** — instead of resuming an engine session, start a *fresh* session and seed it with the prefix (e.g. feed messages 1..N as context / a system-prompt preamble). What are the fidelity limits (lost tool-call state, lost thinking, token cost, no true "continuation")? Is this a real fork or only an approximation?
5. **Anything else** — internal session-state files beyond the JSONL, `~/.claude` session records, an undocumented API, etc.

## Constraints on a valid answer
- **The control surface is TUI-over-tmux**, and the **JSONL transcript is treated as the master record.** A mechanism that requires only file operations + a documented CLI resume is ideal; one that requires the Agent SDK is a costed exception; one that requires an interactive-only TUI gesture that can't be driven from outside is close to useless to us (say so).
- **Distinguish conversation state from file/code state.** Claude Code's "rewind/checkpoint" features have historically included rewinding *edited files*. We care specifically about the **conversation** (the message history sent to the model). If a feature rewinds files but not the conversation (or vice-versa), say exactly which.
- **No dependence on unshipped, experimental, or version-fragile features** as the load-bearing answer. If the only path is an experimental flag, mark it speculative and give the honest fallback.
- **Respect tool-call/tool-result integrity.** A Claude transcript pairs each `tool_use` with a later `tool_result`; truncating between a pair, or resuming a transcript with a dangling tool call, may be rejected or corrupt state. Address whether truncation must fall on safe boundaries (turn ends only?) and how one finds them.
- **The answer must degrade to an honest fallback.** If neither true rewind nor true fork is feasible, say so plainly and describe the best approximation (e.g. whole-session `--resume` only; reconstruct-and-replay with stated fidelity loss; or cutting the feature).

## What is already known / assumed (do not re-derive)
- Whole-session resume works: `claude --resume <session-id>` rebuilds the entire conversation from the transcript. The open question is resuming/branching at a point *other than the end*.
- The transcript is `<session-id>.jsonl`; the session id is pinned at launch and the sidecar can read, copy, and (in principle) edit these files on disk in WSL2.
- The dashboard does NOT use the Agent SDK for the main path; an SDK-only mechanism is available but costly to adopt.
- Handoff's *UI* half — opening a "Create agent" form pre-populated with the source agent's settings — is already handled; the **unknown** is only the *conversation-carry* (fork) half.

## Deliver a structured report
Produce a single, self-contained report the operator can retrieve in **one action**. Return it as **one downloadable Markdown file if your tool supports it**, otherwise as the entire report inside **one fenced code block / canvas / artifact** (never scattered across the chat), and give a **suggested filename: `s10-research-15-rewind-handoff.md`** so it drops straight into `dev/notes/research/`. Use exactly these sections:
1. **Restated question** — rewind (A) and fork (B), in your own words, to confirm framing.
2. **Options considered** — each candidate mechanism (1–5 above + any you add), described concretely, split by whether it serves rewind, fork, or both.
3. **Trade-offs** — for each: what it costs, where it breaks (transcript integrity, tool-pair boundaries, token cost, SDK-vs-tmux, version fragility), what it assumes.
4. **Per-finding confidence** — tag every material claim confirmed / plausible / speculative; **explicitly flag every claim that needs a live spike or in-repo check** before we rely on it.
5. **Sources & citations** — links/titles for every non-obvious claim (official docs preferred; version-date them where the behavior is version-sensitive).
6. **Verdict + recommendation + fallback** — a clear **YES / PARTIAL / NO** for each of rewind and fork; if YES/PARTIAL, the single most promising concrete mechanism to spike next (with the exact steps a spike would run: what files to edit/copy, what command to run, what to observe); if NO, the honest fallback and what to tell the team to cut or approximate.
