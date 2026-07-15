"""Hermetic unit tests for Handoff artifacts (§7.19, §8.4, §11 #16).

The decided contract this file encodes:

  * On **Handoff** (the fork-with-context-carryover #15 built), #16 layers a
    generated **summary/handoff report** on the plain context carry-over — a
    utility-LLM pass over the source agent's recent transcript, distilled into
    SHORT structured markdown (what was being done / key decisions / current state
    & pending; ⚠ assumed format, §7.14 TL;DR style).
  * The artifact is persisted as a **Library doc** (§8.4) under the project's
    ``docs/`` with **provenance** (created-by / session), via :mod:`library`.
  * It's wired BOTH as a ``handoff`` flag on ``POST /sessions/{id}/fork`` (the
    Create payload references the doc) AND as a dedicated
    ``POST /sessions/{id}/handoff-report`` — both ride the same generator.

The LLM generation is the only live aspect; it is STUBBED here (injected
``generate=`` / a monkeypatched ``utility_llm.handoff_report``), so the assembly
+ Library write + provenance + endpoint/fork plumbing is what's pinned. No SDK,
no WSL, no network — pure files on ``tmp_path``.
"""

import asyncio
import sys
from pathlib import Path

import pytest

_SIDECAR = Path(__file__).resolve().parent.parent / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))

import deletion  # noqa: E402
import handoff  # noqa: E402
import library  # noqa: E402
import state_store  # noqa: E402
import storage  # noqa: E402
import utility_llm  # noqa: E402
import main  # noqa: E402
from main import SessionState  # noqa: E402
from fastapi import HTTPException  # noqa: E402


@pytest.fixture(autouse=True)
def _clean(tmp_path, monkeypatch):
    monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(tmp_path / "rt"))
    deletion.reset(); state_store.reset()
    main.sessions.clear()
    _ord = main._identity_ordinal
    yield
    main._identity_ordinal = _ord
    deletion.reset(); state_store.reset()
    main.sessions.clear()


def _proj(tmp_path, name="proj") -> str:
    p = tmp_path / name
    p.mkdir(parents=True, exist_ok=True)
    return str(p)


def _session(cwd, sid="s1", identity=None):
    s = SessionState(session_id=sid, agent_type=None, model="claude-x",
                     permission_mode="acceptEdits", cwd=cwd, system_prompt=None,
                     driver_name="bridge", identity=identity)
    return s


def _events():
    return [
        {"type": "user", "content": "please refactor the parser"},
        {"type": "assistant", "content": [
            {"type": "text", "text": "I refactored parse() and decided to keep the old API."},
            {"type": "tool_use", "name": "Edit", "input": {}},  # skipped (non-text)
        ]},
        {"type": "status_change", "status": "idle"},  # skipped (non-message)
    ]


# ---------------------------------------------------------------------------
# Pure reducers
# ---------------------------------------------------------------------------

class TestTranscriptReducer:
    def test_keeps_only_message_text_tagged_by_role(self):
        text = handoff.transcript_text_from_events(_events())
        assert "user: please refactor the parser" in text
        assert "assistant: I refactored parse() and decided to keep the old API." in text
        # Non-text blocks and non-message events contribute nothing.
        assert "tool_use" not in text and "status_change" not in text

    def test_empty_events_yield_empty_string(self):
        assert handoff.transcript_text_from_events([]) == ""
        assert handoff.transcript_text_from_events(None) == ""

    def test_tail_is_kept_under_limit(self):
        evs = [{"type": "assistant", "content": "x" * 100} for _ in range(50)]
        out = handoff.transcript_text_from_events(evs, limit=200)
        assert len(out) == 200        # the freshest tail, capped


