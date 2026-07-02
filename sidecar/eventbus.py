"""Cross-agent event bus + message addressing.

The sidecar owns ONE aggregated, identity-stamped event stream the whole
dashboard subscribes to — replacing the per-session `/history` poll. This module
is the bus: it stamps a lightweight **envelope** onto every event and mirrors it
into a **bounded global ring** that the merged `/events` endpoint replays + streams.

**Envelope** (stamped in :func:`stamp`):
  ``{id, agent_id, seq, type, ts, source, recipients, ...payload}``
  * ``agent_id`` — the sender (the identity stamp = the session id).
  * ``seq`` — a **separate monotonic** ordering key the sidecar assigns at emit.
    *Never parse the id for order* — order by ``seq``.
  * ``id`` — a **deterministic** composite ``{agent_id}:{source_kind}:{anchor}``.
    For transcript events the driver supplies ``anchor`` = the JSONL entry uuid
    + ``source_kind='t'``, so re-polling the same entry dedups to a no-op and a
    reconnect replays without duplicates. Synthesized events (no anchor) get a
    unique ``{agent_id}:s:seq{n}`` id and never dedup.
  * ``source`` + ``recipients[]`` — who it's from + a typed list of
    addressees (``user | <agent-id> | scratch``), default ``source=agent_id`` /
    ``recipients=['user']``. **Addressed-to drives routing + the From/To filter +
    Sent/Received direction — NOT visibility** (every event still shows in the feed).

It is a **bounded bus, not a stored mega-log**: the on-disk JSONL transcripts stay
the source of truth; this ring is a rolling window the UI virtualizes/backfills
against, and From/To filters apply server-side (:func:`event_matches`, :func:`replay`).
"""

from __future__ import annotations

import asyncio
import os
from collections import deque
from datetime import datetime
from typing import Any, Iterable

# Bounded merged history — a rolling window, NOT the per-session unbounded log.
GLOBAL_RING_MAX = int(os.environ.get("AWL_EVENT_RING_MAX", "5000"))

_global_seq: int = 0
GLOBAL_RING: deque[dict[str, Any]] = deque(maxlen=GLOBAL_RING_MAX)
GLOBAL_SUBSCRIBERS: list[asyncio.Queue[dict[str, Any]]] = []


def reset() -> None:
    """Reset all bus state — for tests (the bus is process-global, like `sessions`)."""
    global _global_seq
    _global_seq = 0
    GLOBAL_RING.clear()
    GLOBAL_SUBSCRIBERS.clear()


def next_seq() -> int:
    """The next monotonic ordering value (stream-wide; 1-based)."""
    global _global_seq
    _global_seq += 1
    return _global_seq


def stamp(
    event: dict[str, Any],
    *,
    agent_id: str,
    emitted_ids: set[str],
    source: str | None = None,
    recipients: list[str] | None = None,
) -> dict[str, Any] | None:
    """Stamp the identity/addressing envelope onto ``event`` in place.

    Returns the stamped event, or ``None`` when it duplicates an already-emitted
    **anchored** event (the re-poll/reconnect dedup → no-op). Synthesized events
    (no ``anchor``) never dedup. ``source`` / ``recipients`` already on the event
    are preserved (a link fire or user send may pre-address it); otherwise they
    default to the agent and ``['user']``.
    """
    anchor = event.get("anchor")
    kind = event.get("source_kind", "s")
    if anchor is not None:
        ev_id = f"{agent_id}:{kind}:{anchor}"
        if ev_id in emitted_ids:
            return None  # re-poll dedup → no-op
        emitted_ids.add(ev_id)
    else:
        ev_id = None  # assigned from seq below (always unique)

    seq = next_seq()
    event["agent_id"] = agent_id
    event["seq"] = seq
    event.setdefault("ts", event.get("timestamp") or datetime.now().isoformat())
    if source is not None:
        event["source"] = source
    else:
        event.setdefault("source", agent_id)
    if recipients is not None:
        event["recipients"] = recipients
    else:
        event.setdefault("recipients", ["user"])
    event["id"] = ev_id if ev_id is not None else f"{agent_id}:{kind}:seq{seq}"
    return event


def publish_global(event: dict[str, Any]) -> None:
    """Mirror a stamped event into the bounded ring + fan out to merged subscribers."""
    GLOBAL_RING.append(event)
    for q in list(GLOBAL_SUBSCRIBERS):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass  # slow merged subscriber: bounded-drop (it can re-backfill via ?since)


def event_matches(
    event: dict[str, Any],
    sources: Iterable[str] | None,
    recipients: Iterable[str] | None,
) -> bool:
    """Server-side From/To filter. ``sources`` matches the event's ``source``;
    ``recipients`` matches if ANY of the event's recipients is in the set."""
    if sources:
        if event.get("source") not in set(sources):
            return False
    if recipients:
        want = set(recipients)
        ev_recips = event.get("recipients") or []
        if not any(r in want for r in ev_recips):
            return False
    return True


def replay(
    since: int | None = None,
    sources: Iterable[str] | None = None,
    recipients: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """The merged history slice for scroll-backfill: ring events with
    ``seq > since`` that pass the From/To filter, in ring (seq) order."""
    src = set(sources) if sources else None
    rcp = set(recipients) if recipients else None
    out: list[dict[str, Any]] = []
    for ev in list(GLOBAL_RING):
        if since is not None and ev.get("seq", 0) <= since:
            continue
        if event_matches(ev, src, rcp):
            out.append(ev)
    return out
