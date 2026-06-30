"""Runtime session records — sidecar-owned persistence for restart survival.

The `bridge` driver runs each session as a real Claude Code TUI in tmux/WSL2,
which OUTLIVES the sidecar process. So when the sidecar restarts we can rebind to
those still-alive tmux sessions instead of losing them — but only if we remembered
their tmux names. This module is that memory: a tiny JSON file mapping each
sidecar session id to the minimal record needed to reconnect (tmux name + the
config used to create it).

Location: a sidecar-owned runtime directory (``sidecar/runtime/`` by default,
overridable via ``AWL_SIDECAR_RUNTIME`` — tests point it at a temp dir). The
directory is gitignored: these records are live operational state, never tracked.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

logger = logging.getLogger("awl-sidecar.runtime")


def runtime_dir() -> Path:
    """The dashboard runtime store directory (the 🏠 Dashboard home, OD-23).

    ``sidecar/runtime/`` by default, overridable via ``AWL_SIDECAR_RUNTIME``.
    This is the single source of truth for the dashboard-owned store location —
    ``storage.dashboard_runtime_dir`` resolves to exactly this, so Setups /
    templates / identity / sessions never diverge across modules.
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


def _load_all() -> dict[str, dict[str, Any]]:
    path = _records_file()
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return data


def _write_all(records: dict[str, dict[str, Any]]) -> None:
    path = _records_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(records, f, indent=2)
    tmp.replace(path)  # atomic-ish on the same filesystem


def save_record(record: dict[str, Any]) -> None:
    """Insert or update a session record (keyed by ``session_id``)."""
    sid = record.get("session_id")
    if not sid:
        return
    records = _load_all()
    records[sid] = record
    _write_all(records)
    logger.debug("Saved runtime record for session %s (tmux %s)",
                 sid, record.get("tmux_name"))


def remove_record(session_id: str) -> None:
    """Drop a session record if present (no-op when absent)."""
    if not session_id:
        return
    records = _load_all()
    if records.pop(session_id, None) is not None:
        _write_all(records)
        logger.debug("Removed runtime record for session %s", session_id)


def all_records() -> list[dict[str, Any]]:
    """Return every persisted session record."""
    return list(_load_all().values())
