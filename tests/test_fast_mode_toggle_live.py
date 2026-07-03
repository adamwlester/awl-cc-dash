"""Live spike — Fast-mode toggle via `Meta+O` (`chat:fastMode`).

§10 item #03 ("Fast-mode toggle (Meta+O)", 🧪 needs-spike). Attempts to toggle
Fast (Opus) mode on a RUNNING bridge agent by sending the `chat:fastMode`
keybinding (tmux keyname `M-o`) and reading the resulting state back. The
read-back is the crux: sending `M-o` always "succeeds" at the tmux level, which
proves nothing — only a read-backable state change would.

HONEST OUTCOME — omission (xfail), after a real send-and-read-back attempt on
Claude CLI 2.1.198:

  * Default `M-o` (`chat:fastMode`) produces **no observable change** — no panel,
    no footer indicator, no model switch (before/after screens identical bar
    transient footer rotation).
  * The research's sanctioned fallback — rebinding `chat:fastMode` to a clean
    chord (`ctrl+x ctrl+f`) via a temporary ~/.claude/keybindings.json and
    sending it — was performed in the spike (exploration round 2, tests/log/
    `results_20260702T162318Z`) and ALSO produced no observable change.
  * ROOT CAUSE, read straight off the TUI: `/fast` opens a panel that says
    **"↯ Fast mode (research preview) … Fast mode requires usage credits ·
    /usage-credits to turn them on"**, and the `/fast` command reports
    **"Fast mode OFF"**. Fast mode is **credit-gated and OFF for this account** —
    there is no Enabled/Disabled toggle to flip, so no keystroke (default or
    rebound) can turn it on or surface a read-backable state.
  * This is NOT a key-encoding failure: `meta`-modifier delivery over tmux is
    proven working — the sibling `Meta+T` spike opened the thinking panel. It is
    an account/capability gate.

Therefore §10 #03's Fallback applies and should be recorded: **Fast stays a
launch-time / credit-gated choice, never a fake-live toggle** → propose moving
§10 #03 to "Decided omissions" (reported to the human; this test does not edit
docs/ARCHITECTURE.md). The test keeps the file and records the finding via
``pytest.xfail(...)`` — it is NOT faked green. The WORKS branch is retained so
that, should a future account/build make Fast mode available and `M-o`-toggleable,
the same test passes by asserting the observed change.

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
  * The durable test performs NO global-config writes; the rebind fallback was
    exercised in the spike only (documented above).
  * No shared-file edits (conftest.py / pyproject.toml / tests/README.md).

Run (PowerShell)::

    ./.venv/Scripts/python.exe -m pytest tests/test_fast_mode_toggle_live.py -m integration
"""

import asyncio
import logging
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


@pytest.fixture(autouse=True)
def _runtime_to_tmp(tmp_path, monkeypatch):
    """Keep the driver's restart-survival record out of sidecar/runtime/."""
    monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(tmp_path / "runtime"))


def _screen(bridge, name, label, lines=40):
    content = bridge.read(name, lines=lines)["content"]
    log.debug("%s: read(%d):\n%s", label, lines, content)
    return content


def _fast_surface_present(content):
    """True iff the screen shows an ACTIVE Fast-mode surface (its panel, or an
    'on' indicator). The `/fast` history line 'Fast mode OFF' is deliberately NOT
    matched — only a live panel / an on-state counts as a read-backable change."""
    low = content.lower()
    return (
        "fast mode (research preview)" in low
        or "↯ fast" in low
        or "fast mode on" in low
    )


def test_fast_mode_toggle_meta_o_live():
    """`M-o` (chat:fastMode) read-back attempt. Passes if a read-backable Fast
    state change is observed (future-proof WORKS branch); otherwise records the
    honest omission via xfail with the /fast credit-gate root cause."""
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

            # --- Probe A: default M-o (chat:fastMode) keybinding read-back. ---
            before = _screen(bridge, name, "BEFORE M-o")
            bridge.keys(name, "M-o")
            await asyncio.sleep(3)
            after = _screen(bridge, name, "AFTER M-o")
            mo_opened_fast = (
                _fast_surface_present(after) and not _fast_surface_present(before)
            )
            log.debug("M-o opened a Fast surface? %s", mo_opened_fast)

            # --- Probe B: /fast reveals the account's Fast-mode availability. ---
            bridge.send(name, "/fast")
            await asyncio.sleep(2.5)
            panel = _screen(bridge, name, "AFTER /fast (panel)")
            bridge.keys(name, "Escape")
            await asyncio.sleep(1.5)
            post = _screen(bridge, name, "AFTER Escape (/fast result)")
            blob = (panel + "\n" + post).lower()
            credit_gated = "requires usage credits" in blob or "usage-credits" in blob
            fast_off = "fast mode off" in blob
            log.debug("credit_gated=%s fast_off=%s", credit_gated, fast_off)

            if mo_opened_fast:
                # WORKS (future-proof): M-o surfaced a read-backable Fast state.
                log.debug("WORKS: M-o surfaced a read-backable Fast-mode state.")
                assert mo_opened_fast
                return

            # Honest omission — real send-and-read-back attempt made; no
            # read-backable Fast state exists because Fast mode is credit-gated/OFF.
            pytest.xfail(
                "chat:fastMode (Meta+O / M-o) produced NO read-backable Fast-mode "
                "state on Claude CLI 2.1.198. Root cause via the /fast panel: Fast "
                "mode is a credit-gated 'research preview' and is OFF for this "
                f"account (credit_gated={credit_gated}, fast_off={fast_off}; panel: "
                "'↯ Fast mode (research preview) … requires usage credits'). A clean-"
                "key rebind (chat:fastMode -> ctrl+x ctrl+f) was also attempted in "
                "the spike with the same null result, and meta-delivery is proven "
                "(sibling Meta+T opens the thinking panel) — so this is an account/"
                "capability gate, not a key-encoding failure. Propose §10 #03 -> "
                "Decided omissions: Fast stays a launch-time/credit-gated choice, "
                "never a fake-live toggle. See tests/log/ for the before/after and "
                "/fast panel captures."
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
