"""Hermetic unit tests for per-agent doc attachment at launch (§7.16, §11 #44).

Decided contract (ARCHITECTURE §7.16, §10 #6, §11 #44; build plan
``dev/notes/2026-07-15-stage5-build-plan.md`` "## #44"):

The Library is the curated docs hub; the "light" v1 mechanism is **per-agent doc
attachment at launch**: ``attached_docs`` (a list of Library doc paths /
identifiers) rides ``CreateSessionRequest`` → ``SessionState`` → ``DriverConfig``
→ the persisted roster record (``state/agents.json`` carries per-agent launch
config), and at bridge launch the driver injects a SHORT system-prompt preamble
listing the attached docs as WSL-reachable absolute paths with one line telling
the agent to consult them. The preamble is COMPOSED with the §11 #39
response-preset instruction when both are present (joined by a blank line —
neither clobbers the other). Automatic relevance retrieval is explicitly OUT of
scope (§10 #6 stays parked).

What this file pins (all pure Python — no WSL/tmux/network):
  * ``storage.doc_path_wsl`` — the general WSL translation for a resolved doc
    path (drive-letter → ``/mnt/<d>/…``; a ``\\\\wsl.localhost`` UNC strips to the
    in-WSL ``/…`` form; ``None`` passes through), consistent with the store's
    fixed ``*_wsl`` helpers.
  * ``library.resolve_attached_doc`` — a bare filename resolves like
    ``resolve_document`` (store ``plans/`` → store ``docs/`` → project root); a
    path reference (absolute, or relative to the project root) resolves to an
    existing ``.md`` file; anything unresolvable (missing file, non-``.md``,
    empty, bad name, no cwd) is ``None`` — best-effort, never raising, so a doc
    deleted since selection can never fail a launch. Never-raising includes an
    embedded NUL in a PATH ref (Windows raises ValueError, not OSError), and
    path spellings are tolerant: rooted-driveless (``/docs/x.md``) reads
    project-root-relative, and the WSL-side ``/mnt/<drive>/…`` form — the exact
    spelling the preamble itself emits — folds to the same file as its Windows
    spelling, so preamble paths round-trip.
  * ``library.attached_docs_wsl`` — order-preserving WSL-absolute paths,
    duplicates collapsed, unresolvable refs skipped.
  * ``library.attached_docs_preamble`` — the lead consult-these-docs line +
    one ``- <wsl path>`` bullet per resolved doc; ``""`` when nothing resolves
    (no docs → no preamble).
  * ``BridgeDriver._create_session()`` — the preamble materializes into the
    launch's ``append_system_prompt``: docs only → the preamble; preset only →
    exactly the preset instruction (unchanged #39 behavior); BOTH → preamble +
    blank line + preset instruction, both intact; neither (or nothing
    resolving) → ``None``. Scripted-fake captured, never executed.
  * ``BridgeDriver.start()`` (create path) — ``attached_docs`` persists into
    the roster record next to ``response_preset``.
  * ``BridgeDriver.fork()`` — the ``--fork-session`` spawn carries the
    DOCS-ONLY preamble as ``append_system_prompt`` (adoption is a warm rebind,
    so the fork's inherited ``attached_docs`` must be real at its own launch —
    never record-only; the #39 preset is deliberately NOT inherited at fork).
  * The sidecar carry — ``CreateSessionRequest.attached_docs`` (default None)
    flows through ``POST /sessions`` into the ``SessionState`` and surfaces in
    ``to_dict()["launch_config"]``; the roster/archive resume descriptors carry
    the field (roster lifts it, the LIGHT archive record resumes it as None).
  * The SessionState → DriverConfig carry at EVERY construction site in
    ``main`` — ``start_session`` (the primary create path), the
    ``reconnect_sessions`` cold restore, ``_resume_agent_from_descriptor``
    (#17), and ``_adopt_forked_session`` (#15) — so reverting any one
    ``attached_docs=…`` carry line fails a test here.

These carry neither the ``integration`` nor the ``slow`` mark.
"""

import asyncio
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_SIDECAR = _REPO / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

