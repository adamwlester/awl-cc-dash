"""Hermetic unit tests for the run-state arbiter (ARCHITECTURE §7.4/§7.17, §11 #21).

The decided contract this file encodes:

  * Hook-pushed run-state is **authoritative-when-fresh**: within the freshness
    window `effective()` reports the pushed phase/tool (source="push"); past it
    the screen-poll status is the floor (source="poll") — HTTP-hook failures are
    silent, so push can never fully replace the poll.
  * `permission_mode` is **event-specific**: only mode-bearing events update it —
    a `Notification` payload never sets or clears the mode (the spike-mapped gap).
  * **Ordering/dedup under concurrent load**: ingests are serialized under a lock
    with a monotonic seq; an exact redelivery (same event + prompt_id +
    tool_use_id) dedups to None; concurrent threads never corrupt the record.
  * `SubagentStart`/`SubagentStop` feed the per-parent **subagent registry**
    (agent_id / type / transcript_path / running-vs-stopped) — the roster's
    active-vs-quiet signal — and count as freshness for the parent.

No WSL, no network — pure module behavior (plus a thread hammer).
"""

import sys
import threading
from pathlib import Path

import pytest

_SIDECAR = Path(__file__).resolve().parent.parent / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))

import runstate  # noqa: E402


@pytest.fixture(autouse=True)
def _clean():
    runstate.reset()
    yield
    runstate.reset()


class TestIngest:
    def test_mode_bearing_events_update_mode(self):
        runstate.ingest("a1", "PreToolUse",
                        {"permission_mode": "acceptEdits", "tool_name": "Bash"})
        rec = runstate.get("a1")
        assert rec["permission_mode"] == "acceptEdits"
        assert rec["current_tool"] == "Bash"
        assert rec["phase"] == "running"

    def test_notification_never_touches_mode_or_phase(self):
        runstate.ingest("a1", "PostToolUse", {"permission_mode": "plan"})
        runstate.ingest("a1", "Notification", {"permission_mode": "bypassPermissions"})
        rec = runstate.get("a1")
        # Notification carries no trustworthy mode — even if a field appears,
        # it is ignored; phase is not moved either.
        assert rec["permission_mode"] == "plan"
        assert rec["phase"] == "running"
        assert rec["last_event"] == "Notification"   # freshness still counts

    def test_stop_clears_tool_and_goes_idle(self):
        runstate.ingest("a1", "PreToolUse", {"tool_name": "Edit"})
        runstate.ingest("a1", "Stop", {"permission_mode": "default"})
        rec = runstate.get("a1")
        assert rec["phase"] == "idle"
        assert rec["current_tool"] is None
        assert rec["permission_mode"] == "default"

    def test_prompt_id_recorded(self):
        runstate.ingest("a1", "UserPromptSubmit", {"prompt_id": "p-77"})
        assert runstate.get("a1")["prompt_id"] == "p-77"

    def test_exact_redelivery_dedups(self):
        p = {"prompt_id": "p1", "tool_use_id": "t1", "tool_name": "Bash"}
        assert runstate.ingest("a1", "PostToolUse", p) is not None
        assert runstate.ingest("a1", "PostToolUse", p) is None   # dropped
        # A different boundary (new tool_use_id) is NOT deduped.
        assert runstate.ingest("a1", "PostToolUse",
                               {"prompt_id": "p1", "tool_use_id": "t2"}) is not None

    def test_events_without_identity_never_dedup(self):
        assert runstate.ingest("a1", "Stop", {}) is not None
        assert runstate.ingest("a1", "Stop", {}) is not None


class TestEffective:
    def test_fresh_push_wins(self):
        runstate.ingest("a1", "PreToolUse", {"tool_name": "Read",
                                             "permission_mode": "default"})
        eff = runstate.effective("a1", "idle")
        assert eff["source"] == "push"
        assert eff["phase"] == "running"       # push beats the poll's "idle"
        assert eff["current_tool"] == "Read"

    def test_stale_push_falls_back_to_poll(self):
        runstate.ingest("a1", "PreToolUse", {"tool_name": "Read"})
        eff = runstate.effective("a1", "idle", freshness_s=0.0)
        assert eff["source"] == "poll"
        assert eff["phase"] == "idle"          # the poll floor
        assert eff["current_tool"] is None     # stale tool not asserted
        assert eff["age_s"] is not None

    def test_never_pushed_is_pure_poll(self):
        eff = runstate.effective("ghost", "running")
        assert eff == {"source": "poll", "age_s": None, "phase": "running",
                       "permission_mode": None, "current_tool": None,
                       "prompt_id": None}


class TestConcurrency:
    def test_thread_hammer_keeps_record_coherent(self):
        # 8 threads × 50 interleaved ingests: the lock + monotonic seq must keep
        # the record coherent (no lost updates, seq strictly increasing, no
        # exception under contention).
        errors: list[Exception] = []

        def hammer(n: int):
            try:
                for i in range(50):
                    runstate.ingest("a1", "PreToolUse",
                                    {"tool_name": f"T{n}-{i}",
                                     "prompt_id": "p", "tool_use_id": f"{n}-{i}",
                                     "permission_mode": "default"})
            except Exception as e:  # pragma: no cover - failure path
                errors.append(e)

        threads = [threading.Thread(target=hammer, args=(n,)) for n in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert not errors
        rec = runstate.get("a1")
        assert rec["seq"] >= 400          # every ingest took a unique seq
        assert rec["phase"] == "running"
        assert rec["current_tool"].startswith("T")

    def test_dedup_under_concurrent_redelivery(self):
        # The same delivery fired from many threads lands exactly once.
        results = []
        payload = {"prompt_id": "p9", "tool_use_id": "t9", "tool_name": "Bash"}

        def fire():
            results.append(runstate.ingest("a1", "PostToolUse", payload))

        threads = [threading.Thread(target=fire) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        applied = [r for r in results if r is not None]
        assert len(applied) == 1


class TestSubagents:
    def test_start_stop_registry(self):
        runstate.ingest_subagent("parent", "SubagentStart", {
            "agent_id": "sub-1", "agent_type": "Explore",
            "transcript_path": "/home/u/.claude/projects/x/sub-1.jsonl",
        })
        live = runstate.subagents_live("parent")
        assert live[0]["status"] == "running"
        assert live[0]["type"] == "Explore"
        runstate.ingest_subagent("parent", "SubagentStop", {
            "agent_id": "sub-1", "last_assistant_message": "done!",
        })
        live = runstate.subagents_live("parent")
        assert live[0]["status"] == "stopped"
        assert live[0]["last_assistant_message"] == "done!"
        assert live[0]["transcript_path"].endswith("sub-1.jsonl")

    def test_subagent_push_counts_as_parent_freshness(self):
        runstate.ingest_subagent("parent", "SubagentStart", {"agent_id": "s"})
        assert runstate.effective("parent", "idle")["source"] == "push"

    def test_missing_agent_id_is_tolerated(self):
        assert runstate.ingest_subagent("parent", "SubagentStart", {}) is None
        assert runstate.subagents_live("parent") == []

    def test_drop_agent_forgets_everything(self):
        runstate.ingest("a1", "Stop", {})
        runstate.ingest_subagent("a1", "SubagentStart", {"agent_id": "s"})
        runstate.drop_agent("a1")
        assert runstate.get("a1") is None
        assert runstate.subagents_live("a1") == []
