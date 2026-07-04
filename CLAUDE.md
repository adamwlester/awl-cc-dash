# CLAUDE.md

## PROJECT IDENTITY

This is **awl-cc-dash** — a dedicated VS Code/Claude Code workspace for the **AWL Multi-Agent Dashboard**: a single-window Electron desktop app for running, monitoring, and coordinating many Claude Code agents at once. Forked out of the old `claude-code-sandbox` general workspace on 2026-06-21 (fresh git history). This runs on a real laptop — not a container or VM. Files outside the project directory are real and permanent.

The repo separates two layers: the **product** (the dashboard itself) lives in flat dirs at the root; the **build workflow** (how this gets built with Claude Code in VS Code) lives under `dev/`.

## FOLDER MAP

**Product (the dashboard):**

| Folder | Purpose |
|--------|---------|
| `frontend/` | The desktop app — Electron + React (electron-vite). **⚠ The React renderer (the visible UI) is a parked prototype** — frozen, to be **rebuilt fresh from the `design/` mockups at the build sprint**, *not* finished in place; don't build or refactor renderer UI now (the design lane owns that surface). The Electron **main-process shell** (sidecar lifecycle, window, packaging) is **not** frozen — it still needs feasibility proof. `api.ts` is the preserve-through-rebuild contract. Current renderer map + build strategy: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) §4/§4.4. |
| `sidecar/` | The FastAPI backend the frontend talks to (port 7690) — the **working MVP** service. It owns a pluggable **driver seam** for talking to agents, plus the feature modules behind the dashboard (event bus, hooks, inbox, scratchpad, library, console, and more). `bridge` (real Claude Code TUI via tmux/WSL2) is the **primary path and the default when no driver is named**; `sdk` (in-process Claude Agent SDK) is a limited-use opt-in. Full module + endpoint map and driver details: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) §5–§6. |
| `bridge/` | The agent-control backbone — tmux/WSL2 control of Claude Code sessions. Importable package (`from bridge import TmuxBridge`). See **CUSTOM TOOLING**. |
| `design/` | UI mockups, palettes, and the **design reference** (`DESIGN.md`). `mockup.html` is the current visual authority; `tokens.css` is the single source of truth for every design value (colors, type, spacing, radius, shadow); `behavior.js` is the **shared component behavior** (interaction logic), loaded by **both** `mockup.html` and `gallery.html` so they can't drift; `styles.css` is the **shared component CSS** linked by both; `gallery.html` is the **interactive component catalog**; `mockup-toolkit.js` is the `Ctrl+G` annotation overlay. |
| `archive/` | Retired-but-referenced material: the design lineage (old mockups/ui-plans under `design/`), rotated DEVLOG archives (`devlog/`), and retired notes/docs (`notes/`, `dev/notes/`, `docs/`). |
| `assets/` | Icon sets — `icons/agents/` (recolorable game-icons.net tiles) and `icons/ui/` (Lucide). |
| `tests/` | The pytest suite — a hermetic per-module unit tier, plus live integration, feasibility-spike, and browser-driven UI tiers that exercise the real bridge/sidecar. Layout + conventions: [tests/README.md](tests/README.md) and **TESTING** below. |
| `docs/` | Committed, curated product reference docs — home of [`ARCHITECTURE.md`](docs/ARCHITECTURE.md), the system/structure reference (see **KEY FILES**). |

**Build workflow & config:**

| Folder | Purpose |
|--------|---------|
| `dev/` | Claude-CLI / VS Code build-workflow assets — **not the app**: `notes/` (working notes + `research/`), `prompts/` (dev-loop prompts), `tools/` (`bootstrap-env.ps1`, `claude-context-extractor/`). |
| `.claude/` | Claude Code config — `settings.json` (permissions, `plansDirectory: ./.claude/plans`), `agents/`, `plans/`, `cc-exports/`. |
| `.vscode/` | VS Code workspace (`awl-cc-dash.code-workspace`), `settings.json`, `tasks.json`, `claude-prompts.code-snippets`. |

**Root files:** `CLAUDE.md`, `DEVLOG.md`, `requirements.txt`, `pyproject.toml`, `.gitignore`, `start-dashboard.bat` (launches the sidecar + Electron together).

