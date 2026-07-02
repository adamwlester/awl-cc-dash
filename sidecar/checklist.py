"""Run-strip completion parser — "agent self-report with barber-pole floor".

Pure logic, no I/O. The dashboard sidecar feeds this module the ordered list of
assistant text strings produced in a run (most recent last); it scans for a
markdown checklist the agent published, and returns done / total plus the label
of the CURRENT in-progress item so the run-strip can render a segmented bar.

FLOOR: a run that publishes NO checklist gets the honest barber-pole
indeterminate sentinel — never a fabricated %. The denominator can GROW mid-run
(the agent adds steps), so the bar may step backward; this module simply
reflects the LATEST checklist block parsed.

Recognized item-line forms (leading whitespace allowed):
    - [ ] foo      * [ ] foo      1. [ ] foo
    - [x] foo      - [X] foo      - [✓] foo
The marker is "done" when it is ``x`` / ``X`` / ``✓`` (or the heavier ``✔``);
``[ ]`` (a space) is not done.

Minimum-items rule
------------------
A *checklist* is a CONTIGUOUS run of item lines. A run of >= 2 items is always a
checklist. A lone single item counts ONLY when it stands alone as its own block
— i.e. the line directly above it and the line directly below it are not
non-blank prose. This lets a deliberate one-step checklist render while a stray
``[ ]`` written inside a paragraph does not false-fire.

When the same checklist is re-published across texts (or twice within one text),
the LATEST block is the source of truth: we scan texts oldest -> newest and,
within each text, take the last checklist block found; the newest text that
contains a block wins.
"""
from __future__ import annotations

import re
from typing import Optional

__all__ = ["parse_checklist", "barber_pole"]

# Markers that mean "done" inside the brackets.
_DONE_MARKERS = {"x", "X", "✓", "✔"}

# A checklist item line. Captures the marker char (or empty for "[ ]") and text.
# Bullet forms: "-", "*", or an ordered "N." / "N)".
_ITEM_RE = re.compile(
    r"""^\s*                       # leading whitespace allowed
        (?:[-*]|\d+[.)])           # bullet: - / * / 1. / 1)
        \s+
        \[\s*(?P<mark>[^\]]?)\s*\] # [ ] / [x] / [X] / [✓]  (single inner char)
        \s*
        (?P<text>.*?)              # the item text
        \s*$
    """,
    re.VERBOSE,
)


def barber_pole() -> dict:
    """The indeterminate sentinel — the honest 'no checklist published' floor.

    Returns a FRESH dict each call (no shared mutable state).
    """
    return {
        "total": 0,
        "done": 0,
        "items": [],
        "current": None,
        "indeterminate": True,
        "fraction": 0.0,
    }


def _is_item_line(line: str) -> bool:
    return _ITEM_RE.match(line) is not None


def _is_blank(line: str) -> bool:
    return line.strip() == ""


def _parse_item(line: str) -> dict:
    m = _ITEM_RE.match(line)
    assert m is not None  # caller guarantees this
    mark = m.group("mark")
    done = mark in _DONE_MARKERS
    return {"text": m.group("text").strip(), "done": done}


def _last_block_in_text(text: str) -> Optional[list[dict]]:
    """Return the LAST checklist block in ``text``, or None.

    A block is a maximal contiguous run of item lines. A 1-line block is kept
    only if it stands alone (no non-blank prose directly above or below it);
    blocks of >= 2 lines always qualify.
    """
    lines = text.splitlines()
    n = len(lines)
    last: Optional[list[dict]] = None

    i = 0
    while i < n:
        if not _is_item_line(lines[i]):
            i += 1
            continue
        # Collect a maximal contiguous run of item lines.
        start = i
        block: list[dict] = []
        while i < n and _is_item_line(lines[i]):
            block.append(_parse_item(lines[i]))
            i += 1
        end = i  # exclusive

        if len(block) >= 2:
            last = block
            continue

        # Single-item block: accept only if it stands alone.
        above_blank = start == 0 or _is_blank(lines[start - 1])
        below_blank = end >= n or _is_blank(lines[end])
        if above_blank and below_blank:
            last = block
        # else: a stray "[ ]" inside prose — ignore it.

    return last


def parse_checklist(texts: list[str]) -> dict:
    """Parse the agent's published checklist from ordered assistant texts.

    ``texts`` is oldest -> newest. The newest text that contains a checklist
    block wins; within a text, the last block wins. Returns:
        {"total", "done", "items", "current", "indeterminate", "fraction"}
    With no checklist found anywhere, returns :func:`barber_pole`.
    """
    chosen: Optional[list[dict]] = None
    for text in texts:
        if not text:
            continue
        block = _last_block_in_text(text)
        if block is not None:
            chosen = block  # later texts override earlier ones

    if not chosen:
        return barber_pole()

    total = len(chosen)
    done = sum(1 for it in chosen if it["done"])
    current = next((it["text"] for it in chosen if not it["done"]), None)
    fraction = (done / total) if total else 0.0

    return {
        "total": total,
        "done": done,
        "items": chosen,
        "current": current,
        "indeterminate": False,
        "fraction": fraction,
    }
