r"""§10 item #4 tail spike — "True mid-run Inject: open tail only".

Probes ONLY the open tail of §10 item 4: is there ANY delivery point on a live
Claude Code TUI that gets a message to a *running* agent EARLIER than its next
hook boundary (``PostToolUse`` / ``Stop``), without corrupting the in-flight
turn? Hook-boundary Inject is already unit-proven (``test_hookbus_unit``,
``test_sidecar_unit``) and ships — it is NOT retested here.

The only other programmatic control surface on an interactive TUI is keystrokes
into the pane (research Q1 approach #8: no signal/env/IPC channel). So the whole
experiment reduces to: if you ``send-keys`` a marker into a pane whose agent is
actively generating (mid-turn, before any tool boundary), does the marker reach
the agent EARLIER than the next hook boundary — or does it merely sit in the
composer textarea and get submitted as the *next* prompt once the turn ends
(which is just Next/Queue), or corrupt the in-flight turn?

Hypothesis (research Q3 input-injection notes + the mandatory-idle-gating gotcha
at line 57): ``send-keys`` lands in the composer textarea, which the TUI does not
consume until the current turn finishes — so typeahead behaves as **Next**
(submitted after the turn), not immediate mid-turn delivery. Expected verdict:
no earlier safe point → the §10 Fallback (hook-boundary delivery + transparent
Next/Queue degrade) is the final model.

Decisive read-back (the crux, §5): the marker instruction, once submitted from
the composer, appears as a genuine ``user`` entry in the JSONL transcript — the
signature of an ordinary queued prompt (out-of-band hook injects are NEVER
written to the transcript; see ``sidecar/main.py`` send-inject comment). Combined
with the essay turn completing uncorrupted BEFORE that user entry, this proves
delivery-at/after-the-boundary, not earlier-than-boundary injection. If instead
the marker reached the agent (an assistant reaction) WITHOUT ever becoming a
``user`` entry, that would be a genuine earlier delivery point (WORKS) and this
test would be rewritten as a positive assertion on it.

Isolation rules (parallel-safe — CRITICAL; other agents may run live sessions):
  * ONE new file only — this one.
  * Every tmux session + WSL throwaway dir is uniquely named (``inject-tail-<uuid>``).
  * NEVER ``tmux kill-server`` — teardown removes ONLY this test's own session
    (``tb.close(name)``) and its own dir. We instantiate our OWN ``TmuxBridge()``
    rather than depend on conftest's session-scoped ``bridge`` fixture, whose
    setup AND teardown both call ``tmux kill-server`` (would kill siblings).
  * Sessions are TAB-LESS: ``create(..., show=False)``; never ``show=True`` / ``show()``.

Run::

    .\.venv\Scripts\python.exe -m pytest tests\test_inject_tail_live.py -m integration
"""

import logging
import sys
import time
import uuid
from pathlib import Path

import pytest

# The tmux bridge package lives at the repo root (`bridge/`); the sidecar's
# modules import as top-level from `sidecar/`. Put both on sys.path.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SIDECAR = _REPO_ROOT / "sidecar"
for p in (str(_REPO_ROOT), str(_SIDECAR)):
    if p not in sys.path:
        sys.path.insert(0, p)

from bridge import TmuxBridge  # noqa: E402

log = logging.getLogger("tests.inject_tail")

pytestmark = [pytest.mark.integration, pytest.mark.slow]


# --- read-back helpers -------------------------------------------------------

def _state(tb, name):
    try:
        return tb.status(name)["state"]
    except Exception:  # transient capture failure — treat as unknown
        return "unknown"


