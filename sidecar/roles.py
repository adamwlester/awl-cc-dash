"""Agent roles — the two-scope ``agent.md`` preset catalog (DESIGN.md's ND 12 Role combobox).

The Create panel's Role combobox is the **agent.md preset loader**: picking a
role auto-fills the Create fields from the file's front matter. Entries group
by the settled two-scope model this module reads:

  * **System** — the persistent cross-project store, ``~/.claude/agents`` (the
    old "User" scope folded in). Claude Code's own config is **surfaced, not
    owned** (the storage doctrine): read in place, never copied or written.
    ``AWL_SYSTEM_AGENTS_DIR`` overrides the location — resolved per call, like
    the other ``AWL_*`` storage overrides — so the unit tier stays hermetic.
  * **Project** — ``<project>/.awl-cc-dash/agents/`` (``storage.agents_dir``,
    §8.2): project ``agent.md`` role presets committed with the repo.

**Front matter** is parsed by a deliberately small hand parser (no PyYAML — the
observed agent.md corpus uses only a shallow subset): ``---`` fences,
``key: value`` scalars, inline comma lists (``tools: Read, Glob,
mcp__context7__*``), YAML block lists (``skills:`` followed by ``  - distill``
lines), and ``#``-commented lines ignored (so a ``#model: fable`` never
shadows the live ``model:``). A file with no front matter at all parses as
``({}, body)``. Normalized keys: ``name`` (fallback: the filename stem),
``description``, ``color``, ``model``, ``tools``, ``skills``,
``permission_mode``, ``max_turns`` (int), ``effort`` — the wire payload is
snake_case like the rest of the sidecar API, even though the agent.md
front-matter spellings they're read FROM stay camelCase (``permissionMode``,
``maxTurns`` — the file convention).

**Color:** the files use Claude Code's *named*-color convention (``purple``,
``orange``, …) while the dashboard's identity color is an ``--ag-*`` hex
(:data:`identity.AG_COLORS`). Each role therefore carries BOTH ``color`` (the
raw front-matter value) and ``color_hex`` — a raw ``#rrggbb`` passes through
as-is, a known name maps via :data:`NAMED_COLOR_TO_HEX`, anything else (or no
color) is ``None``. The mapping must happen before ``POST /sessions`` (its
``IdentityInput.color`` expects hex), so it lives here beside the parse.

The listing payload stays LIGHT: the normalized front-matter fields plus
``file`` (absolute path) and ``scope`` — the markdown body (the role's
system-prompt text) is deliberately NOT returned. Pure functions, no FastAPI;
paths resolve at call time; reads never create directories (only a future
write side would, via ``storage.ensure_agents_dir``).
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Any

import storage
from identity import AG_COLORS

logger = logging.getLogger("awl-sidecar.roles")

# The combobox group headers — exactly the mockup's ROLE_DEFS group strings
# (design/behavior.js), so the endpoint reproduces the designed labels.
SYSTEM_LABEL = "System agents (~/.claude/agents · cross-project)"
PROJECT_LABEL = "Project agents (<project>/.awl-cc-dash/agents)"

_MD_SUFFIX = ".md"
_FENCE = "---"

# `key: value` — a front-matter key starts a line (no indent), letters first.
_KEY_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*)\s*:\s*(.*)$")
# `- item` — a YAML block-list entry (dash at ANY indent, zero included:
# `tools:\n- Read` is valid, common YAML that PyYAML parses identically to the
# indented form). Safe unanchored: appends are gated on an open list key, and
# _KEY_RE's letter-first anchor keeps keys and items unambiguous.
_LIST_ITEM_RE = re.compile(r"^\s*-\s+(.*)$")
_HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")

# Keys whose values are lists: inline (`tools: Read, Glob`) or block form.
_LIST_KEYS = {"tools", "skills"}

# Claude Code's subagent `color:` convention is a small NAMED set (observed:
# orange/green/purple/pink; the CLI's palette adds red/blue/yellow/cyan). The
# dashboard needs an `--ag-*` hex, so each name maps to the nearest-feel
# AG_COLORS token (chosen by eye against the token swatches):
#   red    -> vermilion #af3c3a (the truest red; crimson reads pink-shifted)
#   blue   -> cobalt    #006bbb (the primary blue; azure/indigo are shifted)
#   green  -> emerald   #008149 (the primary green; fern reads olive)
#   yellow -> citron    #876300 (the yellow-olive token; gold reads orange)
#   purple -> violet    #7152b5 (the primary purple; orchid reads magenta)
#   orange -> amber     #aa4600
#   pink   -> magenta   #9e3f84 (the pink-leaning token; orchid reads purple)
#   cyan   -> cyan      #007f91 (name collision IS the mapping)
# The AG_COLORS names themselves (crimson, fern, teal, …) also map — to their
# own hex — so a role authored with a dashboard token name round-trips.
_AG_BY_NAME = dict(AG_COLORS)
NAMED_COLOR_TO_HEX: dict[str, str] = {
    **_AG_BY_NAME,
    "red": _AG_BY_NAME["vermilion"],
    "blue": _AG_BY_NAME["cobalt"],
    "green": _AG_BY_NAME["emerald"],
    "yellow": _AG_BY_NAME["citron"],
    "purple": _AG_BY_NAME["violet"],
    "orange": _AG_BY_NAME["amber"],
    "pink": _AG_BY_NAME["magenta"],
    # "cyan" is already present from AG_COLORS.
}


# ---------------------------------------------------------------------------
# Scope locations
# ---------------------------------------------------------------------------

def system_agents_dir() -> Path:
    """The System scope — ``~/.claude/agents`` (Windows home; surfaced, not owned).

    ``AWL_SYSTEM_AGENTS_DIR`` overrides it (resolved per call) so tests can
    point at a controlled fixture dir.
    """
    override = os.environ.get("AWL_SYSTEM_AGENTS_DIR")
    return Path(override) if override else Path.home() / ".claude" / "agents"


def project_agents_dir(cwd: str | None) -> Path | None:
    """The Project scope — ``<project>/.awl-cc-dash/agents/`` (or ``None`` cwd-less)."""
    return storage.agents_dir(cwd)


# ---------------------------------------------------------------------------
# Front-matter parsing (hand-rolled — the observed shallow YAML subset only)
# ---------------------------------------------------------------------------

def _unquote(value: str) -> str:
    """Strip one pair of matched surrounding quotes (YAML-style ``"…"``/``'…'``).

    Real files quote values whose content would otherwise be misread — e.g.
    ``color: "#E879F9"`` (gsd-ui-researcher.md), where the bare ``#`` would look
    like a comment. Only a *matched* pair is stripped, once — interior quotes
    survive untouched.
    """
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    """Split an ``agent.md`` into ``(front-matter dict, markdown body)``.

    Handles ``---`` fences, ``key: value`` scalars, inline comma lists for the
    known list keys, block lists (``key:`` + ``- item`` lines at any indent,
    zero-indent included), and
    ignores ``#``-commented and blank lines (without breaking an open block
    list). No opening fence → ``({}, text)`` — the whole file is body. An
    unterminated fence consumes to EOF (body ``""``) rather than erroring.
    """
    lines = (text or "").splitlines()
    if not lines or lines[0].strip() != _FENCE:
        return {}, text or ""
    fm: dict[str, Any] = {}
    open_list: str | None = None   # key collecting `- item` lines, if any
    i = 1
    while i < len(lines):
        line = lines[i]
        i += 1
        if line.strip() == _FENCE:
            break
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue               # comment/blank — an open block list survives
        m_item = _LIST_ITEM_RE.match(line)
        if m_item and open_list is not None:
            fm.setdefault(open_list, [])
            if isinstance(fm[open_list], list):
                fm[open_list].append(_unquote(m_item.group(1).strip()))
            continue
        m = _KEY_RE.match(line)
        if m:
            key, value = m.group(1), m.group(2).strip()
            if value == "":
                open_list = key    # a block list may follow
                fm.setdefault(key, [])
            else:
                open_list = None
                if key in _LIST_KEYS:
                    fm[key] = [_unquote(v.strip()) for v in value.split(",") if v.strip()]
                else:
                    fm[key] = _unquote(value)
            continue
        open_list = None           # unrecognized content ends any block list
    body = "\n".join(lines[i:])
    return fm, body


def _scalar(fm: dict[str, Any], key: str) -> str | None:
    v = fm.get(key)
    if isinstance(v, list):
        return v[0] if v else None
    if isinstance(v, str) and v:
        return v
    return None


def _string_list(fm: dict[str, Any], key: str) -> list[str] | None:
    v = fm.get(key)
    if isinstance(v, list):
        return [str(x) for x in v]
    if isinstance(v, str) and v:
        return [p.strip() for p in v.split(",") if p.strip()]
    return None


def _int_or_none(value: Any) -> int | None:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def color_hex_for(color: str | None) -> str | None:
    """A raw ``#rrggbb`` passes through; a known name maps; else ``None``."""
    if not color:
        return None
    color = color.strip()
    if _HEX_RE.match(color):
        return color
    return NAMED_COLOR_TO_HEX.get(color.lower())


