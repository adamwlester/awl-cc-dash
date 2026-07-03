# META-PROMPT — Generate the §10 test-build prompts

**Role:** You are a *prompt-writer, not a test-builder.** Your single deliverable is a *family* of
self-contained build prompts — one per test — that will each be handed to a **separate** Claude Code build
agent (running in-repo). You write the prompts and stop. **Do not build, run, or scaffold any test yourself.**

You have full repo access. The downstream build agents also run in-repo, so their prompts may say "read file
X" freely.

---

## 1. Read these first (ground every prompt in reality)

- `docs/ARCHITECTURE.md` **§10** (Open questions & research queue) — the source list. Every item has a status
  tag, an **Evidence** line, **Desired final behavior**, **Current blocker**, **Research/POC must establish**,
  and **Fallback**. Each child prompt is built from its item's four bullets.
- `dev/notes/research/claude-code-mode-control-research.md` — the **mechanism** research. This is where the
  concrete "how to test it" levers live (Shift+Tab/`BTab` cycling, `Meta+T`/`Meta+O` keybindings,
  `capture-pane -e`, PreToolUse hooks, PID→session mapping, statusline context). Pull the specific lever for
  each item from here.
- `tests/test_bridge_finisher_live.py` — **THE pattern to copy.** How a live test builds a driver, drives the
  bridge, and asserts. Every new backend test mirrors this shape.
- `tests/test_tmux_bridge.py`, `tests/conftest.py` — the fixtures (`bridge`, `live_session`), the
  `integration`/`slow` markers, session handling.
- `tests/README.md` — two-tier model (hermetic default vs live opt-in), run commands, conventions.
- `bridge/bridge.py` — the bridge API (`create`/`send`/`keys`/`read`/`read_log`/`status`/`wait_idle`/`watch`/…).
  `sidecar/drivers/bridge.py` — the driver, `CAPABILITIES`, and the `set_mode`/`set_thinking`/`set_fast`
  **no-ops** these spikes are meant to challenge.
- `CLAUDE.md` — the behavioral rules every child prompt must inherit (git/branch, tab-less bridge sessions,
  DEVLOG, pytest, `.scratch`, verifying UI changes).

---

## 2. The prompts to produce

Emit **one child prompt per item below.** Core set = the **9 🧪 needs-spike items** + the **UI slice**
(10 prompts):

| # | §10 item | Known lever (confirm in the research) | Read-back / observable to verify it took |
|---|----------|----------------------------------------|------------------------------------------|
| 1 | #1 Mid-run permission-mode change | Shift+Tab / `BTab` sent via `keys()`; pre-arm bypass with `--allow-dangerously-skip-permissions` | the mode text in the status line (e.g. `⏵⏵ accept edits on`) |
| 2 | #2 Thinking-mode toggle | `Meta+T` (`chat:thinkingToggle`) via `keys()` | `thinking` blocks appearing/disappearing in the transcript |
| 3 | #3 Fast-mode toggle | `Meta+O` (`chat:fastMode`) via `keys()` | the Fast-mode state indicator |
| 4 | #5 Console rendering fidelity | `capture-pane -e` (ANSI-preserving) | **split:** first prove live-mirror + keystroke passthrough *wiring*, then ANSI *fidelity* |
| 5 | #6 Plan/Decision hook interception | PreToolUse hooks for `ExitPlanMode`/`AskUserQuestion` | **split:** *detection* (surface a card) vs *answer/resume* loop |
| 6 | #8 Subagent pending-vs-active | subagent-transcript recency (file mtime / last-event) or hook context | a reliable active-vs-pending signal |
| 7 | #9 Context breakdown & Compact | `/context` scrape + `compact_boundary` transcript metadata | per-category rows; compaction events |
| 8 | #10 One-click launch | Electron main spawns/supervises/shuts-down the sidecar | clean spawn + teardown that preserves detach-on-close; test **with** project close/reopen |
| 9 | #11 Per-agent cost | JSONL `usage` fields / `/cost` scrape | a non-fabricated per-session number, or an honest "none available" |
| 10 | **UI slice** (frontend) | Playwright-python driving the **already-tested sidecar API** | render live feed · send a prompt · permission approve/deny · run-state — **NOT** button polish |

