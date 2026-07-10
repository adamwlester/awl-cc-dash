"""Storage & scoping homes — the one canonical model for *where data lives*.

One rule (ARCHITECTURE §8.1): **anything about a specific project or its team
lives in that project's folder; only reusable building blocks live with the
dashboard; Claude's own data is surfaced or referenced, never owned or copied.**

  🏠 **Dashboard** — ``sidecar/runtime/`` (override ``AWL_SIDECAR_RUNTIME``):
      the app's shared toolbox — Setups, prompt templates, and the projects
      index. Reusable, project-agnostic. (Canonical accessor:
      :func:`dashboard_runtime_dir`, == ``runtime_store.runtime_dir``.)

  📁 **Project** — ``<project>/.awl-cc-dash/`` where ``<project>`` is the
      **canonical repo root** derived from an agent's ``cwd`` (git top-level,
      symlink + ``/mnt``-alias normalized, WSL-internal POSIX homes mapped to
      their ``\\\\wsl.localhost\\<distro>\\…`` UNC form — :func:`project_root`):
      everything about ONE project and its team, committed so it travels with
      the repo.
      Subdir taxonomy (§8.2): ``plans/`` · ``docs/`` (scratchpad lives here) ·
      ``assets/`` · ``state/`` (dashboard-owned JSON state). Subdirs are created
      as they are first populated — no empty scaffolding.

  👥 **Setup** — a reusable team (roster only). A dashboard concept saved in the
      dashboard store, *not* a folder.

Claude Code's own config (``~/.claude``, ``<project>/.claude``) is **surfaced,
not owned** — the dashboard reads/edits it in place; it does not store it here.

**Tie-breaker for fuzzy cases:** is this about *one project*, or reusable across
projects? One project → ``<project>/.awl-cc-dash/``; reusable → the dashboard store.

The project home is WSL-reachable via the proven Windows↔WSL2 translation
(``bridge.paths.win_to_wsl`` — the same mechanism ``mcp_sync`` uses); we reuse it
rather than re-solving path normalization per feature.
"""

from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

import runtime_store

logger = logging.getLogger("awl-sidecar.storage")

# Reuse the proven WSL2↔Windows path translation from the bridge package. The
# sidecar runs with its own dir on sys.path (not the repo root), so add the repo
# root the way the bridge driver does, then import the shared utility. A local
# fallback keeps this module importable even if the bridge package is absent
# (e.g. a stripped test env) — it must never be the reason storage can't load.
_REPO_ROOT = str(Path(__file__).resolve().parents[1])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

try:
    from bridge import paths as _bridge_paths  # type: ignore[import-not-found]
    win_to_wsl = _bridge_paths.win_to_wsl
except Exception:  # pragma: no cover - exercised only when bridge is unavailable
    _bridge_paths = None

    def win_to_wsl(path):  # type: ignore[no-redef]
        """Fallback copy of the proven translation (see ``bridge/paths.py``)."""
        if not path:
            return path
        if path.startswith("/"):
            return path
        path = path.replace("\\", "/")
        m = re.match(r"^([A-Za-z]):/(.*)$", path)
        if m:
            return f"/mnt/{m.group(1).lower()}/{m.group(2)}"
        return path

# The WSL distro anchoring the \\wsl.localhost\<distro>\ UNC form of a
# WSL-INTERNAL cwd. bridge.paths doesn't currently export a distro constant
# (TmuxBridge defaults its own ctor arg), so probe for one and fall back to
# the same "Ubuntu" default the bridge uses.
_WSL_DISTRO: str = getattr(_bridge_paths, "DEFAULT_DISTRO", None) or "Ubuntu"


# Project-home directory + the files that live in it. The folder spells out the
# product name — deliberately NOT `.awl` (too vague) and NOT `.cc-dash` (reads
# as Claude Code's own config, which is `.claude/`). §8.2.
_AWL_DIRNAME = ".awl-cc-dash"
_LEGACY_AWL_DIRNAME = ".awl"          # pre-rename home; migrated on touch
_SCRATCHPAD_NAME = "scratchpad.md"    # shared team scratchpad (docs/)
_PLAN_REVIEWS_NAME = "plan-reviews.json"  # LEGACY review side-store (superseded by per-doc .meta.json sidecars)

