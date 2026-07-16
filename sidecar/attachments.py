"""Attachments & citations — asset materialization into the project store (§10 #1, §7.14, §7.16, §8.2).

The decided design is the research report's **Option A**
(``dev/notes/research/attachment-citation-path-materialization-report.md``,
2026-07-02): every attached or cited file is **copied** into the open project's
own store —

    <project>/.awl-cc-dash/assets/<asset_id>/<original-filename>

— and the canonical asset state is **project-relative** (``rel_path`` + hash +
metadata), never a receiver-specific absolute path. Receivers get *renderings*
(:func:`render_wsl_path` / :func:`render_http_url`): a WSL agent gets a
WSL-readable absolute path (``/mnt/…`` for Windows-drive stores; the native
``/home/…`` form for WSL-internal stores — both via the proven
``storage.doc_path_wsl`` translation, never re-derived here), while the
Electron renderer gets the sidecar HTTP URL (``GET /assets/{id}/{filename}`` —
the recommended default render path: the app already fetches everything over
localhost HTTP, which sidesteps Electron CSP/UNC-path policy entirely).

Metadata rides a **per-asset sidecar** beside the bytes — the §8.5 pairing
convention (content + metadata as separate files, paired by name), adapted to
arbitrary asset extensions by pairing on the FULL filename:
``assets/<id>/<filename>.meta.json``. The sidecar holds ``sha256`` · ``size`` ·
``mime`` · ``created`` · provenance (who/when/source) · an optional **citation
anchor** (``{doc, location}`` — §7.14 "Citations are built with Attach"), and
stamps ``schema_version: 1``. Assets are **immutable after publication** —
write temp, rename into place, verify the hash; no in-place edits.

Two write legs, chosen automatically from the canonical project root
(:func:`store_kind`):

  * **Windows-drive store** (``C:\\…`` — the common case): plain atomic Python
    I/O — write a ``.tmp-…`` sibling, ``os.replace`` into place, hash-verify by
    re-read.
  * **WSL-internal store** (``\\\\wsl.localhost\\<distro>\\…`` or
    ``\\\\wsl$\\…``): plain Python writes over the UNC share are the researched
    slow/fragile path, so bytes stream through ``wsl.exe -d <distro> -- bash -c
    'mkdir -p … && cat > tmp && mv tmp final'`` with **binary stdin** (never
    command-line args — Windows caps a command line at ~32 KB), then
    hash-verify via ``sha256sum`` *inside* the distro. The distro name is
    parsed from the UNC root itself, so the leg follows whatever distro
    actually hosts the project. (Live-proven — incl. ``wslpath -w`` round-trips
    on names with spaces/unicode — in ``tests/test_attachments_live.py``.)

Ingest accepts raw bytes (:func:`ingest_bytes` — the endpoint's **base64-JSON
upload body**, the decided upload form) or a local **source-path reference**
(:func:`ingest_source_path`) in any spelling the storage layer folds
(``C:\\…``, ``/mnt/c/…``, a WSL-internal ``/home/…``, UNC) — the original
spelling is kept as ``provenance.source`` for audit, never as the locator.

The message-attachment block (:func:`attachments_block`) renders the ONE
attributed front-matter-style block the send flow appends to a prompt carrying
attachment references (§7.3/§7.14 conventions — the bracketed attributed style
the piggyback/queue-awareness notes use): a lead line (resolved through the
§11 #45 prompt library, group ``attachments`` / item ``lead``, with
:data:`ATTACHMENTS_LEAD` as the in-code fallback) plus one
``- <receiver-readable absolute path>`` bullet per asset, citation anchors
riding inline.
"""

from __future__ import annotations

import hashlib
import json
import logging
import mimetypes
import os
import re
import shlex
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import storage

logger = logging.getLogger("awl-sidecar.attachments")

