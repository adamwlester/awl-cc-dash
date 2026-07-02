"""Hermetic unit tests for the sidecar's session bookkeeping.

Pure: no driver, no WSL2/tmux, no model. Feeds plain event dicts through
``SessionState.handle_event`` to prove the permission wiring — a
``permission_request`` event flips ``has_pending_permission`` and stores the
detail; a ``permission_resolved`` event clears it. These carry neither the
``integration`` nor the ``slow`` mark.
"""

import sys
from pathlib import Path

import pytest

# The sidecar runs with its own dir on sys.path (not the repo root).
_SIDECAR = Path(__file__).resolve().parent.parent / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))

import asyncio  # noqa: E402

import eventbus  # noqa: E402
import main  # noqa: E402
from main import SessionState  # noqa: E402
from drivers import default_driver_name  # noqa: E402
from identity import (  # noqa: E402
    assign_identity, AG_COLORS, AG_ICONS, AG_ICONS_CURATED,
)


@pytest.fixture(autouse=True)
def _clean_event_bus():
    # The cross-agent bus is process-global (like `sessions`) — reset per test.
    eventbus.reset()
    yield
    eventbus.reset()


def _session():
    return SessionState(
        session_id="s1", agent_type=None, model=None,
        permission_mode="default", cwd=None, system_prompt=None,
        driver_name="bridge",
    )


def test_permission_request_sets_pending_flag():
    s = _session()
    assert s.to_dict()["has_pending_permission"] is False

    detail = {"question": "Do you want to create x.txt?",
              "options": [{"index": 1, "label": "Yes"}]}
    s.handle_event({"type": "permission_request", "data": detail})

    assert s.pending_permission == detail
    assert s.to_dict()["has_pending_permission"] is True
    # The event is also fanned out to subscribers/history.
    assert s.events[-1]["type"] == "permission_request"


def test_permission_resolved_clears_pending_flag():
    s = _session()
    s.handle_event({"type": "permission_request", "data": {"question": "?"}})
    assert s.pending_permission is not None

    s.handle_event({"type": "permission_resolved"})
    assert s.pending_permission is None
    assert s.to_dict()["has_pending_permission"] is False
    assert s.events[-1]["type"] == "permission_resolved"


def test_status_enum_untouched_by_permission_events():
    # Pending reads off the flag, not a new status value — status stays as-is.
    s = _session()
    s.status = "running"
    s.handle_event({"type": "permission_request", "data": {"question": "?"}})
    assert s.status == "running"
    s.handle_event({"type": "permission_resolved"})
    assert s.status == "running"


# ---------------------------------------------------------------------------
# Default driver selection
#
# Policy: `bridge` is the primary path the dashboard is built around, so an
# unnamed session must run on `bridge`. `sdk` is a reserved, explicit-only
# backup engine. These guard the default (and that explicit `sdk` still works).
# ---------------------------------------------------------------------------

def test_default_driver_is_bridge_when_unset(monkeypatch):
    # Nothing named (no AWL_DRIVER, no per-session driver) -> the primary path.
    monkeypatch.delenv("AWL_DRIVER", raising=False)
    assert default_driver_name() == "bridge"


def test_awl_driver_env_still_selects_sdk(monkeypatch):
    # sdk stays reachable as an explicit choice (case/whitespace tolerant).
    monkeypatch.setenv("AWL_DRIVER", " SDK ")
    assert default_driver_name() == "sdk"


def test_unnamed_session_reports_bridge(monkeypatch):
    # The API surface (to_dict, used by /health and session listing) reports the
    # default for a not-yet-connected session that named no driver.
    monkeypatch.delenv("AWL_DRIVER", raising=False)
    s = SessionState(
        session_id="s2", agent_type=None, model=None,
        permission_mode="default", cwd=None, system_prompt=None,
        driver_name=None,
    )
    assert s.to_dict()["driver"] == "bridge"


def test_explicit_sdk_session_preserved(monkeypatch):
    # Per-session sdk selection is preserved regardless of the default/env.
    monkeypatch.delenv("AWL_DRIVER", raising=False)
    s = SessionState(
        session_id="s3", agent_type=None, model=None,
        permission_mode="default", cwd=None, system_prompt=None,
        driver_name="sdk",
    )
    assert s.to_dict()["driver"] == "sdk"


# ---------------------------------------------------------------------------
# Agent identity assignment (sidecar/identity.py)
# ---------------------------------------------------------------------------

