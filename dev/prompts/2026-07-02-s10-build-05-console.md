# Build prompt — Console mirror: wiring + ANSI-fidelity spike

## 1. Header

- **Test working name:** `console_mirror_live` (Console rendering fidelity spike)
- **§10 item:** **#5 — Console rendering fidelity — 🧪 needs-spike** (docs/ARCHITECTURE.md §10, item **#5**, `→ §7.13`)
- **Goal:** Prove the Console mirror **wiring** first (keystrokes pass through to the live pane and the mirror reflects the change), then **separately** probe **ANSI fidelity** — show that an `-e` (escape-preserving) `capture-pane` recovers the SGR styling that the plain `read()` path drops. This is a **split** spike: two clearly separate parts in one file.

---

## 2. Read first

Open these before writing a line:

1. **Your §10 item — the exact wording.** `docs/ARCHITECTURE.md` §10, item **#5 "Console rendering fidelity"** (around lines 1101–1111). Read all four bullets (Desired / Blocker / Research-POC-must-establish / Fallback) verbatim — do not work from the paraphrase below.
2. **The research.** `dev/notes/research/claude-code-mode-control-research.md` — **§ "Question 3: driving the TUI reliably"** (Run-state detection / input-injection context, ~line 97+). Corroborates that `tmux capture-pane` is the read mechanism and that plain capture drops ANSI.
3. **THE PATTERN TO COPY:** `tests/test_bridge_finisher_live.py` — copy its *shape* (module-level `pytestmark`, `sys.path` insert of `sidecar/`, a throwaway WSL `diag_dir`, each test body an `async flow()` run via `asyncio.run(flow())`, read-state-back-and-assert). **Do NOT copy its `bridge` fixture dependency** — see §7 for why.
4. **The two modules under test:**
   - `bridge/bridge.py` — `read()` (line ~534: `capture-pane -t '<name>' -p -J -S -<lines>` — **no `-e`**, so it strips ANSI), `_run()` (line ~156: raw WSL bash, your handle for an `-e` capture), `create()` (line ~283, note `show=False` default), `send()` (~497), `keys()` (~517), `close()` (~589).
   - `sidecar/main.py` — `POST /sessions/{id}/console/run` (line ~1354, `console_run`): it does `drv._bridge.send(tmux_name, command)` → `sleep(1.0)` → `drv._bridge.read(tmux_name, lines=40)`. That **send-then-read** is exactly the wiring your Gap A mirrors. You do **not** need the HTTP layer — drive the bridge directly, as the finisher drives the driver directly.

---

## 3. Mechanism / hypothesis

The §10 item explicitly tracks **two separate gaps** — reproduce that framing:

- **Gap A — wiring (keystroke passthrough + live mirror).** The lever: `bridge.send()` / `bridge.keys()` map straight onto `tmux send-keys`, and `bridge.read()` (`capture-pane -p -J -S`) reads the pane back. The `console/run` endpoint is literally `send` then `read`. **Hypothesis:** a keystroke typed into a live pane shows up on the very next capture — passthrough and mirror are wired. Research **Question 3 (Run-state / input-injection)** confirms `capture-pane` + `send-keys` is the established, reliable drive/read loop (independently corroborated by the bjornjee/primeline-ai analogs cited there).

- **Gap B — fidelity (ANSI recovery).** The lever: `bridge.read()` runs `capture-pane` **without `-e`**, so ANSI/SGR escapes are stripped to plain text. Re-capturing the **same** pane with `capture-pane -e` (escape-preserving) via `bridge._run("tmux capture-pane -t '<name>' -e -p -J -S -<n>")` should re-expose the raw SGR sequences (`ESC[…m`, i.e. bytes `\x1b[`). **Hypothesis:** the `-e` capture contains `\x1b[` sequences; the plain `read()` of the same screen does not. This proves the styling is **recoverable** — but only via `-e` **plus** a terminal-renderer (xterm.js-class) in the frontend, which §10's blocker names and which is **out of scope for a backend spike**. The Claude Code TUI at rest is colored (prompt box, hint text), so SGR codes are present on any idle screen.

---

## 4. Build this

One new file: **`tests/test_console_mirror_live.py`**. Module-level `pytestmark = [pytest.mark.integration, pytest.mark.slow]`. Mirror the finisher's imports/`sys.path` handling. **Two test functions** (the split), both driving your **own** `TmuxBridge` (see §7 — do NOT use the shared `bridge` fixture).