# §8.5 pairing convention adapted to assets: `<filename>.meta.json` beside the
# bytes (FULL-name pairing — asset extensions vary, so stem pairing would be
# ambiguous). The suffix is reserved: no asset file may claim it.
_META_SUFFIX = ".meta.json"
_SCHEMA_VERSION = 1

# The store subdir assets live in (§8.2) — same value storage's accessor uses.
_ASSETS_SUBDIR = "assets"

# Windows-forbidden filename characters (plus control chars). A WSL-native
# store could hold e.g. `photo:1.png`, but its Windows UNC view could not —
# sanitizing keeps every asset addressable from BOTH sides of the boundary.
_FORBIDDEN_CHARS_RE = re.compile(r'[<>:"|?*\x00-\x1f]')
_MAX_NAME_LEN = 150

# Windows reserved device names — bare `NUL` makes os.replace fail with
# FileExistsError on this Windows 11 build (probe-proven), and the classic
# rule also reserves the stem before an extension (`nul.txt`) on older
# views. Sanitized with a `_` prefix (same spirit as the forbidden-char
# substitution) so the asset stays addressable from both sides.
_RESERVED_DEVICE_RE = re.compile(r"^(?:CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])(?:\.|$)",
                                 re.IGNORECASE)

# \\wsl.localhost\<distro>\… or \\wsl$\<distro>\… — a WSL-internal store root.
_UNC_WSL_ROOT_RE = re.compile(
    r"^[\\/]{2}(?:wsl\.localhost|wsl\$)[\\/]([^\\/]+)(?:[\\/]|$)", re.IGNORECASE)

# In-memory upload guard (bytes are held in memory through hash + write).
_DEFAULT_MAX_MB = 256

# The in-code fallback lead line of the message-attachments block (§7.14). The
# shipped default lives verbatim in assets/prompts/actions.md (group
# `attachments`, item `lead`); a project copy overrides it item-wise (§11 #45).
ATTACHMENTS_LEAD = "[Attached files — read each at its listed absolute path]"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _max_bytes() -> int:
    """The ingest size cap (bytes) — ``AWL_ASSET_MAX_MB`` (default 256), read at
    call time so tests/deployments can tune it without a restart."""
    try:
        mb = int(os.environ.get("AWL_ASSET_MAX_MB", "") or _DEFAULT_MAX_MB)
    except ValueError:
        mb = _DEFAULT_MAX_MB
    return max(1, mb) * 1024 * 1024


# ---------------------------------------------------------------------------
# Filename + citation validation
# ---------------------------------------------------------------------------

def safe_asset_filename(filename: str) -> str:
    """Validate + sanitize a client-supplied asset filename; returns the safe name.

    Anything that could escape the asset dir is refused (:class:`ValueError`):
    path separators, any ``..`` occurrence, empty names. Windows-forbidden
    characters (``<>:"|?*`` + control chars) are replaced with ``_`` so the
    name stays addressable from both sides of the WSL boundary; trailing dots/
    spaces (which Windows silently strips) are removed; a leading-dot name is
    prefixed ``_`` (hidden/tmp-style names collide with the internal sidecar +
    temp naming); a Windows reserved device name (``NUL``, ``CON``, ``COM1``…,
    bare or with an extension) is prefixed ``_`` too — bare ``NUL`` breaks
    ``os.replace`` outright on Windows stores, and the WSL leg accepting it
    would leave the asset unreadable from the Windows side. Spaces, unicode,
    and case are **preserved** — each asset owns
    its own ``<asset_id>/`` dir, so case-only collisions between assets cannot
    happen. The reserved ``.meta.json`` suffix is refused. Over-long names are
    truncated to ``_MAX_NAME_LEN`` (150) chars keeping the extension.
    """
    name = (filename or "").strip()
    if not name:
        raise ValueError("filename required")
    if "/" in name or "\\" in name:
        raise ValueError(f"filename must not contain path separators: {filename!r}")
    if ".." in name:
        raise ValueError(f"filename must not contain '..': {filename!r}")
    name = _FORBIDDEN_CHARS_RE.sub("_", name)
    name = name.rstrip(". ")
    if not name:
        raise ValueError(f"filename has no usable characters: {filename!r}")
    if name.startswith("."):
        name = "_" + name.lstrip(".")
    if _RESERVED_DEVICE_RE.match(name):
        name = "_" + name
    if name.lower().endswith(_META_SUFFIX):
        raise ValueError(
            f"the {_META_SUFFIX!r} suffix is reserved for the metadata sidecar: {filename!r}")
    if len(name) > _MAX_NAME_LEN:
        stem, dot, ext = name.rpartition(".")
        if dot and 0 < len(ext) <= 16:
            name = stem[: _MAX_NAME_LEN - len(ext) - 1] + "." + ext
        else:
            name = name[:_MAX_NAME_LEN]
    return name


