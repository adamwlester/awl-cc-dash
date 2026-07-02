"""Storage & scoping homes — the one canonical model for *where data lives*.

One rule: **dashboard data lives with the dashboard; project data lives with the
project; teams (Setups) are reusable and live with the dashboard.** Three homes,
all keyed off each agent's ``cwd`` (never a fixed path), so the physical location
is free to change with no rearchitecting:

  🏠 **Dashboard** — ``sidecar/runtime/`` (override ``AWL_SIDECAR_RUNTIME``):
      the app's memory — per-agent identity, which sessions exist, saved
      **Setups** (rosters), and reusable **templates**. Reusable, project-agnostic.
      (Canonical accessor: :func:`dashboard_runtime_dir`, == ``runtime_store.runtime_dir``.)

  📁 **Project** — ``<project>/.awl/`` where ``<project>`` = the agent's ``cwd``:
      dashboard-owned *project* data that must travel with the repo and be
      WSL-reachable so the agents can read it — the team **scratchpad**
      and the **plan-review side-store**. Nothing project-specific leaks
      up into the dashboard store.

  👥 **Setup** — a reusable team (roster only: agents, roles/models/identities,
      links). A dashboard concept saved in the dashboard store, *not* a folder.

Claude Code's own config (``~/.claude``, ``<project>/.claude``) is **surfaced,
not owned** — the dashboard reads/edits it in place; it does not store it here.

**Tie-breaker for fuzzy cases:** is this about the *project*, or the *team/tool*?
Project → ``<project>/.awl/``; team/tool → the dashboard store.

The project home is WSL-reachable via the proven Windows↔WSL2 translation
(``bridge.paths.win_to_wsl`` — the same mechanism ``mcp_sync`` uses); we reuse it
rather than re-solving path normalization per feature.
"""

from __future__ import annotations

import sys
from pathlib import Path

import runtime_store

# Reuse the proven WSL2↔Windows path translation from the bridge package. The
# sidecar runs with its own dir on sys.path (not the repo root), so add the repo
# root the way the bridge driver does, then import the shared utility. A local
# fallback keeps this module importable even if the bridge package is absent
# (e.g. a stripped test env) — it must never be the reason storage can't load.
_REPO_ROOT = str(Path(__file__).resolve().parents[1])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

try:
    from bridge.paths import win_to_wsl  # type: ignore[import-not-found]
except Exception:  # pragma: no cover - exercised only when bridge is unavailable
    import re

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


# Project-home directory + the files that live in it.
_AWL_DIRNAME = ".awl"
_SCRATCHPAD_NAME = "scratchpad.md"   # shared team scratchpad
_PLAN_REVIEWS_NAME = "plan-reviews.json"  # Library plans review side-store

# Dashboard-store files (project-agnostic, reusable).
_SETUPS_NAME = "setups.json"      # saved Setups (rosters)
_TEMPLATES_NAME = "templates.json"  # reusable prompt templates


# ---------------------------------------------------------------------------
# 🏠 Dashboard store (reusable, project-agnostic)
# ---------------------------------------------------------------------------

def dashboard_runtime_dir() -> Path:
    """The 🏠 Dashboard home — exactly ``runtime_store.runtime_dir()``.

    Single source of truth: identity, sessions, Setups, and templates all sit
    here, never under a project's ``.awl/``.
    """
    return runtime_store.runtime_dir()


def setups_path() -> Path:
    """Saved Setups (rosters) — a dashboard-store file."""
    return dashboard_runtime_dir() / _SETUPS_NAME


def templates_path() -> Path:
    """Saved prompt templates — a dashboard-store file.

    Tool-level reusable data (like Setups). *Project-specific* templates may
    later live in ``<project>/.awl/``; the reusable set lives here.
    """
    return dashboard_runtime_dir() / _TEMPLATES_NAME


# ---------------------------------------------------------------------------
# 📁 Project home (<project>/.awl/, keyed off the agent's cwd)
# ---------------------------------------------------------------------------

def project_root(cwd: str | None) -> Path | None:
    """The project root for an agent — its ``cwd``, or ``None`` if it has none.

    Code keys off ``cwd``, never a fixed path: the dashboard treats whatever the
    agent's ``cwd`` is as the project home regardless of where it physically sits.
    """
    if not cwd:
        return None
    return Path(cwd)


def project_awl_dir(cwd: str | None) -> Path | None:
    """``<project>/.awl/`` (Windows-side Path), or ``None`` when ``cwd`` is absent."""
    root = project_root(cwd)
    if root is None:
        return None
    return root / _AWL_DIRNAME


def ensure_project_awl_dir(cwd: str | None) -> Path:
    """Create ``<project>/.awl/`` (idempotent) and return it.

    Raises ``ValueError`` when the agent has no ``cwd`` (no project home exists).
    """
    awl = project_awl_dir(cwd)
    if awl is None:
        raise ValueError("agent has no cwd; cannot resolve a project home")
    awl.mkdir(parents=True, exist_ok=True)
    return awl


def scratchpad_path(cwd: str | None) -> Path | None:
    """The team scratchpad ``<project>/.awl/scratchpad.md``."""
    awl = project_awl_dir(cwd)
    return None if awl is None else awl / _SCRATCHPAD_NAME


def plan_reviews_path(cwd: str | None) -> Path | None:
    """The plans review side-store ``<project>/.awl/plan-reviews.json``."""
    awl = project_awl_dir(cwd)
    return None if awl is None else awl / _PLAN_REVIEWS_NAME


# ---------------------------------------------------------------------------
# WSL-reachable forms (the agents read the project home from inside WSL2)
# ---------------------------------------------------------------------------

def _to_wsl(path: Path | None) -> str | None:
    if path is None:
        return None
    # win_to_wsl wants forward slashes / a drive-letter path; str(Path) on
    # Windows yields backslashes, which the translator normalizes.
    return win_to_wsl(str(path))


def project_awl_dir_wsl(cwd: str | None) -> str | None:
    """``<project>/.awl/`` as a WSL-reachable ``/mnt/...`` path (or ``None``)."""
    return _to_wsl(project_awl_dir(cwd))


def scratchpad_path_wsl(cwd: str | None) -> str | None:
    """The scratchpad path, WSL-reachable so the agents can read/append it."""
    return _to_wsl(scratchpad_path(cwd))


def plan_reviews_path_wsl(cwd: str | None) -> str | None:
    """The plan-reviews side-store path, WSL-reachable."""
    return _to_wsl(plan_reviews_path(cwd))