Set up a module-local `TmuxBridge` and a throwaway WSL dir yourself (own fixtures, uniquely named):

```python
import uuid, pytest
from pathlib import Path
# ... sys.path insert of repo root so `from bridge import TmuxBridge` resolves ...
from bridge import TmuxBridge

pytestmark = [pytest.mark.integration, pytest.mark.slow]

SLUG = "conmirror"                      # tmux-name + dir prefix — parallel-safe

@pytest.fixture
def br():
    b = TmuxBridge()
    yield b
    # NO kill-server, NO shutdown() — teardown removes only our own session (below)

@pytest.fixture
def diag_dir(br):
    path = f"/home/lester/awl-{SLUG}-{uuid.uuid4().hex[:8]}"
    br._run(f"mkdir -p {path}")
    yield path
    br._run(f"rm -rf {path}")
```

Helper to spawn a live, **tab-less**, uniquely-named session and wait for the TUI to be ready:

```python
def _spawn(br, diag_dir):
    name = f"{SLUG}-{uuid.uuid4().hex[:8]}"      # unique per test
    br.create(name, cwd=diag_dir, show=False)    # show=False = NO tab (mandatory)
    # wait for the composer to appear before driving
    br.watch(name, r"(Welcome|❯|for shortcuts|Bypass|>)", timeout=90, interval=1.0)
    return name
```

**Test 1 — `test_gap_a_keystroke_passthrough_and_mirror` (WIRING):**
1. `name = _spawn(br, diag_dir)`.
2. Capture a **baseline** screen: `before = br.read(name, lines=40)["content"]`.
3. Type a unique literal marker into the composer **without submitting** (so the result is deterministic and side-effect-free): `br.send(name, "AWL_CONSOLE_MARKER_<uuid>", press_enter=False)`. (This is the passthrough — same `send-keys` path the `console/run` endpoint uses.)
4. `sleep(~1.0)`, then `after = br.read(name, lines=40)["content"]`.
5. **Assert the mirror reflects the keystrokes:** the marker string is present in `after` and was **not** in `before`. That is the read-back — the pane changed exactly as driven.
6. Clean the composer so nothing is left half-typed: `br.keys(name, "Escape")` (or `C-u`). Do **not** press Enter.
7. (Optional, strengthens the "mirror is live" claim) also confirm a slash command round-trips like the endpoint does: `br.send(name, "/help")` then `read()` and assert the screen changed again. Keep it non-fatal / secondary — the literal-marker assertion is the primary proof.

**Test 2 — `test_gap_b_ansi_recoverable_only_with_e` (FIDELITY):**
1. `name = _spawn(br, diag_dir)` (idle colored TUI screen is enough — no need to drive anything).
2. **Plain capture** via the production path: `plain = br.read(name, lines=40)["content"]`.
3. **Escape-preserving capture** of the **same** pane via raw tmux: `raw = br._run(f"tmux capture-pane -t '{name}' -e -p -J -S -40")`.
4. **Assert fidelity is recoverable only with `-e`:**
   - `"\x1b[" in raw` (SGR escapes present) — or, more robustly, `re.search(r"\x1b\[[0-9;]*m", raw)` is truthy.
   - `"\x1b[" not in plain` (the production `read()` path dropped them).
5. Log a short line (via `logging.getLogger(__name__)` at DEBUG, per repo test convention) recording how many SGR sequences the `-e` capture recovered — that's the "what was learned" note.

Every test wraps its body so the session is always torn down (see §7 teardown). Keep sleeps modest; use `br.watch` / `br.wait_idle` rather than long fixed sleeps where you can.

---

## 5. The read-back is the crux

Sending the keystroke or running the `-e` capture is trivial — **proving it took effect is the entire test.**

- **Gap A observable:** the **exact typed marker string appears in the next `bridge.read()` and was absent from the baseline capture.** If the marker never appears in the mirror, the passthrough/mirror wiring is broken — that is a **finding**, not a pass.
- **Gap B observable:** the **`-e` capture contains raw SGR escape bytes (`\x1b[…m`) that the plain `read()` of the same screen does not.** If the `-e` capture contains no escapes (e.g. tmux/TERM strips them in this environment), fidelity is *not* recoverable this way — write that up as a finding; do not assert-around it.