def _safe_segment(value: str) -> bool:
    """Is ``value`` usable as ONE path segment under the assets dir? (Serve-side
    belt check — the strict gate is the resolve-inside-store check below.)"""
    return bool(value) and "/" not in value and "\\" not in value \
        and ".." not in value and value not in (".",) and "\x00" not in value


def _validate_citation(citation: dict | None) -> dict | None:
    """Normalize the optional citation anchor (§7.14 — Citations ride Attach):
    ``{"doc": <name/path>, "location": <heading/quote/line, optional>}``.
    ``None`` passes through; a present anchor requires a non-empty ``doc``."""
    if citation is None:
        return None
    if not isinstance(citation, dict):
        raise ValueError("citation must be an object with 'doc' (+ optional 'location')")
    doc = str(citation.get("doc") or "").strip()
    if not doc:
        raise ValueError("citation requires a non-empty 'doc'")
    loc = citation.get("location")
    loc = str(loc).strip() if loc is not None else None
    return {"doc": doc, "location": loc or None}


# ---------------------------------------------------------------------------
# Store-kind detection — which write leg does this project need?
# ---------------------------------------------------------------------------

def store_kind(cwd: str | None) -> tuple[str, str | None]:
    """``("windows", None)`` for a drive-letter project root, ``("wsl",
    "<distro>")`` for a WSL-internal one (``\\\\wsl.localhost\\<distro>\\…`` /
    ``\\\\wsl$\\…`` — the distro comes from the canonical root itself, so the
    write leg follows whatever distro actually hosts the project). Raises
    :class:`ValueError` when there is no ``cwd`` (no project store exists).
    Both legs exist and are chosen automatically — callers never pick."""
    root = storage.project_root(cwd)
    if root is None:
        raise ValueError("agent has no cwd; cannot resolve a project store")
    m = _UNC_WSL_ROOT_RE.match(str(root))
    if m:
        return ("wsl", m.group(1))
    return ("windows", None)


# ---------------------------------------------------------------------------
# Ingest — copy bytes into <project>/.awl-cc-dash/assets/<id>/<filename>
# ---------------------------------------------------------------------------