class TestIdentityAssignment:
    def test_defaults_for_first_agent(self):
        ident = assign_identity(None, 0)
        assert ident["role"] == "Agent"
        assert ident["number"] == 1
        assert ident["name"] == ""
        assert ident["color"] == AG_COLORS[0][1]   # round-robin slot 0
        assert ident["icon"] == AG_ICONS_CURATED[0]  # round-robin over the curated 50
        # Color is a real hex value.
        assert ident["color"].startswith("#") and len(ident["color"]) == 7

    def test_color_and_number_round_robin(self):
        # Ordinal n -> color slot n%len(palette) (=25 once the design stream lands
        # the +9; 16 today), number n+1.
        for n in (1, 5, 15, 16, 17):
            ident = assign_identity(None, n)
            assert ident["color"] == AG_COLORS[n % len(AG_COLORS)][1]
            assert ident["number"] == n + 1
        # Wraps at the palette size (generalized so it survives 16 -> 25).
        assert (assign_identity(None, len(AG_COLORS))["color"]
                == assign_identity(None, 0)["color"])

    def test_icon_round_robin_over_curated_50(self):
        # Identity decision: icon = n mod 50 over the CURATED pool (not the full 167 on disk).
        assert len(AG_ICONS_CURATED) == 50
        for n in (0, 1, 25, 49, 50, 51, 99, 100):
            assert assign_identity(None, n)["icon"] == AG_ICONS_CURATED[n % 50]
        # Wraps every 50; adjacent ordinals differ.
        assert assign_identity(None, 50)["icon"] == assign_identity(None, 0)["icon"]
        assert assign_identity(None, 0)["icon"] != assign_identity(None, 49)["icon"]

    def test_curated_pool_is_50_unique_real_icons(self):
        # Exactly 50, all distinct, all bare stems, all present on disk (a subset
        # of the discovered 167) — guards curation drift if an asset is removed.
        assert len(AG_ICONS_CURATED) == 50
        assert len(set(AG_ICONS_CURATED)) == 50
        discovered = set(AG_ICONS)
        for stem in AG_ICONS_CURATED:
            assert "/" not in stem and not stem.endswith(".svg")
            assert stem in discovered, f"curated icon missing on disk: {stem}"

    def test_overrides_are_honored(self):
        req = {"role": "Reviewer", "number": 7, "name": "Ada",
               "color": "#123456", "icon": "fox-head"}
        ident = assign_identity(req, 3)
        assert ident == {"role": "Reviewer", "number": 7, "name": "Ada",
                         "color": "#123456", "icon": "fox-head"}

    def test_partial_override_fills_rest(self):
        ident = assign_identity({"name": "Bob"}, 2)
        assert ident["name"] == "Bob"
        assert ident["role"] == "Agent"
        assert ident["number"] == 3
        assert ident["color"] == AG_COLORS[2][1]

    def test_icons_are_real_names(self):
        # The discovered icon set is non-empty and names are bare stems.
        assert AG_ICONS and all("/" not in n and not n.endswith(".svg")
                                for n in AG_ICONS)

    def test_identity_surfaced_on_to_dict(self):
        ident = assign_identity(None, 0)
        s = SessionState(
            session_id="s4", agent_type=None, model=None,
            permission_mode="default", cwd=None, system_prompt=None,
            driver_name="bridge", identity=ident,
        )
        assert s.to_dict()["identity"] == ident


# ---------------------------------------------------------------------------
# Cross-agent event envelope + addressing on push_event
# ---------------------------------------------------------------------------

