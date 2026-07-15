"""Hermetic unit tests — the STAGE-3 readout surfaces (§11 #30 / #31 / #32).

The decided contracts this file encodes:

  * **#30 — `/context` breakdown + compaction history (§7.18).**
    ``bridge/transcript.py``'s ``parse_context_output`` parses the `/context`
    screen (and the markdown table `/context` also records into the JSONL — the
    spike's steadier secondary read-back) into stable per-category keys with
    numeric token/percent values; ``compact_history`` derives count/type/when +
    token deltas from ``compact_boundary`` transcript metadata. The driver's
    ``get_context_breakdown`` is idle-gated (RuntimeError("busy")) and the
    endpoint ``GET /sessions/{id}/context/breakdown`` is ON-DEMAND only —
    409 busy, 400 without the capability, ``fetched_at`` stamped; the JSONL
    floor (``GET /sessions/{id}/context``) stays untouched.

  * **#31 — per-turn statusLine capture (§7.18 source 2).** Every bridge
    agent's materialized settings gain a ``statusLine`` command appending each
    render's JSON payload to the per-agent launch-config dir
    (``~/.awl-cc-dash-agents/<name>/statusline.jsonl``); the driver reads the
    LAST line lazily (``get_statusline_snapshot`` — a cheap tail) and
    ``GET /sessions/{id}/context`` gains a ``per_turn`` field. Best-effort
    throughout: absent file / corrupt line → ``per_turn: null``;
    ``AWL_DISABLE_STATUSLINE=1`` opts out fleet-wide.

  * **#32 — per-agent cost (§7.15).** ``parse_cost_output`` parses the `/cost`
    Usage dialog's per-SESSION panel — the specific ``Total cost: $X`` line
    (never any ``$`` on screen) plus the per-model breakdown; the driver's
    ``get_cost`` is an idle-gated console scrape and ``GET /sessions/{id}/cost``
    is ON-DEMAND only (endpoint-only — each read costs a live TUI round-trip,
    so it is deliberately NOT in ``/usage``'s per-agent rows or any poll loop).
    An unparseable panel returns ``usd: null`` honestly, never a fabrication.

No WSL, no tmux, no model — fakes throughout. Live proofs:
``test_context_breakdown_live.py``, ``test_statusline_capture_live.py``,
``test_cost_endpoint_live.py``.
"""

import asyncio
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_SIDECAR = _REPO_ROOT / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))

from fastapi import HTTPException  # noqa: E402

import main  # noqa: E402
from main import SessionState  # noqa: E402
from bridge.transcript import (  # noqa: E402
    compact_history, find_context_markdown, parse_context_output,
)


# -----------------------------------------------------------------------------
# #30 — parse_context_output (screen + markdown-table shapes)
# -----------------------------------------------------------------------------

# Realistic screen shape — the category rows the spike proved parse on 2.1.198.
_CONTEXT_SCREEN = """\
 ▐▛███▜▌   Context Usage
▝▜█████▛▘  claude-sonnet-5 · 37k/967k tokens (4%)
  ▘▘ ▝▝
           ⛁ System prompt: 9.0k tokens (0.9%)
           ⛀ System tools: 21.9k tokens (2.3%)
           ⛁ MCP tools: 1.2k tokens (0.1%)
           ⛀ Memory files: 1,024 tokens (0.1%)
           ⛁ Skills: 2.1k tokens (0.2%)
           ⛀ Messages: 4.4k tokens (0.5%)
           ⛶ Free space: 896.6k (92.7%)
           ⛝ Autocompact buffer: 33.0k tokens (3.4%)
"""

_CONTEXT_MARKDOWN = """\
## Context Usage
| Category | Tokens | Percentage |
|----------|--------|------------|
| System prompt | 9k | 0.9% |
| System tools | 21.9k | 2.3% |
| Messages | 4.4k | 0.5% |
| Free space | 896.6k | 92.7% |
"""


