"""Live spike — Console mirror: wiring + ANSI-fidelity (§10 item #5).

Two clearly separate parts in ONE file (the "split" spike the §10 item tracks):

* **Gap A — wiring (keystroke passthrough + live mirror).** A literal marker
  typed into a live pane (the same ``send-keys`` path ``POST /console/run`` uses)
  shows up on the very next ``capture-pane`` read and was absent from the
  baseline capture. Proves passthrough + mirror are wired end-to-end below the
  HTTP layer.

* **Gap B — fidelity (ANSI recovery).** The production ``bridge.read()`` runs
  ``capture-pane`` WITHOUT ``-e``, so SGR/ANSI escapes are stripped to plain
  text. Re-capturing the SAME idle (already colored) pane with
  ``capture-pane -e`` re-exposes the raw ``\\x1b[...m`` sequences. Proves the
  styling is *recoverable* — but faithful rendering still needs an xterm.js-class
  terminal renderer in the frontend, which the §10 blocker names and which is
  **out of scope for this backend spike** (that half stays deferred, not failed).

Outcome (see DEVLOG for the run): Gap A passing while Gap B proves the escapes
are recoverable-via-``-e``-only is the legitimate, expected split result.

Parallel-safe: every tmux session is uniquely named (``conmirror-<uuid8>``), we
instantiate our OWN ``TmuxBridge`` (NOT conftest's session-scoped ``bridge``
fixture, whose setup/teardown call ``tmux kill-server`` and would kill sibling
agents' live sessions), and teardown removes ONLY our own session + throwaway
dir. NEVER ``kill-server`` / ``shutdown()``.

Run::

    pytest tests/test_console_mirror_live.py -m integration   # from repo root
"""

import logging
import re
import sys
import time
import uuid
from pathlib import Path

import pytest

# The tmux bridge package lives at the repo root (`bridge/`). Put the repo root
# on sys.path so `from bridge import TmuxBridge` resolves regardless of cwd.
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from bridge import TmuxBridge  # noqa: E402

log = logging.getLogger(__name__)

pytestmark = [pytest.mark.integration, pytest.mark.slow]

SLUG = "conmirror"  # tmux-name + dir prefix — parallel-safe, unique per session


# -----------------------------------------------------------------------------
# Own fixtures — NOT conftest's destructive session-scoped `bridge` fixture.
# -----------------------------------------------------------------------------

@pytest.fixture
def br():
    """Our OWN TmuxBridge. Teardown does NOTHING destructive to the tmux server
    (no kill-server, no shutdown()) — each test removes only its own session."""
    b = TmuxBridge()
    yield b
    # Intentionally no shutdown()/kill-server: sibling agents may be running
    # live sessions on the same tmux server. Per-test teardown closes our own.


@pytest.fixture
def diag_dir(br):
    """A fresh, empty WSL throwaway dir; removed after the test."""
    path = f"/home/lester/awl-{SLUG}-{uuid.uuid4().hex[:8]}"
    br._run(f"mkdir -p {path}")
    yield path
    br._run(f"rm -rf {path}")


def _spawn(br, diag_dir):
    """Spawn a live, TAB-LESS, uniquely-named session and wait for the TUI to be
    ready. create() already clears startup gates and waits for idle; the watch is
    a light readiness backstop (its pattern matches any composed idle prompt)."""
    name = f"{SLUG}-{uuid.uuid4().hex[:8]}"      # unique per test
    br.create(name, cwd=diag_dir, show=False)    # show=False = NO tab (mandatory)
    try:
        br.watch(name, r"(Welcome|❯|for shortcuts|Bypass|>)",
                 timeout=90, interval=1.0)
    except Exception as e:  # noqa: BLE001 — soft readiness guard; create() waited
        log.debug("readiness watch did not match (create already idled): %s", e)
    return name


def _safe_close(br, name):
    """Best-effort teardown of ONLY our own session — never touches the server."""
    if not name:
        return
    try:
        br.close(name)
    except Exception as e:  # noqa: BLE001
        log.debug("close(%s) during teardown was a no-op/failed: %s", name, e)


# -----------------------------------------------------------------------------
# Gap A — wiring: keystroke passthrough + live mirror
# -----------------------------------------------------------------------------

