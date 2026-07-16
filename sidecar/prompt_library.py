"""Prompt / UI-text markdown library — scope-aware canned text (§7.14, §8.2, §8.4, §11 #45).

One human-editable **markdown library** is the single home for every UI-injected /
canned text the dashboard sends on the user's behalf: the Response (Structure)
preset instructions (§11 #39), the Library/Compose **Revise** and **Summarize**
system texts, the Compose **snippet/template** canned bodies, the attached-docs
launch-preamble lead (§11 #44) — plus more as they surface.

**Two scopes (operator-decided 2026-07-15 — nothing lives in ``~/.claude``):**

  * **Shipped defaults** — committed in-repo at ``assets/prompts/``
    (``responses.md`` · ``snippets.md`` · ``actions.md``), version-controlled and
    travelling with the product (the ``assets/names/agent-names.json`` pattern).
    Edited as source; never written through the API.
  * **Project copy** — ``<project>/.awl-cc-dash/docs/prompts/`` (§8.2), written
    by the product (``POST /prompt-library``), committed with the project.

**Precedence:** project overrides defaults, *item-wise* (a project file that
overrides one item leaves every other item falling through to the shipped
default). A consumer whose item exists in **neither** scope degrades to its
in-code fallback constant (:mod:`response_presets` catalog,
``utility_llm.REVISE_SYSTEMS`` / ``SUMMARIZE_SYSTEM``,
``library.ATTACHED_DOCS_LEAD``) — the library must never be the reason a launch
or a utility pass fails.

**Format:** the ``## group`` / ``### item`` convention. A ``## `` line opens a
group, a ``### `` line under it opens an item, and everything until the next
heading is that item's text (outer blank lines trimmed, inner text verbatim).
Prose before the first ``## `` (a file header) and between a ``## `` and its
first ``### `` (a group preamble) is documentation space — ignored by the
parser, so the files stay self-describing. **Known limitation:** an item body
cannot itself contain lines starting ``## `` / ``### `` (they would re-parse as
structure) — which is why the handoff-report system text, whose body embeds
``##`` section headings, stays in-code in :mod:`utility_llm`.

Write side (:func:`write_item`) targets the **project scope only** and
re-renders the target file in canonical form (group → items → bodies) — sibling
groups/items in that file are preserved through the parse, but free-form prose
a human added to the *project* copy is not (the shipped defaults, where the
documentation prose lives, are never rewritten). A written item lives in
exactly one project file: the target is inferred project-scope-first (then the
shipped defaults), and the write purges the same group/key from every other
project file so a stale duplicate can never shadow it.

Seam notes: reads resolve paths at **call time** (so ``AWL_PROMPT_DEFAULTS`` —
the test/dev override for the defaults dir — and per-call ``cwd`` always apply),
never touch the disk beyond reads, and never create directories; only
:func:`write_item` materializes ``docs/prompts/`` (via ``storage.ensure_docs_dir``,
§8.2's created-as-first-populated rule). Writes are atomic (tmp + ``os.replace``).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import storage

# The shipped default files (organized by purpose, §11 #45). The project scope
# may carry any *.md — both scopes are read as the union of their .md files.
DEFAULT_FILES = ("responses.md", "snippets.md", "actions.md")

_PROMPTS_SUBDIR = "prompts"      # under <project>/.awl-cc-dash/docs/
_MD_SUFFIX = ".md"

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Heading forms. Exactly two / three '#' then whitespace — '####…' and '##…'
# (no space) are body text, so deeper headings can appear inside an item.
_GROUP_RE = re.compile(r"^##\s+(.+?)\s*$")
_ITEM_RE = re.compile(r"^###\s+(.+?)\s*$")

# Project-scope target files: a plain basename, no traversal, .md only.
_SAFE_FILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]*\.md$")


# ---------------------------------------------------------------------------
# Pure parser / renderer — the ##/### convention
# ---------------------------------------------------------------------------

def _trim_outer_blank(lines: list[str]) -> str:
    """Join body lines with the outer blank LINES trimmed — inner text verbatim.

    Only whole blank (whitespace-only) lines at the edges go; the first/last
    content line keeps its leading/trailing whitespace, so indented bodies
    (code-like snippets) survive intact — a plain ``.strip()`` would de-indent
    the first line, and worse, could promote a whitespace-prefixed ``' ## x'``
    into a real heading on the write side."""
    start, end = 0, len(lines)
    while start < end and not lines[start].strip():
        start += 1
    while end > start and not lines[end - 1].strip():
        end -= 1
    return "\n".join(lines[start:end])


def parse_markdown(text: str) -> dict[str, dict[str, str]]:
    """Parse ``## group`` / ``### item`` markdown into ``{group: {item: text}}``.

    Bodies are the raw lines between headings with outer blank lines trimmed
    (inner content verbatim; CRLF normalizes to ``\\n``). File-header prose and
    group preambles are ignored; an item outside any group is ignored; a
    duplicated item within a file resolves last-wins. An empty body is a real
    (present) item with ``""`` text — distinct from a missing item.
    """
    groups: dict[str, dict[str, str]] = {}
    group: str | None = None
    item: str | None = None
    buf: list[str] = []

    def _flush() -> None:
        nonlocal buf
        if group is not None and item is not None:
            groups[group][item] = _trim_outer_blank(buf)
        buf = []

    for line in (text or "").splitlines():
        m = _GROUP_RE.match(line)
        if m:
            _flush()
            group = m.group(1)
            item = None
            groups.setdefault(group, {})
            continue
        m = _ITEM_RE.match(line)
        if m:
            _flush()
            item = m.group(1) if group is not None else None
            if group is not None and item is not None:
                groups[group].setdefault(item, "")
            continue
        buf.append(line)
    _flush()
    return groups


def render_markdown(groups: dict[str, dict[str, str]]) -> str:
    """Render ``{group: {item: text}}`` back to canonical ##/### markdown.

    The inverse of :func:`parse_markdown` up to the outer-blank-line trim — a
    render→parse round-trip preserves every group, item, and (trimmed) body,
    including the first content line's indentation.
    """
    lines: list[str] = []
    for group, items in groups.items():
        lines.append(f"## {group}")
        lines.append("")
        for key, body in items.items():
            lines.append(f"### {key}")
            lines.append("")
            body = _trim_outer_blank((body or "").splitlines())
            if body:
                lines.append(body)
                lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


# ---------------------------------------------------------------------------
# Scope locations + loading
# ---------------------------------------------------------------------------

def defaults_dir() -> Path:
    """The shipped-defaults dir — ``<repo>/assets/prompts/``.

    ``AWL_PROMPT_DEFAULTS`` overrides it (resolved per call, like the other
    ``AWL_*`` storage overrides) so tests can point at a controlled dir.
    """
    override = os.environ.get("AWL_PROMPT_DEFAULTS")
    return Path(override) if override else _REPO_ROOT / "assets" / "prompts"


def project_prompts_dir(cwd: str | None) -> Path | None:
    """``<project>/.awl-cc-dash/docs/prompts/`` for an agent cwd (or ``None``)."""
    d = storage.docs_dir(cwd)
    return None if d is None else d / _PROMPTS_SUBDIR


def _load_dir(directory: Path | None) -> tuple[dict[str, dict[str, str]], dict[str, str]]:
    """Union of every ``*.md`` in ``directory`` → ``(groups, group→filename)``.

    Files merge in sorted-name order; the ``group→filename`` map records the
    FIRST file a group appeared in (the write-side inference home). A missing
    or unreadable dir/file contributes nothing — reads are best-effort.
    """
    groups: dict[str, dict[str, str]] = {}
    homes: dict[str, str] = {}
    if directory is None:
        return groups, homes
    try:
        paths = sorted(directory.glob("*" + _MD_SUFFIX))
    except OSError:  # pragma: no cover - dir vanishing mid-scan
        return groups, homes
    for path in paths:
        try:
            parsed = parse_markdown(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError):
            # Unreadable OR undecodable (cp1252/UTF-16 hand-save) file is
            # skipped — one bad file must never disable the whole library.
            continue
        for group, items in parsed.items():
            homes.setdefault(group, path.name)
            groups.setdefault(group, {}).update(items)
    return groups, homes


def load_defaults() -> dict[str, dict[str, str]]:
    """The shipped-defaults scope as ``{group: {item: text}}``."""
    return _load_dir(defaults_dir())[0]


def load_project(cwd: str | None) -> dict[str, dict[str, str]]:
    """The project scope as ``{group: {item: text}}`` (``{}`` when absent)."""
    return _load_dir(project_prompts_dir(cwd))[0]


def resolved(cwd: str | None = None) -> dict[str, dict[str, str]]:
    """The merged view: defaults with the project scope layered on, item-wise.

    Without a ``cwd`` (no project in play) this is exactly the defaults.
    """
    merged = load_defaults()
    for group, items in load_project(cwd).items():
        merged.setdefault(group, {}).update(items)
    return merged


def resolve(group: str, key: str, cwd: str | None = None,
            default: str | None = None) -> str | None:
    """One item's text by ``group`` + ``key``, project-overrides-defaults.

    Returns the project text when the project scope has the item (a present
    empty body counts — it is a real override), else the shipped default, else
    ``default`` (``None`` = missing, letting consumers apply their in-code
    fallback). Group/key match the heading text exactly (whitespace-trimmed).
    """
    if cwd:
        proj = load_project(cwd)
        if group in proj and key in proj[group]:
            return proj[group][key]
    defaults = load_defaults()
    if group in defaults and key in defaults[group]:
        return defaults[group][key]
    return default


# ---------------------------------------------------------------------------
# Write side — PROJECT scope only (defaults are repo files, edited as source)
# ---------------------------------------------------------------------------

def write_item(cwd: str | None, group: str, key: str, text: str,
               file: str | None = None) -> dict:
    """Upsert ONE item into the project scope and persist it atomically.

    ``file`` names the target ``.md`` inside ``docs/prompts/`` (basename only);
    when omitted it is inferred from where ``group`` already lives — the
    PROJECT scope first (so a project-only group stays updatable without
    re-passing its file), then the shipped defaults. Raises ``ValueError`` for:
    no ``cwd`` (the project scope needs a project home), an unknown group with
    no explicit ``file``, an unsafe file name, an empty/multi-line group or
    key, a body containing ``## ``/``### `` heading lines (they would re-parse
    as structure — the format's documented limitation), or a target file that
    is not valid UTF-8 (never clobbered blind). Existing groups/items in the
    target file are preserved through the parse; the file is re-rendered
    canonically (tmp + ``os.replace``). After the write, the same group/key is
    purged from every OTHER project file (a file emptied by the purge is
    removed) — an item lives in exactly one project file, so a successful
    write is always what reads resolve (sorted-name merging can't shadow it).
    """
    group = (group or "").strip()
    key = (key or "").strip()
    for label, value in (("group", group), ("key", key)):
        if not value:
            raise ValueError(f"prompt-library {label} must be non-empty")
        if "\n" in value or "\r" in value:
            raise ValueError(f"prompt-library {label} must be a single line")
    for line in (text or "").splitlines():
        if _GROUP_RE.match(line) or _ITEM_RE.match(line):
            raise ValueError(
                "item text may not contain '## '/'### ' heading lines — "
                "they are the library's file structure")
    if file is None:
        # Project scope first — the scope being written — then the defaults.
        _, proj_homes = _load_dir(project_prompts_dir(cwd))
        file = proj_homes.get(group)
        if file is None:
            _, homes = _load_dir(defaults_dir())
            file = homes.get(group)
        if file is None:
            raise ValueError(
                f"unknown group {group!r} — pass an explicit target file")
    if not _SAFE_FILE_RE.match(file):
        raise ValueError(f"invalid prompt-library file name {file!r}")
    # ensure_docs_dir raises ValueError itself when cwd is absent (§8.2).
    prompts = storage.ensure_docs_dir(cwd) / _PROMPTS_SUBDIR
    prompts.mkdir(parents=True, exist_ok=True)
    path = prompts / file
    try:
        groups = (parse_markdown(path.read_text(encoding="utf-8-sig"))
                  if path.is_file() else {})
    except UnicodeDecodeError:
        raise ValueError(
            f"existing prompt file {file!r} is not valid UTF-8 — fix or "
            "remove it before writing")
    groups.setdefault(group, {})[key] = _trim_outer_blank((text or "").splitlines())
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(render_markdown(groups), encoding="utf-8")
    os.replace(tmp, path)
    # An item lives in exactly ONE project file: purge the same group/key from
    # every other *.md so the sorted-name last-wins merge in _load_dir can
    # never shadow the write just made (undecodable siblings are left alone —
    # reads skip them anyway).
    for other in sorted(prompts.glob("*" + _MD_SUFFIX)):
        if other.name == file:
            continue
        try:
            other_groups = parse_markdown(other.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeDecodeError):
            continue
        items = other_groups.get(group)
        if items is None or key not in items:
            continue
        del items[key]
        if not items:
            del other_groups[group]
        if other_groups:
            other_tmp = other.with_suffix(other.suffix + ".tmp")
            other_tmp.write_text(render_markdown(other_groups), encoding="utf-8")
            os.replace(other_tmp, other)
        else:
            other.unlink()
    return {"path": str(path), "file": file, "group": group, "key": key,
            "scope": "project"}
