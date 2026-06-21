"""Integration tests for the ``cc_tmux_bridge`` library.

These are real integration tests: they spin up actual Claude Code TUI sessions
in WSL2/tmux, send real prompts, and read real screens. Nothing is mocked.

Because the suite is a stateful, ordered flow (create -> send -> ... -> shutdown)
it relies on the ``live_session`` fixture for the shared 'test-1' session and on
pytest's in-file definition order. Run it with::

    pytest tests/ -m integration        # from the repo root
    tests/run.ps1                        # convenience wrapper (resolves the venv)

Failures are easiest to diagnose from the timestamped DEBUG log in tests/log/.
"""

import logging
import os
import time

import pytest

from cc_tmux_bridge.bridge import TmuxBridgeError

log = logging.getLogger("tests.tmux_bridge")

# Whole module hits real WSL/tmux + a live model, and is slow by nature.
pytestmark = [pytest.mark.integration, pytest.mark.slow]


# -----------------------------------------------------------------------------
# Core operations
# -----------------------------------------------------------------------------

def test_list_empty(bridge):
    """Before any session is created, the list is empty."""
    assert bridge.list() == []


def test_session_created(bridge, live_session):
    """The live_session fixture successfully created 'test-1'."""
    names = [s["name"] for s in bridge.list()]
    log.debug("active sessions after create: %s", names)
    assert live_session in names


def test_create_duplicate_errors(bridge, live_session):
    with pytest.raises(TmuxBridgeError, match="already exists"):
        bridge.create(live_session)


def test_read(bridge, live_session):
    result = bridge.read(live_session, lines=20)
    log.debug("read screen tail: %r", result["content"][-300:])
    assert result["status"] == "ok"
    assert result["lines"] > 0
    assert len(result["content"]) > 0


def test_send_and_response(bridge, live_session):
    prompt = "Reply with exactly: TEST_SEND_OK"
    result = bridge.send(live_session, prompt)
    assert result["status"] == "sent"
    assert result["textLength"] == len(prompt)

    # Poll for the marker rather than sleeping a fixed interval — model latency
    # varies with machine load, so a fixed wait is flaky.
    log.info("polling up to 60s for model response...")
    res = bridge.watch(live_session, "TEST_SEND_OK", timeout=60)
    log.debug("matched: %r", res["match"])
    assert "TEST_SEND_OK" in res["match"]


def test_send_no_enter(bridge, live_session):
    result = bridge.send(live_session, "typed but not sent", press_enter=False)
    assert result["status"] == "sent"


def test_keys_ctrl_c(bridge, live_session):
    result = bridge.keys(live_session, "C-c")
    assert result["status"] == "sent"
    assert result["keys"] == ["C-c"]


def test_keys_no_args_errors(bridge, live_session):
    with pytest.raises(TmuxBridgeError, match="No keys specified"):
        bridge.keys(live_session)


def test_send_to_nonexistent_errors(bridge):
    with pytest.raises(TmuxBridgeError, match="not found"):
        bridge.send("nonexistent-session", "hello")


# -----------------------------------------------------------------------------
# Session management
# -----------------------------------------------------------------------------

def test_rename_roundtrip(bridge, live_session):
    result = bridge.rename(live_session, "test-renamed")
    assert result["status"] == "renamed"
    names = [s["name"] for s in bridge.list()]
    assert "test-renamed" in names and live_session not in names
    # rename back so later tests still find 'test-1'
    bridge.rename("test-renamed", live_session)


def test_resume_existing(bridge, live_session):
    result = bridge.resume(live_session)
    assert result["status"] == "resumed"


def test_resume_new(bridge):
    result = bridge.resume("test-resume-new", cwd="C:/Users/lester")
    assert result["status"] == "created"


def test_status(bridge, live_session):
    time.sleep(5)
    result = bridge.status(live_session)
    log.debug("status: %s", result)
    assert result["status"] == "ok"
    assert result["state"] in ("idle", "generating", "permission_prompt", "unknown")


