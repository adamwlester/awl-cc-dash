"""Prompt templates store (OD-16) — backend persistence only.

Templates are a single-select, reusable list (None + saved). Picking one inserts
a ``template`` block whose ``{{placeholder}}`` pills get filled (or left unfilled).
This module is the backend store for that feature; the Editor UI is design-stream
and out of scope here.

**Storage (OD-23):** the **dashboard runtime store** — templates are tool-level
reusable, project-agnostic data (like Setups), so they live in the dashboard home
(``sidecar/runtime/templates.json`` by default, overridable via
``AWL_SIDECAR_RUNTIME``). We resolve the path through ``storage.templates_path()``
at **call-time**, never at import-time, so an env override always applies. If
``storage`` (or its accessor) is somehow unavailable, we fall back to
``$AWL_SIDECAR_RUNTIME/templates.json`` (or ``sidecar/runtime/templates.json``).

Each stored template is a dict::

    {"id", "name", "body", "placeholders": [...], "created_at"}

``placeholders`` are the unique ``{{token}}`` names in first-seen order, unless an
explicit list is provided.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

# ``{{ token }}`` — capture the inner name, tolerating surrounding whitespace.
_PLACEHOLDER_RE = re.compile(r"\{\{\s*([^{}]+?)\s*\}\}")


# ---------------------------------------------------------------------------
# Storage location (resolved at call-time so AWL_SIDECAR_RUNTIME applies)
# ---------------------------------------------------------------------------

def _store_path() -> Path:
    """The templates JSON path inside the dashboard runtime store.

    Resolved per call so a test (or runtime) ``AWL_SIDECAR_RUNTIME`` override
    takes effect. Prefers the canonical ``storage.templates_path()`` accessor;
    falls back to ``$AWL_SIDECAR_RUNTIME/templates.json`` if storage is absent.
    """
    try:
        import storage  # local import: keep import-time side effects out

        return storage.templates_path()
    except Exception:  # pragma: no cover - only when storage is unavailable
        override = os.environ.get("AWL_SIDECAR_RUNTIME")
        base = Path(override) if override else Path(__file__).resolve().parent / "runtime"
        return base / "templates.json"


# ---------------------------------------------------------------------------
# Low-level persistence (a JSON list on disk)
# ---------------------------------------------------------------------------

def _load_all() -> list[dict[str, Any]]:
    path = _store_path()
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [t for t in data if isinstance(t, dict)]


def _write_all(templates: list[dict[str, Any]]) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(templates, f, indent=2)
    tmp.replace(path)  # atomic-ish on the same filesystem


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract_placeholders(body: str) -> list[str]:
    """Unique ``{{name}}`` tokens from ``body``, in first-seen order."""
    seen: list[str] = []
    for match in _PLACEHOLDER_RE.findall(body or ""):
        if match not in seen:
            seen.append(match)
    return seen


def _new_id() -> str:
    """A short, collision-resistant id."""
    return uuid.uuid4().hex[:8]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def list_templates() -> list[dict[str, Any]]:
    """All saved templates (missing file → ``[]``)."""
    return _load_all()


def get_template(template_id: str) -> dict[str, Any] | None:
    """The template with ``template_id``, or ``None`` if absent."""
    for t in _load_all():
        if t.get("id") == template_id:
            return t
    return None


def add_template(
    name: str,
    body: str,
    placeholders: list[str] | None = None,
) -> dict[str, Any]:
    """Create and persist a template, returning the stored dict.

    ``placeholders`` defaults to the unique ``{{name}}`` tokens auto-extracted
    from ``body`` (first-seen order) when not explicitly given.
    """
    if placeholders is None:
        placeholders = _extract_placeholders(body)

    template = {
        "id": _new_id(),
        "name": name,
        "body": body,
        "placeholders": list(placeholders),
        "created_at": time.time(),
    }

    templates = _load_all()
    templates.append(template)
    _write_all(templates)
    return template


def update_template(
    template_id: str,
    *,
    name: str | None = None,
    body: str | None = None,
    placeholders: list[str] | None = None,
) -> dict[str, Any] | None:
    """Partially update a template; return the updated dict or ``None``.

    If ``body`` changes and ``placeholders`` is not explicitly given, the
    placeholders are re-extracted from the new body.
    """
    templates = _load_all()
    for i, t in enumerate(templates):
        if t.get("id") != template_id:
            continue

        if name is not None:
            t["name"] = name
        if body is not None:
            t["body"] = body
            if placeholders is None:
                t["placeholders"] = _extract_placeholders(body)
        if placeholders is not None:
            t["placeholders"] = list(placeholders)

        templates[i] = t
        _write_all(templates)
        return t
    return None


def remove_template(template_id: str) -> bool:
    """Delete the template with ``template_id``; ``True`` if one was removed."""
    templates = _load_all()
    remaining = [t for t in templates if t.get("id") != template_id]
    if len(remaining) == len(templates):
        return False
    _write_all(remaining)
    return True


def render_template(template_id: str, values: dict[str, Any]) -> str | None:
    """Substitute ``{{key}}`` placeholders in the body with ``values``.

    Unfilled placeholders are left intact as ``{{key}}``. Pure given a stored
    template; returns ``None`` if the template doesn't exist.
    """
    template = get_template(template_id)
    if template is None:
        return None

    def _sub(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in values:
            return str(values[key])
        return match.group(0)  # leave unfilled token intact

    return _PLACEHOLDER_RE.sub(_sub, template.get("body", ""))


def reset() -> None:
    """Delete the store file (test helper). No-op if it doesn't exist."""
    path = _store_path()
    try:
        path.unlink()
    except FileNotFoundError:
        pass