def ingest_bytes(
    cwd: str | None,
    filename: str,
    data: bytes,
    *,
    created_by: str = "user",
    session: str | None = None,
    source: str = "upload",
    citation: dict | None = None,
) -> dict:
    """Materialize one attachment from raw bytes; returns the asset record.

    The canonical record (also written as the ``<filename>.meta.json`` sidecar
    beside the bytes) is project-relative — ``rel_path`` + ``sha256`` + ``size``
    + ``mime`` + ``created`` + provenance (who/when/source) + the optional
    citation anchor — never a receiver-specific absolute path (Option A).
    Writes are atomic (temp + rename) on BOTH legs, and the written bytes are
    hash-verified before the sidecar is written — a failed verification removes
    the file and raises :class:`RuntimeError`, so a torn asset is never
    published. :class:`ValueError` on a bad filename/citation/size or a missing
    ``cwd``.
    """
    if not isinstance(data, (bytes, bytearray)):
        raise ValueError("data must be bytes")
    data = bytes(data)
    if len(data) > _max_bytes():
        raise ValueError(
            f"attachment exceeds the {_max_bytes() // (1024 * 1024)} MB ingest limit")
    name = safe_asset_filename(filename)
    cit = _validate_citation(citation)
    kind, distro = store_kind(cwd)  # raises ValueError when cwd is absent

    asset_id = uuid.uuid4().hex[:12]
    created = _utc_now()
    record = {
        "schema_version": _SCHEMA_VERSION,
        "id": asset_id,
        "filename": name,
        "rel_path": f"{_ASSETS_SUBDIR}/{asset_id}/{name}",
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": len(data),
        "mime": guess_mime(name),
        "created": created,
        "provenance": {
            "created_by": created_by,
            "created_at": created,
            "source": source,
            "session": session,
        },
        "citation": cit,
    }
    meta_bytes = json.dumps(record, indent=2, ensure_ascii=False).encode("utf-8")
    if kind == "wsl":
        _ingest_wsl(cwd, distro or "", asset_id, name, data, meta_bytes,
                    record["sha256"])
    else:
        _ingest_windows(cwd, asset_id, name, data, meta_bytes, record["sha256"])
    logger.info("asset ingested: %s (%s, %d bytes, %s leg)",
                record["rel_path"], record["mime"], record["size"], kind)
    return record


def ingest_source_path(
    cwd: str | None,
    source_path: str,
    filename: str | None = None,
    *,
    created_by: str = "user",
    session: str | None = None,
    citation: dict | None = None,
) -> dict:
    """Materialize one attachment from a local file reference.

    ``source_path`` accepts every spelling the storage layer folds for cwds —
    ``C:\\…``, the ``/mnt/<drive>/…`` WSL alias, a WSL-internal ``/home/…``
    (read over its UNC view), and UNC itself. The bytes are copied (Option A:
    never reference the original in place — it can move/vanish); the original
    spelling is recorded as ``provenance.source`` for audit only. ``filename``
    defaults to the source's basename. :class:`FileNotFoundError` when the
    source doesn't exist; :class:`ValueError` for a directory or an over-cap
    file — the ``AWL_ASSET_MAX_MB`` cap is enforced on ``stat()`` **before**
    the read, so a huge source never buffers into memory just to be refused.
    """
    sp = (source_path or "").strip()
    if not sp:
        raise ValueError("source_path required")
    win = storage.normalize_path_alias(sp)
    p = Path(win)
    if not p.is_file():
        if p.is_dir():
            raise ValueError(f"source_path is a directory, not a file: {source_path}")
        raise FileNotFoundError(source_path)
    if p.stat().st_size > _max_bytes():
        raise ValueError(
            f"attachment exceeds the {_max_bytes() // (1024 * 1024)} MB ingest limit")
    data = p.read_bytes()
    return ingest_bytes(cwd, filename or p.name, data, created_by=created_by,
                        session=session, source=sp, citation=citation)


def _atomic_write(path: Path, data: bytes) -> None:
    """Windows-leg atomic publication: unique ``.tmp-…`` sibling + ``os.replace``
    (a crash mid-write never leaves a torn/partial final file)."""
    tmp = path.with_name(path.name + f".tmp-{uuid.uuid4().hex[:6]}")
    try:
        tmp.write_bytes(data)
        os.replace(tmp, path)
    finally:
        if tmp.exists():  # a failed replace must not leave residue behind
            try:
                tmp.unlink()
            except OSError:
                pass


def _ingest_windows(cwd: str | None, asset_id: str, name: str, data: bytes,
                    meta_bytes: bytes, sha256: str) -> None:
    """The Windows-drive write leg: plain atomic Python I/O + re-read verify."""
    asset_dir = storage.ensure_assets_dir(cwd) / asset_id
    asset_dir.mkdir(parents=True, exist_ok=True)
    final = asset_dir / name
    _atomic_write(final, data)
    readback = hashlib.sha256(final.read_bytes()).hexdigest()
    if readback != sha256:
        try:
            final.unlink()
        except OSError:
            pass
        raise RuntimeError("asset write verification failed (sha256 mismatch after write)")
    _atomic_write(asset_dir / (name + _META_SUFFIX), meta_bytes)