## KEY FILES

Cross-cutting docs every session should know about — read the relevant one before diving in:

| File | What it is |
|------|------------|
| [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) | The **final-vision system reference** — the intended final system, written as settled architecture: the processes (Electron ↔ FastAPI sidecar `:7690` ↔ driver seam ↔ tmux/WSL2 bridge), the one-project product model, the coordination spine, and the storage model, with every product decision woven into the prose and **"⚠ Today"** markers wherever code hasn't caught up. **The doc leads the build**: builds converge on it and clear markers (the build backlog is its own §11 *Build backlog & queue*); its text changes only when a decision changes. The system counterpart to DESIGN.md (UI intent) and DEVLOG.md (history). |
| `DEVLOG.md` | Append-only project log (migration, backend, dashboard, tooling) — the **recent window**. **Read it before making changes**, and **log every repo change before you end the turn** — see the DEVLOG rule under [BEHAVIORAL RULES](#behavioral-rules) and the file header for format. Older entries are rotated into `archive/devlog/` and summarized in the file's **Archived history** index; read those archives **on demand** only when a task needs older history, not by default. |
| `design/DESIGN.md` | Ground-truth **design reference** for the dashboard's UI/UX intent — read it before any dashboard-design or frontend work. The mockups in `design/` (authority: `mockup.html`, with values in `tokens.css`) own the exact visuals. |
| `AGENTS.md` | Codex-specific entry point: points Codex sessions back to this guide and explains that Codex agents are support capacity for focused implementation, review, docs, testing, and repo-management work while Claude Max tokens are constrained. Claude agents should treat it as coordination context, not a replacement for this guide. |

## CUSTOM TOOLING

### bridge (tmux agent control)

Python package at the repo root: `bridge/` — the agent-control backbone. It drives Claude Code TUI sessions as **detached** tmux sessions inside WSL2 and reads them without any window (`capture-pane` for live screen state + the JSONL transcript for messages); a Windows Terminal tab opens only on an explicit attach via `show()`, never automatically on creation (see the bridge-sessions rule under **BEHAVIORAL RULES**), and sessions persist even if a tab is closed. Import it as `from bridge import TmuxBridge` (add the repo root to `sys.path` first if it isn't already), or drive it from the CLI with `python -m bridge <command>`. Full method reference, capabilities, and internals: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) §6.4.

### claude-context-extractor

Python dev utility at `dev/tools/claude-context-extractor/`. Pulls a full **claude.ai** (web/desktop) conversation — tool calls, results, citations, artifacts, and full thinking — into a raw `conversation.json` plus a clean `transcript.md`, extracted `artifacts/`, and a `summary.md`, so external Claude context can be captured and handed to another session. Stdlib-only core; run it from its own folder, where the commands and auth (a gitignored, account-level `session_key.txt`) live.

### ui-verify (headed UI verification)

Node + Playwright launcher at `dev/tools/ui-verify/` — the standard way to drive the `design/` mockups in a **real headed Chromium** for UI verification. It opens the browser **parked behind your windows** (no focus theft, not throttled) yet renders identically to a front window, so every UI-verification pass can run headed without interrupting you. Script a drive with the `launch`/`serveDir` exports (see `selftest.mjs`), or use the CLI to open the mockup parked; screenshots go to `.scratch/ui-verify/`. Usage + the parked-vs-front parity proof: [`dev/tools/ui-verify/README.md`](dev/tools/ui-verify/README.md).

## TESTING

**Use pytest for all tests.** This is the standard — reach for it when adding or changing testable behavior, rather than writing ad-hoc scripts. The suite lives in `tests/` at the repo root and spans a hermetic per-module unit tier plus live integration, feasibility-spike, and browser-driven UI tiers that exercise the real bridge/sidecar. Each `tests/` dir owns a gitignored `log/` subdir for timestamped per-run debug logs. **The suite layout, tiers, markers, and conventions live in [`tests/README.md`](tests/README.md)** — read it before adding tests.

**How to run** (uses a repo-root `.venv`):
```powershell
tests\run.ps1                                  # runs everything in tests/ via .venv
.\.venv\Scripts\python.exe -m pytest tests\    # equivalent, direct
```
Create the venv if it's missing:
```powershell
python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt
```
No `testpaths` is configured — pass the path you want to run.

## BEHAVIORAL RULES

### Git — never branch without express permission
Work happens on **`main`**. Commit normal work directly to `main`; do **not** create or switch to a new branch without my explicit, in-conversation go-ahead.
- **This overrides the harness default.** The built-in Bash guidance ("if on the default branch, branch first") does **not** apply in this repo — never auto-create a `feature/*` (or any) branch as a side effect of starting work. This binds **every agent and subagent**, including autonomous, batch, and background runs.
- **Branch-creating commands require a yes first:** `git checkout -b` / `-B`, `git switch -c` / `-C`, `git branch <name>`, and `git worktree add`. These are gated in [`.claude/settings.json`](.claude/settings.json) (`ask`), so they will prompt — if one prompts, **stop and ask**, don't work around it. Read-only git (`status`, `log`, `branch -vv`, `diff`), committing to `main`, and `git push` all stay free — only branch creation prompts.
- **If a task genuinely needs branch isolation,** say so and wait for my explicit approval before creating anything. When approved and the work is merged, merge back to `main` and delete the branch rather than leaving it to accumulate.

### Scope & safety
- **Default to working inside the project directory — but step outside when the task genuinely needs it.** Going outside `awl-cc-dash` is allowed (reading a reference doc, checking global `~/.claude/` config, using a tool that writes to LocalAppData) when it clearly serves what you're doing. Treat it as a deliberate call, not a reflex: before you do it, be sure it's actually necessary and that an in-project option doesn't already cover it. Routine, reversible, out-of-project reads need no permission — just do them thoughtfully.
- **Confirmation is for the irreversible, and only when I'm here.** For anything destructive or hard to undo outside the project (deleting/overwriting files, changing global config), get my go-ahead first — but only when I'm reachable. Never let an out-of-project step block an unattended or long autonomous run. When you can't ask, take the conservative path and note what you did (and why) in your wrap-up. When you do touch global config (`~/.claude/`, etc.), explain the change either way.

### Working style
- **Clarity first, then concision.** Be practical and low-ceremony, but never at the cost of being understandable — a concise answer I can't follow is a failed answer. Write so I can actually read it: plain language, real sentences, structure over a wall of text. **When brevity and clarity pull against each other, clarity wins — every time. Never compress a sentence past the point where I can follow it on first read.**
- **Understand before you act.** Don't jump straight to changes on anything non-trivial — make sure you grasp what I'm asking and why first, and when a request is ambiguous or a decision is mine, check before building. Small, obvious, reversible steps don't need this; larger or irreversible ones do.
- **Lead with a plain-language overview, then the detail.** Especially for big topics, cross-cutting changes, or anything on the backend (the FastAPI sidecar, the bridge, drivers, SSE, async — largely outside my comfort zone): open with a short, high-level, lay-language summary of what's going on / what you did / what you're proposing, framed in outcomes, before the technical specifics. When I ask for "a high-level overview," that's the default I already want — not a special mode.
- **Always cite files and locations — but a pointer is an address, not an explanation.** When you discuss code or edits, link the exact spot as a clickable Markdown path — `[main.py:42](sidecar/main.py#L42)` — never a bare filename or an unlocated "the handler." That's how I follow what changed. **And never drop a bare section number, file, or symbol on its own — a naked "§7.5" or "the driver seam" — as if I already know it: say in plain words what it is and why it matters, then attach the link. The reference lets me verify the thing; it does not replace explaining it.**
- **Never hard-wrap text I'll edit.** In anything I work with directly — content inside code blocks in your replies, and every Markdown/text/code file in the repo (docs, DEVLOG, design notes, ARCHITECTURE) — write each paragraph as one continuous line and let the editor soft-wrap. Do not insert manual newlines to wrap a paragraph to a column width; frozen mid-paragraph line breaks are painful to reflow. (Structural newlines are fine and expected: separate list items, headings, table rows, and code lines still break normally — this is only about not width-wrapping running prose.) Ordinary conversational prose in a reply I'm only reading, not copying, can wrap however it likes.
- **Write transient artifacts to `.scratch/`** — screenshots, scratch HTML, debug dumps, ad-hoc server logs — never the repo root or other project folders. Prefix any `filename` you pass to screenshot/export tools with `.scratch/`. One-off files may be deleted when done; accumulation in `.scratch/` is acceptable.

### Editing discipline
- **Preserve intent, not mistakes — carry untouched parts forward faithfully.** When you edit a file or produce a new version of an existing artifact (for example, a new UI mockup branched from the prior one), reproduce the parts you weren't asked to change exactly as they were. Carrying them forward in full is real work and part of the task: don't skip, summarize, simplify, restyle, or drop sections just because faithfully reproducing them is tedious. The usual failure here is cutting corners, so when in doubt keep the prior version intact, and before finishing confirm nothing outside the requested change was lost or quietly altered.
- **This is about not *losing* work — it is not a license to under-edit.** It does not mean "touch as little as possible." When a task calls for a real refactor, do the complete job: change every place the change genuinely reaches, and don't leave it half-applied to feel safe. Faithful preservation and thorough, complete refactoring are both required — timid, partial edits are their own failure mode.
- **Fix what's clearly wrong when you pass it.** If you come across an obvious error, a stale reference, or a detail the rest of the repo contradicts, and you're confident it's wrong, correct it rather than faithfully preserving a known mistake — then note the fix (and DEVLOG it if it's a repo change). Preservation protects the prior author's intent, not its bugs. If you're not sure it's wrong, leave it and flag it instead of silently changing it.
- **CLAUDE.md is not exempt from "update all related docs."** When a change makes any statement in this file stale — a folder's purpose, a default, a pointer, a rule — update CLAUDE.md in the same pass, just as you would `docs/ARCHITECTURE.md`, `design/DESIGN.md`, or `DEVLOG.md`. A stale CLAUDE.md is the one every future session silently inherits, so it's the highest-priority doc to keep true, not the easiest to forget.

### DEVLOG — project memory (not optional)
`DEVLOG.md` is the project's memory; an unlogged change is, to the next session, a change that never happened.
- **Log every repo change.** Before you end any turn in which you created, deleted, moved, or meaningfully edited a file (code, config, docs, or design) — and before you tell the user you're "done" — append a new entry at the **bottom** of the Log (it runs oldest → newest). Default to logging: the bar is "did the repo change?", not "was it significant?" — if you're unsure, it qualifies.
- **Format** (append-only; never edit or delete past entries — `DEVLOG.md` is 100% append-only, with no in-place-editable sections): a `### YYYY-MM-DD HH:MM:SS — short title` heading, 1–4 lines on what changed and the observable outcome, then a `Files:` line.
- **Rotate when long.** Past ~700 lines, move the oldest entries (top of the Log) **verbatim** — cut only at `### ` headings, never mid-entry — into the newest `archive/devlog/DEVLOG-archive-NN.md`, appending in order, until `DEVLOG.md` is back under ~300 lines; then refresh the digest + index row in the **Archived history** section at the bottom. Never edit archived entries.
- Full rules and the rotation procedure live in the `DEVLOG.md` header — follow those.

### Design changes — reuse first, then propagate across all six `design/` files
`design/` is one system in six files, each owning one thing: **`tokens.css`** = every value · **`styles.css`** = shared component CSS (linked by both the mockup and the gallery) · **`behavior.js`** = shared component **behavior / interaction logic** (loaded by both the mockup and the gallery — the single source of truth for how controls actually act, so the two can't drift) · **`mockup.html`** = the working app surface + each component's `data-comp` name and `data-status` marker · **`gallery.html`** = the **interactive catalog** (every reusable component shown as the *real, live* component — variants side-by-side, operable controls you can actually drive, driven by the shared `behavior.js`) · **`DESIGN.md`** = the rules and intent. **Read [`design/DESIGN.md`](design/DESIGN.md) before changing any of them.**
- **Reuse before adding.** Check `tokens.css` for an existing token and `styles.css` for an existing class/pattern *before* introducing a new one. Never hardcode a value that belongs in `tokens.css` (colour, type, spacing, sizing, radius, border-width) — reference it via `var()`. New tokens are additive; never rename an existing one.
- **Propagate every change to all the files it touches:** a **value** → `tokens.css`; **component CSS** → `styles.css`; a component's **behavior / interaction logic** → `behavior.js` (shared, so the mockup and gallery stay in lockstep — never duplicate behavior into one of them); a **new or changed component** → tag it in `mockup.html` (`data-comp`, plus `data-status` if dormant/undecided) **and** add a `gx-card` to `gallery.html` with the component's *real markup* (behaviour comes free from `behavior.js`; show every variant, and label any data-state — disabled/empty/error — that can't be reached by interacting) **and** register its name in `DESIGN.md`; a **rule or intent** → `DESIGN.md`. A change that lands in only one file when it owes others is unfinished.
- **No design value lives outside `tokens.css`** except where DESIGN.md documents an exception (currently: the Console's self-contained `--term-*` palette, the per-instance `--nc` agent-colour binding, and runtime values like progress-bar widths and the resizable panes' default divider positions — their inline `flex:` ratios; the panes' min/max size *constraints*, the fixed dev-window size, and the pinned column widths ARE tokens: the `--win-*` / `--col-*` / `--pane-*` Layout set). **And nothing in `design/` references any backlog** (the build backlog lives in `docs/ARCHITECTURE.md` §11; all backlogs stay out of `design/` so the design system stays at its six files). Verify the result per **Verifying UI changes** below.

### Verifying UI changes
- **Drive the rendered UI — never hand back on static checks alone.** For anything that renders (the dashboard mockups above all), `node --check` / grep / reading the diff is necessary but NOT sufficient — it says nothing about layout, wrapping, overflow, or whether a control actually works. Layout, formatting, overflow, and dynamic behavior are part of the deliverable — not the user's job to catch.
- **Verify in a real headed browser via the `ui-verify` script — one pass, not two.** Drive the change through [`dev/tools/ui-verify/`](dev/tools/ui-verify/) (see CUSTOM TOOLING): it serves over `localhost` and runs headed **parked behind the user's work**, so it never steals focus — run it freely, even while they're active. Every pass is already headed, so there is **no headless-vs-headed rendering gap to reconcile — do not add a separate "headed parity" re-screenshot pass** (the retired workflow iterated headless, then re-shot once headed to confirm the two matched; that second pass caught only mode drift, which no longer exists). **"One pass" drops the mode-reconciliation pass only — it does *not* mean checking fewer states or controls.**
- **In that pass, before you call a UI change done:** **resize the affected panel(s) to both narrow and wide extremes** (this layout is resizable, and that is where it breaks), and **click through every control you touched** — expand/collapse, toggles, each dropdown/menu, the whole flow. Screenshot each state, compare it to the stated intent, and fix what's off — all before reporting back. **This width-scrutiny + click-coverage is the real quality gate, not the browser mode** — the layout misses that slipped through before came from thin screenshot scrutiny, not from which mode was used.

### Bridge sessions: a terminal opens only on explicit request, never as a side effect
The bridge drives Claude Code agents as **detached** tmux sessions in WSL2 and reads them via `capture-pane` (screen state) and the JSONL transcript (messages), so a session needs no window to run or be read. A Windows Terminal tab is only a way for a human to watch a session; an auto-popped tab steals the user's desktop focus and routes their keystrokes into the CLI mid-task.
- **Programmatic creation must never open a tab as a side effect.** Anything that creates sessions in code (the test suite, fixtures, batch spawns, the sidecar's bridge driver, scratch scripts) creates them tab-less. Don't reintroduce automatic tab-opening when adding any of these.
- **A tab opens only on a deliberate human request.** That request is the dashboard user choosing to attach in the product, the user asking to watch a session during dev, or a human running `python -m bridge create` by hand at a terminal (where invoking the command is itself the request, so the CLI may default to showing a tab). The mechanism is the opt-in path (currently `create(..., show=True)` / the `show()` method). This rule constrains *automatic* behavior only; it does not limit the product's deliberate manual-attach feature, which DESIGN.md calls out as a tmux advantage.
