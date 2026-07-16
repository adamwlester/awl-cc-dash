"""Hermetic unit tests — the readout surfaces (§11 #30 / #31 / #32 / #46).

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

  * **#46 — per-turn settings + summary capture (§7.19/§7.14).** Every
    dashboard-initiated turn yields exactly ONE thin Timeline record at its
    completion — the capture rides the SAME exactly-once gate as the turn
    count (the bridge driver's reply-gated run→idle / the SDK ``result``, both
    consuming ``_was_running`` once), never a parallel turn detector. The
    record joins the settings-at-turn from what's already known at the
    boundary — the statusline capture's model (#31; ``session.model``
    fallback), the run-state arbiter's ``permission_mode`` (§7.4;
    ``session.permission_mode`` fallback), and the session-tracked
    effort/thinking levers (recorded by the set-effort/set-thinking
    endpoints; set-effort is validated + idle-gated because `/effort` has no
    read-back surface) — plus a concise one-line summary: the reply's leading
    line (the #39 preamble lean), first-sentence fallback, sanely truncated
    (``timeline.turn_summary``). Captures are SERIALIZED per session (the
    ``_capture_tail`` chain) with the timestamp stamped at the completion
    point, so stored order is completion order. Persistence is thin per §8.3
    (the settings snapshot is NOT in the transcript): the bridge driver
    appends each record as one JSON line to the per-agent launch-config
    ``turns.jsonl`` (beside ``statusline.jsonl``) and reads it back ordered;
    corrupt lines skip, a failed append keeps the in-memory record AND
    re-appends it in order on the next capture (``_turns_pending``).
    ``GET /sessions/{id}/timeline`` serves the ordered list with ``turn``
    re-minted 1..N in stored order (monotonic across sidecar restarts).

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


# -----------------------------------------------------------------------------
# #46 — turn_summary / settings_string / model_from_snapshot (pure helpers)
# -----------------------------------------------------------------------------

import runstate  # noqa: E402
import timeline  # noqa: E402


class TestTurnSummary:
    def test_leading_line_is_the_summary(self):
        # The #39 preamble lean: agents lead every reply with a one-liner.
        text = "Fixed the poll race.\n\nDetails: the coasted interval missed…"
        assert timeline.turn_summary(text) == "Fixed the poll race."

    def test_leading_blank_lines_and_markdown_markers_are_skipped(self):
        text = "\n\n## Summary line here\nbody"
        assert timeline.turn_summary(text) == "Summary line here"
        assert timeline.turn_summary("- did the thing\n- more") == "did the thing"

    def test_emphasis_is_not_stripped(self):
        # Only marker runs followed by whitespace strip — **bold** stays intact.
        assert timeline.turn_summary("**Done.** All green.") == "**Done.** All green."

    def test_long_line_falls_back_to_first_sentence(self):
        first = "The rework landed cleanly across all three drivers."
        text = first + " " + ("Then a lot of trailing detail. " * 20)
        assert timeline.turn_summary(text) == first

    def test_long_unbroken_line_truncates_with_ellipsis(self):
        text = "x" * 400  # no sentence boundary at all
        out = timeline.turn_summary(text)
        assert out.endswith("…")
        assert len(out) <= timeline.SUMMARY_MAX

    def test_empty_and_none_are_an_honest_none(self):
        assert timeline.turn_summary(None) is None
        assert timeline.turn_summary("") is None
        assert timeline.turn_summary("   \n \n") is None

    def test_version_numbers_are_not_sentence_boundaries(self):
        # "[.!?]" only counts followed by whitespace, so v2.1.191 stays whole.
        first = "Gated on v2.1.191 as decided."
        text = first + " " + ("More detail follows here. " * 20)
        assert timeline.turn_summary(text) == first


class TestSettingsString:
    def test_full_join(self):
        out = timeline.settings_string(model="claude-sonnet-5", mode="default",
                                       effort="high", thinking=True)
        assert out == "claude-sonnet-5 · default · effort high · thinking on"

    def test_unknown_parts_are_omitted_not_fabricated(self):
        assert timeline.settings_string(model="sonnet") == "sonnet"
        assert timeline.settings_string() == ""

    def test_thinking_is_tristate(self):
        # None = unknown (omitted); False = known-off (shown).
        assert "thinking" not in timeline.settings_string(model="m")
        assert timeline.settings_string(thinking=False) == "thinking off"


class TestModelFromSnapshot:
    def test_prefers_the_payload_model_id(self):
        snap = {"model": {"id": "claude-sonnet-5", "display_name": "Sonnet"}}
        assert timeline.model_from_snapshot(snap) == "claude-sonnet-5"

    def test_display_name_and_plain_string_fallbacks(self):
        assert timeline.model_from_snapshot(
            {"model": {"display_name": "Sonnet"}}) == "Sonnet"
        assert timeline.model_from_snapshot({"model": "opus"}) == "opus"

    def test_absent_or_unshaped_is_none(self):
        assert timeline.model_from_snapshot(None) is None
        assert timeline.model_from_snapshot({}) is None
        assert timeline.model_from_snapshot({"model": 42}) is None


# -----------------------------------------------------------------------------
# #46 — the capture join (main._capture_turn_record) + exactly-once scheduling
# -----------------------------------------------------------------------------

class _TimelineDriver:
    """Fake bridge-shaped driver for the #46 capture + timeline surfaces."""

    name = "fakebridge"

    def __init__(self, snapshot=None, records=None, fail_append=False,
                 caps=("timeline",)):
        self._snapshot = snapshot
        self._records = list(records or [])
        self._fail_append = fail_append
        self._caps = set(caps)
        self.appended: list[dict] = []

    def supports(self, cap):
        return cap in self._caps

    async def get_statusline_snapshot(self):
        return self._snapshot

    async def append_turn_record(self, record):
        if self._fail_append:
            raise RuntimeError("wsl gone")
        self.appended.append(record)

    async def get_timeline(self):
        return list(self._records)


