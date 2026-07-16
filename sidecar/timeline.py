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

This module is the pure, hermetically-testable half: summary derivation, the
settings string, model extraction from a statusline payload, and the record
shape. The IO halves live where they belong — the join + schedule in
``main._capture_turn_record``, the thin persist (per-agent ``turns.jsonl``
beside ``statusline.jsonl`` in the launch-config dir, §8.3: the
settings-at-turn snapshot is NOT in the transcript, so it must persist) in
the bridge driver's ``append_turn_record``/``get_timeline``, and the read
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
                 thinking: bool | None = None,
                 summary: str | None = None) -> dict[str, Any]:
    """One thin per-turn Timeline record (§8.3 — small, append-friendly).

    Carries the structured settings fields, their rendered ``settings`` string,
    and the one-line ``summary``. ``turn`` is the session-local completed-turn
    count at capture time; the read surface re-mints the ordinal in stored
    order so the index stays monotonic across sidecar restarts.
    """
    return {
        "turn": turn,
        "timestamp": timestamp,
        "model": model,
        "mode": mode,
        "effort": effort,
        "thinking": thinking,
        "settings": settings_string(model=model, mode=mode, effort=effort,
                                    thinking=thinking),
        "summary": summary,
    }
