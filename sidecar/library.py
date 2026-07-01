"""Library (OD-15, v1 = read + render, project-scoped).

The Library surfaces the agents' own working artifacts to the dashboard:

  * **Documents & Plans** — ``.md`` files that live in the project directory (the
    agents' ``cwd``, WSL-reachable). v1 is *read + render only*: enumerate the
    files (:func:`list_markdown`) and return a single doc's raw content
    (:func:`read_document`). Write-back of doc contents, assets/media, and richer
    plan formats are **deferred** — not built here.

  * **Plan-review side-store** — owner / state / verdict / comments that can't
    live inside a ``.md``. This is a small structured JSON file, one per project,
    at ``<project>/.awl/plan-reviews.json``, a JSON **object keyed by the plan's
    FILENAME**. It carries the plan↔agent **owner** mapping plus review metadata.
    (The Approve/Revise/Reject → resume action is out of scope for v1 — this
    module only stores the verdict/comments, it does not act on them.)

Design seam: the core file functions are **path-explicit** — they take an
explicit review-file path (or document/root path), so they're fully testable on a
``tmp_path`` with no ``cwd`` semantics. Thin ``*_for_cwd`` convenience wrappers
resolve the project-scoped path via :mod:`storage` (``plan_reviews_path(cwd)``)
and delegate straight to the path-explicit core.

Listing is **non-recursive**: Documents and Plans are flat collections (a docs
dir, or a ``plans`` subdir), so a top-level scan is the intended scope — nested
trees are not walked. Pass ``subdir`` to scope into e.g. ``"plans"``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import storage

# Files within a directory whose name ends in this are documents/plans.
_MD_SUFFIX = ".md"


# ---------------------------------------------------------------------------
# Documents & Plans — read + render (.md files in the project dir)
# ---------------------------------------------------------------------------

def _iso_mtime(path: Path) -> str:
    """The file's modified time as a local ISO-8601 timestamp string."""
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat()


def list_markdown(root_dir: str, subdir: str | None = None) -> list[dict]:
    """List ``.md`` files directly under ``root_dir`` (or ``root_dir/subdir``).

    Non-recursive: only the immediate directory is scanned (Documents and Plans
    are flat collections). Directories whose name ends in ``.md`` are skipped —
    only regular files count. A missing directory (or a path that isn't a
    directory) yields ``[]`` rather than raising.

    Each entry::

        {"filename": str, "path": str, "size": int, "modified": str(iso)}

    Results are sorted by ``filename`` for a stable rendering order.
    """
    base = Path(root_dir)
    if subdir:
        base = base / subdir
    if not base.is_dir():
        return []

    entries: list[dict] = []
    for child in base.iterdir():
        if not child.is_file():
            continue
        if child.suffix.lower() != _MD_SUFFIX:
            continue
        st = child.stat()
        entries.append(
            {
                "filename": child.name,
                "path": str(child),
                "size": st.st_size,
                "modified": datetime.fromtimestamp(st.st_mtime).isoformat(),
            }
        )
    entries.sort(key=lambda e: e["filename"])
    return entries


def read_document(path: str) -> dict:
    """Read a single document's raw text.

    Returns ``{"filename": str, "path": str, "content": str}``. Raises
    :class:`FileNotFoundError` if the file does not exist (or isn't a file).
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(path)
    return {
        "filename": p.name,
        "path": str(p),
        "content": p.read_text(encoding="utf-8"),
    }


# ---------------------------------------------------------------------------
# Plan-review side-store — path-explicit core (JSON keyed by plan filename)
# ---------------------------------------------------------------------------

def load_reviews(review_path: str) -> dict:
    """Read the whole side-store JSON object. Missing/empty file → ``{}``.

    A malformed/corrupt file also degrades to ``{}`` rather than crashing the
    Library read path — the side-store is metadata, never the source of truth.
    """
    p = Path(review_path)
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8") or "{}")
    except (json.JSONDecodeError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def get_review(review_path: str, filename: str) -> dict | None:
    """The review entry for one plan ``filename``, or ``None`` if absent."""
    entry = load_reviews(review_path).get(filename)
    return entry if isinstance(entry, dict) else None


def set_review(
    review_path: str,
    filename: str,
    *,
    owner: str | None = None,
    state: str | None = None,
    verdict: str | None = None,
    comments: str | None = None,
) -> dict:
    """Upsert the review entry for one plan ``filename`` and persist the store.

    Only the **provided** (non-``None``) fields are merged into any existing
    entry — passing nothing for a field leaves it untouched, so partial updates
    never clobber unrelated metadata. Every write re-stamps ``updated_at`` (UTC
    ISO-8601). Creates the parent directory (e.g. ``.awl/``) and the file if they
    don't exist. Returns the stored entry.

    ``state`` / ``verdict`` are free-form strings in v1 (e.g. verdict in
    ``{"approve", "revise", "reject"}``) — not hard-enforced.
    """
    p = Path(review_path)
    reviews = load_reviews(review_path)

    entry = dict(reviews.get(filename) or {})
    updates = {
        "owner": owner,
        "state": state,
        "verdict": verdict,
        "comments": comments,
    }
    for key, value in updates.items():
        if value is not None:
            entry[key] = value
    entry["updated_at"] = datetime.now(timezone.utc).isoformat()

    reviews[filename] = entry

    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(reviews, indent=2, ensure_ascii=False), encoding="utf-8")
    return entry


def remove_review(review_path: str, filename: str) -> bool:
    """Delete the review entry for one plan ``filename``.

    Returns ``True`` if an entry was removed, ``False`` if there was none (or the
    file didn't exist). Persists the store when something was removed.
    """
    p = Path(review_path)
    reviews = load_reviews(review_path)
    if filename not in reviews:
        return False
    del reviews[filename]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(reviews, indent=2, ensure_ascii=False), encoding="utf-8")
    return True


# ---------------------------------------------------------------------------
# Thin cwd convenience wrappers (resolve the project-scoped path via storage)
# ---------------------------------------------------------------------------

def _reviews_path_for_cwd(cwd: str | None) -> str:
    """``<project>/.awl/plan-reviews.json`` for an agent's ``cwd`` (as a str).

    Raises ``ValueError`` when the agent has no ``cwd`` — there's no project home
    to scope the side-store to.
    """
    rp = storage.plan_reviews_path(cwd)
    if rp is None:
        raise ValueError("agent has no cwd; cannot resolve a plan-reviews side-store")
    return str(rp)


def load_reviews_for_cwd(cwd: str | None) -> dict:
    """:func:`load_reviews` scoped to an agent's project home."""
    return load_reviews(_reviews_path_for_cwd(cwd))


def get_review_for_cwd(cwd: str | None, filename: str) -> dict | None:
    """:func:`get_review` scoped to an agent's project home."""
    return get_review(_reviews_path_for_cwd(cwd), filename)


def set_review_for_cwd(
    cwd: str | None,
    filename: str,
    *,
    owner: str | None = None,
    state: str | None = None,
    verdict: str | None = None,
    comments: str | None = None,
) -> dict:
    """:func:`set_review` scoped to an agent's project home."""
    return set_review(
        _reviews_path_for_cwd(cwd),
        filename,
        owner=owner,
        state=state,
        verdict=verdict,
        comments=comments,
    )


def remove_review_for_cwd(cwd: str | None, filename: str) -> bool:
    """:func:`remove_review` scoped to an agent's project home."""
    return remove_review(_reviews_path_for_cwd(cwd), filename)