import library  # noqa: E402
import response_presets  # noqa: E402
import storage  # noqa: E402
from drivers.base import DriverConfig  # noqa: E402
from drivers.bridge import BridgeDriver  # noqa: E402


def _project(tmp_path: Path, name: str = "proj") -> str:
    """A tmp project dir with a .git marker so storage.project_root pins to it."""
    cwd = tmp_path / name
    (cwd / ".git").mkdir(parents=True)
    return str(cwd)


def _store_doc(cwd: str, filename: str, subdir: str = "docs",
               content: str = "# doc") -> Path:
    base = (storage.ensure_docs_dir(cwd) if subdir == "docs"
            else storage.ensure_plans_dir(cwd))
    p = base / filename
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# storage.doc_path_wsl — the general WSL form for a dynamically-resolved doc
# ---------------------------------------------------------------------------

class TestDocPathWsl:
    def test_drive_letter_path_translates_to_mnt(self):
        assert storage.doc_path_wsl("C:\\proj\\docs\\a.md") == "/mnt/c/proj/docs/a.md"

    def test_wsl_unc_path_strips_to_in_wsl_form(self):
        assert storage.doc_path_wsl(
            "\\\\wsl.localhost\\Ubuntu\\home\\u\\x.md") == "/home/u/x.md"

    def test_none_passes_through(self):
        assert storage.doc_path_wsl(None) is None


# ---------------------------------------------------------------------------
# library.resolve_attached_doc — one reference -> an existing .md path (or None)
# ---------------------------------------------------------------------------

class TestResolveAttachedDoc:
    def test_bare_filename_resolves_from_store_docs(self, tmp_path):
        cwd = _project(tmp_path)
        p = _store_doc(cwd, "guide.md")
        assert library.resolve_attached_doc(cwd, "guide.md") == p

    def test_bare_filename_prefers_plans_over_docs(self, tmp_path):
        # Same search order as resolve_document: plans/ -> docs/ -> root.
        cwd = _project(tmp_path)
        _store_doc(cwd, "same.md", subdir="docs")
        plan = _store_doc(cwd, "same.md", subdir="plans")
        assert library.resolve_attached_doc(cwd, "same.md") == plan

    def test_bare_filename_falls_back_to_project_root(self, tmp_path):
        cwd = _project(tmp_path)
        rootdoc = Path(cwd) / "README.md"
        rootdoc.write_text("# root", encoding="utf-8")
        assert library.resolve_attached_doc(cwd, "README.md") == rootdoc

    def test_absolute_path_reference_resolves(self, tmp_path):
        cwd = _project(tmp_path)
        p = _store_doc(cwd, "api.md")
        assert library.resolve_attached_doc(cwd, str(p)) == p.resolve()

    def test_relative_path_reference_resolves_against_project_root(self, tmp_path):
        cwd = _project(tmp_path)
        nested = Path(cwd) / "notes"
        nested.mkdir()
        doc = nested / "howto.md"
        doc.write_text("# nested", encoding="utf-8")
        assert library.resolve_attached_doc(cwd, "notes/howto.md") == doc.resolve()

    def test_unresolvable_references_are_none_never_raise(self, tmp_path):
        cwd = _project(tmp_path)
        assert library.resolve_attached_doc(cwd, "missing.md") is None      # absent bare name
        assert library.resolve_attached_doc(cwd, "notes/gone.md") is None   # absent path
        assert library.resolve_attached_doc(cwd, "") is None                # empty
        assert library.resolve_attached_doc(cwd, "  ") is None              # whitespace
        # A bad bare name (resolve_document's ValueError) degrades to None.
        assert library.resolve_attached_doc(cwd, "notes.txt") is None
        # No cwd -> nothing to resolve against.
        assert library.resolve_attached_doc(None, "guide.md") is None

    def test_non_md_path_does_not_resolve(self, tmp_path):
        # The Library's collections are markdown-only; a non-.md path is not a doc.
        cwd = _project(tmp_path)
        txt = Path(cwd) / "data.txt"
        txt.write_text("plain", encoding="utf-8")
        assert library.resolve_attached_doc(cwd, str(txt)) is None

    def test_embedded_nul_in_path_ref_degrades_to_none(self, tmp_path):
        # On Windows a NUL in a path raises ValueError (not OSError) from
        # Path.resolve() — it must degrade to None / no preamble, NEVER escape
        # into (and fail) the launch (best-effort contract).
        cwd = _project(tmp_path)
        assert library.resolve_attached_doc(cwd, "docs/gui\x00de.md") is None
        assert library.attached_docs_preamble(cwd, ["docs/gui\x00de.md"]) == ""

    def test_rooted_driveless_ref_resolves_project_root_relative(self, tmp_path):
        # `/README.md` (rooted but driveless — Windows is_absolute() is False)
        # reads project-root-relative, never drive-anchored (C:\README.md).
        cwd = _project(tmp_path)
        rootdoc = Path(cwd) / "README.md"
        rootdoc.write_text("# root", encoding="utf-8")
        assert library.resolve_attached_doc(cwd, "/README.md") == rootdoc.resolve()
        nested = Path(cwd) / "docs"
        nested.mkdir()
        doc = nested / "guide.md"
        doc.write_text("# g", encoding="utf-8")
        assert library.resolve_attached_doc(cwd, "/docs/guide.md") == doc.resolve()

    def test_wsl_mnt_spelling_round_trips(self, tmp_path):
        # The preamble emits /mnt/<drive>/… paths; re-attaching that EXACT
        # spelling must land on the same file (the storage layer's alias fold,
        # the same folding project cwds get).
        cwd = _project(tmp_path)
        p = _store_doc(cwd, "guide.md")
        wsl = storage.doc_path_wsl(p)
        assert wsl.startswith("/mnt/")
        assert library.resolve_attached_doc(cwd, wsl) == p.resolve()
        # And the full helper round-trips: attaching what attached_docs_wsl
        # emitted yields the same WSL path again.
        assert library.attached_docs_wsl(cwd, [wsl]) == [wsl]