_TURN_EVENTS = [
    {"type": "status_change", "status": "running"},
    {"type": "assistant",
     "content": [{"type": "text",
                  "text": "Fixed the poll race.\n\nLong detail body…"}]},
]


class _SlowSnapDriver(_TimelineDriver):
    """First statusline snapshot stalls (a slow WSL round trip); later ones
    return instantly — the serialization hazard's exact shape."""

    def __init__(self, delay=0.15):
        super().__init__(snapshot={"model": {"id": "m1"}})
        self._delay = delay
        self._calls = 0

    async def get_statusline_snapshot(self):
        self._calls += 1
        if self._calls == 1:
            await asyncio.sleep(self._delay)
        return self._snapshot


class _FlakyPersistDriver(_TimelineDriver):
    """append_turn_record fails the first N times, then succeeds."""

    def __init__(self, failures=1):
        super().__init__()
        self._failures = failures

    async def append_turn_record(self, record):
        if self._failures > 0:
            self._failures -= 1
            raise RuntimeError("wsl hiccup")
        self.appended.append(record)


class TestTurnCaptureRecord:
    def teardown_method(self):
        main.sessions.pop("s1", None)
        runstate.reset()

    def test_joins_statusline_model_arbiter_mode_and_session_levers(self):
        runstate.reset()
        drv = _TimelineDriver(snapshot={"model": {"id": "claude-sonnet-5"}})
        s = _register(drv)
        s.model = "sonnet"                 # launch fallback — loses to snapshot
        s.permission_mode = "default"      # fallback — loses to the hook push
        s.last_effort = "high"
        s.last_thinking = True
        s.events = list(_TURN_EVENTS)
        s._turn_start_idx = 1
        runstate.ingest("s1", "UserPromptSubmit",
                        {"permission_mode": "acceptEdits"})
        asyncio.run(main._capture_turn_record(s, 2, 1))
        assert len(s.turns) == 1
        rec = s.turns[0]
        assert rec["turn"] == 2
        assert rec["model"] == "claude-sonnet-5"
        assert rec["mode"] == "acceptEdits"
        assert rec["effort"] == "high" and rec["thinking"] is True
        assert rec["settings"] == \
            "claude-sonnet-5 · acceptEdits · effort high · thinking on"
        assert rec["summary"] == "Fixed the poll race."
        assert rec["timestamp"]
        # Persisted thin through the driver surface (turns.jsonl side).
        assert drv.appended == [rec]

    def test_fallbacks_when_nothing_pushed_or_captured(self):
        runstate.reset()
        drv = _TimelineDriver(snapshot=None)
        s = _register(drv)
        s.model = "sonnet"
        s.permission_mode = "plan"
        s.events = []                      # no reply text at all
        asyncio.run(main._capture_turn_record(s, 1, 0))
        rec = s.turns[0]
        assert rec["model"] == "sonnet"    # session launch model
        assert rec["mode"] == "plan"       # session mode
        assert rec["effort"] is None and rec["thinking"] is None
        assert rec["settings"] == "sonnet · plan"
        assert rec["summary"] is None      # honest miss, never fabricated

    def test_persist_failure_keeps_the_in_memory_record(self):
        drv = _TimelineDriver(fail_append=True)
        s = _register(drv)
        s.events = list(_TURN_EVENTS)
        s._turn_start_idx = 1
        asyncio.run(main._capture_turn_record(s, 1, 1))  # must not raise
        assert len(s.turns) == 1
        assert s.turns[0]["summary"] == "Fixed the poll race."

    def test_failed_persist_is_retried_in_order_on_the_next_capture(self):
        # A transient WSL hiccup on turn k's append must not permanently hole
        # turns.jsonl (the endpoint serves the file when non-empty, so a
        # dropped line would be unservable for the agent's life): the record
        # queues on `_turns_pending` and rides AHEAD of turn k+1's append, so
        # the file heals in completion order.
        drv = _FlakyPersistDriver(failures=1)
        s = _register(drv)
        s.events = list(_TURN_EVENTS)
        s._turn_start_idx = 1
        asyncio.run(main._capture_turn_record(s, 1, 1, "t1"))
        assert len(s.turns) == 1 and drv.appended == []  # queued, not lost
        assert [r["turn"] for r in s._turns_pending] == [1]
        asyncio.run(main._capture_turn_record(s, 2, 1, "t2"))
        assert [r["turn"] for r in drv.appended] == [1, 2]  # healed, in order
        assert [r["timestamp"] for r in drv.appended] == ["t1", "t2"]
        assert s._turns_pending == []

    def test_driver_without_capture_surfaces_still_records_in_memory(self):
        # An SDK-shaped driver: no statusline snapshot, no persist surface.
        class _Plain:
            name = "sdkish"

            def supports(self, cap):
                return False

        s = _register(_Plain())
        s.model = "opus"
        s.events = list(_TURN_EVENTS)
        s._turn_start_idx = 1
        asyncio.run(main._capture_turn_record(s, 1, 1))
        assert s.turns[0]["model"] == "opus"
        assert s.turns[0]["summary"] == "Fixed the poll race."


