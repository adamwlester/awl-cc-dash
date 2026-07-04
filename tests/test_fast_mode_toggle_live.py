"""Live spike — Fast-mode toggle via `Meta+O` (`chat:fastMode`) + `Space`.

§10 item #03 ("Fast-mode toggle (Meta+O)"). Proves that Fast (Opus) mode can be
controlled on a RUNNING bridge agent from the keyboard and that the resulting
state is READ-BACKABLE — the crux that was previously blocked.

WHAT THE LIVE SPIKE FOUND (Claude CLI 2.1.201, account with Fast credits enabled
2026-07-04):

  * `Meta+O` (tmux `M-o`, `chat:fastMode`) opens the **"↯ Fast mode (research
    preview)"** panel on the running session::

        ↯ Fast mode (research preview)
        High-speed mode for Opus 4.8. Draws from usage credits at a higher rate.
          Fast mode  OFF  $10/$50 per Mtok
        Learn more: https://code.claude.com/docs/en/fast-mode

  * With the panel open, **`Space` toggles** the state — the panel's
    `Fast mode  OFF/ON  $10/$50 per Mtok` line flips and is a plain-text scrape
    (`capture-pane -p -J` strips ANSI). `Enter`/`Escape` just CLOSE the panel;
    `Space` is the state lever. A clean there-and-back flip (OFF → ON → OFF)
    proves the state is both settable and read-backable, i.e. `set_fast()` can be
    wired as open-panel → read → Space-to-target → close (mirrors the proven
    `Meta+T` thinking control, §10 #02).

  * EARLIER (credit-gated account, CLI 2.1.198): the same `M-o` opened the panel
    but it read `Fast mode OFF` with **"requires usage credits"** and no keystroke
    could turn it on — an account/capability gate, not a key-encoding failure
    (meta-delivery was already proven by the sibling `Meta+T` spike). That state
    is still handled honestly below: if the panel reports credit-gated, the test
    `xfail`s rather than faking green.

Drives a `BridgeDriver` (per the build prompt) and reads the screen through a
SELF-OWNED `TmuxBridge` targeting `driver.tmux_name`.

Parallel-safe isolation (CRITICAL — sibling agents may run their own live
sessions concurrently):
  * ONE new file only; the driver's tmux name is `awl-<uuid8>` (unique) and the
    sidecar session id is slug-prefixed `fastmode-<uuid8>`.
  * NEVER `tmux kill-server` / `bridge.shutdown()` — tear down ONLY this session
    via `driver.close()` (+ belt-and-suspenders `bridge.close(name)`) and
    `rm -rf` this test's own diag dir.
  * Does NOT use conftest's `bridge` fixture (its setup AND teardown call
    `_kill_all_tmux()` = `tmux kill-server`, which would kill siblings). We
    instantiate our OWN `TmuxBridge()` for WSL shell helpers and screen reads.
  * Leaves Fast mode OFF before teardown so nothing keeps drawing credits.
  * No shared-file edits (conftest.py / pyproject.toml / tests/README.md).

Run (PowerShell)::

    ./.venv/Scripts/python.exe -m pytest tests/test_fast_mode_toggle_live.py -m integration
"""

import asyncio
import logging
import re
import sys
import uuid
from pathlib import Path

import pytest

# Make the sidecar's modules importable as top-level (it runs with its own dir on
# sys.path, not the repo root) — mirrors the finisher's shim.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SIDECAR = _REPO_ROOT / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))
# The bridge package lives at the repo root; make it importable for our own
# TmuxBridge (screen reads + WSL shell helpers).
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from drivers.bridge import BridgeDriver  # noqa: E402
from drivers.base import DriverConfig  # noqa: E402
from bridge import TmuxBridge  # noqa: E402

log = logging.getLogger(__name__)

pytestmark = [pytest.mark.integration, pytest.mark.slow]

_PANEL_MARKER = "fast mode (research preview)"


@pytest.fixture(autouse=True)
def _runtime_to_tmp(tmp_path, monkeypatch):
    """Keep the driver's restart-survival record out of sidecar/runtime/."""
    monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(tmp_path / "runtime"))


def _screen(bridge, name, label, lines=45):
    content = bridge.read(name, lines=lines)["content"]
    log.debug("%s: read(%d):\n%s", label, lines, content)
    return content


def _fast_panel_state(content):
    """Parse the open "↯ Fast mode (research preview)" panel.

    Returns 'on' / 'off' (from the `Fast mode  ON/OFF  $.../Mtok` line),
    'credit-gated' when the panel reports it needs usage credits, or None when the
    panel isn't open / can't be parsed. The `$/Mtok` line only exists in the OPEN
    panel, so it isn't confused with the closed-state footer 'Fast mode OFF'.
    """
    low = content.lower()
    if _PANEL_MARKER not in low:
        return None
    if "requires usage credits" in low or "usage-credits" in low:
        return "credit-gated"
    for line in content.splitlines():
        if "mtok" not in line.lower():
            continue
        norm = re.sub(r"\s+", " ", line.lower()).strip()
        if "fast mode on" in norm:
            return "on"
        if "fast mode off" in norm:
            return "off"
    return None


