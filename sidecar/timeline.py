"""Per-turn Timeline capture helpers (§7.19 / §7.14, §11 #46).

Every dashboard-initiated turn gets one thin Timeline record at its
exactly-once completion (the bridge driver's reply-gated run→idle / the SDK
driver's ``result`` — the capture rides those completion points in
``main.handle_event``, never a parallel turn detector): the agent's
**settings at that turn** (model + mode/effort/thinking, joined at the turn
boundary from what the statusline capture (§11 #31), the run-state arbiter
(§7.4), and the session's tracked levers already know) and a **concise
one-line summary** of the reply (source: the reply's leading line, per the
§11 #39 preamble lean — agents lead every reply with a one-liner; fallback:
the first sentence of the reply text, sanely truncated).

Each turn record also carries the turn's **transcript anchors** (the #46
rewind-anchor residual): ``prompt_uuid`` (the turn's user-prompt JSONL entry
uuid) and ``reply_uuid`` (the closing assistant entry uuid), lifted from the
turn's events at capture — null-safe additive fields (SDK/synthesized events
carry no anchor; old lines without the fields stay readable everywhere). And
the SAME ``turns.jsonl`` carries typed **rewind event records**
(``{"type": "rewind", "timestamp", "to_prompt_index"}``) appended by the
sidecar on each successful dashboard rewind: the JSONL transcript itself is
append-only (a rewind writes nothing at rewind time; no engine checkpoint id
exists anywhere), so persisting the rewind EVENT here is what lets the read
surface replay which turns are rolled back — see ``replay_timeline``. Turn
records may additively carry ``"type": "turn"`` on new writes; any line
WITHOUT a type is a turn (backward compat — old files replay identically).
Manual-terminal rewinds (outside the dashboard) write no event and stay
unmarked — consistent with the settled scope that the Timeline logs
dashboard turns.

This module is the pure, hermetically-testable half: summary derivation, the
settings string, model extraction from a statusline payload, the record
shapes, the anchor lift, and the rolled-state replay. The IO halves live
where they belong — the join + schedule in ``main._capture_turn_record``,
the rewind-event append in ``main._append_rewind_record`` (chained through
the same per-session capture serialization), the thin persist (per-agent
``turns.jsonl`` beside ``statusline.jsonl`` in the launch-config dir, §8.3:
the settings-at-turn snapshot is NOT in the transcript, so it must persist)
in the bridge driver's ``append_turn_record``/``get_timeline``, and the read
surface at ``GET /sessions/{id}/timeline``.

Contract pinned by ``tests/test_readouts_unit.py`` (the #46 sections).
"""

from __future__ import annotations

import re
from typing import Any

# The sane truncation bound for a one-line summary: past this the leading line
# is not a one-liner, so the first sentence (then a hard cut) takes over.
SUMMARY_MAX = 140

# First sentence-ending punctuation that is actually a boundary (followed by
# whitespace), so "v2.1.191" or "3.14" never reads as a sentence end.
_SENTENCE_END = re.compile(r"[.!?](?=\s)")

# Leading markdown structure markers (headings, list bullets, quotes) — noise
# on a one-line preview. Only marker runs followed by whitespace strip, so
# emphasis like ``**Bold**`` stays intact.
_LEAD_MARKERS = re.compile(r"^(?:[#>*\-•]+\s+)+")


def turn_summary(text: str | None) -> str | None:
    """A concise one-line summary of a turn's assistant reply.

    Source: the reply's **leading non-empty line** (the §11 #39 preamble lean —
    the presets instruct agents to open every reply with a one-line summary),
    with leading markdown markers stripped. Fallback when that line is not a
    one-liner (longer than ``SUMMARY_MAX``): its **first sentence**, and a hard
    ellipsis cut if even that runs long. ``None`` for an empty/absent reply —
    an honest miss, never a fabricated line.
    """
    if not text:
        return None
    line = ""
    for raw in text.splitlines():
        raw = raw.strip()
        if raw:
            line = _LEAD_MARKERS.sub("", raw).strip()
            if line:
                break
    if not line:
        return None
    if len(line) > SUMMARY_MAX:
        m = _SENTENCE_END.search(line)
        if m:
            line = line[:m.end()].strip()
        if len(line) > SUMMARY_MAX:
            line = line[:SUMMARY_MAX - 1].rstrip() + "…"
    return line


