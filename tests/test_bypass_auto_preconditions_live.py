"""Live spike — Bypass & Auto permission-mode LAUNCH preconditions.

§10 item #20 ("Bypass & Auto permission-mode launch preconditions", 🧪
needs-spike; docs/ARCHITECTURE.md §10 #20 → §6.2, §7.11; relates to #1). A
SPIKE-OR-REPORT task: establish, live, which permission-mode segments are
actually reachable given how an agent was launched, and — critically — HOW an
unreachable segment presents (silent no-op vs visible refusal), because the UI
must never present a control that silently does nothing.

DISTINCT FROM #1: #1 spikes the mid-run *cycle* (Shift+Tab / `BTab`); #20 spikes
whether the *endpoints* of that cycle (Bypass, Auto) are even reachable depending
on launch flags. Read-back technique is shared with #1 and the existing
`test_permission_mode_cycle_live.py`: read the resulting mode back from the live
status line — never assert the value you sent.

TERMINOLOGY (resolved live) — the build prompt loosely labels acceptEdits as
"Auto (accept-edits)", but on this build these are THREE DISTINCT cycle segments
with distinct status-line indicators, so this spike characterizes each:
  * ``acceptEdits`` — indicator ``⏵⏵ accept edits on`` (the design's "Edit" segment)
  * ``auto``        — indicator ``⏵⏵ auto mode on``     (the design's "Auto" segment,
                       the background-classifier mode)
  * ``bypassPermissions`` — indicator ``⏵⏵ bypass permissions on``
  * ``plan``        — indicator ``⏸ plan mode on``
  * ``default``     — no mode indicator (``? for shortcuts``)

FINDINGS (live, Claude Code 2.1.198, 2026-07-02)
------------------------------------------------
Default-launch cycle ring on this account/build (no flags):
  ``default → acceptEdits → plan → auto → (wrap to default)``.

  * **acceptEdits** — reachable with NO launch flag: launchable directly
    (``--permission-mode acceptEdits`` → "accept edits on") and one ``BTab`` from
    default. Precondition: NONE.
  * **auto** — reachable with NO launch flag on THIS account: it sits in the
    default-launch ring (3 ``BTab`` from default) and launches directly
    (``--permission-mode auto`` → "auto mode on"), with NO opt-in prompt observed.
    CAVEAT: the mode-control research says ``auto`` needs eligibility (v2.1.83+, a
    qualifying plan/model) + a one-time opt-in on a non-qualifying account; this
    account qualifies (or was already opted in), so on a DIFFERENT account the
    precondition may be an opt-in/eligibility gate. This spike records the
    reachable-here result and flags the account-dependence.
  * **bypassPermissions** — NOT reachable without a launch pre-arm: it is ABSENT
    from the default-launch cycle ring (cycling wraps default→…→auto→default and
    bypass never appears). This is the key failure-mode finding: an unreachable
    Bypass is a **silent absence from the cycle** — no refusal line, no indicator;
    the only signal is that the ring wraps past it. Reachable via a launch pre-arm:
    ``--permission-mode bypassPermissions`` (the production ``create`` path) starts
    the agent IN bypass ("bypass permissions on"), the startup-gate clearer
    accepting the warning; ``--allow-dangerously-skip-permissions`` ADDS bypass to
    the cycle without activating it (start in default, then ``BTab`` reaches
    bypass).

UI RULE this establishes (§20 Desired / fallback): gate the Bypass segment behind
a launch-time choice — launch with ``--permission-mode bypassPermissions`` (start
in bypass) or ``--allow-dangerously-skip-permissions`` (arm it for mid-run cycle);
when neither is present, DISABLE/HIDE the Bypass control — never present it as a
live control, because without the pre-arm it silently no-ops (the segment is not
in the ring). acceptEdits and auto need no launch flag on this build, but the Auto
segment's availability is account-eligibility-dependent, so the UI should confirm
it (e.g. from the launch config / a probe) rather than assume it.

SAFETY: Bypass mode disables permission prompts. Every agent is confined to its
own throwaway WSL diag dir and driven with NO destructive commands — the spike
only READS the mode indicator, it never exercises a dangerous action.

PARALLEL-SAFE ISOLATION (CRITICAL — sibling agents may run their own live
sessions concurrently; violating any of these can kill their work):
  * ONE new file only; uniquely-named, slug-prefixed sessions ``bypassauto-<uuid8>``
    (several are launched — every one is tracked and closed).
  * NEVER ``tmux kill-server`` / ``bridge.shutdown()`` — tear down ONLY this test's
    sessions via ``bridge.close(name)`` + ``rm -rf`` its own diag dirs.
  * Does NOT use conftest's session-scoped ``bridge`` fixture (its setup AND
    teardown call ``_kill_all_tmux()`` = ``tmux kill-server``, which would kill
    siblings). We instantiate our OWN ``TmuxBridge()``.
  * No shared-file edits (conftest.py / pyproject.toml / tests/README.md).

Run (PowerShell)::

    ./.venv/Scripts/python.exe -m pytest tests/test_bypass_auto_preconditions_live.py -m integration
"""

