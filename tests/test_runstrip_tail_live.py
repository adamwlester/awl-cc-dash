r"""§10 item #7 tail spike — "Real run-strip completion %: open tail only".

Probes ONLY the open tail of §10 item 7: does ANY engine-side progress signal
exist — beyond the agent's self-reported checklist — that yields a *trustworthy*
completion measure (a real numerator AND denominator)? The checklist floor is
already unit-proven (``test_checklist_unit``, 19 cases) and ships — it is NOT
retested here.

Mechanism (per §7.10 and §10 item 7): the shipped model is "agent self-report
with the barber-pole floor"; the engine emits no progress signal. The candidate
engine-side signals live in ``drivers.bridge.derive_context_usage`` —
``work_steps`` / ``tool_total`` / ``tools`` / ``turns`` — plus any structured
todo-tool (``TodoWrite``) event. Research Q3 item 3 (deterministic transcript
overlay: tool_use ids minus tool_result ids) proves only busy-vs-idle, NOT a
completion fraction.

Hypothesis (the expected honest negative): no trustworthy engine-side progress
*fraction* exists. ``derive_context_usage`` yields NUMERATORS (steps taken) with
no knowable DENOMINATOR (total steps a run will need — unknowable mid-run); a
``TodoWrite`` list (if it fires at all) carries a done/total but is still the
agent CHOOSING to self-report, exactly like the markdown checklist — not the
engine-emitted ground truth the item asks for. Expected verdict: confirm the
§10 Fallback (checklist self-report + barber-pole floor) as the final model.

Read-back (the crux): run a genuine multi-tool task that publishes NO checklist,
then read the transcript back and ask — is there a trustworthy progress FRACTION
the engine gave us that we did not have to ask the agent for? The measurement is
``derive_context_usage(read_log(slug))`` plus a raw-entry scan for a TodoWrite
tool_use, asserted for the numerator-only shape (real counts, no denominator
field), and a sanity check that the shipped checklist floor stays barber-pole
indeterminate when no checklist is published.

Isolation rules (parallel-safe — CRITICAL; other agents may run live sessions):
  * ONE new file only — this one.
  * Every tmux session + WSL throwaway dir is uniquely named (``runstrip-tail-<hex>``).
  * NEVER ``tmux kill-server`` — teardown removes ONLY this test's own session
    (``bridge.close(slug)``) and its own dir, in a try/finally. We instantiate
    our OWN ``TmuxBridge()`` rather than depend on conftest's session-scoped
    ``bridge`` fixture, whose setup AND teardown both ``tmux kill-server``.
  * Sessions are TAB-LESS: ``create(...)`` with ``show`` defaulting False; never
    ``show=True`` / ``show()``.

Run::

    .\.venv\Scripts\python.exe -m pytest tests\test_runstrip_tail_live.py -m integration
"""

import logging
import sys
import time
import uuid
from pathlib import Path

import pytest