class TestTurnCaptureScheduling:
    def teardown_method(self):
        main.sessions.pop("s1", None)
        runstate.reset()

    def test_no_running_loop_skips_capture_silently(self):
        # handle_event is called synchronously in hermetic paths (and by the
        # poll-bundle end-to-end test) — the capture must be a silent no-op
        # there, never an exception, and never load-bearing for the turn.
        import inbox
        inbox.reset()
        try:
            s = _register(_TimelineDriver())
            s.status = "running"
            s._was_running = True
            s.handle_event({"type": "status_change", "status": "idle",
                            "timestamp": "t"})
            assert s.turn_count == 1       # the turn still completes
            assert s.turns == []           # capture skipped without a loop
        finally:
            inbox.reset()

    def test_completion_captures_exactly_once_and_stray_idle_adds_nothing(self):
        # End-to-end on a live loop: the exactly-once completion idle (as the
        # bridge driver emits it) yields ONE record; a stray idle re-read adds
        # none — the capture rides the same _was_running gate as the turn count.
        import inbox
        inbox.reset()

        async def flow():
            drv = _TimelineDriver(snapshot={"model": {"id": "m1"}})
            s = _register(drv)
            s.events = list(_TURN_EVENTS)
            s._turn_start_idx = 1
            s.status = "running"
            s._was_running = True
            s.handle_event({"type": "status_change", "status": "idle",
                            "timestamp": "t"})
            for _ in range(100):
                if s.turns:
                    break
                await asyncio.sleep(0.01)
            assert len(s.turns) == 1
            assert s.turns[0]["summary"] == "Fixed the poll race."
            assert drv.appended == [s.turns[0]]
            # Stray idle: no _was_running left to consume — no second record.
            s.handle_event({"type": "status_change", "status": "idle",
                            "timestamp": "t2"})
            await asyncio.sleep(0.05)
            assert len(s.turns) == 1

        try:
            asyncio.run(flow())
        finally:
            inbox.reset()

    def test_sdk_result_completion_captures_exactly_once(self):
        # The SDK driver's turns end on a `result` event (never a was-running
        # idle status_change) — the capture must ride THAT completion point
        # too, and exactly once: a stray re-emitted result adds nothing.
        import inbox
        inbox.reset()

        async def flow():
            drv = _TimelineDriver(snapshot={"model": {"id": "m1"}})
            s = _register(drv)
            s.events = list(_TURN_EVENTS)
            s._turn_start_idx = 1
            s.status = "running"
            s._was_running = True
            s.handle_event({"type": "result", "data": {"num_turns": 3},
                            "timestamp": "t"})
            for _ in range(100):
                if s.turns:
                    break
                await asyncio.sleep(0.01)
            assert len(s.turns) == 1
            assert s.turns[0]["summary"] == "Fixed the poll race."
            assert drv.appended == [s.turns[0]]
            # Stray result: no _was_running left to consume — no second record.
            s.handle_event({"type": "result", "data": {}, "timestamp": "t2"})
            await asyncio.sleep(0.05)
            assert len(s.turns) == 1

        try:
            asyncio.run(flow())
        finally:
            inbox.reset()

    def test_captures_are_serialized_per_session(self):
        # Turn 1's capture stalls on its statusline snapshot (a slow WSL round
        # trip); turn 2 completes fast behind it. The `_capture_tail` chain
        # must keep stored order == completion order — stored order IS the
        # endpoint's re-minted ordinal order, in both the mirror and the
        # persisted file.
        import inbox
        inbox.reset()

        async def flow():
            drv = _SlowSnapDriver()
            s = _register(drv)
            s.events = [
                {"type": "status_change", "status": "running"},
                {"type": "assistant",
                 "content": [{"type": "text", "text": "First turn done."}]},
            ]
            s._turn_start_idx = 1
            s.status = "running"
            s._was_running = True
            s.handle_event({"type": "status_change", "status": "idle",
                            "timestamp": "t1"})
            # The queued follow-up turn completes while capture 1 is stalled.
            s.events.append({"type": "status_change", "status": "running"})
            start2 = len(s.events)
            s.events.append({"type": "assistant",
                             "content": [{"type": "text",
                                          "text": "Second turn done."}]})
            s._turn_start_idx = start2
            s.status = "running"
            s._was_running = True
            s.handle_event({"type": "status_change", "status": "idle",
                            "timestamp": "t2"})
            for _ in range(300):
                if len(s.turns) == 2:
                    break
                await asyncio.sleep(0.01)
            assert [r["summary"] for r in s.turns] == \
                ["First turn done.", "Second turn done."]
            assert [r["summary"] for r in drv.appended] == \
                ["First turn done.", "Second turn done."]
            assert [r["turn"] for r in s.turns] == [1, 2]

        try:
            asyncio.run(flow())
        finally:
            inbox.reset()


