Read `C:\Users\lester\MeDocuments\AI\AGENTS.md` first: shared instructions for every repo in that folder (Claude Code loads it automatically; Codex must read it). The rest of this file is this repo's own instructions.

# awl-cc-dash

The workspace for the AWL Multi-Agent Dashboard: a single-window Electron desktop app for running, monitoring and coordinating many Claude Code agents at once. The product lives in flat folders at the root; how it gets built with Claude Code lives under `dev/`.

## Docs index

| Before you                                  | Read                                              |
| ------------------------------------------- | ------------------------------------------------- |
| Change anything                             | `DEVLOG.md` (recent window; rules in its header)  |
| Find where something lives                  | `docs/repo-layout.md`                             |
| Work on the sidecar, bridge, drivers, store | `docs/ARCHITECTURE.md`                            |
| Do design or frontend work                  | `design/DESIGN.md`, `docs/design-changes.md`      |
| Call a user interface (UI) change done      | `docs/ui-verification.md`                         |
| Add or run tests                            | `tests/README.md`                                 |
| Reply, edit files or hand off               | `docs/working-rules.md`                           |

## Rules for this repo

- **Log every repo change** in `DEVLOG.md` before ending the turn and before saying "done": a new entry at the bottom, never editing past entries. Format and rotation are in its header.
- **The architecture doc leads the build.** Builds converge on `docs/ARCHITECTURE.md` and clear its "Today" markers; its text changes only when a decision changes. The build backlog is its §11.
- **Design is one system in five files** (`tokens.css`, `styles.css`, `behavior.js`, `mockup.html`, `DESIGN.md` in `design/`): reuse before adding, never hardcode a value that belongs in `tokens.css`, and propagate each change to every file it touches (`docs/design-changes.md`).
- **The frontend consumes `design/` as its visual authority**; never redesign it in the renderer.
- **Verify anything that renders** in one headed pass with the parked `ui-verify` browser (`dev/tools/ui-verify/`): resize the affected panels to narrow and wide extremes, click every control you touched, and screenshot each state. Static checks alone are not enough (`docs/ui-verification.md`).
- **Bridge sessions are created tab-less.** A terminal tab opens only on a deliberate human request (`create(..., show=True)` or `show()`), never as a side effect of tests, fixtures, batch spawns, the sidecar driver or scripts (`docs/working-rules.md`).
- **Use pytest for all tests**, not ad-hoc scripts. The `test_*_unit.py` docstrings state each module's decided contract: read the matching one before building or changing a module.
- **`.awl-cc-dash/state/` is runtime data:** commit it deliberately, never as a side effect of unrelated commits, and never hand-edit it. Tests never touch the store.
- **Carry untouched parts of an edited file forward exactly**, and finish a refactor everywhere it reaches (`docs/working-rules.md`).
- **Scripts here read keys from environment variables;** run them through agent-vault (its README is in `C:/Users/lester/MeDocuments/AI/agent-commons/tools/agent-vault/`).
- **Lead with a plain overview on backend topics**, cite code as clickable line-anchored links, and end a run with a one-line git check-in: what merged back to `main` and any branch worth keeping (`docs/working-rules.md`).
- **Codex** does not change `.claude/` unless asked.

## Layout

- `frontend/`: the Electron + React desktop app; `api.ts` is the frontend-to-sidecar contract.
- `sidecar/`: the FastAPI backend on port 7690, with the driver seam (`bridge` by default, `sdk` opt-in).
- `bridge/`: tmux control of Claude Code sessions in Windows Subsystem for Linux 2 (WSL2); `from bridge import TmuxBridge` or `python -m bridge`.
- `design/`: mockups and the five-file design system.
- `assets/`: shipped icons, agent-name pool, prompt-library defaults and agent definitions.
- `tests/`: the pytest suite (unit, live integration, spike and browser tiers).
- `docs/`: product reference and these agent docs.
- `.awl-cc-dash/`: the dashboard's own committed project store for this repo.
- `dev/`: build-workflow notes, prompts and tools; not the app.
- `archive/`: retired but referenced material.
- `start-dashboard.bat`: launches the sidecar and Electron together.

## Checks

Uses the repo-root `.venv` (creation command in `tests/README.md`). No `testpaths` is set, so pass the path. Plain `tests\run.ps1` also runs the live tier against real agents.

```
tests\run.ps1 -m "not integration and not slow"
node dev/tools/variant-lint/variant-lint.mjs
```