import contextlib
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

# Status-line mode indicators discovered live on Claude Code 2.1.198 (plain-text
# substrings — `read()` uses `capture-pane -p -J` which strips the ANSI/glyphs,
# so we match the words). Order matters: check the most specific first.
_MODE_INDICATORS = (
    ("bypassPermissions", "bypass permissions on"),
    ("acceptEdits", "accept edits on"),
    ("plan", "plan mode on"),
    ("auto", "auto mode on"),
)


def _read_tail(bridge, name, n=20):
    return bridge.read(name, lines=n)["content"]


def _mode_of(bridge, name):
    """Read the current permission mode back from the live status line.

    Returns ``(label, tail)`` where label is one of the four indicated modes or
    ``"default"`` when no mode indicator is shown (default mode shows none).
    """
    tail = _read_tail(bridge, name)
    low = tail.lower()
    for label, needle in _MODE_INDICATORS:
        if needle in low:
            return label, tail
    return "default", tail


def _wait_idle(bridge, name, timeout=25.0, interval=0.5):
    """Idle-gate before sending BTab (a key sent mid-turn is lost / misfires)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if bridge.status(name).get("state") == "idle":
                return True
        except Exception as e:  # pragma: no cover - environment dependent
            log.debug("status(%s) raised: %s", name, e)
        time.sleep(interval)
    return False


def _looks_like_menu(tail):
    """A numbered opt-in/enrollment menu (e.g. the auto-mode opt-in) rather than a
    clean mode line — so the cycle helper can back out with Escape and record it."""
    low = tail.lower()
    return ("don't ask again" in low or "enable auto" in low
            or "opt in" in low or "do you want to enable" in low)


def _cycle_collect(bridge, name, presses):
    """Idle-gate, then send ``presses`` single ``BTab``s, recording the mode read
    back after each. Returns a list of ``(i, label, tail)``. If an opt-in menu is
    detected, records it as label ``"opt-in-menu"`` and Escapes out."""
    steps = []
    for i in range(1, presses + 1):
        if not _wait_idle(bridge, name):
            log.debug("cycle(%s): not idle before BTab #%d", name, i)
        bridge.keys(name, "BTab")
        time.sleep(1.2)
        label, tail = _mode_of(bridge, name)
        if label == "default" and _looks_like_menu(tail):
            label = "opt-in-menu"
            log.debug("cycle(%s) BTab #%d -> opt-in menu, escaping:\n%s",
                      name, i, tail[-500:])
            bridge.keys(name, "Escape")
            time.sleep(0.8)
        log.debug("cycle(%s) BTab #%d -> %s", name, i, label)
        steps.append((i, label, tail))
    return steps


class _Fleet:
    """Tracks every session this test launches so teardown closes them all — and
    ONLY them (never a broad kill). Each ``launch`` makes its own throwaway dir."""

    def __init__(self, bridge):
        self.bridge = bridge
        self._sessions: list[tuple[str, str]] = []  # (name, diag)

    def launch(self, *, permission_mode, claude_args="", label=""):
        name = f"bypassauto-{uuid.uuid4().hex[:8]}"
        diag = f"/home/lester/awl-bypassauto-{uuid.uuid4().hex[:8]}"
        self.bridge._run(f"mkdir -p {diag}")
        self._sessions.append((name, diag))
        info = self.bridge.create(
            name, cwd=diag, permission_mode=permission_mode,
            claude_args=claude_args, show=False,
        )
        log.debug("launch %s (mode=%s args=%r): %s", label or name,
                  permission_mode, claude_args, info)
        self.bridge.wait_idle(name, timeout=60, interval=1.0)
        return name

    def close_all(self):
        for name, diag in self._sessions:
            with contextlib.suppress(Exception):
                self.bridge.close(name)
            with contextlib.suppress(Exception):
                self.bridge._run(f"rm -rf {diag}")


@pytest.fixture
def fleet():
    bridge = TmuxBridge()
    f = _Fleet(bridge)
    try:
        yield f
    finally:
        f.close_all()  # close ONLY this test's sessions; never kill-server


# -----------------------------------------------------------------------------
# acceptEdits — the "Edit" segment. Precondition: none.
# -----------------------------------------------------------------------------

def test_acceptedits_reachable_without_flag(fleet):
    """acceptEdits is reachable with NO launch flag — launchable directly."""
    name = fleet.launch(permission_mode="acceptEdits", label="acceptEdits-direct")
    label, tail = _mode_of(fleet.bridge, name)
    log.debug("acceptEdits direct-launch read-back: %s\n%s", label, tail[-400:])
    assert label == "acceptEdits", (
        "launching with --permission-mode acceptEdits did NOT land in acceptEdits "
        f"(status line read back mode {label!r}). Tail:\n{tail[-400:]}"
    )


# -----------------------------------------------------------------------------
# auto — the "Auto" segment. Precondition: none on this account (eligibility-
# dependent in general).
# -----------------------------------------------------------------------------

def test_auto_reachable_without_flag(fleet):
    """auto is reachable with NO launch flag on this account — both directly and
    by cycling from a default launch. (Records the account-eligibility caveat.)"""
    # Direct launch into auto.
    name = fleet.launch(permission_mode="auto", label="auto-direct")
    label, tail = _mode_of(fleet.bridge, name)
    log.debug("auto direct-launch read-back: %s\n%s", label, tail[-400:])
    if label != "auto":
        # Honest report: if this account can't launch auto, that IS the finding —
        # do not fabricate a pass.
        pytest.xfail(
            "auto not reachable by direct launch on this account/build "
            f"(read back {label!r}) — the design's Auto segment requires "
            "eligibility/opt-in here; UI must gate it. Tail:\n" + tail[-400:]
        )

    # And reachable by cycling from a default launch (default→acceptEdits→plan→auto).
    dname = fleet.launch(permission_mode="default", label="auto-cycle")
    steps = _cycle_collect(fleet.bridge, dname, presses=3)
    labels = [s[1] for s in steps]
    log.debug("default-launch cycle to auto: %s", labels)
    assert "auto" in labels, (
        "cycling from a default launch never reached auto — ring was "
        f"{labels}; auto may not be enabled on this account"
    )


# -----------------------------------------------------------------------------
# bypassPermissions — the crux. Launch-gated; unreachable = silent absence.
# -----------------------------------------------------------------------------

def test_bypass_absent_from_cycle_without_flag(fleet):
    """Without a launch pre-arm, Bypass is NOT in the cycle ring — cycling wraps
    past it and it never appears. This characterizes the unreachable-segment
    failure mode: a SILENT absence (no refusal, no indicator)."""
    name = fleet.launch(permission_mode="default", label="bypass-absent")
    # 5 presses is a full traversal + wrap of the observed ring
    # (default→acceptEdits→plan→auto→default→acceptEdits), so if bypass were in
    # the ring it would have appeared.
    steps = _cycle_collect(fleet.bridge, name, presses=5)
    labels = [s[1] for s in steps]
    log.debug("default-launch full ring traversal: %s", labels)
    assert "bypassPermissions" not in labels, (
        "bypass appeared in the cycle from a NORMAL launch — it should be "
        f"launch-gated. Ring observed: {labels}"
    )
    # Positive evidence the cycle actually moved (so 'absent' isn't just a dead
    # BTab): at least acceptEdits was reached.
    assert "acceptEdits" in labels, (
        "the BTab cycle did not advance at all (no acceptEdits seen) — cannot "
        f"conclude bypass is absent vs. the cycle being stuck. Ring: {labels}"
    )
    log.debug(
        "FINDING: bypass is silently absent from the default-launch ring %s — "
        "no refusal, no indicator; the UI must not present it as a live control "
        "without a launch pre-arm", labels,
    )


def test_bypass_reachable_with_permission_mode_launch(fleet):
    """Bypass IS reachable when launched via the production path
    (--permission-mode bypassPermissions); the startup-gate clearer accepts the
    warning and the agent starts IN bypass. SAFETY: only the indicator is read."""
    name = fleet.launch(permission_mode="bypassPermissions", label="bypass-prod")
    label, tail = _mode_of(fleet.bridge, name)
    log.debug("bypassPermissions launch read-back: %s\n%s", label, tail[-400:])
    assert label == "bypassPermissions", (
        "launching with --permission-mode bypassPermissions did NOT land in "
        f"bypass (read back {label!r}). Either the mode flag or the startup-gate "
        f"clearer failed. Tail:\n{tail[-400:]}"
    )


def test_bypass_added_to_cycle_with_allow_flag(fleet):
    """--allow-dangerously-skip-permissions ARMS bypass without activating it: the
    agent starts in default, and cycling now REACHES bypass (proving the alternate
    launch precondition the UI can use for a mid-run-toggleable Bypass)."""
    name = fleet.launch(
        permission_mode="default",
        claude_args="--allow-dangerously-skip-permissions",
        label="bypass-armed",
    )
    # Should start in default (armed, not activated).
    start_label, start_tail = _mode_of(fleet.bridge, name)
    log.debug("allow-flag launch start mode: %s", start_label)
    # Cycle enough to traverse the armed ring (default→acceptEdits→plan→
    # bypassPermissions→auto→wrap): up to 5 presses.
    steps = _cycle_collect(fleet.bridge, name, presses=5)
    labels = [s[1] for s in steps]
    log.debug("armed-launch ring traversal: %s (start=%s)", labels, start_label)
    if "bypassPermissions" not in labels:
        # If the flag doesn't add bypass to the cycle on this build, that's an
        # honest negative — the production --permission-mode path (proven above)
        # remains the reliable precondition. Record, don't fabricate.
        pytest.xfail(
            "--allow-dangerously-skip-permissions did NOT add bypass to the cycle "
            f"on Claude Code 2.1.198 (ring: {labels}, start={start_label}). Use "
            "--permission-mode bypassPermissions (proven) as the Bypass precondition."
        )
    log.debug("FINDING: --allow-dangerously-skip-permissions armed bypass into the "
              "cycle %s without starting in it (start=%s)", labels, start_label)
