# Build prompt — System-wide fault detection spike (the harvest half)

## 1. Header

- **Test working name:** `system_fault_harvest_live`
- **§10 item:** **#16 — System-wide fault detection — the harvest half behind the "System" Error cards — 🧪 needs-spike** (docs/ARCHITECTURE.md §10, item **#16**, `→ §5, §7.2, §7.8`)
- **Goal:** Establish, for each of the three **non-deterministic** system faults — **account rate/usage-cap hit**, **auth expiry**, **global MCP outage** — whether a **reliable, machine-readable signal** exists that the sidecar could key on to raise the fleet-wide "System" Error card. **Scope is the harvest half only.** The deterministic tmux/WSL/sidecar-liveness probes are ordinary build (body §5/§7) — **do not** spike those.

This is a **spike-or-omit** task. For each fault, the honest deliverable is either "here is the concrete signal + how to read it" or "no reliable signal is observable on this build — surface best-effort or omit." A confirmed *negative* per fault is a finding, not a failure. Do **not** invent a signal that isn't there.

---

## 2. Read first (open these before writing a line)

1. **Your §10 item — exact wording.** `docs/ARCHITECTURE.md` §10, item **#16** (in "Priority — coverage-audit additions"). Read all bullets. Note the explicit split: harvest half = spike; liveness probes = build.
2. **What the card looks like (so you know what a detector must feed).** `docs/ARCHITECTURE.md` §7.2 (the "System" pseudo-identity + its ⚠Today marker) and §7.8 (Inbox / Error rows). `design/DESIGN.md` — the System identity + the Inbox Error row. You are building the **detector**, not the card.
3. **What the code already does — and explicitly punts.** Read these anchors:
   - `sidecar/inbox.py` ~lines 9–11 — warnings are synthesized from the deterministic lifecycle-cap poll-loop; **"The rate/usage-cap subtype is gated on settings/account usage data and is not derived here."** (This is exactly the harvest gap.)
   - `sidecar/inbox.py` ~line 111 — a **screen-text `rate_limit` classifier already exists**: `re.compile(r"\b(429|rate[ _-]?limit|quota exceeded|too many requests)\b", re.I)`. Your spike validates/extends this against realistic samples, and asks the same "is there a signal?" question for auth-expiry and MCP-outage (which have **no** classifier today).
   - `sidecar/main.py` ~line 1748 `/usage` and ~line 1755 — **"Plan / rate-limit windows are intentionally NOT here."** So `/usage` is not the rate-cap signal.
4. **The research.** `dev/notes/research/claude-code-mode-control-research.md` (run-state / screen-state detection — how the bridge classifies pane text) and `dev/notes/research/research-cli-stream-and-permissions-api.md` (error/permission surfaces). For MCP: `dev/notes/research/claude-code-plugin-ecosystem-research.md` and `dev/notes/research/mcp-server-configuration-reference.md` (how MCP servers are configured and how an outage would surface). Pull the candidate signal for each fault from here and mark it confirm-on-this-build.
5. **THE pattern to copy.** `tests/test_bridge_finisher_live.py` — mirror its shape (module-level `pytestmark`, sidecar-on-`sys.path` shim, throwaway WSL diag dir, `asyncio.run(flow())`, read-state-back-and-assert). Bridge API you'll use: `create`, `send`, `read` (ANSI-stripped screen), `read_log`, `status`, `wait_idle`, `close`, `_run`.

---

## 3. Mechanism / hypothesis

Each of the three harvest faults has a *candidate* signal; the spike confirms which are real and machine-readable:

- **Rate/usage-cap hit** — hypothesis: surfaces as **screen/transcript text** matching the existing `rate_limit` classifier (`429` / "rate limit" / "quota exceeded" / "too many requests"). *You cannot safely provoke a real cap*, so validate the classifier against **representative sample strings** (from the research / real Claude Code error copy) and confirm the bridge's `read()` would surface such a line if it occurred. Flag whether the classifier's patterns match the *actual* wording this CLI build emits (confirm the copy).
- **Auth expiry** — hypothesis: surfaces as a distinct screen/CLI line (e.g. a re-login / "session expired" / OAuth-refresh prompt) and/or a detectable state in the local creds (an `expiresAt`/timestamp field). Probe **both**: (a) is there an observable screen signal? (b) can the sidecar read a creds expiry timestamp (see the `account_band`/creds reading in `sidecar/settings_io.py`) as a proactive signal? Determine which is reliable.
- **Global MCP outage** — hypothesis: **provokable live and safely.** Launch an agent configured with an **unreachable/bogus MCP server**, drive a turn that would use it, and observe how the failure surfaces (screen text, a tool-error entry in the JSONL transcript, an MCP status line). This is the one fault you can actually trigger without harming the account.

**Confirm, do not assume:** the exact wording/shape of each signal on the installed CLI build, and whether it is stable enough to key a detector on (vs. cosmetic/localized text that would make a brittle matcher).

---

## 4. Build this

Create **one** new file: **`tests/test_system_fault_harvest_live.py`**. Slug: **`sysfault`**. Module-level `pytestmark = [pytest.mark.integration, pytest.mark.slow]`. Mirror the finisher's imports/shim. Use your **own** `TmuxBridge()` (see §7 — do NOT use the shared `bridge` fixture). Structure as **three focused test functions**, one per fault (the ones that can only be validated against samples are still real tests — they assert the classifier/creds-read behavior):