# ---------------------------------------------------------------------------
# Role listing
# ---------------------------------------------------------------------------

def parse_role_file(path: Path, scope: str) -> dict[str, Any]:
    """One ``agent.md`` → the LIGHT role payload (front matter, no body)."""
    fm, _ = parse_front_matter(path.read_text(encoding="utf-8-sig"))
    color = _scalar(fm, "color")
    return {
        "name": _scalar(fm, "name") or path.stem,
        "description": _scalar(fm, "description"),
        "color": color,
        "color_hex": color_hex_for(color),
        "model": _scalar(fm, "model"),
        "tools": _string_list(fm, "tools"),
        "skills": _string_list(fm, "skills"),
        # Wire keys are snake_case (the sidecar API convention); the values
        # are still read from the camelCase agent.md front-matter spellings.
        "permission_mode": _scalar(fm, "permissionMode"),
        "max_turns": _int_or_none(fm.get("maxTurns")),
        "effort": _scalar(fm, "effort"),
        "file": str(path.resolve()),
        "scope": scope,
    }


def list_roles(directory: Path | None, scope: str) -> list[dict[str, Any]]:
    """Every ``*.md`` role in ``directory``, sorted by name.

    Best-effort like the prompt library's reads: a missing/unreadable dir
    contributes nothing, and an unreadable/undecodable file is skipped (debug
    log) — one bad file must never disable the whole catalog. Non-``.md``
    files are ignored.
    """
    if directory is None:
        return []
    try:
        paths = sorted(directory.glob("*" + _MD_SUFFIX))
    except OSError:  # pragma: no cover - dir vanishing mid-scan
        return []
    roles: list[dict[str, Any]] = []
    for path in paths:
        try:
            roles.append(parse_role_file(path, scope))
        except (OSError, UnicodeDecodeError) as e:
            logger.debug("skipping unreadable agent.md %s: %s", path, e)
    roles.sort(key=lambda r: (r["name"] or "").lower())
    return roles
