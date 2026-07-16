"""Hermetic unit tests for Import external Claude context (§11 #28 — §7.3, §7.16, §8.6).

The decided contract this file encodes:

  * The working exporters at ``dev/tools/claude-context-extractor/``
    (``extract-web.py`` — claude.ai, needs a gitignored ``session_key.txt`` +
    network; ``extract-desktop.py`` — the desktop app's local session store)
    are reused **verbatim** via subprocess shell-out: ``sidecar/import_context.py``
    runs ``--list`` to enumerate sessions by title and ``--name=<title> --out
    <temp dir under .scratch/> --no-open`` to export (the equals-form spelling,
    so a dash-leading title still binds), capturing the markdown the tool
    writes (the temp export dir is removed after capture; ``--no-open``
    always — an import never pops an editor window).
  * **One engine, one selectable destination** (``import_by_title(source,
    title, destination, target_agent, cwd)``): ``agent`` delivers the markdown
    (framed with an attributed header) onto the target agent's §7.3 prompt
    queue via an injected ``deliver`` callable — ``queue`` disposition,
    enqueued never dropped; ``panel`` returns the rendered markdown for the
    operator read panel; ``library`` persists a §7.16 reference doc under the
    project's ``docs/`` with §8.5 provenance stamped
    (``created_by="import:<source>"``, ``session=<external id>``) and
    ``-2``/``-3``… disambiguation instead of clobbering.
  * **Honest degrades, never a crash or a hang:** a missing session key /
    desktop store / extractor tool raises ``SourceUnavailableError`` (HTTP
    400, plain-language); no title match raises ``SessionNotFoundError``
    (404); the bounded subprocess timeout (``AWL_IMPORT_TIMEOUT``, default
    120 s) raises ``ExtractorTimeoutError`` (504); any other extractor failure
    (incl. an ambiguous title) is the base ``ImportContextError`` (400).
  * Endpoints: ``GET /import/external?source=web|desktop`` lists; ``POST
    /import/external {source, title, destination, target_agent?, cwd?}``
    imports — destination prerequisites validated BEFORE the network-bound
    fetch (400 unknown source/destination, missing ``target_agent``, or a
    ``library`` cwd that doesn't resolve to an existing project; 404 unknown
    target agent), the agent target's liveness RE-CHECKED at delivery time
    (retired/deleted mid-fetch → honest 409, never a silent drop), an idle
    target flushed immediately (with the §11 #34 poll nudge), a busy one kept
    queued.

The extractor subprocess is FAKED throughout (``import_context._run`` /
``subprocess.run``) — no network, no WSL, no real exporter runs; the scratch
base is pointed at ``tmp_path`` via ``AWL_IMPORT_SCRATCH``. These carry
neither the ``integration`` nor the ``slow`` mark.
"""

import asyncio
import subprocess
import sys
from pathlib import Path

import pytest

_SIDECAR = Path(__file__).resolve().parent.parent / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))

import import_context  # noqa: E402
import library  # noqa: E402
import state_store  # noqa: E402
import main  # noqa: E402
from main import SessionState  # noqa: E402
from fastapi import HTTPException  # noqa: E402


@pytest.fixture(autouse=True)
def _clean(tmp_path, monkeypatch):
    monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(tmp_path / "rt"))
    monkeypatch.setenv("AWL_IMPORT_SCRATCH", str(tmp_path / "scratch"))
    state_store.reset()
    main.sessions.clear()
    yield
    state_store.reset()
    main.sessions.clear()


# ---------------------------------------------------------------------------
# Fakes & fixtures
# ---------------------------------------------------------------------------

_EXTERNAL_ID = "123e4567-e89b-12d3-a456-426614174000"

_MD = f"""# Linting explained simply

- conversation: {_EXTERNAL_ID}
- messages: 4
- exported: 2026-07-15 10:00

---

## human
what is linting?

## assistant
Linting is static analysis of source code.
"""

_EXPORT_BASENAME = "claude-2026-07-01-linting-explained-simply"


def _proc(rc=0, stdout="", stderr=""):
    return subprocess.CompletedProcess([], rc, stdout, stderr)


