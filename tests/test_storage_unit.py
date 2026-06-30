"""Hermetic unit tests for the storage & scoping homes (OD-23).

Pure path logic — no driver, no WSL2/tmux, no live agent. Proves the three
storage homes resolve correctly off each agent's ``cwd``:

  * Dashboard runtime store  — ``sidecar/runtime/`` (override ``AWL_SIDECAR_RUNTIME``):
    reusable, project-agnostic — Setups + templates live here.
  * Project home             — ``<project>/.awl/`` keyed off the agent's ``cwd``,
    WSL-reachable so the agents can read it (scratchpad + plan-reviews).
  * Setup                    — a roster in the dashboard store (not a folder).

These carry neither the ``integration`` nor the ``slow`` mark.
"""

import sys
from pathlib import Path

# The sidecar runs with its own dir on sys.path (not the repo root).
_SIDECAR = Path(__file__).resolve().parent.parent / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))

import storage  # noqa: E402


# ---------------------------------------------------------------------------
# Project home — <project>/.awl/, keyed off the agent's cwd
# ---------------------------------------------------------------------------

class TestProjectHome:
    def test_awl_dir_is_dot_awl_under_cwd(self, tmp_path):
        proj = tmp_path / "myproj"
        proj.mkdir()
        assert storage.project_awl_dir(str(proj)) == proj / ".awl"

    def test_awl_dir_keys_off_cwd_not_a_fixed_path(self, tmp_path):
        a = tmp_path / "projA"
        b = tmp_path / "projB"
        a.mkdir(); b.mkdir()
        # Two different cwds -> two different project homes (never a shared dir).
        assert storage.project_awl_dir(str(a)) != storage.project_awl_dir(str(b))
        assert storage.project_awl_dir(str(a)).parent == a

    def test_none_cwd_has_no_project_home(self):
        assert storage.project_awl_dir(None) is None
        assert storage.scratchpad_path(None) is None
        assert storage.plan_reviews_path(None) is None

    def test_ensure_creates_the_awl_dir(self, tmp_path):
        proj = tmp_path / "fresh"
        proj.mkdir()
        awl = storage.ensure_project_awl_dir(str(proj))
        assert awl == proj / ".awl"
        assert awl.is_dir()

    def test_ensure_is_idempotent(self, tmp_path):
        proj = tmp_path / "fresh"
        proj.mkdir()
        first = storage.ensure_project_awl_dir(str(proj))
        second = storage.ensure_project_awl_dir(str(proj))  # no error second time
        assert first == second and second.is_dir()

    def test_ensure_raises_without_cwd(self):
        import pytest
        with pytest.raises(ValueError):
            storage.ensure_project_awl_dir(None)

    def test_named_project_files(self, tmp_path):
        proj = tmp_path / "p"
        proj.mkdir()
        awl = proj / ".awl"
        # OD-17 scratchpad + OD-15 plan-review side-store live in the project home.
        assert storage.scratchpad_path(str(proj)) == awl / "scratchpad.md"
        assert storage.plan_reviews_path(str(proj)) == awl / "plan-reviews.json"


# ---------------------------------------------------------------------------
# WSL-reachability — the agents read the project home from inside WSL2
# ---------------------------------------------------------------------------

class TestWslReachable:
    def test_windows_cwd_maps_to_mnt(self):
        # A Windows project path -> a /mnt/<drive>/... path the WSL agent can read.
        wsl = storage.project_awl_dir_wsl("C:/Users/lester/proj")
        assert wsl == "/mnt/c/Users/lester/proj/.awl"

    def test_backslash_cwd_normalized(self):
        wsl = storage.project_awl_dir_wsl(r"C:\Users\lester\proj")
        assert wsl == "/mnt/c/Users/lester/proj/.awl"

    def test_scratchpad_wsl_path(self):
        wsl = storage.scratchpad_path_wsl("C:/Users/lester/proj")
        assert wsl == "/mnt/c/Users/lester/proj/.awl/scratchpad.md"

    def test_none_cwd_has_no_wsl_path(self):
        assert storage.project_awl_dir_wsl(None) is None
        assert storage.scratchpad_path_wsl(None) is None


# ---------------------------------------------------------------------------
# Dashboard runtime store — reusable, project-agnostic (Setups + templates)
# ---------------------------------------------------------------------------

class TestDashboardStore:
    def test_runtime_dir_honors_override(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(tmp_path / "rt"))
        assert storage.dashboard_runtime_dir() == tmp_path / "rt"

    def test_setups_and_templates_live_in_the_dashboard_store(self, tmp_path, monkeypatch):
        rt = tmp_path / "rt"
        monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(rt))
        # Reusable, project-agnostic tool-level data — NOT under any <project>/.awl.
        assert storage.setups_path() == rt / "setups.json"
        assert storage.templates_path() == rt / "templates.json"

    def test_runtime_dir_matches_runtime_store(self, tmp_path, monkeypatch):
        # Single source of truth: storage's dashboard home is exactly the dir
        # runtime_store persists sessions.json into (no divergent location).
        import runtime_store
        monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(tmp_path / "rt"))
        assert storage.dashboard_runtime_dir() == runtime_store.runtime_dir()