# ---------------------------------------------------------------------------
# library.attached_docs_wsl — WSL-absolute list (ordered, dedup, best-effort)
# ---------------------------------------------------------------------------

class TestAttachedDocsWsl:
    def test_resolves_to_wsl_absolute_paths_in_order(self, tmp_path):
        cwd = _project(tmp_path)
        a = _store_doc(cwd, "a.md")
        b = _store_doc(cwd, "b.md", subdir="plans")
        out = library.attached_docs_wsl(cwd, ["a.md", "b.md"])
        assert out == [storage.doc_path_wsl(a), storage.doc_path_wsl(b)]
        for w in out:
            assert w.startswith("/") and "\\" not in w  # WSL-reachable absolute

    def test_unresolvable_refs_are_skipped(self, tmp_path):
        cwd = _project(tmp_path)
        a = _store_doc(cwd, "a.md")
        out = library.attached_docs_wsl(cwd, ["ghost.md", "a.md"])
        assert out == [storage.doc_path_wsl(a)]

    def test_duplicate_spellings_collapse_to_first(self, tmp_path):
        cwd = _project(tmp_path)
        a = _store_doc(cwd, "a.md")
        # Bare filename + absolute path address the SAME file -> one entry.
        out = library.attached_docs_wsl(cwd, ["a.md", str(a)])
        assert out == [storage.doc_path_wsl(a)]

    def test_none_and_empty_refs_are_empty(self, tmp_path):
        cwd = _project(tmp_path)
        assert library.attached_docs_wsl(cwd, None) == []
        assert library.attached_docs_wsl(cwd, []) == []


# ---------------------------------------------------------------------------
# library.attached_docs_preamble — the short consult-these-docs launch preamble
# ---------------------------------------------------------------------------

