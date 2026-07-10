"""Shared scratchpad — the team's always-current shared comms channel.

Every agent **auto-reads** the scratchpad (the corrected 2026-06-30 policy,
reversing explicit-send-only). Delivered as a **per-agent delta off a read
watermark** (the same mechanism as link shared-context) so context stays
bounded: each agent keeps a last-read pointer and receives only **new posts past
that pointer**, which then advances. First read (no watermark) = the **full
board**; deltas thereafter; an agent's **own posts** are included (positioned in
the shared timeline — reading never emits a post, so no echo loop).

Delivery moments (wired in `main`): **live mid-run push** to running agents via
the hook channel (a `context` inject = passive additionalContext that does
NOT trigger a turn), and **start-of-run catch-up** for idle agents (they have no
tool boundary, so they pick up their delta when they next run). Posts carry
`recipients:[scratch]` in the addressing envelope. **Storage** =
`<project>/.awl/scratchpad.md` (per the storage & scoping model), WSL-reachable.

This module owns the log + delta + render; process-local (like `eventbus`),
keyed by a **project key** (the project root, so co-located agents share one
board). `reset()` clears it.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import watermark

_LOG: dict[str, list[dict[str, Any]]] = defaultdict(list)
# Monotonic post seq (module-global; per-project boards only need per-board
# monotonicity, which a global counter gives for free). A plain int rather than
# itertools.count so `restore()` can advance it past reloaded posts' seqs.
_next_seq: int = 1


def reset() -> None:
    global _next_seq
    _LOG.clear()
    _next_seq = 1


def _wm_key(agent_id: str, project_key: str) -> str:
    return f"scratch:{project_key}:{agent_id}"


def post(project_key: str, author: str, text: str, *,
         persist_path: str | None = None) -> dict[str, Any]:
    """Append a post (author attribution + timestamp + monotonic seq) to the
    project's board; optionally mirror the board to a markdown file."""
    global _next_seq
    p = {
        "seq": _next_seq,
        "author": author,
        "text": text,
        "ts": datetime.now().isoformat(),
    }
    _next_seq += 1
    _LOG[project_key].append(p)
    if persist_path:
        _persist(project_key, persist_path)
    return p


def restore(project_key: str, posts: list[dict[str, Any]]) -> None:
    """Seed a project's board from its persisted ``.md`` mirror (project load).

    Replaces the board wholesale (load runs before any live posts) and advances
    the seq counter past the reloaded posts so future posts keep monotonicity —
    the reloaded seqs (1..N by line order) are what persisted bookmarks refer to.
    """
    global _next_seq
    _LOG[project_key] = list(posts)
    max_seq = max((int(p.get("seq") or 0) for p in posts), default=0)
    if max_seq >= _next_seq:
        _next_seq = max_seq + 1


def all_posts(project_key: str) -> list[dict[str, Any]]:
    return list(_LOG.get(project_key, ()))


def unread(agent_id: str, project_key: str) -> list[dict[str, Any]]:
    """The agent's delta: new posts past its read watermark (advances it). First
    call with no watermark returns the full board."""
    posts = _LOG.get(project_key, ())
    items = [(p["seq"], p) for p in posts]
    return watermark.delta(_wm_key(agent_id, project_key), items)


def peek_unread(agent_id: str, project_key: str) -> list[dict[str, Any]]:
    """Same selection as `unread` but WITHOUT advancing the watermark."""
    posts = _LOG.get(project_key, ())
    items = [(p["seq"], p) for p in posts]
    return watermark.peek(_wm_key(agent_id, project_key), items)


def render(posts: list[dict[str, Any]]) -> str:
    """Render a delta as a bounded, attributed block for injection / display."""
    lines = ["[Shared scratchpad — new post(s)]"]
    for p in posts:
        lines.append(f"- ({p['author']}) {p['text']}")
    return "\n".join(lines)


def _persist(project_key: str, path: str) -> None:
    """Mirror the whole board to a markdown file (best-effort)."""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        out = ["# Shared scratchpad", ""]
        for post_ in _LOG.get(project_key, ()):
            out.append(f"- **{post_['author']}** ({post_['ts']}): {post_['text']}")
        p.write_text("\n".join(out) + "\n", encoding="utf-8")
    except Exception:  # pragma: no cover - persistence is best-effort
        pass
