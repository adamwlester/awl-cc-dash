"""Per-project state store — the §8.2 ``state/`` persistence layer (§11 #3/#4/#42).

Implements the persist-vs-derive contract (§8.3): everything in the Persist rows
is small JSON **written as it changes** (write-through — no shutdown snapshot to
lose), living in the open project's ``<project>/.awl-cc-dash/state/``:

  * ``agents.json``    — the project roster: session records + identity + launch
                         config + ``claude_session_id`` + resolved transcript path,
                         plus the permanently **retired identity numbers**.
  * ``inbox.json``     — persisted Inbox items (open-ended type set, §7.8).
  * ``links.json``     — agent-to-agent links (full config + runtime counters).
  * ``bookmarks.json`` — read-watermarks (scratchpad per agent; link shared-context
                         per source→target), i.e. the ``watermark`` module's marks.
  * ``routing.jsonl``  — append-only thin routing overlay: ``{anchor_id, source,
                         recipients}`` for NON-default routing only (§8.6).

Mechanics (§8.7): **atomic write-replace per file** (a per-write-unique tmp name
+ ``os.replace``) so concurrent writers can't tear JSON; append-only for the
``.jsonl``; every committed JSON carries a ``schema_version`` stamp (#42 —
readers tolerate a missing/older stamp; migration machinery stays deferred until
a format changes). Every read→modify→write pair here runs under one module-level
lock (``_IO_LOCK``) so concurrent in-process writers (request handlers, hook
callbacks, threads) can't interleave and lose each other's updates. Writes are
also **merge-shaped, not rebuild-shaped**: ``persist_inbox_for`` replaces only
the triggering agent's slice of ``inbox.json`` (other agents' items — loaded or
not — stay untouched), and ``persist_links_for`` merges one link's row by ``id``
into every candidate ``links.json`` (so a tombstoned link whose endpoints are no
longer registered never vanishes from disk).

Loading is **lazy per project** (§11 #3): the first session whose canonical root
resolves to a project triggers :func:`load_project`, which seeds the in-memory
feature modules (inbox / links / watermark / deletion) and reloads the scratchpad
board from its ``docs/scratchpad.md`` (the ``.md`` is the board's persistence —
§8.3). Thereafter the modules' persist hooks write straight through here.

The scratchpad ``.md`` round-trip: posts are mirrored as
``- **author** (ts): text`` lines with every continuation line (a post whose
text contained newlines) indented two spaces; on reload each UNINDENTED
matching line becomes a post (seq = line order, 1..N — stable because the board
is append-only and rewritten whole) and indented lines re-attach to the
preceding post with the prefix stripped, so text that itself looks like a post
line never splits into a phantom post. On load, the project's persisted
``scratch:{key}:*`` read-watermarks clamp to the reloaded board length (legacy
global-seq marks could exceed it and would swallow new posts forever).
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Callable

import storage
import inbox
import links
import watermark
import deletion
import scratchpad

logger = logging.getLogger("awl-sidecar.state")

SCHEMA_VERSION = 1

# Canonical roots whose state/ has been loaded this process (idempotence guard).
_LOADED: set[str] = set()

# agent_id -> canonical project key, so persist hooks fired with only an agent
# id can route to the right project store. Registered by the session layer.
_AGENT_PROJECT: dict[str, str] = {}

# One lock over every read→modify→write pair in this module (§8.7 concurrent
# writers): request handlers, hook callbacks, and worker threads all funnel
# their state-file updates through here, so no writer can read a file, be
# interleaved by another writer, and then clobber that writer's update.
_IO_LOCK = threading.Lock()


def reset() -> None:
    """Test/lifecycle hook: forget loads + agent routing (files stay put)."""
    _LOADED.clear()
    _AGENT_PROJECT.clear()


# ---------------------------------------------------------------------------
# Atomic file primitives
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    """Atomic write-replace (§8.7): tmp file + ``os.replace`` — never torn.

    The tmp name is UNIQUE per write (``.{pid}-{threadid}.tmp``) so two
    concurrent writers can never collide on one tmp file; ``os.replace``
    consumes the tmp, which is its cleanup.
    """
    data = {"schema_version": SCHEMA_VERSION, **data}
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}-{threading.get_ident()}.tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Paths (all under <project>/.awl-cc-dash/state/)
# ---------------------------------------------------------------------------

def _state_path(project_key: str, name: str) -> Path | None:
    d = storage.state_dir(project_key)
    return None if d is None else d / name


def agents_path(project_key: str) -> Path | None:
    return _state_path(project_key, "agents.json")


def inbox_path(project_key: str) -> Path | None:
    return _state_path(project_key, "inbox.json")


def links_path(project_key: str) -> Path | None:
    return _state_path(project_key, "links.json")


def bookmarks_path(project_key: str) -> Path | None:
    return _state_path(project_key, "bookmarks.json")


def routing_path(project_key: str) -> Path | None:
    return _state_path(project_key, "routing.jsonl")


def archive_path(project_key: str) -> Path | None:
    return _state_path(project_key, "archive.json")


# ---------------------------------------------------------------------------
# Agent → project routing (persist hooks only get an agent id)
# ---------------------------------------------------------------------------

def register_agent(agent_id: str, cwd: str | None) -> None:
    """Bind an agent id to its canonical project key (create/reconnect time)."""
    key = storage.project_key(cwd)
    if key:
        _AGENT_PROJECT[agent_id] = key


def unregister_agent(agent_id: str) -> None:
    _AGENT_PROJECT.pop(agent_id, None)


def project_of(agent_id: str) -> str | None:
    return _AGENT_PROJECT.get(agent_id)


# ---------------------------------------------------------------------------
# Roster (agents.json) — records + retired numbers
# ---------------------------------------------------------------------------

def load_roster(project_key: str) -> dict[str, dict[str, Any]]:
    """The project's session records, keyed by sidecar session id."""
    p = agents_path(project_key)
    if p is None:
        return {}
    agents = _read_json(p).get("agents")
    return agents if isinstance(agents, dict) else {}