# -----------------------------------------------------------------------------
# #46 — the thin persist surface (driver turns.jsonl append/read + TmuxBridge)
# -----------------------------------------------------------------------------

class _TurnsBridge:
    def __init__(self, text="", boom=False):
        self._text = text
        self._boom = boom
        self.appended: list[tuple] = []

    def turns_append(self, name, line):
        self.appended.append((name, line))

    def turns_read(self, name):
        if self._boom:
            raise RuntimeError("wsl gone")
        return self._text


class TestDriverTurnsPersistence:
    def test_append_writes_one_compact_json_line(self):
        import json as _json
        d = _bridge_driver()
        d._bridge = _TurnsBridge()
        rec = {"turn": 1, "settings": "m · default", "summary": "Did it."}
        asyncio.run(d.append_turn_record(rec))
        assert len(d._bridge.appended) == 1
        name, line = d._bridge.appended[0]
        assert name == d.tmux_name
        assert "\n" not in line            # ONE line per record
        assert _json.loads(line) == rec

    def test_get_timeline_parses_ordered_and_skips_corrupt_lines(self):
        text = ('{"turn":1,"summary":"a"}\n'
                '\n'
                '{"turn":2,"summ'          # torn tail-line
                '\n[1,2,3]\n'              # non-object JSON
                '{"turn":3,"summary":"c"}')
        d = _bridge_driver()
        d._bridge = _TurnsBridge(text=text)
        out = asyncio.run(d.get_timeline())
        assert [r["summary"] for r in out] == ["a", "c"]

    def test_missing_file_and_failed_read_are_empty_lists(self):
        d = _bridge_driver()
        d._bridge = _TurnsBridge(text="")
        assert asyncio.run(d.get_timeline()) == []
        d._bridge = _TurnsBridge(boom=True)
        assert asyncio.run(d.get_timeline()) == []


