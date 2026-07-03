# Build prompt — Run-strip completion %: engine-signal open-tail spike

## 1. Header

- **Test working name:** `runstrip-tail` (engine-progress-signal spike)
- **§10 item:** **#7 — Real run-strip completion % — open tail only — ◐ partially proven** (docs/ARCHITECTURE.md §10, "Priority — Medium", item **7**).
- **Goal:** Spike **ONLY the open tail** of item #7: does **any engine-side progress signal** exist — beyond the agent's self-reported checklist — that yields a *trustworthy* completion measure (a real numerator **and** denominator)? Do **NOT** retest the checklist floor; it is already unit-proven and ships.

This is a **lightweight, low-priority tail spike**. One real live session, read the transcript back, inspect for a genuine engine progress signal, and report a verdict. A well-supported honest "no engine progress signal exists" is a **valid, expected outcome** — not a failure.

---

## 2. Read first (open these before writing a line)

- **Its §10 item:** `docs/ARCHITECTURE.md` §10, **item 7** ("Real run-strip completion %", lines ~1128–1137) — and the panel it feeds, **§7.10 "Run-strip, checklist & marquee"** (lines ~576–584). The §10 item is the authority; read the exact wording of its four bullets there (reproduced in §3 below).
- **Research pointer:** `dev/notes/research/claude-code-mode-control-research.md` → **Question 3**, item **3 "Deterministic transcript overlay"** (line ~104). This is the *only* lightly-relevant lever: tail the JSONL, collect `tool_use` ids minus `tool_result` ids. It proves *busy-vs-idle*, **not** a completion fraction — note that distinction.
- **THE pattern to copy:** `tests/test_bridge_finisher_live.py` — copy its **shape** (module-level `pytestmark`, throwaway WSL dir fixture, `asyncio.run(flow())` bodies, driving the driver/bridge directly with no HTTP layer). See §7 for the isolation caveat about its `bridge` fixture.
- **Modules this test touches (read them):**
  - `sidecar/checklist.py` — the shipped self-report parser (`parse_checklist`, `barber_pole`). **Read it to understand what already ships — then leave it alone.** Its unit proof is `tests/test_checklist_unit.py` (19 cases). **Do NOT retest it.**
  - `sidecar/main.py` — `GET /sessions/{id}/checklist` (line ~1228) and `_assistant_texts()` (line ~1208): how the shipped strip is fed.
  - `sidecar/drivers/bridge.py` — **`derive_context_usage(entries)`** (line ~103), a pure function importable as `from drivers.bridge import derive_context_usage`. It returns `work_steps`, `tools`, `tool_total`, `turns` — the **candidate engine-side signals** this spike probes.
  - `bridge/bridge.py` — `read_log(name, last_n=None, types=None)` (line ~960): parses the JSONL transcript into entry dicts (the input `derive_context_usage` expects). Also `create`, `send`, `wait_idle`, `close`, `_run`.

---

## 3. Mechanism / hypothesis

The shipped model (per §7.10 and §10 item 7) is **"agent self-report with barber-pole as the floor"**: a checklist the agent publishes in prose is parsed to `done ÷ total`; **no checklist → honest barber-pole indeterminate, never a fabricated %**. The engine itself **emits no progress signal**.

The §10 item's four bullets (read the real §10 for exact wording):
1. **Desired:** the run-strip shows a genuine completion percentage for *every* run.
2. **Blocker:** the engine emits no progress signal; the only honest source is the self-reported checklist, and without one the strip is barber-pole indeterminate.
3. **Research/POC must establish:** whether any **engine-side signal (transcript structure, todo-tool events)** yields a *trustworthy* progress measure **beyond** the checklist mandate.
4. **Fallback:** checklist self-report with the barber-pole floor is the **final** model.

**Candidate engine-side signals to probe (from the item + `derive_context_usage`):**
- **`work_steps` / `tool_total` / `tools`** — real, engine-derived counts from the transcript. But they are **numerator-only**: you can count steps *taken*, never the *total steps a run will need*. A percentage needs a denominator the engine never provides.
- **Todo-tool events (`TodoWrite`)** — if this Claude Code build emits a structured todo tool with per-item completion, that *would* carry a `done/total`. **But note the nuance:** a TodoWrite list is still the **agent choosing to self-report**, exactly like the markdown checklist — it is not an engine-emitted ground truth. So even a firing TodoWrite is *another self-report channel*, not the "genuine engine signal" the item asks for.
- **Transcript overlay (research Q3 item 3):** proves busy-vs-idle only; no fraction. Explicitly **not** a completion measure.