def _install_fake_run(monkeypatch, *, rc=0, stdout="", stderr="", md=None,
                      calls=None):
    """Replace ``import_context._run`` with a scripted fake. With ``md`` set it
    behaves like a successful export: writes the markdown (and a .source.json
    sibling, like the web tool) into the ``--out`` dir it was given."""
    def run(source, args, timeout_s=None):
        if calls is not None:
            calls.append((source, list(args)))
        if md is not None and "--out" in args:
            out = Path(args[args.index("--out") + 1])
            out.mkdir(parents=True, exist_ok=True)
            (out / f"{_EXPORT_BASENAME}.md").write_text(md, encoding="utf-8")
            (out / f"{_EXPORT_BASENAME}.source.json").write_text("{}",
                                                                 encoding="utf-8")
        return _proc(rc, stdout, stderr)
    monkeypatch.setattr(import_context, "_run", run)


def _proj(tmp_path, name="proj") -> str:
    p = tmp_path / name
    p.mkdir(parents=True, exist_ok=True)
    return str(p)


def _session(sid="s1", status="idle"):
    s = SessionState(session_id=sid, agent_type=None, model=None,
                     permission_mode="acceptEdits", cwd=None,
                     system_prompt=None, driver_name="bridge")
    s.status = status
    main.sessions[sid] = s
    return s


# ---------------------------------------------------------------------------
# list_external — parsing the extractors' --list output
# ---------------------------------------------------------------------------

class TestListExternal:
    def test_web_rows_parse_to_uniform_dicts(self, monkeypatch):
        stdout = (
            f"2026-07-05T12:34:56  {_EXTERNAL_ID}  Linting explained simply\n"
            # An empty updated_at still parses (the tool prints '' + 2 spaces).
            f"  99999999-e89b-12d3-a456-426614174999  (untitled)\n")
        _install_fake_run(monkeypatch, stdout=stdout)
        rows = import_context.list_external("web")
        assert rows == [
            {"source": "web", "id": _EXTERNAL_ID,
             "title": "Linting explained simply",
             "updated_at": "2026-07-05T12:34:56", "model": None},
            {"source": "web", "id": "99999999-e89b-12d3-a456-426614174999",
             "title": "(untitled)", "updated_at": None, "model": None},
        ]

    def test_web_list_invokes_only_dash_dash_list(self, monkeypatch):
        calls = []
        _install_fake_run(monkeypatch, stdout="", calls=calls)
        import_context.list_external("web")
        assert calls == [("web", ["--list"])]

    def test_desktop_rows_parse_fixed_width_and_skip_chrome(self, monkeypatch):
        stdout = (
            "2 local-agent-mode sessions:\n"
            "\n"
            f"  {'2026-07-05 12:34':16}  {'claude-sonnet-4-5':16}  glossary-maintenance-strategy-1\n"
            f"  {'?':16}  {'claude-opus-4-6':16}  untimed session\n")
        _install_fake_run(monkeypatch, stdout=stdout)
        rows = import_context.list_external("desktop")
        assert rows == [
            {"source": "desktop", "id": None,
             "title": "glossary-maintenance-strategy-1",
             "updated_at": "2026-07-05 12:34", "model": "claude-sonnet-4-5"},
            {"source": "desktop", "id": None, "title": "untimed session",
             "updated_at": None, "model": "claude-opus-4-6"},
        ]

    def test_unknown_source_is_a_request_error(self):
        with pytest.raises(ValueError, match="web|desktop"):
            import_context.list_external("codex")

    def test_missing_extractor_script_degrades_plainly(self, monkeypatch, tmp_path):
        # The tool dir exists but carries no scripts -> SourceUnavailableError,
        # naming the expected location (never an unexplained crash).
        monkeypatch.setattr(import_context, "TOOL_DIR", tmp_path / "no-tools")
        with pytest.raises(import_context.SourceUnavailableError,
                           match="extractor is missing"):
            import_context.list_external("web")


# ---------------------------------------------------------------------------
# Honest degrades — missing key / store, timeout, no match, ambiguity
# ---------------------------------------------------------------------------