def save_roster_record(project_key: str, record: dict[str, Any]) -> None:
    """Insert/update one session record in the project roster (write-through)."""
    sid = record.get("session_id")
    p = agents_path(project_key)
    if not sid or p is None:
        return
    with _IO_LOCK:
        data = _read_json(p)
        agents = data.get("agents")
        if not isinstance(agents, dict):
            agents = {}
        agents[sid] = record
        data["agents"] = agents
        data.setdefault("retired_numbers", [])
        _write_json(p, data)


def remove_roster_record(project_key: str, session_id: str) -> bool:
    p = agents_path(project_key)
    if p is None:
        return False
    with _IO_LOCK:
        data = _read_json(p)
        agents = data.get("agents")
        if not isinstance(agents, dict) or session_id not in agents:
            return False
        del agents[session_id]
        data["agents"] = agents
        _write_json(p, data)
    return True


def load_retired_numbers(project_key: str) -> list[int]:
    p = agents_path(project_key)
    if p is None:
        return []
    nums = _read_json(p).get("retired_numbers")
    return [int(n) for n in nums] if isinstance(nums, list) else []


def persist_retired_number(project_key: str, number: int) -> None:
    """Record a permanently-retired identity number (§7.12 — never reused)."""
    p = agents_path(project_key)
    if p is None:
        return
    with _IO_LOCK:
        data = _read_json(p)
        nums = data.get("retired_numbers")
        nums = [int(n) for n in nums] if isinstance(nums, list) else []
        if int(number) not in nums:
            nums.append(int(number))
        data["retired_numbers"] = sorted(nums)
        data.setdefault("agents", {})
        _write_json(p, data)


# ---------------------------------------------------------------------------
# Agent archive (archive.json) — Retire = deep-freeze, distinct-id records
# ---------------------------------------------------------------------------
#
# The §11 #18 Agent archive: retiring an agent DEEP-FREEZES its record into a
# sibling ``state/archive.json`` (a distinct-id table, keyed by ``archive_id``),
# written through the same atomic write-replace + ``schema_version`` model as
# ``agents.json``. Records are light — the transcript is REFERENCED in place,
# never copied (§8.6). Delete stays a TRUE wipe (§7.12) distinct from archive;
# ``remove_archive_record`` is the real delete of an archived row.


def load_archive(project_key: str) -> dict[str, dict[str, Any]]:
    """The project's archived agent records, keyed by distinct ``archive_id``."""
    p = archive_path(project_key)
    if p is None:
        return {}
    recs = _read_json(p).get("archived")
    return recs if isinstance(recs, dict) else {}