Read the state **back from the live pane**, exactly as the finisher reads files back with `_cat` — never assert on the value you just sent.

---

## 6. Two honest exits (spike-or-omit)

- **WORKS (expected for Gap A; likely for Gap B):** keep the file as a durable live test. Add a 2–3 line note (in the module docstring and DEVLOG) of what was learned: *Gap A wiring is proven — keystrokes pass through and the mirror reflects them; the `console/run` endpoint's send-then-read is sound. Gap B — ANSI styling IS recoverable via `capture-pane -e`; faithful rendering still needs an xterm.js-class renderer in the frontend, which is out of scope for this backend spike (that half stays deferred, not failed).*
- **GENUINELY IMPOSSIBLE AFTER A REAL LIVE ATTEMPT:** if — after actually spawning a session and capturing — Gap B's `-e` capture yields no escapes on this machine (TERM/tmux config strips SGR), do **NOT** fabricate a green. Write up the findings and propose the fidelity half move toward §10 "Decided omissions" / the plain-text-mirror fallback. "Impossible" requires a real run, never a re-read of the code.
- **Honest split outcome:** **Gap A passing while Gap B is deferred as "fidelity needs a frontend renderer, out of scope for a backend spike" is a legitimate, expected result — not a failure.** State it plainly if that's what happens.

---

## 7. Isolation rules (parallel-safe — critical)

Other agents may be running live bridge sessions at the same time. Reproduce **all** of these in the file and obey them:

- **ONE new file only** — `tests/test_console_mirror_live.py`. Create nothing else.
- **Uniquely-named tmux sessions** — every session name is `"conmirror-" + uuid` (the `SLUG` prefix). Never a fixed/shared name.
- **NEVER call `tmux kill-server`** (and never `TmuxBridge.shutdown()`) in teardown — it kills sibling agents' live sessions.
- **Run ONLY your own new test in isolation** — not the whole live tier.
- **Do NOT edit `tests/conftest.py`, `pyproject.toml`, or `tests/README.md`.** If you think you need a shared change (a new fixture, marker, or a pythonpath tidy), **STOP and report it to the human** — do not edit a shared file.
- **Non-obvious trap — do NOT reuse the finisher's `bridge` fixture.** That fixture is conftest's **session-scoped** `bridge`, whose **setup AND teardown both call `_kill_all_tmux()` (= `tmux kill-server`)**. Fine for a human running one file alone; fatal here — it would kill sibling agents' live sessions and breaks parallel-safety. So **instantiate your OWN `TmuxBridge()` inside this module** (as in §4) for the WSL shell helpers (`mkdir`/`rm`/raw `-e` capture via `_run`) and for driving, and in teardown **remove ONLY your own uniquely-named session** via `br.close(name)` plus your own throwaway `diag_dir`. Ensure each test `close()`s the session it spawned even on failure (try/finally around the body).

---

## 8. Definition of done

- Run your **single** new test through the repo venv and paste the **actual** pytest summary line, no paraphrase — the terminal `= N passed =` line (and/or `tests/log/results_latest.txt`):

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\test_console_mirror_live.py -m integration
  ```
  (equivalently `tests\run.ps1 tests\test_console_mirror_live.py -m integration`). Create the venv first if missing, per CLAUDE.md → Testing.
- This spike is **backend-only** — no rendered UI surface — so the "Verifying UI changes" browser pass does **not** apply here (the xterm.js renderer is explicitly out of scope). If you happen to touch anything that renders, follow CLAUDE.md "Verifying UI changes".
- **DEVLOG the change** before finishing — append a dated entry (what landed, the pass/fail line, and the Gap A / Gap B outcome) per the DEVLOG rule.

---

## 9. Guardrails (from CLAUDE.md)

- **Never create a git branch.** Work on `main`. Do not run `git checkout -b` / `switch -c` / `branch <name>` / `worktree add` — they're gated and will prompt; if one prompts, stop.
- **Bridge sessions stay TAB-LESS.** Always `create(..., show=False)` (the default) and **never call `show()`** — a tab must never open as a side effect of a test.
- **Scratch artifacts go to `.scratch/`** (gitignored), never the repo root or other project folders.
- **pytest is the standard** — no ad-hoc scripts; this deliverable is a pytest module.