class TestParseContextOutput:
    def test_parses_screen_rows_into_stable_keys(self):
        parsed = parse_context_output(_CONTEXT_SCREEN)
        assert {"system_prompt", "system_tools", "mcp_tools", "memory",
                "skills", "messages", "free_space",
                "autocompact_buffer"} <= set(parsed)

    def test_token_suffixes_and_percent_values(self):
        parsed = parse_context_output(_CONTEXT_SCREEN)
        assert parsed["system_prompt"]["tokens"] == 9_000
        assert parsed["system_prompt"]["percent"] == 0.9
        assert parsed["free_space"]["tokens"] == 896_600
        assert parsed["free_space"]["percent"] == 92.7
        # Comma-grouped plain number (no k suffix).
        assert parsed["memory"]["tokens"] == 1_024

    def test_every_row_carries_a_numeric_value_and_raw_line(self):
        parsed = parse_context_output(_CONTEXT_SCREEN)
        for key, vals in parsed.items():
            assert vals["tokens"] is not None or vals["percent"] is not None, key
            assert vals["raw"].strip()

    def test_parses_the_transcript_markdown_table_too(self):
        # The spike's bonus discovery: `/context` also records a markdown table
        # into the JSONL — same label+numbers-per-line shape, same parser.
        parsed = parse_context_output(_CONTEXT_MARKDOWN)
        assert parsed["system_prompt"]["tokens"] == 9_000
        assert parsed["free_space"]["percent"] == 92.7

    def test_label_without_numbers_is_not_a_row(self):
        parsed = parse_context_output("System prompt: loading...\nMessages: —")
        assert parsed == {}

    def test_empty_and_unrelated_text_parse_to_nothing(self):
        assert parse_context_output("") == {}
        assert parse_context_output(None) == {}
        assert parse_context_output("❯ hello\n─────────") == {}

    def test_first_occurrence_wins_on_duplicates(self):
        text = "Messages: 4.4k tokens (0.5%)\nMessages: 9.9k tokens (1.5%)"
        assert parse_context_output(text)["messages"]["tokens"] == 4_400


class TestFindContextMarkdown:
    def test_finds_newest_context_table_user_entry(self):
        entries = [
            {"type": "user", "message": {"content": "hello"}},
            {"type": "user", "message": {"content": _CONTEXT_MARKDOWN}},
            {"type": "assistant", "message": {"content": []}},
        ]
        assert find_context_markdown(entries) == _CONTEXT_MARKDOWN

    def test_absent_returns_none(self):
        assert find_context_markdown([
            {"type": "user", "message": {"content": "no table here"}},
        ]) is None
        assert find_context_markdown([]) is None


# -----------------------------------------------------------------------------
# #30 — compact_history (compact_boundary metadata)
# -----------------------------------------------------------------------------

def _boundary(when="2026-07-14T12:00:00Z", trigger="manual", pre=45_000,
              post=9_000, dur=15_000):
    # The exact live-proven shape (test_context_compact_live Lever B).
    return {"type": "system", "subtype": "compact_boundary",
            "content": "Conversation compacted", "timestamp": when,
            "compactMetadata": {"trigger": trigger, "preTokens": pre,
                                "postTokens": post, "durationMs": dur}}


class TestCompactHistory:
    def test_empty_transcript_has_no_history(self):
        assert compact_history([]) == {"count": 0, "boundaries": []}

    def test_counts_and_shapes_boundaries_in_order(self):
        entries = [
            {"type": "user", "message": {"content": "hi"}},
            _boundary(when="T1", trigger="manual"),
            {"type": "assistant", "message": {"content": []}},
            _boundary(when="T2", trigger="auto", pre=90_000, post=12_000),
        ]
        hist = compact_history(entries)
        assert hist["count"] == 2
        assert [b["when"] for b in hist["boundaries"]] == ["T1", "T2"]
        assert hist["boundaries"][0]["type"] == "manual"
        assert hist["boundaries"][1] == {
            "when": "T2", "type": "auto", "pre_tokens": 90_000,
            "post_tokens": 12_000, "duration_ms": 15_000}

    def test_missing_metadata_yields_none_fields(self):
        entry = {"type": "system", "subtype": "compact_boundary",
                 "timestamp": "T3"}
        hist = compact_history([entry])
        assert hist["count"] == 1
        assert hist["boundaries"][0] == {
            "when": "T3", "type": None, "pre_tokens": None,
            "post_tokens": None, "duration_ms": None}

    def test_other_system_entries_do_not_count(self):
        entries = [
            {"type": "system", "subtype": "other"},
            {"type": "user", "isCompactSummary": True,
             "message": {"content": "summary"}},   # companion entry ≠ boundary
            "not-a-dict",
        ]
        assert compact_history(entries)["count"] == 0