Then, in a clearly separated **"Optional — close the open tail (low priority)"** section, emit one
lightweight spike prompt each for the two ◐ partially-proven items — spiking **only their open tail**, never
retesting the proven part:
- **#4 True mid-run Inject** — spike only *"is there any earlier-than-hook-boundary injection point?"*
  (hook-boundary Inject is already unit-proven — do not retest it).
- **#7 Real run-strip completion %** — spike only *"is there any engine progress signal beyond the
  self-reported checklist?"* (the checklist floor is already unit-proven).

**Do NOT** write prompts for #12 or #13 (🔬 needs-research) — those go to the research generator.

---

## 3. What every child BUILD prompt MUST contain

Each child prompt is handed to a fresh agent with no memory of this thread, so it must be fully self-contained:

1. **Header** — the test's working name, its §10 item (`#N — name — 🧪 needs-spike`), and a one-line goal.
2. **Read first** — the exact files that agent should open (its §10 item, the relevant section of the
   mode-control research, `tests/test_bridge_finisher_live.py` as the pattern, and the specific
   bridge/sidecar module it touches).
3. **Mechanism / hypothesis** — the known lever (from the table above, confirmed against the research) and
   what we expect to happen.
4. **Build this** — a new `tests/<slug>_live.py` marked `@pytest.mark.integration` + `@pytest.mark.slow`,
   mirroring the finisher pattern, that: **(a)** spawns a tab-less, **uniquely-named** bridge session,
   **(b)** drives the behavior via the bridge, **(c)** *reads the resulting state back* to verify (name the
   exact observable — see the table's read-back column), **(d)** asserts on it.
5. **The read-back is the crux** — state plainly: *sending the keystroke is trivial; proving it took effect
   is the whole test.* If the result isn't observable, that's a finding, not a pass.
6. **Two honest exits (spike-or-omit)** — **works** → keep it as a durable live test + a short note of what
   was learned; **genuinely impossible after a real attempt** → **do NOT fabricate a green.** Write up the
   findings and propose moving the §10 item to *Decided omissions*. "Impossible" requires an actual attempt,
   never just re-reading the code no-op.
7. **Isolation rules (parallel-safe — critical)** — **one new file only.** Name tmux sessions uniquely
   (prefix with the test slug). **NEVER call `tmux kill-server`** in teardown (it kills sibling agents'
   sessions). Run **only your own new test** in isolation — not the whole live tier. **Do not edit**
   `tests/conftest.py`, `pyproject.toml`, or `tests/README.md`; if you need a shared change (a new fixture,
   marker, or the `pythonpath` tidy), **STOP and report it to the human** rather than editing a shared file.
8. **Definition of done** — run your single new test through the repo venv, paste the **actual** pass/fail
   line (no paraphrase), and for anything that renders follow CLAUDE.md's "Verifying UI changes." **DEVLOG**
   the change before finishing.
9. **Guardrails (from CLAUDE.md)** — never create a git branch (work on `main`); bridge sessions stay
   **tab-less** (no auto-attach); scratch artifacts go to `.scratch/`; pytest is the standard.

**UI-slice prompt — extra requirements** (it differs from the backend spikes): use **Playwright-python +
pytest** (stays in the same venv, no Node toolchain), needs a **running sidecar**, ships a **minimal fixture
page** that talks only to the sidecar HTTP/SSE API, lives in **`tests/ui/`**, and **leaves `frontend/`
completely untouched.** Note that adding the `tests/ui/` subfolder is the trigger for the small `pythonpath`
fix in `pyproject.toml` — the agent must **flag that to the human**, not perform it.

---

## 4. Naming + output

Write each child prompt as its **own file** in `dev/prompts/`, with the `NN` = the §10 item number so every
prompt traces straight back to the queue:

```
2026-07-02-s10-build-01-permission-mode.md
2026-07-02-s10-build-02-thinking-mode.md
2026-07-02-s10-build-03-fast-mode.md
2026-07-02-s10-build-05-console.md
2026-07-02-s10-build-06-plan-decision.md
2026-07-02-s10-build-08-subagent-status.md
2026-07-02-s10-build-09-context-compact.md
2026-07-02-s10-build-10-oneclick-launch.md
2026-07-02-s10-build-11-per-agent-cost.md
2026-07-02-s10-build-UI-slice.md
# optional, low-priority:
2026-07-02-s10-build-04-inject-tail.md
2026-07-02-s10-build-07-runstrip-tail.md
```

When done: **DEVLOG** your additions (one entry listing the files created) and **stop.** Do not build any
tests — the prompts are the deliverable.
