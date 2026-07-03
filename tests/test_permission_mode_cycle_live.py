"""Live spike — mid-run permission-mode change via Shift+Tab (`BTab`).

§10 item #01 ("Mid-run permission-mode change", 🧪 needs-spike). Proves — or
disproves — that an agent's permission mode can be changed LIVE, mid-run, by
cycling `Shift+Tab` (tmux keyname `BTab`) through the bridge, and that the new
mode ACTUALLY CHANGES BEHAVIOR (an auto-accepted Write stops raising a
permission prompt), not just the on-screen indicator.

Two-layer read-back is the whole point (see §5 of the build prompt):
  * Layer 1 — indicator: the status line flips to "accept edits on".
  * Layer 2 — behavior: a subsequent Write raises NO permission prompt and the
    file lands unattended. Suppression has regressed on some builds (#52822,
    #55255), so the indicator alone is not enough — we verify BEHAVIOR too.

Mechanism authority: dev/notes/research/claude-code-mode-control-research.md,
Question 1. The cycle order with no optional modes pre-armed is exactly
`default -> acceptEdits -> plan`, so ONE `BTab` from `default` reaches
`acceptEdits`. This test deliberately does NOT pre-arm bypass/auto (no
`--allow-dangerously-skip-permissions`), keeping its cycle deterministic.

This drives the raw `TmuxBridge` directly (no `BridgeDriver`, no HTTP layer):
the observable we verify is a raw screen-state (`status()["state"]`), which the
bridge exposes and needs no async event pump.

Parallel-safe isolation (CRITICAL — sibling agents may run their own live
sessions concurrently):
  * ONE new file only; uniquely-named, slug-prefixed session `permmode-<uuid8>`.
  * NEVER `tmux kill-server` / `bridge.shutdown()` — tear down ONLY this
    session via `bridge.close(name)` + `rm -rf` this test's own diag dir.
  * Does NOT use conftest's `bridge` fixture (its setup AND teardown call
    `_kill_all_tmux()` = `tmux kill-server`, which would kill siblings). We
    instantiate our OWN `TmuxBridge()` for both WSL shell helpers and driving.
  * No shared-file edits (conftest.py / pyproject.toml / tests/README.md).

Run (PowerShell)::

    ./.venv/Scripts/python.exe -m pytest tests/test_permission_mode_cycle_live.py -m integration
"""

import logging
import sys
import time
import uuid
from pathlib import Path

import pytest

# The tmux bridge package lives at the repo root (`bridge/`). Make it importable
# explicitly so this file stands alone (resolved relative to this file, so cwd
# doesn't matter). conftest also inserts the repo root, but we don't rely on it.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from bridge import TmuxBridge  # noqa: E402

log = logging.getLogger(__name__)

pytestmark = [pytest.mark.integration, pytest.mark.slow]


def _cat(bridge, path):
    """Read a file inside WSL, or the sentinel __MISSING__ if absent."""
    return bridge._run(f"cat {path} 2>/dev/null || echo __MISSING__")