class TestAttachedDocsPreamble:
    def test_preamble_lists_docs_under_the_lead_line(self, tmp_path):
        cwd = _project(tmp_path)
        a = _store_doc(cwd, "a.md")
        b = _store_doc(cwd, "b.md")
        text = library.attached_docs_preamble(cwd, ["a.md", "b.md"])
        lines = text.split("\n")
        assert lines[0] == library.ATTACHED_DOCS_LEAD
        assert lines[1] == f"- {storage.doc_path_wsl(a)}"
        assert lines[2] == f"- {storage.doc_path_wsl(b)}"
        assert len(lines) == 3

    def test_no_docs_means_no_preamble(self, tmp_path):
        cwd = _project(tmp_path)
        assert library.attached_docs_preamble(cwd, None) == ""
        assert library.attached_docs_preamble(cwd, []) == ""
        # Nothing RESOLVING is the same as nothing attached.
        assert library.attached_docs_preamble(cwd, ["ghost.md"]) == ""


# ---------------------------------------------------------------------------
# BridgeDriver._create_session() — the preamble materializes into the launch,
# composed with the #39 preset instruction. Hermetic: the TmuxBridge.create
# call is monkeypatch-captured, never executed (mirrors
# test_response_presets_unit.TestCreateSessionForwardsPreset).
# ---------------------------------------------------------------------------

def _driver(**cfg):
    return BridgeDriver(DriverConfig(**cfg), lambda e: None)


def _capture_create(d, monkeypatch):
    seen = {}

    def fake_create(name, **kw):
        seen["name"] = name
        seen.update(kw)
        return {"session_id": "deadbeef"}

    monkeypatch.setattr(d._bridge, "create", fake_create)
    return seen


class TestCreateSessionComposesPreamble:
    def test_docs_only_appends_the_preamble(self, tmp_path, monkeypatch):
        cwd = _project(tmp_path)
        _store_doc(cwd, "a.md")
        d = _driver(cwd=cwd, attached_docs=["a.md"])
        seen = _capture_create(d, monkeypatch)
        d._create_session()
        expected = library.attached_docs_preamble(cwd, ["a.md"])
        assert expected  # sanity: the doc resolved
        assert seen["append_system_prompt"] == expected
        assert seen["append_system_prompt"].startswith(library.ATTACHED_DOCS_LEAD)

    def test_docs_compose_with_preset_joined_by_blank_line(self, tmp_path, monkeypatch):
        cwd = _project(tmp_path)
        _store_doc(cwd, "a.md")
        d = _driver(cwd=cwd, attached_docs=["a.md"], response_preset="tldr_table")
        seen = _capture_create(d, monkeypatch)
        d._create_session()
        docs_text = library.attached_docs_preamble(cwd, ["a.md"])
        preset_text = response_presets.instruction_for("tldr_table")
        # Neither clobbers the other: preamble first, blank line, then preset.
        assert seen["append_system_prompt"] == docs_text + "\n\n" + preset_text
        assert docs_text in seen["append_system_prompt"]
        assert preset_text in seen["append_system_prompt"]

    def test_preset_only_is_unchanged_39_behavior(self, tmp_path, monkeypatch):
        cwd = _project(tmp_path)
        d = _driver(cwd=cwd, response_preset="concise")
        seen = _capture_create(d, monkeypatch)
        d._create_session()
        assert seen["append_system_prompt"] == \
            response_presets.instruction_for("concise")

    def test_neither_appends_nothing(self, tmp_path, monkeypatch):
        cwd = _project(tmp_path)
        d = _driver(cwd=cwd)
        seen = _capture_create(d, monkeypatch)
        d._create_session()
        assert seen["append_system_prompt"] is None

    def test_unresolvable_docs_append_nothing(self, tmp_path, monkeypatch):
        # A doc deleted since selection degrades to no preamble — never a
        # failed launch, never a dead path handed to the agent.
        cwd = _project(tmp_path)
        d = _driver(cwd=cwd, attached_docs=["ghost.md"])
        seen = _capture_create(d, monkeypatch)
        d._create_session()
        assert seen["append_system_prompt"] is None


