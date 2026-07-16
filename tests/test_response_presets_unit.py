"""Hermetic unit tests for per-agent response-format presets (§7.14, §11 #39).

Decided contract (ARCHITECTURE §7.14, §11 #39; build plan
``dev/notes/2026-07-15-stage5-build-plan.md`` #39):

A small preset menu of reply formats (including the operator's TL;DR-table +
emoji-status house style), chosen ONCE per agent. The choice REACHES and PERSISTS
to the agent (``state/agents.json``); a per-message override is deferred. The
mechanism: the chosen preset's instruction is APPENDED to the agent's system
prompt at launch (``claude --append-system-prompt``, via the bridge driver), so
every reply follows the format.

What this file pins (all pure Python — no WSL/tmux/network):
  * ``response_presets`` catalog — the menu shape (id/label/description), the
    ``default`` no-op, the operator's ``tldr_table`` style present, and
    ``instruction_for`` returning ``""`` for default/unknown/None (a missing
    preset injects NOTHING) and the real text for a named preset.
  * ``TmuxBridge.create()`` — a ``--append-system-prompt <instruction>`` token
    rides the launched tmux command when (and only when) an instruction is
    passed. Scripted-fake captured, never executed.
  * ``BridgeDriver._create_session()`` — resolves the instruction from
    ``config.response_preset`` and forwards it to ``create()``; the default /
    unset preset forwards ``None`` (nothing appended).
  * ``GET /presets/response`` / ``GET|POST /sessions/{id}/response-preset`` — the
    catalog, and set→persist→get round-trip: the choice lands on the session, the
    driver config, and the roster record (state/agents.json), with a 400 on an
    unknown id and a 404 on an unknown session.
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

import response_presets  # noqa: E402
from bridge.bridge import TmuxBridge  # noqa: E402
from drivers.bridge import BridgeDriver  # noqa: E402
from drivers.base import DriverConfig  # noqa: E402


# ---------------------------------------------------------------------------
# response_presets — the catalog + instruction resolution
# ---------------------------------------------------------------------------

class TestCatalog:
    def test_catalog_rows_have_id_label_description_only(self):
        rows = response_presets.catalog()
        assert isinstance(rows, list) and rows
        for r in rows:
            assert set(r.keys()) == {"id", "label", "description"}
            # The instruction text is NOT leaked into the menu payload.
            assert "instruction" not in r

    def test_default_and_operator_style_present(self):
        ids = {r["id"] for r in response_presets.catalog()}
        assert "default" in ids
        assert "tldr_table" in ids  # the operator's TL;DR-table + emoji style
        assert response_presets.DEFAULT_PRESET == "default"

    def test_default_preset_is_a_noop(self):
        # The default injects NOTHING — the agent keeps its natural style.
        assert response_presets.instruction_for("default") == ""

    def test_tldr_table_instruction_is_the_operator_style(self):
        instr = response_presets.instruction_for("tldr_table")
        assert instr  # non-empty
        low = instr.lower()
        assert "tl;dr" in low
        assert "table" in low
        # The emoji-status half of the house style.
        assert "✅" in instr and "⚠️" in instr

    def test_instruction_for_unknown_and_none_is_empty(self):
        assert response_presets.instruction_for("nope") == ""
        assert response_presets.instruction_for(None) == ""

    def test_is_valid_and_get(self):
        assert response_presets.is_valid("concise") is True
        assert response_presets.is_valid("nope") is False
        assert response_presets.is_valid(None) is False
        assert response_presets.get("nope") is None
        got = response_presets.get("tldr_table")
        assert got and "instruction" in got  # get() DOES carry the text


# ---------------------------------------------------------------------------
# TmuxBridge.create() — the --append-system-prompt token on the launched command.
# Hermetic: _run / _list_raw / _clear_startup_gates scripted-fake captured, never
# executed (mirrors test_git_identity_unit.TestCreateGitEnvPrefix).
# ---------------------------------------------------------------------------

class TestCreateAppendSystemPrompt:
    def _patched_bridge(self, monkeypatch, name):
        b = TmuxBridge()
        captured = {"commands": []}

        def fake_run(cmd, timeout=30, stdin_data=None):
            captured["commands"].append(cmd)
            return ""

        state = {"listed": 0}

        def fake_list_raw():
            state["listed"] += 1
            return {} if state["listed"] == 1 else {name: {"pid": "42"}}

        monkeypatch.setattr(b, "_run", fake_run)
        monkeypatch.setattr(b, "_list_raw", fake_list_raw)
        monkeypatch.setattr(b, "_clear_startup_gates", lambda n, **kw: None)
        monkeypatch.setattr("bridge.bridge.time.sleep", lambda s: None)
        return b, captured

    def _launch_cmd(self, captured):
        cmds = [c for c in captured["commands"] if c.startswith("tmux new-session")]
        assert len(cmds) == 1, f"expected one tmux new-session, got: {cmds}"
        return cmds[0]

    def test_append_flag_present_when_instruction_given(self, monkeypatch):
        b, captured = self._patched_bridge(monkeypatch, "rp")
        b.create("rp", cwd="/tmp/x",
                 append_system_prompt="Lead with a one-line TL;DR.")
        cmd = self._launch_cmd(captured)
        assert "--append-system-prompt" in cmd
        # The instruction text rides the command (shell-quoted; a distinctive
        # substring survives the quoting intact).
        assert "one-line TL;DR" in cmd

    def test_no_append_flag_when_omitted(self, monkeypatch):
        b, captured = self._patched_bridge(monkeypatch, "plain")
        b.create("plain", cwd="/tmp/x")
        cmd = self._launch_cmd(captured)
        assert "--append-system-prompt" not in cmd

    def test_empty_instruction_is_a_noop(self, monkeypatch):
        b, captured = self._patched_bridge(monkeypatch, "empty")
        b.create("empty", cwd="/tmp/x", append_system_prompt="")
        cmd = self._launch_cmd(captured)
        assert "--append-system-prompt" not in cmd


# ---------------------------------------------------------------------------
# BridgeDriver._create_session() — resolves the preset -> append_system_prompt.
# Hermetic: the TmuxBridge.create call is monkeypatch-captured, never executed
# (mirrors test_git_identity_unit.TestCreateSessionForwardsGitIdentity).
# ---------------------------------------------------------------------------

def _driver(**cfg):
    return BridgeDriver(DriverConfig(**cfg), lambda e: None)


class TestCreateSessionForwardsPreset:
    def _capture_create(self, d, monkeypatch):
        seen = {}

        def fake_create(name, **kw):
            seen["name"] = name
            seen.update(kw)
            return {"session_id": "deadbeef"}

        monkeypatch.setattr(d._bridge, "create", fake_create)
        return seen

    def test_named_preset_forwards_its_instruction(self, monkeypatch):
        d = _driver(response_preset="tldr_table")
        seen = self._capture_create(d, monkeypatch)
        d._create_session()
        assert seen["append_system_prompt"] == \
            response_presets.instruction_for("tldr_table")
        assert seen["append_system_prompt"]  # non-empty

    def test_default_preset_forwards_none(self, monkeypatch):
        d = _driver(response_preset="default")
        seen = self._capture_create(d, monkeypatch)
        d._create_session()
        assert seen["append_system_prompt"] is None

    def test_unset_preset_forwards_none(self, monkeypatch):
        d = _driver()  # response_preset=None
        seen = self._capture_create(d, monkeypatch)
        d._create_session()
        assert seen["append_system_prompt"] is None


# ---------------------------------------------------------------------------
# Endpoints — GET catalog, GET/POST per-agent preset (persist to agents.json)
# ---------------------------------------------------------------------------

class _FakeDriver:
    """A stand-in bridge driver carrying just what the set endpoint touches:
    a mutable config (to keep in sync) and a persistable roster record."""

    name = "bridge"

    def __init__(self, config, record):
        self.config = config
        self._record = record


class TestPresetEndpoints:
    @pytest.fixture(autouse=True)
    def _clean(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(tmp_path / "rt"))
        import main
        import runtime_store
        import state_store
        state_store.reset()
        main.sessions.clear()
        self.main = main
        self.runtime_store = runtime_store
        self.tmp_path = tmp_path
        yield
        state_store.reset()
        main.sessions.clear()

    def _seed_agent(self, sid="a1", preset=None):
        main = self.main
        cwd = str(self.tmp_path / "proj")
        Path(cwd).mkdir(parents=True, exist_ok=True)
        session = main.SessionState(
            session_id=sid, agent_type=None, model="m",
            permission_mode="acceptEdits", cwd=cwd, system_prompt=None,
            driver_name="bridge", response_preset=preset,
            identity={"role": "Agent", "number": 1, "name": "goop"})
        config = DriverConfig(cwd=cwd, response_preset=preset)
        record = {"session_id": sid, "tmux_name": "awl-" + sid,
                  "driver": "bridge", "cwd": cwd, "response_preset": preset}
        session.driver = _FakeDriver(config, record)
        main.sessions[sid] = session
        return session, config, record

    def test_catalog_endpoint(self):
        out = asyncio.run(self.main.response_preset_catalog())
        assert out["default"] == "default"
        ids = {r["id"] for r in out["presets"]}
        assert "default" in ids and "tldr_table" in ids

    def test_get_default_preset_is_none(self):
        self._seed_agent("a1", preset=None)
        out = asyncio.run(self.main.get_response_preset("a1"))
        assert out == {"session_id": "a1", "response_preset": None}

    def test_set_persists_to_session_config_and_record(self):
        session, config, record = self._seed_agent("a1", preset=None)
        req = self.main.SetResponsePresetRequest(preset="tldr_table")
        out = asyncio.run(self.main.set_response_preset("a1", req))
        assert out["response_preset"] == "tldr_table"
        # Reaches the session, the driver config, and the roster record...
        assert session.response_preset == "tldr_table"
        assert config.response_preset == "tldr_table"
        assert record["response_preset"] == "tldr_table"
        # ...and persists to state/agents.json (read back via runtime_store).
        persisted = {r["session_id"]: r for r in self.runtime_store.all_records()}
        assert persisted["a1"]["response_preset"] == "tldr_table"
        # A subsequent GET reflects the choice.
        got = asyncio.run(self.main.get_response_preset("a1"))
        assert got["response_preset"] == "tldr_table"

    def test_set_unknown_preset_is_400(self):
        self._seed_agent("a1")
        from fastapi import HTTPException
        req = self.main.SetResponsePresetRequest(preset="bogus")
        with pytest.raises(HTTPException) as ei:
            asyncio.run(self.main.set_response_preset("a1", req))
        assert ei.value.status_code == 400

    def test_set_unknown_session_is_404(self):
        from fastapi import HTTPException
        req = self.main.SetResponsePresetRequest(preset="concise")
        with pytest.raises(HTTPException) as ei:
            asyncio.run(self.main.set_response_preset("ghost", req))
        assert ei.value.status_code == 404

    def test_launch_config_surfaces_preset(self):
        session, _c, _r = self._seed_agent("a1", preset="concise")
        assert session.to_dict()["launch_config"]["response_preset"] == "concise"
