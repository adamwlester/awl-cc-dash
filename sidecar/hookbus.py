"""Hook channel — the durable per-agent inject inbox + hook-output builders.

The spike-gated path that the hook spike proved out **live** on the
installed build (claude 2.1.195): a running agent receives a queued inject
**mid-turn at the next tool boundary**, without stopping, via a `PostToolUse`
HTTP hook that returns `hookSpecificOutput.additionalContext`. A `Stop` hook
(`decision:"block"` + reason) backstops the no-tool-call case so a pure-text
turn still catches an active inject at turn-end.

Two inject **kinds**:

* ``inject``  — an *active* message (a link Inject trigger, or a Plan/Decision prompt)
  that SHOULD provoke the agent to act. Delivered via PostToolUse, and eligible
  for the Stop backstop so a no-tool turn still catches it.
* ``context`` — *passive* context (a scratchpad delta, or link shared context)
  that must NOT trigger a turn. Delivered via PostToolUse ``additionalContext``
  only; never via the Stop backstop (blocking Stop would force a continuation).

**Durable + ack-on-2xx.** An inject leaves the inbox only when a ``drain`` hands
it to a 2xx hook response. The build treats a failed/timed-out HTTP hook as
non-blocking, so an undelivered inject simply stays pending for the next
boundary (the drain endpoints only call ``drain`` once they are about to return
200, so a server error leaves the inbox untouched).

Pure-logic and process-local (mirrors ``eventbus``): no I/O, hermetically
testable. ``reset()`` clears it (tests + a fresh process).
"""
from __future__ import annotations

import itertools
from collections import defaultdict, deque
from datetime import datetime
from typing import Any, Iterable

# Per-agent FIFO inbox of pending injects, keyed by the **sidecar** session id
# (the same id the bridge bakes into each agent's hook URL as ?agent=<id>).
_INBOX: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
_id_counter = itertools.count(1)

# The build caps injected hook output (additionalContext / Stop reason) at 10000
# chars; render defensively under that so a large scratchpad delta can't be
# silently spilled to a file mid-run.
MAX_INJECT_CHARS = 10000


def reset() -> None:
    """Drop all pending injects (tests + fresh process)."""
    _INBOX.clear()


def enqueue_inject(agent_id: str, text: str, *, kind: str = "inject",
                   source: str | None = None,
                   inject_id: str | None = None) -> dict[str, Any]:
    """Queue an inject for delivery at ``agent_id``'s next hook boundary.

    ``kind="inject"`` (default) = an active message; ``kind="context"`` = passive
    (scratchpad/shared-context) that never triggers a turn. Returns the stamped
    inject dict.
    """
    inj = {
        "id": inject_id or f"inj{next(_id_counter)}",
        "text": text,
        "kind": kind,
        "source": source,
        "created_at": datetime.now().isoformat(),
    }
    _INBOX[agent_id].append(inj)
    return inj


def pending(agent_id: str, kinds: Iterable[str] | None = None) -> list[dict[str, Any]]:
    """Pending (undelivered) injects for ``agent_id``, oldest first, without
    removing them. Optionally filtered to ``kinds``."""
    kindset = set(kinds) if kinds is not None else None
    return [i for i in _INBOX.get(agent_id, ())
            if kindset is None or i["kind"] in kindset]


def drain(agent_id: str, kinds: Iterable[str] | None = None) -> list[dict[str, Any]]:
    """Remove and return ``agent_id``'s pending injects (the ack), oldest first.

    With ``kinds`` set, only those kinds are removed/returned and the rest stay
    pending — so a Stop drain (``kinds={"inject"}``) never consumes passive
    ``context`` injects, which wait for the next PostToolUse boundary / run.
    """
    q = _INBOX.get(agent_id)
    if not q:
        return []
    kindset = set(kinds) if kinds is not None else None
    if kindset is None:
        taken = list(q)
        q.clear()
        return taken
    taken: list[dict[str, Any]] = []
    kept: deque[dict[str, Any]] = deque()
    for i in q:
        (taken if i["kind"] in kindset else kept).append(i)
    _INBOX[agent_id] = kept
    return taken


def _render(injects: list[dict[str, Any]]) -> str:
    """Render injects into one bounded human/agent-readable block."""
    n = len(injects)
    header = f"[AWL inbox — {n} message{'s' if n != 1 else ''} delivered to you mid-turn]"
    lines = [header]
    for inj in injects:
        src = inj.get("source")
        prefix = f"from {src}: " if src else ""
        lines.append(f"- {prefix}{inj['text']}")
    block = "\n".join(lines)
    if len(block) > MAX_INJECT_CHARS:
        block = block[: MAX_INJECT_CHARS - 1] + "…"
    return block


def post_tool_use_output(injects: list[dict[str, Any]]) -> dict[str, Any]:
    """The exact JSON a PostToolUse hook returns to inject ``injects`` mid-turn.

    Empty list -> ``{}`` (a 2xx no-op, per the build's HTTP-hook contract).
    """
    if not injects:
        return {}
    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": _render(injects),
        }
    }


def stop_output(injects: list[dict[str, Any]]) -> dict[str, Any]:
    """The exact JSON a Stop hook returns to surface active ``injects`` at turn-end.

    ``decision:"block"`` re-prompts the model with the reason so a no-tool turn
    still catches an active inject. Empty list -> ``{}`` (let the turn end).
    """
    if not injects:
        return {}
    return {"decision": "block", "reason": _render(injects)}