def _status_becomes(bridge, name, target, timeout=20.0, interval=0.5):
    """Poll `status(name)["state"]` until it equals `target`; True if reached.

    Every read is logged at DEBUG so a failure is diagnosable from tests/log/.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            st = bridge.status(name)
            state = st.get("state")
        except Exception as e:  # pragma: no cover - environment dependent
            log.debug("status(%s) raised: %s", name, e)
            state = None
        log.debug("status(%s) -> %s (want %s)", name, state, target)
        if state == target:
            return True
        time.sleep(interval)
    return False


def _status_never(bridge, name, forbidden, duration=20.0, interval=0.5):
    """Poll for `duration`s asserting `status[state]` NEVER equals `forbidden`.

    Returns (ok, last_state). ok is False the moment `forbidden` is observed.
    """
    deadline = time.time() + duration
    last = None
    while time.time() < deadline:
        try:
            st = bridge.status(name)
            last = st.get("state")
        except Exception as e:  # pragma: no cover - environment dependent
            log.debug("status(%s) raised: %s", name, e)
            last = None
        log.debug("status(%s) -> %s (forbidding %s)", name, last, forbidden)
        if last == forbidden:
            return False, last
        time.sleep(interval)
    return True, last


def _indicator_shows(bridge, name, needle, tries=10, interval=0.5):
    """Retry-read the screen until `needle` (case-insensitive) appears.

    Returns (found, last_content) so the caller can assert and log evidence.
    """
    needle_l = needle.lower()
    content = ""
    for _ in range(tries):
        content = bridge.read(name, lines=20)["content"]
        log.debug("read(%s) tail:\n%s", name, content[-600:])
        if needle_l in content.lower():
            return True, content
        time.sleep(interval)
    return False, content


def test_permission_mode_cycle_btab_live():
    """One `BTab` from `default` reaches `acceptEdits` (indicator flips) AND
    acceptEdits genuinely suppresses a subsequent Write's permission prompt."""
    bridge = TmuxBridge()
    name = f"permmode-{uuid.uuid4().hex[:8]}"
    diag = f"/home/lester/awl-permmode-{uuid.uuid4().hex[:8]}"
    bridge._run(f"mkdir -p {diag}")

    try:
        # 2) Launch tab-less in `default` mode; wait for the TUI to finish loading.
        info = bridge.create(name, cwd=diag, permission_mode="default", show=False)
        log.debug("created session: %s", info)
        bridge.wait_idle(name, timeout=60, interval=1.0)

        # 3) Baseline: default mode DOES prompt on a Write.
        bridge.send(
            name,
            "Create a file named a.txt containing exactly the word banana. "
            "Use the Write tool. Do not do anything else.",
        )
        assert _status_becomes(bridge, name, "permission_prompt", timeout=40), (
            "default mode never raised a permission_prompt for the Write — "
            "the session did not start in a prompting mode"
        )
        # Dismiss the prompt (deny) and settle back to a safe idle state.
        bridge.keys(name, "Escape")
        bridge.wait_idle(name, timeout=30, interval=1.0)
        # a.txt must NOT exist (the write was denied).
        assert _cat(bridge, f"{diag}/a.txt") == "__MISSING__", (
            "a.txt was written despite denying the default-mode prompt"
        )

        # 4) Confirm indicator baseline — still in default, so "accept edits on"
        #    is absent.
        baseline = bridge.read(name, lines=20)["content"]
        log.debug("baseline screen tail:\n%s", baseline[-600:])
        assert "accept edits on" not in baseline.lower(), (
            "indicator already shows acceptEdits before any BTab was sent"
        )

        # 5) Idle-gate, then cycle exactly one step (default -> acceptEdits).
        assert _status_becomes(bridge, name, "idle", timeout=20), (
            "session not idle before sending BTab (would land a key mid-turn)"
        )
        bridge.keys(name, "BTab")
        time.sleep(1)

        # 6) Layer 1 — read the indicator back (retry).
        found, after = _indicator_shows(bridge, name, "accept edits on", tries=10)
        assert found, (
            "indicator did not advance to 'accept edits on' after one BTab "
            "(likely a BTab-encoding misfire; research fallback = rebind "
            f"chat:cycleMode). Last screen tail:\n{after[-600:]}"
        )

        # 7) Layer 2 (THE crux) — verify BEHAVIOR: a Write now raises NO prompt
        #    and the file lands unattended.
        assert _status_becomes(bridge, name, "idle", timeout=20), (
            "session not idle before the acceptEdits Write test"
        )
        bridge.send(
            name,
            "Create a file named b.txt containing exactly the word cherry. "
            "Use the Write tool. Do not do anything else.",
        )
        no_prompt, last_state = _status_never(
            bridge, name, "permission_prompt", duration=20
        )
        assert no_prompt, (
            "acceptEdits did NOT suppress the Write prompt — a permission_prompt "
            f"fired (last state {last_state!r}). Live-confirmed suppression "
            "regression on this build (cf. #52822 / #55255)."
        )
        # ... and the write actually landed with the expected contents.
        wrote = False
        for _ in range(40):
            if _cat(bridge, f"{diag}/b.txt") == "cherry":
                wrote = True
                break
            time.sleep(0.5)
        assert wrote, (
            "b.txt never landed with 'cherry' under acceptEdits — the mode "
            "flipped the indicator but the unattended write did not complete"
        )
        log.debug(
            "WORKS: one BTab default->acceptEdits (indicator + behavior) on this build"
        )
    finally:
        # Tear down ONLY this session + this test's own diag dir. NEVER kill-server.
        try:
            bridge.close(name)
        except Exception as e:  # pragma: no cover - best effort
            log.debug("close(%s) failed: %s", name, e)
        try:
            bridge._run(f"rm -rf {diag}")
        except Exception as e:  # pragma: no cover - best effort
            log.debug("rm -rf %s failed: %s", diag, e)
