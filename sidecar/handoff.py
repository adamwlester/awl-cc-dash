"""Handoff artifacts (§7.19, §8.4, §11 #16) — the summary layered on Handoff.

When an agent is handed off (the fork-with-context-carryover #15 built), #16 adds
a generated **summary/handoff report** on top of the plain context carry-over: a
concise, structured note — what the agent was doing, the decisions it made, and
the current state / what's pending — so the picking-up agent (or the operator)
doesn't have to re-read the whole conversation.

The seam is small and testable:

  * :func:`transcript_text_from_events` — a PURE reducer from a session's already
    fanned-out events (assistant/user text blocks) to a plain-text transcript
    excerpt (the tail, most recent). No SDK, no I/O.
  * :func:`compose_handoff_doc` — a PURE wrapper that frames the LLM summary body
    with a small provenance header (title + from-agent + timestamp).
  * :func:`generate_and_store_handoff` — orchestration: run the utility-LLM pass
    over the excerpt, compose the doc, and persist it as a Library doc under the
    project's ``docs/`` (§8.4) with provenance (:mod:`library`). The LLM call is
    injectable (``generate=``) so the assembly/plumbing unit-tests hermetically
    and only the actual generation is a live concern.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Awaitable, Callable, Optional

import library
import utility_llm

# Cap the transcript excerpt fed to the utility LLM: the report is a distillation,
# and the tail carries the freshest state (§11 #16 — "recent transcript").
_EXCERPT_LIMIT = 12000


def _block_text(content: Any) -> str:
    """Flatten a message ``content`` (str, or a list of typed blocks) to text.

    Only human-readable text is kept — ``text`` blocks (and bare strings); tool
    calls / tool results and other non-text blocks are skipped, mirroring
    :func:`utility_llm._text_of`."""
    if isinstance(content, str):
        return content
    if not content:
        return ""
    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict):
            t = block.get("text")
            if isinstance(t, str) and (block.get("type") in (None, "text")):
                parts.append(t)
    return "\n".join(p for p in parts if p)


def transcript_text_from_events(events: list[dict], *, limit: int = _EXCERPT_LIMIT) -> str:
    """Reduce a session's events to a plain-text transcript excerpt (the tail).

    Keeps only ``assistant`` / ``user`` message text, in order, tagged by role; the
    most recent ``limit`` characters are returned (the freshest state is what a
    handoff needs). Empty when nothing textual has streamed yet."""
    lines: list[str] = []
    for ev in events or []:
        role = ev.get("type")
        if role not in ("assistant", "user"):
            continue
        text = _block_text(ev.get("content")).strip()
        if text:
            lines.append(f"{role}: {text}")
    joined = "\n\n".join(lines)
    return joined[-limit:] if limit and len(joined) > limit else joined


def _slug(value: str | None) -> str:
    """A filesystem/URL-safe slug for a doc filename (lowercase, ``-`` separators)."""
    s = re.sub(r"[^a-z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return s or "agent"


def build_handoff_filename(source_identity: dict | None, *,
                           now: datetime | None = None) -> str:
    """``handoff-<name-or-agent>-<YYYYMMDD-HHMMSS>.md`` (unique per second)."""
    name = (source_identity or {}).get("name") if isinstance(source_identity, dict) else None
    stamp = (now or datetime.now()).strftime("%Y%m%d-%H%M%S")
    return f"handoff-{_slug(name)}-{stamp}.md"


def compose_handoff_doc(summary_body: str, *, source_identity: dict | None,
                        source_session_id: str | None,
                        now: datetime | None = None) -> str:
    """Frame the LLM summary body with a small provenance header (§8.5 provenance
    is ALSO stamped in the sidecar; the header is the human-visible echo)."""
    ident = source_identity if isinstance(source_identity, dict) else {}
    name = ident.get("name")
    number = ident.get("number")
    who = name or (f"agent {number}" if number is not None else "agent")
    ts = (now or datetime.now()).isoformat(timespec="seconds")
    header = f"# Handoff — {who}\n\n_Generated {ts}"
    if source_session_id:
        header += f" · from session {source_session_id}"
    header += "_\n"
    body = (summary_body or "").strip() or "_(no transcript content to summarize yet)_"
    return f"{header}\n{body}\n"


# The generation callable: ``(excerpt, model) -> report body``. Defaults to the
# utility-LLM pass; injectable so the plumbing tests hermetically.
GenerateFn = Callable[[str, Optional[str]], Awaitable[str]]


async def generate_and_store_handoff(
    cwd: str | None,
    transcript_text: str,
    *,
    source_session_id: str | None,
    source_identity: dict | None = None,
    target_session_id: str | None = None,
    model: str | None = None,
    generate: Optional[GenerateFn] = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Generate the handoff summary and persist it as a Library doc (§8.4, §11 #16).

    Runs the utility-LLM pass (``generate`` — defaults to
    :func:`utility_llm.handoff_report`) over ``transcript_text``, frames it with a
    provenance header, writes it to ``<project>/.awl-cc-dash/docs/`` via
    :func:`library.create_document`, and stamps provenance (created-by = the
    source agent's name/id; session = the source session) via
    :func:`library.set_provenance`. Requires a ``cwd`` with a project home (the
    Library is project-scoped, §8.2) — raises ``ValueError`` otherwise. Returns
    ``{filename, path, subdir, summary, created_by, target_session_id}``."""
    gen = generate or utility_llm.handoff_report
    summary_body = await gen(transcript_text, model)
    content = compose_handoff_doc(
        summary_body, source_identity=source_identity,
        source_session_id=source_session_id, now=now)
    filename = build_handoff_filename(source_identity, now=now)
    doc = library.create_document(cwd, filename, content, subdir="docs")
    created_by = (source_identity or {}).get("name") if isinstance(source_identity, dict) else None
    created_by = created_by or source_session_id
    library.set_provenance(doc["path"], created_by=created_by, session=source_session_id)
    return {
        "filename": doc["filename"],
        "path": doc["path"],
        "subdir": doc["subdir"],
        "summary": summary_body,
        "created_by": created_by,
        "target_session_id": target_session_id,
    }
