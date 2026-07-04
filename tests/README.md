# Tests

The pytest suite for **awl-cc-dash**. It is the most trustworthy record of *what
the backend actually does* — more current than the docs, and unlike them it is
**executable**. When a doc and a test disagree, trust the test.

Two things this suite does **not** cover — treat them as unproven until they are:
the **Electron/React frontend** (no *component* tests — one live contract spike
aside, see below) and the **live bridge behavior** unless you deliberately run the
integration tier (below).

---

## The two tiers (the mental model)

Every test file is one of two kinds. Know which you are running.

| Tier | Marker | Needs | Speed | Default run? |
|------|--------|-------|-------|--------------|
| **Hermetic unit** | *(none)* | nothing — pure Python, no I/O, no network, no WSL | ~2s for the whole tier | ✅ yes |
| **Live / integration** | `integration`, `slow` | real **WSL2 + tmux + a Claude Code TUI** on this laptop | minutes (TUI startup, live model turns) | ⏸️ opt-in |

The hermetic tier is the everyday safety net: run it constantly, it should always
be green. The live tier is the *end-to-end* proof that the tmux bridge still drives
a real agent — run it deliberately (it spawns detached tmux sessions in WSL2; no
terminal windows pop, per the bridge-sessions rule in `CLAUDE.md`).

---

## Coverage map — file → what it pins down

Case counts are indicative (they drift as tests are added); the **mapping** is the
durable part. Keep this table current when you add/remove/rename test files (see
**Maintenance** below).

### Hermetic unit tier (default)

| File | Pins down (module under test) | ~cases |
|------|-------------------------------|:-----:|
| `test_bridge_unit.py` | `bridge/` pkg (screen-state detection, context-usage & turn derivation, transcript parsing) + `sidecar/drivers/base.py` + `sidecar/drivers/bridge.py` (non-live paths) + `sidecar/runtime_store.py` | ~88 |
| `test_sidecar_unit.py` | `sidecar/main.py` endpoints + driver wiring + `identity.py` + hookbus/links/eventbus integration | ~41 |
| `test_settings_io_unit.py` | `settings_io.py` (settings read/write) | ~35 |
| `test_marquee_unit.py` | `marquee.py` (transcript tail marquee) | ~25 |
| `test_library_unit.py` | `library.py` (doc/plan render, deferrals) | ~25 |
| `test_checklist_unit.py` | `checklist.py` (run-strip completion parser + barber-pole floor) | ~19 |
| `test_watermark_unit.py` | `watermark.py` (read-watermark deltas) | ~17 |
| `test_templates_store_unit.py` | `templates_store.py` (prompt templates, placeholder extraction) | ~17 |
| `test_deletion_unit.py` | `deletion.py` (retire/delete modeling) | ~17 |
| `test_console_catalog_unit.py` | `console_catalog.py` (console command catalog) | ~17 |
| `test_eventbus_unit.py` | `eventbus.py` (merged SSE event bus) | ~16 |
| `test_inbox_unit.py` | `inbox.py` (dispositions / inbox) | ~15 |
| `test_storage_unit.py` | `storage.py` (on-disk store) | ~14 |
| `test_subagents_naming_unit.py` | `subagents_naming.py` (subagent identity/naming) | ~13 |
| `test_hookbus_unit.py` | `hookbus.py` (hook-boundary Inject, hook delivery) | ~12 |
| `test_links_unit.py` | `links.py` (link edges/persistence) | ~10 |
| `test_scratchpad_unit.py` | `scratchpad.py` (+ `watermark.py`) | ~8 |
| `test_utility_llm_unit.py` | `utility_llm.py` (Revise/Summarize passes) | ~6 |

Each unit file opens with a docstring stating the **authoritative decided behavior**
it encodes — read that docstring first; it is the spec.

### Live / integration tier (opt-in)

| File | Pins down | ~cases |
|------|-----------|:-----:|
| `test_tmux_bridge.py` | The `bridge` package control surface end-to-end: create/send/keys/read/list/rename/resume/status/batch/broadcast/interrupt/scrollback/watch/wait_idle/export/show/set_cwd/set_model/mcp_sync/read_log | ~29 |
| `test_bridge_finisher_live.py` | The bridge **driver** behaviors the product leans on: **permission approve/deny**, **resume-after-restart**, **model + effort take** | ~4 |

### Feasibility spikes (opt-in, live) — engine-capability evidence