def _wait_state(tb, name, target, timeout, interval=0.5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _state(tb, name) == target:
            return True
        time.sleep(interval)
    return False


def _tight_wait_generating(tb, name, timeout, interval=0.1):
    """Detect the 'generating' state with a tight poll so we can act inside even
    a short window (the marker must be typed + Entered while still generating)."""
    return _wait_state(tb, name, "generating", timeout, interval=interval)


def _generating(tb, name, lines=45):
    """True if the agent is generating, read from a WIDE capture.

    ``status()`` keys off the bottom 15 lines, but once the marker is typed into
    the composer that composer text pushes the "✻ …" spinner line out of a
    15-line window, so ``status()`` mis-reads a still-generating agent as idle.
    A wider capture keeps the spinner in view, so this stays correct with text in
    the composer — which is exactly the state we probe."""
    try:
        content = tb.read(name, lines=lines)["content"]
        return tb._detect_state(content) == "generating"
    except Exception:
        return False


def _safe_read_log(tb, name):
    try:
        return tb.read_log(name)
    except Exception:
        return []


def _text_of(entry):
    """Flatten a transcript entry's message content to plain text."""
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


def _texts(entries, kind):
    return [
        _text_of(e)
        for e in entries
        if e.get("type") == kind and not e.get("isSidechain")
    ]


def _first_idx(entries, pred):
    for i, e in enumerate(entries):
        if pred(e):
            return i
    return None


# --- the spike ---------------------------------------------------------------

def test_mid_run_inject_open_tail():
    """Live probe: typeahead into a mid-generation pane is deferred to the next
    turn (Next/Queue), not delivered earlier than the hook boundary.

    Because the installed model's streaming speed varies ~50x run-to-run, we
    RETRY (fresh marker each attempt) until we catch a genuine mid-turn window:
      1. drive a long, tool-less generating turn (no tool boundary to rescue
         delivery early);
      2. type the marker WITHOUT Enter (it lands in the composer), then, still
         generating, press Enter to submit it;
      3. ACCEPT the attempt only once we positively observe the marker staying
         QUEUED (no user entry) and UN-REACTED-TO while the agent generates for
         >= HELD_SECS — that held-mid-turn state is itself the negative finding.
    Then watch the marker submit at the essay's boundary and be answered as an
    ordinary subsequent turn (marker_in_user, essay_before_marker_prompt).
    """
    tb = TmuxBridge()
    slug = uuid.uuid4().hex[:8]
    name = f"inject-tail-{slug}"
    path = f"/home/lester/inject-tail-{slug}"
    tb._run(f"mkdir -p {path}")
    try:
        info = tb.create(name, cwd=path, show=False)  # tab-less; never show=True
        log.debug("created session %s: %s", name, info)

        # A long, TOOL-LESS generating turn (no tool boundary can fire and
        # "rescue" delivery early). Output streaming speed varies ~50x run to
        # run, so essay length is not a reliable window lever — but EXTENDED
        # THINKING is: an "ultrathink" hard-reasoning prompt reliably keeps the
        # agent generating for tens of seconds (measured ~59s on this backend),
        # a huge margin over the ~1s it takes to type the marker and press Enter
        # while still generating. A few fresh-marker attempts (drained via
        # wait_idle between, so sends never pile into the message queue) suffice;
        # we accept an attempt only when we positively observe the typed marker
        # staying QUEUED (unsubmitted, un-reacted-to) while the agent generates —
        # which is itself the negative finding.
        essays = [
            "Ultrathink very hard and at great length, step by step, about "
            "whether mathematics is discovered or invented, exploring at least "
            "ten distinct angles in depth. Then write a detailed 1500-word "
            "essay on your conclusion. Do not use any tools.",
            "Ultrathink at great length, weighing many perspectives step by "
            "step, about what makes a human life meaningful. Then write a "
            "detailed 1500-word essay. Do not use any tools.",
            "Ultrathink very hard and at length about several of the hardest "
            "unsolved problems in mathematics, reasoning step by step through "
            "each. Then write a detailed 1500-word essay. Do not use any tools.",
        ]

        # --- Open a genuine mid-turn window and act inside it ----------------
        MAX_ATTEMPTS = 4          # extended thinking makes attempt 0 near-certain
        HELD_SECS = 3.0           # queued-during-generation dwell to accept
        MARKER = ""
        instruction = ""
        typeahead_in_composer = False
        marker_in_assistant_while_queued = True   # pessimistic default
        held_observed = False
        t_enter = None
        for attempt in range(MAX_ATTEMPTS):
            # Fresh marker so a missed attempt (essay ended, marker submitted at
            # idle) can never be confused with the accepted mid-turn attempt.
            MARKER = f"INJECT_TAIL_{uuid.uuid4().hex[:6]}"
            instruction = (
                f"If you can read this mid-turn, immediately stop and reply with "
                f"exactly {MARKER}"
            )

            # Start from a clean, idle composer (drains any stray prior marker).
            try:
                tb.wait_idle(name, timeout=90)
            except Exception:
                pass
            tb.keys(name, "C-u")

            tb.send(name, essays[attempt % len(essays)])
            if not _tight_wait_generating(tb, name, timeout=45):
                log.debug("attempt %d: essay never reached generating", attempt)
                continue

            # Confirm generating with an EMPTY composer (status is reliable here;
            # once we type the marker the composer text hides the spinner and
            # status falsely reads idle — see _generating). The ultrathink window
            # is ~tens of seconds, so this single check plus a prompt Enter keeps
            # us safely mid-turn without re-checking status while the composer is
            # occupied.
            if not _generating(tb, name):
                log.debug("attempt %d: not generating pre-type; retry", attempt)
                continue

            # Type the marker WITHOUT Enter — it lands in the composer.
            t_type = time.time()
            tb.send(name, instruction, press_enter=False)
            scr1 = tb.read(name, lines=60)["content"]
            in_composer = MARKER in scr1

            # Press Enter promptly to submit the composed marker mid-turn. We do
            # NOT re-check status between type and Enter: the occupied composer
            # would falsely read idle. The long window makes this Enter mid-turn
            # with near-certainty; the post-Enter probe below verifies it landed
            # mid-turn by observing the marker stay QUEUED during live generation.
            t_enter = time.time()
            tb.keys(name, "Enter")     # press Enter WHILE generating (the crux)

            # Verify the Enter landed mid-turn: probe that the marker stays
            # UNSUBMITTED (no user entry) AND the agent has NOT reacted to it,
            # while the essay is still generating, for >= HELD_SECS.
            held_start = None
            marker_reacted_while_queued = False
            probe_deadline = time.time() + 15
            while time.time() < probe_deadline:
                gen = _generating(tb, name)   # wide-window (see _generating)
                ents = _safe_read_log(tb, name)
                mu = any(MARKER in t for t in _texts(ents, "user"))
                ma = any(MARKER in t for t in _texts(ents, "assistant"))
                if gen and not mu:
                    if ma:
                        marker_reacted_while_queued = True  # WORKS signal
                    if held_start is None:
                        held_start = time.time()
                    elif time.time() - held_start >= HELD_SECS:
                        held_observed = True
                        break
                else:
                    # Essay ended (marker submitted) or state changed — this
                    # attempt didn't hold long enough; stop probing it.
                    break
                time.sleep(0.3)

            log.debug(
                "attempt %d: in_composer=%s held_observed=%s "
                "reacted_while_queued=%s (window %.1fs)",
                attempt, in_composer, held_observed,
                marker_reacted_while_queued, time.time() - t_type,
            )

            if held_observed:
                typeahead_in_composer = in_composer
                marker_in_assistant_while_queued = marker_reacted_while_queued
                break

            # Missed: clean up (the marker may have been submitted at idle; the
            # next loop's wait_idle drains it). Fresh marker next attempt.
            tb.keys(name, "C-u")

        # A valid experiment requires positively catching the marker QUEUED
        # during live generation. Failing that is an environment/speed blocker
        # (backend too fast across every attempt), NOT a negative finding — the
        # negative finding is what we assert once we DO catch the window.
        assert held_observed and t_enter is not None, (
            "could not catch a mid-turn window where the typed marker stayed "
            "queued during live generation across %d attempts — the backend "
            "streamed too fast every time. This is a capture blocker, not a "
            "finding; re-run when generation is slower." % MAX_ATTEMPTS
        )

        # We have proven the marker stays queued (unsubmitted, unreacted-to)
        # while the agent generates. Now watch it submit at the boundary and be
        # answered as an ordinary subsequent turn. Record a full timeline.
        timeline = []
        marker_asst = marker_user = essay_asst = False
        mid_turn_hit = marker_in_assistant_while_queued
        deadline = time.time() + 300
        while time.time() < deadline:
            entries = _safe_read_log(tb, name)
            a_texts = _texts(entries, "assistant")
            u_texts = _texts(entries, "user")
            marker_asst = any(MARKER in t for t in a_texts)
            marker_user = any(MARKER in t for t in u_texts)
            essay_asst = any(len(t) > 400 and MARKER not in t for t in a_texts)
            st = _state(tb, name)
            timeline.append(
                (round(time.time() - t_enter, 1), st,
                 marker_asst, marker_user, essay_asst)
            )
            # An earlier-than-boundary hit = the agent reacts to the marker
            # while it has NOT yet been submitted as an ordinary prompt.
            if marker_asst and not marker_user:
                mid_turn_hit = True
            if marker_asst and marker_user:
                break
            time.sleep(0.5)

        # Let everything settle (the long essay turn + any queued marker turn).
        try:
            tb.wait_idle(name, timeout=180)
        except Exception as e:
            log.debug("wait_idle after enter: %s", e)

        entries = _safe_read_log(tb, name)
        a_texts = _texts(entries, "assistant")
        u_texts = _texts(entries, "user")
        marker_in_assistant = any(MARKER in t for t in a_texts)
        marker_in_user = any(MARKER in t for t in u_texts)
        essay_completed = any(len(t) > 400 and MARKER not in t for t in a_texts)
        essay_idx = _first_idx(
            entries,
            lambda e: e.get("type") == "assistant"
            and len(_text_of(e)) > 400 and MARKER not in _text_of(e),
        )
        marker_user_idx = _first_idx(
            entries,
            lambda e: e.get("type") == "user" and MARKER in _text_of(e),
        )
        essay_before_marker_prompt = (
            essay_idx is not None and marker_user_idx is not None
            and essay_idx < marker_user_idx
        )

        # earlier-safe-delivery = the marker reached the agent WITHOUT riding
        # the composer→submit path (i.e. no user entry). That would be a real
        # out-of-band mid-turn channel (WORKS). Deferred/Next = the marker
        # became an ordinary user prompt (marker_in_user).
        earlier_safe_point = marker_in_assistant and not marker_in_user

        log.debug(
            "RESULT: typeahead_in_composer=%s held_queued_mid_turn=%s "
            "marker_in_assistant=%s marker_in_user=%s essay_completed=%s "
            "essay_before_marker_prompt=%s mid_turn_hit=%s earlier_safe_point=%s",
            typeahead_in_composer, held_observed, marker_in_assistant,
            marker_in_user, essay_completed, essay_before_marker_prompt,
            mid_turn_hit, earlier_safe_point,
        )
        log.debug("timeline (dt, state, mkA, mkU, essayA):")
        for row in timeline:
            log.debug("  %s", row)
        log.debug("user_texts=%r", [t[:120] for t in u_texts])
        log.debug(
            "assistant_texts(len,head)=%r",
            [(len(t), t[:80]) for t in a_texts],
        )

        # --- Assertions (the honest negative — item 4's expected outcome) ----
        # P1: typeahead is *possible* — the text lands in the composer while the
        # agent is mid-turn (proving the send-keys surface works) ...
        assert typeahead_in_composer, (
            "typeahead did not even land in the composer while generating — the "
            "send-keys surface may be broken; inspect tests/log before "
            "concluding anything about mid-turn delivery"
        )
        # ... but neither typing NOR pressing Enter mid-turn reached the agent
        # while the marker was queued (it never reacted during the held window).
        assert not marker_in_assistant_while_queued, (
            "the agent reacted to the marker while it was still queued mid-turn "
            "— that would be an earlier delivery point (WORKS); investigate"
        )
        # P2: the marker was delivered as an ordinary queued prompt (rode the
        # composer, submitted at/after the boundary) — a real user entry.
        assert marker_in_user, (
            "the marker never became a queued user prompt. If it reached the "
            "agent mid-turn with NO user entry (earlier_safe_point=%s), that is "
            "the WORKS exit — rewrite this as a positive earlier-delivery test. "
            "Otherwise the marker was lost; inspect the timeline/transcript in "
            "tests/log." % earlier_safe_point
        )
        # The in-flight essay turn completed uncorrupted, BEFORE the marker turn.
        assert essay_completed, (
            "the in-flight essay turn did not complete — possible mid-turn "
            "corruption from the injected Enter; investigate"
        )
        assert essay_before_marker_prompt, (
            "the marker prompt was not strictly after the completed essay turn "
            "— mid-turn delivery may have occurred; investigate the transcript"
        )
        # The bottom line: NO earlier-than-boundary safe delivery point exists —
        # typeahead is Next/Queue, exactly the §10 item-4 Fallback.
        assert not earlier_safe_point, (
            "UNEXPECTED WORKS: the marker reached the agent without riding the "
            "composer→submit path — an earlier safe delivery point exists. "
            "Keep this test but flip it to assert that positive observable, and "
            "flag §10 item 4 for upgrade."
        )
    finally:
        try:
            tb.close(name)  # our session only — NEVER kill-server
        except Exception as e:
            log.debug("close(%s): %s", name, e)
        try:
            tb._run(f"rm -rf {path}")
        except Exception as e:
            log.debug("rm -rf %s: %s", path, e)