class TestDegrades:
    def test_missing_session_key_degrade(self, monkeypatch):
        # extract-web.py exits 1 with its load_key message when session_key.txt
        # is absent/placeholder — the engine turns that into a plain-language
        # SourceUnavailableError pointing at the key file.
        _install_fake_run(monkeypatch, rc=1, stderr=(
            "No sessionKey found. Pass --session-key, set CLAUDE_SESSION_KEY, "
            "or paste it into session_key.txt."))
        with pytest.raises(import_context.SourceUnavailableError,
                           match="session_key.txt"):
            import_context.list_external("web")

    def test_rejected_session_key_degrade(self, monkeypatch):
        _install_fake_run(monkeypatch, rc=1,
                          stderr="HTTP 401 on https://claude.ai/api/organizations\n{}")
        with pytest.raises(import_context.SourceUnavailableError,
                           match="rejected the stored session key"):
            import_context.list_external("web")

    def test_missing_desktop_store_degrade(self, monkeypatch):
        _install_fake_run(monkeypatch, rc=1, stderr=(
            "No local-agent-mode session store found (is the Claude desktop "
            "app installed?). Pass --root <dir> if sessions live somewhere "
            "non-standard."))
        with pytest.raises(import_context.SourceUnavailableError,
                           match="desktop app"):
            import_context.list_external("desktop")

    def test_subprocess_timeout_degrade(self, monkeypatch):
        # The bounded timeout fires INSIDE _run (subprocess.run raises
        # TimeoutExpired after killing the child) -> ExtractorTimeoutError,
        # never a hang and never a raw traceback.
        def hang(*a, **k):
            raise subprocess.TimeoutExpired(cmd="extract-web.py", timeout=5)
        monkeypatch.setattr(import_context.subprocess, "run", hang)
        with pytest.raises(import_context.ExtractorTimeoutError,
                           match="did not finish"):
            import_context.list_external("web")

    def test_timeout_knob_env_parse(self, monkeypatch):
        monkeypatch.setenv("AWL_IMPORT_TIMEOUT", "7.5")
        assert import_context._timeout_s() == 7.5
        monkeypatch.setenv("AWL_IMPORT_TIMEOUT", "not-a-number")
        assert import_context._timeout_s() == import_context.DEFAULT_TIMEOUT_S

    def test_no_title_match_is_not_found(self, monkeypatch):
        _install_fake_run(monkeypatch, rc=1,
                          stderr='No conversation title matching "nope".')
        with pytest.raises(import_context.SessionNotFoundError, match="nope"):
            import_context.fetch_markdown("web", "nope")

    def test_ambiguous_title_is_a_plain_400_class_error(self, monkeypatch):
        _install_fake_run(monkeypatch, rc=1, stderr=(
            '"lint" is ambiguous — 3 matches:\n  ...\n'
            "Refine --name, or use --conversation <uuid>."))
        with pytest.raises(import_context.ImportContextError,
                           match="more than one"):
            import_context.fetch_markdown("web", "lint")

    def test_no_match_with_trigger_words_in_title_stays_not_found(self, monkeypatch):
        # The no-match exit message embeds the queried title VERBATIM — a title
        # that happens to contain a prerequisite trigger string ("HTTP 401",
        # "Network error") must still classify as not-found (404), never as a
        # source-prerequisite 400 telling the operator to rotate a good key.
        _install_fake_run(monkeypatch, rc=1, stderr=(
            'No conversation title matching "debugging HTTP 401 responses".'))
        with pytest.raises(import_context.SessionNotFoundError):
            import_context.fetch_markdown("web", "debugging HTTP 401 responses")
        _install_fake_run(monkeypatch, rc=1, stderr=(
            'No conversation title matching "Network error triage".'))
        with pytest.raises(import_context.SessionNotFoundError):
            import_context.fetch_markdown("web", "Network error triage")

    def test_ambiguous_candidates_with_trigger_words_stay_ambiguous(self, monkeypatch):
        # The ambiguous listing prints CANDIDATE TITLES on indented lines —
        # trigger strings inside them must not flip the class to
        # SourceUnavailableError (the matchers are line-start anchored).
        _install_fake_run(monkeypatch, rc=1, stderr=(
            '"error" is ambiguous — 2 matches:\n'
            f"  2026-07-05T00:00:00  {_EXTERNAL_ID}  Network error triage\n"
            f"  2026-07-04T00:00:00  {_EXTERNAL_ID}  HTTP 401 postmortem\n"
            "Refine --name, or use --conversation <uuid>."))
        with pytest.raises(import_context.ImportContextError, match="more than one"):
            import_context.fetch_markdown("web", "error")

    def test_success_with_no_markdown_written_is_an_error(self, monkeypatch):
        # rc == 0 but the export dir stayed empty -> honest error, never a
        # silent empty import.
        _install_fake_run(monkeypatch, rc=0, stdout="Wrote to ...")
        with pytest.raises(import_context.ImportContextError,
                           match="no markdown"):
            import_context.fetch_markdown("web", "Linting explained simply")


# ---------------------------------------------------------------------------
# fetch_markdown — capture the export, then clean up
# ---------------------------------------------------------------------------