def _wsl_run(distro: str, bash_cmd: str, *, input_bytes: bytes | None = None,
             timeout: int = 120) -> bytes:
    """Run one bash command inside ``distro`` with BINARY stdin/stdout.

    The bridge's ``_run`` is text-mode; asset bytes must never pass through a
    text transformation (line endings, encodings), so this binary twin exists.
    Payloads ride stdin — never the command line (the ~32 KB Windows cap).
    Raises :class:`RuntimeError` with the stderr detail on any failure.
    """
    cmd = ["wsl.exe", "-d", distro, "--", "bash", "-c", bash_cmd]
    try:
        result = subprocess.run(
            cmd, capture_output=True, timeout=timeout,
            input=input_bytes if input_bytes is not None else b"")
    except FileNotFoundError as e:
        raise RuntimeError(f"wsl.exe is not available: {e}")
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"WSL command timed out after {timeout}s: {bash_cmd[:80]}")
    if result.returncode != 0:
        err = (result.stderr or b"").decode("utf-8", "replace").strip()
        raise RuntimeError(err or f"WSL command failed (exit {result.returncode})")
    return result.stdout or b""


def _ingest_wsl(cwd: str | None, distro: str, asset_id: str, name: str,
                data: bytes, meta_bytes: bytes, sha256: str) -> None:
    """The WSL-native write leg (the researched path for WSL-internal stores):
    ``mkdir -p && cat > tmp && mv tmp final`` inside the distro, bytes over
    binary stdin, then an in-distro ``sha256sum`` read-back verify."""
    assets_win = storage.assets_dir(cwd)
    base_wsl = storage.doc_path_wsl(assets_win) if assets_win is not None else None
    if not base_wsl or not base_wsl.startswith("/"):
        raise RuntimeError(
            f"cannot derive a WSL path for the store assets dir: {assets_win}")
    q = shlex.quote
    d = f"{base_wsl}/{asset_id}"
    final = f"{d}/{name}"
    tmp = f"{d}/.ingest-{uuid.uuid4().hex[:6]}.tmp"
    _wsl_run(distro,
             f"mkdir -p {q(d)} && cat > {q(tmp)} && mv {q(tmp)} {q(final)}",
             input_bytes=data)
    out = _wsl_run(distro, f"sha256sum {q(final)}").decode("utf-8", "replace")
    got = out.split()[0] if out.split() else ""
    if got.lower() != sha256:
        _wsl_run(distro, f"rm -f {q(final)}")
        raise RuntimeError(
            "asset write verification failed (sha256 mismatch after WSL write)")
    meta_tmp = f"{d}/.meta-{uuid.uuid4().hex[:6]}.tmp"
    _wsl_run(distro,
             f"cat > {q(meta_tmp)} && mv {q(meta_tmp)} {q(final + _META_SUFFIX)}",
             input_bytes=meta_bytes)


# ---------------------------------------------------------------------------
# Read side — records, listing, and the traversal-safe serve resolution
# ---------------------------------------------------------------------------

def guess_mime(filename: str) -> str:
    """Best-effort MIME from the filename; ``application/octet-stream`` floor."""
    return mimetypes.guess_type(filename)[0] or "application/octet-stream"


def _synthesized_record(asset_id: str | None, file: Path, rel_path: str) -> dict:
    """A degraded record for media with no sidecar (hand-dropped into
    ``assets/`` outside the ingest path) — stat-derived, empty provenance."""
    st = file.stat()
    return {
        "schema_version": _SCHEMA_VERSION,
        "id": asset_id,
        "filename": file.name,
        "rel_path": rel_path,
        "sha256": None,
        "size": st.st_size,
        "mime": guess_mime(file.name),
        "created": datetime.fromtimestamp(st.st_mtime, timezone.utc).isoformat(),
        "provenance": {},
        "citation": None,
    }


