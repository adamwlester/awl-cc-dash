# Build prompt — Usage & context data-source probe (grouped: §10 #18 + #21)

## 1. Header

- **Test working name:** `usage_context_sources_live`
- **§10 items (GROUPED — one test, two items):**
  - **#18 — statusLine `context_window` as a live mid-run context source — 🧪 needs-spike**
  - **#21 — Usage / limits source-boundary confirmation — 🧪 needs-spike**
- **Goal:** In **one** live session, probe every candidate **data source** the dashboard's context + usage readouts depend on, and record — per source — exactly what it delivers under the bridge: **(A)** whether a configured **statusLine** exposes a machine-readable `context_window` value **mid-run** (#18); **(B)** what **account identity** the local creds actually provide (#21); **(C)** what **usage/limits** any reachable API/CLI surface actually provides (#21).
- **Why grouped:** #18 and #21 are the same shape of question — *"does source X actually yield field Y under the bridge?"* — and share one live-session setup + one set of inspections. Keeping them one test avoids duplicate scaffolding. Each item is reported **independently** so the §10 entries resolve separately. This complements (does not retest) the already-built **#9 context derivation** (`test_bridge_unit`) and **#11 per-agent-cost** (`build-11`) spikes.

This is a **spike-or-confirm** task. Per source, the deliverable is "here is the field + how to read it" or "this source does **not** deliver that field on this build." A confirmed absence is a finding that sets an honest data boundary — do **not** invent data a source doesn't provide.

---

## 2. Read first (open these before writing a line)

1. **Your §10 items — exact wording.** `docs/ARCHITECTURE.md` §10, items **#18** and **#21** (in "Priority — coverage-audit additions"). Read all bullets of each. Note #18's tension: **DESIGN asserts context "can't be read mid-run"** — this spike tests whether that's actually true.
2. **The research — the specific levers.** `dev/notes/research/claude-code-mode-control-research.md`:
   - **~line 80** — "Context: tokens summed from JSONL `usage`; the window is **model-dependent** via `model::context_window()` (200,000 default, 1,000,000 for the 1M-context Opus)."
   - **~line 150** — "make the context window model-dependent (or **read `context_window_size` from the statusline payload**)." **This is the #18 lever:** a configured statusLine may emit a `context_window`/`context_window_size` value the sidecar can read live.
   Also skim `dev/notes/research/claude-compaction-reference.md` (context window sizing).
3. **The code these feed.** Read:
   - `sidecar/main.py` — `get_context_usage` (~line 1606) and `GET /usage` (~line 1748, header ~line 1745 "Usage (token / context aggregate)"; ~line 1755 "Plan / rate-limit windows are intentionally NOT here"), and the "Settings — … account/usage" section (~line 1377). This is where confirmed sources would land.
   - `sidecar/settings_io.py` — `account_band(creds_path)` (~line 208) reads local creds and returns `{email, org, plan}` **for display only** (~lines 35–36); the lenient field maps + wrapper-nest keys (`oauthAccount`/`account`/`user`/`claudeAiOauth`/`auth`, ~line 198). **This is the #21 account-source path.**
   - `sidecar/drivers/bridge.py` — `get_context_usage()` on the driver (what it currently derives from JSONL) and how a statusLine payload could be captured.
4. **THE pattern to copy.** `tests/test_bridge_finisher_live.py` — mirror its shape (module-level `pytestmark`, sidecar-on-`sys.path` shim, throwaway WSL diag dir, `asyncio.run(flow())`, read-state-back-and-assert). Bridge API: `create`, `send`, `read`, `read_log`, `status`, `wait_idle`, `close`, `_run`.

---

## 3. Mechanism / hypothesis

Three sources, three sub-probes in one session:

- **(A) #18 — statusLine `context_window` mid-run.** Lever: configure a **statusLine** for the agent (Claude Code renders a status line whose payload/command can include a `context_window`/`context_window_size` field). Hypothesis: while the agent is **mid-run (generating)**, the statusLine value is observable (on the pane via `read()`, or via the statusLine command's output) and parseable — giving live context usage that JSONL-after-the-fact can't. If observable mid-run, DESIGN's "can't read mid-run" is wrong and should be reconciled; if not, DESIGN stands.
- **(B) #21 — account identity from creds.** Lever: the `account_band()` creds-reading path. Hypothesis: local creds yield `{email, org, plan}` reliably. Probe what fields are actually present (via the same lenient/nested reading) and whether `plan` (tier) is among them.
- **(C) #21 — usage/limits from an API/CLI surface.** Hypothesis: usage/limit *windows* are **not** locally available (the code already says `/usage` intentionally excludes rate-limit windows). Probe whether *any* reachable surface (a `/usage`-style CLI command, an API the creds' token could call, statusLine usage fields) yields live usage/limit numbers — or confirm the honest boundary that limits are **not** locally derivable.

**Confirm, do not assume:** the exact field names/shape on the installed build; whether the statusLine value updates mid-run vs only at turn boundaries; and which of `{email, org, plan, usage, limits}` are genuinely present vs absent.

---

## 4. Build this

Create **one** new file: **`tests/test_usage_context_sources_live.py`**. Slug: **`usagesrc`**. Module-level `pytestmark = [pytest.mark.integration, pytest.mark.slow]`. Mirror the finisher's imports/shim. Use your **own** `TmuxBridge()` (see §7 — do NOT use the shared `bridge` fixture). Structure as **three focused test functions**, tagged in their names/docstrings with the §10 item they answer:

- **`test_18_statusline_context_window_midrun`** — spawn a tab-less, uniquely-named session configured with a **statusLine that surfaces the context value** (per research ~line 150). Drive a long generating turn; **while `status(name) == "generating"`**, read back the statusLine value (via `read()` of the pane and/or the statusLine command output) and assert a machine-readable `context_window`/`context_window_size` is present and numeric mid-run. If it only appears at turn end (not mid-run), record that precisely — it changes the #18 verdict.
- **`test_21_account_band_from_creds`** — exercise the `account_band()` creds path against the real local creds and record which of `{email, org, plan}` (and any usage/limit fields) are actually present. Assert on what IS present; record absences.
- **`test_21_usage_limits_surface`** — probe any reachable usage/limits surface (a `/usage`-style command run via the Console/bridge, or the driver's `get_context_usage()`), and record whether live usage/limit numbers are obtainable or confirm the boundary that they are not locally derivable.

Log at DEBUG (`logging.getLogger(__name__)`) a per-source table: `source → field → present? → sample value` — full detail to `tests/log/`.

---

## 5. The read-back is the crux

Configuring a statusLine or calling a creds reader is trivial — **the whole test is confirming the field is actually there and usable.** Per sub-probe, name the observable and read it back from the live source, never assert a value you supplied:

- **#18:** a numeric `context_window`/`context_window_size` read back from the statusLine **while status is still `generating`** → live mid-run context is available (reconcile DESIGN). Only-at-turn-end, or absent → DESIGN's "can't read mid-run" holds; record it.
- **#21 account:** the exact set of creds fields present (email/org/plan) → confirms the account band's real source. A missing `plan`/tier is a finding for the Usage UI.
- **#21 usage/limits:** actual live usage/limit numbers from a reachable surface → confirmed source; nothing obtainable → the honest boundary (limits not locally derivable), which is a legitimate result, not a failure.
- **A confirmed absence is a FINDING per item.** It sets the data boundary the Usage/context UI must respect — do not paper over it with a fabricated number.

---

## 6. Two honest exits (spike-or-confirm) — reported per item

- **CONFIRMED (per source)** — the source delivers the field; the test asserts on it. Keep `tests/test_usage_context_sources_live.py` as a durable test. Report **separately for #18 and #21** exactly which fields each source yields — this lets the two §10 items resolve independently (e.g. #18 confirmed but #21-limits an honest boundary).
- **BOUNDARY / ABSENT AFTER A REAL PROBE (per source)** — a source doesn't deliver a field. Do **NOT** fabricate it. Record the boundary and map it to the item's fallback: #18 → context stays JSONL/`/context`-derived, DESIGN's "can't read mid-run" stands; #21 → show only what a source demonstrably provides, mark the rest an honest boundary. "Absent" requires the actual probe, never a code re-read. Per-item outcomes may differ; report each independently and say which §10 item each result resolves.

---

## 7. Isolation rules (parallel-safe — CRITICAL: reproduce these in the file header/comments)

Sibling agents may be running their own live bridge sessions at the same time. Violating any of these can kill their work.

- **ONE new file only** — `tests/test_usage_context_sources_live.py`. Do not touch any other test file.
- **Uniquely-named tmux session** — prefix with the slug: `usagesrc-<uuid8>`. Never a fixed/shared name.
- **Read creds; never write or mutate them.** The account probe is read-only against the real local creds — do not modify, re-auth, or delete any credential file.
- **Any statusLine config is scoped to YOUR agent only** — set it in your own throwaway diag-dir / per-agent settings, never in a shared/global config other agents inherit.
- **NEVER call `tmux kill-server`** (directly or via any helper) in teardown — it kills *every* agent's sessions.
- **Run ONLY your own new test** in isolation — not the whole live tier.
- **Do NOT edit shared files** — `tests/conftest.py`, `pyproject.toml`, `tests/README.md`, or any global Claude Code settings. If you think you need a new fixture, marker, pythonpath tidy, or a shared-config change, **STOP and report it to the human**.
- **The non-obvious trap:** the finisher leans on conftest's session-scoped **`bridge` fixture**, whose **setup AND teardown both call `_kill_all_tmux()` (= `tmux kill-server`)** — which would kill sibling agents' sessions. **Instantiate your OWN `TmuxBridge()`** and tear down only your uniquely-named session via `bridge.close(name)` + your own dir. Never a broad kill.

---

## 8. Definition of done

- Run your **single** new test through the repo venv and paste the **actual** pytest result line — no paraphrase (the terminal `= N passed =` / `= N xfailed =` line, and/or `tests/log/results_latest.txt`):

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\test_usage_context_sources_live.py -m integration
  # or:  tests\run.ps1 tests\test_usage_context_sources_live.py -m integration
  ```
  (Create the venv first if missing: `python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt`.)
- Your report must **separately** state the verdict for **#18** (statusLine context mid-run: available or not) and **#21** (which of account/usage/limits each source delivers) — the two items resolve independently.
- Nothing here renders a UI, so the CLAUDE.md "Verifying UI changes" browser pass does not apply.
- **DEVLOG the change** before you finish — append a new dated entry at the bottom of `DEVLOG.md` (per-item findings for #18 and #21, files added), per the CLAUDE.md DEVLOG rule.

---

## 9. Guardrails (from CLAUDE.md — reproduce, do not skip)

- **Never create a git branch.** Work on `main`. Do not run `git checkout -b` / `switch -c` / `branch <name>` / `worktree add` — these are gated and will prompt; if one prompts, **stop**. Committing to `main` is fine (but the orchestrator handles git here — do not commit unless told).
- **Bridge sessions stay TAB-LESS.** Create with `show=False`; **never** pass `show=True` and **never** call `show()`. An auto-popped Windows Terminal tab steals the user's focus mid-task.
- **Scratch artifacts go to `.scratch/`** — never the repo root or other project folders. Per-run DEBUG detail goes to `tests/log/` (gitignored) via `logging.getLogger(__name__)`.
- **pytest is the standard** — no ad-hoc scripts. Tag this live test `@pytest.mark.integration` + `@pytest.mark.slow` (module-level `pytestmark`).
