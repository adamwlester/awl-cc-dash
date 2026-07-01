"""Safe, path-explicit read/write primitives for Claude Code settings JSON (OD-18).

The Settings surface (Config / MCP / Plugins tabs) becomes interactive: this
module is the low-level file layer under it. It reads and writes the real Claude
Code JSON files — the user-global ``~/.claude`` scope and the per-project
``<project>/.claude`` scope — but it does so **only** on file paths the caller
hands in. Nothing here hardcodes, discovers, or defaults to a real config
location; the caller (endpoint layer, wired later) is responsible for resolving
which scope's file to touch. That keeps this module hermetically testable and
means it can never write to a user's real config by accident.

Confirmation gating
-------------------
Every mutating call requires ``confirm=True`` and raises
:class:`ConfirmationRequired` (a ``PermissionError`` subclass) otherwise. This
models the confirm-gate the UI enforces: a plain confirm for ordinary edits, a
heavier one for global/destructive writes. The gate is enforced *before* any
filesystem change, so a refused call leaves the target file untouched. This
module does not distinguish plain-vs-heavy confirms — that policy lives in the
endpoint/UI layer; here a write is either confirmed or it is not.

Feasibility boundary (honest, NOT enforced here)
------------------------------------------------
This is a *file* layer. It writes what the engine can persist; it does not, and
cannot, make those changes take effect out of band. Two honest limits the UI
must surface (and which this module deliberately does not pretend to enforce):

* **Mid-run permission-mode is engine-BLOCKED.** You can persist a
  ``permissionMode`` value to a settings file, but a running Claude Code
  session will not adopt it mid-run — that is a hard engine limitation.
* **Per-agent MCP / model / plugins apply at launch/restart, not live.**
  Writing these fields is real, but they take effect when the agent next
  launches or restarts — they are "applies at launch", not fake-live.

Anything read-only (the account band: email / org / plan from local creds) is
exposed for display only via :func:`account_band`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Union

__all__ = [
    "ConfirmationRequired",
    "read_json",
    "write_json",
    "set_key",
    "toggle_key",
    "remove_key",
    "account_band",
]

PathLike = Union[str, "os.PathLike[str]", Path]


class ConfirmationRequired(PermissionError):
    """Raised by a mutating call when ``confirm`` is not ``True``.

    Subclasses :class:`PermissionError` so callers may catch either the specific
    type or the broad built-in.
    """


def _require_confirm(confirm: bool) -> None:
    if confirm is not True:
        raise ConfirmationRequired(
            "This write is confirm-gated; pass confirm=True to proceed."
        )


def read_json(path: PathLike) -> dict:
    """Read a JSON settings object from ``path``.

    Tolerant by design: a missing file, an empty/whitespace-only file, corrupt
    JSON, or valid-JSON-that-isn't-an-object all resolve to ``{}`` rather than
    raising, so a fresh/absent config reads as "no settings yet".
    """
    p = Path(path)
    try:
        text = p.read_text(encoding="utf-8")
    except (FileNotFoundError, NotADirectoryError, IsADirectoryError, OSError):
        return {}
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def write_json(path: PathLike, data: dict, *, confirm: bool) -> dict:
    """Atomically write ``data`` as pretty JSON to ``path`` (confirm-gated).

    Raises :class:`ConfirmationRequired` if ``confirm`` is not ``True`` (before
    any filesystem change). Otherwise creates parent directories as needed and
    writes via a temp file + atomic replace so a reader never sees a partial
    file. Returns the written ``data``.
    """
    _require_confirm(confirm)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    tmp = p.with_name(f"{p.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, p)  # atomic on same filesystem
    finally:
        # Clean up the temp file if the replace didn't consume it.
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
    return data


def _split(dotted_key: str) -> list[str]:
    parts = [seg for seg in dotted_key.split(".") if seg != ""]
    if not parts:
        raise ValueError(f"empty dotted key: {dotted_key!r}")
    return parts


def set_key(path: PathLike, dotted_key: str, value: Any, *, confirm: bool) -> dict:
    """Set a nested key by dotted path (read-modify-write), returning the full doc.

    Intermediate dicts are created as needed; a scalar sitting where a container
    is required is replaced by a dict. e.g. ``set_key(p, "permissions.deny", [...])``
    or ``set_key(p, "env.FOO", "bar")``. Confirm-gated.
    """
    _require_confirm(confirm)
    parts = _split(dotted_key)
    doc = read_json(path)
    cursor: dict = doc
    for seg in parts[:-1]:
        nxt = cursor.get(seg)
        if not isinstance(nxt, dict):
            nxt = {}
            cursor[seg] = nxt
        cursor = nxt
    cursor[parts[-1]] = value
    return write_json(path, doc, confirm=True)


def toggle_key(path: PathLike, dotted_key: str, *, confirm: bool) -> dict:
    """Flip a boolean at ``dotted_key`` and return the full doc.

    An absent value is treated as ``False`` (so its first toggle yields ``True``).
    A present non-boolean value flips on its truthiness. Confirm-gated.
    """
    _require_confirm(confirm)
    parts = _split(dotted_key)
    doc = read_json(path)
    cursor: dict = doc
    for seg in parts[:-1]:
        nxt = cursor.get(seg)
        if not isinstance(nxt, dict):
            nxt = {}
            cursor[seg] = nxt
        cursor = nxt
    current = cursor.get(parts[-1], False)
    cursor[parts[-1]] = not bool(current)
    return write_json(path, doc, confirm=True)


def remove_key(path: PathLike, dotted_key: str, *, confirm: bool) -> dict:
    """Delete a nested key if present and return the full doc.

    A key (or any intermediate segment) that doesn't exist is a no-op — the doc
    is still normalized and rewritten. Confirm-gated.
    """
    _require_confirm(confirm)
    parts = _split(dotted_key)
    doc = read_json(path)
    cursor: Any = doc
    for seg in parts[:-1]:
        cursor = cursor.get(seg) if isinstance(cursor, dict) else None
        if not isinstance(cursor, dict):
            cursor = None
            break
    if isinstance(cursor, dict):
        cursor.pop(parts[-1], None)
    return write_json(path, doc, confirm=True)


# Lenient field-name maps for the read-only account band. We accept several
# common spellings seen across Claude Code creds files and normalize to
# email / org / plan.
_EMAIL_FIELDS = ("email", "emailAddress", "email_address", "userEmail")
_ORG_FIELDS = ("org", "organization", "organizationName", "orgName", "organization_name")
_PLAN_FIELDS = ("plan", "subscriptionType", "planType", "subscription", "tier", "plan_type")

# Creds files often nest the interesting fields under a wrapper object.
_NEST_KEYS = ("oauthAccount", "account", "user", "claudeAiOauth", "auth")


def _first(source: dict, fields: tuple[str, ...]) -> Any:
    for name in fields:
        if name in source and source[name] not in (None, ""):
            return source[name]
    return None


def account_band(creds_path: PathLike) -> dict:
    """Read local creds and return ``{"email", "org", "plan"}`` for display.

    Read-only. Lenient about field names (see ``_EMAIL/ORG/PLAN_FIELDS``) and
    looks one level into a common wrapper object (``oauthAccount``/``account``/
    etc.) when the fields aren't at the top level. Returns
    ``{"signed_out": True}`` when the file is missing/corrupt or no recognized
    field is present. Only keys that were found are included; a partial read
    still returns whatever was recognized.
    """
    data = read_json(creds_path)

    # Search the top level, then merge in a single recognized wrapper object.
    scopes = [data]
    for key in _NEST_KEYS:
        nested = data.get(key)
        if isinstance(nested, dict):
            scopes.append(nested)

    band: dict = {}
    for label, fields in (("email", _EMAIL_FIELDS), ("org", _ORG_FIELDS), ("plan", _PLAN_FIELDS)):
        for scope in scopes:
            val = _first(scope, fields)
            if val is not None:
                band[label] = val
                break

    if not band:
        return {"signed_out": True}
    return band