# §8.2 subdir taxonomy.
_PLANS_SUBDIR = "plans"
_DOCS_SUBDIR = "docs"
_ASSETS_SUBDIR = "assets"
_STATE_SUBDIR = "state"

# Dashboard-store files (project-agnostic, reusable).
_SETUPS_NAME = "setups.json"      # saved Setups (rosters)
_TEMPLATES_NAME = "templates.json"  # reusable prompt templates
_PROJECTS_INDEX_NAME = "projects.json"  # known project roots + last-opened (§3.5)


# ---------------------------------------------------------------------------
# 🏠 Dashboard store (reusable, project-agnostic)
# ---------------------------------------------------------------------------

def dashboard_runtime_dir() -> Path:
    """The 🏠 Dashboard home — exactly ``runtime_store.runtime_dir()``.

    Single source of truth: Setups, templates, and the projects index sit
    here, never under a project's ``.awl-cc-dash/``.
    """
    return runtime_store.runtime_dir()


def setups_path() -> Path:
    """Saved Setups (rosters) — a dashboard-store file."""
    return dashboard_runtime_dir() / _SETUPS_NAME


def templates_path() -> Path:
    """Saved prompt templates — a dashboard-store file (project-agnostic by design, §7.14)."""
    return dashboard_runtime_dir() / _TEMPLATES_NAME


def projects_index_path() -> Path:
    """The known-projects index ``projects.json`` (§3.5) — a dashboard-store file.

    The list of known canonical project roots plus last-opened times. Powers the
    Projects picker and makes cold discovery after a reboot possible (the app
    cannot scan the disk for ``.awl-cc-dash/`` folders).
    """
    return dashboard_runtime_dir() / _PROJECTS_INDEX_NAME


# ---------------------------------------------------------------------------
# 📁 Project home — canonical root derivation (§8.1 "<project> defined")
# ---------------------------------------------------------------------------

_MNT_RE = re.compile(r"^/mnt/([A-Za-z])(/.*)?$")


def _normalize_alias(cwd: str) -> str:
    """Fold every cwd spelling to ONE canonical Windows-side form.

    The sidecar runs on Windows; an agent's cwd may arrive in several
    spellings, and all of them must land on one canonical form so a project
    never splits across two stores:

      * ``/mnt/<drive>/…`` (the WSL alias of a Windows path) folds back to
        ``X:\\…``.
      * A POSIX-rooted path that is NOT ``/mnt/<drive>/…`` is a true
        **WSL-internal** home (e.g. ``/home/lester/x``) — its canonical
        Windows-side form is the ``\\\\wsl.localhost\\<distro>\\…`` UNC path.
        (Passing it through unchanged, the old behavior, made ``Path.resolve``
        anchor it to the Windows current drive — ``C:\\home\\…`` — corrupting
        the key.)
      * UNC inputs (``\\\\wsl.localhost\\…`` and other shares) pass through;
        ``Path.resolve()`` normalizes them, so both spellings of a WSL-internal
        root yield ONE project key.
    """
    posix = cwd.replace("\\", "/")
    if posix.startswith("//"):
        return cwd            # already UNC — resolve() normalizes it
    if posix.startswith("/"):
        m = _MNT_RE.match(posix)
        if m:
            drive = m.group(1).upper()
            rest = (m.group(2) or "/").lstrip("/")
            return f"{drive}:\\{rest.replace('/', chr(92))}" if rest else f"{drive}:\\"
        return f"\\\\wsl.localhost\\{_WSL_DISTRO}" + posix.replace("/", "\\")
    return cwd


def _git_toplevel(path: Path) -> Path | None:
    """Nearest ancestor (including ``path`` itself) containing a ``.git`` entry.

    Pure filesystem walk — no ``git`` subprocess — so it is cheap and hermetic.
    A ``.git`` *file* (worktree/submodule pointer) counts the same as a dir.
    Returns None when no ancestor is a git root (not every project is a repo).
    """
    for candidate in (path, *path.parents):
        if (candidate / ".git").exists():
            return candidate
    return None