# ---------------------------------------------------------------------------
# BridgeDriver.fork() — the fork's OWN launch carries the docs preamble (§11
# #15/#44). Adoption is a warm rebind (never _create_session), so the
# --fork-session spawn itself must carry append_system_prompt or the fork's
# inherited attached_docs would be record-only (readback claiming docs the
# agent never saw, and behavior silently flipping at the next cold restore).
# ---------------------------------------------------------------------------

class TestForkSpawnCarriesDocsPreamble:
    def test_fork_passes_docs_only_preamble(self, tmp_path, monkeypatch):
        cwd = _project(tmp_path)
        _store_doc(cwd, "a.md")
        d = _driver(cwd=cwd, attached_docs=["a.md"], response_preset="concise")
        seen = {}

        def fake_fork(src, new_name, **kw):
            seen.update(kw)
            return {"status": "ok", "name": new_name, "session_id": "f-1"}

        monkeypatch.setattr(d._bridge, "fork", fake_fork)
        monkeypatch.setattr(d, "nudge", lambda: None)
        asyncio.run(d.fork("awl-fork-1"))
        assert seen["append_system_prompt"] == \
            library.attached_docs_preamble(cwd, ["a.md"])
        # The #39 preset is deliberately NOT inherited at fork — docs ONLY.
        assert response_presets.instruction_for("concise") \
            not in seen["append_system_prompt"]

    def test_fork_without_docs_passes_none(self, tmp_path, monkeypatch):
        cwd = _project(tmp_path)
        d = _driver(cwd=cwd)
        seen = {}

        def fake_fork(src, new_name, **kw):
            seen.update(kw)
            return {"status": "ok", "name": new_name, "session_id": "f-2"}

        monkeypatch.setattr(d._bridge, "fork", fake_fork)
        monkeypatch.setattr(d, "nudge", lambda: None)
        asyncio.run(d.fork("awl-fork-2"))
        assert seen["append_system_prompt"] is None


# ---------------------------------------------------------------------------
# BridgeDriver.start() (create path) — attached_docs persists into the roster
# record (state/agents.json carries per-agent launch config, §8.2/§8.4).
# ---------------------------------------------------------------------------

class _FakeCreateBridge:
    """Stands in for TmuxBridge on the create path (no WSL/tmux)."""

    def __init__(self):
        self.create_kwargs = None

    def create(self, name, **kw):
        self.create_kwargs = {"name": name, **kw}
        return {"session_id": "cid-777"}

    def session_id_for(self, name):
        return "cid-777"

    def wait_idle(self, name, timeout, interval):
        return True


class TestStartPersistsAttachedDocs:
    def test_record_carries_attached_docs(self, tmp_path, monkeypatch):
        import drivers.bridge as db
        saved: dict = {}
        monkeypatch.setattr(db, "_save_record", lambda r: saved.update(r))
        cwd = _project(tmp_path)
        _store_doc(cwd, "a.md")
        d = BridgeDriver(
            DriverConfig(cwd=cwd, attached_docs=["a.md"],
                         response_preset="concise"),
            lambda e: None, session_id="s44")
        d._bridge = _FakeCreateBridge()
        asyncio.run(d.start())
        assert saved["session_id"] == "s44"
        assert saved["attached_docs"] == ["a.md"]
        # Rides NEXT TO the preset — the two launch-config fields coexist.
        assert saved["response_preset"] == "concise"

    def test_record_carries_none_when_nothing_attached(self, tmp_path, monkeypatch):
        import drivers.bridge as db
        saved: dict = {}
        monkeypatch.setattr(db, "_save_record", lambda r: saved.update(r))
        cwd = _project(tmp_path)
        d = BridgeDriver(DriverConfig(cwd=cwd), lambda e: None, session_id="s45")
        d._bridge = _FakeCreateBridge()
        asyncio.run(d.start())
        assert saved["attached_docs"] is None


# ---------------------------------------------------------------------------
# Sidecar carry — request model -> SessionState -> launch_config readback,
# and the resume-descriptor normalization (roster lifts the field; the LIGHT
# archive record has none).
# ---------------------------------------------------------------------------