class TestTmuxBridgeTurnsFile:
    def test_append_pipes_the_line_via_stdin_beside_statusline(self, monkeypatch):
        # stdin (`cat >>`) so a long record never hits the ~32 KB cmdline cap;
        # the path is the launch-config dir's turns.jsonl (beside statusline.jsonl).
        from bridge import TmuxBridge
        b = TmuxBridge()
        calls = []

        def fake_run(cmd, timeout=30, stdin_data=None):
            calls.append((cmd, stdin_data))
            return ""

        monkeypatch.setattr(b, "_run", fake_run)
        b.turns_append("agent-x", '{"turn":1}')
        cmd, stdin = calls[0]
        assert "agent-x/turns.jsonl" in cmd
        assert "cat >>" in cmd and "mkdir -p" in cmd
        assert stdin == '{"turn":1}\n'     # exactly one trailing newline

    def test_read_returns_text_and_missing_file_is_empty(self, monkeypatch):
        from bridge import TmuxBridge
        from bridge.bridge import TmuxBridgeError
        b = TmuxBridge()
        monkeypatch.setattr(
            b, "_run", lambda cmd, timeout=30, stdin_data=None: '{"turn":1}')
        assert b.turns_read("agent-x") == '{"turn":1}'

        def boom(cmd, timeout=30, stdin_data=None):
            raise TmuxBridgeError("no wsl")

        monkeypatch.setattr(b, "_run", boom)
        assert b.turns_read("agent-x") == ""


# -----------------------------------------------------------------------------
# #46 — GET /sessions/{id}/timeline + the effort/thinking lever tracking
# -----------------------------------------------------------------------------