class TestFetchMarkdown:
    def test_captures_markdown_title_and_external_id(self, monkeypatch):
        calls = []
        _install_fake_run(monkeypatch, md=_MD, calls=calls)
        fetched = import_context.fetch_markdown("web", "Linting explained simply")
        assert fetched["markdown"] == _MD
        assert fetched["title"] == "Linting explained simply"
        assert fetched["external_id"] == _EXTERNAL_ID
        assert fetched["filename"] == f"{_EXPORT_BASENAME}.md"
        # The exporter was reused verbatim: --name=/--out/--no-open, one call.
        (source, args), = calls
        assert source == "web" and args[0] == "--name=Linting explained simply"
        assert "--out" in args and "--no-open" in args

    def test_dash_leading_title_binds_via_equals_form(self, monkeypatch):
        # A session renamed to a dash-leading, no-space token ("-drafts") is
        # listable — the equals-form spelling keeps it importable too (argparse
        # would refuse a separate-token "-drafts" as option-like).
        calls = []
        _install_fake_run(monkeypatch, md=_MD, calls=calls)
        import_context.fetch_markdown("web", "-drafts")
        (source, args), = calls
        assert args[0] == "--name=-drafts"

    def test_temp_export_dir_is_cleaned_up(self, monkeypatch, tmp_path):
        _install_fake_run(monkeypatch, md=_MD)
        import_context.fetch_markdown("web", "Linting explained simply")
        scratch = tmp_path / "scratch"  # AWL_IMPORT_SCRATCH from the fixture
        assert not scratch.exists() or not any(scratch.iterdir())

    def test_blank_title_is_a_request_error(self):
        with pytest.raises(ValueError, match="title"):
            import_context.fetch_markdown("web", "   ")


# ---------------------------------------------------------------------------
# import_by_title — one engine, one selectable destination
# ---------------------------------------------------------------------------

class TestDestinations:
    def test_unknown_destination_is_a_request_error(self):
        with pytest.raises(ValueError, match="destination"):
            import_context.import_by_title("web", "x", "email")

    def test_agent_requires_target_and_deliver(self):
        with pytest.raises(ValueError, match="target_agent"):
            import_context.import_by_title("web", "x", "agent")
        with pytest.raises(ValueError, match="deliver"):
            import_context.import_by_title("web", "x", "agent", target_agent="s1")

    def test_panel_returns_the_rendered_markdown(self, monkeypatch):
        _install_fake_run(monkeypatch, md=_MD)
        out = import_context.import_by_title("web", "Linting", "panel")
        assert out["destination"] == "panel"
        assert out["markdown"] == _MD
        assert out["title"] == "Linting explained simply"
        assert out["external_id"] == _EXTERNAL_ID

    def test_agent_delivers_attributed_markdown_via_callback(self, monkeypatch):
        _install_fake_run(monkeypatch, md=_MD)
        delivered = []

        def deliver(agent_id, text):
            delivered.append((agent_id, text))
            return {"status": "queued", "position": 0}

        out = import_context.import_by_title("web", "Linting", "agent",
                                             target_agent="s1", deliver=deliver)
        assert out["destination"] == "agent" and out["target_agent"] == "s1"
        assert out["delivery"] == {"status": "queued", "position": 0}
        (agent_id, text), = delivered
        assert agent_id == "s1"
        # The attributed header frames the export; the export rides verbatim.
        assert text.startswith("[Imported external Claude context — "
                               '"Linting explained simply" from claude.ai (web)')
        assert _MD in text

    def test_library_writes_doc_with_provenance(self, monkeypatch, tmp_path):
        _install_fake_run(monkeypatch, md=_MD)
        cwd = _proj(tmp_path)
        out = import_context.import_by_title("web", "Linting", "library", cwd=cwd)
        assert out["destination"] == "library"
        path = Path(out["path"])
        assert path.is_file()
        assert path.parent == Path(cwd) / ".awl-cc-dash" / "docs"
        assert path.read_text(encoding="utf-8") == _MD
        # §8.5 provenance in the sidecar: who imported it + the external id.
        prov = library.doc_provenance(path)
        assert prov["created_by"] == "import:web"
        assert prov["session"] == _EXTERNAL_ID
        assert out["provenance"]["created_by"] == "import:web"

    def test_library_reimport_disambiguates_never_clobbers(self, monkeypatch, tmp_path):
        _install_fake_run(monkeypatch, md=_MD)
        cwd = _proj(tmp_path)
        first = import_context.import_by_title("web", "Linting", "library", cwd=cwd)
        second = import_context.import_by_title("web", "Linting", "library", cwd=cwd)
        assert Path(first["path"]).name == f"{_EXPORT_BASENAME}.md"
        assert Path(second["path"]).name == f"{_EXPORT_BASENAME}-2.md"
        assert Path(first["path"]).is_file() and Path(second["path"]).is_file()

    def test_library_without_project_home_is_a_request_error(self, monkeypatch):
        # And it fails BEFORE the network-bound fetch — a request that can
        # never land must not cost an extractor run first.
        calls = []
        _install_fake_run(monkeypatch, md=_MD, calls=calls)
        with pytest.raises(ValueError, match="cwd|project"):
            import_context.import_by_title("web", "Linting", "library", cwd=None)
        assert calls == []


