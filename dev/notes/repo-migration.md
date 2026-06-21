# Port the AWL dashboard into its own repo (`awl-cc-dash`)

> ⚠️ **SUPER TENTATIVE — REFERENCE ONLY.** This is a snapshot of early migration *thinking*, not a
> spec or source of truth. It is loose, partial, and likely already stale: decisions changed during the
> actual move (e.g. `archive/` was kept, with an `archive/_ignored/` bucket for untracked transcripts).
> **Trust the live repo, `.gitignore`, and `DEVLOG.md` over anything written here** wherever they
> disagree. Use this only to recall the original intent/rationale — do not execute it step-by-step.

## Context

The multi-agent dashboard has outgrown the general-purpose `claude-code-sandbox` repo.
Its design ([`agent-dashboard/README.md`](agent-dashboard/README.md)) describes a product-scale
app (3-pane layout, agent linking, shared scratchpad, approvals Inbox, plan-review docs, settings,
rewind/handoff), it's the stated primary focus, and the sandbox's 144 MB of personal/unrelated
history (transcripts, notes, property research) is the wrong home for it.

The code is still small — one ~530-line [`frontend/src/renderer/App.tsx`](agent-dashboard/frontend/src/renderer/App.tsx)
and a ~419-line [`sidecar/main.py`](agent-dashboard/sidecar/main.py) — so moving now is cheap, and
it's better to move **before** the structural overhaul than to restructure twice.

Key facts driving the plan:
- The tmux control layer is **already built and working**: [`tools/cc_tmux_bridge/`](tools/cc_tmux_bridge/)
  (20 methods, pytest suite). It must come along — the design calls it "the backbone."
- The sidecar currently **bypasses** the bridge and drives `claude_agent_sdk.ClaudeSDKClient`
  directly. Wiring it onto the bridge is a **follow-up phase**, not part of the port.
- The empty remote `awl-cc-dash` already exists (no README/.gitignore/license).
- **Hard constraint:** the new repo must be a self-contained **Claude Code workspace** so Adam can
  keep building it with Claude Code in VS Code. User-level `~/.claude` config carries over for free;
  only project-scoped pieces must be recreated.