def project_root(cwd: str | None) -> Path | None:
    """The **canonical** project root for an agent — derived from its ``cwd``.

    §8.1: git top-level, with symlink and ``C:\\…``/``/mnt/c/…`` path aliases
    resolved to one canonical form — so a subfolder launch or a path alias still
    lands on the same ``.awl-cc-dash/`` folder. WSL-internal cwds are first-class:
    ``/home/lester/x`` and ``\\\\wsl.localhost\\<distro>\\home\\lester\\x`` are one
    project (both canonicalize to the UNC form — see :func:`_normalize_alias`).
    Code keys off each agent's ``cwd``, never a fixed path, so a project can
    physically move with no rearchitecting. Returns None when the agent has no cwd.
    """
    if not cwd:
        return None
    resolved = Path(_normalize_alias(cwd)).resolve()
    return _git_toplevel(resolved) or resolved


def project_key(cwd: str | None) -> str | None:
    """The canonical root as a string — THE cross-module project key.

    Used wherever a cwd scopes shared state (the scratchpad board, the state
    store cache, link/bookmark grouping), so two spellings of one project can
    never split its state.
    """
    root = project_root(cwd)
    return None if root is None else str(root)


def project_awl_dir(cwd: str | None) -> Path | None:
    """``<project>/.awl-cc-dash/`` (Windows-side Path), or ``None`` when ``cwd`` is absent."""
    root = project_root(cwd)
    if root is None:
        return None
    return root / _AWL_DIRNAME


def ensure_project_awl_dir(cwd: str | None) -> Path:
    """Create ``<project>/.awl-cc-dash/`` (idempotent) and return it.

    Also runs the one-time legacy ``.awl/`` migration (see
    :func:`migrate_legacy_store`) so any pre-rename store is folded in the first
    time the project home is touched.

    Raises ``ValueError`` when the agent has no ``cwd`` (no project home exists).
    """
    awl = project_awl_dir(cwd)
    if awl is None:
        raise ValueError("agent has no cwd; cannot resolve a project home")
    migrate_legacy_store(cwd)
    awl.mkdir(parents=True, exist_ok=True)
    return awl


# --- §8.2 subdir accessors (created as first populated, via the ensure_* forms) ---

def plans_dir(cwd: str | None) -> Path | None:
    """``<project>/.awl-cc-dash/plans/`` — plan .md files + their sidecars."""
    awl = project_awl_dir(cwd)
    return None if awl is None else awl / _PLANS_SUBDIR


def docs_dir(cwd: str | None) -> Path | None:
    """``<project>/.awl-cc-dash/docs/`` — dashboard-owned markdown docs + sidecars."""
    awl = project_awl_dir(cwd)
    return None if awl is None else awl / _DOCS_SUBDIR


def assets_dir(cwd: str | None) -> Path | None:
    """``<project>/.awl-cc-dash/assets/`` — Library → Assets media."""
    awl = project_awl_dir(cwd)
    return None if awl is None else awl / _ASSETS_SUBDIR


def state_dir(cwd: str | None) -> Path | None:
    """``<project>/.awl-cc-dash/state/`` — dashboard-owned JSON state for THIS project."""
    awl = project_awl_dir(cwd)
    return None if awl is None else awl / _STATE_SUBDIR


def _ensure_subdir(cwd: str | None, sub: Path | None) -> Path:
    if sub is None:
        raise ValueError("agent has no cwd; cannot resolve a project home")
    ensure_project_awl_dir(cwd)
    sub.mkdir(parents=True, exist_ok=True)
    return sub


def ensure_plans_dir(cwd: str | None) -> Path:
    return _ensure_subdir(cwd, plans_dir(cwd))


def ensure_docs_dir(cwd: str | None) -> Path:
    return _ensure_subdir(cwd, docs_dir(cwd))


def ensure_assets_dir(cwd: str | None) -> Path:
    return _ensure_subdir(cwd, assets_dir(cwd))


def ensure_state_dir(cwd: str | None) -> Path:
    return _ensure_subdir(cwd, state_dir(cwd))


def scratchpad_path(cwd: str | None) -> Path | None:
    """The team scratchpad ``<project>/.awl-cc-dash/docs/scratchpad.md`` (§7.7)."""
    d = docs_dir(cwd)
    return None if d is None else d / _SCRATCHPAD_NAME