One-shot **engine-feasibility probes** (built 2026-07-02, verified against commit
`af4964d`), each answering an open question in `docs/ARCHITECTURE.md` §10: *can the
real Claude Code engine, via the bridge, actually do X?* They live in the live tier
(they need WSL2 + tmux + a real TUI, and carry the `integration`+`slow` markers, so
the hermetic run deselects them) but differ in **purpose** from the standing suite
above — they generate **evidence**, not regression protection: run one to *settle a
question*, not on every change. Each file's module docstring states the decided
behavior; the `Verdict` here is the one-line summary, and the run records are in
`tests/log/`. The full findings + their doc consequences are folded into
`ARCHITECTURE.md` §10 (the open questions these answer).

| File | Probes: can the engine… | Verdict |
|------|-------------------------|---------|
| `test_rewind_handoff_live.py` | …rewind a session to an earlier point **and** fork/handoff a new agent from a point? | ✅ FEASIBLE (both) |
| `test_permission_mode_cycle_live.py` | …change permission mode mid-run (Shift+Tab) and actually suppress prompts? | ✅ FEASIBLE |
| `test_plan_decision_hooks_live.py` | …surface `ExitPlanMode`/`AskUserQuestion` as inbox cards, then resume the agent? | ✅ FEASIBLE |
| `test_thinking_toggle_live.py` | …toggle extended-thinking on a running agent and read it back? | ✅ FEASIBLE (via the modal panel) |
| `test_context_compact_live.py` | …parse `/context` by category and detect `/compact` boundaries? | ✅ FEASIBLE |
| `test_per_agent_cost_live.py` | …report a real per-agent $ cost (via `/cost`)? | ✅ FEASIBLE (overturns the "honest blank" assumption) |
| `test_subagent_status_live.py` | …tell a subagent is active vs. quiet from its own transcript? | ✅ FEASIBLE |
| `test_hook_event_stream_live.py` | …get live run-state (permission_mode + tool) from hook payloads? | ✅ FEASIBLE (caveats: Notification lacks it; concurrent-load untested) |
| `test_bypass_auto_preconditions_live.py` | …reach the Bypass/Auto permission segments given how the agent was launched? | ✅ FEASIBLE (bypass is silently absent if not pre-armed) |
| `test_usage_context_sources_live.py` | …read mid-run context + account/usage from local sources? | ✅ FEASIBLE (data-boundaries only; live % is screen-scrape) |
| `test_console_mirror_live.py` | …passthrough keystrokes and recover ANSI from the console pane? | ✅ FEASIBLE (faithful xterm rendering = a frontend job) |
| `test_oneclick_launch_live.py` | …have the app own the sidecar lifecycle without killing agents? | ✅ FEASIBLE (modeled in Python; real Electron POC still owed) |
| `tests/ui/test_ui_slice_live.py` | …drive the whole live loop from a browser speaking only `api.ts`? | ✅ FEASIBLE |
| `test_system_fault_harvest_live.py` | …read machine signals for System faults (rate/usage cap, auth, MCP)? | ⚠ PARTIAL — MCP + auth OK; **usage-cap wording not matched** |
| `test_console_clear_transcript_live.py` | …survive a Console `/clear` without orphaning the transcript? | ⚠ HAZARD — `/clear` **orphans** new turns (`/compact` is safe) |
| `test_polling_scale_ceiling_live.py` | …scale the ~1s per-agent poll to a fleet? | ⚠ FEASIBLE test, bad curve — **degrades from N=1** (needs rework) |
| `test_fast_mode_toggle_live.py` | …toggle Fast/Opus mode live? | 🚫 OMITTED — account credit-gated (lands `xfail`) |

### Support files

| Path | Purpose |
|------|---------|
| `conftest.py` | Shared fixtures (`bridge`, `live_session`) + per-run timestamped DEBUG log setup. Adds the repo root to `sys.path`. |
| `run.ps1` | Convenience runner — resolves the local `.venv` and passes all args through to pytest. |
| `log/` | Per-run artifacts (gitignored): timestamped DEBUG logs (`tmux_bridge_*.log`, pruned to the newest 20) **and** durable results records (`results_*.xml` JUnit + `results_*.txt` summary + `results_latest.txt`). |

---

## What is established vs not

**Established (green hermetic unit tests, verified current):** the sidecar feature
modules and the bridge's non-live logic — the whole list in the unit table above.
These import the *real* modules (`sys.path → sidecar/`, bare `import <module>`), so a
green run means the current code satisfies the encoded contract.

