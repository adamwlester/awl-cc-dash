"""Shared per-key read-watermark for the AWL sidecar.

A process-local, in-memory store (same spirit as ``eventbus``) that tracks a
last-read pointer into an append-log, keyed by an arbitrary string. Each
consumer keeps its own pointer and receives only NEW items past it, which then
advances.

Used by:
- the scratchpad delta — keys like ``f"scratch:{agent}"``
- the link shared-context delta — keys like ``f"shared:{source}:{target}"``

Sequence numbers are assumed to start at 1, so a never-advanced key has a
watermark of 0. Sequences are typically strictly monotonic increasing, but
gaps are permitted (do not assume gap-free).

Not thread-safe by design (matches the rest of the process-local sidecar
stores); callers run single-threaded per request.
"""

from __future__ import annotations

from typing import Any, Callable, List, Tuple

# key -> highest seq already read
_marks: dict[str, int] = {}

# Optional write-through persist hook (installed by state_store): fired with the
# key after any mutation, so advanced marks land in the project's
# state/bookmarks.json (§8.3). None (the default) = pure in-memory behavior.
_persist_hook: Callable[[str], None] | None = None


def set_persist_hook(fn: Callable[[str], None] | None) -> None:
    """Install (or clear) the write-through persist hook."""
    global _persist_hook
    _persist_hook = fn


def _notify(key: str) -> None:
    if _persist_hook is not None:
        try:
            _persist_hook(key)
        except Exception:  # pragma: no cover - persistence must never break reads
            pass


def reset() -> None:
    """Clear all watermarks."""
    _marks.clear()


def get(key: str) -> int:
    """Return the current watermark for ``key`` (0 when never advanced)."""
    return _marks.get(key, 0)


def set(key: str, seq: int) -> None:
    """Force the watermark for ``key`` to ``seq``."""
    _marks[key] = seq
    _notify(key)


def drop(key: str) -> bool:
    """Remove a key's watermark entirely (agent deletion, §7.12/§11 #11)."""
    existed = _marks.pop(key, None) is not None
    if existed:
        _notify(key)
    return existed


def keys() -> list[str]:
    """All keys currently holding a watermark."""
    return list(_marks.keys())


def restore(marks: dict[str, int]) -> None:
    """Seed watermarks from a persisted store (project load) — no hooks fired."""
    _marks.update(marks)


def _select(key: str, items: List[Tuple[int, Any]]) -> List[Any]:
    """Payloads whose seq > current watermark, in input order."""
    mark = get(key)
    return [payload for seq, payload in items if seq > mark]


def delta(key: str, items: List[Tuple[int, Any]]) -> List[Any]:
    """New payloads past the watermark, advancing the watermark.

    ``items`` is a list of ``(seq, payload)`` tuples. Returns the payloads whose
    ``seq`` is greater than the current watermark for ``key``, in input order,
    and advances the watermark to the max seq present in ``items`` (not just the
    returned ones) — so a re-query with the same items returns ``[]``.

    If ``items`` is empty, returns ``[]`` and leaves the watermark unchanged.
    The watermark never regresses: if the max seq present is below the current
    watermark, the watermark is left untouched.
    """
    if not items:
        return []
    new = _select(key, items)
    max_seq = max(seq for seq, _ in items)
    if max_seq > get(key):
        _marks[key] = max_seq
        _notify(key)
    return new


def peek(key: str, items: List[Tuple[int, Any]]) -> List[Any]:
    """Same selection as :func:`delta` but WITHOUT advancing (a preview)."""
    if not items:
        return []
    return _select(key, items)
