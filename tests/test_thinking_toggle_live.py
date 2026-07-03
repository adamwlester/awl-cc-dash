"""Live spike — thinking-mode control via `Meta+T` (`chat:thinkingToggle`).

§10 item #02 ("Thinking-mode toggle (Meta+T)", 🧪 needs-spike). Proves that
thinking can be controlled on a RUNNING Claude Code agent by sending the
`chat:thinkingToggle` keybinding (tmux keyname `M-t`) through the bridge, and
that the resulting state is READ-BACKABLE.

WHAT THE LIVE SPIKE ACTUALLY FOUND (Claude CLI 2.1.198), refining the hypothesis
in the build prompt:

  * `M-t` is NOT a blind, absolute-less toggle. It opens an interactive
    **"Toggle thinking mode" panel** on the running session::

        ❯ 1. Enabled ✔  Claude will think before responding
          2. Disabled   Claude will respond without extended thinking
          Enter to confirm · Esc to cancel

    The `✔` marks the CURRENT state, and the state is set ABSOLUTELY by choosing
    option 1/2 + Enter. This is BETTER than the hypothesised blind toggle: the
    state is both directly READ-BACKABLE and SETTABLE from the screen (ANSI is
    stripped by `capture-pane -p -J`, so the panel is a plain-text scrape) —
    exactly what §10 #02's POC needed to establish. Because the panel is modal,
    any text `send()` while it is open lands in the panel, not as a prompt.

  * The specifically-hypothesised observable — `thinking`-type blocks in the
    JSONL transcript — did NOT hold on this build: with thinking **Enabled** by
    default, a step-by-step reasoning turn on the default model (**Fable 5**, a
    fast model) emitted ZERO `thinking` transcript blocks (captured in the
    exploratory run, tests/log/). So transcript thinking-block presence is a
    model-dependent, unreliable observable here; the **panel** is the reliable
    one. (`has_thinking()` below is retained to document that attempt.)

Observable asserted (the read-back that is the crux): the panel's Enabled/Disabled
selection (which line carries the `✔`) changes when we set the opposite option
and re-open — a clean there-and-back flip proves the state is both settable and
read-backable via `M-t`. This unblocks wiring `set_thinking()` as
open-panel → read → select-target → confirm, and advertising the capability.

Shape chosen: **pure-bridge (synchronous)** — `keys()`/`read()`/`close()` are
blocking bridge calls; no async driver behaviour is needed, so no `asyncio.run`.

Parallel-safe isolation (CRITICAL — sibling agents may run their own live
sessions concurrently):
  * ONE new file only; uniquely-named, slug-prefixed session `think-<uuid8>`.
  * NEVER `tmux kill-server` / `bridge.shutdown()` — tear down ONLY this session
    via `bridge.close(name)` + `rm -rf` this test's own diag dir.
  * Does NOT use conftest's `bridge` fixture (its setup AND teardown call
    `_kill_all_tmux()` = `tmux kill-server`, which would kill siblings). We
    instantiate our OWN `TmuxBridge()` for both WSL shell helpers and driving.
  * No shared-file edits (conftest.py / pyproject.toml / tests/README.md).

Run (PowerShell)::

    ./.venv/Scripts/python.exe -m pytest tests/test_thinking_toggle_live.py -m integration
"""

import logging
import sys
import time
import uuid
from pathlib import Path

import pytest

# The tmux bridge package lives at the repo root (`bridge/`). Make it importable
# explicitly so this file stands alone (resolved relative to this file).
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from bridge import TmuxBridge  # noqa: E402

log = logging.getLogger(__name__)

pytestmark = [pytest.mark.integration, pytest.mark.slow]

_PANEL_MARKER = "toggle thinking mode"
_CHECKS = ("✔", "✓")  # the mark on the currently-active option