# -----------------------------------------------------------------------------
# Shared endpoint harness — fake drivers registered into main.sessions
# -----------------------------------------------------------------------------

def _session():
    return SessionState(
        session_id="s1", agent_type=None, model=None,
        permission_mode="default", cwd=None, system_prompt=None,
        driver_name="bridge",
    )


def _register(driver):
    s = _session()
    s.driver = driver
    main.sessions["s1"] = s
    return s


class _ReadoutDriver:
    """Fake bridge-shaped driver for the #30/#31/#32 readout endpoints."""

    name = "fake"

    def __init__(self, caps=(), breakdown=None, snapshot=None, cost=None,
                 error=None):
        self._caps = set(caps)
        self._breakdown = breakdown
        self._snapshot = snapshot
        self._cost = cost
        self._error = error

    def supports(self, cap):
        return cap in self._caps

    async def get_context_breakdown(self):
        if self._error:
            raise RuntimeError(self._error)
        return dict(self._breakdown)

    async def get_context_usage(self):
        return {"tokens": 123, "window": 200_000, "percent": 0.06}

    async def get_statusline_snapshot(self):
        if self._error:
            raise RuntimeError(self._error)
        return self._snapshot

    async def get_cost(self):
        if self._error:
            raise RuntimeError(self._error)
        return dict(self._cost)


class TestContextBreakdownEndpoint:
    def teardown_method(self):
        main.sessions.pop("s1", None)

    def test_returns_rows_history_and_fetched_at(self):
        _register(_ReadoutDriver(
            caps={"context_breakdown"},
            breakdown={"rows": [{"key": "system_prompt", "tokens": 9000,
                                 "percent": 0.9, "raw": "System prompt: 9k"}],
                       "compact_history": {"count": 0, "boundaries": []}}))
        out = asyncio.run(main.get_context_breakdown_endpoint("s1"))
        assert out["rows"][0]["key"] == "system_prompt"
        assert out["compact_history"] == {"count": 0, "boundaries": []}
        assert out["fetched_at"]

    def test_busy_maps_to_409(self):
        _register(_ReadoutDriver(caps={"context_breakdown"}, error="busy"))
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.get_context_breakdown_endpoint("s1"))
        assert ei.value.status_code == 409
        assert "busy" in ei.value.detail

    def test_no_capability_is_400(self):
        _register(_ReadoutDriver(caps=set()))
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.get_context_breakdown_endpoint("s1"))
        assert ei.value.status_code == 400

    def test_unknown_session_404(self):
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.get_context_breakdown_endpoint("nope"))
        assert ei.value.status_code == 404


# -----------------------------------------------------------------------------
# #30 — driver idle-gate honesty (scripted fake bridge)
# -----------------------------------------------------------------------------

class TestDriverBreakdownIdleGate:
    def test_busy_screen_raises_busy_without_sending(self, monkeypatch):
        from drivers.bridge import BridgeDriver
        from drivers.base import DriverConfig
        d = BridgeDriver(DriverConfig(), lambda e: None)

        class _BusyBridge:
            def __init__(self):
                self.sent = []

            def _idle_gate(self, name, timeout=5.0):
                return False

            def send(self, name, text):  # pragma: no cover - must not happen
                self.sent.append(text)

        d._bridge = _BusyBridge()
        with pytest.raises(RuntimeError, match="busy"):
            asyncio.run(d.get_context_breakdown())
        assert d._bridge.sent == [], "/context must never be blind-sent mid-turn"


# -----------------------------------------------------------------------------
# #31 — statusLine capture: materialized settings + lazy snapshot read
# -----------------------------------------------------------------------------

def _bridge_driver():
    from drivers.bridge import BridgeDriver
    from drivers.base import DriverConfig
    return BridgeDriver(DriverConfig(), lambda e: None)


