# CLAUDE.md

## Workspace identity

This is Adam's Claude Code sandbox — a general-purpose VS Code-based workspace for AI/agentic workflows, research, and personal knowledge management. Its current primary build focus is the **AWL multi-agent dashboard** (see **Key files**). This runs on a real laptop — not a container or VM. Files outside the project directory are real and permanent.

## Folder map

| Folder | Purpose |
|--------|---------|
| `agent-dashboard/` | Dashboard UI — design wireframes, Electron frontend, FastAPI sidecar |
| `archive/` | Completed or inactive items, kept for reference |
| `briefs/` | Session briefs — distilled intent documents from agents |
| `cc-exports/` | Exported Claude Code session transcripts |
| `claude-code-sandbox-env/` | Shared Python virtualenv for the workspace (used by the test runner and tooling) |
| `docs/` | Documentation, research, guides, and `temp/` subfolder for scratch work |
| `projects/` | Standalone projects with their own dev logs (fb-group-search, property-research) |
| `prompts/` | Reusable prompts and system instructions |
| `tools/` | Scripts and utilities (e.g. `cc_tmux_bridge/`) |
| `tests/` | Workspace-level test suites (pytest). See **Testing** below. |
| `.claude/` | Claude Code config — settings, permissions, agents, skills, plugins |
| `.vscode/` | VS Code workspace settings and tasks |

## Key files

Cross-cutting docs every session should know about — read the relevant one before diving in:

| File | What it is |
|------|------------|
| `DEVLOG.md` | Append-only project log for the whole workspace (bridges, backend, dashboard, tooling). **Read it before making changes**, and **log every repo change before you end the turn** — see the DEVLOG rule under [Behavioral rules](#behavioral-rules) and the file header for format. |
| `agent-dashboard/README.md` | Ground-truth **design reference** for the multi-agent dashboard's UI/UX intent — purpose, the 3-pane layout, each panel, the interaction/communication model, and the design system. Read it before working on dashboard design or the frontend; the wireframe mockups in `agent-dashboard/design/` own the exact visuals. |

## Custom Tooling

### cc_tmux_bridge

Python package at `tools/cc_tmux_bridge/` (workspace-local).

Controls Claude Code TUI sessions running in tmux inside WSL2. Every session automatically gets a visible Windows Terminal tab. Sessions persist even if WT is closed — `show()` reconnects.

**Import:** add the `tools/` directory to `sys.path`, then import. For example:
```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path("tools").resolve()))   # repo-root-relative
from cc_tmux_bridge import TmuxBridge
```

**CLI:** `python -m cc_tmux_bridge <command>` (run from the `tools/` directory or with `PYTHONPATH=tools`).

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
- `export(mode="log")` — exports structured JSONL transcript to file. Implemented and lightly tested.
- `close()` — kills a single session (vs `shutdown()` which kills all). Implemented, not covered in test suite.

**Test suite:** `tests/test_tmux_bridge.py` — pytest integration suite covering all operations.

### claude-context-extractor

Python script at `tools/claude-context-extractor/` (moved here from `projects/` on 2026-06-14 — it's
a reusable utility, not a standalone project).

Pulls a full **claude.ai** (web/desktop) conversation via the internal API — tool calls, results,
citations, artifacts, and full thinking — and saves raw `conversation.json` + a clean `transcript.md`
+ extracted `artifacts/` + a `summary.md`. Purpose: capture external Claude context to hand to another
session. Stdlib-only core; run from its own folder.

- **Auth:** paste your claude.ai `sessionKey` into `session_key.txt` (gitignored, account-level — delete when done).
- **Commands:** `--list` · `--conversation <url|uuid>` · `--name "<title>"` (resolve by title) ·
  `--summary <dir|json>` (offline (re)summary). Every export also auto-writes `summary.md`
  (turns, tools, timing, token estimate).
- **Tokens:** `--tokens {heuristic,tiktoken,api}` — `api` is exact via Anthropic's free
  `count_tokens` endpoint (needs `ANTHROPIC_API_KEY`); heuristic/tiktoken are offline estimates.
- **Gotchas:** `out/` + `session_key.txt` are gitignored; large `conversation.json` exports can
  exceed a connector's ~1MB tool-result cap — feed `transcript.md`/`summary.md` or chunked reads instead.
- History: absorbed an earlier sibling, `tools/claude-export/` — its inline `--session-key` and `--out` were folded in and that dir was removed (2026-06-14).

## Testing

**Use pytest for all tests.** This is the workspace standard — reach for it when adding or
changing testable behavior, rather than writing ad-hoc scripts.

**Where tests live:** a `tests/` directory at the relevant scope.
- Workspace-level tooling → `tests/` at the repo root.
- A project → `tests/` inside that project (e.g. `projects/fb-group-search/tests/`).

Each `tests/` dir owns a `log/` subdir (gitignored) for timestamped per-run debug logs.

**How to run:**
```powershell
tests\run.ps1                 # workspace suite via the shared venv
.\claude-code-sandbox-env\Scripts\python.exe -m pytest <path>   # any suite
```
No `testpaths` is configured (multi-project workspace) — pass the path you want to run.

**Conventions** (config in `pyproject.toml`, fuller notes in `tests/README.md`):
- Console output stays concise; full DEBUG detail (commands, payloads, raw screens,
  tracebacks) goes to the per-run file in `tests/log/`. Log with `logging.getLogger(__name__)`
  at DEBUG the inputs/outputs you'd want when a failure needs diagnosing.
- Tag non-hermetic tests `@pytest.mark.integration` and slow ones `@pytest.mark.slow`.
- Share expensive setup via session-scoped fixtures (see the `bridge` / `live_session`
  fixtures in `tests/conftest.py`) rather than relying on cross-test side effects.

## Behavioral rules

- Stay inside the project directory for all operations unless explicitly told otherwise.
- **Keep `DEVLOG.md` current — not optional.** It is the project's memory; an unlogged change is,
  to the next session, a change that never happened. **Trigger:** before you end any turn in which
  you created, deleted, moved, or meaningfully edited a file (code, config, docs, or design) — and
  before you tell the user you're "done" — append a new entry. **Default to logging:** the bar is
  "did the repo change?", not "was it significant?" — if you're unsure, it qualifies. **Format**
  (append-only; never edit or delete past entries): a `### YYYY-MM-DD HH:MM:SS — short title`
  heading, 1–4 lines on what changed and the observable outcome, then a `Files:` line. Full rules
  live in the DEVLOG header.
- When touching global config (`~/.claude/`, etc.), explain the change before making it.
- Be direct, practical, low-ceremony. Lead with action, follow with a brief explanation.
- Write all transient artifacts (screenshots, scratch HTML, debug dumps, ad-hoc server
  logs) into `.scratch/` — never the repo root or other project folders. When passing a
  `filename` to screenshot/export tools, prefix it with `.scratch/`. One-off files may be
  deleted when done; accumulation in `.scratch/` is acceptable.
- **Preserve everything you weren't asked to change.** When you edit a file or produce a
  new version of an existing artifact (for example, a new UI mockup branched from the
  prior one), reproduce the untouched parts exactly as they were. Carrying them forward in
  full is real work, and that work is part of the task: don't skip, summarize, simplify,
  restyle, or drop sections just because faithfully reproducing them is tedious. The usual
  failure here is cutting corners, not over-editing, so when in doubt, keep the prior
  version intact. Before finishing, look back over the result and confirm nothing outside
  the requested change was lost or quietly altered.
- **Verify UI changes by driving the rendered UI — never hand back on static checks alone.**
  For anything that renders (the dashboard mockups above all), `node --check` / grep / reading
  the diff is necessary but NOT sufficient — it says nothing about layout, wrapping, overflow, or
  whether a control actually works. **Before you call a UI change done:** open it in a browser
  (serve over `http://localhost` — the Playwright MCP browser blocks `file:`), **resize the
  affected panel(s) to both narrow and wide extremes** (this layout is resizable, and that is where
  it breaks), and **click through every control you touched** — expand/collapse, toggles, each
  dropdown/menu, the whole flow. Screenshot each state, compare it to the stated intent, and fix
  what's off, all before reporting back. Layout, formatting, overflow, and dynamic behavior are part
  of the deliverable — not the user's job to catch.
  - **Do the iteration headless; finish with one headed pass.** Run the Playwright MCP browser
  `--headless` for the whole resize/click/screenshot loop so it doesn't steal focus or windows
  while the user is working. This is the default for all UI verification. Then, once the change
  looks done, do a **single headed pass** to confirm the rendering is identical to what you saw
  headless before reporting back. This headed confirmation is a **hard rule, not a judgment call**
  — run it for every UI change, not only when you suspect a difference (soft "only if it might
  differ" wording just gets skipped). Keep it light: it's a parity check (re-screenshot the
  touched states at the narrow and wide extremes and compare), not a full re-drive of every
  control. It interferes only briefly, once, at the very end — by design.