def settings_string(model: str | None = None, mode: str | None = None,
                    effort: str | None = None,
                    thinking: bool | None = None) -> str:
    """Render the settings-at-turn join as one display string.

    ``"<model> · <mode> · effort <effort> · thinking on|off"`` with unknown
    (None/empty) parts simply omitted — a young session with nothing known yet
    renders ``""`` honestly rather than fabricating fields. ``thinking`` is
    tri-state: None = unknown (omitted), False = known-off (shown).
    """
    parts: list[str] = []
    if model:
        parts.append(str(model))
    if mode:
        parts.append(str(mode))
    if effort:
        parts.append(f"effort {effort}")
    if thinking is not None:
        parts.append("thinking on" if thinking else "thinking off")
    return " · ".join(parts)


def model_from_snapshot(snap: Any) -> str | None:
    """The model out of a statusline payload (§11 #31), or None.

    The payload's ``model`` field is ``{id, display_name}`` on the mapped
    builds (id preferred — it matches the transcript/session spelling); a
    plain-string ``model`` is taken as-is. Anything else → None (the caller
    falls back to the session's launch model).
    """
    if not isinstance(snap, dict):
        return None
    m = snap.get("model")
    if isinstance(m, dict):
        return m.get("id") or m.get("display_name") or None
    if isinstance(m, str):
        return m or None
    return None


def build_record(*, turn: int, timestamp: str, model: str | None = None,
                 mode: str | None = None, effort: str | None = None,
                 thinking: bool | None = None, summary: str | None = None,
                 prompt_uuid: str | None = None,
                 reply_uuid: str | None = None) -> dict[str, Any]:
    """One thin per-turn Timeline record (§8.3 — small, append-friendly).

    Carries the structured settings fields, their rendered ``settings`` string,
    the one-line ``summary``, and the turn's transcript anchors
    (``prompt_uuid``/``reply_uuid`` — null-safe additive: an SDK-driven or
    synthesized turn has no transcript entry to anchor to). ``turn`` is the
    session-local completed-turn count at capture time; the read surface
    re-mints the ordinal in stored order so the index stays monotonic across
    sidecar restarts. New writes carry ``"type": "turn"`` explicitly; readers
    treat any typeless line as a turn (old files replay identically).
    """
    return {
        "type": "turn",
        "turn": turn,
        "timestamp": timestamp,
        "model": model,
        "mode": mode,
        "effort": effort,
        "thinking": thinking,
        "settings": settings_string(model=model, mode=mode, effort=effort,
                                    thinking=thinking),
        "summary": summary,
        "prompt_uuid": prompt_uuid,
        "reply_uuid": reply_uuid,
    }


def _prompt_like(ev: dict[str, Any]) -> bool:
    """True when a transcript user event is a real operator prompt.

    Tool results are ALSO type-"user" transcript entries (content blocks of
    type ``tool_result``), a Task-spawning turn interleaves the subagent's own
    sidechain prompt into the same JSONL (the driver flags it ``sidechain``),
    and the CLI writes meta user lines (flagged ``meta``) — none of those are
    the prompt. A real prompt's content is a plain string, or content blocks
    with no ``tool_result`` block.
    """
    if ev.get("sidechain") or ev.get("meta"):
        return False
    content = ev.get("content")
    if isinstance(content, list):
        return not any(isinstance(b, dict) and b.get("type") == "tool_result"
                       for b in content)
    return True


def turn_anchors(events: list[dict[str, Any]],
                 start_idx: int = 0) -> tuple[str | None, str | None]:
    """(prompt_uuid, reply_uuid) lifted from ONE turn's events.

    ``events`` is the session's FULL event list; ``start_idx`` is the turn's
    boundary index (where the last ``running`` status_change left it — the
    same window base the summary lift uses). Only transcript-anchored events
    count (``source_kind == 't'`` with a JSONL ``anchor`` uuid — the same
    anchors the event bus mints ``{agent_id}:t:{uuid}`` ids from), and a
    subagent's sidechain entries never anchor the parent turn.

    The REPLY anchor is the last non-sidechain assistant entry in the forward
    window (``start_idx`` up to the next ``running`` boundary). The PROMPT
    anchor needs BOTH directions: in live bridge ordering the driver polls the
    turn's user JSONL entry (events() step 2) BEFORE it emits the screen's
    ``running`` flip (step 3), and a mid-turn permission prompt re-emits
    ``running`` on resolution — so the prompt event usually sits BEFORE
    ``start_idx``, between the send's own synthetic ``running`` and the
    boundary. The lift takes the first prompt-like user entry in the forward
    window (the rarer polled-late ordering), else scans BACKWARD from
    ``start_idx``, stopping at the previous turn's completion (any
    non-``running`` status_change — every completed turn ends with an idle,
    and the send path pushes its synthetic ``running`` before the prompt can
    be polled in, so the scan never crosses into an earlier turn's prompt;
    intermediate ``running`` re-emissions, e.g. post-permission, are walked
    through). Prompt-like excludes tool results (also type-"user" entries),
    meta lines, and sidechain entries — ``_prompt_like``. Null-safe
    throughout — a turn with no anchored events (SDK driver, synthesized
    events) yields ``(None, None)``, never a fabricated anchor.
    """
    prompt: str | None = None
    reply: str | None = None
    for ev in events[start_idx:]:
        if not isinstance(ev, dict):
            continue
        if ev.get("type") == "status_change" and ev.get("status") == "running":
            break  # a new turn started; don't bleed into it
        if ev.get("source_kind") != "t" or not ev.get("anchor"):
            continue
        if ev.get("type") == "user":
            if prompt is None and _prompt_like(ev):
                prompt = ev.get("anchor")
        elif ev.get("type") == "assistant" and not ev.get("sidechain"):
            reply = ev.get("anchor")
    if prompt is None:
        for ev in reversed(events[:start_idx]):
            if not isinstance(ev, dict):
                continue
            if ev.get("type") == "status_change" \
                    and ev.get("status") != "running":
                break  # the previous turn's completion — never bleed past it
            if (ev.get("type") == "user" and ev.get("source_kind") == "t"
                    and ev.get("anchor") and _prompt_like(ev)):
                prompt = ev.get("anchor")
                break
    return prompt, reply


