"""Runtime session records — restart-surviving persistence for the roster.

The `bridge` driver runs each session as a real Claude Code TUI in tmux/WSL2,
which OUTLIVES the sidecar process. So when the sidecar restarts we can rebind to
those still-alive tmux sessions instead of losing them — but only if we remembered
their tmux names. This module is that memory.

**Where records live (§8.2/§8.4):** the roster is PER-PROJECT — a record whose
``cwd`` resolves to a canonical project root is written through to that project's
``<project>/.awl-cc-dash/state/agents.json`` (via :mod:`state_store`), so the
roster travels with the repo. Only a record with **no** resolvable project home
falls back to the app-level ``sidecar/runtime/sessions.json`` (the legacy home).
Saving a project-homed record also touches the 🏠 ``projects.json`` index (§3.5),
which is how :func:`all_records` can enumerate every project's roster after a
reboot without scanning the disk. **Project rosters win:** :func:`all_records`
aggregates project-first (a stale pre-migration app-level copy can never shadow
the fresher project record), and :func:`save_record` removes any app-level copy
of the same session once the project-side write succeeds. The legacy file's own
read→modify→write pairs run under a module lock so concurrent in-process
writers can't lose each other's updates.

Location of the app-level fallback + index: the sidecar-owned runtime directory
(``sidecar/runtime/`` by default, overridable via ``AWL_SIDECAR_RUNTIME`` — tests
point it at a temp dir). Gitignored: live operational state, never tracked.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger("awl-sidecar.runtime")

# Guards the legacy sessions.json read→modify→write pairs (save/remove): two
# concurrent in-process writers must never interleave a load and clobber each
# other's records.
_LEGACY_LOCK = threading.Lock()


def runtime_dir() -> Path:
    """The dashboard runtime store directory (the 🏠 Dashboard home in the storage & scoping model).

    ``sidecar/runtime/`` by default, overridable via ``AWL_SIDECAR_RUNTIME``.
    This is the single source of truth for the dashboard-owned store location —
    ``storage.dashboard_runtime_dir`` resolves to exactly this, so Setups /
    templates / the projects index never diverge across modules.
    """
    override = os.environ.get("AWL_SIDECAR_RUNTIME")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent / "runtime"


def _runtime_dir() -> Path:
    # Back-compat private alias; delegates to the public accessor above.
    return runtime_dir()


def _records_file() -> Path:
    return _runtime_dir() / "sessions.json"


def _load_all_legacy() -> dict[str, dict[str, Any]]:
    path = _records_file()
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _write_all_legacy(records: dict[str, dict[str, Any]]) -> None:
    path = _records_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    tmp.replace(path)  # atomic-ish on the same filesystem


def _state_modules():
    """Lazy import (storage imports this module at load — avoid the cycle)."""
    import state_store
    import storage
    return state_store, storage


def save_record(record: dict[str, Any]) -> None:
    """Insert or update a session record (keyed by ``session_id``).

    Routes by home: a resolvable project ``cwd`` → the project's
    ``state/agents.json`` (+ the projects index); no project → the app-level
    ``sessions.json`` fallback. After a successful project-side write any
    app-level copy of the same session (a pre-migration leftover) is removed,
    so a stale legacy record can never linger next to the fresher project one.
    """
    sid = record.get("session_id")
    if not sid:
        return
    try:
        state_store, storage = _state_modules()
        key = storage.project_key(record.get("cwd"))
    except Exception:  # pragma: no cover - stripped envs
        state_store, key = None, None
    if key and state_store is not None:
        state_store.save_roster_record(key, record)
        state_store.touch_projects_index(key)
        with _LEGACY_LOCK:
            records = _load_all_legacy()
            if records.pop(sid, None) is not None:
                _write_all_legacy(records)
                logger.debug("Dropped stale app-level copy of session %s", sid)
        logger.debug("Saved roster record for session %s into project %s", sid, key)
        return
    with _LEGACY_LOCK:
        records = _load_all_legacy()
        records[sid] = record
        _write_all_legacy(records)
    logger.debug("Saved runtime record for session %s (tmux %s, app-level)",
                 sid, record.get("tmux_name"))


def remove_record(session_id: str) -> None:
    """Drop a session record wherever it lives (no-op when absent)."""
    if not session_id:
        return
    with _LEGACY_LOCK:
        records = _load_all_legacy()
        removed = records.pop(session_id, None) is not None
        if removed:
            _write_all_legacy(records)
    if removed:
        logger.debug("Removed runtime record for session %s (app-level)", session_id)
        return
    try:
        state_store, _storage = _state_modules()
    except Exception:  # pragma: no cover - stripped envs
        return
    for key in state_store.known_projects():
        if state_store.remove_roster_record(key, session_id):
            logger.debug("Removed roster record for session %s from %s",
                         session_id, key)
            return


def all_records() -> list[dict[str, Any]]:
    """Every persisted session record — every indexed project's roster + app-level.

    Built PROJECT-FIRST: when a session id exists in both a project roster and
    the app-level ``sessions.json`` (a pre-migration leftover), the project
    record — the write-through home, always fresher — wins; the legacy copy
    only fills ids no project knows.
    """
    out: dict[str, dict[str, Any]] = {}
    try:
        state_store, _storage = _state_modules()
        for key in state_store.known_projects():
            for sid, rec in state_store.load_roster(key).items():
                out.setdefault(sid, rec)
    except Exception:  # pragma: no cover - stripped envs
        pass
    for sid, rec in _load_all_legacy().items():
        out.setdefault(sid, rec)
    return list(out.values())