**Approach:** clean new local dir → curated copy of the subset → fresh git history → push.
Keep the port faithful (lift, don't restructure); do the monorepo restructure as a separate phase
inside the new repo.

## Phase 1 — Create the clean local repo (faithful port)

Create the new dir **outside** the sandbox, e.g. `C:\Users\lester\MeDocuments\AppData\Anthropic\awl-cc-dash\`.

**Target layout — flat, minimal nesting (no overbuild).** Two conceptual layers: the **product**
(the dashboard) at root, and a single **`dev/`** dir for the Claude-CLI / VS Code *build-workflow*
assets — kept apart from dashboard operations.

```
awl-cc-dash/                        # ── the repo (committed) ──
│
├── frontend/                       # Electron + React desktop app  [PRODUCT]
│   ├── src/
│   │   ├── main/index.ts           # Electron main process (window, lifecycle)
│   │   ├── preload/index.ts        # exposes the sidecar URL to the renderer
│   │   └── renderer/
│   │       ├── App.tsx             # the entire UI today (~530 lines)
│   │       ├── main.tsx            # React mount
│   │       └── index.html
│   ├── electron.vite.config.ts
│   ├── tsconfig.json
│   ├── package.json
│   └── node_modules/               # (gitignored — restore with `npm install`)
│
├── sidecar/                        # FastAPI service the desktop talks to  [PRODUCT]
│   └── main.py                     # Agent API on :7690 (Session→Agent rename + driver seam later)
│
├── bridge/                         # tmux/WSL2 control of Claude Code sessions  [PRODUCT]
│   ├── __init__.py
│   ├── __main__.py
│   ├── bridge.py                   # TmuxBridge — create/send/read/status/…
│   ├── cli.py
│   ├── mcp.py                      # MCP config sync for WSL
│   ├── paths.py
│   ├── transcript.py               # JSONL transcript parsing
│   └── README.md
│
├── design/                         # UI mockups & palette work (visual source of truth)  [PRODUCT]
│   ├── ui-concept-v9p14.html       # current authority mockup
│   ├── palette-options/
│   └── ui-snipets/
│
├── archive/                        # retired-but-referenced material — the design lineage
│   ├── ui-concept-v1…v9p10.html    # prior mockup versions (DESIGN.md links back here)
│   ├── ui-plan-v1.md  ui-plan-v2.md
│   └── migration-execution-log.md  v7p1-crash-legacy/
│
├── tests/                          # pytest suite — the whole dir, as-is  [PRODUCT]
│   ├── test_tmux_bridge.py
│   ├── conftest.py
│   ├── run.ps1
│   ├── claude-desktop/
│   ├── README.md
│   └── log/                        # (gitignored — per-run debug logs)
│
├── docs/                           # static, committed reference  [PRODUCT]
│   └── DESIGN.md                   # the big design reference (was agent-dashboard/README.md)
│
├── dev/                            # Claude-CLI / VS Code BUILD workflow — NOT the app
│   ├── notes/                      # your working notes (committed; flat, subfolder when crowded)
│   ├── prompts/                    # your dev-loop prompts
│   ├── bootstrap-env.ps1           # creates the sidecar venv + installs the SDK
│   └── context-extractor/          # (maybe) claude.ai transcript capture — code only
│
├── .claude/                        # ── workspace config (MUST live at repo root) ──
│   ├── settings.json               # permissions allowlist + "plansDirectory": "./.claude/plans"
│   ├── agents/                     # e.g. vibe-guide.md (optional)
│   └── plans/                      # the dashboard's OWN build-plans (this file's future home)
│
├── .vscode/
│   ├── awl-cc-dash.code-workspace
│   ├── settings.json
│   └── tasks.json                  # task: run start-dashboard.bat
│
├── CLAUDE.md                       # project memory + the UI-verification rule
├── DEVLOG.md                       # append-only project log
├── README.md                       # short: what it is + how to run it
├── requirements.txt                # sidecar + bridge Python deps
├── pyproject.toml                  # pytest config + markers
├── .gitignore
└── start-dashboard.bat             # launches the sidecar + Electron together
```

> **Runtime data lives OUTSIDE this tree** — the dashboard's own state (projects, agents, events,
> scratchpad, links, setups) is written to a data root in `%APPDATA%\awl-cc-dash`, never committed.
> See [Runtime data, documents & vocabulary](#runtime-data-documents--vocabulary-design-note--informs-the-sidecar-phase)
> for that layout.

Rule for the CLI-vs-dashboard split: **movable dev assets → `dev/`; config that Claude Code / VS Code
require at root (`.claude/`, `CLAUDE.md`, `.vscode/`) stays at root.** Product dirs stay flat;
internal structure (sidecar `drivers/` seam, frontend `features/`) is added *inside* them only when
the code needs it — not scaffolded empty up front.

**Docs vs notes vs scratch (convention):** `docs/` = committed, curated **product reference**
(DESIGN.md etc., contributor audience); `dev/notes/` = your committed **working notes** (process,
decisions, todos — messy-OK, for you/your agents); `.scratch/` = gitignored **throwaway**. Don't mix
notes into `docs/` (the sandbox's `docs/human-notes-misc.md` is the anti-pattern this fixes).

**Copy IN — core (the dashboard + what it depends on):**
| From (sandbox) | To (new repo) | Why |
|----------------|---------------|-----|
| `agent-dashboard/frontend/` (src, config — **not** `node_modules/`, **not** `out/`) | `frontend/` | the desktop app |
| `agent-dashboard/sidecar/main.py` (**not** `__pycache__/`) | `sidecar/main.py` | the API service |
| `agent-dashboard/design/` | `design/` | mockups / palette work |
| `agent-dashboard/README.md` | `README.md` | the design reference |
| `agent-dashboard/start-dashboard.bat` | `start-dashboard.bat` | launcher (path-update) |
| `tools/cc_tmux_bridge/` (**not** `__pycache__/`) | `bridge/` | **the backbone** — agent control |
| `tools/bootstrap-env.ps1` | `dev/bootstrap-env.ps1` | venv setup for the sidecar (Claude Agent SDK) — saves re-setup |
| **whole `tests/` dir** (test_tmux_bridge.py, conftest.py, run.ps1, README.md, claude-desktop/ — **not** `log/`, `__pycache__/`) | `tests/` | the bridge pytest harness (incl. markers) |
| root `pyproject.toml` (pytest config/markers) + `requirements.txt` | root | test config + Python deps |
| `prompts/` | `dev/prompts/` | your Claude-CLI / VS Code **build** prompts (dev-loop inputs, not app content) |
| `archive/agent-dashboard/` (design lineage — old mockups, ui-plans, migration log) | `archive/` | superseded design the DESIGN.md references; **drop** the `agent-dashboard/` nesting |

**Copy IN — maybe (adjacent, decide at copy time):**
| `tools/claude-context-extractor/` **code only** (`extract.py`, `README.md`) | `dev/context-extractor/` | transcript/context capture — relates to the README's open "Transcript payload" question. **Never** its `out/` or `session_key.txt`. |

**Explicitly DO NOT copy:** the old `.git/`, `node_modules/`, `out/` (frontend build **and** extractor output), `__pycache__/`,
`claude-code-sandbox-env/` (venv), `cc-exports/`, `briefs/`, `projects/`, the **rest of** `archive/`
(everything except `archive/agent-dashboard/` — i.e. its `cc-exports/`, `sdk-spikes/`, `system-audits/`,
`tool-tests/`, etc.), **`tools/claude-context-extractor/session_key.txt`** (secret) + its `out/`, and the root `*.png` scratch shots.

After de-nesting, fix the one inbound link in `docs/DESIGN.md`:
`../archive/agent-dashboard/ui-plan-v2.md` → `../archive/ui-plan-v2.md`.

**Bridge rename `cc_tmux_bridge` → `bridge` (verified minor — the package uses relative imports
throughout, has no internal self-reference, and `paths.py` targets Claude Code's dirs, not its own
location, so the folder rename needs zero edits to the package body).** Only the callers change:
- `tests/conftest.py` — `from cc_tmux_bridge import TmuxBridge` → `from bridge import TmuxBridge`,
  and repoint its `sys.path` insert from `tools/` to the **repo root**.
- `tests/test_tmux_bridge.py` — `from cc_tmux_bridge.bridge import TmuxBridgeError` → `from bridge.bridge import …`.
- Any `python -m cc_tmux_bridge` → `python -m bridge` (auto-works after rename; update scripts/README).
- Cosmetic: logger name `"cc_tmux_bridge"`→`"bridge"`; optionally export `TmuxBridgeError` from
  `bridge/__init__.py` so callers can `from bridge import TmuxBridge, TmuxBridgeError`.
- *(Sidecar-phase, not now):* add a minimal `pyproject.toml` for the bridge + `pip install -e .` so
  `import bridge` resolves from the sidecar (whose cwd is `sidecar/`).

## Phase 2 — Make it a Claude Code workspace

Recreate the project-scoped config (user-level `~/.claude` skills/plugins/MCP/GSD/hooks already follow you in):

- **`.gitignore`** (write this FIRST, before `git add`): `node_modules/`, `out/`, `dist/`,
  `__pycache__/`, `*.pyc`, `.venv/`, `*.png` scratch, `.scratch/`, `session_key.txt`, `.env`.
- **`.claude/settings.json`** — adapt from [`.claude/settings.json`](.claude/settings.json) with a
  permissions allowlist for the real dev loop: `npm`/`electron-vite`, `python`/`uvicorn`, `pytest`,
  and the **`wsl`/`tmux`** commands the bridge driver runs (so the agent doesn't stall on approvals
  when it tests the bridge path); keep `enableAllProjectMcpServers: true` for Playwright/Excalidraw.
- **`CLAUDE.md`** — new project memory: folder map, key files, and — load-bearing for this UI-heavy
  app — the **UI-verification rule** transplanted from the sandbox CLAUDE.md (serve over
  `http://localhost`, Playwright **headless** resize/click-through loop, then a **headed** parity pass).
- **`DEVLOG.md`** — fresh, with a first entry recording the port.
- **`.vscode/`** — a `.code-workspace` + a `tasks.json` task that runs `start-dashboard.bat`.
- Optional: bring [`.claude/agents/vibe-guide.md`](.claude/agents/vibe-guide.md).

## Phase 3 — Initialize, commit, push

```bash
cd <new repo dir>
git init -b main
git add -A                      # .gitignore already in place
git commit -m "Initial import: AWL dashboard ported from claude-code-sandbox"
git remote add origin https://github.com/adamwlester/awl-cc-dash.git
git push -u origin main
```

## Phase 4 — Rehydrate & verify it runs (end-to-end)

1. `cd frontend && npm install`
2. Sidecar deps into a fresh venv: `fastapi`, `uvicorn`, `sse-starlette`, `pydantic`,
   `claude-agent-sdk` (capture into a `requirements.txt`).
3. Run `start-dashboard.bat` → confirm the Electron window opens and the title bar shows
   **Connected** (sidecar healthy on `:7690`).
4. Create a session, send a prompt, confirm the event feed renders a result.
5. **UI check (per the transplanted rule):** open the renderer over `http://localhost` in the
   Playwright MCP browser headless, resize the panes to narrow/wide extremes, click the controls,
   screenshot; then one headed parity pass.
6. `pytest tests/` for the bridge suite.

## Runtime data, documents & vocabulary (design note — informs the sidecar phase)

**Vocabulary (decided) — three tiers, don't conflate:**
- **Project** — the reusable, named, persisted unit: a set of agents + their links + shared
  scratchpad + setup. What Save/Load acts on and what gets reused. (Supersedes the loose "session"
  we'd used for the top-level dir.)
- **Agent** — a participant in a project (the README's term). NB: the sidecar's **current `Session`
  entity / `/sessions` API actually models an agent** (model, mode, cost, status) — rename
  `Session` → `Agent` in the refactor; that removes the confusion this fixes.
- **session** (lowercase, kept) — only the underlying **Claude Code conversation** an agent runs in:
  the `session_id` that resumes and that Rewind/Handoff act on. Literally a session in Claude Code's
  API — do **not** rename it to project.

**Two kinds of documents:**
- *Read-in-place* (app doesn't own them): the Documentation panel's Plan/Todo/Readme/Claude read the
  agents' real files — plans from each agent's `~/.claude/plans/*.md`, README/CLAUDE.md/todo from the
  project the agents work in. Read/written at their real paths; NOT stored in this repo or the data
  root. (Distinct from the dashboard's own build-plans under `./.claude/plans`.)
- *Owned state* (app generates it): lives in a **data root OUTSIDE the repo**, default the Electron
  `app.getPath('userData')` dir (`%APPDATA%\awl-cc-dash`), path configurable. Fixes the current
  in-memory-only event history (no persistence/crash-recovery today).

**Data-root layout** (single implicit project to start; the `projects/<name>/` wrapper is already
forward-compatible for multi-project later):
```
<dataRoot>/projects/<project>/
├── agents/<agent-id>/
│   ├── meta.json        # identity, model, mode, status, cost, turns, + Claude session_id
│   ├── events.jsonl     # append-only feed (replaces the in-memory list)
│   └── transcript.jsonl # optional raw transcript
├── scratchpad.md
├── links.json
└── setup.json           # the saved agents + links
```

## Follow-up (NOT this port — separate phases in the new repo)

- **Monorepo restructure** to `apps/desktop` · `services/sidecar` · `packages/bridge` (overhaul to
  support the assumed UI features). Done once, in the clean repo.
- **Sidecar → bridge driver swap**: replace `ClaudeSDKClient` with `cc_tmux_bridge` behind the same
  `/sessions` HTTP API (gets crash recovery, visible WT tabs, `/fast`+thinking, subagents, transcript
  payloads for linking). Decide SDK-direct vs bridge vs hybrid here.
- **Bridge ownership (a/b):** decide whether the dashboard repo becomes the canonical home for
  `cc_tmux_bridge` or it stays mirrored in the sandbox. Deferred — copying it in didn't force this.

## Open items

- Final repo name confirmed: `awl-cc-dash`.
- **`dev/` dir name** — confirm `dev/` vs an alt (`workbench/`, `.dev/`).
- **`context-extractor`** — bring the code into `dev/` now, or leave it in the sandbox for later.
- **README handling** — move the big design reference to `docs/DESIGN.md` and write a short real
  root `README.md` (recommended), or keep it as the root `README.md` for now.
- Whether to also wire a multi-root `.code-workspace` so the sandbox stays visible alongside.
