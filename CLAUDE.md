# CLAUDE.md

## Project identity

This is **awl-cc-dash** — a dedicated VS Code/Claude Code workspace for the **AWL Multi-Agent Dashboard**: a single-window Electron desktop app for running, monitoring, and coordinating many Claude Code agents at once. Forked out of the old `claude-code-sandbox` general workspace on 2026-06-21 (fresh git history). This runs on a real laptop — not a container or VM. Files outside the project directory are real and permanent.

The repo separates two layers: the **product** (the dashboard itself) lives in flat dirs at the root; the **build workflow** (how this gets built with Claude Code in VS Code) lives under `dev/`.

## Folder map

**Product (the dashboard):**

| Folder | Purpose |
|--------|---------|
| `frontend/` | The desktop app — Electron + React (electron-vite); the **working MVP**, built in place. The UI today is largely one `src/renderer/App.tsx`. |
| `sidecar/` | FastAPI service the frontend talks to (`main.py`, port 7690) — the **working MVP** backend. Pluggable **driver seam** under `drivers/` (`base`/`sdk`/`bridge`) with shared `serialize.py`. The **`bridge` driver (real Claude Code TUI via tmux/WSL2) is the primary path the dashboard is built around** — **live-verified below the UI** (run-state, permission round-trips, resume, model/effort) **and now proven end-to-end *through the dashboard UI*** — creating an agent with no driver named comes up on `bridge`, spawns a real tmux session (no tab), and runs live turns that render in the feed (the verifying pass also caught & fixed an `EventRenderer` crash on the bridge's string-content user-prompt events). The `sdk` driver (in-process Claude Agent SDK) is a **limited-use engine** reserved for specific non-interactive tasks (e.g. programmatic flows that don't need a real TUI, such as the Revise / Summarize utility-LLM passes) — **not** the default. **`bridge` is the default when no driver is named**; select `sdk` explicitly with `AWL_DRIVER=sdk` or the per-session `driver` field (an explicitly-named *unknown* driver still falls back to `sdk`). |
| `bridge/` | The agent-control backbone — tmux/WSL2 control of Claude Code sessions. Importable package (`from bridge import TmuxBridge`). See **Custom Tooling**. |
| `design/` | UI mockups, palettes, and the **design reference** (`DESIGN.md`). `mockup.html` is the current visual authority; `tokens.css` is the single source of truth for every design value (colors, type, spacing, radius, shadow); `mockup-toolkit.js` is the `Ctrl+G` annotation overlay. |
| `archive/` | Retired-but-referenced material: the design lineage (old mockups, ui-plans). |
| `assets/` | Icon sets — `icons/agents/` (recolorable game-icons.net tiles) and `icons/ui/` (Lucide). |
| `tests/` | pytest suite — live bridge/sidecar integration (`test_tmux_bridge.py`, `test_bridge_finisher_live.py`) + hermetic unit tests (`test_bridge_unit.py`, `test_sidecar_unit.py`). See **Testing** below. |
| `docs/` | Committed, curated product reference docs. |

**Build workflow & config:**

| Folder | Purpose |
|--------|---------|
| `dev/` | Claude-CLI / VS Code build-workflow assets — **not the app**: `notes/` (working notes + `research/`), `prompts/` (dev-loop prompts), `tools/` (`bootstrap-env.ps1`, `claude-context-extractor/`). |
| `.claude/` | Claude Code config — `settings.json` (permissions, `plansDirectory: ./.claude/plans`), `agents/`, `plans/`, `cc-exports/`. |
| `.vscode/` | VS Code workspace (`awl-cc-dash.code-workspace`), `settings.json`, `tasks.json`, `claude-prompts.code-snippets`. |

**Root files:** `CLAUDE.md`, `DEVLOG.md`, `requirements.txt`, `pyproject.toml`, `.gitignore`, `start-dashboard.bat` (launches the sidecar + Electron together).

## Key files

Cross-cutting docs every session should know about — read the relevant one before diving in:

| File | What it is |
|------|------------|
| `DEVLOG.md` | Append-only project log (migration, backend, dashboard, tooling) — the **recent window**. **Read it before making changes**, and **log every repo change before you end the turn** — see the DEVLOG rule under [Behavioral rules](#behavioral-rules) and the file header for format. Older entries are rotated into `archive/devlog/` and summarized in the file's **Archived history** index; read those archives **on demand** only when a task needs older history, not by default. |
| `design/DESIGN.md` | Ground-truth **design reference** for the dashboard's UI/UX intent — purpose, the 3-pane layout, each panel, the interaction/communication model, and the design system. Read it before working on dashboard design or the frontend; the mockups in `design/` (authority: `mockup.html`, with values in `tokens.css`) own the exact visuals. |
| `dev/notes/repo-migration.md` | Loose, possibly-stale notes from the sandbox→awl-cc-dash migration (target layout, what moved where). Background only — trust the actual files over it. |

## Custom Tooling

### bridge (tmux agent control)

Python package at the repo root: `bridge/`.

Controls Claude Code TUI sessions running in tmux inside WSL2. Sessions run detached and are driven/read without any window (`capture-pane` + JSONL transcript); a Windows Terminal tab is opened only on an explicit attach via `show()`, never automatically on creation (see the bridge-sessions rule under **Behavioral rules**). Sessions persist even if a tab is closed — `show()` reconnects.

**Import:** `bridge` is a top-level package from the repo root:
```python
from bridge import TmuxBridge
```
If your code isn't run with the repo root on `sys.path`, add it first:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))   # repo root
from bridge import TmuxBridge
```

**CLI:** `python -m bridge <command>` (run from the repo root or with `PYTHONPATH=<repo-root>`).

**20 methods:** create, send, keys, read, read_log, list, show, close, shutdown, rename, resume, status, batch_create, broadcast, interrupt, scrollback, watch, wait_idle, export, mcp_sync. Plus config setters: set_cwd, set_model.

**Key capabilities:**
- Screen state detection (`status`) — idle, generating, permission_prompt, unknown
- JSONL transcript parsing (`read_log`) — structured access to conversation history
- MCP config sync (`mcp_sync`) — translates Windows MCP configs for WSL
- Pattern matching (`watch`) — poll until output matches a regex
- Idle blocking (`wait_idle`) — block until agent finishes responding
- Multi-agent (`batch_create`, `broadcast`, `interrupt`) — parallel session control

**Built-in but not yet fully utilized:**
- `extract_messages()` in `transcript.py` — converts JSONL entries to clean `[{role, content, timestamp}]` dicts. Available but not surfaced in the CLI or test suite.
- `export(mode="log")` — exports structured JSONL transcript to file. Implemented; only the sibling `scrollback` mode is tested (the `log` branch is untested).
- `close()` — kills a single session (vs `shutdown()` which kills all). Implemented, not covered in test suite.

**Test suite:** `tests/test_tmux_bridge.py` — pytest integration suite covering all operations.

### claude-context-extractor

Python script at `dev/tools/claude-context-extractor/` (a reusable dev utility, kept under `dev/`).

Pulls a full **claude.ai** (web/desktop) conversation via the internal API — tool calls, results, citations, artifacts, and full thinking — and saves raw `conversation.json` + a clean `transcript.md` + extracted `artifacts/` + a `summary.md`. Purpose: capture external Claude context to hand to another session. Stdlib-only core; run from its own folder.

- **Auth:** paste your claude.ai `sessionKey` into `session_key.txt` (gitignored, account-level — delete when done).
- **Commands:** `--list` · `--conversation <url|uuid>` · `--name "<title>"` (resolve by title) · `--summary <dir|json>` (offline (re)summary). Every export also auto-writes `summary.md` (turns, tools, timing, token estimate).
- **Tokens:** `--tokens {heuristic,tiktoken,api}` — `api` is exact via Anthropic's free `count_tokens` endpoint (needs `ANTHROPIC_API_KEY`); heuristic/tiktoken are offline estimates.
- **Gotchas:** `out/` + `session_key.txt` are gitignored; large `conversation.json` exports can exceed a connector's ~1MB tool-result cap — feed `transcript.md`/`summary.md` or chunked reads instead.

## Testing

**Use pytest for all tests.** This is the standard — reach for it when adding or changing testable behavior, rather than writing ad-hoc scripts. Tests live in `tests/` at the repo root — live bridge/sidecar integration suites (`test_tmux_bridge.py`, `test_bridge_finisher_live.py`) plus hermetic unit tests (`test_bridge_unit.py`, `test_sidecar_unit.py`). Each `tests/` dir owns a `log/` subdir (gitignored) for timestamped per-run debug logs.

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

**Conventions** (config in `pyproject.toml`, fuller notes in `tests/README.md`):
- Console output stays concise; full DEBUG detail (commands, payloads, raw screens, tracebacks) goes to the per-run file in `tests/log/`. Log with `logging.getLogger(__name__)` at DEBUG the inputs/outputs you'd want when a failure needs diagnosing.
- Tag non-hermetic tests `@pytest.mark.integration` and slow ones `@pytest.mark.slow`.
- Share expensive setup via session-scoped fixtures (see the `bridge` / `live_session` fixtures in `tests/conftest.py`) rather than relying on cross-test side effects.

## Behavioral rules

### Scope & safety
- Stay inside the project directory for all operations unless explicitly told otherwise.
- When touching global config (`~/.claude/`, etc.), explain the change before making it.

### Working style
- Be direct, practical, low-ceremony. Lead with action, follow with a brief explanation.
- Write all transient artifacts (screenshots, scratch HTML, debug dumps, ad-hoc server logs) into `.scratch/` — never the repo root or other project folders. Prefix any `filename` you pass to screenshot/export tools with `.scratch/`. One-off files may be deleted when done; accumulation in `.scratch/` is acceptable.

### Editing discipline
- **Preserve everything you weren't asked to change.** When you edit a file or produce a new version of an existing artifact (for example, a new UI mockup branched from the prior one), reproduce the untouched parts exactly as they were. Carrying them forward in full is real work, and that work is part of the task: don't skip, summarize, simplify, restyle, or drop sections just because faithfully reproducing them is tedious. The usual failure here is cutting corners, not over-editing, so when in doubt, keep the prior version intact. Before finishing, look back over the result and confirm nothing outside the requested change was lost or quietly altered.

### DEVLOG — project memory (not optional)
`DEVLOG.md` is the project's memory; an unlogged change is, to the next session, a change that never happened.
- **Log every repo change.** Before you end any turn in which you created, deleted, moved, or meaningfully edited a file (code, config, docs, or design) — and before you tell the user you're "done" — append a new entry at the **bottom** of the Log (it runs oldest → newest). Default to logging: the bar is "did the repo change?", not "was it significant?" — if you're unsure, it qualifies.
- **Format** (append-only; never edit or delete past entries — `DEVLOG.md` is 100% append-only, with no in-place-editable sections): a `### YYYY-MM-DD HH:MM:SS — short title` heading, 1–4 lines on what changed and the observable outcome, then a `Files:` line.
- **Rotate when long.** Past ~700 lines, move the oldest entries (top of the Log) **verbatim** — cut only at `### ` headings, never mid-entry — into the newest `archive/devlog/DEVLOG-archive-NN.md`, appending in order, until `DEVLOG.md` is back under ~300 lines; then refresh the digest + index row in the **Archived history** section at the bottom. Never edit archived entries.
- Full rules and the rotation procedure live in the `DEVLOG.md` header — follow those.

### Verifying UI changes
- **Drive the rendered UI — never hand back on static checks alone.** For anything that renders (the dashboard mockups above all), `node --check` / grep / reading the diff is necessary but NOT sufficient — it says nothing about layout, wrapping, overflow, or whether a control actually works. Layout, formatting, overflow, and dynamic behavior are part of the deliverable — not the user's job to catch.
- **Before you call a UI change done:** open it in a browser (serve over `http://localhost` — the Playwright MCP browser blocks `file:`), **resize the affected panel(s) to both narrow and wide extremes** (this layout is resizable, and that is where it breaks), and **click through every control you touched** — expand/collapse, toggles, each dropdown/menu, the whole flow. Screenshot each state, compare it to the stated intent, and fix what's off — all before reporting back.
- **Iterate headless; finish with one headed pass.** Run the Playwright MCP browser `--headless` for the whole resize/click/screenshot loop so it doesn't steal focus or windows while the user is working — the default for all UI verification. Then, once the change looks done, do a **single headed pass** to confirm the rendering is identical to what you saw headless. This headed parity check is a **hard rule, not a judgment call** — run it for every UI change, not only when you suspect a difference (soft "only if it might differ" wording just gets skipped). Keep it light: re-screenshot the touched states at the narrow and wide extremes and compare, not a full re-drive of every control. It interferes only briefly, once, at the very end — by design.

### Bridge sessions: a terminal opens only on explicit request, never as a side effect
The bridge drives Claude Code agents as **detached** tmux sessions in WSL2 and reads them via `capture-pane` (screen state) and the JSONL transcript (messages), so a session needs no window to run or be read. A Windows Terminal tab is only a way for a human to watch a session; an auto-popped tab steals the user's desktop focus and routes their keystrokes into the CLI mid-task.
- **Programmatic creation must never open a tab as a side effect.** Anything that creates sessions in code (the test suite, fixtures, batch spawns, the sidecar's bridge driver, scratch scripts) creates them tab-less. Don't reintroduce automatic tab-opening when adding any of these.
- **A tab opens only on a deliberate human request.** That request is the dashboard user choosing to attach in the product, the user asking to watch a session during dev, or a human running `python -m bridge create` by hand at a terminal (where invoking the command is itself the request, so the CLI may default to showing a tab). The mechanism is the opt-in path (currently `create(..., show=True)` / the `show()` method). This rule constrains *automatic* behavior only; it does not limit the product's deliberate manual-attach feature, which DESIGN.md calls out as a tmux advantage.