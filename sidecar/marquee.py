"""Marquee — low-fidelity liveness signal for a running agent.

The marquee is a scrolling *tail* of an agent's recent transcript output. Its
only job is to say "this agent is running and moving" — it is NOT an audit
surface, so fidelity is deliberately low. The source is the agent's own recent
events (the merged cross-agent stream): assistant text and tool_use blocks.

Event shape (matching the sidecar's assistant/tool events)::

    {"type": "assistant", "content": [
        {"type": "text", "text": "..."},
        {"type": "tool_use", "name": "Read", "input": {"file_path": "app.tsx"}},
        {"type": "tool_use", "name": "Bash", "input": {"command": "npm test"}},
    ]}

Pure logic only — no I/O, no backend. Given a list of events it derives a single
line to display; when nothing new is renderable it reports idle so the UI can
hold its last line.
"""

from __future__ import annotations

import ntpath
import posixpath

__all__ = ["activity_verb", "marquee_line", "is_idle"]

# Tools whose activity verb carries a file path (basename shown).
_FILE_TOOLS = ("Read", "Edit", "Write")

# Max chars of a Bash command surfaced in its activity verb.
_BASH_CMD_LEN = 40

_ELLIPSIS = "…"


def _normalize_ws(text: str) -> str:
    """Collapse all runs of whitespace (incl. newlines/tabs) to single spaces."""
    return " ".join(text.split())


def _basename(path: str) -> str:
    """Basename that works for both POSIX and Windows separators."""
    # Try both separator conventions and take whichever strips more, so a
    # Windows path handled on POSIX (or vice versa) still yields the leaf.
    leaf = posixpath.basename(path)
    leaf = ntpath.basename(leaf)
    return leaf


def activity_verb(block: dict) -> str | None:
    """Derive a short activity verb from a single content block.

    Returns e.g. ``"→ Read app.tsx"`` (Read/Edit/Write → file basename),
    ``"→ Bash npm test"`` (Bash → normalized command prefix), or
    ``"→ <ToolName>"`` for other tools. Returns ``None`` for non-tool blocks.
    """
    if not isinstance(block, dict) or block.get("type") != "tool_use":
        return None

    name = str(block.get("name") or "").strip()
    if not name:
        return None

    inp = block.get("input")
    if not isinstance(inp, dict):
        inp = {}

    if name in _FILE_TOOLS:
        path = inp.get("file_path")
        if isinstance(path, str) and path.strip():
            leaf = _basename(path.strip())
            if leaf:
                return f"→ {name} {leaf}"
        return f"→ {name}"

    if name == "Bash":
        command = inp.get("command")
        if isinstance(command, str):
            command = _normalize_ws(command)
            if command:
                return f"→ {name} {command[:_BASH_CMD_LEN]}"
        return f"→ {name}"

    return f"→ {name}"


def _block_snippet(block: dict) -> str | None:
    """Renderable one-line snippet for a content block, or None if empty."""
    if not isinstance(block, dict):
        return None

    btype = block.get("type")
    if btype == "text":
        text = block.get("text")
        if isinstance(text, str):
            text = _normalize_ws(text)
            if text:
                return text
        return None

    # tool_use (and anything else the verb helper understands)
    return activity_verb(block)


def _latest_snippet(events: list[dict]) -> str | None:
    """Newest-first scan for the most recent meaningful renderable snippet."""
    if not events:
        return None
    for event in reversed(events):
        if not isinstance(event, dict):
            continue
        content = event.get("content")
        if not isinstance(content, list):
            continue
        for block in reversed(content):
            snippet = _block_snippet(block)
            if snippet:
                return snippet
    return None


def marquee_line(events: list[dict], max_len: int = 120) -> str:
    """Derive a single scrolling line from the most recent meaningful output.

    Scans ``events`` newest-first and returns the latest text snippet
    (collapsed to one whitespace-normalized line) or the latest activity verb,
    truncated to ``max_len`` with a trailing ellipsis. Empty / no output → "".
    """
    snippet = _latest_snippet(events)
    if not snippet:
        return ""
    if max_len > 0 and len(snippet) > max_len:
        # Reserve one char for the ellipsis so the result stays within max_len.
        return snippet[: max(0, max_len - 1)] + _ELLIPSIS
    return snippet


def is_idle(events: list[dict]) -> bool:
    """True when there's no recent renderable output (UI holds its last line)."""
    return _latest_snippet(events) is None
