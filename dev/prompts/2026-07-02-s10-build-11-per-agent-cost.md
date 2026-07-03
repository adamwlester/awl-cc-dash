# Build prompt — Per-agent cost harvest spike

## 1. Header

- **Test working name:** `per_agent_cost` (spike → durable live test *or* documented omission)
- **§10 item:** **#11 — Per-agent cost — 🧪 needs-spike** (Priority band: Low)
- **Goal:** Probe whether a **non-fabricated** per-agent cost/usage figure can be harvested for a `bridge` agent — from JSONL `message.usage` token fields, or from a `/cost` scrape over the console path — or confirm the honest "none available" boundary that the code currently ships.

You are a **build agent**. Produce ONE new live test file (or, if the spike proves harvest is genuinely impossible, a findings write-up + a proposal to move #11 to Decided omissions). Do not touch shared test infra. Work on `main`.

---

## 2. Read first (open these before writing a line)

1. **The §10 item itself:** `docs/ARCHITECTURE.md` **§10, item #11 "Per-agent cost"** (search the file for `**11. Per-agent cost**`, ~line 1176). Read all five bullets (Evidence / Desired / Blocker / Research-POC / Fallback) for the exact wording. Also read **§7.15 Settings** (~line 656–667) where the "honest blank, never a fabricated number" intent is stated.
2. **The research:** `dev/notes/research/claude-code-mode-control-research.md` — **§ "Question 4: context monitoring"** (~line 125–135). Items 1–3 there tell you exactly which token fields ARE available (`current_usage` splits by *type* — input/cache/output — not by cost) and note that **summing JSONL `usage` comes out lower than `/context`**. There is **no per-session cost telemetry surface** anywhere in that research. Use this to decide whether a *cost* number (vs a *usage* number) is derivable at all.
3. **THE PATTERN TO COPY:** `tests/test_bridge_finisher_live.py` — mirror its shape exactly (see §4). Note the module-level `pytestmark`, the `_Driven` helper wrapping a `BridgeDriver`, the throwaway-WSL-dir pattern, `asyncio.run(flow())` per test, and the `_cat(bridge, path)` read-back helper.
4. **The modules this test touches (read the real source, do not guess signatures):**
   - `sidecar/drivers/bridge.py` — **`derive_context_usage(entries)`** (~line 103): the ONLY usage math the bridge has; it reads `message.usage` = `input_tokens + cache_read_input_tokens + cache_creation_input_tokens` off the latest main-line assistant entry. There is **no cost field**. `BridgeDriver.get_context_usage()` (~line 681) wraps it. Note `CAPABILITIES` does **not** include `cost`.
   - `bridge/bridge.py` — **`read_log(name, last_n, types)`** (~line 960, parses the JSONL transcript into dicts with `message.usage`), **`send(name, text, press_enter=True)`**, **`read(name, lines)`** (`capture-pane -p -J -S`, ANSI stripped), **`_run(bash_cmd)`** (~line 156, raw WSL shell), **`close(name)`**.
   - `sidecar/main.py` — **`total_cost_usd`** field (line 134) is populated ONLY from an SDK `result` event's `total_cost_usd` (line 278–282); the bridge never emits a `result` event, so it **stays `0.0` for bridge agents**. **`POST /sessions/{id}/console/run`** (line 1354) = `send` a slash command then `read` the screen back. **`GET /usage`** (line 1748) — docstring states outright: *"Per-agent cost stays out of scope (the bridge emits none)."*

---

## 3. Mechanism / hypothesis

**Known lever (confirmed against code + research):** A `bridge` agent produces a JSONL transcript whose assistant entries carry `message.usage` token counts (input / cache_read / cache_creation / output). That is *usage*, and `derive_context_usage` already harvests it reliably. **Cost is a different thing** — turning tokens into dollars needs a per-model price table the dashboard does not have, and Question 4 of the research documents **no per-session cost telemetry surface** (statusline `current_usage` splits by token *type*, not cost; there is no cost hook field or transcript cost record).

Two candidate harvest paths this spike tests head-to-head:

- **(a) JSONL usage fields** — already proven to yield a *token* number (`read_log` → `derive_context_usage`). Hypothesis: this reliably yields **usage tokens**, but NOT a **cost** figure (no price table, and the sum is known to under-count vs `/context`). So it answers "usage: yes" / "cost: no".
- **(b) `/cost` scraped via the console path** — `send("/cost")` then `read()` the screen. Hypothesis: on a Max/Pro subscription account, `/cost` does **not** print a dollar figure (subscription plans typically render a "no cost estimate available" / duration-only panel rather than API-billing dollars). If it prints nothing dollar-shaped and defensible, that is the honest boundary — a **finding**, not a failure.

Expected honest outcome (from §7.15 + Question 4): **usage tokens are available; a trustworthy per-session *cost* is not** → keep the no-cost boundary the code already ships. Recording that with live evidence IS the deliverable.

---

## 4. Build this

Create **ONE** new file: **`tests/test_per_agent_cost_live.py`** (slug = `per_agent_cost`). Mirror `test_bridge_finisher_live.py`:

- Module top: the sidecar-on-`sys.path` shim (copy lines 28–36 of the finisher verbatim — `_REPO_ROOT / "sidecar"` inserted into `sys.path`, then `from drivers.bridge import BridgeDriver`, `from drivers.base import DriverConfig`).
- `pytestmark = [pytest.mark.integration, pytest.mark.slow]`.
- **Do NOT reuse conftest's `bridge` fixture** (see §7 — its teardown calls `tmux kill-server`). Instead, in this module, instantiate your **own** `from bridge import TmuxBridge` (add repo root to `sys.path` too) for the WSL shell helpers and for the read-back, and build your own throwaway-dir fixture that removes only its own dir.
- Give every session a **unique, slug-prefixed name**: e.g. `session_id=f"pacost-{uuid.uuid4().hex[:8]}"` so the driver's tmux session name is unique and parallel-safe.

**Test body (single `flow()` run via `asyncio.run`):**

1. **Spawn** a tab-less BridgeDriver in a fresh throwaway WSL dir (copy the finisher's `_Driven` + `diag_dir` approach, but with your OWN `TmuxBridge` instance, not the shared fixture). NEVER pass `show=True`.
2. **Drive a real turn** so the transcript has usage: `await d.driver.send("Reply with exactly: COST_OK")`, then poll `read_log` until an `assistant` entry containing `COST_OK` lands (copy `_send_marker_and_wait` from the finisher). This guarantees `message.usage` exists to harvest.
3. **Path (a) — JSONL usage:** call `await d.driver.get_context_usage()` (or `derive_context_usage(read_log(...))` directly). Assert it returns a dict with a non-None integer `tokens` > 0. Log it. Then assert the observable truth: this dict has **`tokens`/`work_steps` but NO `cost`/`total_cost_usd`/dollar key** — prove the usage-vs-cost distinction in code (`assert "cost" not in usage and "total_cost_usd" not in usage`).
4. **Path (b) — `/cost` scrape:** `bridge.send(tmux_name, "/cost")`, `sleep(~2s)`, `screen = bridge.read(tmux_name, lines=40)["content"]`. Log the full screen to the per-run debug log. Then **inspect it for a defensible dollar figure**: search for a `$`-prefixed number with a regex (e.g. `\$\s?\d+(\.\d+)?`). Record whether one appeared. On a subscription account the expected result is **no billing-dollar figure** (a "no cost estimate" / duration panel) — capture whatever it actually shows.
5. **Verdict assertion (see §5):** the test asserts the **honest state** — either a defensible number was found (with its source recorded) OR no cost figure is available and the code's `0.0` / out-of-scope boundary is correct. A **fabricated/guessed** number must never be asserted as a cost.

Keep console output concise; push the raw `/cost` screen, the usage dict, and the regex result to `logging.getLogger(__name__)` at DEBUG (per `tests/README.md` convention) so a failure is diagnosable.

---

## 5. The read-back is the crux

Sending `/cost` or reading `read_log` is trivial. **Proving a number is trustworthy is the whole test.** The specific observables and how to read each back:

- **Usage (path a):** the dict from `get_context_usage()` / `derive_context_usage()`. Read-back = the actual integer `tokens` off the latest assistant `message.usage`. This is real and defensible **as usage** — but it is NOT cost. The test must make that explicit (assert no cost key exists), because conflating usage tokens with a dollar cost would itself be the fabrication we are guarding against.
- **Cost (path b):** the `/cost` **screen text**, read back via `bridge.read(...)`. The observable is: *does a defensible `$`-denominated per-session figure appear?* If yes — record the exact line and its source and keep it. If no (the likely subscription outcome) — that IS the finding: **no reliable per-agent cost available**, matching `total_cost_usd == 0.0` for bridge agents and the `GET /usage` "out of scope" docstring.

If neither path yields a trustworthy **cost** number, that is a **FINDING, not a pass-by-omission** — write it up (§6). Do not invent a price table and multiply tokens to manufacture a green.

---

## 6. Two honest exits (spike-or-omit)

- **WORKS** — if a live `/cost` scrape (or another surface you discover live) yields a **defensible, non-fabricated per-session cost or usage number**: keep `tests/test_per_agent_cost_live.py` as a durable live test that asserts on that observable, and add a short note (top-of-file docstring + DEVLOG) of exactly what was harvested and from where. If only *usage tokens* are trustworthy (the likely case), the durable test asserts the usage number AND asserts that cost is correctly absent.
- **GENUINELY IMPOSSIBLE AFTER A REAL LIVE ATTEMPT** — if, after actually spawning a session and running `/cost` live, no trustworthy cost figure exists: **do not fabricate a green.** Write up the findings (what `/cost` printed, that JSONL yields usage-not-cost, that `total_cost_usd` stays `0.0`) and **propose moving #11 to Decided omissions** in `docs/ARCHITECTURE.md` §10 — the fallback ("no per-agent cost is shown; the account-level usage band §7.15 remains the cost surface") is already the shipped design, so this is a legitimate spike result. "Impossible" requires an **actual live attempt**, never a code-reading no-op. A durable test that asserts the honest boundary (usage present, cost correctly absent/`0.0`) is a perfectly good WORKS outcome too — prefer it over deletion if it is stable.

**Item-specific steer:** the most likely honest result is *"usage tokens are available, but a true COST needs a price table and no per-session cost telemetry exists"* → recommend keeping the no-cost boundary (which matches the current design and §7.15). Recording that as a finding is a **success**, not a failure.

---

## 7. Isolation rules (parallel-safe — CRITICAL; reproduce these in the file header comment)

- **ONE new file only:** `tests/test_per_agent_cost_live.py`. Create nothing else under `tests/`.
- **Unique tmux session names** — prefix every session with the slug (`pacost-<uuid8>`), so it can't collide with a sibling agent's session.
- **NEVER call `tmux kill-server`** (directly or via a fixture that does) in teardown — it kills other agents' live sessions.
- **Run ONLY your own new test** in isolation — never the whole live tier.
- **Do NOT edit** `tests/conftest.py`, `pyproject.toml`, or `tests/README.md`. If you think you need a shared change (a new fixture, a new marker, or the pythonpath tidy), **STOP and report it to the human** — do not edit a shared file.
- **The non-obvious trap:** the finisher leans on conftest's **session-scoped `bridge` fixture**, whose **setup AND teardown both call `_kill_all_tmux()` (= `tmux kill-server`)**. That is fine for a human running one file alone, but it would kill sibling agents' live sessions and breaks the parallel-safe rule. So **do NOT depend on that fixture** for a destructive lifecycle: **instantiate your OWN `TmuxBridge()`** inside your test module for the WSL shell helpers (mkdir / cat / rm) and for driving/reading, and in teardown remove **ONLY your own uniquely-named session** (via `close(name)`) and your own throwaway dir (`_run("rm -rf <yourdir>")`). If you believe you truly need the shared fixture or a new shared fixture/marker, **STOP and report to the human.**

---

## 8. Definition of done

- Run your **single** new test through the repo venv and paste the **actual** pytest result line (no paraphrase):
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\test_per_agent_cost_live.py -m integration
  # or:  tests\run.ps1 tests\test_per_agent_cost_live.py -m integration
  ```
  Paste the terminal `= N passed =` (or failure) line and/or `tests/log/results_latest.txt`.
- Create the venv first if missing: `python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt`.
- This test renders nothing (no UI surface), so the CLAUDE.md "Verifying UI changes" headed-pass rule does not apply here — but if you touch any rendered surface, follow it.
- **DEVLOG the change** before you finish: append a dated entry at the bottom of `DEVLOG.md` (heading + 1–4 lines + `Files:`) describing the new test / findings and the observed outcome.

---

## 9. Guardrails (from CLAUDE.md — reproduce, don't paraphrase away)

- **Never create a git branch.** Work on `main`. Do not run `git checkout -b` / `switch -c` / `branch <name>` / `worktree add` — they are gated and will prompt; if one prompts, stop and ask.
- **Bridge sessions stay TAB-LESS.** Never pass `show=True` to `create()`, never call `show()`. Sessions run detached; auto-popping a tab steals the user's focus.
- **Scratch artifacts go to `.scratch/`** (gitignored) — never the repo root. Per-run debug logs already go to `tests/log/`.
- **pytest is the standard** — no ad-hoc scripts; the deliverable is a pytest test (or a documented findings + omission proposal).
- **DEVLOG every repo change** before ending the turn (also in §8).