def _open_fast_panel(bridge, name, label, tries=14, interval=0.6):
    """Send `M-o`, poll until the Fast panel is open and parseable; return (state, screen)."""
    bridge.keys(name, "M-o")
    content = ""
    for _ in range(tries):
        content = _screen(bridge, name, label)
        st = _fast_panel_state(content)
        if st is not None:
            return st, content
        import time
        time.sleep(interval)
    return None, content


def _space_and_read(bridge, name, label, tries=14, interval=0.6):
    """With the panel OPEN, press `Space` (the toggle) and read the state back."""
    bridge.keys(name, "Space")
    content = ""
    for _ in range(tries):
        import time
        time.sleep(interval)
        content = _screen(bridge, name, label)
        st = _fast_panel_state(content)
        if st in ("on", "off", "credit-gated"):
            return st, content
    return None, content


def test_fast_mode_toggle_meta_o_live():
    """`M-o` opens the Fast-mode panel; `Space` toggles OFF<->ON, read-backable
    from the panel, with a there-and-back flip proving repeatability. On a
    credit-gated account the panel reports it and the test xfails honestly."""
    bridge = TmuxBridge()
    diag = f"/home/lester/awl-fastmode-{uuid.uuid4().hex[:8]}"
    bridge._run(f"mkdir -p {diag}")
    events: list[dict] = []

    async def flow():
        driver = BridgeDriver(
            DriverConfig(cwd=diag, permission_mode="default"),
            events.append,
            session_id=f"fastmode-{uuid.uuid4().hex[:8]}",
        )
        name = None
        try:
            await driver.start()
            name = driver.tmux_name
            log.debug("driver.tmux_name=%s (unique awl-<uuid8>)", name)
            await asyncio.sleep(3)  # let the TUI paint

            # 1) Open the panel and read the CURRENT Fast state.
            state1, screen1 = _open_fast_panel(bridge, name, "open #1 (baseline)")
            if state1 == "credit-gated":
                pytest.xfail(
                    "Fast mode is credit-gated on this account — the `M-o` panel "
                    "reports 'requires usage credits'. Meta-delivery is proven "
                    "(sibling Meta+T opens the thinking panel), so this is an "
                    "account/capability gate, not a key-encoding failure. Enable "
                    "Fast credits (/usage-credits) to run the flip proof. See "
                    "tests/log/ for the panel capture."
                )
            assert state1 in ("on", "off"), (
                "M-o did not open a parseable '↯ Fast mode (research preview)' "
                f"panel — the mechanism this spike relies on is absent. Screen "
                f"tail:\n{screen1[-600:]}"
            )
            opposite = "on" if state1 == "off" else "off"

            # 2) Toggle with Space and read back — the crux: the keystroke-driven
            #    change must be observable in the panel.
            state2, screen2 = _space_and_read(bridge, name, "after Space #1 (toggle)")
            if state2 == "credit-gated":
                pytest.xfail(
                    "Fast toggle blocked: panel went credit-gated on Space. Enable "
                    "Fast credits to run the flip proof."
                )
            assert state2 == opposite, (
                f"Space did not toggle Fast to {opposite!r} / was not read-backable: "
                f"panel shows {state2!r}. Screen:\n{screen2[-600:]}"
            )

            # 3) Flip BACK — proves repeatability in both directions, not a one-way
            #    screen artifact.
            state3, screen3 = _space_and_read(bridge, name, "after Space #2 (flip back)")
            assert state3 == state1, (
                f"flipping Fast back to {state1!r} did not read back cleanly: panel "
                f"shows {state3!r}. Screen:\n{screen3[-600:]}"
            )

            # 4) Ensure we leave Fast OFF (never leave it drawing credits), then
            #    close the panel so the session ends clean.
            if state3 == "on":
                _space_and_read(bridge, name, "after Space #3 (force OFF)")
            bridge.keys(name, "Escape")
            log.debug(
                "WORKS: M-o opens the Fast panel; Space flips state read-back "
                "%s -> %s -> %s (settable + read-backable, repeatable).",
                state1, state2, state3,
            )
        finally:
            try:
                await driver.close()
            except Exception as e:  # pragma: no cover - best effort
                log.debug("driver.close() failed: %s", e)
            if name:
                try:
                    bridge.close(name)
                except Exception as e:  # pragma: no cover - best effort
                    log.debug("bridge.close(%s) failed: %s", name, e)
            try:
                bridge._run(f"rm -rf {diag}")
            except Exception as e:  # pragma: no cover - best effort
                log.debug("rm -rf %s failed: %s", diag, e)

    asyncio.run(flow())
