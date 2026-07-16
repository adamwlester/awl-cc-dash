"""Library — project-scoped docs/plans read + render, plus per-doc metadata sidecars.

The Library surfaces the agents' own working artifacts to the dashboard:

  * **Documents & Plans** — ``.md`` files that live in the project directory (the
    agents' ``cwd``, WSL-reachable) and in the project store's ``plans/`` /
    ``docs/`` dirs (§8.2). Enumerate the files (:func:`list_markdown`), return a
    single doc's raw content (:func:`read_document`), and — for the
    dashboard-owned store only — create / delete / rename (:func:`create_document`,
    :func:`delete_document`, :func:`rename_document_pair`). **Write scope is the
    two content collections**: every mutating operation is gated to files under
    the store's ``plans/`` or ``docs/`` subtrees
    (:func:`document_in_content_dirs`) — never ``state/`` or other store files;
    read-side checks keep the wider :func:`document_in_store`. Everything outside
    ``<project>/.awl-cc-dash/`` stays browse-read-only (§8.5 rule 5), and review
    writes never mint a sidecar at the repo root
    (:func:`resolve_document_for_write` drops the root candidate that
    :func:`resolve_document` keeps for reads).

  * **Per-doc metadata sidecars (§8.5)** — content and metadata are separate
    files, **paired by name**: ``roadmap.md`` + ``roadmap.meta.json`` next to it.
    The review layer NEVER writes into the content file. The sidecar holds the
    review state/verdict (+ who/when), comment threads (id · text · author ·
    timestamp · resolved), quote-anchors (quoted snippet + nearest heading — the
    store just holds them; matching/highlighting is the UI's job, degrading
    implicitly to doc-level when the text drifts), and provenance
    (created-by/when/session). Every sidecar written stamps
    ``schema_version: 1``. Writes are atomic (tmp + ``os.replace``).

  * **Legacy plan-review side-store** — the superseded central store, one JSON
    file per project (``<project>/.awl-cc-dash/plan-reviews.json``) keyed by the
    plan's FILENAME. The ``load_reviews`` / ``set_review`` function family is
    **kept** (other callers/tests pin it), but the endpoints now ride the
    sidecars; :func:`migrate_plan_reviews` folds the legacy file into per-doc
    sidecars on first project read and renames it ``plan-reviews.json.migrated``
    so migration never re-runs.

  * **Attached docs at launch (§7.16, §11 #44)** — resolve an agent's attached
    Library-doc references to WSL-reachable absolute paths and render the short
    consult-these-docs preamble the bridge driver appends to the agent's system
    prompt at launch (:func:`resolve_attached_doc`, :func:`attached_docs_wsl`,
    :func:`attached_docs_preamble`).

Design seam: the core file functions are **path-explicit** — they take an
explicit document / review-file path, so they're fully testable on a
``tmp_path`` with no ``cwd`` semantics. Thin ``*_for_cwd`` / cwd-taking
wrappers resolve the project-scoped paths via :mod:`storage`
(``plans_dir`` / ``docs_dir`` / ``plan_reviews_path``) and delegate straight to
the path-explicit core.

Listing is **non-recursive**: Documents and Plans are flat collections (a docs
dir, or a ``plans`` subdir), so a top-level scan is the intended scope — nested
trees are not walked. Pass ``subdir`` to scope into e.g. ``"plans"``.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import storage

# Files within a directory whose name ends in this are documents/plans.
_MD_SUFFIX = ".md"

# Per-doc sidecar naming + schema (§8.5): `<stem>.meta.json` next to `<stem>.md`.
_META_SUFFIX = ".meta.json"
_SCHEMA_VERSION = 1


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

        {"filename": str, "path": str, "size": int, "modified": str(iso),
         "provenance": {created_by?, created_at?, session?}}

    The ``provenance`` block (§8.5, §11 #41) is lifted from the doc's paired
    ``.meta.json`` sidecar (created-by / when / session) so the renderer's Authors
    lens can group by author straight off the listing; it is ``{}`` for any doc
    with no sidecar or no recorded provenance (a browse-read-only ``.md`` outside
    the store, or a doc the dashboard never stamped). Results are sorted by
    ``filename`` for a stable rendering order.
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
                "provenance": doc_provenance(child),
            }
        )
    entries.sort(key=lambda e: e["filename"])
    return entries


def read_document(path: str) -> dict:
    """Read a single document's raw text.

    Returns
    ``{"filename": str, "path": str, "content": str, "provenance": {...}}``.
    ``provenance`` (§8.5, §11 #41) is the created-by / when / session block from
    the doc's paired ``.meta.json`` sidecar, or ``{}`` when there is none — so the
    Authors lens can read a single doc's author on open, not only from the
    listing. Raises :class:`FileNotFoundError` if the file does not exist (or
    isn't a file).
    """
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(path)
    return {
        "filename": p.name,
        "path": str(p),
        "content": p.read_text(encoding="utf-8"),
        "provenance": doc_provenance(p),
    }


# ---------------------------------------------------------------------------
# Per-doc metadata sidecars (§8.5) — path-explicit core
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _skeleton_meta() -> dict:
    """The empty sidecar shape — every reader can rely on these keys existing."""
    return {
        "schema_version": _SCHEMA_VERSION,
        "review": {},       # owner / state / verdict / verdict_by / verdict_at
        "comments": [],     # [{id, text, author, ts, resolved, anchor_quote, anchor_heading}]
        "provenance": {},   # {created_by, created_at, session}
    }


def _safe_md_filename(filename: str) -> str:
    """Validate a client-supplied document filename (store-scoped writes only).

    Rejects anything that could escape the store dir it is joined to: path
    separators, any ``..`` occurrence, and empty names. Requires the ``.md``
    suffix (the Library's document collections are markdown-only). Returns the
    validated name. Raises :class:`ValueError` on any violation.
    """
    name = (filename or "").strip()
    if not name:
        raise ValueError("filename required")
    if "/" in name or "\\" in name:
        raise ValueError(f"filename must not contain path separators: {filename!r}")
    if ".." in name:
        raise ValueError(f"filename must not contain '..': {filename!r}")
    if not name.lower().endswith(_MD_SUFFIX):
        raise ValueError(f"filename must end with .md: {filename!r}")
    if name.lower() == _MD_SUFFIX:
        raise ValueError(f"filename needs a stem before .md: {filename!r}")
    return name


def meta_path(md_path: str | Path) -> Path:
    """The sidecar path paired to a document: ``<dir>/<stem>.meta.json``."""
    p = Path(md_path)
    return p.with_name(p.stem + _META_SUFFIX)


def load_meta(md_path: str | Path) -> dict:
    """Read a document's sidecar. Missing/corrupt/mis-shaped → the skeleton dict.

    The sidecar is metadata, never the source of truth — a broken file degrades
    to empty rather than crashing the Library read path. Loaded data is folded
    over the skeleton so every expected key exists with the right type.
    """
    mp = meta_path(md_path)
    skeleton = _skeleton_meta()
    if not mp.is_file():
        return skeleton
    try:
        data = json.loads(mp.read_text(encoding="utf-8") or "{}")
    except (json.JSONDecodeError, OSError):
        return skeleton
    if not isinstance(data, dict):
        return skeleton
    for key, default in skeleton.items():
        if not isinstance(data.get(key), type(default)):
            data[key] = default
    return data


def save_meta(md_path: str | Path, meta: dict) -> dict:
    """Persist a document's sidecar atomically; returns the dict as written.

    Atomic write-replace: the JSON is written to a ``.tmp`` file in the same
    directory, then ``os.replace``d over the real sidecar — a crash mid-write
    never leaves a torn sidecar (nor a lingering ``.tmp``). Every save stamps
    ``schema_version`` (currently 1) and re-stamps ``updated_at`` (UTC ISO-8601).
    Creates the parent directory if needed.
    """
    mp = meta_path(md_path)
    out = dict(meta)
    out["schema_version"] = _SCHEMA_VERSION
    out["updated_at"] = _utc_now()
    mp.parent.mkdir(parents=True, exist_ok=True)
    tmp = mp.with_name(mp.name + ".tmp")
    try:
        tmp.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, mp)
    finally:
        if tmp.exists():  # a failed replace must not leave residue behind
            try:
                tmp.unlink()
            except OSError:
                pass
    return out


def set_doc_review(
    md_path: str | Path,
    *,
    owner: str | None = None,
    state: str | None = None,
    verdict: str | None = None,
    verdict_by: str | None = None,
) -> dict:
    """Merge review fields into a document's sidecar; returns the saved meta.

    Merge-don't-clobber (the legacy :func:`set_review` semantics): only the
    **provided** (non-``None``) fields land — passing nothing for a field leaves
    it untouched, so partial updates never wipe unrelated metadata. Setting a
    ``verdict`` also stamps ``verdict_at`` (UTC ISO-8601) — the §8.5 "who/when".
    ``state`` / ``verdict`` stay free-form strings (not hard-enforced).
    """
    meta = load_meta(md_path)
    review = meta["review"]
    for key, value in (("owner", owner), ("state", state),
                       ("verdict", verdict), ("verdict_by", verdict_by)):
        if value is not None:
            review[key] = value
    if verdict is not None:
        review["verdict_at"] = _utc_now()
    return save_meta(md_path, meta)


def _next_comment_id(comments: list) -> str:
    """The next ``c<N>`` id, unique per sidecar (max existing N + 1 — resolved
    or out-of-order entries never cause a reuse)."""
    highest = 0
    for c in comments:
        cid = str((c or {}).get("id") or "") if isinstance(c, dict) else ""
        if cid.startswith("c") and cid[1:].isdigit():
            highest = max(highest, int(cid[1:]))
    return f"c{highest + 1}"


def add_comment(
    md_path: str | Path,
    *,
    text: str,
    author: str,
    anchor_quote: str | None = None,
    anchor_heading: str | None = None,
) -> dict:
    """Append a comment to a document's sidecar; returns the comment dict.

    Ids run ``c1``, ``c2``, … unique per sidecar. A comment may carry a
    quote-anchor — the quoted snippet plus the nearest heading (§8.5): the store
    just holds them; matching/highlighting is the UI's job, and a comment whose
    anchor no longer matches degrades implicitly to a doc-level comment (no hard
    link to break).
    """
    meta = load_meta(md_path)
    comment = {
        "id": _next_comment_id(meta["comments"]),
        "text": text,
        "author": author,
        "ts": _utc_now(),
        "resolved": False,
        "anchor_quote": anchor_quote,
        "anchor_heading": anchor_heading,
    }
    meta["comments"].append(comment)
    save_meta(md_path, meta)
    return comment


def resolve_comment(md_path: str | Path, comment_id: str) -> bool:
    """Mark one comment resolved. Returns ``True`` if found (and persisted),
    ``False`` when no comment carries that id (nothing written)."""
    meta = load_meta(md_path)
    for c in meta["comments"]:
        if isinstance(c, dict) and c.get("id") == comment_id:
            c["resolved"] = True
            save_meta(md_path, meta)
            return True
    return False


def set_provenance(
    md_path: str | Path,
    *,
    created_by: str | None = None,
    session: str | None = None,
) -> dict:
    """Merge provenance (created-by / session) into a sidecar; returns the saved meta.

    ``created_at`` is stamped on the **first** provenance write and never
    re-stamped — it records when the document entered the store, not the last
    touch (that's ``updated_at``).
    """
    meta = load_meta(md_path)
    prov = meta["provenance"]
    if created_by is not None:
        prov["created_by"] = created_by
    if session is not None:
        prov["session"] = session
    if "created_at" not in prov:
        prov["created_at"] = _utc_now()
    return save_meta(md_path, meta)


def doc_provenance(md_path: str | Path) -> dict:
    """The document's provenance block (``{created_by?, created_at?, session?}``).

    Read straight off the paired ``.meta.json`` sidecar via :func:`load_meta`, so
    a missing/corrupt sidecar or an un-stamped doc degrades to ``{}`` rather than
    raising — the Library read path (§11 #41: the Authors lens) never fails on a
    doc that carries no provenance. Read-only; never writes a sidecar.
    """
    prov = load_meta(md_path).get("provenance")
    return prov if isinstance(prov, dict) else {}


def rename_document_pair(md_path: str | Path, new_filename: str) -> dict:
    """Rename a document AND its sidecar together (§8.5 rule 3); dashboard-mediated.

    The pair moves as one: ``roadmap.md`` + ``roadmap.meta.json`` →
    ``final.md`` + ``final.meta.json`` (the sidecar may be absent — then only the
    ``.md`` moves). Refuses to overwrite an existing target (``.md`` **or**
    sidecar) with :class:`FileExistsError`, checked before anything moves so a
    refusal never leaves a half-renamed pair; if the sidecar's rename itself
    fails mid-pair, the ``.md`` rename is rolled back (best-effort) before the
    error propagates — a pair is never left half-renamed. ``new_filename`` is a bare
    ``.md`` filename (validated — no separators/``..``). Raises
    :class:`FileNotFoundError` when the source ``.md`` doesn't exist. Returns
    ``{"old": str, "new": str}`` (the ``.md`` paths).
    """
    src = Path(md_path)
    if not src.is_file():
        raise FileNotFoundError(str(md_path))
    name = _safe_md_filename(new_filename)
    dst = src.with_name(name)
    if dst.exists():
        raise FileExistsError(str(dst))
    src_meta = meta_path(src)
    dst_meta = meta_path(dst)
    if src_meta.is_file() and dst_meta.exists():
        raise FileExistsError(str(dst_meta))
    src.rename(dst)
    if src_meta.is_file():
        try:
            src_meta.rename(dst_meta)
        except OSError:
            # The pair must never be left half-renamed: roll the .md back
            # (best-effort) before surfacing the failure.
            try:
                dst.rename(src)
            except OSError:  # pragma: no cover - rollback is best-effort
                pass
            raise
    return {"old": str(src), "new": str(dst)}


def find_orphan_metas(dir_path: str | Path) -> list[str]:
    """Sidecars in a directory whose paired ``.md`` is missing (§8.5 rule 3).

    Non-recursive, like the doc listings. Returns the orphaned ``.meta.json``
    paths (sorted, as strings). A missing/non-directory path yields ``[]``.
    """
    base = Path(dir_path)
    if not base.is_dir():
        return []
    orphans = []
    for child in sorted(base.iterdir()):
        if not child.is_file() or not child.name.endswith(_META_SUFFIX):
            continue
        md_name = child.name[: -len(_META_SUFFIX)] + _MD_SUFFIX
        if not (base / md_name).is_file():
            orphans.append(str(child))
    return orphans


def relink_meta(orphan_meta_path: str | Path, md_path: str | Path) -> bool:
    """Re-link an orphaned sidecar to a named ``.md`` by renaming it into pair
    position. Returns ``True`` on success (or when already paired), ``False``
    when the orphan or the target ``.md`` doesn't exist, or when the target
    already has a sidecar (never overwritten)."""
    src = Path(orphan_meta_path)
    md = Path(md_path)
    if not src.is_file() or not md.is_file():
        return False
    target = meta_path(md)
    if target == src:
        return True  # already paired
    if target.exists():
        return False  # the .md already has a sidecar; never clobber it
    src.rename(target)
    return True


# ---------------------------------------------------------------------------
# Dashboard-owned document create/delete (store-scoped writes only, §8.5 rule 5)
# ---------------------------------------------------------------------------

def document_in_store(path: str | Path, cwd: str | None) -> bool:
    """Is ``path`` inside this project's ``.awl-cc-dash/`` store?

    Both sides are ``resolve()``d before comparing, so symlinks and relative
    segments can't smuggle a path out of (or fake a path into) the store. The
    READ-side scope check; mutating operations gate on the tighter
    :func:`document_in_content_dirs` (§8.5 rule 5).
    """
    store = storage.project_awl_dir(cwd)
    if store is None:
        return False
    try:
        p = Path(path).resolve()
        store_resolved = store.resolve()
    except OSError:
        return False
    return p == store_resolved or store_resolved in p.parents


def document_in_content_dirs(path: str | Path, cwd: str | None) -> bool:
    """Is ``path`` inside the store's ``plans/`` or ``docs/`` content dirs?

    The WRITE-scope gate for every mutating Library operation (create / delete /
    rename / edit-in-place / comment / review writes): only the two document
    collections of ``<project>/.awl-cc-dash/`` are writable — never ``state/``
    (the dashboard's JSON state) nor arbitrary store files. Both sides are
    ``resolve()``d like :func:`document_in_store`, which stays the read-side
    check.
    """
    try:
        p = Path(path).resolve()
    except OSError:
        return False
    for d in (storage.plans_dir(cwd), storage.docs_dir(cwd)):
        if d is None:
            continue
        try:
            d_resolved = d.resolve()
        except OSError:
            continue
        if d_resolved in p.parents:
            return True
    return False


def create_document(cwd: str | None, filename: str, content: str, subdir: str = "docs") -> dict:
    """Create a dashboard-owned document in the project store (§8.2).

    ``subdir`` must be ``"docs"`` or ``"plans"`` (:class:`ValueError` otherwise) —
    the two document collections of ``<project>/.awl-cc-dash/``. ``filename`` is
    validated (:func:`_safe_md_filename` — no separators/``..``, ``.md`` only) so
    a crafted name can't escape the store. Refuses an existing target with
    :class:`FileExistsError`. Creates the store dir on first use. Returns
    ``{"filename", "path", "subdir"}``.
    """
    if subdir not in ("docs", "plans"):
        raise ValueError(f"subdir must be 'docs' or 'plans', not {subdir!r}")
    name = _safe_md_filename(filename)
    base = storage.ensure_docs_dir(cwd) if subdir == "docs" else storage.ensure_plans_dir(cwd)
    target = base / name
    if target.exists():
        raise FileExistsError(str(target))
    target.write_text(content or "", encoding="utf-8")
    return {"filename": name, "path": str(target), "subdir": subdir}


def delete_document(path: str | Path, cwd: str | None) -> dict:
    """Delete a dashboard-owned document AND its paired sidecar.

    Refuses (``ValueError``) any path not under the store's ``plans/`` or
    ``docs/`` content dirs — the Library may browse other repo ``.md``
    read-only, and it never deletes ``state/`` or other store files (§8.5
    rule 5; scope checked via :func:`document_in_content_dirs`, both sides
    resolved). The path is ``resolve()``d first and BOTH the unlink and the
    sidecar pairing operate on the resolved path, so an alias spelling
    (symlink, short name, dotted segment) can never half-delete the pair. Only
    ``.md`` targets are deletable (the sidecar rides along, it is not addressed
    directly). Raises :class:`FileNotFoundError` when the ``.md`` is missing.
    Returns ``{"deleted": [resolved paths]}``.
    """
    if not document_in_content_dirs(path, cwd):
        raise ValueError(
            f"path is not under the project store's plans/ or docs/ dirs: {path}")
    p = Path(path).resolve()
    if p.suffix.lower() != _MD_SUFFIX:
        raise ValueError(f"only .md documents can be deleted: {path}")
    if not p.is_file():
        raise FileNotFoundError(str(path))
    deleted = [str(p)]
    p.unlink()
    mp = meta_path(p)
    if mp.is_file():
        mp.unlink()
        deleted.append(str(mp))
    return {"deleted": deleted}


def resolve_document(cwd: str | None, filename: str) -> Path | None:
    """Find a document by bare filename: store ``plans/``, then store ``docs/``,
    then the project root. Returns the first existing ``.md`` path, else
    ``None``. The filename is validated (no separators/``..``) so a crafted
    value can't address outside those three collections. READ-side resolution —
    review/comment writes resolve via :func:`resolve_document_for_write`."""
    name = _safe_md_filename(filename)
    for base in (storage.plans_dir(cwd), storage.docs_dir(cwd), storage.project_root(cwd)):
        if base is not None and (base / name).is_file():
            return base / name
    return None


def resolve_document_for_write(cwd: str | None, filename: str) -> Path | None:
    """Like :func:`resolve_document` but WRITE-scoped: only the store's
    ``plans/`` and ``docs/`` collections are candidates — the bare project-root
    candidate is dropped, so a review/comment write can never mint a sidecar at
    the repo root (§8.5 rule 5; the migration keeps its own recorded root-seam
    behavior for legacy entries)."""
    name = _safe_md_filename(filename)
    for base in (storage.plans_dir(cwd), storage.docs_dir(cwd)):
        if base is not None and (base / name).is_file():
            return base / name
    return None


# ---------------------------------------------------------------------------
# Attached docs at launch (§7.16, §11 #44 — the "light" v1)
# ---------------------------------------------------------------------------

# The one-line instruction that leads the launch preamble — tells the agent
# what the listed paths are and to consult them. Kept short and task-neutral
# (the preamble is context wiring, never task content).
ATTACHED_DOCS_LEAD = (
    "Reference docs attached to this session — read the file at a listed path "
    "whenever it is relevant to your task:"
)


def resolve_attached_doc(cwd: str | None, ref: str) -> Path | None:
    """Resolve ONE attached-doc reference (§11 #44) to an existing ``.md`` path.

    A reference is either a **bare filename** (resolved exactly like
    :func:`resolve_document`: store ``plans/``, then store ``docs/``, then the
    project root) or a **path** to an existing ``.md`` file (the Library's
    collections are markdown-only; non-``.md`` paths don't resolve). A path
    reference accepts every spelling that naturally comes back to the sidecar:
    a Windows-absolute path, a project-root-relative path (with or without a
    leading ``/``), and the WSL-side spellings the storage layer already folds
    for cwds — ``/mnt/<drive>/…`` (the exact form the launch preamble itself
    emits, so preamble paths round-trip) and a WSL-internal POSIX root
    (``/home/…`` → the ``\\\\wsl.localhost`` UNC form). Returns ``None`` for
    anything that doesn't resolve: attachment is best-effort at launch, so a
    doc deleted (or a reference mistyped) since selection must never fail the
    launch — it simply doesn't materialize into the preamble.
    """
    ref = (ref or "").strip()
    if not ref:
        return None
    if "/" not in ref and "\\" not in ref:
        try:
            return resolve_document(cwd, ref)
        except ValueError:
            return None
    # A path reference. Build its candidate readings in probe order — the
    # first existing .md wins. Probing must never raise (a NUL or other bad
    # character in a ref degrades to None, never fails the launch).
    candidates: list[Path] = []
    posix = ref.replace("\\", "/")
    if Path(ref).is_absolute():
        candidates.append(Path(ref))
    elif posix.startswith("/"):
        # Rooted but driveless (Windows `is_absolute()` is False): either a
        # project-rooted spelling (`/docs/x.md` ≡ `docs/x.md`) or a WSL-side
        # absolute (`/mnt/c/…`, `/home/…`). Probe the cheap local reading
        # first, then the storage-layer alias fold — the same folding project
        # cwds get, so both spellings of one doc land on the same file.
        root = storage.project_root(cwd)
        if root is not None:
            candidates.append(root / posix.lstrip("/"))
        candidates.append(Path(storage.normalize_path_alias(ref)))
    else:
        root = storage.project_root(cwd)
        if root is None:
            return None
        candidates.append(root / ref)
    for cand in candidates:
        try:
            cand = cand.resolve()
            if cand.suffix.lower() == _MD_SUFFIX and cand.is_file():
                return cand
        except (OSError, ValueError):
            continue
    return None


def attached_docs_wsl(cwd: str | None, refs: list[str] | None) -> list[str]:
    """Resolve attached-doc references to WSL-reachable ABSOLUTE paths (§11 #44).

    Each reference resolves via :func:`resolve_attached_doc`, then translates to
    the WSL-reachable form the agents actually open (``storage.doc_path_wsl`` —
    the same translation the store's fixed ``*_wsl`` paths ride). Order is
    preserved, duplicates collapse to the first occurrence, and unresolvable
    references are skipped (best-effort — see :func:`resolve_attached_doc`).
    """
    out: list[str] = []
    for ref in refs or []:
        p = resolve_attached_doc(cwd, ref)
        if p is None:
            continue
        w = storage.doc_path_wsl(p)
        if w and w not in out:
            out.append(w)
    return out


def _attached_docs_lead(cwd: str | None) -> str:
    """The preamble's lead line, resolved through the §11 #45 prompt library.

    Group ``attached-docs``, item ``lead`` (shipped default seeded verbatim in
    ``assets/prompts/actions.md``; project scope overrides). Falls back to the
    in-code :data:`ATTACHED_DOCS_LEAD` when neither scope has a non-empty item
    or the library is unavailable — never raises into a launch."""
    try:
        import prompt_library  # sidecar dir on sys.path — lazy, fault-isolated
        return prompt_library.resolve("attached-docs", "lead", cwd) or ATTACHED_DOCS_LEAD
    except Exception:
        return ATTACHED_DOCS_LEAD


def attached_docs_preamble(cwd: str | None, refs: list[str] | None) -> str:
    """The short launch preamble listing an agent's attached docs (§11 #44).

    One lead line (:func:`_attached_docs_lead` — consult these when relevant;
    library-resolved with :data:`ATTACHED_DOCS_LEAD` as the fallback) followed
    by one ``- <wsl path>`` bullet per resolved doc. ``""`` when no
    reference resolves (no docs → no preamble — nothing is appended to the
    agent's system prompt). The bridge driver composes this with the
    response-preset instruction (§11 #39) at launch; automatic relevance
    retrieval stays out of scope (§10 #6).
    """
    paths = attached_docs_wsl(cwd, refs)
    if not paths:
        return ""
    return "\n".join([_attached_docs_lead(cwd)] + [f"- {p}" for p in paths])


# ---------------------------------------------------------------------------
# Legacy central store → per-doc sidecar migration + project-wide aggregation
# ---------------------------------------------------------------------------

def migrate_plan_reviews(cwd: str | None) -> int:
    """Fold the legacy central ``plan-reviews.json`` into per-doc sidecars (§8.5).

    Runs on first project read (the ``GET /library/reviews`` handler calls it
    before aggregating). For each legacy filename key the target document is
    matched **by bare filename** (the legacy store keyed bare filenames from the
    old flat layout): ``.awl-cc-dash/plans/<name>`` first, then
    ``<project root>/<name>``; when neither ``.md`` exists the sidecar is created
    in ``plans/`` anyway (plans were the legacy store's subject) — it lands as a
    detectable, re-linkable orphan rather than silently dropping review data.
    Keys are reduced to their basename before matching, so a crafted key can't
    escape the project.

    The merge is **non-destructive — existing sidecar fields win**: a review
    field already present in the sidecar is kept; legacy ``comments`` (free-form
    string or list) are converted to comment dicts only when the sidecar has no
    comments of its own. After migrating, the legacy file is renamed
    ``plan-reviews.json.migrated`` so migration never re-runs (idempotent: a
    second call finds no legacy file and no-ops). Returns the number of legacy
    entries migrated (``0`` when there was nothing to do).
    """
    legacy_path = storage.plan_reviews_path(cwd)
    if legacy_path is None or not legacy_path.is_file():
        return 0
    legacy = load_reviews(str(legacy_path))
    root = storage.project_root(cwd)
    migrated = 0
    for key, entry in legacy.items():
        if not isinstance(entry, dict):
            continue
        name = Path(key).name  # basename only — a crafted key can't escape
        if not name:
            continue
        plans = storage.plans_dir(cwd)
        candidates = [plans / name, root / name]
        target_md = next((c for c in candidates if c.is_file()), None)
        if target_md is None:
            target_md = storage.ensure_plans_dir(cwd) / name
        meta = load_meta(target_md)
        review = meta["review"]
        for field in ("owner", "state", "verdict"):
            value = entry.get(field)
            if value is not None and field not in review:
                review[field] = value
        if not meta["comments"]:
            meta["comments"] = _comments_from_legacy(entry)
        save_meta(target_md, meta)
        migrated += 1
    legacy_path.replace(legacy_path.with_name(legacy_path.name + ".migrated"))
    return migrated


def _comments_from_legacy(entry: dict) -> list[dict]:
    """Convert a legacy entry's free-form ``comments`` (string, or list of
    strings/dicts) into §8.5 comment dicts. Author falls back to the legacy
    owner (else ``"user"``); the timestamp to the legacy ``updated_at``."""
    raw = entry.get("comments")
    if raw is None or raw == "" or raw == []:
        return []
    items = raw if isinstance(raw, list) else [raw]
    fallback_author = str(entry.get("owner") or "user")
    fallback_ts = entry.get("updated_at") or _utc_now()
    out: list[dict] = []
    for i, item in enumerate(items, start=1):
        if isinstance(item, dict):
            out.append({
                "id": f"c{i}",
                "text": str(item.get("text") or ""),
                "author": str(item.get("author") or fallback_author),
                "ts": str(item.get("ts") or fallback_ts),
                "resolved": bool(item.get("resolved", False)),
                "anchor_quote": item.get("anchor_quote"),
                "anchor_heading": item.get("anchor_heading"),
            })
        else:
            out.append({
                "id": f"c{i}",
                "text": str(item),
                "author": fallback_author,
                "ts": str(fallback_ts),
                "resolved": False,
                "anchor_quote": None,
                "anchor_heading": None,
            })
    return out


def aggregate_metas(cwd: str | None) -> dict:
    """Every sidecar under the project store's ``plans/`` and ``docs/`` dirs —
    plus the project ROOT's top-level ``*.meta.json`` (read-only, so migrated
    root-doc reviews stay visible) — as a **filename-keyed** dict: the
    ``GET /library/reviews`` response shape.

    Keys are the paired ``.md`` filenames (``roadmap.md`` → its meta); orphaned
    sidecars are included under their implied ``.md`` name (they still carry
    review data worth showing). On a same-name collision the scan order wins:
    ``plans/``, then ``docs/``, then the root (later entries are not merged).
    The root scan is READ-side only — no write path creates sidecars there.
    Missing dirs contribute nothing.
    """
    out: dict = {}
    for d in (storage.plans_dir(cwd), storage.docs_dir(cwd),
              storage.project_root(cwd)):
        if d is None or not d.is_dir():
            continue
        for child in sorted(d.iterdir()):
            if not child.is_file() or not child.name.endswith(_META_SUFFIX):
                continue
            md_name = child.name[: -len(_META_SUFFIX)] + _MD_SUFFIX
            if md_name in out:
                continue  # earlier dirs win the collision (plans → docs → root)
            out[md_name] = load_meta(d / md_name)
    return out


# ---------------------------------------------------------------------------
# Plan-review side-store — path-explicit core (JSON keyed by plan filename)
#
# LEGACY (§8.5): superseded by the per-doc sidecars above. The function family
# is kept — callers/tests still pin it and it is the migration's reader — but
# the /library/reviews endpoints now ride the sidecar layer.
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
