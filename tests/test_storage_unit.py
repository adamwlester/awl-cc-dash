"""Hermetic unit tests for the storage & scoping homes (ARCHITECTURE §8.1/§8.2).

Pure path logic — no driver, no WSL2/tmux, no live agent. The decided contract:

  * Dashboard runtime store — ``sidecar/runtime/`` (override ``AWL_SIDECAR_RUNTIME``):
    reusable, project-agnostic — Setups, templates, and the projects index.
  * Project home — ``<project>/.awl-cc-dash/`` where ``<project>`` is the
    **canonical repo root** derived from the agent's ``cwd``: git top-level,
    with symlink and ``C:\\…``/``/mnt/c/…`` aliases resolved to ONE form, so a
    subfolder launch or a path alias still lands on the same store.
  * §8.2 subdir taxonomy: ``plans/`` · ``docs/`` (scratchpad = ``docs/scratchpad.md``)
    · ``assets/`` · ``state/`` — created as first populated, never scaffolded.
  * One-time legacy migration: a pre-rename ``<project>/.awl/`` store folds into
    ``.awl-cc-dash/`` on first touch; existing targets are never overwritten.

These carry neither the ``integration`` nor the ``slow`` mark.
"""

import sys
from pathlib import Path

import pytest

# The sidecar runs with its own dir on sys.path (not the repo root).
_SIDECAR = Path(__file__).resolve().parent.parent / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))

import storage  # noqa: E402


# ---------------------------------------------------------------------------
# Canonical project root (§8.1 "<project> defined")
# ---------------------------------------------------------------------------

class TestCanonicalRoot:
    def test_plain_dir_is_its_own_root(self, tmp_path):
        proj = tmp_path / "myproj"
        proj.mkdir()
        assert storage.project_root(str(proj)) == proj.resolve()

    def test_subfolder_launch_lands_on_git_toplevel(self, tmp_path):
        repo = tmp_path / "repo"
        (repo / ".git").mkdir(parents=True)
        sub = repo / "packages" / "web"
        sub.mkdir(parents=True)
        # An agent launched in a subfolder still resolves the REPO root.
        assert storage.project_root(str(sub)) == repo.resolve()
        assert storage.project_awl_dir(str(sub)) == repo.resolve() / ".awl-cc-dash"

    def test_git_file_counts_as_toplevel_marker(self, tmp_path):
        # A .git FILE (worktree/submodule pointer) marks the root the same way.
        repo = tmp_path / "wt"
        repo.mkdir()
        (repo / ".git").write_text("gitdir: elsewhere", encoding="utf-8")
        sub = repo / "src"
        sub.mkdir()
        assert storage.project_root(str(sub)) == repo.resolve()

    def test_mnt_alias_folds_to_windows_spelling(self):
        # /mnt/c/… and C:\… are the SAME project — one canonical key.
        a = storage.project_key("/mnt/c/Users/lester/proj")
        b = storage.project_key(r"C:\Users\lester\proj")
        assert a == b

    def test_wsl_internal_posix_and_unc_spellings_share_one_key(self):
        # /home/… (a true WSL-internal cwd) and its \\wsl.localhost UNC
        # spelling are the SAME project — one canonical key.
        a = storage.project_key("/home/awl-test-user/proj")
        b = storage.project_key(r"\\wsl.localhost\Ubuntu\home\awl-test-user\proj")
        assert a == b

    def test_wsl_internal_root_never_anchors_to_a_windows_drive(self):
        # The old behavior resolved /home/… against the Windows current drive
        # (C:\home\…), corrupting the key. It must map to the UNC form.
        key = storage.project_key("/home/awl-test-user/proj")
        assert key.lower().startswith("\\\\wsl.localhost\\")
        assert ":" not in key    # no drive letter crept in

    def test_project_key_matches_root(self, tmp_path):
        proj = tmp_path / "p"
        proj.mkdir()
        assert storage.project_key(str(proj)) == str(storage.project_root(str(proj)))

    def test_none_cwd_has_no_root(self):
        assert storage.project_root(None) is None
        assert storage.project_key(None) is None


