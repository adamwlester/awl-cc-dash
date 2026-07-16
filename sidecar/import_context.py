"""Import external Claude context (§11 #28 — §7.3, §7.16, §8.6).

Pulls an OUTSIDE Claude session (a claude.ai web chat, or a Claude desktop-app
local-agent-mode session) into the dashboard by title, wrapping the working
stdlib exporters at ``dev/tools/claude-context-extractor/`` — ``extract-web.py``
(network + a gitignored ``session_key.txt``) and ``extract-desktop.py`` (local
disk, no auth). The exporters are reused **verbatim** via subprocess shell-out:
this module never reimplements their fetching/rendering; it runs them with
``--out`` pointed at a throwaway dir under ``.scratch/`` and captures the
markdown they write (``--no-open`` always — an import must never pop an editor).

**One engine, one selectable destination** (§11 #28; the operator-recorded lean
is (a) first, (b) close behind, but the engine is destination-agnostic):

* ``"agent"``   — the imported markdown is delivered to a target agent via the
  §7.3 prompt queue (``queue`` disposition — enqueued, never dropped), framed
  with a small attributed header so the agent knows what it is reading.
  Delivery itself is injected (the ``deliver`` callable) so this module stays
  free of the sidecar's session table.
* ``"panel"``   — the rendered markdown is returned to the caller for the
  operator-facing read panel (the acute pain §11 #28 names).
* ``"library"`` — persisted as a Library reference doc (§7.16) under the
  project's ``docs/`` via :func:`library.create_document`, with provenance
  stamped in the ``.meta.json`` sidecar (§8.5): ``created_by="import:<source>"``
  and ``session=<the external conversation/session id>``.

This is distinct from §8.6 (dashboard agents' *own* transcripts, referenced in
place) — imports are outside sessions, captured once as content.

**Honest degrades** — the extractors are external tools with external
prerequisites, so every failure maps to a typed, plain-language error (never a
crash, never a hang):

* :class:`SourceUnavailableError` — the extractor script is missing, the
  claude.ai ``session_key.txt`` is absent/rejected, claude.ai is unreachable,
  or the desktop app's session store isn't on this machine (→ HTTP 400).
* :class:`SessionNotFoundError` — no session title matches (→ HTTP 404).
* :class:`ExtractorTimeoutError` — the subprocess exceeded the bounded timeout
  (``AWL_IMPORT_TIMEOUT`` seconds, default 120) and was killed (→ HTTP 504).
* :class:`ImportContextError` — the base: any other extractor failure,
  including an ambiguous title (its message lists the candidates) (→ HTTP 400).

Hermetically testable: tests fake :func:`_run` (no subprocess) and point
``AWL_IMPORT_SCRATCH`` at a temp dir. See ``tests/test_import_context_unit.py``.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

import library

# ---------------------------------------------------------------------------
# Locations & knobs
# ---------------------------------------------------------------------------

# This file lives at <repo>/sidecar/, so the repo root is one up.
REPO_ROOT = Path(__file__).resolve().parents[1]
# The working exporters, reused verbatim (§11 #28).
TOOL_DIR = REPO_ROOT / "dev" / "tools" / "claude-context-extractor"

_SCRIPTS = {
    "web": "extract-web.py",
    "desktop": "extract-desktop.py",
}
SOURCES = tuple(_SCRIPTS)
DESTINATIONS = ("agent", "panel", "library")

# Bounded subprocess timeout (seconds) — the web extractor does real network
# I/O, so give it room, but a wedged extractor must never hang the sidecar.
DEFAULT_TIMEOUT_S = 120.0


def _timeout_s() -> float:
    """The extractor-subprocess timeout, env-configurable via
    ``AWL_IMPORT_TIMEOUT`` (seconds). Read at call time; an unparsable value
    falls back to the default."""
    raw = os.environ.get("AWL_IMPORT_TIMEOUT", "")
    try:
        return float(raw) if raw else DEFAULT_TIMEOUT_S
    except ValueError:
        return DEFAULT_TIMEOUT_S


def _scratch_base() -> Path:
    """Where per-import ``--out`` temp dirs live: ``<repo>/.scratch/import-context/``
    (transient artifacts belong in ``.scratch/``), overridable for tests via
    ``AWL_IMPORT_SCRATCH``."""
    override = os.environ.get("AWL_IMPORT_SCRATCH", "")
    return Path(override) if override else REPO_ROOT / ".scratch" / "import-context"


# ---------------------------------------------------------------------------
# Typed degrade errors (main maps these to plain HTTP responses)
# ---------------------------------------------------------------------------

class ImportContextError(Exception):
    """Base: the import could not complete — carries a plain-language message."""


class SourceUnavailableError(ImportContextError):
    """A source prerequisite is absent: missing extractor script, missing or
    rejected claude.ai session key, unreachable network, or no desktop-app
    session store on this machine."""


class SessionNotFoundError(ImportContextError):
    """No external session title matched the requested title."""


class ExtractorTimeoutError(ImportContextError):
    """The extractor subprocess exceeded the bounded timeout and was killed."""


# ---------------------------------------------------------------------------
# Subprocess seam (faked in unit tests)
# ---------------------------------------------------------------------------

def _script(source: str) -> Path:
    """The extractor script for ``source``. ``ValueError`` on an unknown source
    (a caller bug / bad request); :class:`SourceUnavailableError` when the
    script itself is missing from the tree."""
    if source not in _SCRIPTS:
        raise ValueError(f"source must be one of {'|'.join(SOURCES)}, not {source!r}")
    script = TOOL_DIR / _SCRIPTS[source]
    if not script.is_file():
        raise SourceUnavailableError(
            f"the {source} extractor is missing — expected it at {script} "
            "(dev/tools/claude-context-extractor/)")
    return script


def _run(source: str, args: list[str], timeout_s: float | None = None
         ) -> subprocess.CompletedProcess:
    """Run one extractor invocation (stdlib CLI, reused verbatim) with a hard
    timeout. Output is captured, never streamed; nothing here opens a window
    (callers always pass ``--no-open`` on export paths). Raises
    :class:`ExtractorTimeoutError` when the bounded timeout expires (the child
    is killed by ``subprocess.run``) and :class:`SourceUnavailableError` when
    the interpreter/script cannot be launched at all."""
    script = _script(source)
    cmd = [sys.executable, str(script), *args]
    limit = timeout_s if timeout_s is not None else _timeout_s()
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=limit)
    except subprocess.TimeoutExpired:
        raise ExtractorTimeoutError(
            f"the {source} extractor did not finish within {limit:.0f}s and was "
            "stopped — claude.ai may be slow or unreachable; try again, or check "
            "the tool by hand (dev/tools/claude-context-extractor/)")
    except OSError as e:
        raise SourceUnavailableError(f"could not launch the {source} extractor: {e}")


def _classify_failure(source: str, proc: subprocess.CompletedProcess,
                      title: str | None = None) -> ImportContextError:
    """Map a non-zero extractor exit to the honest typed error. The exporters
    fail via ``sys.exit(<message>)`` (message on stderr), so the wording below
    is matched against their actual exit strings.

    Two defenses keep the mapping honest: the by-title outcomes (no-match /
    ambiguous) are checked FIRST, and every matcher is anchored to a line start
    (``re.M``) — because the no-match message embeds the operator's queried
    title verbatim (``No conversation title matching "<title>".``) and the
    ambiguous listing prints candidate titles, an unanchored substring like
    ``HTTP 401`` or ``Network error`` inside a title must never masquerade as
    a source-prerequisite failure (which would send the operator off to rotate
    a perfectly good session key)."""
    text = "\n".join(filter(None, [(proc.stderr or "").strip(),
                                   (proc.stdout or "").strip()]))
    if re.search(r"^No (?:conversation|session) title matching ", text, re.M):
        wanted = f' "{title}"' if title else ""
        return SessionNotFoundError(
            f"no {source} session title matches{wanted} — list the sessions and "
            "pick an exact title")
    if re.search(r'^".*" is ambiguous — \d+ matches:', text, re.M):
        return ImportContextError(
            f"that title matches more than one {source} session — refine it to "
            f"an exact title. Extractor said: {text[:800]}")
    if re.search(r"^No sessionKey", text, re.M):
        return SourceUnavailableError(
            "the claude.ai import needs your logged-in sessionKey — paste it "
            "into dev/tools/claude-context-extractor/session_key.txt (gitignored; "
            "the tool README shows where to find it in your browser)")
    if re.search(r"^HTTP (?:401|403) on ", text, re.M):
        return SourceUnavailableError(
            "claude.ai rejected the stored session key (expired or logged out) — "
            "refresh dev/tools/claude-context-extractor/session_key.txt and retry")
    if re.search(r"^Network error on ", text, re.M):
        return SourceUnavailableError(
            "could not reach claude.ai — check the network connection and retry")
    if re.search(r"^No local-agent-mode session store", text, re.M):
        return SourceUnavailableError(
            "no Claude desktop-app session store was found on this machine — "
            "desktop imports need the Claude desktop app (and at least one "
            "local-agent-mode session)")
    tail = text[-800:] if text else "(no output)"
    return ImportContextError(f"the {source} extractor failed: {tail}")


# ---------------------------------------------------------------------------
# list_external — enumerate importable outside sessions by title
# ---------------------------------------------------------------------------

# extract-web.py --list rows: "<updated_at[:19]>  <uuid>  <title>"
_WEB_ROW = re.compile(
    r"^(?P<updated>\S*)\s{2}"
    r"(?P<id>[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\s{2}"
    r"(?P<title>.*)$")

# extract-desktop.py --list rows: "  <when:16>  <model:16>  <title>"
_DESKTOP_ROW = re.compile(
    r"^\s{2}(?P<when>\d{4}-\d{2}-\d{2} \d{2}:\d{2}|\?)\s+"
    r"(?P<model>\S+)\s{2,}(?P<title>.+)$")


def list_external(source: str, timeout_s: float | None = None) -> list[dict[str, Any]]:
    """List an external source's sessions by title (the extractor's ``--list``).

    Returns a uniform row shape for both sources:
    ``{"source", "id", "title", "updated_at", "model"}`` — ``id`` is the
    claude.ai conversation uuid (``None`` for desktop rows, which the tool
    lists by title only) and ``model`` is desktop-only. Non-row output lines
    (headers, hints, blanks) are skipped. Raises the module's typed errors on
    any extractor failure (see the module docstring)."""
    proc = _run(source, ["--list"], timeout_s=timeout_s)
    if proc.returncode != 0:
        raise _classify_failure(source, proc)
    rows: list[dict[str, Any]] = []
    for line in (proc.stdout or "").splitlines():
        if not line.strip():
            continue
        if source == "web":
            m = _WEB_ROW.match(line)
            if m:
                rows.append({
                    "source": "web",
                    "id": m.group("id"),
                    "title": m.group("title").strip(),
                    "updated_at": m.group("updated") or None,
                    "model": None,
                })
        else:
            m = _DESKTOP_ROW.match(line)
            if m:
                when = m.group("when")
                rows.append({
                    "source": "desktop",
                    "id": None,
                    "title": m.group("title").strip(),
                    "updated_at": None if when == "?" else when,
                    "model": m.group("model"),
                })
    return rows


# ---------------------------------------------------------------------------
# fetch_markdown — export one session by title, capture the markdown
# ---------------------------------------------------------------------------

# The export's own header carries the external id: "- conversation: <uuid>"
# (web) / "- session: <id>" (desktop).
_EXTERNAL_ID = re.compile(r"^- (?:conversation|session): (.+)$", re.M)


def fetch_markdown(source: str, title: str, timeout_s: float | None = None
                   ) -> dict[str, Any]:
    """Export one outside session by title and capture its rendered markdown.

    Runs the extractor with ``--name=<title> --out <temp dir> --no-open`` (the
    equals-form spelling, so a dash-leading title like ``-drafts`` binds as the
    value instead of being refused by argparse as an option-like token; the
    temp dir is a throwaway under ``.scratch/import-context/`` — see
    :func:`_scratch_base`),
    reads the ``.md`` it wrote into memory, and removes the temp dir (the
    sidecar keeps the content, not the export droppings). Returns
    ``{"source", "title_query", "title", "filename", "external_id", "markdown"}``
    — ``title`` is the export's own heading (falls back to the query),
    ``external_id`` the conversation/session id parsed from the export header
    (may be ``None``). Raises the module's typed errors on failure, including
    :class:`ImportContextError` when the extractor exits 0 but wrote no
    markdown (never a silent empty import)."""
    if not (title or "").strip():
        raise ValueError("title is required")
    out_dir = _scratch_base() / f"import-{uuid.uuid4().hex[:8]}"
    out_dir.mkdir(parents=True, exist_ok=True)
    try:
        proc = _run(source, [f"--name={title}", "--out", str(out_dir), "--no-open"],
                    timeout_s=timeout_s)
        if proc.returncode != 0:
            raise _classify_failure(source, proc, title=title)
        exports = sorted(
            (p for p in out_dir.glob("*.md") if not p.name.endswith(".summary.md")),
            key=lambda p: p.stat().st_mtime, reverse=True)
        if not exports:
            raise ImportContextError(
                f"the {source} extractor reported success but wrote no markdown "
                f"export for \"{title}\" — nothing to import")
        md_path = exports[0]
        markdown = md_path.read_text(encoding="utf-8", errors="replace")
        heading = next((ln[2:].strip() for ln in markdown.splitlines()
                        if ln.startswith("# ")), None)
        m = _EXTERNAL_ID.search(markdown)
        return {
            "source": source,
            "title_query": title,
            "title": heading or title,
            "filename": md_path.name,
            "external_id": m.group(1).strip() if m else None,
            "markdown": markdown,
        }
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Destination routing — one engine, one selectable destination
# ---------------------------------------------------------------------------

_SOURCE_LABELS = {"web": "claude.ai (web)", "desktop": "the Claude desktop app"}


def render_agent_prompt(fetched: dict[str, Any]) -> str:
    """Frame the imported markdown for agent delivery: a small attributed
    header (like the §7.6 piggyback block) so the receiving agent knows this is
    imported outside context handed over by the operator, then the export
    verbatim."""
    label = _SOURCE_LABELS.get(fetched.get("source", ""), fetched.get("source", "?"))
    header = (f"[Imported external Claude context — \"{fetched.get('title')}\" "
              f"from {label}, delivered by the operator for your reference]")
    return f"{header}\n\n{fetched.get('markdown', '')}"


def _to_library(fetched: dict[str, Any], cwd: str | None) -> dict[str, Any]:
    """Persist the import as a Library reference doc (§7.16) with provenance.

    Writes ``<project>/.awl-cc-dash/docs/<export-filename>.md`` via
    :func:`library.create_document` (which validates the filename and needs a
    project home — ``ValueError`` without one), disambiguating ``-2``/``-3``…
    rather than clobbering an existing doc, then stamps provenance in the
    ``.meta.json`` sidecar (§8.5): ``created_by="import:<source>"`` +
    ``session=<external id>``."""
    base = Path(fetched["filename"]).stem
    doc: dict[str, Any] | None = None
    for n in range(1, 100):
        candidate = f"{base}.md" if n == 1 else f"{base}-{n}.md"
        try:
            doc = library.create_document(cwd, candidate,
                                          fetched["markdown"], subdir="docs")
            break
        except FileExistsError:
            continue
    if doc is None:  # pragma: no cover - 99 same-named imports
        raise ImportContextError(
            f"could not find a free filename for {base}.md in the Library")
    created_by = f"import:{fetched['source']}"
    library.set_provenance(doc["path"], created_by=created_by,
                           session=fetched.get("external_id"))
    return {**doc, "provenance": {"created_by": created_by,
                                  "session": fetched.get("external_id")}}


def import_by_title(source: str, title: str, destination: str,
                    target_agent: str | None = None, cwd: str | None = None, *,
                    deliver: Callable[[str, str], dict[str, Any]] | None = None,
                    timeout_s: float | None = None) -> dict[str, Any]:
    """The §11 #28 engine: pull one outside session by title, route it to ONE
    destination.

    ``destination``:

    * ``"agent"``   — requires ``target_agent`` and a ``deliver`` callable
      (``deliver(target_agent, prompt_text) -> dict``, supplied by the sidecar:
      it enqueues on the target's §7.3 prompt queue). The delivered text is the
      attributed :func:`render_agent_prompt` framing.
    * ``"panel"``   — the result carries the rendered ``markdown`` for the
      operator read panel.
    * ``"library"`` — requires a ``cwd`` with a project home; writes the doc +
      provenance (see :func:`_to_library`).

    ``ValueError`` on an unknown destination or missing destination
    prerequisites (caller/request errors); the module's typed
    :class:`ImportContextError` family for extractor failures."""
    if destination not in DESTINATIONS:
        raise ValueError(
            f"destination must be one of {'|'.join(DESTINATIONS)}, not {destination!r}")
    if destination == "agent" and not target_agent:
        raise ValueError("destination 'agent' requires target_agent")
    if destination == "agent" and deliver is None:
        raise ValueError("destination 'agent' requires a deliver callable")
    if destination == "library" and not cwd:
        # Checked BEFORE the (network-bound) fetch — a request that can never
        # land must not cost an up-to-timeout extractor run first.
        raise ValueError(
            "destination 'library' requires cwd (the project whose "
            ".awl-cc-dash/docs/ the imported doc lands under)")

    fetched = fetch_markdown(source, title, timeout_s=timeout_s)
    base = {"source": source, "destination": destination,
            "title": fetched["title"], "filename": fetched["filename"],
            "external_id": fetched["external_id"]}

    if destination == "panel":
        return {**base, "markdown": fetched["markdown"]}
    if destination == "library":
        stored = _to_library(fetched, cwd)
        return {**base, **stored}
    # destination == "agent"
    delivered = deliver(target_agent, render_agent_prompt(fetched))  # type: ignore[misc]
    return {**base, "target_agent": target_agent,
            "delivery": delivered if isinstance(delivered, dict) else {}}