**Hypothesis:** No trustworthy engine-side progress *fraction* exists. `derive_context_usage` yields numerators with **no knowable denominator**; TodoWrite (if present at all) is self-report, not engine truth. **Expected verdict: the honest negative** — confirming the item's Fallback as the final model. The spike's job is to *prove that by a real attempt*, not by re-reading code.

**Cite in your writeup:** research Q3 item 3 (transcript overlay = busy/idle, not %), and §10 item 7 as the authority (engine emits no progress signal; checklist + barber-pole floor is the honest model).

---

## 4. Build this

Create **one** new file: `tests/test_runstrip_tail_live.py`.

- Module-level `pytestmark = [pytest.mark.integration, pytest.mark.slow]`.
- Mirror the finisher's import shim (put `sidecar/` on `sys.path`, then `from drivers.bridge import derive_context_usage`) and `from bridge import TmuxBridge`.
- **Do NOT depend on conftest's session-scoped `bridge` fixture** (see §7). Instantiate your **own** `TmuxBridge()` in the test module.

**Flow (single `async def flow()` run via `asyncio.run`, or a plain sync body — the bridge calls are sync; wrap blocking bridge calls with `asyncio.to_thread` if you go async):**

1. **Spawn** a tab-less, **uniquely-named** session:
   ```python
   slug = f"runstrip-tail-{uuid.uuid4().hex[:8]}"
   bridge = TmuxBridge()
   diag = f"/home/lester/awl-{slug}"
   bridge._run(f"mkdir -p {diag}")
   bridge.create(name=slug, cwd=diag)   # show defaults False — NEVER pass show=True
   ```
2. **Drive a genuine multi-step task WITHOUT requesting a checklist** — so we see what the engine emits on its own, e.g.:
   *"Create three files a.txt, b.txt, and c.txt, each containing only its own letter, using the Write tool. Do not print a checklist or any progress list. When done reply exactly DONE_TAIL."* Send with `bridge.send(slug, prompt)`. Approve any permission prompts by driving Enter with `bridge.keys(slug, "Enter")` in a short poll loop (or spawn the session in a permissive mode via `create(..., permission_mode="acceptEdits")` / `allowed_tools=["Write"]` — confirm the exact create kwarg names in `bridge/bridge.py` before using them). Keep it simple; the point is to generate a real multi-tool-use transcript.
3. **Wait** for the run to finish: `bridge.wait_idle(slug, timeout=...)`, and/or poll `read_log` until an assistant entry contains `DONE_TAIL`.
4. **READ THE STATE BACK** — this is the spike's measurement:
   ```python
   entries = bridge.read_log(slug)
   usage = derive_context_usage(entries)      # work_steps, tools, tool_total, turns
   # Scan raw entries for any todo-tool signal:
   todo_uses = [b for e in entries if e.get("type") == "assistant"
                for b in ((e.get("message") or {}).get("content") or [])
                if isinstance(b, dict) and b.get("type") == "tool_use"
                and "todo" in str(b.get("name", "")).lower()]
   ```
   Log `usage`, `tool_total`, and `todo_uses` at DEBUG so the finding is captured in `tests/log/`.
5. **Evaluate for a trustworthy progress measure:**
   - Is there any engine-emitted **denominator**? (`derive_context_usage` gives none — `work_steps`/`tool_total` are numerators only.)
   - Did any **TodoWrite**-style tool fire carrying `done/total`? If yes, note it — but classify it as **self-report**, not engine ground truth (see §3 nuance).
   - Confirm the checklist path is untouched: this run published no checklist, so `checklist.parse_checklist(...)` on these texts would return `barber_pole()` — you may assert that as a sanity check that the floor still holds, but **do not** re-exercise the parser's item-matching logic (that's `test_checklist_unit`'s job).
6. **Assert** per the verdict you reach (see §5/§6): either assert on the discovered engine signal (WORKS), or assert the honest negative (no engine-emitted denominator; `work_steps`/`tool_total` are numerator-only) and document it.

---

## 5. The read-back is the crux

Sending the task and watching files appear is trivial. **What proves or disproves item #7 is reading the transcript back and asking: is there a trustworthy progress *fraction* the engine gave us that we did not have to ask the agent for?**

- **Named observable:** from `derive_context_usage(read_log(slug))` — `work_steps`, `tool_total`, `tools`, `turns` — plus a raw-entry scan for a **`TodoWrite`-style `tool_use`** carrying per-item completion.
- **The test of "trustworthy":** a real completion % needs a **numerator AND a denominator**. The engine signals give a numerator (steps taken) with **no denominator** (total steps unknowable mid-run). A TodoWrite list *has* both but is **agent self-report**, not engine truth.
- **If no trustworthy engine-side measure is observable, that is a FINDING, not a pass.** Record exactly what the transcript *did* and *did not* contain. Do not paper over the absence with a green assertion on a numerator-only count dressed up as progress.

---