**Established only when the live tier is run:** the tmux bridge end-to-end — session
control, permission round-trips, resume, model/effort. Green by default means
*nothing* about the live bridge; run the integration tier to confirm it.

**Not established anywhere (known gaps — do not assume these work):**

- 🔴 **Frontend (Electron/React).** No *component* tests exist. This is the "barely
  functional" layer; it has no automated safety net. *(One live spike,
  `tests/ui/test_ui_slice_live.py`, now proves a browser speaking the `api.ts`
  contract can drive the full loop end-to-end — but the React components themselves
  remain untested.)*
- 🟡 **`sidecar/serialize.py`** — the driver→event normalization *seam*. No dedicated
  test.
- 🟡 **`sidecar/runtime_store.py`** — exercised only incidentally via the bridge unit
  test; no dedicated coverage.
- 🟡 **`sidecar/drivers/sdk.py`** — the limited-use SDK engine. No test.

---

## Running

Uses a repo-root `.venv`. Create it once if missing:

```powershell
python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt
```

Then:

```powershell
# Hermetic unit tier only — the everyday run (fast, no WSL needed):
tests\run.ps1 -m "not integration and not slow"

# Everything, including the live tier (needs WSL2 + tmux + Claude Code):
tests\run.ps1

# Just the live tier:
tests\run.ps1 -m "integration or slow"

# A single test by keyword:
tests\run.ps1 -k mcp_sync
```

Equivalent direct invocation (bypasses run.ps1):

```powershell
.\.venv\Scripts\python.exe -m pytest tests\ -m "not integration and not slow"
```

> ⚠️ Plain `tests\run.ps1` runs **everything**, including the live tier, which will
> try to spawn real WSL2/tmux sessions. On a machine without WSL those tests fail
> (not because the code is broken). Use the `-m "not integration and not slow"`
> filter for a clean hermetic run.

No `testpaths` is configured — pass the path you want.

---

## Results records & where to look when something fails

Every run writes durable artifacts into `tests/log/` (all gitignored), so "did it
pass?" is answered by a **file**, not by scrollback or an agent's paste:

- **`results_<stamp>.txt`** (+ **`results_latest.txt`**) — human-readable record:
  PASS/FAIL, counts (incl. skipped/deselected), duration, **the git commit it was
  verified against**, the tier (hermetic vs live), the selection (`-m`/`-k`), Python
  version, and — for live runs — the WSL distro + Claude Code CLI version. Any
  failures are listed with a one-line reason.
- **`results_<stamp>.xml`** — JUnit XML, the machine-readable equivalent (per-test
  pass/fail/skip + timing) for tooling.
- **`tmux_bridge_<stamp>.log`** — the verbose DEBUG story for *diagnosing* a failure:
  exact WSL/tmux commands, raw screen captures, detected states, tracebacks. Bulky,
  so only the newest 20 are kept; the small results records are never pruned.

The results record's `Commit:` field carries `-dirty` when the tree had uncommitted
changes at run time — a sha alone doesn't fully capture what was tested. The durable,
**committed** "what's verified" ledger lives in `DEVLOG.md` and the `ARCHITECTURE.md
§10` evidence citations; these per-run files are the raw evidence that feeds it.

---

## Conventions (apply to all new tests)

- **Framework:** pytest. Put tests in a `tests/` dir at the relevant scope.
- **Hermetic by default:** a new test should need nothing external. If it touches
  WSL/tmux/network/a live TUI, tag it `@pytest.mark.integration` (and
  `@pytest.mark.slow` if it takes many seconds), module-level `pytestmark = [...]`
  is fine — see the two live files.
- **State the contract:** open each file with a docstring naming the *decided
  behavior* it encodes, so the test doubles as a spec.
- **Logging:** use `logging.getLogger(__name__)`; DEBUG goes to the per-run log file
  automatically. Log the raw inputs/outputs you'd want when diagnosing a failure.
- **Fixtures over implicit order:** share expensive setup (like a live session) via
  session-scoped fixtures (`conftest.py`), not cross-test side effects.
- **Markers** are declared in `pyproject.toml` (`integration`, `slow`).

---

## Maintenance

This README is a **durable map, not a run snapshot** — do not paste pass/fail counts
as its headline (they rot). When you **add, remove, or rename a test file**, or when
a **coverage gap closes or opens**, update:

1. the **Coverage map** table (file → module → tier), and
2. the **What is established vs not** section (especially the 🔴/🟡 gaps list).

A test-suite change that leaves this README stale is unfinished.
