"""Tier-2 agent-to-agent linking — the link store, caps, and grouping (OD-04..08).

A **link** joins two agents and carries the OD-06 relationship config:

* **direction** — ``a2b`` / ``b2a`` / ``both`` (the agent-pair arrow).
* **relationship** — any of ``direct`` (reply-to conversation, OD-04) and
  ``shared`` (passive shared-context awareness, OD-06).
* **trigger** — the OD-05 delivery mode a fire uses (Now/Next/Queue/Inject/Hold;
  ``queue`` default).
* **End-After** (OD-07) — two independent caps, ``end_after_exchanges`` (default
  **25**; a round-trip = one message each direction = 2 messages) and
  ``end_after_tokens``; either reached ends the auto-exchange (the runaway
  backstop behind strict one-in-flight alternation).

This module is the **pure store + cap logic** (hermetically testable). The
serialized reply-to ENGINE (record who an agent is answering → on its
generating→idle, fire that turn's output back to the inbound's source) lives in
``main`` where the session/queue/hook machinery is, and is verified live.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass, field
from typing import Any

_id_counter = itertools.count(1)
_LINKS: dict[str, "Link"] = {}

VALID_DIRECTIONS = {"a2b", "b2a", "both"}
DEFAULT_END_AFTER_EXCHANGES = 25  # OD-07


@dataclass
class Link:
    id: str
    a: str
    b: str
    direction: str = "both"
    relationship: list[str] = field(default_factory=lambda: ["direct"])
    shared_content: list[str] = field(default_factory=list)
    shared_backfill: bool = False
    trigger: str = "queue"
    end_after_exchanges: int | None = DEFAULT_END_AFTER_EXCHANGES
    end_after_tokens: int | None = None
    # runtime counters (a fire = one message in one direction)
    messages: int = 0
    tokens: int = 0
    active: bool = True

    def allows(self, src: str, dst: str) -> bool:
        """Can ``src`` send to ``dst`` over this link, per its direction?"""
        if {src, dst} != {self.a, self.b}:
            return False
        if self.direction == "both":
            return True
        if self.direction == "a2b":
            return src == self.a and dst == self.b
        return src == self.b and dst == self.a  # b2a

    def other(self, agent: str) -> str | None:
        """The peer on the far side of the link from ``agent``."""
        if agent == self.a:
            return self.b
        if agent == self.b:
            return self.a
        return None

    def arrow_for(self, group_agent: str) -> str:
        """OD-08 direction arrow relative to the group's agent: → (to) / ← (from)
        / ↔ (both)."""
        if self.direction == "both":
            return "↔"
        # does the group agent SEND on this link?
        sends = (self.direction == "a2b" and group_agent == self.a) or \
                (self.direction == "b2a" and group_agent == self.b)
        return "→" if sends else "←"

    def is_direct(self) -> bool:
        return "direct" in self.relationship

    def is_shared(self) -> bool:
        return "shared" in self.relationship

    @property
    def exchanges(self) -> int:
        """Completed round-trips (each = a message in each direction)."""
        return self.messages // 2

    def over_cap(self) -> bool:
        """True once an End-After cap is reached (the auto-exchange must stop)."""
        if self.end_after_exchanges is not None and \
                self.messages >= 2 * self.end_after_exchanges:
            return True
        if self.end_after_tokens is not None and self.tokens >= self.end_after_tokens:
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id, "a": self.a, "b": self.b, "direction": self.direction,
            "relationship": list(self.relationship),
            "shared_content": list(self.shared_content),
            "shared_backfill": self.shared_backfill,
            "trigger": self.trigger,
            "end_after_exchanges": self.end_after_exchanges,
            "end_after_tokens": self.end_after_tokens,
            "messages": self.messages, "exchanges": self.exchanges,
            "tokens": self.tokens, "active": self.active,
        }


def reset() -> None:
    _LINKS.clear()


def add_link(*, a: str, b: str, direction: str = "both",
             relationship: list[str] | None = None,
             shared_content: list[str] | None = None,
             shared_backfill: bool = False,
             trigger: str = "queue",
             end_after_exchanges: int | None = DEFAULT_END_AFTER_EXCHANGES,
             end_after_tokens: int | None = None,
             link_id: str | None = None) -> Link:
    if direction not in VALID_DIRECTIONS:
        direction = "both"
    lk = Link(
        id=link_id or f"lnk{next(_id_counter)}",
        a=a, b=b, direction=direction,
        relationship=relationship if relationship else ["direct"],
        shared_content=shared_content or [],
        shared_backfill=shared_backfill,
        trigger=trigger,
        end_after_exchanges=end_after_exchanges,
        end_after_tokens=end_after_tokens,
    )
    _LINKS[lk.id] = lk
    return lk


def get_link(link_id: str) -> Link | None:
    return _LINKS.get(link_id)


def remove_link(link_id: str) -> bool:
    return _LINKS.pop(link_id, None) is not None


def all_links() -> list[Link]:
    return list(_LINKS.values())


def find_direct_link(src: str, dst: str) -> Link | None:
    """The active direct-messaging link that lets ``src`` send to ``dst`` (either
    orientation, gated by direction). Used by the reply-to engine to find where
    to route a finished turn's output."""
    for lk in _LINKS.values():
        if lk.active and lk.is_direct() and lk.allows(src, dst):
            return lk
    return None


def grouped_by_agent() -> dict[str, list[dict[str, Any]]]:
    """OD-08: all links grouped by agent. A link joins two agents, so it appears
    under BOTH groups (deliberate double-listing). Each entry: the other agent +
    the direction arrow relative to that group's agent."""
    out: dict[str, list[dict[str, Any]]] = {}
    for lk in _LINKS.values():
        for agent in (lk.a, lk.b):
            out.setdefault(agent, []).append({
                "link_id": lk.id,
                "other": lk.other(agent),
                "arrow": lk.arrow_for(agent),
                "relationship": list(lk.relationship),
                "trigger": lk.trigger,
                "active": lk.active,
            })
    return out