## 6. Two honest exits (spike-or-omit)

- **WORKS** — the live transcript reveals a genuine engine-side signal yielding a trustworthy `done/total` beyond the checklist (e.g. a `TodoWrite` tool that the item would accept as sufficient, or an engine-emitted denominator). Keep `test_runstrip_tail_live.py` as a **durable live test** asserting on that signal, and add a short note (in the test docstring + DEVLOG) of exactly what was found and where it lives in the transcript.
- **GENUINELY IMPOSSIBLE AFTER A REAL ATTEMPT** (the expected outcome) — after actually running the live session and inspecting the transcript, no trustworthy engine-side progress *fraction* exists (`derive_context_usage` is numerator-only; TodoWrite is self-report or absent). **Do NOT fabricate a green.** Keep the test as a durable **negative/finding** test that asserts the numerator-only nature (e.g. `usage` exposes counts but no denominator field), write up the findings in DEVLOG, and **propose closing the tail**: confirm the §10 Fallback ("checklist self-report with the barber-pole floor is the final model") as the settled answer and propose moving item #7 from ◐ partially-proven to a **Decided omission / resolved-as-fallback** in §10. "Impossible" requires this **actual live attempt** — never a code re-read no-op.

Either way, the deliverable is a real live run plus a clear verdict.

---

## 7. Isolation rules (parallel-safe — critical)

Reproduce these in the test file (docstring/comments) and obey them:

- **ONE new file only:** `tests/test_runstrip_tail_live.py`. Add nothing else.
- **Name tmux sessions uniquely** — prefix with the slug (`runstrip-tail-<hex>`). Never a fixed name.
- **NEVER call `tmux kill-server`** (directly or via any helper) in teardown — it kills sibling agents' live sessions.
- **Run ONLY your own new test in isolation** — never the whole live tier.
- **Do NOT edit `tests/conftest.py`, `pyproject.toml`, or `tests/README.md`.** If you think you need a shared change (new fixture, marker, or a pythonpath tidy), **STOP and report it to the human** — do not edit a shared file.
- **Non-obvious trap — do NOT reuse the finisher's `bridge` fixture:** the finisher leans on conftest's **session-scoped `bridge` fixture, whose setup AND teardown both call `_kill_all_tmux()` (= `tmux kill-server`)**. That is fine for a human running one file alone, but it would **kill sibling agents' live sessions** and breaks parallel-safety. So **instantiate your OWN `TmuxBridge()`** inside this test module for WSL shell helpers (`_run` mkdir/cat/rm) and for driving, and in teardown remove **ONLY your own uniquely-named session** via `bridge.close(slug)` and **only your own** throwaway dir via `bridge._run(f"rm -rf {diag}")`. Use `try/finally` so cleanup runs even on failure. If you believe you truly need the shared fixture or a new shared fixture/marker, **STOP and report to the human** rather than editing a shared file.

---

## 8. Definition of done

- Run your **single** new test through the repo venv and paste the **actual** pass/fail line verbatim (the pytest `= N passed =` / `= N failed =` line, and/or `tests/log/results_latest.txt`) — no paraphrase. Windows PowerShell:
  ```powershell
  .\.venv\Scripts\python.exe -m pytest tests\test_runstrip_tail_live.py -m integration
  # or: tests\run.ps1 tests\test_runstrip_tail_live.py -m integration
  ```
  (Create the venv first if missing: `python -m venv .venv; .\.venv\Scripts\python -m pip install -r requirements.txt`.)
- Include the **verdict** (WORKS vs. honest-negative) and, if negative, the concrete evidence from the transcript (what `derive_context_usage` returned, whether any TodoWrite fired) plus the proposed §10 disposition.
- This test renders nothing (no UI). If you happen to touch anything that renders, follow CLAUDE.md **"Verifying UI changes"** — otherwise not applicable.
- **DEVLOG the change** before finishing: append a dated entry (what the spike ran, the verdict, files touched).

---

## 9. Guardrails (from CLAUDE.md)

- **Never create a git branch.** All work stays on **`main`**. Do not run `git checkout -b` / `switch -c` / `branch <name>` / `worktree add` — they are gated and will prompt; if one prompts, **stop and ask**.
- **Bridge sessions stay TAB-LESS.** Never pass `show=True` to `create(...)` and never call `show()` — a tab must never open as a side effect. Sessions run detached and are read via `capture-pane` / `read_log`.
- **Scratch artifacts go to `.scratch/`** (gitignored) — never the repo root or other project folders. WSL throwaway dirs live under `/home/lester/awl-<slug>` and are `rm -rf`'d in teardown.
- **pytest is the standard** — no ad-hoc scripts. New test is `tests/test_runstrip_tail_live.py`, tagged `integration` + `slow`.