def plan_reviews_path(cwd: str | None) -> Path | None:
    """The LEGACY plan-review side-store ``<project>/.awl-cc-dash/plan-reviews.json``.

    Superseded by per-doc ``.meta.json`` sidecars (§8.5); kept as the migration
    source and until the sidecar layer fully replaces its readers.
    """
    awl = project_awl_dir(cwd)
    return None if awl is None else awl / _PLAN_REVIEWS_NAME


# ---------------------------------------------------------------------------
# One-time legacy migration — `.awl/` → `.awl-cc-dash/` (§11 #1)
# ---------------------------------------------------------------------------

def migrate_legacy_store(cwd: str | None) -> bool:
    """Fold a pre-rename ``<project>/.awl/`` store into ``.awl-cc-dash/``.

    Idempotent and conservative: known files move to their new homes
    (``scratchpad.md`` → ``docs/scratchpad.md``; ``plan-reviews.json`` → the
    store root), anything unrecognized moves to the store root verbatim, and an
    existing target is NEVER overwritten (the legacy file is left in place for a
    human to reconcile). A child that cannot be moved (e.g. locked by another
    process) is skipped with a warning and the rest keep migrating — this
    function never raises into :func:`ensure_project_awl_dir`, so a stuck
    legacy file can never break session create; the skipped child is retried
    on the next touch. The legacy dir is removed only when emptied. Returns
    True when anything was actually moved (honest — skipped children don't count).
    """
    root = project_root(cwd)
    if root is None:
        return False
    legacy = root / _LEGACY_AWL_DIRNAME
    if not legacy.is_dir():
        return False
    new = root / _AWL_DIRNAME
    moved_any = False
    for child in list(legacy.iterdir()):
        if child.name == _SCRATCHPAD_NAME:
            target = new / _DOCS_SUBDIR / _SCRATCHPAD_NAME
        else:
            target = new / child.name
        if target.exists():
            continue  # never overwrite; leave the legacy copy for reconciliation
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            child.rename(target)
        except OSError:
            # A locked/unmovable child must not break the migration (nor the
            # session create above it) — skip it, keep going, retry next touch.
            logger.warning("legacy store migration: could not move %s (skipped)",
                           child, exc_info=True)
            continue
        moved_any = True
    try:
        next(legacy.iterdir())
    except StopIteration:
        try:
            legacy.rmdir()
        except OSError:  # pragma: no cover - removal is best-effort
            pass
    except OSError:  # pragma: no cover - listing is best-effort
        pass
    return moved_any


# ---------------------------------------------------------------------------
# WSL-reachable forms (the agents read the project home from inside WSL2)
# ---------------------------------------------------------------------------

# \\wsl.localhost\<distro>\<path> — the in-WSL form is simply /<path>.
_WSL_UNC_RE = re.compile(r"^[\\/]{2}wsl\.localhost[\\/][^\\/]+([\\/].*)?$",
                         re.IGNORECASE)


def _to_wsl(path: Path | None) -> str | None:
    if path is None:
        return None
    s = str(path)
    # A \\wsl.localhost\<distro>\… root is already INSIDE WSL: strip the UNC
    # prefix to the plain /<path> the agents see (win_to_wsl would pass the
    # UNC through untranslated — never hand agents a /mnt/c/home/… mistake).
    m = _WSL_UNC_RE.match(s)
    if m:
        return (m.group(1) or "/").replace("\\", "/")
    # win_to_wsl wants forward slashes / a drive-letter path; str(Path) on
    # Windows yields backslashes, which the translator normalizes.
    return win_to_wsl(s)


def project_awl_dir_wsl(cwd: str | None) -> str | None:
    """``<project>/.awl-cc-dash/`` as a WSL-reachable ``/mnt/...`` path (or ``None``)."""
    return _to_wsl(project_awl_dir(cwd))


def plans_dir_wsl(cwd: str | None) -> str | None:
    """The plans dir, WSL-reachable — the value ``plansDirectory`` is set to (§8.5)."""
    return _to_wsl(plans_dir(cwd))


def scratchpad_path_wsl(cwd: str | None) -> str | None:
    """The scratchpad path, WSL-reachable so the agents can read/append it."""
    return _to_wsl(scratchpad_path(cwd))


def plan_reviews_path_wsl(cwd: str | None) -> str | None:
    """The legacy plan-reviews side-store path, WSL-reachable."""
    return _to_wsl(plan_reviews_path(cwd))
