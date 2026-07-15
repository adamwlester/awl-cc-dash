"""
JSONL transcript parser for Claude Code sessions.

Claude Code writes session transcripts as JSONL files under:
  ~/.claude/projects/{project-hash}/{session-id}.jsonl

Each line is a JSON object with a "type" field:
  - "user"      : user messages
  - "assistant"  : assistant responses (may have thinking + text blocks)
  - "file-history-snapshot" : file state snapshots
  - "last-prompt" : final prompt marker

This module finds and parses these transcripts.
"""

import json
import re
from .paths import WSL_CLAUDE_PROJECTS


def _encode_cwd(cwd):
    """Encode a cwd the way Claude Code names its transcript project dir.

    Claude Code replaces every non-alphanumeric character in the absolute cwd
    with a single dash — this covers '/', '.', '_', spaces, etc., not just '/'.
    e.g. /mnt/c/Users/lester/.scratch -> -mnt-c-Users-lester--scratch
    """
    return re.sub(r"[^a-zA-Z0-9]", "-", cwd)


def _resolve_project_dir(bridge, cwd):
    """Resolve the ~/.claude/projects subdir for a session's cwd.

    The encoding is lossy (many distinct chars collapse to '-'), so rather than
    trust a reconstructed name blindly we confirm it against the real directory
    names under projects/. Falls back to a dash-collapsed match so we still
    resolve even if Claude Code's encoding differs in some edge case (e.g.
    consecutive separators). Returns the WSL path to the project dir, or None.
    """
    encoded = _encode_cwd(cwd)
    base = WSL_CLAUDE_PROJECTS

    # Fast path: the encoded directory exists as-is.
    try:
        hit = bridge._run(f"test -d '{base}/{encoded}' && echo OK || true")
    except Exception:
        hit = ""
    if hit.strip() == "OK":
        return f"{base}/{encoded}"

    # Derive from the real listing: match the encoded cwd against actual dir
    # names, comparing dash-collapsed forms for robustness.
    try:
        listing = bridge._run(f"ls -1 {base} 2>/dev/null || true")
    except Exception:
        return None
    names = [n.strip() for n in listing.strip().split("\n") if n.strip()]
    target = re.sub(r"-+", "-", encoded)
    for name in names:
        if re.sub(r"-+", "-", name) == target:
            return f"{base}/{name}"
    return None


def _resolve_session_id(bridge, session_name):
    """The claude ``--session-id`` (uuid) for a tmux session, or None.

    The bridge records it in ``_session_uuids`` at ``create()``. After a sidecar
    restart that resumed a still-alive session, the driver re-registers the id
    (persisted in the runtime record) before reading — so this in-memory map is
    authoritative for every session the dashboard owns. A session NOT launched by
    this bridge (no entry) falls through to the legacy newest-file heuristic.
    """
    return getattr(bridge, "_session_uuids", {}).get(session_name)


def find_transcript(bridge, session_name):
    """Find the JSONL transcript file for a session.

    Strategy:
    1. Get the session's cwd from tmux → resolve its `~/.claude/projects` subdir.
    2. Resolve the session's OWN transcript by its claude ``--session-id``: the
       file is ``<session-id>.jsonl``. This is collision-proof — two agents in
       the same cwd (same project dir) each resolve to their own file. The id
       comes from the bridge's in-memory map (set at create) or, after a resume,
       is recovered from the live process args (see ``_resolve_session_id``).
    3. Only when the id is unknown (a session not launched by this bridge) fall
       back to the legacy single-file / newest-file heuristic.

    Args:
        bridge: TmuxBridge instance (for running WSL commands).
        session_name: The tmux session name.

    Returns:
        WSL path to the JSONL file, or None if not found.
    """
    try:
        # Get the cwd of the session's pane
        cwd = bridge._tmux(
            f"display-message -t '{session_name}' -p '#{{pane_current_path}}'"
        )
    except Exception:
        cwd = None

    if not cwd:
        return None
    cwd = cwd.strip()

    # Find the projects/ subdir Claude Code uses for this cwd (matches its full
    # non-alphanumeric→'-' encoding, verified against the real dir listing).
    project_dir = _resolve_project_dir(bridge, cwd)
    if not project_dir:
        return None

    # Resolve THIS session's transcript by its known session id. When the id is
    # known but the file doesn't exist yet (e.g. before the first turn), return
    # None rather than fall through to "newest" — newest could be a co-located
    # sibling's transcript, which is exactly the collision we're fixing.
    sid = _resolve_session_id(bridge, session_name)
    if sid:
        candidate = f"{project_dir}/{sid}.jsonl"
        try:
            hit = bridge._run(f"test -f '{candidate}' && echo OK || true")
        except Exception:
            hit = ""
        return candidate if hit.strip() == "OK" else None

    # --- Legacy fallback (unknown session id) --------------------------------
    # Only reached for sessions this bridge didn't launch with --session-id.
    try:
        files = bridge._run(f"ls {project_dir}/*.jsonl 2>/dev/null || true")
    except Exception:
        return None

    if not files.strip():
        return None

    jsonl_files = [f.strip() for f in files.strip().split("\n") if f.strip()]

    if not jsonl_files:
        return None

    # If there's only one, use it. Otherwise, find the most recently modified.
    if len(jsonl_files) == 1:
        return jsonl_files[0]

    # Find the newest file
    try:
        newest = bridge._run(
            f"ls -t {project_dir}/*.jsonl 2>/dev/null | head -1"
        )
        return newest.strip() if newest.strip() else jsonl_files[0]
    except Exception:
        return jsonl_files[0]