- **`test_rate_cap_signal_classifier`** — assert the existing `inbox.py` `rate_limit` regex matches a set of representative cap-error strings and does **not** match benign lines; then confirm end-to-end that a line of that shape placed on a live pane is recoverable via `bridge.read()` (you may `echo` a representative line into the pane, or drive a benign turn and confirm the read path surfaces pane text). Record whether the classifier's wording matches the CLI's actual copy (flag if you can't confirm the real wording).
- **`test_auth_expiry_signal`** — probe the two candidate signals: read the local creds via the `settings_io` account-reading path and report whether an expiry/timestamp field is present and usable; and document whether any screen signal is observable (without actually expiring auth). Assert on what IS readable; record absences as findings.
- **`test_mcp_outage_signal_live`** — the provokable one. Spawn a tab-less, uniquely-named session configured with a **deliberately unreachable MCP server** (a bogus command/URL) in your throwaway diag dir, drive a turn that touches it, and read back (via `read()` / `read_log()`) exactly how the outage surfaces. Assert a machine-readable signal exists (a specific error entry/line); if none is reliably observable, record that.

For each fault, log at DEBUG (`logging.getLogger(__name__)`) the exact signal you found (or its absence) and the concrete matcher a detector would use — full detail to `tests/log/`.

---

## 5. The read-back is the crux

The point is **not** "does the card render" — it's **"is there a signal the sidecar can reliably detect?"** Name the observable per fault and read it back from the live surface (screen / transcript / creds), never assert on a value you injected as if the engine produced it:

- **Rate cap:** the classifier matches real-shaped cap text AND `bridge.read()` surfaces such a pane line → a detector is feasible. Mismatch between the classifier and the CLI's actual copy = a finding (the matcher needs updating).
- **Auth expiry:** a creds expiry field the sidecar can read, and/or a stable screen signal → feasible; neither → surface best-effort or omit.
- **MCP outage:** a specific, stable error entry in the transcript/screen when an unreachable server is used → feasible; only silent failure or cosmetic text → record that a reliable detector isn't available.
- **If a fault has no reliable machine-readable signal, that is a FINDING** — it feeds the §16 fallback (that fault is surfaced best-effort or omitted). Do not soften it into a false "detector works."

---

## 6. Two honest exits (spike-or-omit)

- **WORKS (per fault)** — you identified a reliable, machine-readable signal and the test asserts on it. Keep `tests/test_system_fault_harvest_live.py` as a durable test and note, per fault, the exact detector a build would implement (matcher + source). This graduates the harvest half toward a body §5/§7 fault-detection subsystem feeding the §7.2/§7.8 card.
- **NO SIGNAL AFTER A REAL ATTEMPT (per fault)** — for any fault where no reliable signal is observable, do **NOT** fabricate one. Record the finding and propose the §16 fallback for *that* fault (best-effort screen surface, or omit; the deterministic liveness probes still fire). "No signal" requires the actual probe (sample-match test for the cap, live outage for MCP, creds/screen probe for auth) — never a code re-read. Per-fault outcomes may differ; report each independently.

---

## 7. Isolation rules (parallel-safe — CRITICAL: reproduce these in the file header/comments)

Sibling agents may be running their own live bridge sessions at the same time. Violating any of these can kill their work.

- **ONE new file only** — `tests/test_system_fault_harvest_live.py`. Do not touch any other test file.
- **Uniquely-named tmux session** — prefix with the slug: `sysfault-<uuid8>`. Never a fixed/shared name.
- **The bogus MCP server must be scoped to YOUR agent only** — configure it in your own throwaway diag dir / per-agent settings, never in a shared/global MCP registry other agents inherit.
- **Never actually expire, exhaust, or tamper with the real account/auth.** The auth and rate-cap tests are *observation/sample* tests — do not attempt to trigger a real cap or a real logout.
- **NEVER call `tmux kill-server`** (directly or via any helper) in teardown — it kills *every* agent's sessions.
- **Run ONLY your own new test** in isolation — not the whole live tier.
- **Do NOT edit shared files** — `tests/conftest.py`, `pyproject.toml`, `tests/README.md`, or the global MCP config. If you think you need a new fixture, marker, pythonpath tidy, or a shared config change, **STOP and report it to the human**.
- **The non-obvious trap:** the finisher leans on conftest's session-scoped **`bridge` fixture**, whose **setup AND teardown both call `_kill_all_tmux()` (= `tmux kill-server`)** — which would kill sibling agents' sessions. **Instantiate your OWN `TmuxBridge()`** and tear down only your uniquely-named session via `bridge.close(name)` + your own dir. Never a broad kill.

---

## 8. Definition of done

- Run your **single** new test through the repo venv and paste the **actual** pytest result line — no paraphrase (the terminal `= N passed =` / `= N xfailed =` line, and/or `tests/log/results_latest.txt`):

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\test_system_fault_harvest_live.py -m integration
  # or:  tests\run.ps1 tests\test_system_fault_harvest_live.py -m integration
  ```
  (Create the venv first if missing: `python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt`.)
- Your report must state, **per fault** (rate cap / auth expiry / MCP outage), the signal found (matcher + source) or its confirmed absence — this is what the body fault-detection subsystem will implement.
- Nothing here renders a UI, so the CLAUDE.md "Verifying UI changes" browser pass does not apply.
- **DEVLOG the change** before you finish — append a new dated entry at the bottom of `DEVLOG.md` (per-fault findings, files added), per the CLAUDE.md DEVLOG rule.

---

## 9. Guardrails (from CLAUDE.md — reproduce, do not skip)

- **Never create a git branch.** Work on `main`. Do not run `git checkout -b` / `switch -c` / `branch <name>` / `worktree add` — these are gated and will prompt; if one prompts, **stop**. Committing to `main` is fine (but the orchestrator handles git here — do not commit unless told).
- **Bridge sessions stay TAB-LESS.** Create with `show=False`; **never** pass `show=True` and **never** call `show()`. An auto-popped Windows Terminal tab steals the user's focus mid-task.
- **Scratch artifacts go to `.scratch/`** — never the repo root or other project folders. Per-run DEBUG detail goes to `tests/log/` (gitignored) via `logging.getLogger(__name__)`.
- **pytest is the standard** — no ad-hoc scripts. Tag this live test `@pytest.mark.integration` + `@pytest.mark.slow` (module-level `pytestmark`).