def get_archive_record(project_key: str, archive_id: str) -> dict[str, Any] | None:
    """One archived record from a project by its distinct id (or ``None``)."""
    return load_archive(project_key).get(archive_id)


def save_archive_record(project_key: str, record: dict[str, Any]) -> None:
    """Insert one archived record into the project archive (write-through).

    Keyed by the record's distinct ``archive_id``. A no-op when the record has
    no ``archive_id`` or the project has no on-disk home (cwd-less agents don't
    archive — the archive is per-project, §8.2). Atomic write-replace + stamped
    ``schema_version`` like every other state file.
    """
    aid = record.get("archive_id")
    p = archive_path(project_key)
    if not aid or p is None:
        return
    with _IO_LOCK:
        data = _read_json(p)
        archived = data.get("archived")
        if not isinstance(archived, dict):
            archived = {}
        archived[aid] = record
        data["archived"] = archived
        _write_json(p, data)


def remove_archive_record(project_key: str, archive_id: str) -> bool:
    """TRUE-delete one archived record (§7.12) — a real wipe of the archive row.

    Returns True when a row was removed, False when it was already absent.
    """
    p = archive_path(project_key)
    if p is None:
        return False
    with _IO_LOCK:
        data = _read_json(p)
        archived = data.get("archived")
        if not isinstance(archived, dict) or archive_id not in archived:
            return False
        del archived[archive_id]
        data["archived"] = archived
        _write_json(p, data)
    return True


def all_archived_records() -> list[dict[str, Any]]:
    """Every archived record across every known project (project-first).

    Mirrors ``runtime_store.all_records()`` for the live roster: aggregates the
    archive of every project in the 🏠 projects index so the operator sees the
    whole archive without a per-project call. Distinct ids never collide, so a
    plain first-writer-wins de-dup is enough.
    """
    out: dict[str, dict[str, Any]] = {}
    for key in known_projects():
        for aid, rec in load_archive(key).items():
            out.setdefault(aid, rec)
    return list(out.values())


def find_archive_record(archive_id: str) -> tuple[str, dict[str, Any]] | None:
    """Locate an archived record by id across known projects → ``(key, record)``."""
    for key in known_projects():
        rec = get_archive_record(key, archive_id)
        if rec is not None:
            return key, rec
    return None


def delete_archived_anywhere(archive_id: str) -> bool:
    """TRUE-delete an archived record wherever it lives (§7.12). True if removed."""
    for key in known_projects():
        if remove_archive_record(key, archive_id):
            return True
    return False


# ---------------------------------------------------------------------------
# Projects index (🏠 projects.json, §3.5) — known roots + last-used
# ---------------------------------------------------------------------------

def touch_projects_index(project_key: str) -> None:
    """Upsert a canonical root into the known-projects index (cold discovery)."""
    from datetime import datetime
    path = storage.projects_index_path()
    with _IO_LOCK:
        data = _read_json(path)
        projects = data.get("projects")
        if not isinstance(projects, dict):
            projects = {}
        entry = projects.get(project_key)
        entry = dict(entry) if isinstance(entry, dict) else {}
        entry["last_used"] = datetime.now().isoformat()
        projects[project_key] = entry
        data["projects"] = projects
        _write_json(path, data)


def known_projects() -> dict[str, dict[str, Any]]:
    """The known-projects index: canonical root -> {last_used, …}."""
    projects = _read_json(storage.projects_index_path()).get("projects")
    return projects if isinstance(projects, dict) else {}


# ---------------------------------------------------------------------------
# Write-through persistence (the persist hooks' targets)
# ---------------------------------------------------------------------------

def persist_inbox_for(agent_id: str) -> None:
    """Merge ONE agent's inbox slice into its project's ``inbox.json``.

    Per-agent merge, never a rebuild: only the triggering agent's key is
    set/replaced (deleted when its item list is empty — the §7.12 hard-delete
    wipe); every other agent's slice in the file — including agents that are
    unloaded or no longer registered — stays untouched, so a write for one
    agent can never silently drop another's persisted items.
    """
    key = project_of(agent_id)
    if not key:
        return
    p = inbox_path(key)
    if p is None:
        return
    with _IO_LOCK:
        data = _read_json(p)
        items = data.get("items")
        items = dict(items) if isinstance(items, dict) else {}
        lst = inbox.items_for(agent_id, include_resolved=True)
        if lst:
            items[agent_id] = lst
        else:
            items.pop(agent_id, None)
        _write_json(p, {"items": items})