def parse_transcript(bridge, filepath, last_n=None, types=None):
    """Parse a JSONL transcript file.

    Args:
        bridge: TmuxBridge instance (for running WSL commands).
        filepath: WSL path to the JSONL file.
        last_n: If set, only return the last N entries.
        types: If set, filter to these message types.

    Returns:
        list of parsed JSONL entries (dicts).
    """
    if last_n:
        raw = bridge._run(f"tail -n {last_n * 3} '{filepath}'", timeout=15)
    else:
        raw = bridge._run(f"cat '{filepath}'", timeout=30)

    entries = []
    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        if types and entry.get("type") not in types:
            continue

        entries.append(entry)

    if last_n:
        entries = entries[-last_n:]

    return entries


def consume_transcript_chunk(chunk):
    """Parse complete JSONL lines out of a raw transcript byte chunk. Pure.

    The §11 #34 incremental-read half: ``poll_bundle`` returns the transcript
    bytes from a caller-tracked offset; this consumes only up to the LAST
    newline — the partial trailing line (a write in progress, possibly cutting
    a multi-byte character) is left unconsumed and re-read whole next poll, so
    a torn entry can never be emitted or corrupt the offset arithmetic.
    Unparseable complete lines are skipped but still consumed (mirroring
    ``parse_transcript``'s drop-bad-lines behavior).

    Args:
        chunk: Raw bytes from the current offset (as from ``poll_bundle``).

    Returns:
        ``(entries, consumed_bytes)`` — parsed dict entries in order, and how
        many bytes the caller's offset may advance.
    """
    if not chunk:
        return [], 0
    cut = chunk.rfind(b"\n")
    if cut < 0:
        return [], 0
    consumed = cut + 1
    entries = []
    for line in chunk[:consumed].split(b"\n"):
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line.decode("utf-8", errors="replace")))
        except json.JSONDecodeError:
            continue
    return entries, consumed


# --------------------------------------------------------------------------- #
# /context breakdown + compaction history (§7.18, §11 #30)
# --------------------------------------------------------------------------- #

# The per-category rows the context dropdown renders off `/context`. Aliases map
# the rendered labels onto one stable key each — the parse target proven live by
# tests/test_context_compact_live.py (Lever A), whose parser this lifts.
CONTEXT_CATEGORY_ALIASES = {
    "system prompt": "system_prompt",
    "system tools": "system_tools",
    "mcp tools": "mcp_tools",
    "custom agents": "custom_agents",
    "memory files": "memory",
    "skills": "skills",
    "messages": "messages",
    "free space": "free_space",
    "autocompact buffer": "autocompact_buffer",
}
# Canonical row order for serialization (a stable UI ordering).
CONTEXT_CATEGORY_ORDER = tuple(CONTEXT_CATEGORY_ALIASES.values())