def load_asset_record(cwd: str | None, asset_id: str) -> dict | None:
    """The asset record for one id, or ``None`` when it doesn't exist.

    Reads the ``<filename>.meta.json`` sidecar in the asset's dir (UNC reads of
    a WSL-internal store are fine — it is *writes* the WSL leg exists for). A
    missing/corrupt sidecar degrades to a stat-synthesized record (the Library
    read path never fails on unmanaged media); an id that isn't a plain
    directory name under ``assets/`` is ``None``, never an error."""
    base = storage.assets_dir(cwd)
    if base is None or not _safe_segment(asset_id):
        return None
    d = base / asset_id
    if not d.is_dir():
        return None
    try:
        children = sorted(p for p in d.iterdir() if p.is_file())
    except OSError:
        return None
    metas = [p for p in children if p.name.endswith(_META_SUFFIX)]
    for mp in metas:
        try:
            rec = json.loads(mp.read_text(encoding="utf-8") or "{}")
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(rec, dict) and isinstance(rec.get("filename"), str) \
                and rec.get("filename"):
            rec.setdefault("id", asset_id)
            rec.setdefault("rel_path",
                           f"{_ASSETS_SUBDIR}/{asset_id}/{rec['filename']}")
            if not isinstance(rec.get("provenance"), dict):
                rec["provenance"] = {}
            return rec
    files = [p for p in children if not p.name.endswith(_META_SUFFIX)
             and ".tmp" not in p.name]
    if not files:
        return None
    return _synthesized_record(asset_id, files[0],
                               f"{_ASSETS_SUBDIR}/{asset_id}/{files[0].name}")


def list_assets(cwd: str | None) -> list[dict]:
    """Every asset in the open project's ``assets/`` dir, with metadata (§7.16
    — the ``GET /library/assets`` shape: id · filename · mime · size · created
    · provenance, plus rel_path/sha256/citation).

    Ingested assets read their sidecars; asset dirs with no sidecar degrade to
    stat-synthesized records; **loose files** dropped directly under
    ``assets/`` (outside the ingest layout) are listed too — honestly, with
    ``id: null`` (they are visible media, but not addressable by the
    ``/assets/{id}/{filename}`` byte endpoint). A missing dir yields ``[]``.
    Sorted by ``rel_path`` for a stable rendering order."""
    base = storage.assets_dir(cwd)
    if base is None or not base.is_dir():
        return []
    out: list[dict] = []
    for child in sorted(base.iterdir()):
        if child.is_dir():
            rec = load_asset_record(cwd, child.name)
            if rec:
                out.append(rec)
        elif child.is_file() and not child.name.endswith(_META_SUFFIX) \
                and ".tmp" not in child.name:
            out.append(_synthesized_record(
                None, child, f"{_ASSETS_SUBDIR}/{child.name}"))
    out.sort(key=lambda r: r.get("rel_path") or "")
    return out


def asset_file_path(cwd: str | None, asset_id: str, filename: str) -> Path | None:
    """Resolve one asset's on-disk file for serving — strictly inside the store.

    The traversal gate for ``GET /assets/{id}/{filename}``: both segments must
    be plain names (no separators, no ``..``), the metadata sidecar is not
    addressable, and the ``resolve()``d result must live strictly inside the
    store's ``assets/`` dir (symlinks/aliases can't smuggle a path out). Returns
    the resolved existing file, else ``None`` — the endpoint 404s anything else.
    """
    base = storage.assets_dir(cwd)
    if base is None:
        return None
    if not (_safe_segment(asset_id) and _safe_segment(filename)):
        return None
    # Case-INSENSITIVE, matching ingest's reservation: NTFS resolves
    # `photo.png.META.JSON` to the sidecar, so a cased spelling must 404 the
    # same way the exact name does (and the same way an ext4 WSL store does).
    if filename.lower().endswith(_META_SUFFIX):
        return None
    try:
        resolved = (base / asset_id / filename).resolve()
        base_resolved = base.resolve()
    except OSError:
        return None
    if base_resolved not in resolved.parents:
        return None
    if not resolved.is_file():
        return None
    return resolved


