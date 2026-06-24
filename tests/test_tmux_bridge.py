"""Integration tests for the ``bridge`` library (tmux Claude Code control).

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

from bridge.bridge import TmuxBridgeError

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


def test_fresh_dir_comes_up_idle(bridge):
    """A session created in a fresh, untrusted dir must clear the folder-trust
    gate during create() and reach idle — not hang on the gate."""
    import uuid

    fresh = f"/home/lester/awl-fresh-{uuid.uuid4().hex[:8]}"
    bridge._run(f"mkdir -p {fresh}")
    name = "fresh-dir-session"
    try:
        bridge.create(name, cwd=fresh)  # create() now clears the trust gate
        result = bridge.wait_idle(name, timeout=60)
        log.debug("fresh-dir wait_idle: %s", result)
        assert result["status"] == "idle"
    finally:
        try:
            bridge.close(name)
        except TmuxBridgeError:
            pass
        bridge._run(f"rm -rf {fresh}")


def test_status(bridge, live_session):
    time.sleep(5)
    result = bridge.status(live_session)
    log.debug("status: %s", result)
    assert result["status"] == "ok"
    assert result["state"] in ("idle", "generating", "permission_prompt", "unknown")


def test_turn_streams_generating_then_idle(bridge, live_session):
    """A real turn must be observed as 'generating' while running, then 'idle'.

    The old detector false-reported 'idle' throughout generation, so the loose
    assertions elsewhere passed even with the bug. This asserts the real
    transition: a long-enough turn is caught mid-flight as 'generating' and
    settles to 'idle' afterwards.

    The prompt deliberately asks for a long answer so generation lasts well
    over the status() poll round-trip (~1s over WSL); a quick reply could
    finish between polls and never be sampled as 'generating'.

    Reliability: uses the warm shared 'test-1' deliberately. It is created once
    at suite start and is long past the node-hook-slowed startup render by the
    time this runs, so its sends submit reliably — unlike a freshly-created
    session, whose splash is still up ~25s in and silently swallows the Enter.
    Two cheap, evidence-backed guards remain:
      * Ctrl+U first. 'test-1' is reused in declaration order and upstream tests
        leave stray text in its input box (e.g. test_send_no_enter's "typed but
        not sent"); without clearing, our prompt appends to that junk and never
        submits. (Verified: Ctrl+U empties the line; Escape does NOT and can
        recall the last message — so don't use it.)
      * Split submit. Sending the literal text and Enter back-to-back can race so
        the Enter lands before the text registers; type the prompt, let it
        render, then press Enter separately.
    The assertions are unchanged and not weakened: a broken detector would never
    report 'generating', so these guards make the real transition observable
    without being able to mask a detection bug.
    """
    prompt = (
        "Write roughly 600 words explaining how tmux sessions, windows, and "
        "panes relate to each other. Take your time and be thorough."
    )
    bridge.keys(live_session, "C-u")        # clear any leftover input
    time.sleep(0.5)
    bridge.send(live_session, prompt, press_enter=False)
    time.sleep(1.0)                          # let the text render before submit
    bridge.keys(live_session, "Enter")

    saw_generating = False
    deadline = time.time() + 30
    while time.time() < deadline:
        state = bridge.status(live_session)["state"]
        if state == "generating":
            saw_generating = True
            break
        time.sleep(0.3)
    log.debug("observed generating during turn: %s", saw_generating)
    assert saw_generating, "never observed 'generating' state during a live turn"

    result = bridge.wait_idle(live_session, timeout=90)
    log.debug("post-turn wait_idle: %s", result)
    assert result["status"] == "idle"


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
    # Runs right after test_show, which calls show() to open a WT tab attached to
    # 'test-1'. This asserts that manual-attach path works (the session reports an
    # attached client) — it is NOT about create()'s now-opt-in tab.
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