def parse_context_output(text):
    """Parse a `/context` screen (or its transcript markdown table) into rows.

    Pure function (no live session), lifted from the proving spike
    (``test_context_compact_live`` Lever A — WORKS on CC 2.1.198). Scans each
    line for a known category label and pulls a token count (``12.3k``,
    ``1,234``, ``1234 tokens``) and/or a percent (``(6.2%)`` / ``6.2%``) off the
    same line. A category counts as parsed only if it yielded a numeric token OR
    percent value. Works on the raw screen scrape AND on the markdown table
    `/context` also records into the JSONL transcript (``| System prompt | 9k |
    0.9% |`` — each row keeps label + numbers on one line).

    Returns:
        ``{stable_key: {"tokens": int|None, "percent": float|None, "raw": str}}``
        — empty when nothing parsed (the honest miss, never a guess).
    """
    parsed = {}
    for raw_line in (text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        low = line.lower()
        for label, key in CONTEXT_CATEGORY_ALIASES.items():
            if label not in low:
                continue
            pct_m = re.search(r"(\d+(?:\.\d+)?)\s*%", line)
            tok_m = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*([kKmM])?\s*(?:tokens?\b)?", line)
            percent = float(pct_m.group(1)) if pct_m else None
            tokens = None
            if tok_m and tok_m.group(1):
                num = float(tok_m.group(1).replace(",", ""))
                suffix = (tok_m.group(2) or "").lower()
                if suffix == "k":
                    num *= 1_000
                elif suffix == "m":
                    num *= 1_000_000
                tokens = int(num)
            if percent is None and tokens is None:
                continue
            parsed.setdefault(key, {"tokens": tokens, "percent": percent, "raw": line})
            break
    return parsed


def find_context_markdown(entries):
    """The `/context` output ALSO lands in the JSONL as a local-command ``user``
    entry rendered as a markdown table (spike bonus discovery — a steadier
    read-back than the raw screen). Returns the newest such text, or None."""
    for e in reversed(entries):
        if not isinstance(e, dict) or e.get("type") != "user":
            continue
        content = (e.get("message") or {}).get("content")
        text = content if isinstance(content, str) else str(content)
        if "Context Usage" in text and "| System prompt" in text:
            return text
    return None


def compact_history(entries):
    """Derive the compaction history from transcript entries. Pure.

    A real ``/compact`` writes a ``type:"system" subtype:"compact_boundary"``
    entry carrying ``compactMetadata`` (trigger / preTokens / postTokens /
    durationMs — live-proven, ``test_context_compact_live`` Lever B). This is
    the §7.18 compaction history: count / type / when, plus the token deltas.

    Returns:
        ``{"count": N, "boundaries": [{"when", "type", "pre_tokens",
        "post_tokens", "duration_ms"}, ...]}`` in transcript order
        (``type`` = the trigger: ``"manual"`` | ``"auto"``).
    """
    boundaries = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        if e.get("type") == "system" and e.get("subtype") == "compact_boundary":
            meta = e.get("compactMetadata") or {}
            boundaries.append({
                "when": e.get("timestamp"),
                "type": meta.get("trigger"),
                "pre_tokens": meta.get("preTokens"),
                "post_tokens": meta.get("postTokens"),
                "duration_ms": meta.get("durationMs"),
            })
    return {"count": len(boundaries), "boundaries": boundaries}


def extract_messages(entries):
    """Extract a simplified conversation from transcript entries.

    Returns a list of dicts with role, content, and timestamp.
    Useful for getting a clean conversation view.
    """
    messages = []
    for entry in entries:
        entry_type = entry.get("type")

        if entry_type == "user":
            msg = entry.get("message", {})
            content = msg.get("content", "")
            # content can be a string or a list of blocks
            if isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif isinstance(block, str):
                        text_parts.append(block)
                content = "\n".join(text_parts)
            messages.append({
                "role": "user",
                "content": content,
                "timestamp": entry.get("timestamp", ""),
            })

        elif entry_type == "assistant":
            msg = entry.get("message", {})
            blocks = msg.get("content", [])
            text_parts = []
            for block in blocks:
                if isinstance(block, dict):
                    if block.get("type") == "text":
                        text_parts.append(block.get("text", ""))
                    elif block.get("type") == "tool_use":
                        text_parts.append(
                            f"[tool: {block.get('name', '?')}]"
                        )
            if text_parts:
                messages.append({
                    "role": "assistant",
                    "content": "\n".join(text_parts),
                    "timestamp": entry.get("timestamp", ""),
                    "model": msg.get("model", ""),
                })

    return messages