class TestComposeAndFilename:
    def test_compose_frames_summary_with_provenance_header(self):
        doc = handoff.compose_handoff_doc(
            "## What was being done\n- stuff",
            source_identity={"name": "nova", "number": 3},
            source_session_id="s1")
        assert doc.startswith("# Handoff — nova")
        assert "from session s1" in doc
        assert "## What was being done" in doc

    def test_compose_handles_empty_summary(self):
        doc = handoff.compose_handoff_doc("", source_identity=None,
                                          source_session_id=None)
        assert "no transcript content" in doc

    def test_filename_is_safe_md(self):
        fn = handoff.build_handoff_filename({"name": "Nova Bright!"})
        assert fn.startswith("handoff-nova-bright-") and fn.endswith(".md")
        # Passes the Library's own filename gate (no separators / .md required).
        assert library._safe_md_filename(fn) == fn

    def test_filename_unnamed_falls_back_to_agent(self):
        fn = handoff.build_handoff_filename(None)
        assert fn.startswith("handoff-agent-")


# ---------------------------------------------------------------------------
# generate_and_store_handoff — the assembly + Library write + provenance
# ---------------------------------------------------------------------------

class TestGenerateAndStore:
    def test_writes_doc_with_provenance_using_injected_generate(self, tmp_path):
        cwd = _proj(tmp_path)
        captured = {}

        async def _gen(text, model):
            captured["text"] = text
            captured["model"] = model
            return "## What was being done\n- refactor"

        art = asyncio.run(handoff.generate_and_store_handoff(
            cwd, "user: please refactor",
            source_session_id="s1", source_identity={"name": "nova", "number": 3},
            target_session_id="fk", model="haiku", generate=_gen))

        # The injected generator saw the transcript + model.
        assert captured["text"] == "user: please refactor"
        assert captured["model"] == "haiku"
        # The doc landed in the project's docs/ dir and holds the framed summary.
        path = Path(art["path"])
        assert path.is_file() and path.parent == storage.docs_dir(cwd)
        body = path.read_text(encoding="utf-8")
        assert body.startswith("# Handoff — nova")
        assert "## What was being done" in body
        assert art["subdir"] == "docs" and art["summary"].startswith("## What")
        assert art["target_session_id"] == "fk"
        # Provenance sidecar stamped (created-by = source name, session = source id).
        meta = library.load_meta(path)
        assert meta["provenance"]["created_by"] == "nova"
        assert meta["provenance"]["session"] == "s1"

    def test_defaults_to_utility_llm_handoff_report(self, tmp_path, monkeypatch):
        cwd = _proj(tmp_path)

        async def _fake_report(text, model=None):
            return "## Key decisions\n- kept API"
        monkeypatch.setattr(utility_llm, "handoff_report", _fake_report)

        art = asyncio.run(handoff.generate_and_store_handoff(
            cwd, "some transcript", source_session_id="s2",
            source_identity={"name": "zed"}))
        assert "## Key decisions" in Path(art["path"]).read_text(encoding="utf-8")

    def test_no_cwd_raises(self):
        with pytest.raises(ValueError):
            asyncio.run(handoff.generate_and_store_handoff(
                None, "t", source_session_id="s1",
                generate=lambda t, m: _async_return("x")))


def _async_return(v):
    async def _c():
        return v
    return _c()


# ---------------------------------------------------------------------------
# POST /sessions/{id}/handoff-report — the dedicated endpoint
# ---------------------------------------------------------------------------

class TestHandoffEndpoint:
    def test_generates_and_stores_for_live_session(self, tmp_path, monkeypatch):
        cwd = _proj(tmp_path)
        s = _session(cwd, identity={"name": "nova", "number": 3})
        s.events = _events()
        main.sessions["s1"] = s

        seen = {}

        async def _fake_report(text, model=None):
            seen["text"] = text
            return "## Current state & what's pending\n- ship it"
        monkeypatch.setattr(utility_llm, "handoff_report", _fake_report)

        out = asyncio.run(main.handoff_report_endpoint(
            "s1", main.HandoffReportRequest(target_session_id="fk")))
        # The report saw the source's recent transcript text.
        assert "refactored parse()" in seen["text"]
        path = Path(out["path"])
        assert path.is_file()
        assert "## Current state" in path.read_text(encoding="utf-8")
        assert out["created_by"] == "nova" and out["target_session_id"] == "fk"

    def test_unknown_session_404(self):
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.handoff_report_endpoint("ghost", main.HandoffReportRequest()))
        assert ei.value.status_code == 404

    def test_no_project_home_400(self):
        s = _session(None)  # cwd-less: nowhere to store the doc
        main.sessions["s1"] = s
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.handoff_report_endpoint("s1", main.HandoffReportRequest()))
        assert ei.value.status_code == 400

    def test_generation_failure_502(self, tmp_path, monkeypatch):
        cwd = _proj(tmp_path)
        main.sessions["s1"] = _session(cwd, identity={"name": "nova"})

        async def _boom(text, model=None):
            raise RuntimeError("sdk down")
        monkeypatch.setattr(utility_llm, "handoff_report", _boom)
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.handoff_report_endpoint("s1", main.HandoffReportRequest()))
        assert ei.value.status_code == 502
        assert "handoff report failed" in ei.value.detail


