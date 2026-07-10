"""Hermetic unit tests for the sidecar's session bookkeeping + endpoint wiring.

Pure: no driver, no WSL2/tmux, no model, no HTTP server (async endpoint
functions are called directly via ``asyncio.run``). Proves:

  * the permission wiring — a ``permission_request`` event flips
    ``has_pending_permission`` and stores the detail; ``permission_resolved``
    clears it;
  * default driver selection (``bridge`` unless explicitly overridden) and
    agent identity assignment;
  * the cross-agent event envelope, the merged ``/events/history`` filters,
    the per-agent prompt queue/dispositions, hook-boundary Inject delivery,
    and reply-to link relays;
  * **the Library endpoints on the per-doc sidecar store (§8.5)** — GET
    ``/library/reviews`` runs the legacy migration then aggregates sidecars;
    POST resolves the doc (plans/ → docs/ → root; 404 when absent) and writes
    the sidecar; document create (409 on exists) / delete / rename and the
    comment add/resolve endpoints, including the 400 guards that scope every
    write to ``<project>/.awl-cc-dash/``; and the ``subdir=plans|docs`` store
    listing with its legacy ``<root>/<subdir>`` fallback.

These carry neither the ``integration`` nor the ``slow`` mark.
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


def test_response_card_coalesces_per_agent():
    """Response card (§7.8): every completed turn raises/updates ONE coalesced
    per-agent card ("a run ended with output the operator has not reviewed"),
    counting unreviewed runs — never a second open card."""
    import inbox
    inbox.reset()
    try:
        s = _session()
        s.handle_event({"type": "status_change", "status": "running"})
        s.handle_event({"type": "status_change", "status": "idle"})
        cards = [i for i in inbox.items_for("s1") if i["type"] == "response"]
        assert len(cards) == 1
        assert cards[0]["data"]["runs"] == 1
        # A second completed turn updates the SAME card (coalesced), runs=2.
        s.handle_event({"type": "status_change", "status": "running"})
        s.handle_event({"type": "status_change", "status": "idle"})
        cards = [i for i in inbox.items_for("s1") if i["type"] == "response"]
        assert len(cards) == 1
        assert cards[0]["data"]["runs"] == 2
        # Completable via the standard resolve; the next turn opens a fresh card.
        inbox.resolve_item("s1", cards[0]["id"])
        s.handle_event({"type": "status_change", "status": "running"})
        s.handle_event({"type": "status_change", "status": "idle"})
        cards = [i for i in inbox.items_for("s1") if i["type"] == "response"]
        assert len(cards) == 1 and cards[0]["data"]["runs"] == 1
    finally:
        inbox.reset()


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
            lk = links.add_link(a="A", b="B", relationship="direct", trigger="queue")
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
            lk = links.add_link(a="A", b="B", relationship="direct",
                                end_after_exchanges=1)  # two-way: cap at 2 messages
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
            lk = links.add_link(a="A", b="B", relationship="direct", trigger="inject")
            b.answering_source, b.answering_link = "A", lk.id
            _finish_turn(b, "mid-run reply")
            main._maybe_relay_reply(b)
            # inject trigger -> A's hook inbox, NOT A's prompt queue
            assert len(a.prompt_queue) == 0
            assert [i["text"] for i in hookbus.pending("A")] == ["mid-run reply"]
        finally:
            main.sessions.pop("A", None); main.sessions.pop("B", None)

    def test_one_way_cap_burns_per_fire(self):
        # §7.6 End-After, direction-aware: on a one-way link EVERY fire is one
        # exchange, so a cap of 1 ends the link after a single relay.
        a, b = _agent("A"), _agent("B")
        main.sessions["A"], main.sessions["B"] = a, b
        try:
            lk = links.add_link(a="A", b="B", direction="a2b",
                                relationship="direct", end_after_exchanges=1)
            a.answering_source, a.answering_link = "B", lk.id
            _finish_turn(a, "one and only fire")
            main._maybe_relay_reply(a)
            assert lk.messages == 1 and lk.exchanges == 1
            assert not lk.active                 # single fire hit the cap
            assert b.answering_source is None    # no alternation set up
        finally:
            main.sessions.pop("A", None); main.sessions.pop("B", None)

    def test_piggyback_trigger_parks_instead_of_enqueueing(self):
        # A piggybacked DM reads as a deferred reply: the fire parks on the
        # peer's pending list and never initiates a turn.
        a, b = _agent("A"), _agent("B")
        main.sessions["A"], main.sessions["B"] = a, b
        try:
            lk = links.add_link(a="A", b="B", relationship="direct",
                                trigger="piggyback")
            b.answering_source, b.answering_link = "A", lk.id
            _finish_turn(b, "deferred reply")
            main._maybe_relay_reply(b)
            assert len(a.prompt_queue) == 0      # nothing enqueued
            assert [p["text"] for p in links.pending_piggyback("A")] == ["deferred reply"]
        finally:
            main.sessions.pop("A", None); main.sessions.pop("B", None)


# ---------------------------------------------------------------------------
# Link endpoints — the §7.6 one-relationship contract at the API seam
# ---------------------------------------------------------------------------

class TestLinkEndpoints:
    def test_create_defaults_trigger_per_relationship(self):
        direct = asyncio.run(main.create_link(main.CreateLinkRequest(a="A", b="B")))
        assert direct["relationship"] == "direct"
        assert direct["trigger"] == "queue"
        shared = asyncio.run(main.create_link(main.CreateLinkRequest(
            a="A", b="B", relationship="shared")))
        assert shared["relationship"] == "shared"
        assert shared["trigger"] == "piggyback"

    def test_create_explicit_trigger_kept(self):
        out = asyncio.run(main.create_link(main.CreateLinkRequest(
            a="A", b="B", relationship="shared", trigger="inject")))
        assert out["trigger"] == "inject"

    def test_create_legacy_list_relationship_takes_first(self):
        # Pre-split clients sent a multi-select list; the first element wins.
        out = asyncio.run(main.create_link(main.CreateLinkRequest(
            a="A", b="B", relationship=["shared", "direct"])))
        assert out["relationship"] == "shared"
        assert out["trigger"] == "piggyback"     # default follows the taken value
        empty = asyncio.run(main.create_link(main.CreateLinkRequest(
            a="A", b="B", relationship=[])))
        assert empty["relationship"] == "direct"

    def test_create_invalid_relationship_400(self):
        from fastapi import HTTPException as _HTTPExc
        with pytest.raises(_HTTPExc) as exc:
            asyncio.run(main.create_link(main.CreateLinkRequest(
                a="A", b="B", relationship="bogus")))
        assert exc.value.status_code == 400


# ---------------------------------------------------------------------------
# Shared-context fire + piggyback delivery (§7.6)
# ---------------------------------------------------------------------------

import watermark  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_watermark():
    watermark.reset()
    yield
    watermark.reset()


def _complete_turn(s, text):
    """Drive a full driver-observed turn: running -> assistant text -> idle
    (the idle transition is what fires the relay + shared-context engines)."""
    s.handle_event({"type": "status_change", "status": "running",
                    "timestamp": "t"})
    s.push_event({"type": "assistant",
                  "content": [{"type": "text", "text": text}], "timestamp": "t"})
    s.handle_event({"type": "status_change", "status": "idle", "timestamp": "t"})


class TestSharedContextFire:
    def test_shared_fire_parks_piggyback_with_watermark(self):
        import inbox
        inbox.reset()
        a, b = _agent("A"), _agent("B")
        main.sessions["A"], main.sessions["B"] = a, b
        try:
            lk = links.add_link(a="A", b="B", relationship="shared")  # piggyback default
            _complete_turn(a, "the update")
            # parked for B, never enqueued (piggyback never initiates a turn)
            assert [p["text"] for p in links.pending_piggyback("B")] == ["the update"]
            assert len(b.prompt_queue) == 0
            # the fire counted + the shared watermark advanced to this turn
            assert lk.messages == 1
            assert watermark.get("shared:A:B") == 1
            assert any(e["type"] == "shared_context_fire" for e in a.events)
            # an idle re-emission does NOT double-park (watermark dedup)
            a.handle_event({"type": "status_change", "status": "idle",
                            "timestamp": "t"})
            assert len(links.pending_piggyback("B")) == 1
        finally:
            main.sessions.pop("A", None); main.sessions.pop("B", None)
            inbox.reset()

    def test_shared_fire_respects_direction(self):
        import inbox
        inbox.reset()
        a, b = _agent("A"), _agent("B")
        main.sessions["A"], main.sessions["B"] = a, b
        try:
            links.add_link(a="A", b="B", direction="b2a", relationship="shared")
            _complete_turn(a, "should not share")   # a2b is not allowed on b2a
            assert links.pending_piggyback("B") == []
        finally:
            main.sessions.pop("A", None); main.sessions.pop("B", None)
            inbox.reset()

    def test_shared_fire_queue_trigger_takes_queue_path(self):
        import inbox
        inbox.reset()
        a, b = _agent("A"), _agent("B")
        b.status = "running"     # keep the enqueued share visible (no auto-flush)
        main.sessions["A"], main.sessions["B"] = a, b
        try:
            links.add_link(a="A", b="B", relationship="shared", trigger="queue")
            _complete_turn(a, "queued share")
            assert [e["prompt"] for e in b.prompt_queue] == ["queued share"]
            assert b.prompt_queue[0]["source"] == "A"
            assert links.pending_piggyback("B") == []
        finally:
            main.sessions.pop("A", None); main.sessions.pop("B", None)
            inbox.reset()

    def test_flush_prepends_piggyback_block_once(self):
        b = _agent("B")
        b.status = "idle"
        main.sessions["B"] = b
        try:
            links.park_piggyback("B", source="A", link_id="lnk1",
                                 text="peer update")
            b.enqueue({"prompt": "do the thing", "source": "user",
                       "recipients": ["B"]}, "queue")
            asyncio.run(main._flush_queue(b))
            assert len(b.driver.sent) == 1
            sent = b.driver.sent[0]
            # ONE bounded block, prepended; the user's prompt rides after it
            assert sent.startswith("[Shared context from linked agents")
            assert "(from A) peer update" in sent
            assert sent.endswith("do the thing")
            # consumed exactly once + surfaced on the feed
            assert links.pending_piggyback("B") == []
            assert any(e["type"] == "piggyback_delivered" for e in b.events)
            # the next flush carries no stale block
            b.status = "idle"
            b.enqueue({"prompt": "second send", "source": "user",
                       "recipients": ["B"]}, "queue")
            asyncio.run(main._flush_queue(b))
            assert b.driver.sent[1] == "second send"
        finally:
            main.sessions.pop("B", None)


# ---------------------------------------------------------------------------
# Identity editing + name registration (§7.5 / §11 #14)
# ---------------------------------------------------------------------------

import deletion  # noqa: E402
import runtime_store  # noqa: E402
from drivers.base import DriverConfig  # noqa: E402


class _FakeIdentityDriver(_FakeDriver):
    """A fake driver shaped like the bridge driver's identity surface: holds the
    persisted roster ``_record``, a ``config`` (whose identity the endpoint
    keeps in sync), and a capability-gated ``set_display_name``."""

    def __init__(self, identity=None):
        super().__init__()
        self.renames: list[str] = []
        self.config = DriverConfig(identity=identity)
        self._record = {"session_id": "s1", "tmux_name": "awl-x",
                        "driver": "bridge", "identity": identity}

    def supports(self, cap):
        return cap == "set_display_name"

    async def set_display_name(self, name):
        self.renames.append(name)


class TestIdentityEndpoint:
    def _wire(self, monkeypatch, identity=None):
        ident = identity or assign_identity({"name": "ivy"}, 0)
        s = _session()
        s.identity = dict(ident)
        drv = _FakeIdentityDriver(identity=dict(ident))
        s.driver = drv
        main.sessions["s1"] = s
        saved: list[dict] = []
        monkeypatch.setattr(runtime_store, "save_record",
                            lambda rec: saved.append(dict(rec)))
        return s, drv, saved

    def test_merge_updates_persists_and_returns(self, monkeypatch):
        s, drv, saved = self._wire(monkeypatch)
        try:
            out = asyncio.run(main.update_identity("s1", main.IdentityUpdateRequest(
                role="Reviewer", color="#123456")))
            assert out["identity"]["role"] == "Reviewer"
            assert out["identity"]["color"] == "#123456"
            assert out["identity"]["name"] == "ivy"     # untouched fields survive
            assert s.identity == out["identity"]
            # persisted through the roster record (what reconnect reads back)
            assert saved and saved[-1]["identity"]["role"] == "Reviewer"
            assert drv._record["identity"]["role"] == "Reviewer"
            assert drv.config.identity["role"] == "Reviewer"
            assert drv.renames == []                    # no name change -> no /rename
        finally:
            main.sessions.pop("s1", None)

    def test_name_edit_drives_rename(self, monkeypatch):
        s, drv, _ = self._wire(monkeypatch)
        try:
            out = asyncio.run(main.update_identity(
                "s1", main.IdentityUpdateRequest(name="rex")))
            assert out["identity"]["name"] == "rex"
            assert drv.renames == ["rex"]               # /rename on the live session
            # same-name edit is a no-op rename
            asyncio.run(main.update_identity(
                "s1", main.IdentityUpdateRequest(name="rex")))
            assert drv.renames == ["rex"]
        finally:
            main.sessions.pop("s1", None)

    def test_rename_capability_gated(self, monkeypatch):
        # A driver without set_display_name (e.g. the sdk driver) still merges +
        # persists — the rename is simply skipped, never an error.
        s, drv, _ = self._wire(monkeypatch)
        s.driver = _FakeDriver()                        # supports() -> False
        try:
            out = asyncio.run(main.update_identity(
                "s1", main.IdentityUpdateRequest(name="rex")))
            assert out["identity"]["name"] == "rex"
            assert s.identity["name"] == "rex"
        finally:
            main.sessions.pop("s1", None)

    def test_retired_number_refused_400(self, monkeypatch):
        s, drv, saved = self._wire(monkeypatch)
        deletion.retire_number(7)
        try:
            with pytest.raises(HTTPException) as exc:
                asyncio.run(main.update_identity(
                    "s1", main.IdentityUpdateRequest(number=7)))
            assert exc.value.status_code == 400
            assert s.identity["number"] != 7            # nothing merged
            assert saved == []                          # nothing persisted
            # a non-retired number is accepted
            out = asyncio.run(main.update_identity(
                "s1", main.IdentityUpdateRequest(number=8)))
            assert out["identity"]["number"] == 8
        finally:
            main.sessions.pop("s1", None)
            deletion.reset()

    def test_unknown_session_404(self):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(main.update_identity(
                "nope", main.IdentityUpdateRequest(role="x")))
        assert exc.value.status_code == 404


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


# ---------------------------------------------------------------------------
# Library endpoints — the per-doc sidecar store (§8.5). Async endpoint
# functions called directly (asyncio.run), all file I/O on tmp_path.
# ---------------------------------------------------------------------------

import json  # noqa: E402

from fastapi import HTTPException  # noqa: E402

import library  # noqa: E402


def _proj(tmp_path):
    """A tmp project with a .git marker so storage.project_root pins to it."""
    proj = tmp_path / "proj"
    (proj / ".git").mkdir(parents=True)
    return proj


def _store_md(proj, subdir, name, body="# Doc\n"):
    d = proj / ".awl-cc-dash" / subdir
    d.mkdir(parents=True, exist_ok=True)
    f = d / name
    f.write_text(body, encoding="utf-8")
    return f


class TestLibraryReviewEndpoints:
    def test_get_runs_migration_then_aggregates(self, tmp_path):
        proj = _proj(tmp_path)
        _store_md(proj, "plans", "phase-1.md")
        legacy = proj / ".awl-cc-dash" / "plan-reviews.json"
        legacy.write_text(json.dumps(
            {"phase-1.md": {"owner": "coder-01", "comments": "old note"}}),
            encoding="utf-8")
        out = asyncio.run(main.library_reviews(cwd=str(proj)))
        # the legacy entry landed in a per-doc sidecar and is aggregated back
        assert out["phase-1.md"]["review"]["owner"] == "coder-01"
        assert [c["text"] for c in out["phase-1.md"]["comments"]] == ["old note"]
        assert (proj / ".awl-cc-dash" / "plans" / "phase-1.meta.json").is_file()
        # migration never re-runs: the legacy file is renamed .migrated
        assert not legacy.exists()
        assert legacy.with_name("plan-reviews.json.migrated").is_file()

    def test_post_writes_a_sidecar(self, tmp_path):
        proj = _proj(tmp_path)
        md = _store_md(proj, "plans", "phase-1.md")
        out = asyncio.run(main.library_set_review(main.ReviewRequest(
            cwd=str(proj), filename="phase-1.md", owner="coder-01",
            state="in_review", verdict="approve", verdict_by="user",
            comments=["looks good"])))
        assert library.meta_path(md).is_file()
        assert out["review"]["verdict"] == "approve"
        assert out["review"]["verdict_by"] == "user"
        assert [c["text"] for c in out["comments"]] == ["looks good"]
        # and the content file stayed pristine (§8.5 rule 1)
        assert md.read_text(encoding="utf-8") == "# Doc\n"

    def test_post_404_when_doc_missing(self, tmp_path):
        proj = _proj(tmp_path)
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.library_set_review(main.ReviewRequest(
                cwd=str(proj), filename="ghost.md", owner="x")))
        assert ei.value.status_code == 404

    def test_post_resolves_docs_and_root_docs_too(self, tmp_path):
        # Documents get the same review treatment as Plans (§8.5 rule 4).
        proj = _proj(tmp_path)
        _store_md(proj, "docs", "notes.md")
        out = asyncio.run(main.library_set_review(main.ReviewRequest(
            cwd=str(proj), filename="notes.md", state="commented")))
        assert out["review"]["state"] == "commented"


class TestLibraryDocumentEndpoints:
    def test_create_then_409_on_duplicate(self, tmp_path):
        proj = _proj(tmp_path)
        out = asyncio.run(main.library_create_document(main.DocumentCreateRequest(
            cwd=str(proj), filename="notes.md", content="# N\n")))
        assert (proj / ".awl-cc-dash" / "docs" / "notes.md").is_file()
        assert out["filename"] == "notes.md"
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.library_create_document(main.DocumentCreateRequest(
                cwd=str(proj), filename="notes.md", content="again")))
        assert ei.value.status_code == 409

    def test_create_400_on_path_escape(self, tmp_path):
        proj = _proj(tmp_path)
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.library_create_document(main.DocumentCreateRequest(
                cwd=str(proj), filename="../escape.md", content="x")))
        assert ei.value.status_code == 400

    def test_delete_removes_doc_and_meta(self, tmp_path):
        proj = _proj(tmp_path)
        md = _store_md(proj, "docs", "gone.md")
        library.set_doc_review(md, owner="a")
        out = asyncio.run(main.library_delete_document(path=str(md), cwd=str(proj)))
        assert not md.exists() and not library.meta_path(md).exists()
        assert len(out["deleted"]) == 2

    def test_delete_400_outside_store(self, tmp_path):
        proj = _proj(tmp_path)
        outside = proj / "readme.md"
        outside.write_text("keep", encoding="utf-8")
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.library_delete_document(path=str(outside), cwd=str(proj)))
        assert ei.value.status_code == 400
        assert outside.is_file()

    def test_delete_404_when_missing(self, tmp_path):
        proj = _proj(tmp_path)
        ghost = proj / ".awl-cc-dash" / "docs" / "ghost.md"
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.library_delete_document(path=str(ghost), cwd=str(proj)))
        assert ei.value.status_code == 404

    def test_rename_moves_the_pair(self, tmp_path):
        proj = _proj(tmp_path)
        md = _store_md(proj, "plans", "draft.md")
        library.set_doc_review(md, owner="a")
        out = asyncio.run(main.library_rename_document(main.DocumentRenameRequest(
            cwd=str(proj), path=str(md), new_filename="final.md")))
        plans = proj / ".awl-cc-dash" / "plans"
        assert (plans / "final.md").is_file() and (plans / "final.meta.json").is_file()
        assert not md.exists()
        assert out["new"] == str(plans / "final.md")

    def test_rename_400_outside_store(self, tmp_path):
        proj = _proj(tmp_path)
        outside = proj / "readme.md"
        outside.write_text("x", encoding="utf-8")
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.library_rename_document(main.DocumentRenameRequest(
                cwd=str(proj), path=str(outside), new_filename="y.md")))
        assert ei.value.status_code == 400

    def test_listing_subdir_prefers_store_then_falls_back_legacy(self, tmp_path):
        proj = _proj(tmp_path)
        # No store plans dir yet -> the legacy <root>/plans listing still works.
        legacy_dir = proj / "plans"
        legacy_dir.mkdir()
        (legacy_dir / "old.md").write_text("x", encoding="utf-8")
        names = {e["filename"] for e in asyncio.run(
            main.library_documents(cwd=str(proj), subdir="plans"))}
        assert names == {"old.md"}
        # Once the store dir exists it wins over the legacy location.
        _store_md(proj, "plans", "new.md")
        names = {e["filename"] for e in asyncio.run(
            main.library_documents(cwd=str(proj), subdir="plans"))}
        assert names == {"new.md"}

    def test_listing_no_subdir_keeps_root_readonly_browse(self, tmp_path):
        proj = _proj(tmp_path)
        (proj / "readme.md").write_text("x", encoding="utf-8")
        _store_md(proj, "docs", "stored.md")
        names = {e["filename"] for e in asyncio.run(
            main.library_documents(cwd=str(proj)))}
        assert names == {"readme.md"}   # root browse only; the store isn't merged in


class TestLibraryCommentEndpoints:
    def test_add_comment_with_anchor(self, tmp_path):
        proj = _proj(tmp_path)
        md = _store_md(proj, "docs", "notes.md")
        out = asyncio.run(main.library_add_comment(main.CommentRequest(
            cwd=str(proj), path=str(md), text="tighten", author="user",
            anchor_quote="quoted bit", anchor_heading="Goals")))
        assert out["id"] == "c1"
        stored = library.load_meta(md)["comments"][0]
        assert stored["anchor_quote"] == "quoted bit"
        assert stored["anchor_heading"] == "Goals"

    def test_add_comment_400_outside_store(self, tmp_path):
        proj = _proj(tmp_path)
        outside = proj / "readme.md"
        outside.write_text("x", encoding="utf-8")
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.library_add_comment(main.CommentRequest(
                cwd=str(proj), path=str(outside), text="nope", author="user")))
        assert ei.value.status_code == 400

    def test_add_comment_404_when_md_missing(self, tmp_path):
        proj = _proj(tmp_path)
        ghost = proj / ".awl-cc-dash" / "docs" / "ghost.md"
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.library_add_comment(main.CommentRequest(
                cwd=str(proj), path=str(ghost), text="x", author="user")))
        assert ei.value.status_code == 404

    def test_resolve_comment_roundtrip_and_404(self, tmp_path):
        proj = _proj(tmp_path)
        md = _store_md(proj, "docs", "notes.md")
        library.add_comment(md, text="fix", author="user")
        out = asyncio.run(main.library_resolve_comment(main.CommentResolveRequest(
            cwd=str(proj), path=str(md), comment_id="c1")))
        assert out["status"] == "resolved"
        assert library.load_meta(md)["comments"][0]["resolved"] is True
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.library_resolve_comment(main.CommentResolveRequest(
                cwd=str(proj), path=str(md), comment_id="c99")))
        assert ei.value.status_code == 404

    def test_resolve_400_outside_store(self, tmp_path):
        proj = _proj(tmp_path)
        outside = proj / "readme.md"
        outside.write_text("x", encoding="utf-8")
        with pytest.raises(HTTPException) as ei:
            asyncio.run(main.library_resolve_comment(main.CommentResolveRequest(
                cwd=str(proj), path=str(outside), comment_id="c1")))
        assert ei.value.status_code == 400
