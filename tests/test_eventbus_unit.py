"""Hermetic unit tests for the cross-agent event bus.

Pure logic — no driver, no SSE transport, no live agent. Proves the event
envelope (id / agent_id / seq / ts / source / recipients), the deterministic-id
dedup (re-poll -> no-op), the bounded global ring, and the server-side From/To
filter + scroll-backfill. These carry neither the integration nor the slow mark.
"""

import sys
from pathlib import Path

_SIDECAR = Path(__file__).resolve().parent.parent / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))

import eventbus  # noqa: E402
import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _clean_bus():
    eventbus.reset()
    yield
    eventbus.reset()


# ---------------------------------------------------------------------------
# Monotonic seq — the ordering key ("never parse the id for order")
# ---------------------------------------------------------------------------

class TestSeq:
    def test_next_seq_is_monotonic(self):
        a, b, c = eventbus.next_seq(), eventbus.next_seq(), eventbus.next_seq()
        assert a < b < c

    def test_reset_restarts_seq(self):
        eventbus.next_seq(); eventbus.next_seq()
        eventbus.reset()
        assert eventbus.next_seq() == 1


# ---------------------------------------------------------------------------
# Envelope stamping (id/agent_id/seq/ts + source/recipients addressing)
# ---------------------------------------------------------------------------

class TestStamp:
    def test_stamps_full_envelope_with_defaults(self):
        seen = set()
        ev = eventbus.stamp({"type": "assistant"}, agent_id="ag1", emitted_ids=seen)
        assert ev["agent_id"] == "ag1"
        assert isinstance(ev["seq"], int) and ev["seq"] >= 1
        assert ev["id"]
        assert ev["ts"]
        assert ev["source"] == "ag1"           # default source = the agent
        assert ev["recipients"] == ["user"]      # default recipients

    def test_deterministic_id_from_transcript_anchor(self):
        seen = set()
        ev = eventbus.stamp(
            {"type": "assistant", "anchor": "uuid-123", "source_kind": "t"},
            agent_id="ag1", emitted_ids=seen,
        )
        # id = {agent_id}:{source_kind}:{anchor} — deterministic, not seq-derived.
        assert ev["id"] == "ag1:t:uuid-123"

    def test_anchored_event_dedups_on_repoll(self):
        seen = set()
        first = eventbus.stamp(
            {"type": "assistant", "anchor": "uuid-9", "source_kind": "t"},
            agent_id="ag1", emitted_ids=seen,
        )
        # Re-polling the same transcript entry (same anchor) is a no-op.
        dup = eventbus.stamp(
            {"type": "assistant", "anchor": "uuid-9", "source_kind": "t"},
            agent_id="ag1", emitted_ids=seen,
        )
        assert first is not None
        assert dup is None

    def test_synthesized_events_never_dedup(self):
        seen = set()
        a = eventbus.stamp({"type": "status_change", "status": "idle"},
                           agent_id="ag1", emitted_ids=seen)
        b = eventbus.stamp({"type": "status_change", "status": "idle"},
                           agent_id="ag1", emitted_ids=seen)
        # No anchor -> seq-based unique ids -> both emitted (distinct transitions).
        assert a is not None and b is not None
        assert a["id"] != b["id"]

    def test_preset_source_and_recipients_preserved(self):
        seen = set()
        ev = eventbus.stamp(
            {"type": "assistant", "source": "user", "recipients": ["ag2", "scratch"]},
            agent_id="ag1", emitted_ids=seen,
        )
        # A caller (link fire / user send) may pre-address an event; stamp keeps it.
        assert ev["source"] == "user"
        assert ev["recipients"] == ["ag2", "scratch"]

    def test_ts_taken_from_existing_timestamp(self):
        seen = set()
        ev = eventbus.stamp(
            {"type": "assistant", "timestamp": "2026-06-30T00:00:00"},
            agent_id="ag1", emitted_ids=seen,
        )
        assert ev["ts"] == "2026-06-30T00:00:00"


# ---------------------------------------------------------------------------
# From/To filter (recipients drives delivery, not visibility)
# ---------------------------------------------------------------------------

class TestFilter:
    def test_no_filter_passes_everything(self):
        ev = {"source": "ag1", "recipients": ["user"]}
        assert eventbus.event_matches(ev, None, None) is True

    def test_source_filter(self):
        ev = {"source": "ag1", "recipients": ["user"]}
        assert eventbus.event_matches(ev, {"ag1"}, None) is True
        assert eventbus.event_matches(ev, {"ag2"}, None) is False

    def test_recipient_filter_is_any_overlap(self):
        ev = {"source": "ag1", "recipients": ["ag2", "user"]}
        assert eventbus.event_matches(ev, None, {"user"}) is True
        assert eventbus.event_matches(ev, None, {"ag2"}) is True
        assert eventbus.event_matches(ev, None, {"ag9"}) is False

    def test_source_and_recipient_both_apply(self):
        ev = {"source": "ag1", "recipients": ["user"]}
        assert eventbus.event_matches(ev, {"ag1"}, {"user"}) is True
        assert eventbus.event_matches(ev, {"ag1"}, {"ag2"}) is False


# ---------------------------------------------------------------------------
# Global ring + replay/backfill (bounded bus, server-side filtering)
# ---------------------------------------------------------------------------

class TestRingReplay:
    def _publish(self, agent_id, recipients, n=1):
        out = []
        for _ in range(n):
            ev = eventbus.stamp({"type": "assistant", "recipients": recipients},
                                agent_id=agent_id, emitted_ids=set())
            eventbus.publish_global(ev)
            out.append(ev)
        return out

    def test_publish_appends_to_ring_in_order(self):
        self._publish("ag1", ["user"])
        self._publish("ag2", ["user"])
        ring = eventbus.replay()
        assert [e["agent_id"] for e in ring] == ["ag1", "ag2"]
        assert ring[0]["seq"] < ring[1]["seq"]

    def test_replay_since_backfill(self):
        evs = self._publish("ag1", ["user"], n=3)
        cutoff = evs[0]["seq"]
        later = eventbus.replay(since=cutoff)
        # Only events strictly after the cutoff seq come back.
        assert all(e["seq"] > cutoff for e in later)
        assert len(later) == 2

    def test_replay_filters_by_source_and_recipient(self):
        self._publish("ag1", ["user"])
        self._publish("ag2", ["ag1"])
        only_ag1 = eventbus.replay(sources={"ag1"})
        assert [e["agent_id"] for e in only_ag1] == ["ag1"]
        to_ag1 = eventbus.replay(recipients={"ag1"})
        assert [e["agent_id"] for e in to_ag1] == ["ag2"]

    def test_ring_is_bounded(self):
        # The merged history is a bounded ring (NOT the per-session unbounded log).
        assert eventbus.GLOBAL_RING.maxlen is not None
        assert eventbus.GLOBAL_RING.maxlen >= 1000