def persist_links_for(link: Any) -> None:
    """Merge ONE link's row (by ``id``) into every candidate ``links.json``.

    Candidates are the projects of the link's currently-registered endpoints
    PLUS any known project whose ``links.json`` already contains this link id —
    so a tombstoned link of a deleted/unregistered agent (§7.12: kept,
    attributed, inactive) still updates in place instead of vanishing on the
    next write. In each file the row is updated-or-appended by ``id`` (removed
    when the link no longer exists in the live store); rows for OTHER links are
    never dropped, whether or not their agents are registered.
    """
    link_id = getattr(link, "id", None)
    if not link_id:
        return
    keys = {k for k in (project_of(link.a), project_of(link.b)) if k}
    for key in known_projects():
        if key in keys:
            continue
        p = links_path(key)
        if p is None or not p.is_file():
            continue
        rows = _read_json(p).get("links")
        if isinstance(rows, list) and any(
                isinstance(r, dict) and r.get("id") == link_id for r in rows):
            keys.add(key)
    live = links.get_link(link_id)
    for key in keys:
        p = links_path(key)
        if p is None:
            continue
        with _IO_LOCK:
            data = _read_json(p)
            rows = data.get("links")
            rows = [r for r in rows if isinstance(r, dict)] \
                if isinstance(rows, list) else []
            replaced = False
            for i, r in enumerate(rows):
                if r.get("id") == link_id:
                    if live is not None:
                        rows[i] = live.to_dict()
                    else:
                        del rows[i]   # the link was removed from the store
                    replaced = True
                    break
            if live is not None and not replaced:
                rows.append(live.to_dict())
            _write_json(p, {"links": rows})


def persist_bookmark(key: str) -> None:
    """Write-through one advanced watermark into its project's bookmarks.json.

    Key routing: ``scratch:{project_key}:{agent}`` embeds its project;
    ``shared:{src}:{dst}`` routes via the src agent's registered project.
    Unroutable keys (hermetic tests, unknown agents) are skipped silently.
    """
    project = None
    if key.startswith("scratch:"):
        rest = key[len("scratch:"):]
        project = rest.rsplit(":", 1)[0] if ":" in rest else None
    elif key.startswith("shared:"):
        parts = key.split(":")
        if len(parts) >= 2:
            project = project_of(parts[1])
    if not project:
        return
    p = bookmarks_path(project)
    if p is None:
        return
    with _IO_LOCK:
        data = _read_json(p)
        marks = data.get("marks")
        marks = marks if isinstance(marks, dict) else {}
        if key in watermark.keys():
            marks[key] = watermark.get(key)
        else:
            marks.pop(key, None)   # dropped (agent deletion) → row removed
        _write_json(p, {"marks": marks})


def append_routing(agent_id: str, anchor_id: str,
                   source: str, recipients: list[str]) -> None:
    """Append one NON-default routing overlay record (§8.6) — append-only."""
    key = project_of(agent_id)
    if not key:
        return
    p = routing_path(key)
    if p is None:
        return
    with _IO_LOCK:
        _append_jsonl(p, {"anchor_id": anchor_id, "source": source,
                          "recipients": list(recipients)})


def load_routing(project_key: str) -> list[dict[str, Any]]:
    """Read the routing overlay (replay-side left-join input)."""
    p = routing_path(project_key)
    if p is None or not p.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            out.append(rec)
    return out


# ---------------------------------------------------------------------------
# Scratchpad .md round-trip (the board's persistence IS its markdown mirror)
# ---------------------------------------------------------------------------

_POST_RE = re.compile(r"^- \*\*(?P<author>.+?)\*\* \((?P<ts>[^)]+)\): (?P<text>.*)$")