def has_thinking(entries):
    """Count `thinking`-type content blocks across assistant entries.

    Retained to document the transcript-observable attempt (see module docstring):
    each assistant entry's ``message.content`` is a list of blocks and a thinking
    block is a dict with ``block["type"] == "thinking"``. Returns the count.
    """
    n = 0
    for e in entries:
        if e.get("type") != "assistant":
            continue
        content = (e.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "thinking":
                n += 1
    return n


def _read_screen(bridge, name, lines=25):
    return bridge.read(name, lines=lines)["content"]


def _thinking_panel_state(content):
    """Parse the open "Toggle thinking mode" panel → 'enabled' / 'disabled' / None.

    The `✔` marks the active option; whichever of the Enabled/Disabled lines
    carries it is the current state. Returns None when the panel isn't open or
    can't be parsed.
    """
    if _PANEL_MARKER not in content.lower():
        return None
    state = None
    for line in content.splitlines():
        if not any(c in line for c in _CHECKS):
            continue
        low = line.lower()
        if "enabled" in low:
            state = "enabled"
        elif "disabled" in low:
            state = "disabled"
    return state


def _open_panel_and_read(bridge, name, label, tries=14, interval=0.5):
    """Send `M-t`, poll until the panel is open and parseable; return (state, screen)."""
    bridge.keys(name, "M-t")
    content = ""
    for _ in range(tries):
        content = _read_screen(bridge, name)
        st = _thinking_panel_state(content)
        log.debug("%s: panel_state=%s screen tail:\n%s", label, st, content[-500:])
        if st is not None:
            return st, content
        time.sleep(interval)
    return None, content


def _select_in_open_panel(bridge, name, target):
    """With the panel OPEN, select 'enabled'(1)/'disabled'(2) + Enter to apply.

    Numbered-menu selection by digit is the proven pattern in this build (the
    startup bypass gate selects "2" + Enter the same way).
    """
    digit = "1" if target == "enabled" else "2"
    bridge.keys(name, digit)
    time.sleep(0.4)
    bridge.keys(name, "Enter")
    time.sleep(1.2)


def test_thinking_toggle_meta_t_live():
    """`M-t` opens the Toggle-thinking-mode panel; the Enabled/Disabled state is
    both settable and read-backable, with a clean there-and-back flip proving
    repeatability. (Mechanism refinement of the transcript-block hypothesis —
    see module docstring.)"""
    bridge = TmuxBridge()
    name = f"think-{uuid.uuid4().hex[:8]}"
    diag = f"/home/lester/awl-think-{uuid.uuid4().hex[:8]}"
    bridge._run(f"mkdir -p {diag}")

    try:
        info = bridge.create(name, cwd=diag, show=False)
        log.debug("created session: %s", info)
        bridge.wait_idle(name, timeout=60, interval=1.0)

        # 1) Open the panel and read the CURRENT thinking state.
        state1, screen1 = _open_panel_and_read(bridge, name, "open #1 (baseline)")
        assert state1 in ("enabled", "disabled"), (
            "M-t did not open a parseable 'Toggle thinking mode' panel — the "
            "mechanism this spike relies on is absent on this build. Last screen "
            f"tail:\n{screen1[-500:]}"
        )
        opposite = "disabled" if state1 == "enabled" else "enabled"

        # 2) Set the OPPOSITE state from within the open panel, then re-open and
        #    read back — the crux: the keystroke-driven change must be observable.
        _select_in_open_panel(bridge, name, opposite)
        state2, screen2 = _open_panel_and_read(bridge, name, "open #2 (after set opposite)")
        assert state2 == opposite, (
            f"setting thinking to {opposite!r} via M-t panel did not take / was "
            f"not read-backable: panel still shows {state2!r}. Screen:\n{screen2[-500:]}"
        )

        # 3) Flip BACK to the original — proves the control is repeatable in both
        #    directions, not a one-way screen artifact.
        _select_in_open_panel(bridge, name, state1)
        state3, screen3 = _open_panel_and_read(bridge, name, "open #3 (after flip back)")
        assert state3 == state1, (
            f"flipping thinking back to {state1!r} did not read back cleanly: "
            f"panel shows {state3!r}. Screen:\n{screen3[-500:]}"
        )

        # Leave the panel closed (Escape) so the session ends idle. (close() kills
        # it regardless, but keep the teardown tidy.)
        bridge.keys(name, "Escape")
        log.debug(
            "WORKS: M-t opens the thinking panel; state read/set/read-back "
            "flipped %s -> %s -> %s (settable + read-backable, repeatable).",
            state1, state2, state3,
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