# ---------------------------------------------------------------------------
# Endpoints — GET/POST /import/external
# ---------------------------------------------------------------------------

class TestEndpoints:
    def test_get_lists_sessions(self, monkeypatch):
        rows = [{"source": "web", "id": "u1", "title": "T",
                 "updated_at": None, "model": None}]
        monkeypatch.setattr(import_context, "list_external", lambda source: rows)
        out = asyncio.run(main.list_import_external(source="web"))
        assert out == {"source": "web", "sessions": rows}

    def test_get_maps_source_unavailable_to_400(self, monkeypatch):
        def boom(source):
            raise import_context.SourceUnavailableError("needs session_key.txt")
        monkeypatch.setattr(import_context, "list_external", boom)
        with pytest.raises(HTTPException) as e:
            asyncio.run(main.list_import_external(source="web"))
        assert e.value.status_code == 400
        assert "session_key.txt" in e.value.detail

    def test_get_maps_timeout_to_504(self, monkeypatch):
        def slow(source):
            raise import_context.ExtractorTimeoutError("did not finish within 120s")
        monkeypatch.setattr(import_context, "list_external", slow)
        with pytest.raises(HTTPException) as e:
            asyncio.run(main.list_import_external(source="web"))
        assert e.value.status_code == 504

    def test_post_agent_enqueues_on_the_prompt_queue(self, monkeypatch):
        _install_fake_run(monkeypatch, md=_MD)
        s = _session("s1", status="running")  # busy -> stays observable in queue
        req = main.ImportExternalRequest(source="web", title="Linting",
                                         destination="agent", target_agent="s1")
        out = asyncio.run(main.import_external(req))
        assert out["destination"] == "agent" and out["target_agent"] == "s1"
        assert out["delivery"]["status"] == "queued"
        # §7.3 conventions: queue disposition, operator-attributed, addressed
        # to the target — enqueued (never dropped) while the agent is busy.
        (entry,) = list(s.prompt_queue)
        assert entry["disposition"] == "queue"
        assert entry["source"] == "user" and entry["recipients"] == ["s1"]
        assert _MD in entry["prompt"]
        assert entry["prompt"].startswith("[Imported external Claude context")

    def test_post_agent_idle_target_flushes_immediately_and_nudges(self, monkeypatch):
        # An IDLE target takes the import NOW: the endpoint's post-import
        # _flush_queue drives driver.send with the attributed prompt (and the
        # §11 #34 nudge snaps the poll cadence) — pins the claim so a refactor
        # dropping the flush cannot pass silently.
        _install_fake_run(monkeypatch, md=_MD)
        s = _session("s1", status="idle")
        sent, nudged = [], []

        class Drv:
            name = "fake"

            async def send(self, prompt):
                sent.append(prompt)

            def nudge(self):
                nudged.append(True)

        s.driver = Drv()
        req = main.ImportExternalRequest(source="web", title="Linting",
                                         destination="agent", target_agent="s1")
        out = asyncio.run(main.import_external(req))
        assert out["delivery"]["status"] == "queued"
        (prompt,) = sent
        assert prompt.startswith("[Imported external Claude context")
        assert _MD in prompt
        assert not s.prompt_queue  # flushed, not parked
        assert s.status == "running"  # the flush started the turn
        assert nudged  # §11 #34: inbound prompt activity tightens the poll

    def test_post_agent_deleted_mid_fetch_is_409_never_a_silent_drop(self, monkeypatch):
        # TOCTOU: the target passes the pre-fetch roster check, then is
        # hard-deleted while the extractor runs. Delivery must re-check
        # liveness — honest 409, nothing enqueued onto the orphaned
        # SessionState, no "queued" success for a dropped import.
        s = _session("s1", status="idle")

        def run(source, args, timeout_s=None):
            main.sessions.clear()  # the operator deletes s1 mid-fetch
            out = Path(args[args.index("--out") + 1])
            out.mkdir(parents=True, exist_ok=True)
            (out / f"{_EXPORT_BASENAME}.md").write_text(_MD, encoding="utf-8")
            return _proc(0, "", "")

        monkeypatch.setattr(import_context, "_run", run)
        req = main.ImportExternalRequest(source="web", title="Linting",
                                         destination="agent", target_agent="s1")
        with pytest.raises(HTTPException) as e:
            asyncio.run(main.import_external(req))
        assert e.value.status_code == 409
        assert "closed while the import" in e.value.detail
        assert not s.prompt_queue  # never enqueued onto the orphan

    def test_post_agent_unknown_target_is_404_before_any_fetch(self, monkeypatch):
        calls = []
        _install_fake_run(monkeypatch, md=_MD, calls=calls)
        req = main.ImportExternalRequest(source="web", title="Linting",
                                         destination="agent", target_agent="ghost")
        with pytest.raises(HTTPException) as e:
            asyncio.run(main.import_external(req))
        assert e.value.status_code == 404
        assert calls == []  # validated before the network-bound fetch

    def test_post_agent_missing_target_is_400(self):
        req = main.ImportExternalRequest(source="web", title="Linting",
                                         destination="agent")
        with pytest.raises(HTTPException) as e:
            asyncio.run(main.import_external(req))
        assert e.value.status_code == 400

    def test_post_unknown_source_and_destination_are_400(self):
        req = main.ImportExternalRequest(source="codex", title="T",
                                         destination="panel")
        with pytest.raises(HTTPException) as e:
            asyncio.run(main.import_external(req))
        assert e.value.status_code == 400
        req = main.ImportExternalRequest(source="web", title="T",
                                         destination="email")
        with pytest.raises(HTTPException) as e:
            asyncio.run(main.import_external(req))
        assert e.value.status_code == 400

    def test_post_panel_returns_markdown(self, monkeypatch):
        _install_fake_run(monkeypatch, md=_MD)
        req = main.ImportExternalRequest(source="web", title="Linting",
                                         destination="panel")
        out = asyncio.run(main.import_external(req))
        assert out["markdown"] == _MD

    def test_post_library_writes_doc(self, monkeypatch, tmp_path):
        _install_fake_run(monkeypatch, md=_MD)
        cwd = _proj(tmp_path)
        req = main.ImportExternalRequest(source="web", title="Linting",
                                         destination="library", cwd=cwd)
        out = asyncio.run(main.import_external(req))
        assert Path(out["path"]).is_file()
        assert library.doc_provenance(out["path"])["created_by"] == "import:web"

    def test_post_library_bad_cwd_is_400_before_any_fetch(self, monkeypatch, tmp_path):
        # The library prerequisite (a cwd under an existing project) is checked
        # BEFORE the network-bound fetch, with a message worded for a library
        # import — both for a missing cwd and for a nonexistent path.
        calls = []
        _install_fake_run(monkeypatch, md=_MD, calls=calls)
        for cwd in (None, str(tmp_path / "does-not-exist")):
            req = main.ImportExternalRequest(source="web", title="Linting",
                                             destination="library", cwd=cwd)
            with pytest.raises(HTTPException) as e:
                asyncio.run(main.import_external(req))
            assert e.value.status_code == 400
            assert "library" in e.value.detail and "cwd" in e.value.detail
        assert calls == []  # no extractor run was spent on either

    def test_post_maps_missing_key_to_400(self, monkeypatch):
        _install_fake_run(monkeypatch, rc=1, stderr="No sessionKey found.")
        req = main.ImportExternalRequest(source="web", title="Linting",
                                         destination="panel")
        with pytest.raises(HTTPException) as e:
            asyncio.run(main.import_external(req))
        assert e.value.status_code == 400
        assert "session_key.txt" in e.value.detail

    def test_post_maps_no_match_to_404_and_timeout_to_504(self, monkeypatch):
        _install_fake_run(monkeypatch, rc=1,
                          stderr='No conversation title matching "Linting".')
        req = main.ImportExternalRequest(source="web", title="Linting",
                                         destination="panel")
        with pytest.raises(HTTPException) as e:
            asyncio.run(main.import_external(req))
        assert e.value.status_code == 404

        def hang(source, args, timeout_s=None):
            raise import_context.ExtractorTimeoutError("did not finish")
        monkeypatch.setattr(import_context, "_run", hang)
        with pytest.raises(HTTPException) as e:
            asyncio.run(main.import_external(req))
        assert e.value.status_code == 504