# ---------------------------------------------------------------------------
# Project home — <project>/.awl-cc-dash/ + the §8.2 subdir taxonomy
# ---------------------------------------------------------------------------

class TestProjectHome:
    def test_awl_dir_is_dot_awl_cc_dash_under_root(self, tmp_path):
        proj = tmp_path / "myproj"
        proj.mkdir()
        assert storage.project_awl_dir(str(proj)) == proj.resolve() / ".awl-cc-dash"

    def test_awl_dir_keys_off_cwd_not_a_fixed_path(self, tmp_path):
        a = tmp_path / "projA"
        b = tmp_path / "projB"
        a.mkdir(); b.mkdir()
        assert storage.project_awl_dir(str(a)) != storage.project_awl_dir(str(b))
        assert storage.project_awl_dir(str(a)).parent == a.resolve()

    def test_none_cwd_has_no_project_home(self):
        assert storage.project_awl_dir(None) is None
        assert storage.scratchpad_path(None) is None
        assert storage.plan_reviews_path(None) is None
        assert storage.state_dir(None) is None

    def test_ensure_creates_the_awl_dir(self, tmp_path):
        proj = tmp_path / "fresh"
        proj.mkdir()
        awl = storage.ensure_project_awl_dir(str(proj))
        assert awl == proj.resolve() / ".awl-cc-dash"
        assert awl.is_dir()

    def test_ensure_is_idempotent(self, tmp_path):
        proj = tmp_path / "fresh"
        proj.mkdir()
        first = storage.ensure_project_awl_dir(str(proj))
        second = storage.ensure_project_awl_dir(str(proj))  # no error second time
        assert first == second and second.is_dir()

    def test_ensure_raises_without_cwd(self):
        with pytest.raises(ValueError):
            storage.ensure_project_awl_dir(None)

    def test_subdir_taxonomy(self, tmp_path):
        proj = tmp_path / "p"
        proj.mkdir()
        awl = proj.resolve() / ".awl-cc-dash"
        assert storage.plans_dir(str(proj)) == awl / "plans"
        assert storage.docs_dir(str(proj)) == awl / "docs"
        assert storage.assets_dir(str(proj)) == awl / "assets"
        assert storage.state_dir(str(proj)) == awl / "state"
        # The scratchpad is a docs/ file; plan-reviews is the LEGACY root file.
        assert storage.scratchpad_path(str(proj)) == awl / "docs" / "scratchpad.md"
        assert storage.plan_reviews_path(str(proj)) == awl / "plan-reviews.json"

    def test_no_empty_scaffolding(self, tmp_path):
        # Accessors never create dirs; ensure_* creates ONLY the asked-for subdir.
        proj = tmp_path / "p"
        proj.mkdir()
        storage.plans_dir(str(proj))
        assert not (proj / ".awl-cc-dash").exists()
        state = storage.ensure_state_dir(str(proj))
        assert state.is_dir()
        assert not (proj / ".awl-cc-dash" / "plans").exists()
        assert not (proj / ".awl-cc-dash" / "docs").exists()


# ---------------------------------------------------------------------------
# Legacy `.awl/` migration (one-time, on touch)
# ---------------------------------------------------------------------------

class TestLegacyMigration:
    def test_known_files_move_to_new_homes(self, tmp_path):
        proj = tmp_path / "p"
        legacy = proj / ".awl"
        legacy.mkdir(parents=True)
        (legacy / "scratchpad.md").write_text("# board\n- a post\n", encoding="utf-8")
        (legacy / "plan-reviews.json").write_text("{}", encoding="utf-8")
        assert storage.migrate_legacy_store(str(proj)) is True
        awl = proj / ".awl-cc-dash"
        assert (awl / "docs" / "scratchpad.md").read_text(encoding="utf-8").startswith("# board")
        assert (awl / "plan-reviews.json").is_file()
        assert not legacy.exists()  # emptied → removed

    def test_never_overwrites_an_existing_target(self, tmp_path):
        proj = tmp_path / "p"
        legacy = proj / ".awl"
        legacy.mkdir(parents=True)
        (legacy / "plan-reviews.json").write_text('{"old": 1}', encoding="utf-8")
        new = proj / ".awl-cc-dash"
        new.mkdir()
        (new / "plan-reviews.json").write_text('{"new": 2}', encoding="utf-8")
        storage.migrate_legacy_store(str(proj))
        # Target kept; legacy copy left in place for human reconciliation.
        assert '"new"' in (new / "plan-reviews.json").read_text(encoding="utf-8")
        assert (legacy / "plan-reviews.json").is_file()

    def test_idempotent_and_noop_without_legacy(self, tmp_path):
        proj = tmp_path / "p"
        proj.mkdir()
        assert storage.migrate_legacy_store(str(proj)) is False
        assert storage.migrate_legacy_store(None) is False

    def test_ensure_runs_the_migration(self, tmp_path):
        proj = tmp_path / "p"
        legacy = proj / ".awl"
        legacy.mkdir(parents=True)
        (legacy / "scratchpad.md").write_text("x", encoding="utf-8")
        storage.ensure_project_awl_dir(str(proj))
        assert (proj / ".awl-cc-dash" / "docs" / "scratchpad.md").is_file()
        assert not legacy.exists()