def test_gap_a_keystroke_passthrough_and_mirror(br, diag_dir):
    """A unique literal marker typed into the composer (NO submit) appears in the
    very next capture and was absent from the baseline — passthrough + mirror are
    wired, exactly the send-then-read the console/run endpoint performs."""
    name = None
    try:
        name = _spawn(br, diag_dir)

        # Baseline screen — the marker must NOT already be present here.
        before = br.read(name, lines=40)["content"]

        marker = f"AWL_CONSOLE_MARKER_{uuid.uuid4().hex[:12]}"
        assert marker not in before, "impossible: fresh uuid marker already on screen"

        # Passthrough: same send-keys path `console/run` uses. No Enter, so the
        # result is deterministic and side-effect-free (nothing is submitted).
        br.send(name, marker, press_enter=False)
        time.sleep(1.0)  # match the endpoint's send-then-read pacing

        after = br.read(name, lines=40)["content"]

        # THE CRUX: read the state back from the live pane — the pane changed
        # exactly as driven. Never assert on the value we just sent.
        assert marker in after, (
            f"marker {marker!r} never appeared in the mirror after typing — "
            f"passthrough/mirror wiring is broken. screen tail:\n{after[-500:]}"
        )
        log.debug("Gap A: marker present in mirror; passthrough + read-back wired.")

        # Clean the composer so nothing is left half-typed. Best-effort, no Enter.
        try:
            br.keys(name, "C-u")       # clear the composed line
            br.keys(name, "Escape")    # dismiss any composer state
        except Exception as e:  # noqa: BLE001
            log.debug("composer cleanup was a no-op: %s", e)
        time.sleep(0.5)

        # Optional, secondary (non-fatal): a slash command round-trips like the
        # endpoint does — send `/help`, read back, confirm the screen changed.
        try:
            cleared = br.read(name, lines=40)["content"]
            br.send(name, "/help")     # press_enter=True — submitted, side-effect-free
            time.sleep(1.5)
            helped = br.read(name, lines=40)["content"]
            changed = helped != cleared
            log.debug("Gap A (secondary): /help round-trip changed screen=%s", changed)
        except Exception as e:  # noqa: BLE001
            log.debug("Gap A (secondary): /help round-trip skipped/failed: %s", e)
    finally:
        _safe_close(br, name)


# -----------------------------------------------------------------------------
# Gap B — fidelity: ANSI recoverable ONLY with `capture-pane -e`
# -----------------------------------------------------------------------------

def test_gap_b_ansi_recoverable_only_with_e(br, diag_dir):
    """The production read() path (no `-e`) drops SGR escapes; re-capturing the
    SAME idle colored pane with `capture-pane -e` re-exposes the raw `\\x1b[...m`
    sequences. Proves fidelity is recoverable — via `-e` PLUS a frontend renderer,
    which is out of scope for this backend spike."""
    name = None
    try:
        name = _spawn(br, diag_dir)
        # An idle Claude Code TUI is already colored (prompt box, hint text), so
        # SGR codes are present on the screen without driving anything.
        time.sleep(1.0)

        # Plain capture — the production path (`capture-pane` WITHOUT `-e`).
        plain = br.read(name, lines=40)["content"]

        # Escape-preserving capture of the SAME pane via raw tmux (`-e`).
        raw = br._run(f"tmux capture-pane -t '{name}' -e -p -J -S -40")

        sgr = re.findall(r"\x1b\[[0-9;]*m", raw)
        log.debug("Gap B: `-e` capture recovered %d SGR escape sequences "
                  "(plain read() had escapes=%s).", len(sgr), "\x1b[" in plain)

        # Fidelity is recoverable ONLY with `-e`:
        assert sgr, (
            "the `-e` capture contained no SGR escapes — ANSI fidelity is NOT "
            "recoverable this way on this machine (TERM/tmux stripped them). "
            f"This is a FINDING, not a pass. raw tail:\n{raw[-500:]!r}"
        )
        assert "\x1b[" not in plain, (
            "the production read() path unexpectedly retained escape bytes — "
            f"plain tail:\n{plain[-500:]!r}"
        )
        log.debug("Gap B: styling IS recoverable via `capture-pane -e`; faithful "
                  "rendering still needs an xterm.js-class frontend renderer "
                  "(out of scope for this backend spike).")
    finally:
        _safe_close(br, name)
