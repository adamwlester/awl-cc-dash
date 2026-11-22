# Repo layout

What each folder and key file in awl-cc-dash holds (as of 2026-11-22). The repo was forked out of the old `claude-code-sandbox` workspace on 2026-06-21 with fresh git history. It separates two layers: the product (the AWL Multi-Agent Dashboard itself) lives in flat folders at the root, and the build workflow (how it gets built with Claude Code in Visual Studio Code (VS Code)) lives under `dev/`.

## Product

### `frontend/`

The desktop app: Electron + React, built with electron-vite. The renderer was rebuilt fresh from the `design/` mockups in the 2026-07-15/16 build run and is wired to the sidecar backends end to end (proven in the real window). The old renderer freeze is over: renderer work follows the normal rules, consuming `design/` as the visual authority and never redesigning it.

- `api.ts` is the preserved frontend-to-sidecar contract; extend it as endpoints land.
- The Electron main-process shell owns the sidecar lifecycle: it adopts a running sidecar or spawns one (checked on `/health`), and implements the close semantics of [ARCHITECTURE](ARCHITECTURE.md) §3.4 through the styled inter-process communication (IPC) dialog (proven).
- Renderer map: [ARCHITECTURE](ARCHITECTURE.md) §4 and §4.4.

### `sidecar/`

The FastAPI backend the frontend talks to, on port 7690: the working minimum viable product (MVP) service. It owns a pluggable driver seam for talking to agents, plus the feature modules behind the dashboard (event bus, hooks, inbox, scratchpad, library, console and more).

- `bridge` (the real Claude Code text user interface (TUI) through tmux in Windows Subsystem for Linux 2 (WSL2)) is the primary path and the default when no driver is named.
- `sdk` (the in-process Claude Agent software development kit (SDK)) is a limited-use opt-in.
- Full module and endpoint map, and driver details: [ARCHITECTURE](ARCHITECTURE.md) §5 and §6.

### `bridge/`

The agent-control backbone: an importable Python package (`from bridge import TmuxBridge`, adding the repo root to `sys.path` first if needed) and a command-line interface (`python -m bridge <command>`). It drives Claude Code sessions as detached tmux sessions inside WSL2 and reads them without any window: `capture-pane` for live screen state and the JSON Lines (JSONL) transcript for messages. Sessions persist even if a watching tab is closed. Agents authenticate against the operator's Claude subscription through a long-lived token injected per spawn, not interactive per-install login and not a global environment variable. Method reference, internals and the authentication model: [ARCHITECTURE](ARCHITECTURE.md) §6.4. The rule on when a terminal tab may open is in [working-rules.md](working-rules.md).

### `design/`

User interface (UI) mockups, palettes and the design reference. The design system is five files, governed by [design-changes.md](design-changes.md):

- `mockup.html`: the current visual authority and the component inventory. Every component carries its canonical `data-comp` name on its root element, and hidden appearance states are declared there with `data-variants` (required on touch; the 2026-07-05 conversion sweep backfilled every earlier component).
- `tokens.css`: the single source of truth for every design value (colours, type, spacing, radius, shadow).
- `styles.css`: the shared component Cascading Style Sheets (CSS).
- `behavior.js`: the shared component behavior (interaction logic).
- `DESIGN.md`: the rules and intent.

Dev-only view tooling rides alongside, outside the design system: `mockup-toolkit.js` (the `Ctrl+G` annotation overlay), `label-overlay.js` (the `Ctrl+L` component-label overlay) and `states.html` (the auto-generated component-states page, which renders every declared `data-variants` state from the live tags at load). The retired interactive catalog (`gallery.html`) is frozen at `archive/design/design-v12p7-gallery-retirement/`.

### `assets/`

Shipped product assets:

- `icons/agents/`: recolourable game-icons.net tiles.
- `icons/ui/`: Lucide icons.
- `names/`: the curated agent-name pool.
- `prompts/`: the shipped prompt-library defaults (`responses.md`, `snippets.md`, `actions.md`), the in-repo scope of the scope-aware canned-text library ([ARCHITECTURE](ARCHITECTURE.md) §11 #45).
- `agents/`: product-shipped agent definitions (`changelog-watcher.md`, `system-check.md`), the easy-run halves of [ARCHITECTURE](ARCHITECTURE.md) §11 #48 and #49.

### `tests/`

The pytest suite: a hermetic per-module unit tier, plus live integration, feasibility-spike and browser-driven UI tiers that exercise the real bridge and sidecar. Each `tests/` folder owns a gitignored `log/` subfolder for timestamped per-run debug logs. Layout, tiers, markers and conventions: [tests/README.md](../tests/README.md).

### `docs/`

Committed, curated product reference docs, including [ARCHITECTURE.md](ARCHITECTURE.md) and these agent docs.

### `.awl-cc-dash/`

The dashboard's own project store for this repo (self-dogfooding, [ARCHITECTURE](ARCHITECTURE.md) §8.2). All committed except `assets/`, which is gitignored runtime media.

- `agents/`: the project-scope `agent.md` role presets the Create Role dropdown loads (builder, reviewer, researcher, scribe, ui-checker; seeded 2026-07-17). Content, editable like any product asset.
- `docs/`, `plans/`: the demo docs and plan with provenance sidecars. Content, editable like any product asset.
- `state/`: runtime data, not product source, including the live demo roster. Committed deliberately (project state travels with the repo), never as a side effect of unrelated commits, and never hand-edited by dev agents.

The demo-store baseline (seeded role presets, demo docs and plan, live demo roster) is the operator-sanctioned workable demo from the 2026-07-17 sprint. Tests never touch the store: they run on `AWL_SIDECAR_RUNTIME` plus per-test temporary working folders.

### `archive/`

Retired but referenced material: the design lineage (old mockups and UI plans under `design/`), rotated DEVLOG archives (`devlog/`), retired notes and docs (`notes/`, `dev/notes/`, `docs/`) and retired test artifacts (`tests/`).

## Build workflow and config

- `dev/`: Claude Code and VS Code build-workflow assets, not the app. `notes/` holds working notes and `research/`; `prompts/` holds dev-loop prompts; `tools/` holds `bootstrap-env.ps1`, `ui-verify/` (see [ui-verification.md](ui-verification.md)), `variant-lint/` (see [design-changes.md](design-changes.md)) and `claude-context-extractor/`.
- `dev/tools/claude-context-extractor/`: exporters for claude.ai, Claude desktop and Codex sessions. Retired as an agent tool on 2026-11-06 (agents look up sessions with agent-commons' `tool-transcripts`), but kept because the product's Import external context feature (`sidecar/import_context.py`, [ARCHITECTURE](ARCHITECTURE.md) §11 #28) shells out to it.
- `transcripts/`: gitignored personal session exports left from the retired export workflow; not part of the product or the agents' workflow (as of 2026-11-22).
- `.claude/`: Claude Code config: `settings.json` (permissions; `plansDirectory: ./.claude/plans`), `agents/`, `plans/`.
- `.vscode/`: the VS Code workspace (`awl-cc-dash.code-workspace`), `settings.json`, `tasks.json`, `claude-prompts.code-snippets`.

## Root files

- `AGENTS.md`: the agents' instructions index.
- `DEVLOG.md`: the project log (below).
- `requirements.txt`, `pyproject.toml`, `.gitignore`.
- `start-dashboard.bat`: launches the sidecar and Electron together.

## Key files

- [docs/ARCHITECTURE.md](ARCHITECTURE.md): the final-vision system reference. It describes the intended final system as settled architecture: the processes (Electron, the FastAPI sidecar on port 7690, the driver seam, the tmux/WSL2 bridge), the one-project product model, the coordination spine and the storage model, with every product decision woven into the prose and "Today" markers wherever code has not caught up. The doc leads the build: builds converge on it and clear markers, and its text changes only when a decision changes. The build backlog is its §11. It is the system counterpart to `DESIGN.md` (UI intent) and `DEVLOG.md` (history).
- [DEVLOG.md](../DEVLOG.md): the append-only project log covering the whole workspace, holding the recent window. Read it before making changes. Older entries are rotated into `archive/devlog/` and summarized in its "Archived history" index; read those archives only when a task needs older history. The logging format and rotation procedure are in its header.
- [design/DESIGN.md](../design/DESIGN.md): the ground-truth design reference for the dashboard's UI and user experience intent. Read it before any dashboard-design or frontend work. The mockups in `design/` (authority `mockup.html`, values in `tokens.css`) own the exact visuals.