def build_rewind_record(*, timestamp: str,
                        to_prompt_index: int) -> dict[str, Any]:
    """One typed rewind event record for ``turns.jsonl``.

    Appended by the sidecar on each SUCCESSFUL dashboard rewind (never on a
    failed one), through the same per-session serialization as turn captures —
    the transcript itself is append-only and no engine checkpoint id exists,
    so this event line is the only persisted trace of the rewind.
    ``to_prompt_index`` = k, the count-from-end the native ``/rewind`` menu
    navigated by (1 = only the latest prompt rolled back).
    """
    return {
        "type": "rewind",
        "timestamp": timestamp,
        "to_prompt_index": int(to_prompt_index),
    }


def replay_timeline(records: list[Any]) -> dict[str, Any]:
    """Replay the interleaved turn/rewind stream into rows + rolled state.

    Ordinals are minted 1..N over TURN records only (typeless lines count as
    turns — old files replay identically; unknown-typed lines are skipped,
    forward-compat), so pure-turn files keep exactly today's numbering. Rolled
    state is a live-stack replay mirroring the renderer's k-from-last
    arithmetic: each turn pushes its ordinal; each rewind record pops/marks the
    top ``k = to_prompt_index`` live ordinals as rolled, clamped honestly at
    the stack size (a manual over-deep k never crashes the read). The replay
    diverges from the real conversation only if manual TUI turns interleave —
    the pre-existing, documented limit (the Timeline logs dashboard turns).

    Returns ``{"turns", "rolled_ranges", "rewinds"}``: rows carry a per-row
    ``rolled`` flag; ``rolled_ranges`` are merged ascending in the renderer's
    exclusive-``from`` representation ({from: the still-live target ordinal,
    to: the newest rolled ordinal} — a row t is rolled iff
    ``from < t <= to``); ``rewinds`` lists each rewind event
    ``{timestamp, to_prompt_index}`` in stored order.
    """
    rows: list[dict[str, Any]] = []
    live: list[int] = []           # ordinals of currently-live turns (the stack)
    rolled: set[int] = set()
    rewinds: list[dict[str, Any]] = []
    for rec in records:
        if not isinstance(rec, dict):
            rec = {"summary": None}  # unreadable record — an honest blank row
        rtype = rec.get("type")
        if rtype == "rewind":
            try:
                k = int(rec.get("to_prompt_index") or 0)
            except (TypeError, ValueError):
                k = 0
            rewinds.append({"timestamp": rec.get("timestamp"),
                            "to_prompt_index": k})
            for _ in range(min(max(k, 0), len(live))):  # honest clamp
                rolled.add(live.pop())
            continue
        if rtype not in (None, "turn"):
            continue  # forward-compat: an unknown typed line is not a turn row
        row = dict(rec)
        row["turn"] = len(rows) + 1
        rows.append(row)
        live.append(row["turn"])
    for row in rows:
        row["rolled"] = row["turn"] in rolled
    ranges: list[dict[str, int]] = []
    for o in sorted(rolled):
        if ranges and o == ranges[-1]["to"] + 1:
            ranges[-1]["to"] = o
        else:
            ranges.append({"from": o - 1, "to": o})
    return {"turns": rows, "rolled_ranges": ranges, "rewinds": rewinds}