class TestEventEnvelope:
    def test_push_stamps_envelope(self):
        s = _session()
        s.push_event({"type": "assistant", "content": []})
        ev = s.events[-1]
        assert ev["agent_id"] == "s1"          # sender = session id
        assert isinstance(ev["seq"], int)        # monotonic ordering key
        assert ev["id"]                          # stable id
        assert ev["ts"]
        assert ev["source"] == "s1"             # default source
        assert ev["recipients"] == ["user"]      # default recipients

    def test_push_dedups_anchored_event_on_repoll(self):
        s = _session()
        s.push_event({"type": "assistant", "anchor": "uuid-1", "source_kind": "t"})
        s.push_event({"type": "assistant", "anchor": "uuid-1", "source_kind": "t"})
        # Same transcript entry re-polled -> a single stored event (no-op dedup).
        anchored = [e for e in s.events if e.get("anchor") == "uuid-1"]
        assert len(anchored) == 1

    def test_push_mirrors_into_global_ring(self):
        s = _session()
        s.push_event({"type": "assistant", "content": []})
        ring = eventbus.replay()
        assert len(ring) == 1
        assert ring[0]["agent_id"] == "s1"

    def test_two_agents_merge_into_one_stream(self):
        a = SessionState(session_id="a1", agent_type=None, model=None,
                         permission_mode="default", cwd=None, system_prompt=None,
                         driver_name="bridge")
        b = SessionState(session_id="b1", agent_type=None, model=None,
                         permission_mode="default", cwd=None, system_prompt=None,
                         driver_name="bridge")
        a.push_event({"type": "assistant", "content": []})
        b.push_event({"type": "assistant", "content": []})
        a.push_event({"type": "assistant", "content": []})
        ring = eventbus.replay()
        assert [e["agent_id"] for e in ring] == ["a1", "b1", "a1"]
        # Monotonic seq across the merged stream.
        seqs = [e["seq"] for e in ring]
        assert seqs == sorted(seqs)

    def test_preaddressed_event_keeps_source_recipients(self):
        s = _session()
        s.push_event({"type": "assistant", "source": "user", "recipients": ["s1"]})
        ev = s.events[-1]
        assert ev["source"] == "user"
        assert ev["recipients"] == ["s1"]


class TestMergedHistoryEndpoint:
    """The merged /events/history endpoint: ring replay + From/To + ?since."""

    def _two_agents(self):
        a = SessionState(session_id="a1", agent_type=None, model=None,
                         permission_mode="default", cwd=None, system_prompt=None)
        b = SessionState(session_id="b1", agent_type=None, model=None,
                         permission_mode="default", cwd=None, system_prompt=None)
        a.push_event({"type": "assistant", "content": []})
        b.push_event({"type": "assistant", "content": [], "recipients": ["a1"]})
        return a, b

    def test_returns_merged_ring(self):
        self._two_agents()
        merged = asyncio.run(main.get_merged_history())
        assert [e["agent_id"] for e in merged] == ["a1", "b1"]

    def test_recipient_filter(self):
        self._two_agents()
        to_a1 = asyncio.run(main.get_merged_history(recipient="a1"))
        assert [e["agent_id"] for e in to_a1] == ["b1"]

    def test_source_filter(self):
        self._two_agents()
        from_a1 = asyncio.run(main.get_merged_history(source="a1"))
        assert [e["agent_id"] for e in from_a1] == ["a1"]

    def test_since_backfill(self):
        self._two_agents()
        merged = asyncio.run(main.get_merged_history())
        cutoff = merged[0]["seq"]
        later = asyncio.run(main.get_merged_history(since=cutoff))
        assert [e["agent_id"] for e in later] == ["b1"]


# ---------------------------------------------------------------------------
# Per-agent ordered prompt queue + idle-flush (no more 409-drop)
# ---------------------------------------------------------------------------

class _FakeDriver:
    name = "fake"

    def __init__(self):
        self.sent: list[str] = []
        self.interrupted = 0

    def supports(self, _cap):
        return False

    async def send(self, prompt):
        self.sent.append(prompt)

    async def interrupt(self):
        self.interrupted += 1