class TestSidecarCarry:
    @pytest.fixture(autouse=True)
    def _clean(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(tmp_path / "rt"))
        import main
        import state_store
        state_store.reset()
        main.sessions.clear()
        self.main = main
        self.tmp_path = tmp_path
        yield
        state_store.reset()
        main.sessions.clear()

    def test_request_model_defaults_to_none(self):
        req = self.main.CreateSessionRequest()
        assert req.attached_docs is None

    def test_create_session_carries_attached_docs(self, monkeypatch):
        main = self.main
        cwd = _project(self.tmp_path)

        async def _stub_start(session):
            session.status = "idle"

        monkeypatch.setattr(main, "start_session", _stub_start)
        req = main.CreateSessionRequest(
            cwd=cwd, driver="bridge", attached_docs=["a.md", "b.md"])
        out = asyncio.run(main.create_session(req))
        sid = out["session_id"]
        assert main.sessions[sid].attached_docs == ["a.md", "b.md"]
        # Surfaced for readback next to the other launch config (§11 #44).
        assert out["launch_config"]["attached_docs"] == ["a.md", "b.md"]

    def test_launch_config_none_when_absent(self, monkeypatch):
        main = self.main
        cwd = _project(self.tmp_path)

        async def _stub_start(session):
            session.status = "idle"

        monkeypatch.setattr(main, "start_session", _stub_start)
        out = asyncio.run(main.create_session(
            main.CreateSessionRequest(cwd=cwd, driver="bridge")))
        assert out["launch_config"]["attached_docs"] is None

    def test_roster_descriptor_lifts_attached_docs(self):
        d = self.main._resumable_from_roster(
            {"session_id": "s1", "claude_session_id": "cid", "cwd": "/p",
             "attached_docs": ["guide.md"]})
        assert d["attached_docs"] == ["guide.md"]

    def test_archive_descriptor_has_no_attached_docs(self):
        # The LIGHT archive record carries no launch config (§11 #18) — a
        # resume from the archive starts with nothing attached.
        d = self.main._resumable_from_archive(
            {"session_id": "s1", "archive_id": "arc1", "cwd": "/p"})
        assert d["attached_docs"] is None


# ---------------------------------------------------------------------------
# SessionState -> DriverConfig carry at EVERY main.py construction site. These
# exercise the REAL functions (start_session / reconnect_sessions /
# _resume_agent_from_descriptor / _adopt_forked_session) with only the driver
# faked, so reverting any single `attached_docs=…` carry line fails here —
# the launch-config field must reach the driver on every path, not just the
# request model and the readback.
# ---------------------------------------------------------------------------

class _CapturedDriver:
    """create_driver-shaped fake: captures its DriverConfig, starts clean."""

    name = "captured"

    def __init__(self, config):
        self.config = config

    def bind_session_id(self, sid):
        self.session_id = sid

    async def start(self):
        return None

    async def events(self):
        return
        yield  # pragma: no cover — makes this an (empty) async generator


class _CapturedBridgeDriver(_CapturedDriver):
    """drivers.bridge.BridgeDriver-shaped fake for the reconnect-style sites
    (cold restore / on-demand resume #17 / fork-adopt #15)."""

    instances: list = []

    def __init__(self, config, on_event, **kwargs):
        super().__init__(config)
        self.kwargs = kwargs
        type(self).instances.append(self)