# ---------------------------------------------------------------------------
# POST /sessions/{id}/fork  — the handoff flag rides the fork flow
# ---------------------------------------------------------------------------

class _ForkSrcDriver:
    name = "bridge"

    def supports(self, cap):
        return cap == "fork"

    async def fork(self, new_name, **kw):
        return {"name": new_name, "source": "s1", "source_session_id": "srcid",
                "session_id": "forkcid", "cwd": kw.get("cwd") or "/home/u/proj",
                "filestate": {"isolated": False}, "rewound_to": None}


class TestForkHandoffFlag:
    def _wire_fork(self, monkeypatch, cwd):
        s = _session(cwd, identity={"name": "nova", "number": 1})
        s.driver = _ForkSrcDriver()
        main.sessions["s1"] = s

        class _Forked:
            session_id = "fk"

            def __init__(self, cwd):
                self.cwd = cwd

            def to_dict(self):
                return {"session_id": "fk", "status": "idle", "identity": {}}

        async def _adopt(descriptor, *, source, identity, model, permission_mode):
            return _Forked(descriptor.get("cwd"))
        monkeypatch.setattr(main, "_adopt_forked_session", _adopt)
        return s

    def test_handoff_flag_generates_artifact(self, tmp_path, monkeypatch):
        cwd = _proj(tmp_path)
        self._wire_fork(monkeypatch, cwd)
        seen = {}

        async def _gen(source, *, cwd, target_session_id, model):
            seen.update(src=source.session_id, cwd=cwd, target=target_session_id)
            return {"filename": "handoff-x.md", "summary": "S"}
        monkeypatch.setattr(main, "_generate_handoff_artifact", _gen)

        out = asyncio.run(main.fork_session(
            "s1", main.ForkRequest(handoff=True, cwd=cwd)))
        assert out["handoff"]["filename"] == "handoff-x.md"
        # Sourced from the ORIGINAL agent, stored in the FORK's cwd, for the fork.
        assert seen["src"] == "s1" and seen["target"] == "fk" and seen["cwd"] == cwd

    def test_no_flag_skips_artifact(self, tmp_path, monkeypatch):
        cwd = _proj(tmp_path)
        self._wire_fork(monkeypatch, cwd)
        called = {"n": 0}

        async def _gen(*a, **k):
            called["n"] += 1
            return {}
        monkeypatch.setattr(main, "_generate_handoff_artifact", _gen)

        out = asyncio.run(main.fork_session("s1", main.ForkRequest()))
        assert "handoff" not in out
        assert called["n"] == 0

    def test_handoff_failure_is_reported_not_fatal(self, tmp_path, monkeypatch):
        cwd = _proj(tmp_path)
        self._wire_fork(monkeypatch, cwd)

        async def _gen(source, *, cwd, target_session_id, model):
            raise RuntimeError("gen boom")
        monkeypatch.setattr(main, "_generate_handoff_artifact", _gen)

        out = asyncio.run(main.fork_session("s1", main.ForkRequest(handoff=True)))
        # The fork still succeeded; the handoff failure rides the payload honestly.
        assert out["session_id"] == "fk"
        assert out["handoff"]["error"] == "gen boom"