class TestStatuslineSettings:
    def test_settings_gain_a_statusline_command(self, monkeypatch):
        monkeypatch.delenv("AWL_DISABLE_STATUSLINE", raising=False)
        d = _bridge_driver()
        settings = d._build_settings()
        sl = settings.get("statusLine")
        assert sl and sl["type"] == "command"
        # The command appends the piped payload to THIS agent's capture file.
        assert f"{d.tmux_name}/statusline.jsonl" in sl["command"]
        assert "cat" in sl["command"] and ">>" in sl["command"]
        # The rendered line is a deliberately inert static marker (it must
        # never look like a spinner/ellipsis to the screen-state classifier).
        assert "echo awl-cc-dash" in sl["command"]
        assert "…" not in sl["command"]

    def test_env_kill_switch_disables_capture(self, monkeypatch):
        monkeypatch.setenv("AWL_DISABLE_STATUSLINE", "1")
        d = _bridge_driver()
        assert d._build_statusline_settings() is None
        assert "statusLine" not in d._build_settings()

    def test_retention_pin_survives_alongside(self, monkeypatch):
        monkeypatch.delenv("AWL_DISABLE_STATUSLINE", raising=False)
        d = _bridge_driver()
        settings = d._build_settings()
        assert settings["cleanupPeriodDays"] == 3650  # §8.6 pin untouched


class _TailBridge:
    def __init__(self, line):
        self._line = line
        self.calls = 0

    def statusline_tail(self, name):
        self.calls += 1
        return self._line


class TestStatuslineSnapshot:
    def test_valid_last_line_parses_to_payload(self):
        d = _bridge_driver()
        d._bridge = _TailBridge(
            '{"context_window": {"context_window_size": 200000, '
            '"used_percentage": 12.5}, "model": {"id": "claude-sonnet-5"}}')
        snap = asyncio.run(d.get_statusline_snapshot())
        assert snap["context_window"]["context_window_size"] == 200000
        assert d._bridge.calls == 1

    def test_absent_file_is_null(self):
        d = _bridge_driver()
        d._bridge = _TailBridge(None)
        assert asyncio.run(d.get_statusline_snapshot()) is None

    def test_torn_or_corrupt_line_is_null(self):
        d = _bridge_driver()
        d._bridge = _TailBridge('{"context_window": {"context_')
        assert asyncio.run(d.get_statusline_snapshot()) is None

    def test_non_object_json_is_null(self):
        d = _bridge_driver()
        d._bridge = _TailBridge('[1, 2, 3]')
        assert asyncio.run(d.get_statusline_snapshot()) is None


class TestContextEndpointPerTurn:
    def teardown_method(self):
        main.sessions.pop("s1", None)

    def test_context_gains_per_turn_payload(self):
        snap = {"context_window": {"context_window_size": 200000}}
        _register(_ReadoutDriver(caps={"context"}, snapshot=snap))
        out = asyncio.run(main.get_context_usage("s1"))
        assert out["tokens"] == 123          # the JSONL floor, untouched
        assert out["per_turn"] == snap       # the freshest per-turn snapshot

    def test_absent_capture_serves_null(self):
        _register(_ReadoutDriver(caps={"context"}, snapshot=None))
        out = asyncio.run(main.get_context_usage("s1"))
        assert out["per_turn"] is None

    def test_driver_without_snapshot_surface_has_no_per_turn(self):
        class _FloorOnly:
            name = "sdkish"

            def supports(self, cap):
                return cap == "context"

            async def get_context_usage(self):
                return {"tokens": 5, "window": 200_000}

        _register(_FloorOnly())
        out = asyncio.run(main.get_context_usage("s1"))
        assert "per_turn" not in out


# -----------------------------------------------------------------------------
# #32 — parse_cost_output (the /cost Usage-dialog per-session panel)
# -----------------------------------------------------------------------------

from bridge.bridge import parse_cost_output  # noqa: E402

# Realistic /cost screen shape — the spike-captured panel (CC 2.1.198).
_COST_SCREEN = """\
 Usage

 Session
    Total cost:            $0.2127
    Total duration (API):  3s
    Total duration (wall): 7s
    Usage by model:
        claude-haiku-4-5:  1.0k input, 25 output, 0 cache read ($0.0012)
        claude-sonnet-5:   4.3k input, 7 output, 33.1k cache write ($0.2116)

 Current session  ██▌ 55% used  ·  Current week  █▌ 11% used

 Esc to close
"""