# ---------------------------------------------------------------------------
# Per-receiver path rendering (Option A: absolute paths are renderings,
# never stored state)
# ---------------------------------------------------------------------------

def asset_win_path(cwd: str | None, record: dict) -> Path | None:
    """The asset's Windows-side absolute path (the sidecar's own view)."""
    base = storage.assets_dir(cwd)
    if base is None or not record.get("filename"):
        return None
    if record.get("id"):
        return base / str(record["id"]) / str(record["filename"])
    return base / str(record["filename"])  # loose (id-less) media


def render_wsl_path(cwd: str | None, record: dict) -> str | None:
    """The receiving **agent's** rendering: a WSL-readable ABSOLUTE path —
    ``/mnt/<drive>/…`` for a Windows-drive store, the native ``/home/…`` for a
    WSL-internal store. Rides ``storage.doc_path_wsl`` (the same proven
    translation every store path uses), never a re-derivation."""
    p = asset_win_path(cwd, record)
    return storage.doc_path_wsl(p) if p is not None else None


def render_http_url(cwd: str | None, record: dict) -> str | None:
    """The **renderer's** rendering: the sidecar-relative HTTP URL
    (``/assets/{id}/{filename}?cwd=…`` — the client prefixes its sidecar base).
    ``None`` for id-less loose media (not endpoint-addressable)."""
    if not record.get("id") or not record.get("filename"):
        return None
    key = storage.project_key(cwd) or (cwd or "")
    return (f"/assets/{quote(str(record['id']), safe='')}"
            f"/{quote(str(record['filename']), safe='')}"
            f"?cwd={quote(key, safe='')}")


# ---------------------------------------------------------------------------
# The message-attachments block (§7.14 — wired into the send flow)
# ---------------------------------------------------------------------------

def _attachments_lead(cwd: str | None) -> str:
    """The block's lead line, resolved through the §11 #45 prompt library
    (group ``attachments``, item ``lead``; shipped default seeded verbatim in
    ``assets/prompts/actions.md``; project scope overrides). Falls back to the
    in-code :data:`ATTACHMENTS_LEAD` — the library is never the reason a send
    fails."""
    try:
        import prompt_library  # sidecar dir on sys.path — lazy, fault-isolated
        return prompt_library.resolve("attachments", "lead", cwd) or ATTACHMENTS_LEAD
    except Exception:
        return ATTACHMENTS_LEAD


def attachments_block(cwd: str | None, records: list[dict] | None) -> str:
    """The ONE attributed block a prompt carrying attachments delivers (§7.14).

    Lead line (:func:`_attachments_lead`) + one ``- <path>`` bullet per asset,
    where ``<path>`` is the RECEIVING AGENT's readable absolute path
    (:func:`render_wsl_path`). A citation anchor rides its bullet inline —
    ``- <path> (cites <doc> @ <location>)`` — per §7.14 "Citations are built
    with Attach". ``""`` when nothing renders (no records / no paths), so the
    caller appends nothing."""
    lines: list[str] = []
    for rec in records or []:
        path = render_wsl_path(cwd, rec)
        if not path:
            continue
        cite = rec.get("citation") or {}
        suffix = ""
        if isinstance(cite, dict) and cite.get("doc"):
            suffix = f" (cites {cite['doc']}"
            if cite.get("location"):
                suffix += f" @ {cite['location']}"
            suffix += ")"
        lines.append(f"- {path}{suffix}")
    if not lines:
        return ""
    return "\n".join([_attachments_lead(cwd)] + lines)