# ---------------------------------------------------------------------------
# WSL-reachability — the agents read the project home from inside WSL2
# ---------------------------------------------------------------------------

class TestWslReachable:
    def test_windows_cwd_maps_to_mnt(self):
        wsl = storage.project_awl_dir_wsl("C:/Users/lester/proj")
        assert wsl == "/mnt/c/Users/lester/proj/.awl-cc-dash"

    def test_backslash_cwd_normalized(self):
        wsl = storage.project_awl_dir_wsl(r"C:\Users\lester\proj")
        assert wsl == "/mnt/c/Users/lester/proj/.awl-cc-dash"

    def test_scratchpad_wsl_path(self):
        wsl = storage.scratchpad_path_wsl("C:/Users/lester/proj")
        assert wsl == "/mnt/c/Users/lester/proj/.awl-cc-dash/docs/scratchpad.md"

    def test_plans_dir_wsl_is_the_plansdirectory_value(self):
        # §8.5: plansDirectory = the ABSOLUTE WSL path of the project's plans/.
        wsl = storage.plans_dir_wsl("C:/Users/lester/proj")
        assert wsl == "/mnt/c/Users/lester/proj/.awl-cc-dash/plans"

    def test_wsl_internal_root_yields_home_rooted_wsl_paths(self):
        # A WSL-internal project's WSL-reachable accessors are /home/…-rooted —
        # NEVER a /mnt/c/home/… mistranslation of a corrupted drive anchor.
        wsl = storage.plans_dir_wsl("/home/awl-test-user/proj")
        assert wsl == "/home/awl-test-user/proj/.awl-cc-dash/plans"

    def test_wsl_unc_root_translates_back_inside_wsl(self):
        wsl = storage.scratchpad_path_wsl(
            r"\\wsl.localhost\Ubuntu\home\awl-test-user\proj")
        assert wsl == "/home/awl-test-user/proj/.awl-cc-dash/docs/scratchpad.md"

    def test_none_cwd_has_no_wsl_path(self):
        assert storage.project_awl_dir_wsl(None) is None
        assert storage.scratchpad_path_wsl(None) is None
        assert storage.plans_dir_wsl(None) is None


# ---------------------------------------------------------------------------
# Dashboard runtime store — reusable, project-agnostic
# ---------------------------------------------------------------------------

class TestDashboardStore:
    def test_runtime_dir_honors_override(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(tmp_path / "rt"))
        assert storage.dashboard_runtime_dir() == tmp_path / "rt"

    def test_reusables_live_in_the_dashboard_store(self, tmp_path, monkeypatch):
        rt = tmp_path / "rt"
        monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(rt))
        # Reusable, project-agnostic — NOT under any <project>/.awl-cc-dash.
        assert storage.setups_path() == rt / "setups.json"
        assert storage.templates_path() == rt / "templates.json"
        assert storage.projects_index_path() == rt / "projects.json"

    def test_runtime_dir_matches_runtime_store(self, tmp_path, monkeypatch):
        import runtime_store
        monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(tmp_path / "rt"))
        assert storage.dashboard_runtime_dir() == runtime_store.runtime_dir()
