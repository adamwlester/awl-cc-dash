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

Contrast — **Retire** = soft/reversible deep-freeze (stop session + archive the
agent's record; recoverable, §7.12 / §11 #18). Retire is **archived by default**:
:func:`build_archive_record` builds the light, distinct-id archive record here
(pure), and the state store persists it into ``state/archive.json``. Unlike
Delete, Retire NEVER erases the transcript — the archive **references** it in
place (path + session id, §8.6), never copies it.

This module is PURE: it PLANS and MARKS. It never touches the real filesystem,
tmux, or the shared stores — the orchestrator wires the real wipe/tombstone from
the structures returned here.
"""
from __future__ import annotations

import uuid
from datetime import datetime
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


# --- agent archive (Retire = deep-freeze, archived by default, §7.12/§11 #18) --

# Reserved lineage fields (§11 #18): the schema RESERVES these — a nullable
# home for the parent / fork / handoff links that #15 (fork/handoff) and #19
# (per-agent git identity) will populate later, plus the separate operator-side
# lineage/graph work. Reserved-but-null now: declared so the graph work has a
# stable shape to fill, NOT populated here.
LINEAGE_FIELDS: tuple[str, ...] = ("parent", "fork", "handoff")


def empty_lineage() -> dict[str, Any]:
    """A fresh reserved-but-null lineage block (``{parent, fork, handoff}``)."""
    return {f: None for f in LINEAGE_FIELDS}


def new_archive_id() -> str:
    """A DISTINCT archive id — never the session id (§11 #18 distinct-ID records).

    Distinct so one agent instantiation is one archive row, and so re-creating
    an agent under the same session id still archives as a separate record.
    """
    return f"arc{uuid.uuid4().hex[:12]}"


def build_archive_record(
    session_id: str,
    *,
    identity: Optional[dict[str, Any]] = None,
    created_at: Optional[str] = None,
    retired_at: Optional[str] = None,
    transcript_path: Optional[str] = None,
    claude_session_id: Optional[str] = None,
    cwd: Optional[str] = None,
    model: Optional[str] = None,
    driver: Optional[str] = None,
    permission_mode: Optional[str] = None,
    git_author: Optional[tuple[str, str]] = None,
    lineage: Optional[dict[str, Any]] = None,
    archive_id: Optional[str] = None,
    tmux_name: Optional[str] = None,
    arm_bypass: bool = False,
) -> dict[str, Any]:
    """Build a LIGHT Agent-archive record — Retire = deep-freeze (§7.12, §11 #18).

    Pure — returns the record; persistence is the state store's job
    (``state_store.save_archive_record``). The record carries:

    * a **distinct** ``archive_id`` (never the session id), plus ``session_id``
      as provenance;
    * an **identity snapshot** (``identity`` dict + convenience ``name`` /
      ``color`` / ``icon``);
    * ``created_at`` (when the agent was created) + ``retired_at`` (now);
    * the transcript **referenced in place** — ``transcript.{claude_session_id,
      transcript_path}`` — **never copied** (§8.6); the fat content stays in the
      one master JSONL;
    * the **reserved lineage fields** (``lineage.{parent, fork, handoff}``),
      nullable + unpopulated for #15/#19's lineage work;
    * light metadata (``cwd`` / ``model`` / ``driver`` / ``permission_mode`` and,
      when known, the per-agent git author/email from #19).
    """
    ident = dict(identity or {})
    lin = empty_lineage()
    if lineage:
        lin.update({k: lineage.get(k) for k in LINEAGE_FIELDS if k in lineage})
    rec: dict[str, Any] = {
        "archive_id": archive_id or new_archive_id(),
        "session_id": session_id,
        "name": ident.get("name") or "",
        "identity": ident,
        "color": ident.get("color"),
        "icon": ident.get("icon"),
        "created_at": created_at,
        "retired_at": retired_at or datetime.now().isoformat(),
        # Transcript is REFERENCED, never copied (§8.6): only the pointer lives here.
        "transcript": {
            "claude_session_id": claude_session_id,
            "transcript_path": transcript_path,
        },
        # Reserved lineage (§11 #18) — filled later by #15/#19; null now.
        "lineage": lin,
        # Light metadata.
        "cwd": cwd,
        "model": model,
        "driver": driver,
        "permission_mode": permission_mode,
        # The agent's tmux session name (§7.19 Timeline persistence): the
        # per-agent launch-config dir (turns.jsonl / statusline.jsonl) is
        # keyed by it, so a resume that reuses the name re-attaches the same
        # Timeline store instead of orphaning it.
        "tmux_name": tmux_name,
        # Pre-armed Bypass (§7.11 arm-without-activate) — a light launch fact
        # like permission_mode, kept so an un-retire relaunches with the ring
        # the operator armed.
        "arm_bypass": bool(arm_bypass),
    }
    if git_author is not None:
        rec["git_author_name"], rec["git_author_email"] = git_author
    return rec


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