# -----------------------------------------------------------------------------
# Multi-agent
# -----------------------------------------------------------------------------

def test_batch_create(bridge):
    agents = [
        {"name": "batch-a", "cwd": "C:/Users/lester"},
        {"name": "batch-b", "cwd": "C:/Users/lester"},
    ]
    results = bridge.batch_create(agents)
    assert len(results) == 2
    assert all(r["status"] == "created" for r in results)


def test_broadcast(bridge):
    time.sleep(8)  # let the two TUIs load
    results = bridge.broadcast(["batch-a", "batch-b"], "Reply with: ACK")
    assert len(results) == 2
    assert all(r["status"] == "sent" for r in results)


def test_interrupt(bridge):
    result = bridge.interrupt("batch-a")
    assert result["status"] == "sent"
    assert result["keys"] == ["C-c"]


# -----------------------------------------------------------------------------
# Output & monitoring
# -----------------------------------------------------------------------------

def test_scrollback(bridge, live_session):
    result = bridge.scrollback(live_session)
    assert result["status"] == "ok"
    assert result["lines"] > 0


def test_watch(bridge, live_session):
    bridge.send(live_session, "Reply with exactly: WATCH_OK")
    result = bridge.watch(live_session, "WATCH_OK", timeout=30)
    assert result["status"] == "matched"
    assert "WATCH_OK" in result["match"]


def test_watch_timeout(bridge, live_session):
    with pytest.raises(TmuxBridgeError, match="Timed out"):
        bridge.watch(live_session, "THIS_WILL_NEVER_MATCH_xyz123", timeout=3, interval=1)


def test_wait_idle(bridge, live_session):
    time.sleep(5)
    # Capture the raw screen the heuristic sees — invaluable when idle
    # detection drifts as the TUI layout changes.
    screen = bridge.read(live_session, lines=15)
    log.debug("pre-wait_idle raw screen:\n%s", screen["content"])
    # Generous timeout: TUI startup + model latency vary a lot with machine load.
    result = bridge.wait_idle(live_session, timeout=90)
    log.debug("wait_idle result: %s", result)
    assert result["status"] in ("idle", "permission_prompt")


def test_export_scrollback(bridge, live_session, tmp_path):
    export_path = os.path.join(str(tmp_path), "test_export_tmp.txt")
    result = bridge.export(live_session, export_path, mode="scrollback")
    assert result["status"] == "exported"
    assert os.path.exists(export_path)
    assert os.path.getsize(export_path) > 0


# -----------------------------------------------------------------------------
# Visibility & lifecycle
# -----------------------------------------------------------------------------

def test_show(bridge, live_session):
    result = bridge.show(live_session)
    assert result["status"] == "shown"


def test_wt_tab_attached(bridge, live_session):
    time.sleep(2)
    sessions = [s for s in bridge.list() if s["name"] == live_session]
    assert len(sessions) == 1
    assert sessions[0]["attached"] is True


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

def test_set_cwd(bridge):
    bridge.set_cwd("C:/some/path")
    assert bridge._default_cwd == "C:/some/path"
    bridge.set_cwd(None)


def test_set_model(bridge):
    bridge.set_model("sonnet")
    assert bridge._default_model == "sonnet"
    bridge.set_model(None)


def test_mcp_sync(bridge):
    result = bridge.mcp_sync()
    log.debug("mcp_sync result: %s", result)
    assert result["status"] == "ok"
    assert len(result["synced"]) > 0
    assert "playwright" in result["skipped"]  # known incompatible


# -----------------------------------------------------------------------------
# JSONL transcript
# -----------------------------------------------------------------------------

def test_read_log(bridge, live_session):
    time.sleep(5)
    entries = bridge.read_log(live_session, last_n=5)
    assert len(entries) > 0
    assert len({e.get("type") for e in entries}) > 0