class TestPromptQueue:
    def test_enqueue_queue_appends_tail(self):
        s = _session()
        s.enqueue({"prompt": "a"}, "queue")
        s.enqueue({"prompt": "b"}, "queue")
        assert [e["prompt"] for e in s.prompt_queue] == ["a", "b"]

    def test_enqueue_next_inserts_head(self):
        s = _session()
        s.enqueue({"prompt": "a"}, "queue")
        s.enqueue({"prompt": "b"}, "next")
        assert [e["prompt"] for e in s.prompt_queue] == ["b", "a"]

    def test_hold_stages_not_queues(self):
        s = _session()
        r = s.enqueue({"prompt": "h"}, "hold")
        assert [e["prompt"] for e in s.held] == ["h"]
        assert len(s.prompt_queue) == 0
        assert r["status"] == "held"

    def test_flush_sends_head_when_idle(self):
        s = _session()
        s.driver = _FakeDriver()
        s.status = "idle"
        s.enqueue({"prompt": "a", "source": "user", "recipients": ["s1"]}, "queue")
        s.enqueue({"prompt": "b"}, "queue")
        asyncio.run(main._flush_queue(s))
        assert s.driver.sent == ["a"]          # head sent
        assert s.status == "running"
        assert [e["prompt"] for e in s.prompt_queue] == ["b"]  # head popped

    def test_flush_noop_when_running(self):
        s = _session()
        s.driver = _FakeDriver()
        s.status = "running"
        s.enqueue({"prompt": "a"}, "queue")
        asyncio.run(main._flush_queue(s))
        assert s.driver.sent == []             # busy: nothing flushed
        assert len(s.prompt_queue) == 1

    def test_flush_noop_when_empty(self):
        s = _session()
        s.driver = _FakeDriver()
        s.status = "idle"
        asyncio.run(main._flush_queue(s))
        assert s.driver.sent == []

    def test_send_to_idle_sends_immediately(self):
        s = _session(); s.driver = _FakeDriver(); s.status = "idle"
        main.sessions["s1"] = s
        try:
            asyncio.run(main.send_prompt("s1", main.SendPromptRequest(prompt="x")))
        finally:
            main.sessions.pop("s1", None)
        assert s.driver.sent == ["x"]

    def test_send_to_busy_enqueues_not_409(self):
        # The queue fix: a prompt to a running agent is QUEUED, never dropped.
        s = _session(); s.driver = _FakeDriver(); s.status = "running"
        main.sessions["s1"] = s
        try:
            r = asyncio.run(main.send_prompt(
                "s1", main.SendPromptRequest(prompt="x", disposition="queue")))
        finally:
            main.sessions.pop("s1", None)
        assert r["status"] == "queued"
        assert s.driver.sent == []
        assert [e["prompt"] for e in s.prompt_queue] == ["x"]

    def test_send_now_interrupts_running_and_heads_queue(self):
        s = _session(); s.driver = _FakeDriver(); s.status = "running"
        main.sessions["s1"] = s
        try:
            asyncio.run(main.send_prompt(
                "s1", main.SendPromptRequest(prompt="x", disposition="now")))
        finally:
            main.sessions.pop("s1", None)
        assert s.driver.interrupted == 1               # Now interrupts the run
        assert s.prompt_queue[0]["prompt"] == "x"      # waits at head for idle-flush
        assert s.driver.sent == []


import hookbus  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_hookbus():
    hookbus.reset()
    yield
    hookbus.reset()


class TestInjectDisposition:
    """The `inject` disposition routes to the hook inbox, NOT the prompt queue,
    and surfaces a synthesized feed event (the inject isn't in the JSONL)."""

    def test_inject_enqueues_to_hookbus_not_queue(self):
        s = _session(); s.driver = _FakeDriver(); s.status = "running"
        main.sessions["s1"] = s
        try:
            r = asyncio.run(main.send_prompt(
                "s1", main.SendPromptRequest(
                    prompt="peer touched foo.py", disposition="inject",
                    source="coder-02")))
        finally:
            main.sessions.pop("s1", None)
        assert r["status"] == "injected"
        # not on the prompt queue, not sent to the driver
        assert len(s.prompt_queue) == 0
        assert s.driver.sent == []
        # waiting on the durable inbox for the next tool boundary
        pend = hookbus.pending("s1")
        assert [i["text"] for i in pend] == ["peer touched foo.py"]
        assert pend[0]["source"] == "coder-02"
        # and a feed event was synthesized
        assert any(e["type"] == "inject" for e in s.events)


import links  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_links():
    links.reset()
    yield
    links.reset()


def _agent(sid):
    s = SessionState(session_id=sid, agent_type=None, model=None,
                     permission_mode="default", cwd=None, system_prompt=None,
                     driver_name="bridge")
    s.driver = _FakeDriver()
    return s


def _finish_turn(s, text):
    """Simulate a completed turn: running (sets _turn_start_idx) -> assistant text."""
    s.push_event({"type": "status_change", "status": "running",
                  "timestamp": "t"})
    s.push_event({"type": "assistant",
                  "content": [{"type": "text", "text": text}], "timestamp": "t"})


