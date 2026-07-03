# Build prompt — Hook event-stream spike (push-based run-state / permission-mode)

## 1. Header

- **Test working name:** `hook_event_stream_live`
- **§10 item:** **#14 — Hook-driven run-state / permission-mode push channel ("hook event stream") — 🧪 needs-spike** (docs/ARCHITECTURE.md §10, item **#14**, `→ §6.2, §7.4, §7.11`)
- **Goal:** Prove — or honestly disprove — that a Claude Code agent's **HTTP hooks** can POST lifecycle events to the sidecar such that **run-state and `permission_mode` arrive as a push signal on the hook payload** (not screen-polling), and that the payload actually carries the fields the push-architecture depends on. This is the concrete, spike-able core of the design question that `dev/prompts/2026-07-02-s10-research-14-hook-event-stream.md` explores.

This is a **spike-or-omit** task. Confirming the payload fields (or honestly recording that a given field is absent) is the deliverable. A "hook fired but carried no `permission_mode`" result is a **finding**, not a failure to be papered over. Do **not** manufacture a pass.

---

## 2. Read first (open these before writing a line)

1. **Your §10 item — exact wording.** `docs/ARCHITECTURE.md` §10, item **#14** (in the "Priority — coverage-audit additions" subsection near the end of §10). Read all bullets: Desired / Blocker / Research-POC / Fallback. Note that §14 is explicitly *"an extension, not a greenfield build"* — the sidecar already ingests some hooks.
2. **The design research (already written — build on it, don't restart cold).** `dev/prompts/2026-07-02-s10-research-14-hook-event-stream.md` — the self-contained research prompt for the *architectural* decision (replace-vs-run-alongside, exact event set, ordering/dedup). Read it to understand the target design; **your spike answers the empirical sub-question it flags for verification**: *does an HTTP-hook payload actually carry `permission_mode` + the current tool on every tool/turn event?* (that prompt tags this "plausible, prior-art-observed — confirm on the installed CLI build").
3. **The mechanism research.** `dev/notes/research/claude-code-mode-control-research.md` — the hook-channel / run-state-detection findings (Question 1's hook approaches, and the note that hooks fire with `permission_mode` "for free" on the *deny* path). Also `dev/notes/research/research-cli-stream-and-permissions-api.md` for the hook/permission surface. Pull the exact candidate event names and payload-field claims from here and treat each as **confirm-on-this-build**.
4. **THE pattern to copy.** `tests/test_bridge_finisher_live.py` — mirror its shape: module-level `pytestmark = [pytest.mark.integration, pytest.mark.slow]`, the sidecar-on-`sys.path` shim, a throwaway WSL diag dir, per-test body run via `asyncio.run(flow())`. It already **exercises the real hook round-trip** (the finisher's inject path POSTs a hook back to the sidecar) — study how it stands up the receiver and how a hook reaches the Windows host from inside WSL2.
5. **The modules this test touches** (read the real code — do not guess signatures):
   - `sidecar/drivers/bridge.py` — `_build_hook_settings` / `_build_hook_settings`-equivalent (~line 452): the per-agent `PostToolUse` + `Stop` HTTP hooks that are wired today, and the WSL→Windows gateway URL construction. This is the path you extend with additional events.
   - `sidecar/hookbus.py` — `post_tool_use_output`, `stop_output`, `enqueue_inject`, `pending`, `drain`: the existing hook-ingest surface. Your spike registers **more** events against a receiver of this shape.
   - `sidecar/main.py` — the `/internal/hooks/...` receiver endpoints the agents POST to. Confirm exactly what the sidecar already accepts and what a new event payload would land in.
   - `bridge/bridge.py` — `wsl_host_ip()` / `sidecar_hook_base_url()` (the default-gateway resolution that makes `http://<gateway-ip>:7690/...` reachable from WSL2), `create`, `keys`, `send`, `status`, `read_log`, `wait_idle`, `close`.

---

## 3. Mechanism / hypothesis

**Known lever (from §14 + research-14 + mode-control research):** Claude Code hooks can be configured as `{"type":"http","url":"http://<gateway-ip>:7690/internal/hooks/…","timeout":N}` and fire on lifecycle events. The sidecar **already** receives `PostToolUse` and `Stop` this way (proven live by the finisher's inject path) over the resolved WSL2 default-gateway URL. The spike **extends** that: register the candidate run-state events (from research-14: `PreToolUse` / `PostToolUse` / `Stop` / `Notification` / `UserPromptSubmit`, and — *if they exist on this build* — `PermissionRequest` / `SubagentStart` / `SubagentStop`) against a lightweight receiver, drive a real agent through a turn (including a permission prompt), and **inspect the actual JSON payloads** the sidecar receives.

**What we expect if the lever works:** each tool/turn boundary POSTs a payload, and that payload contains a machine-readable `permission_mode` (and ideally the current tool name) — giving the sidecar authoritative live mode/run-state **without** screen-polling. If it works, the push channel can become the authoritative-when-present run-state signal with polling as the fallback.

**Confirm, do not assume (research-14 flags these):**
- Whether the payload carries `permission_mode` on **every** tool/turn event (or only some).
- Whether each candidate event name is a **real, documented** hook event on the installed CLI (several — `PermissionRequest`, `SubagentStart`, `StopFailure` — are *candidates that may not exist*; for each you rely on, confirm it fires, and mark any that don't).
- Ordering / dedup behavior when events arrive close together (even single-agent, note out-of-order or duplicate arrivals).

**Cite:** `dev/prompts/2026-07-02-s10-research-14-hook-event-stream.md` (the "verify before relying" list) and `claude-code-mode-control-research.md` (hooks fire with `permission_mode`; the deny path is reliable).

---

## 4. Build this

Create **one** new file: **`tests/test_hook_event_stream_live.py`**. Slug: **`hookstream`**. Marked at module level:

```python
pytestmark = [pytest.mark.integration, pytest.mark.slow]
```

Mirror the finisher's imports/shim (`_REPO_ROOT`, put `sidecar/` on `sys.path`). You will **NOT** use the shared session-scoped `bridge` fixture (see §7 — its teardown calls `tmux kill-server`). Instantiate your **own** `TmuxBridge()`.

**You need a receiver the agent can POST to.** Two viable shapes — pick the simpler that works and note which you chose:

- **Recommended — a tiny in-test HTTP receiver.** Stand up a minimal `http.server`/`aiohttp`/`asyncio` HTTP listener bound to `0.0.0.0` on an ephemeral port, that appends every received `(path, json_body, headers, monotonic_ts)` to an in-memory list. Build the agent's hook URLs against `bridge.wsl_host_ip()` (the WSL2 default-gateway IP) + your port — exactly as the driver builds `sidecar_hook_base_url()` — so the WSL agent can reach your Windows-side receiver. This isolates the spike from the running sidecar and lets you assert on raw payloads.
- **Alternative — reuse the sidecar's ingest.** If standing up a receiver is fiddly, register the events against the real sidecar's `/internal/hooks/...` and read back what it captured. Only do this if you can inspect the raw payloads (not just derived state).

**Concrete flow:**

1. **Setup** — unique session name `f"hookstream-{uuid.uuid4().hex[:8]}"`, throwaway WSL dir `f"/home/lester/awl-hookstream-{uuid.uuid4().hex[:8]}"` via `bridge._run("mkdir -p …")`. Start your receiver; compute the gateway-reachable base URL.
2. **Launch with the extended hook set** — create the agent tab-less (`bridge.create(name, cwd=diag, show=False)`) configured so its Claude Code settings register your candidate events pointing at your receiver URL. Reuse the driver's hook-settings builder where you can (extend `_build_hook_settings`'s event list rather than reinventing the settings JSON), or write the minimal settings your spike needs. `bridge.wait_idle(name, …)`.
3. **Drive a turn that crosses boundaries** — send a prompt that makes at least one **tool call** (e.g. asks the agent to read/write a file in the diag dir) so `PreToolUse`/`PostToolUse` fire, and ideally triggers a **permission prompt** so any permission-related event fires. `wait_idle`.
4. **(Optional) change mode and re-drive** — if item #1's `BTab` cycle is available, cycle the permission mode once and drive another tool call, to check whether the payload's `permission_mode` reflects the change.
5. **Read back the captured payloads (the crux — §5)** — inspect your receiver's recorded list: which events arrived, in what order, with what timing, and — for each — whether `permission_mode` and the current tool are present and correct.

Log at DEBUG (`logging.getLogger(__name__)`) the full list of received events + a compact table of `event → has_permission_mode → has_tool → ts` — full detail to `tests/log/`, console concise.

---

## 5. The read-back is the crux

Registering a hook and receiving *something* is easy — the finisher already proves a hook round-trips. **The entire value of this spike is inspecting the payload contents.** Name the observables and assert on them:

- **Primary observable — `permission_mode` on the payload.** For each tool/turn event received, does `body.get("permission_mode")` (or the documented field name — confirm it) exist and hold a sane value (`default` / `plan` / `acceptEdits` / `bypassPermissions`)? If it is **absent**, that is the single most important finding: the "live mode for free" claim does **not** hold on this build, and the push channel cannot replace mode-reading — record it precisely.
- **Secondary — event coverage & naming.** Which of the candidate events actually fired? Explicitly record which candidate names produced **no** POST (i.e. are not real events on this CLI build) — that shrinks the "exact event set worth registering" question research-14 asks.
- **Tertiary — ordering / dedup.** Note any out-of-order or duplicate arrivals and the inter-event latency you measured. Even a single-agent observation informs the "sequence-number / arbiter needed?" design question.
- **Do not assert on "a POST arrived."** That proves transport, which is already known. Assert on the **fields**, or record their absence as the finding.

---

## 6. Two honest exits (spike-or-omit)

- **WORKS** — the extended hook set fires and the payloads carry `permission_mode` (+ the tool) reliably. Keep `tests/test_hook_event_stream_live.py` as a durable live test asserting the payload fields. Add a module-docstring note of: which events are real on this build, whether `permission_mode` is present per-event, and any ordering/dedup observation. This is the empirical evidence the research-14 decision needs to recommend **replace-vs-run-alongside**; note it explicitly for the research consumer.
- **PARTIAL / NEGATIVE AFTER A REAL ATTEMPT** — hooks fire but `permission_mode` is absent (or only some candidate events exist). Do **NOT** fabricate a green. Keep the file recording the *observed* payload shape (e.g. an assertion on what IS present + an `xfail`/skip carrying the "no `permission_mode` on payload" finding), write it up, and feed it back to the research-14 decision (the push channel augments but cannot *replace* screen-polling for mode). If the whole approach proves unworkable on this build, propose the §14 fallback (screen-polling stays primary) — but "impossible" requires this **actual live attempt**, never a code re-read.

---

## 7. Isolation rules (parallel-safe — CRITICAL: reproduce these in the file header/comments)

Sibling agents may be running their own live bridge sessions at the same time. Violating any of these can kill their work.

- **ONE new file only** — `tests/test_hook_event_stream_live.py`. Do not touch any other test file.
- **Uniquely-named tmux session** — prefix with the slug: `hookstream-<uuid8>`. Never a fixed/shared name.
- **Bind your receiver to an ephemeral/unique port** so two sibling spikes don't collide on a fixed port. Shut the receiver down in teardown.
- **NEVER call `tmux kill-server`** (directly or via any helper) in teardown — it kills *every* agent's sessions.
- **Run ONLY your own new test** in isolation — not the whole live tier.
- **Do NOT edit shared files** — `tests/conftest.py`, `pyproject.toml`, `tests/README.md`, and **do not add persistent hook registrations to the real running sidecar's config**. If you think you need a new fixture, marker, pythonpath tidy, or a sidecar-config change, **STOP and report it to the human** instead of editing a shared file.
- **The non-obvious trap:** the finisher leans on conftest's session-scoped **`bridge` fixture**, whose **setup AND teardown both call `_kill_all_tmux()` (= `tmux kill-server`)**. Fine for a human running one file alone; it **would kill sibling agents' live sessions**. So **instantiate your OWN `TmuxBridge()`** in your module (for WSL `mkdir`/`rm` via `_run`, and for `create`/`keys`/`send`/`read_log`/`wait_idle`/driving), and in teardown remove **ONLY** your own uniquely-named session via `bridge.close(name)` and your own throwaway dir. Never a broad kill.

---

## 8. Definition of done

- Run your **single** new test through the repo venv and paste the **actual** pytest result line — no paraphrase (the terminal `= N passed =` / `= N xfailed =` line, and/or `tests/log/results_latest.txt`):

  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\test_hook_event_stream_live.py -m integration
  # or:  tests\run.ps1 tests\test_hook_event_stream_live.py -m integration
  ```

  (Create the venv first if missing: `python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt`.)
- Whichever exit you land on (WORKS or partial/negative), the pasted result line must reflect the **real** run, and your report must state — explicitly, for the research-14 consumer — whether the payload carries `permission_mode`, which candidate events are real on this build, and any ordering/dedup note.
- Nothing here renders a UI, so the CLAUDE.md "Verifying UI changes" browser pass does not apply.
- **DEVLOG the change** before you finish — append a new dated entry at the bottom of `DEVLOG.md` (what the spike found, files added), per the CLAUDE.md DEVLOG rule.

---

## 9. Guardrails (from CLAUDE.md — reproduce, do not skip)

- **Never create a git branch.** Work on `main`. Do not run `git checkout -b` / `switch -c` / `branch <name>` / `worktree add` — these are gated and will prompt; if one prompts, **stop**. Committing to `main` is fine (but the orchestrator handles git here — do not commit unless told).
- **Bridge sessions stay TAB-LESS.** Create with `show=False`; **never** pass `show=True` and **never** call `show()`. An auto-popped Windows Terminal tab steals the user's focus mid-task.
- **Scratch artifacts go to `.scratch/`** — never the repo root or other project folders. Per-run DEBUG detail goes to `tests/log/` (gitignored) via `logging.getLogger(__name__)`.
- **pytest is the standard** — no ad-hoc scripts. Tag this live test `@pytest.mark.integration` + `@pytest.mark.slow` (module-level `pytestmark`).