class TestParseCostOutput:
    def test_parses_session_total_and_per_model(self):
        out = parse_cost_output(_COST_SCREEN)
        assert out["usd"] == 0.2127
        assert out["per_model"] == [0.0012, 0.2116]
        assert "Total cost" in out["raw"]

    def test_zero_dollar_session_is_a_valid_figure(self):
        out = parse_cost_output("Session\n   Total cost:  $0.0000\n")
        assert out["usd"] == 0.0
        assert out["per_model"] == []

    def test_no_total_cost_line_is_an_honest_none(self):
        # Never merely any `$` on screen — an incidental figure must not parse.
        assert parse_cost_output("The file costs $5 to buy.") is None
        assert parse_cost_output("") is None
        assert parse_cost_output(None) is None


# -----------------------------------------------------------------------------
# #32 — driver idle-gate honesty + the on-demand /cost endpoint
# -----------------------------------------------------------------------------

class TestDriverCost:
    def test_busy_screen_raises_busy_without_sending(self):
        d = _bridge_driver()

        class _BusyBridge:
            def __init__(self):
                self.sent = []

            def _idle_gate(self, name, timeout=5.0):
                return False

            def send(self, name, text):  # pragma: no cover - must not happen
                self.sent.append(text)

        d._bridge = _BusyBridge()
        with pytest.raises(RuntimeError, match="busy"):
            asyncio.run(d.get_cost())
        assert d._bridge.sent == [], "/cost must never be blind-sent mid-turn"

    def test_idle_scrape_parses_and_dismisses(self):
        d = _bridge_driver()

        class _CostBridge:
            def __init__(self):
                self.sent = []
                self.keys_sent = []

            def _idle_gate(self, name, timeout=5.0):
                return True

            def send(self, name, text):
                self.sent.append(text)

            def scrollback(self, name, max_lines=150):
                return {"content": _COST_SCREEN}

            def keys(self, name, *keys):
                self.keys_sent.append(keys)

        import drivers.bridge as dbr
        d._bridge = _CostBridge()
        # No real 3s dialog wait in a unit test.
        orig_sleep = dbr.time.sleep
        dbr.time.sleep = lambda s: None
        try:
            out = asyncio.run(d.get_cost())
        finally:
            dbr.time.sleep = orig_sleep
        assert out["usd"] == 0.2127
        assert d._bridge.sent == ["/cost"]
        assert ("Escape",) in d._bridge.keys_sent  # dialog dismissed

    def test_unparseable_screen_returns_null_usd(self):
        d = _bridge_driver()

        class _BlankBridge:
            def _idle_gate(self, name, timeout=5.0):
                return True

            def send(self, name, text):
                pass

            def scrollback(self, name, max_lines=150):
                return {"content": "nothing cost-shaped here"}

            def keys(self, name, *keys):
                pass

        import drivers.bridge as dbr
        d._bridge = _BlankBridge()
        orig_sleep = dbr.time.sleep
        dbr.time.sleep = lambda s: None
        try:
            out = asyncio.run(d.get_cost())
        finally:
            dbr.time.sleep = orig_sleep
        assert out["usd"] is None
        assert out["per_model"] == []
        assert "nothing cost-shaped" in out["raw"]


class TestCostEndpoint:
    def teardown_method(self):
        main.sessions.pop("s1", None)

    def test_returns_cost_with_fetched_at(self):
        _register(_ReadoutDriver(
            caps={"cost"},
            cost={"usd": 0.21, "per_model": [0.01, 0.20], "raw": "Total cost"}))
        out = asyncio.run(main.get_cost_endpoint("s1"))
        assert out["usd"] == 0.21
        assert out["per_model"] == [0.01, 0.20]
        assert out["fetched_at"]

    def test_busy_maps_to_409(self):
        _register(_ReadoutDriver(caps={"cost"}, error="busy"))
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.get_cost_endpoint("s1"))
        assert ei.value.status_code == 409

    def test_no_capability_is_400(self):
        _register(_ReadoutDriver(caps=set()))
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.get_cost_endpoint("s1"))
        assert ei.value.status_code == 400

    def test_unknown_session_404(self):
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.get_cost_endpoint("nope"))
        assert ei.value.status_code == 404