# The tmux bridge package lives at the repo root (`bridge/`); the sidecar's
# modules import as top-level from `sidecar/`. Put both on sys.path (mirrors the
# finisher's shim).
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SIDECAR = _REPO_ROOT / "sidecar"
for p in (str(_REPO_ROOT), str(_SIDECAR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from bridge import TmuxBridge  # noqa: E402
from drivers.bridge import derive_context_usage  # noqa: E402
import checklist  # noqa: E402  (sidecar/checklist.py — the shipped floor parser)

log = logging.getLogger("tests.runstrip_tail")

pytestmark = [pytest.mark.integration, pytest.mark.slow]

# The exact shape derive_context_usage returns. Pinning it is the decisive
# negative assertion: of these fields, work_steps/tool_total/turns/tools are
# NUMERATORS (counts so far) and tokens/window/percent are CONTEXT-token metrics
# — NONE is a work-completion denominator, so no trustworthy progress fraction is
# derivable. If a future build adds a denominator field, this test flags it (the
# WORKS case to investigate).
_USAGE_KEYS = {
    "tokens", "window", "model", "percent", "turns",
    "work_steps", "tools", "tool_total",
}


def _text_of(entry):
    msg = entry.get("message") or {}
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        buf = []
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text":
                buf.append(b.get("text") or "")
            elif isinstance(b, str):
                buf.append(b)
        return "\n".join(buf)
    return ""


def _assistant_texts(entries):
    return [
        _text_of(e)
        for e in entries
        if e.get("type") == "assistant" and not e.get("isSidechain")
    ]


def _safe_read_log(bridge, name):
    try:
        return bridge.read_log(name)
    except Exception:
        return []


def _wait_for_marker(bridge, name, marker, timeout=180, interval=1.0):
    """Poll the transcript for `marker` in an assistant entry; approve any stray
    permission prompt by pressing Enter along the way. Returns True on found."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            st = bridge.status(name)["state"]
        except Exception:
            st = "unknown"
        if st == "permission_prompt":
            bridge.keys(name, "Enter")   # approve (belt-and-suspenders)
            time.sleep(1.0)
            continue
        if any(marker in t for t in _assistant_texts(_safe_read_log(bridge, name))):
            return True
        time.sleep(interval)
    return any(marker in t for t in _assistant_texts(_safe_read_log(bridge, name)))


def test_runstrip_completion_no_engine_progress_fraction():
    """Live probe: a genuine multi-tool run publishing NO checklist yields real
    engine NUMERATORS (work_steps / tool_total) but NO engine denominator, so no
    trustworthy completion fraction exists — the checklist + barber-pole floor is
    the honest model (§10 item 7 Fallback)."""
    bridge = TmuxBridge()
    slug = f"runstrip-tail-{uuid.uuid4().hex[:8]}"
    diag = f"/home/lester/awl-{slug}"
    bridge._run(f"mkdir -p {diag}")
    try:
        # acceptEdits so the three Write calls auto-accept (a clean multi-tool
        # transcript without permission friction). show defaults False (tab-less).
        info = bridge.create(name=slug, cwd=diag, permission_mode="acceptEdits")
        log.debug("created session %s: %s", slug, info)

        # Genuine multi-step task, WITHOUT requesting a checklist — so we see
        # what the engine emits on its own.
        prompt = (
            "Create three files a.txt, b.txt, and c.txt in the current "
            "directory, each containing only its own letter (a, b, c "
            "respectively), using THREE separate Write tool calls, one per "
            "file. Do not print a checklist or any progress list. When done, "
            "reply with exactly DONE_TAIL."
        )
        bridge.send(slug, prompt)

        done = _wait_for_marker(bridge, slug, "DONE_TAIL", timeout=180)
        try:
            bridge.wait_idle(slug, timeout=30)
        except Exception as e:
            log.debug("wait_idle after task: %s", e)

        # --- READ THE STATE BACK (the measurement) --------------------------
        entries = bridge.read_log(slug)
        usage = derive_context_usage(entries)
        # Raw-entry scan for a TodoWrite-style tool_use carrying per-item state.
        todo_uses = [
            b for e in entries if e.get("type") == "assistant"
            for b in ((e.get("message") or {}).get("content") or [])
            if isinstance(b, dict) and b.get("type") == "tool_use"
            and "todo" in str(b.get("name", "")).lower()
        ]
        a_texts = _assistant_texts(entries)
        cl = checklist.parse_checklist(a_texts)  # shipped floor parser
        files = {
            f: bridge._run(f"cat {diag}/{f} 2>/dev/null || echo __MISSING__")
            for f in ("a.txt", "b.txt", "c.txt")
        }

        log.debug("DONE_TAIL reached=%s files=%s", done, files)
        log.debug(
            "usage: work_steps=%s tool_total=%s tools=%s turns=%s "
            "tokens=%s window=%s percent=%s model=%s",
            usage.get("work_steps"), usage.get("tool_total"), usage.get("tools"),
            usage.get("turns"), usage.get("tokens"), usage.get("window"),
            usage.get("percent"), usage.get("model"),
        )
        log.debug("usage keys: %s", sorted(usage))
        log.debug(
            "TodoWrite tool_uses: %s (classified as SELF-REPORT, not engine truth)",
            [b.get("name") for b in todo_uses],
        )
        log.debug("checklist floor: %s", cl)

        # --- Assertions (the honest negative — item 7's expected outcome) ----
        # A genuine multi-tool run actually happened (real engine numerators):
        assert done, (
            "agent never reported DONE_TAIL — the multi-step task did not "
            "complete; inspect the transcript/screen in tests/log"
        )
        assert usage["tool_total"] >= 3, (
            "expected >= 3 tool_use blocks (three Write calls) — the run must "
            "produce a real multi-tool transcript; got tool_total=%s tools=%s"
            % (usage["tool_total"], usage["tools"])
        )
        assert usage["work_steps"] >= 1, (
            "expected >= 1 engine work-step; got %s" % usage["work_steps"]
        )

        # The decisive negative: derive_context_usage exposes ONLY numerators
        # (work_steps / tool_total / turns / tools) plus CONTEXT-token metrics
        # (tokens / window / percent) — and NO work-completion denominator. The
        # exact shape is pinned so a future engine denominator would flag here
        # as the WORKS case to investigate.
        assert set(usage) == _USAGE_KEYS, (
            "derive_context_usage shape changed (symmetric diff %s). If a new "
            "field yields a total-work-steps DENOMINATOR, that is the WORKS "
            "exit — a trustworthy engine progress fraction may now exist; "
            "flip this test to assert on it and flag §10 item 7 for upgrade."
            % (set(usage) ^ _USAGE_KEYS)
        )
        # 'percent' is % of CONTEXT TOKENS used, categorically not % of work
        # done — it is a pure function of tokens/window with no work-step term,
        # so it cannot serve as a run-strip completion measure.
        expected_ctx_pct = (
            round(usage["tokens"] / usage["window"] * 100, 2)
            if usage["window"] else 0.0
        )
        assert usage["percent"] == expected_ctx_pct, (
            "the only percentage derive_context_usage yields is CONTEXT-token "
            "usage (tokens/window), not work completion — 'percent' cannot "
            "serve as a run-strip progress fraction"
        )

        # A TodoWrite list (if any fired) is agent SELF-REPORT, not engine
        # ground truth (§3 nuance) — it does not create an engine denominator.
        # Record it; do not fail on either presence or absence.
        if todo_uses:
            log.debug(
                "NOTE: %d TodoWrite tool_use(s) fired — a done/total *self-report* "
                "channel, NOT the engine-emitted ground truth item 7 asks for.",
                len(todo_uses),
            )

        # The shipped floor holds: a run that published NO checklist yields the
        # honest barber-pole indeterminate sentinel — never a fabricated %.
        assert cl["indeterminate"] is True and cl["total"] == 0 \
            and cl["done"] == 0 and cl["fraction"] == 0.0, (
            "checklist floor is not barber-pole-indeterminate for a run that "
            "published no checklist: %s (did the agent print a progress list "
            "despite instructions? inspect the transcript)" % cl
        )
    finally:
        try:
            bridge.close(slug)  # our session only — NEVER kill-server
        except Exception as e:
            log.debug("close(%s): %s", slug, e)
        try:
            bridge._run(f"rm -rf {diag}")
        except Exception as e:
            log.debug("rm -rf %s: %s", diag, e)