def parse_scratchpad_md(text: str) -> list[dict[str, Any]]:
    """Parse the mirrored board back into posts (seq = line order, 1..N).

    Only an UNINDENTED line matching the mirror format starts a post. Indented
    lines (the mirror writes every continuation line with a two-space prefix)
    are continuations of the previous post's text with that prefix stripped —
    so post text that itself contains a ``- **x** (t): y`` line round-trips
    verbatim instead of splitting into a phantom post. Unindented non-heading
    lines that don't match still attach as continuations (pre-indent legacy
    mirrors). The leading ``# Shared scratchpad`` heading and blanks between
    posts are skipped.
    """
    posts: list[dict[str, Any]] = []
    for line in text.splitlines():
        indented = line.startswith("  ")
        m = None if indented else _POST_RE.match(line)
        if m:
            posts.append({
                "seq": len(posts) + 1,
                "author": m.group("author"),
                "text": m.group("text"),
                "ts": m.group("ts"),
            })
        elif posts and indented:
            posts[-1]["text"] += "\n" + line[2:]
        elif posts and line.strip() and not line.startswith("#"):
            posts[-1]["text"] += "\n" + line   # legacy unindented continuation
    return posts


# ---------------------------------------------------------------------------
# Project load — seed the in-memory modules from disk (lazy, once per root)
# ---------------------------------------------------------------------------

def load_project(cwd: str | None) -> bool:
    """Load a project's persisted state into the live modules (idempotent).

    Called on the first session whose canonical root resolves to the project
    (create or reconnect) and by the Projects open flow. Returns True when a
    load actually ran (False for no-cwd or already-loaded roots).
    """
    key = storage.project_key(cwd)
    if not key or key in _LOADED:
        return False
    _LOADED.add(key)

    # Legacy `.awl/` stores fold in before anything reads (§11 #1).
    try:
        storage.migrate_legacy_store(key)
    except Exception:  # pragma: no cover - best-effort migration
        logger.warning("legacy store migration failed for %s", key, exc_info=True)

    # Inbox items.
    p = inbox_path(key)
    if p is not None:
        items = _read_json(p).get("items")
        if isinstance(items, dict):
            for aid, lst in items.items():
                if isinstance(lst, list):
                    inbox.restore(aid, lst)

    # Links (config + counters + ids).
    p = links_path(key)
    if p is not None:
        rows = _read_json(p).get("links")
        if isinstance(rows, list):
            links.restore(rows)

    # The scratchpad board reloads from its .md (§8.3 — the .md IS the store)
    # BEFORE the watermarks, so the board length is known for clamping.
    board_len = 0
    sp = storage.scratchpad_path(key)
    if sp is not None and sp.is_file():
        try:
            posts = parse_scratchpad_md(sp.read_text(encoding="utf-8"))
            if posts:
                scratchpad.restore(key, posts)
            board_len = len(posts)
        except Exception:  # pragma: no cover - a corrupt board must not block open
            logger.warning("scratchpad reload failed for %s", key, exc_info=True)

    # Read-watermarks. This project's scratch marks clamp to the reloaded board
    # length: the reloaded seqs run 1..N, but a persisted mark can exceed N
    # (legacy marks recorded the old module-GLOBAL post seqs) — restored as-is
    # it would sit past the whole board and silently swallow new posts forever.
    p = bookmarks_path(key)
    if p is not None:
        marks = _read_json(p).get("marks")
        if isinstance(marks, dict):
            marks = {k: int(v) for k, v in marks.items()
                     if isinstance(v, (int, float))}
            scratch_prefix = f"scratch:{key}:"
            for k in marks:
                if k.startswith(scratch_prefix) and marks[k] > board_len:
                    marks[k] = board_len
            watermark.restore(marks)

    # Retired identity numbers.
    for n in load_retired_numbers(key):
        deletion.retire_number(n)

    touch_projects_index(key)
    logger.info("Loaded project state for %s", key)
    return True


# ---------------------------------------------------------------------------
# Hook installation — write-through wiring for the in-memory modules
# ---------------------------------------------------------------------------

def install_hooks() -> None:
    """Install the write-through persist hooks on the feature modules.

    Called once at sidecar startup (and by tests that exercise persistence).
    Hooks fire on every mutation; unroutable agents (no registered project) are
    skipped, so hermetic unit tests of the pure modules stay file-free.
    """
    inbox.set_persist_hook(persist_inbox_for)
    links.set_persist_hook(persist_links_for)
    watermark.set_persist_hook(persist_bookmark)
