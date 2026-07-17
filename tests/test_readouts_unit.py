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

    The rewind-anchor residual rides the same record (spike-proven facts:
    the JSONL transcript is append-only — a rewind writes NOTHING at rewind
    time, and no engine checkpoint id exists anywhere). Each turn record
    additively carries the turn's TRANSCRIPT ANCHORS — ``prompt_uuid`` (the
    user-prompt JSONL entry uuid) and ``reply_uuid`` (the closing assistant
    entry uuid), lifted at capture from the turn's events (the same
    ``anchor``/``source_kind='t'`` fields the event bus mints deterministic
    ids from; ``timeline.turn_anchors``) — null-safe: an SDK-driven or
    synthesized turn records nulls, never a fabricated anchor. The lift
    honors LIVE bridge ordering: the driver polls the turn's prompt entry in
    BEFORE it emits the boundary's ``running`` flip (and a mid-turn
    permission prompt re-emits ``running``), so when the forward window
    misses the prompt the lift scans BACKWARD, walking through intermediate
    ``running`` flips and stopping at the previous turn's completion; tool
    results (type-"user" transcript entries too), CLI meta lines, and a
    subagent's sidechain entries (both flagged by the driver's
    ``_entry_to_event``) never anchor a turn; and because the screen flips
    idle ~1s before the transcript tail is polled into events (the
    reply-relay's exact lag), the capture SETTLES — re-lifts summary +
    anchors until two consecutive lifts agree, bounded
    (``main._CAPTURE_SETTLE_SECS``/``_ATTEMPTS``; hermetic runs zero the
    sleep, the re-lift logic still runs). Each
    SUCCESSFUL dashboard rewind appends a typed REWIND EVENT record
    (``{"type": "rewind", timestamp, to_prompt_index}``) to the SAME
    ``turns.jsonl`` through the SAME per-session serialization
    (``_capture_tail`` chain + the ``_turns_pending`` in-order drain — a
    rewind record can never land ahead of a turn record still draining), and
    mirrors it into ``session.turns``; a FAILED rewind appends nothing. New
    turn records carry ``"type": "turn"``; any line WITHOUT a type is a turn
    (old files replay identically). The read surface REPLAYS the interleaved
    stream (``timeline.replay_timeline``): ordinals are minted over TURN
    records only (pure-turn files keep today's numbering exactly), a live
    stack pushes each turn and each rewind pops/marks the top
    ``k = to_prompt_index`` ordinals rolled (clamped honestly at the stack
    size — never a crash), so post-rewind turns stay live and chained
    rewinds compose. The response gains per-row ``rolled`` plus top-level
    ``rolled_ranges`` (merged ascending, exclusive-``from``: a row t is
    rolled iff ``from < t <= to``) and ``rewinds``, keeping the
    ``{session_id, count, turns}`` shape otherwise (count = turn rows).
    The read also MERGES records still queued on the transient-persist-
    failure path (``_turns_pending``, snapshotted BEFORE the file read with
    the drained prefix deduped off the file tail) — a rewind event whose
    append hiccuped must still roll its rows, never silently serve un-rolled
    state the renderer's k-from-last arithmetic would act on.
    Manual-terminal rewinds write no event and stay unmarked — the settled
    scope (the Timeline logs dashboard turns); the replay mirrors the
    renderer's k-from-last arithmetic and diverges only if manual TUI turns
    interleave (the pre-existing limit).

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


@pytest.fixture(autouse=True)
def _zero_capture_settle(monkeypatch):
    """Zero the #46 capture's trailing-entry settle SLEEP for hermetic runs —
    the re-lift loop still executes (TestCaptureSettle pins its logic), only
    the between-attempt wait is removed. Returns the live value so the budget
    test can assert it stays a real positive settle."""
    original = main._CAPTURE_SETTLE_SECS
    monkeypatch.setattr(main, "_CAPTURE_SETTLE_SECS", 0)
    return original


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
# #46 — the transcript anchors (build_record fields + the turn_anchors lift)
# -----------------------------------------------------------------------------

class TestBuildRecordAnchors:
    def test_carries_anchor_fields_additively_and_types_new_writes(self):
        rec = timeline.build_record(turn=1, timestamp="t",
                                    prompt_uuid="u-1", reply_uuid="a-9")
        assert rec["prompt_uuid"] == "u-1" and rec["reply_uuid"] == "a-9"
        # New writes are explicitly typed; readers treat typeless as turn.
        assert rec["type"] == "turn"

    def test_defaults_are_null_safe(self):
        rec = timeline.build_record(turn=1, timestamp="t")
        assert rec["prompt_uuid"] is None and rec["reply_uuid"] is None


class TestTurnAnchors:
    # Live bridge ordering (drivers/bridge.py events()): within one poll cycle
    # step 2 polls transcript entries BEFORE step 3 emits the screen's
    # `running` flip, and the send path pushed its own synthetic `running`
    # before the driver could poll anything — so the turn's prompt entry
    # normally sits BETWEEN the two, BEFORE the boundary the capture snapshots.
    def test_live_ordering_prompt_sits_before_the_boundary(self):
        events = [
            {"type": "status_change", "status": "running"},  # synthetic (send)
            {"type": "user", "source_kind": "t", "anchor": "u-prompt",
             "content": "read file X and fix it"},
            {"type": "status_change", "status": "running"},  # driver flip
            {"type": "assistant", "source_kind": "t", "anchor": "a-close",
             "content": [{"type": "text", "text": "done"}]},
        ]
        assert timeline.turn_anchors(events, 3) == ("u-prompt", "a-close")

    def test_tool_results_never_masquerade_as_the_prompt(self):
        # Tool results are type-"user" transcript entries too — in a tool
        # turn the window's first user entry is a tool_result; the real
        # prompt sits before the boundary and must still win.
        events = [
            {"type": "status_change", "status": "running"},
            {"type": "user", "source_kind": "t", "anchor": "u-prompt",
             "content": "fix it"},
            {"type": "status_change", "status": "running"},
            {"type": "assistant", "source_kind": "t", "anchor": "a-tool",
             "content": [{"type": "tool_use", "id": "t1"}]},
            {"type": "user", "source_kind": "t", "anchor": "u-toolresult",
             "content": [{"type": "tool_result", "tool_use_id": "t1"}]},
            {"type": "assistant", "source_kind": "t", "anchor": "a-close",
             "content": [{"type": "text", "text": "done"}]},
        ]
        assert timeline.turn_anchors(events, 3) == ("u-prompt", "a-close")

    def test_backward_scan_walks_through_a_mid_turn_permission_running(self):
        # A permission prompt mid-turn re-emits `running` on resolution and
        # moves the boundary AGAIN — the backward scan walks through
        # intermediate running flips (only a non-running status_change stops
        # it) to reach the prompt.
        events = [
            {"type": "status_change", "status": "idle"},     # prev turn's end
            {"type": "status_change", "status": "running"},  # synthetic (send)
            {"type": "user", "source_kind": "t", "anchor": "u-prompt",
             "content": "write the file"},
            {"type": "status_change", "status": "running"},  # driver flip
            {"type": "assistant", "source_kind": "t", "anchor": "a-tool",
             "content": [{"type": "tool_use", "id": "t1"}]},
            {"type": "permission_request", "data": {}},
            {"type": "permission_resolved"},
            {"type": "status_change", "status": "running"},  # post-permission
            {"type": "user", "source_kind": "t", "anchor": "u-toolresult",
             "content": [{"type": "tool_result", "tool_use_id": "t1"}]},
            {"type": "assistant", "source_kind": "t", "anchor": "a-close",
             "content": [{"type": "text", "text": "written"}]},
        ]
        assert timeline.turn_anchors(events, 8) == ("u-prompt", "a-close")

    def test_backward_scan_never_bleeds_past_the_previous_turns_end(self):
        # No prompt entry for THIS turn (nothing polled yet): the scan stops
        # at the previous completion idle — it must not steal the previous
        # turn's prompt.
        events = [
            {"type": "user", "source_kind": "t", "anchor": "u-prev",
             "content": "earlier ask"},
            {"type": "assistant", "source_kind": "t", "anchor": "a-prev",
             "content": [{"type": "text", "text": "earlier answer"}]},
            {"type": "status_change", "status": "idle"},     # prev turn's end
            {"type": "status_change", "status": "running"},
            {"type": "assistant", "source_kind": "t", "anchor": "a-2",
             "content": [{"type": "text", "text": "hi"}]},
        ]
        assert timeline.turn_anchors(events, 4) == (None, "a-2")

    def test_polled_late_prompt_is_found_in_the_forward_window(self):
        # The rarer ordering: the prompt entry lags a poll cycle behind the
        # screen flip and lands INSIDE the window.
        events = [
            {"type": "status_change", "status": "running"},
            {"type": "user", "source_kind": "t", "anchor": "u-late",
             "content": "do the thing"},
            {"type": "assistant", "source_kind": "t", "anchor": "a-1",
             "content": [{"type": "text", "text": "ok"}]},
        ]
        assert timeline.turn_anchors(events, 1) == ("u-late", "a-1")

    def test_stops_at_the_next_turn_boundary(self):
        events = [
            {"type": "user", "source_kind": "t", "anchor": "u-1",
             "content": "q"},
            {"type": "assistant", "source_kind": "t", "anchor": "a-1"},
            {"type": "status_change", "status": "running"},
            {"type": "assistant", "source_kind": "t", "anchor": "a-next-turn"},
        ]
        assert timeline.turn_anchors(events, 0) == ("u-1", "a-1")

    def test_sidechain_and_meta_entries_never_anchor_the_parent_turn(self):
        # A Task-spawning turn interleaves the subagent's own sidechain
        # prompt/replies into the same transcript, and the CLI writes meta
        # user lines — the driver flags both; neither is the parent's prompt
        # or closing reply.
        events = [
            {"type": "status_change", "status": "running"},
            {"type": "user", "source_kind": "t", "anchor": "u-meta",
             "content": "Caveat: the messages below…", "meta": True},
            {"type": "user", "source_kind": "t", "anchor": "u-side",
             "content": "subagent task prompt", "sidechain": True},
            {"type": "user", "source_kind": "t", "anchor": "u-prompt",
             "content": "spawn a subagent"},
            {"type": "assistant", "source_kind": "t", "anchor": "a-side",
             "content": [{"type": "text", "text": "subagent says"}],
             "sidechain": True},
            {"type": "assistant", "source_kind": "t", "anchor": "a-close",
             "content": [{"type": "text", "text": "parent close"}]},
            {"type": "assistant", "source_kind": "t", "anchor": "a-side2",
             "content": [{"type": "text", "text": "late sidechain"}],
             "sidechain": True},
        ]
        assert timeline.turn_anchors(events, 1) == ("u-prompt", "a-close")

    def test_unanchored_events_are_null_safe(self):
        # SDK/synthesized events carry no transcript anchor — an honest miss,
        # never a fabricated one.
        events = [
            {"type": "user", "content": []},
            {"type": "assistant", "source_kind": "s"},
        ]
        assert timeline.turn_anchors(events, 0) == (None, None)
        assert timeline.turn_anchors([], 0) == (None, None)


# -----------------------------------------------------------------------------
# #46 — replay_timeline (the interleaved turn/rewind stream → rolled state)
# -----------------------------------------------------------------------------

def _t(n):
    return {"type": "turn", "turn": n, "timestamp": f"t{n}", "summary": f"s{n}"}


def _rw(k, ts="rw"):
    return {"type": "rewind", "timestamp": ts, "to_prompt_index": k}


class TestReplayTimeline:
    def test_pure_turn_file_is_all_live_with_todays_numbering(self):
        # No rewind records: count/ordinals exactly as before the residual.
        out = timeline.replay_timeline([_t(7), _t(1)])
        assert [r["turn"] for r in out["turns"]] == [1, 2]
        assert [r["rolled"] for r in out["turns"]] == [False, False]
        assert out["rolled_ranges"] == [] and out["rewinds"] == []

    def test_single_rewind_k1_rolls_the_head(self):
        out = timeline.replay_timeline([_t(1), _t(2), _rw(1)])
        assert [r["rolled"] for r in out["turns"]] == [False, True]
        assert out["rolled_ranges"] == [{"from": 1, "to": 2}]
        assert out["rewinds"] == [{"timestamp": "rw", "to_prompt_index": 1}]

    def test_single_rewind_k2_rolls_the_top_two(self):
        out = timeline.replay_timeline([_t(1), _t(2), _t(3), _rw(2)])
        assert [r["rolled"] for r in out["turns"]] == [False, True, True]
        assert out["rolled_ranges"] == [{"from": 1, "to": 3}]

    def test_post_rewind_turns_stay_live(self):
        out = timeline.replay_timeline([_t(1), _t(2), _rw(1), _t(3)])
        assert [r["rolled"] for r in out["turns"]] == [False, True, False]
        assert out["rolled_ranges"] == [{"from": 1, "to": 2}]

    def test_chained_rewinds_with_a_fresh_turn_between_compose(self):
        # k=1, a fresh turn, k=1 again: the live stack is [1,2]→[1]→[1,3]→[1],
        # so ordinals 2 and 3 are rolled — adjacent, merged into one range.
        out = timeline.replay_timeline([_t(1), _t(2), _rw(1), _t(3), _rw(1)])
        assert [r["rolled"] for r in out["turns"]] == [False, True, True]
        assert out["rolled_ranges"] == [{"from": 1, "to": 3}]
        assert [r["to_prompt_index"] for r in out["rewinds"]] == [1, 1]

    def test_disjoint_rolled_runs_stay_separate_ranges(self):
        # Rolled 2, then two live turns, then rolled 4: a live ordinal (3)
        # sits between the runs — the merge must NOT bridge it.
        out = timeline.replay_timeline([_t(1), _t(2), _rw(1), _t(3), _t(4),
                                        _rw(1)])
        assert [r["rolled"] for r in out["turns"]] == \
            [False, True, False, True]
        assert out["rolled_ranges"] == [{"from": 1, "to": 2},
                                        {"from": 3, "to": 4}]

    def test_k_over_stack_clamps_honestly_and_never_crashes(self):
        out = timeline.replay_timeline([_t(1), _rw(5)])
        assert [r["rolled"] for r in out["turns"]] == [True]
        assert out["rolled_ranges"] == [{"from": 0, "to": 1}]
        assert out["rewinds"] == [{"timestamp": "rw", "to_prompt_index": 5}]
        # A rewind event with no turns at all is replayable too.
        out = timeline.replay_timeline([_rw(2)])
        assert out["turns"] == [] and out["rolled_ranges"] == []
        assert [r["to_prompt_index"] for r in out["rewinds"]] == [2]

    def test_typeless_old_lines_replay_as_turns(self):
        # Backward compat: pre-residual files carry no "type" — they must
        # replay identically to typed turn records.
        old = {"turn": 1, "timestamp": "t1", "summary": "old"}
        out = timeline.replay_timeline([old, _t(2), _rw(1)])
        assert [r["turn"] for r in out["turns"]] == [1, 2]
        assert [r["rolled"] for r in out["turns"]] == [False, True]

    def test_unknown_typed_lines_are_skipped_not_rows(self):
        # Forward compat: a future typed line is neither a turn row nor a
        # rewind — ordinals stay stable around it.
        out = timeline.replay_timeline([_t(1), {"type": "mystery"}, _t(2)])
        assert [r["turn"] for r in out["turns"]] == [1, 2]
        assert all(r["rolled"] is False for r in out["turns"])


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

    def test_capture_lifts_anchors_in_live_bridge_event_ordering(self):
        # LIVE ordering (not the polled-late one): the driver polls the
        # prompt entry in BEFORE it emits the running flip the capture window
        # starts at (the send already pushed a synthetic running before
        # either) — the lift reaches BACK for the prompt and forward for the
        # closing reply.
        drv = _TimelineDriver()
        s = _register(drv)
        s.events = [
            {"type": "status_change", "status": "running"},  # synthetic (send)
            {"type": "user", "source_kind": "t", "anchor": "u-abc",
             "content": "do the thing"},
            {"type": "status_change", "status": "running"},  # driver flip
            {"type": "assistant", "source_kind": "t", "anchor": "a-def",
             "content": [{"type": "text", "text": "Fixed the poll race."}]},
        ]
        s._turn_start_idx = 3
        asyncio.run(main._capture_turn_record(s, 1, 3))
        rec = s.turns[0]
        assert rec["prompt_uuid"] == "u-abc"
        assert rec["reply_uuid"] == "a-def"
        assert rec["type"] == "turn"       # new writes are explicitly typed
        assert drv.appended == [rec]       # anchors persist thin, additively

    def test_capture_tool_turn_never_anchors_a_tool_result_as_the_prompt(self):
        # A tool turn's window starts with a tool_result user entry — the
        # persisted prompt_uuid must be the real prompt (before the
        # boundary), never the tool result.
        drv = _TimelineDriver()
        s = _register(drv)
        s.events = [
            {"type": "status_change", "status": "running"},
            {"type": "user", "source_kind": "t", "anchor": "u-prompt",
             "content": "read file X and fix it"},
            {"type": "status_change", "status": "running"},
            {"type": "assistant", "source_kind": "t", "anchor": "a-tool",
             "content": [{"type": "tool_use", "id": "t1"}]},
            {"type": "user", "source_kind": "t", "anchor": "u-toolresult",
             "content": [{"type": "tool_result", "tool_use_id": "t1"}]},
            {"type": "assistant", "source_kind": "t", "anchor": "a-close",
             "content": [{"type": "text", "text": "Fixed."}]},
        ]
        s._turn_start_idx = 3
        asyncio.run(main._capture_turn_record(s, 1, 3))
        rec = s.turns[0]
        assert rec["prompt_uuid"] == "u-prompt"    # never "u-toolresult"
        assert rec["reply_uuid"] == "a-close"

    def test_capture_without_anchors_records_nulls(self):
        # SDK-driven / synthesized events carry no transcript anchor — the
        # fields stay null-safe, never fabricated.
        drv = _TimelineDriver()
        s = _register(drv)
        s.events = list(_TURN_EVENTS)      # no anchor / source_kind fields
        s._turn_start_idx = 1
        asyncio.run(main._capture_turn_record(s, 1, 1))
        rec = s.turns[0]
        assert rec["prompt_uuid"] is None and rec["reply_uuid"] is None
        assert rec["summary"] == "Fixed the poll race."

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


class TestCaptureSettle:
    """The trailing-entry settle: the bridge flips generating->idle off SCREEN
    state ~1s before the transcript tail is polled into events (the exact lag
    `_maybe_relay_reply` retries for), so a multi-entry reply could otherwise
    persist `reply_uuid` anchored mid-reply. The capture re-lifts summary +
    anchors until two consecutive lifts agree (bounded)."""

    def teardown_method(self):
        main.sessions.pop("s1", None)
        runstate.reset()

    def test_capture_relifts_until_the_window_is_stable(self, monkeypatch):
        drv = _TimelineDriver()
        s = _register(drv)
        s.events = [
            {"type": "status_change", "status": "running"},
            {"type": "user", "source_kind": "t", "anchor": "u-1",
             "content": "long ask"},
            {"type": "status_change", "status": "running"},
            {"type": "assistant", "source_kind": "t", "anchor": "a-mid",
             "content": [{"type": "text", "text": "First entry…"}]},
        ]
        s._turn_start_idx = 3

        real_anchors = main.timeline.turn_anchors
        lifts = {"n": 0}

        def lift_with_late_tail(events, start_idx=0):
            # The closing entry flushes between lift 1 and lift 2 — exactly
            # the screen-idle-before-transcript-tail lag.
            lifts["n"] += 1
            if lifts["n"] == 2:
                s.events.append(
                    {"type": "assistant", "source_kind": "t",
                     "anchor": "a-close",
                     "content": [{"type": "text", "text": "Closing entry."}]})
            return real_anchors(events, start_idx)

        monkeypatch.setattr(main.timeline, "turn_anchors", lift_with_late_tail)
        asyncio.run(main._capture_turn_record(s, 1, 3))
        rec = s.turns[0]
        assert rec["reply_uuid"] == "a-close"   # the closing entry, not a-mid
        assert lifts["n"] >= 3                  # re-lifted until stable

    def test_live_settle_budget_is_a_real_bounded_wait(self, _zero_capture_settle):
        # The autouse fixture zeroes the sleep for hermetic speed and hands
        # back the LIVE value — production must keep a real positive settle
        # with a bounded attempt budget (the relay's shape).
        assert _zero_capture_settle > 0
        assert 1 <= main._CAPTURE_SETTLE_ATTEMPTS <= 10


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
        assert out == {"session_id": "s1", "count": 0, "turns": [],
                       "rolled_ranges": [], "rewinds": []}

    def test_unknown_session_404(self):
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.get_timeline_endpoint("nope"))
        assert ei.value.status_code == 404

    def test_rewind_records_replay_into_rolled_state(self):
        # The persisted rewind event is replayed at the read surface: per-row
        # `rolled`, merged `rolled_ranges`, the `rewinds` list — and `count` /
        # ordinals cover TURN rows only (the rewind line is not a row).
        records = [_t(1), _t(2), _rw(1, ts="rw1"), _t(3)]
        _register(_TimelineDriver(records=records))
        out = asyncio.run(main.get_timeline_endpoint("s1"))
        assert out["count"] == 3
        assert [r["turn"] for r in out["turns"]] == [1, 2, 3]
        assert [r["rolled"] for r in out["turns"]] == [False, True, False]
        assert out["rolled_ranges"] == [{"from": 1, "to": 2}]
        assert out["rewinds"] == [{"timestamp": "rw1", "to_prompt_index": 1}]

    def test_mirror_fallback_replays_the_same_rolled_truth(self):
        # A driver with no persist surface still gets consistent rolled state:
        # the rewind record is mirrored into session.turns alongside the turn
        # records, and the same replay runs over the mirror.
        s = _register(_ReadoutDriver(caps=set()))
        s.turns = [_t(1), _t(2), _rw(1)]
        out = asyncio.run(main.get_timeline_endpoint("s1"))
        assert out["count"] == 2
        assert [r["rolled"] for r in out["turns"]] == [False, True]
        assert out["rolled_ranges"] == [{"from": 1, "to": 2}]

    def test_pending_rewind_record_is_served_before_it_drains(self):
        # A rewind event whose turns.jsonl append transiently failed sits on
        # _turns_pending until the next capture drains it. The read surface
        # must still serve the rolled truth: the renderer keeps NO client-side
        # marking anymore, and a user rewinding again over silently un-rolled
        # rows would compute k one prompt too deep.
        drv = _TimelineDriver(records=[_t(1), _t(2), _t(3)])
        s = _register(drv)
        rw = _rw(1, ts="rw-pending")
        s.turns = [_t(1), _t(2), _t(3), rw]
        s._turns_pending.append(rw)
        out = asyncio.run(main.get_timeline_endpoint("s1"))
        assert out["count"] == 3
        assert [r["rolled"] for r in out["turns"]] == [False, False, True]
        assert out["rolled_ranges"] == [{"from": 2, "to": 3}]
        assert out["rewinds"] == [{"timestamp": "rw-pending",
                                   "to_prompt_index": 1}]

    def test_pending_records_already_on_the_file_tail_are_not_doubled(self):
        # Snapshot-then-read means a drain racing the GET can land the
        # snapshot prefix on the file tail — the merge dedupes it (a doubled
        # rewind would roll k extra turns).
        rw = _rw(1, ts="rw-dup")
        drv = _TimelineDriver(records=[_t(1), _t(2), rw])
        s = _register(drv)
        s._turns_pending.append(dict(rw))  # value-equal, as a JSON round trip
        out = asyncio.run(main.get_timeline_endpoint("s1"))
        assert out["count"] == 2
        assert [r["rolled"] for r in out["turns"]] == [False, True]
        assert out["rewinds"] == [{"timestamp": "rw-dup",
                                   "to_prompt_index": 1}]

    def test_pending_turn_record_is_served_too(self):
        # The merge is record-agnostic: a still-pending TURN record shows as
        # its row (the pre-existing pending gap closed for turns as well).
        drv = _TimelineDriver(records=[_t(1)])
        s = _register(drv)
        t2 = _t(2)
        s.turns = [_t(1), t2]
        s._turns_pending.append(t2)
        out = asyncio.run(main.get_timeline_endpoint("s1"))
        assert out["count"] == 2
        assert [r["turn"] for r in out["turns"]] == [1, 2]


# -----------------------------------------------------------------------------
# #46 — the rewind event record (POST /sessions/{id}/rewind → turns.jsonl)
# -----------------------------------------------------------------------------

class _RewindRecordDriver(_TimelineDriver):
    """#46 rewind-event surface: a bridge-shaped driver with BOTH the rewind
    lever and the turns.jsonl persist surface (append_turn_record via
    _TimelineDriver)."""

    def __init__(self, error=None, **kw):
        super().__init__(**kw)
        self._error = error

    def supports(self, cap):
        return cap in {"rewind", "timeline"}

    async def rewind(self, to_prompt_index):
        if self._error:
            raise RuntimeError(self._error)
        return {"status": "rewound", "name": "s1",
                "to_prompt_index": to_prompt_index}


class TestRewindEventRecord:
    def teardown_method(self):
        main.sessions.pop("s1", None)

    def test_success_appends_the_typed_record_and_mirrors_it(self):
        drv = _RewindRecordDriver()
        s = _register(drv)
        out = asyncio.run(main.rewind_session(
            "s1", main.RewindRequest(to_prompt_index=2)))
        assert out["status"] == "ok"       # the endpoint envelope is unchanged
        assert len(drv.appended) == 1
        rec = drv.appended[0]
        assert rec["type"] == "rewind" and rec["to_prompt_index"] == 2
        assert rec["timestamp"]
        assert s.turns == [rec]            # mirrored alongside session.turns

    def test_bridge_rewind_failure_appends_nothing(self):
        # A failed rewind (busy / version-gated / bridge error) must leave the
        # record untouched — no phantom rewind event, mirror included.
        for reason, code in (("busy", 409), ("version_unsupported", 400),
                             ("tmux exploded", 500)):
            drv = _RewindRecordDriver(error=reason)
            s = _register(drv)
            with pytest.raises(HTTPException) as ei:
                asyncio.run(main.rewind_session("s1", main.RewindRequest()))
            assert ei.value.status_code == code
            assert drv.appended == [] and s.turns == []

    def test_rewind_record_drains_behind_a_still_pending_turn_record(self):
        # File-order guarantee: a turn record whose persist failed transiently
        # (queued on _turns_pending) drains FIRST — the rewind event can never
        # land ahead of a turn record still draining.
        drv = _RewindRecordDriver()
        s = _register(drv)
        stuck = _t(1)
        s.turns.append(stuck)
        s._turns_pending.append(stuck)     # turn 1's append failed earlier
        asyncio.run(main.rewind_session(
            "s1", main.RewindRequest(to_prompt_index=1)))
        assert [r.get("type") for r in drv.appended] == ["turn", "rewind"]
        assert s._turns_pending == []

    def test_rewind_record_chains_behind_an_in_flight_capture(self):
        # The rewind append rides the SAME per-session _capture_tail chain as
        # turn captures: a capture stalled on its statusline snapshot still
        # lands its turn record BEFORE the rewind event.
        class _SlowSnapRewind(_RewindRecordDriver):
            async def get_statusline_snapshot(self):
                await asyncio.sleep(0.05)
                return None

        async def flow():
            drv = _SlowSnapRewind()
            s = _register(drv)
            s.events = list(_TURN_EVENTS)
            s._turn_start_idx = 1
            main._capture_turn(s)          # schedules; stalls on the snapshot
            await main.rewind_session(
                "s1", main.RewindRequest(to_prompt_index=1))
            assert [r.get("type") for r in drv.appended] == ["turn", "rewind"]
            assert [r.get("type") for r in s.turns] == ["turn", "rewind"]

        asyncio.run(flow())


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