class TestDriverConfigCarry:
    @pytest.fixture(autouse=True)
    def _clean(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(tmp_path / "rt"))
        import main
        import state_store
        state_store.reset()
        main.sessions.clear()
        _CapturedBridgeDriver.instances = []
        self.main = main
        self.tmp_path = tmp_path
        yield
        state_store.reset()
        main.sessions.clear()
        _CapturedBridgeDriver.instances = []

    # NOTE: the lifecycle paths spawn a listen task inside their own loop;
    # asyncio.run()'s shutdown cancels + gathers pending tasks, and _listen
    # handles CancelledError, so the tests never await it across loops.

    def test_start_session_carries_attached_docs_into_driver_config(self, monkeypatch):
        # The PRIMARY production path: create_session -> start_session builds
        # the DriverConfig from the SessionState (main.py start_session).
        main = self.main
        cwd = _project(self.tmp_path)
        captured = {}

        def fake_create_driver(config, on_event, driver_name=None):
            captured["config"] = config
            return _CapturedDriver(config)

        monkeypatch.setattr(main, "create_driver", fake_create_driver)
        session = main.SessionState(
            session_id="s-carry", agent_type=None, model=None,
            permission_mode="acceptEdits", cwd=cwd, system_prompt=None,
            driver_name="bridge", attached_docs=["a.md"],
            response_preset="concise")

        async def _run():
            await main.start_session(session)
            if session.listen_task:
                await session.listen_task

        asyncio.run(_run())
        assert session.status == "idle"
        assert captured["config"].attached_docs == ["a.md"]
        # Rides next to the sibling launch-config field, same seam.
        assert captured["config"].response_preset == "concise"

    def test_reconnect_cold_restore_carries_attached_docs(self, monkeypatch):
        # reconnect_sessions' cold branch rebuilds the DriverConfig from the
        # persisted roster record (main.py reconnect_sessions).
        main = self.main
        import bridge as bridge_pkg
        import drivers.bridge as db
        import runtime_store
        cwd = _project(self.tmp_path)

        class _NoTmux:
            def list(self):
                return []          # nothing alive -> the COLD branch

        monkeypatch.setattr(bridge_pkg, "TmuxBridge", _NoTmux)
        monkeypatch.setattr(db, "BridgeDriver", _CapturedBridgeDriver)
        runtime_store.save_record({
            "session_id": "s-cold", "tmux_name": "awl-cold",
            "claude_session_id": "cid-cold", "cwd": cwd,
            "attached_docs": ["guide.md"],
        })
        asyncio.run(main.reconnect_sessions())
        assert "s-cold" in main.sessions
        assert main.sessions["s-cold"].attached_docs == ["guide.md"]
        assert _CapturedBridgeDriver.instances[-1].config.attached_docs == ["guide.md"]
        assert _CapturedBridgeDriver.instances[-1].kwargs["cold_restore"] is True

    def test_resume_descriptor_carries_attached_docs(self, monkeypatch):
        # The on-demand resume path (#17): descriptor -> SessionState +
        # DriverConfig (main.py _resume_agent_from_descriptor).
        main = self.main
        import drivers.bridge as db
        cwd = _project(self.tmp_path)
        monkeypatch.setattr(db, "BridgeDriver", _CapturedBridgeDriver)
        d = {"session_id": "s-res", "cwd": cwd, "claude_session_id": "cid-res",
             "attached_docs": ["guide.md"]}
        session = asyncio.run(main._resume_agent_from_descriptor(d))
        assert session.attached_docs == ["guide.md"]
        assert _CapturedBridgeDriver.instances[-1].config.attached_docs == ["guide.md"]

    def test_fork_adopt_carries_attached_docs(self, monkeypatch):
        # The fork-adopt path (#15): the fork inherits the source's docs into
        # its SessionState + DriverConfig (main.py _adopt_forked_session); the
        # matching launch BEHAVIOR is pinned by TestForkSpawnCarriesDocsPreamble.
        main = self.main
        import drivers.bridge as db
        cwd = _project(self.tmp_path)
        monkeypatch.setattr(db, "BridgeDriver", _CapturedBridgeDriver)
        source = main.SessionState(
            session_id="s-src", agent_type=None, model=None,
            permission_mode="acceptEdits", cwd=cwd, system_prompt=None,
            driver_name="bridge", attached_docs=["guide.md"])
        descriptor = {"name": "awl-fork-x", "cwd": cwd, "session_id": "cid-fork",
                      "source_session_id": "cid-src", "rewound_to": None}
        session = asyncio.run(main._adopt_forked_session(
            descriptor, source=source,
            identity={"name": "forky", "number": 2}, model=None,
            permission_mode="acceptEdits"))
        assert session.attached_docs == ["guide.md"]
        assert _CapturedBridgeDriver.instances[-1].config.attached_docs == ["guide.md"]
