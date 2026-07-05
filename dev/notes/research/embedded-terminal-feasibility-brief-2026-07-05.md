---
source: claude
created: 2026-07-05
tags: [research, feasibility, console, terminal, xterm, node-pty, ttyd, tmux, wsl2, architecture-alignment]
---

# Research Brief: Embedding a live terminal (run Claude in-window, still intercept the output)

**Date:** 2026-07-05
**Scope:** Whether the dashboard can embed a real terminal, run a Claude Code agent live inside it, and still work with that agent's output programmatically — and, critically, how that idea lines up with the *already-settled* design and the research the repo has already done. This is an alignment + approach brief for whoever builds it later, not a fresh from-scratch investigation.

---

## TL;DR (plain language)

Yes — this is feasible, and it is a proven pattern (it is how VS Code, Wave, Tabby, and Hyper all work). More importantly, **it is not a new feature.** The dashboard already specs exactly this surface — the per-agent **Console** (the "watch and type into the agent's real terminal" tab, `ARCHITECTURE.md` §7.13) — and already logs the one remaining question about it as an open item (§10 #5, "Console rendering fidelity"). A live feasibility spike on 2026-07-02 already **proved the hard half**: keystroke passthrough works, and the terminal's colours/spinners are recoverable. What's left is a frontend choice, not an engine unknown.

The real decision hiding inside the user's question is a fork the docs have never explicitly reconciled: **do we render the terminal by *polling* snapshots (the conservative path the settled Console design picked), or by *streaming* a live attached terminal (the more ambitious path an earlier in-repo research doc actually recommended)?** The user's instinct — "a real terminal" — matches the *streaming* recommendation. Both are viable; they differ in feel, effort, and how cleanly they fit our "thin frontend, smart sidecar" architecture.

One misconception worth killing up front: embedding the terminal does **not**, by itself, give you a cleaner way to read the agent's output. An interactive Claude terminal only ever emits a *painted screen*, however you tap it. The clean, machine-readable stream already exists elsewhere — the on-disk transcript the dashboard already reads. So: embed the terminal for the **human**; keep reading the **transcript** for the machine. They stay separate, exactly as the design already has it.

**Bottom line:** don't do more open-ended research (the pattern is settled and the repo already researched it). Decide the polling-vs-streaming framing, then — if streaming — run one small, targeted spike.

---

## Sources

**Internal — the design this must align with (primary):**
- The system reference, [`docs/ARCHITECTURE.md`](../../../docs/ARCHITECTURE.md): the **Console** spec (§7.13 — the focused-agent "real terminal mirror + keystroke passthrough" tab); the **open-question queue** (§10 #5 "Console rendering fidelity", already spike-proven on the engine side); the **thin-client boundary** (§2 and §4.1 — the frontend is a thin HTTP/SSE client, the sidecar is the single source of coordination truth); the **frozen-renderer rule** (§4.4 — the visible UI is frozen and rebuilt fresh, but the Electron shell/transport plumbing is not); the **transcript-as-master-record** policy (§8.6) and the **event envelope** (§7.1); the **driver seam** and the deliberate `sdk`-driver carve-out for non-interactive work (§6.1–§6.3); the **bridge internals** (§6.4).
- The frontend↔sidecar contract, [`frontend/src/renderer/api.ts`](../../../frontend/src/renderer/api.ts): the current Console surface is `consoleRun()` returning a `ConsoleRunResult { screen }` — a one-shot screen scrape. There is **no** streaming-terminal endpoint in the contract today.
- The design/UI intent, [`design/DESIGN.md`](../../../design/DESIGN.md): the Console is the focused-agent left-pane tab whose bottom strip is the slash-command run bar; it repaints to whichever agent is selected.

**Internal — prior research already done (this is the external grounding; it did not need redoing):**
- [`electron-agent-dashboard-architecture-research.md`](electron-agent-dashboard-architecture-research.md) (2026-04-01) — a deep survey of *this exact question*: xterm.js + its attach addon, `node-pty`, `ttyd` (terminal-over-WebSocket), and the reference terminals (VS Code, **Wave** 18.8k★, **Tabby** 70k★, Hyper, **Superset**). It lays out three embedding approaches, the WSL2-networking caveats, and the known `node-pty` Windows/Electron issues. This is the source of the external facts below.
- [`research-cli-stream-and-permissions-api.md`](research-cli-stream-and-permissions-api.md) — the CLI's stream-interception surface: `claude -p --output-format stream-json --verbose [--include-partial-messages]` emits clean NDJSON (messages, tool calls, results, permission events); this is the *non-interactive* print mode the Agent SDK uses. It establishes the interactive-vs-print-mode split that Finding 4 turns on.

**Internal — spike evidence & project history:**
- `test_console_mirror_live` (live tmux/WSL, 2026-07-02), cited in `ARCHITECTURE.md` §10 #5: keystroke passthrough works and ANSI is recoverable from the pane via `capture-pane -e`.
- [`DEVLOG.md`](../../../DEVLOG.md) archive-01 digest: records the sandbox-era pivot *away* from xterm/ttyd terminal embedding toward the SDK + `stream-json` path — relevant because the default has since flipped back to real TUIs (the `bridge` driver), reopening the embedding question (see Finding 2).

---

## Key Findings

**1. This is not a new feature — it's the already-designed Console, and the engine half is already proven.** The dashboard already specs a per-agent Console (`ARCHITECTURE.md` §7.13) as *"a live mirror of the agent's real terminal screen plus keystroke passthrough,"* with a slash-command runner and demand-driven polling. The one open thread is logged as §10 #5 ("Console rendering fidelity"), and it is marked **partially proven**: the 2026-07-02 live spike showed keystroke passthrough works and the terminal's colours are recoverable via `capture-pane -e`. The doc's own words: the remaining gap is *"pure frontend — a faithful xterm-class renderer — which is a build decision, not an engine feasibility question."* So the user's idea lands on already-mapped ground, and "can we?" is already answered **yes** for the currently-chosen approach.

**2. The pivotal distinction — polling vs streaming — and the settled design and the earlier research quietly disagree.** There are two genuinely different ways to put a terminal in the window:
- **Polled snapshot (what the settled Console picks):** the sidecar polls `capture-pane -e` a few times per second and xterm.js *paints those periodic snapshots*; keystrokes go back via the bridge's `keys()`. High-fidelity and ANSI-accurate, but still a fast-refreshing photocopy. Feasibility is proven; only the renderer component is unbuilt, and that is a build-sprint item, not a research question.
- **Streaming attach (what the user is describing, and what the 2026-04-01 research actually recommended):** a real tmux client — `ttyd` or `node-pty` running `tmux attach` — pipes the live pseudo-terminal byte stream *continuously* into xterm.js's attach addon. Sub-10ms latency, native terminal feel, tmux persistence for free.

The unreconciled fact: `ARCHITECTURE.md`'s settled Console is the **polling** model, but the in-repo 2026-04-01 research **recommended the streaming `ttyd` attach** ("Approach A") and explicitly judged polling *"not recommended for interactive use... fine for a dashboard view."* **The user's "real terminal" instinct matches the earlier research's recommendation, not the currently-settled spec.** Surfacing that gap is the single most useful thing this brief does.

There is a lineage that explains — but does not settle — the gap. The project **once evaluated terminal embedding (xterm/ttyd) and then pivoted away from it** to the Agent SDK + `stream-json` path (the sandbox-era "architecture pivot where the Agent SDK + stream-json replaced xterm/ttyd terminal embedding", per the [DEVLOG archive-01 digest](../../../DEVLOG.md)). Since then the architecture has **flipped the default back to real interactive TUIs** — the `bridge` driver is now the primary path and the `sdk`/`stream-json` engine is demoted to limited non-interactive use (§6.1–§6.3). But when the Console was speced against those revived real TUIs, it was given **capture-pane polling**, not a revival of the dropped xterm/ttyd embedding. So the user's question is, precisely: *now that real TUIs are the default again, should we revive the terminal-embedding approach we dropped back when the SDK path was primary?* That is a live, reasonable question — the original reason for dropping embedding (we'd moved off real TUIs entirely) no longer holds.

**3. Three concrete transports exist, with clear trade-offs** (from the 2026-04-01 research, still current):

| # | Approach | How it renders | Feel / latency | New dependency | Architecture fit | Main risk |
|---|----------|----------------|----------------|----------------|------------------|-----------|
| **A** | `ttyd` in WSL + xterm.js **attach addon** | live PTY stream over a WebSocket | native, sub-10ms | `ttyd` binary in WSL | renderer talks to a WS — closer to the thin-client model than B | can the renderer reach a WS *inside* WSL2 without manual port-forwarding? (untested); one `ttyd` per session vs a multiplexer |
| **B** | `node-pty` in Electron main spawns `wsl … tmux attach` | live PTY stream over Electron IPC | native (VS Code/Tabby/Hyper pattern) | `node-pty` native module | **opens a second Windows→WSL path that bypasses the sidecar** — a real departure from §2/§4.1 | `node-pty` Windows/Electron compatibility issues (worker_threads); native-module build/ABI |
| **C** | poll `capture-pane -e`, paint into xterm.js | periodic screen snapshots | ~100–200ms refresh; fine to watch, less "live" | none (bridge already does this) | **cleanest fit** — stays behind the sidecar HTTP boundary | not truly interactive-grade; it's a fast photocopy — *this is the settled Console* |

**4. "Run Claude in the terminal AND intercept the output" — the precise truth, so no one is misled.** For an *interactive* Claude TUI, the terminal's output is a rendered full-screen application (cursor moves, redraws, escape codes) **no matter how you tap it** — `capture-pane`, a `ttyd` attach, or even owning the PTY directly. There is no clean logical event stream coming out of the interactive terminal. The clean machine-readable stream (NDJSON of messages, tool calls, results, permission events) exists only in a *different, non-interactive run mode* — `claude -p --output-format stream-json` (per [`research-cli-stream-and-permissions-api.md`](research-cli-stream-and-permissions-api.md)) — which is exactly what the `sdk` driver and the utility passes use, and which the design deliberately reserves for non-interactive work (§6.3). **You cannot have both a live interactive TUI to watch and a clean stdout event stream from the same process; they are mutually exclusive modes.** The design already resolves this correctly: the agent runs the interactive TUI (for the human), and the clean programmatic truth is the **JSONL transcript on disk** (§8.6), which is already the event bus's source (§7.1). So the embedded terminal — any flavour — is a *human viewing/typing surface*; programmatic interception stays on the transcript. Embedding the terminal does not, by itself, give you a cleaner data tap than the dashboard already has. *(This refines the casual "own the PTY, tee the stream" framing: for a full-screen TUI specifically, owning the PTY still only yields painted screen bytes, not clean events.)*

**5. Architecture-fit constraints the implementer must respect.**
- **Thin-client boundary (§2, §4.1).** The frontend is a thin HTTP/SSE client; the sidecar is the single source of coordination truth. Approach **B** (`node-pty` in Electron main) opens a *second* Windows→WSL data path that bypasses the sidecar — a genuine architectural departure, not a detail. Approach **A** (`ttyd` WebSocket the renderer connects to) or a **sidecar-brokered WebSocket** keeps the boundary cleaner. This is a decision to make consciously.
- **Frozen-renderer rule (§4.4).** The xterm.js *component* is renderer surface — frozen, rebuilt fresh at the build sprint — so **don't build the visible Console UI now**. But the *transport/shell plumbing* (a `ttyd` process, a `node-pty` bridge, a WS endpoint) is explicitly **not** frozen and is exactly the kind of feasibility unknown the shell is meant to prove out now. A transport spike is in-bounds today; polishing the on-screen terminal is not.
- **Don't embed N live terminals.** This already matches the design: the Console is per-focused-agent and visibility-gated (§7.13 polls only while visible). Any attach approach should be on-demand for the focused agent — attach-on-open, detach-on-close — never one live terminal per agent across the fleet.

**6. The novel risk at the intersection — the one thing a spike must actually check.** Neither prior doc examined the *coexistence* this system uniquely needs: the sidecar runs a **continuous `capture-pane` poll on every session** for coordination (status classification, permission-menu detection, transcript resolution — §6.2, §6.4). If a live xterm.js client *also* attaches to that same tmux session, tmux resizes the window to the smallest attached client, and tmux's own behaviours (status bar, copy-mode, prefix keys, scroll capture) can leak into the pane — the **Superset finding** the 2026-04-01 doc quotes: *"tmux takes over the scroll bar, selection, hotkeys... this hijack inside xterm.js makes it feel extremely clunky."* The concrete hazard for us: a live attach could change the pane geometry the sidecar's scraper assumes, or garble what `capture-pane` returns mid-poll — potentially disturbing the very coordination reads the whole product depends on. `ttyd` may insulate this better than raw tmux-in-xterm because it manages its own PTY layer, but that is untested here. **This — live attach running concurrently with the sidecar's capture-pane polling on one session — is the specific, load-bearing unknown, and it is exactly what a spike should isolate.**

---

## Confidence Assessment

**High confidence:**
- Terminal embedding is a settled, mature pattern — VS Code, Wave (18.8k★), Tabby (70k★), and Hyper all ship xterm.js + a PTY backend. (2026-04-01 research.)
- The engine half of the *current* (polling) Console approach is spike-proven: `capture-pane -e` recovers ANSI and keystroke passthrough works. (`test_console_mirror_live`, live, 2026-07-02; §10 #5.)
- The interactive-TUI vs clean-NDJSON-stream mutual exclusivity is well-established from the CLI internals research — the clean stream is print mode only. (`research-cli-stream-and-permissions-api.md`.)
- This capability is already homed in the design as §7.13 + §10 #5; it is not net-new scope.

**Medium confidence:**
- `ttyd`-attached-to-tmux is the best *streaming* transport (the 2026-04-01 recommendation) — but WSL2 networking (can the Electron renderer reach a `ttyd` WebSocket running inside WSL2 without hand-rolled port-forwarding?) and multi-session management (one `ttyd` per session vs a multiplexing proxy) are flagged **unverified**.
- `node-pty` as the fallback transport works in principle (it's the VS Code/Tabby pattern) but carries flagged Windows/Electron compatibility issues (worker_threads, native-module build).

**Low confidence / unverified:**
- Whether a live attach coexists cleanly with the sidecar's continuous `capture-pane` polling on the *same* session (Finding 6) — untested by anyone, and unique to our topology.
- Whether xterm.js + an attached tmux session avoids the "clunky hijack" in *our* setup specifically — untested.

---

## Gaps

- **Coexistence of live-attach + capture-pane polling on one session** — unexamined anywhere; the highest-value unknown (Finding 6).
- **WSL2 networking** for a renderer→`ttyd`-in-WSL WebSocket — flagged in the 2026-04-01 research, never tested.
- **Multi-session `ttyd` management** at fleet scale — one instance per session vs a single on-demand multiplexing proxy; no source settled it.
- **The unmade product decision:** does the design intend to *upgrade* the Console from polling to streaming, or keep polling and treat xterm.js purely as a high-fidelity snapshot renderer? This is currently implicit, and it determines whether any of the streaming work is even in scope.

---

## Recommended Next Steps (prioritized)

1. **Decide the framing question first (cheap, architecture/operator call).** Is the goal to *render the existing polled Console faithfully* — i.e. finish §10 #5 as already speced, which is build-sprint frontend work needing **no spike** — or to *upgrade the Console to a real streaming terminal* (adopt the 2026-04-01 recommendation), which needs the spike below? These are different amounts of work and different architectures; everything else follows from this answer.
2. **If streaming: run one focused spike** (the smallest thing that resolves the real unknowns; slot it against the existing §10 #5 item). Attach **one** live terminal — start with `ttyd` (Approach A) — to **one** existing bridge tmux session, and in the same run **keep the sidecar's `capture-pane` poll running against it**. Verify: **(a)** does the Electron renderer reach the `ttyd` WebSocket across the WSL2 boundary without hand-rolled port-forwarding; **(b)** does the live attach perturb the poller's screen reads, status classification, or permission-menu detection (Finding 6); **(c)** does it feel native or hijack-clunky. Fall back to `node-pty` (Approach B) only if `ttyd`'s WSL networking fails. Shape it as a `tests/*_live.py` feasibility spike, the same way §10 items are settled ([`tests/README.md`](../../../tests/README.md)).
3. **Reconcile the docs either way.** Update the Console open question (§10 #5) — and, if the decision is to pursue streaming, the Console spec (§7.13) — to record the polling-vs-streaming choice explicitly and cite the 2026-04-01 research, so the divergence between that research's recommendation and the settled design stops being silent. (The Console's *visual form* is `DESIGN.md`'s; this is a *transport/architecture* note, so it belongs in `ARCHITECTURE.md`.)
4. **Keep the interception model unchanged.** Whichever terminal transport wins, programmatic interception stays on the JSONL transcript / event bus (§8.6, §7.1). Do **not** parse the terminal byte stream for machine use, and do **not** switch agents to `stream-json` print mode to get clean data — that would forfeit the interactive real TUI the whole product is built on (§6.2). Terminal = human surface; transcript = machine surface.