class TestTimelineEndpoint:
    def teardown_method(self):
        main.sessions.pop("s1", None)

    def test_driver_backed_rows_reminted_in_stored_order(self):
        # `turn` is re-minted 1..N in stored order: the persisted file survives
        # a sidecar restart while the session-local count resets, so the stored
        # per-run numbers may repeat — the read surface stays monotonic.
        records = [
            {"turn": 7, "timestamp": "t1", "settings": "m · default",
             "summary": "first"},
            {"turn": 1, "timestamp": "t2", "settings": "m · plan",
             "summary": "second"},
        ]
        _register(_TimelineDriver(records=records))
        out = asyncio.run(main.get_timeline_endpoint("s1"))
        assert out["count"] == 2
        assert [r["turn"] for r in out["turns"]] == [1, 2]
        assert [r["summary"] for r in out["turns"]] == ["first", "second"]
        assert out["turns"][0]["settings"] == "m · default"

    def test_driver_without_timeline_serves_the_in_memory_mirror(self):
        s = _register(_ReadoutDriver(caps=set()))
        s.turns = [{"turn": 1, "timestamp": "t", "settings": "",
                    "summary": "mirrored"}]
        out = asyncio.run(main.get_timeline_endpoint("s1"))
        assert out["count"] == 1
        assert out["turns"][0]["summary"] == "mirrored"

    def test_empty_driver_read_falls_back_to_the_mirror(self):
        s = _register(_TimelineDriver(records=[]))
        s.turns = [{"turn": 1, "timestamp": "t", "settings": "",
                    "summary": "mem"}]
        out = asyncio.run(main.get_timeline_endpoint("s1"))
        assert [r["summary"] for r in out["turns"]] == ["mem"]

    def test_no_turns_yet_is_an_empty_list_never_an_error(self):
        _register(_TimelineDriver(records=[]))
        out = asyncio.run(main.get_timeline_endpoint("s1"))
        assert out == {"session_id": "s1", "count": 0, "turns": []}

    def test_unknown_session_404(self):
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.get_timeline_endpoint("nope"))
        assert ei.value.status_code == 404


class _EffortLever:
    """Fake driver exposing only set_effort; records whether it was driven."""

    name = "fake"

    def __init__(self):
        self.sent: list[str] = []

    def supports(self, cap):
        return cap == "set_effort"

    async def set_effort(self, effort):
        self.sent.append(effort)


class TestLeverTracking:
    """set-effort / set-thinking record the last-known lever on the session —
    the #46 settings join's only source for them (neither the arbiter nor the
    statusline payload reports effort/thinking). `/effort` has NO read-back
    surface (the bridge lever just types the slash command), so set-effort is
    validated + idle-gated at the endpoint: what gets recorded was a known
    level sent at an idle boundary, never an arbitrary string or a mid-run
    send the TUI would queue instead of apply."""

    def teardown_method(self):
        main.sessions.pop("s1", None)

    def test_set_effort_records_the_lever(self):
        drv = _EffortLever()
        s = _register(drv)
        asyncio.run(main.set_effort("s1", main.SetEffortRequest(effort="high")))
        assert s.last_effort == "high"
        assert drv.sent == ["high"]

    def test_set_effort_mid_run_is_409_busy_and_not_recorded(self):
        # Typed into a generating TUI, `/effort` lands as queued composer
        # input, not an applied setting — recording it would fabricate the
        # per-turn settings for the in-flight turn.
        drv = _EffortLever()
        s = _register(drv)
        s.status = "running"
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.set_effort(
                "s1", main.SetEffortRequest(effort="high")))
        assert ei.value.status_code == 409
        assert s.last_effort is None
        assert drv.sent == []              # never typed into the busy TUI

    def test_set_effort_unknown_level_is_400_and_not_recorded(self):
        drv = _EffortLever()
        s = _register(drv)
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.set_effort(
                "s1", main.SetEffortRequest(effort="bananas")))
        assert ei.value.status_code == 400
        assert s.last_effort is None
        assert drv.sent == []              # never sent to the TUI

    def test_set_thinking_records_the_read_back_state(self):
        class _Lever:
            name = "fake"

            def supports(self, cap):
                return cap == "set_thinking"

            async def set_thinking(self, on):
                return False               # read-back disagrees with the ask

        s = _register(_Lever())
        out = asyncio.run(
            main.set_thinking("s1", main.SetThinkingRequest(on=True)))
        assert out["thinking"] is False    # read-back, never an echo
        assert s.last_thinking is False