class TestReplyToRelay:
    """Serialized reply-to: a finished turn answering a linked peer fires
    that turn's output back to the peer, and sets the peer's reply-to in return."""

    def test_relay_enqueues_to_peer_and_sets_replyto(self):
        a, b = _agent("A"), _agent("B")
        main.sessions["A"], main.sessions["B"] = a, b
        try:
            lk = links.add_link(a="A", b="B", relationship=["direct"], trigger="queue")
            b.answering_source, b.answering_link = "A", lk.id
            _finish_turn(b, "here is my reply")
            main._maybe_relay_reply(b)
            # B's output is enqueued to A, addressed From B -> [A]
            assert [e["prompt"] for e in a.prompt_queue] == ["here is my reply"]
            assert a.prompt_queue[0]["source"] == "B"
            assert a.prompt_queue[0]["recipients"] == ["A"]
            # and A is now set to reply back to B (alternation)
            assert a.answering_source == "B" and a.answering_link == lk.id
            # B's reply-to state is cleared (one-in-flight)
            assert b.answering_source is None
            assert lk.messages == 1
        finally:
            main.sessions.pop("A", None); main.sessions.pop("B", None)

    def test_relay_noop_without_answering_source(self):
        b = _agent("B"); main.sessions["B"] = b
        try:
            _finish_turn(b, "just a normal turn")
            main._maybe_relay_reply(b)  # no answering_source -> nothing happens
            assert all(s == b for s in [b])  # no crash
        finally:
            main.sessions.pop("B", None)

    def test_cap_ends_exchange_and_stops_alternation(self):
        a, b = _agent("A"), _agent("B")
        main.sessions["A"], main.sessions["B"] = a, b
        try:
            lk = links.add_link(a="A", b="B", relationship=["direct"],
                                end_after_exchanges=1)  # cap at 2 messages
            # first fire B->A (message 1): not capped, sets A's reply-to
            b.answering_source, b.answering_link = "A", lk.id
            _finish_turn(b, "msg1")
            main._maybe_relay_reply(b)
            assert lk.active and a.answering_source == "B"
            # second fire A->B (message 2): hits the cap -> link inactive, no more reply-to
            _finish_turn(a, "msg2")
            main._maybe_relay_reply(a)
            assert lk.messages == 2 and lk.over_cap() and not lk.active
            assert b.answering_source is None   # alternation stopped
        finally:
            main.sessions.pop("A", None); main.sessions.pop("B", None)

    def test_inject_trigger_routes_to_hookbus(self):
        a, b = _agent("A"), _agent("B")
        main.sessions["A"], main.sessions["B"] = a, b
        try:
            lk = links.add_link(a="A", b="B", relationship=["direct"], trigger="inject")
            b.answering_source, b.answering_link = "A", lk.id
            _finish_turn(b, "mid-run reply")
            main._maybe_relay_reply(b)
            # inject trigger -> A's hook inbox, NOT A's prompt queue
            assert len(a.prompt_queue) == 0
            assert [i["text"] for i in hookbus.pending("A")] == ["mid-run reply"]
        finally:
            main.sessions.pop("A", None); main.sessions.pop("B", None)


class TestHookDrainEndpoints:
    def test_post_tool_use_drains_and_acks(self):
        s = _session(); main.sessions["s1"] = s
        try:
            hookbus.enqueue_inject("s1", "hello mid-turn", source="user")
            out = asyncio.run(main.hook_post_tool_use(agent="s1"))
            ctx = out["hookSpecificOutput"]["additionalContext"]
            assert "hello mid-turn" in ctx
            # acked: a second drain is an empty no-op
            assert asyncio.run(main.hook_post_tool_use(agent="s1")) == {}
            # delivered event surfaced on the feed
            assert any(e["type"] == "inject_delivered" for e in s.events)
        finally:
            main.sessions.pop("s1", None)

    def test_post_tool_use_empty_is_noop(self):
        assert asyncio.run(main.hook_post_tool_use(agent="nobody")) == {}

    def test_stop_only_blocks_for_active_injects(self):
        main.sessions["s1"] = _session()
        try:
            hookbus.enqueue_inject("s1", "passive", kind="context")
            # nothing active -> Stop is a no-op, passive stays pending
            assert asyncio.run(main.hook_stop(agent="s1")) == {}
            assert [i["text"] for i in hookbus.pending("s1")] == ["passive"]
            # an active inject -> Stop blocks with the reason
            hookbus.enqueue_inject("s1", "answer me", kind="inject")
            out = asyncio.run(main.hook_stop(agent="s1"))
            assert out["decision"] == "block"
            assert "answer me" in out["reason"]
            # the passive one is still NOT consumed by the Stop drain
            assert [i["text"] for i in hookbus.pending("s1")] == ["passive"]
        finally:
            main.sessions.pop("s1", None)
