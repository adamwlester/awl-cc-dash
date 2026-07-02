"""Permanent Delete planning (pure logic).

Delete is a HARD, irreversible wipe governed by one rule: **WIPE the agent's
private footprint; TOMBSTONE everything shared.**

- **WIPE** (private, hard): the dashboard runtime record, the live tmux session
  (close), and the agent's on-disk Claude Code transcript + its subagent
  transcripts (true on-disk erasure). Available from any state — a running agent
  is interrupted+closed first.
- **TOMBSTONE** (shared, kept + attributed + marked deleted/inactive): the
  agent's scratchpad posts, feed events/messages, and its link
  history. Delete must NOT rewrite the shared record or corrupt peers'
  watermarks/stream. Link edges become INACTIVE tombstones on the surviving
  peer's list (non-functional), not silent removals.
- **CLEAR** (own transient state): the agent's queued prompts + inbox items are
  dropped (operational, not shared history).
- **NO identity recycling**: the agent's NUMBER is permanently retired —
  monotonic, never reused. Color/icon may still cycle; the tombstone holds the
  retired number.

Contrast — **Retire** = soft/reversible (stop session + archive config/transcript;
recoverable). Not implemented here; only the distinction is modelled.

This module is PURE: it PLANS and MARKS. It never touches the real filesystem,
tmux, or the shared stores — the orchestrator wires the real wipe/tombstone from
the structures returned here.
"""
from __future__ import annotations

from typing import Any, Optional


# --- deletion planning ---------------------------------------------------

def plan_deletion(
    agent_id: str,
    *,
    transcript_path: Optional[str] = None,
    subagent_paths: Optional[list[Optional[str]]] = None,
    link_ids: Optional[list[str]] = None,
    identity_number: Optional[int] = None,
) -> dict[str, Any]:
    """Build a structured permanent-delete plan for ``agent_id``.

    Pure — returns a description the orchestrator executes; deletes nothing.

    The ``wipe.transcripts`` list is the agent's main transcript followed by its
    subagent transcripts, with any ``None`` entries omitted (a running agent is
    interrupted + closed before the wipe, so ``wipe.tmux`` is always ``True``).
    """
    transcripts: list[str] = []
    if transcript_path is not None:
        transcripts.append(transcript_path)
    for p in subagent_paths or []:
        if p is not None:
            transcripts.append(p)

    return {
        "wipe": {
            "runtime_record": agent_id,
            "tmux": True,
            "transcripts": transcripts,
        },
        "tombstone": {
            "links": list(link_ids or []),
            "retired_number": identity_number,
        },
        "clear": {
            "queue": True,
            "inbox": True,
        },
    }


# --- shared-record tombstoning (copy, never mutate) ----------------------

def tombstone_event(event: dict[str, Any]) -> dict[str, Any]:
    """Return a COPY of a feed/scratchpad event marked deleted + attributed.

    Adds ``"deleted": True`` and preserves ``source``/identity. The input is
    never mutated — the shared record is appended to, not rewritten, so peers'
    watermarks and stream stay intact.
    """
    out = dict(event)
    out["deleted"] = True
    return out


def tombstone_link(link: dict[str, Any]) -> dict[str, Any]:
    """Return a COPY of a link edge as an inactive, non-functional tombstone.

    Sets ``"active": False`` and ``"deleted": True``. The edge survives on the
    peer's list (attributed, marked) rather than being silently removed. The
    input is never mutated.
    """
    out = dict(link)
    out["active"] = False
    out["deleted"] = True
    return out


# --- retired-number registry (no identity recycling) ---------------------

_RETIRED: set[int] = set()


def reset() -> None:
    """Clear the retired-number registry (test/lifecycle hook)."""
    _RETIRED.clear()


def retire_number(n: int) -> None:
    """Permanently retire identity number ``n`` — it is never reused."""
    _RETIRED.add(int(n))


def is_retired(n: int) -> bool:
    """Return whether identity number ``n`` has been retired."""
    return int(n) in _RETIRED


def next_free_number(start: int = 1) -> int:
    """Lowest integer >= ``start`` that is NOT retired (monotonic skip).

    Advances past retired numbers so old tombstoned numbers never collide.
    """
    n = int(start)
    while n in _RETIRED:
        n += 1
    return n
