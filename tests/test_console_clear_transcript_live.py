r"""Console `/clear` (and `/compact`) transcript-path orphaning spike — live (§10 #19).

Spike-or-report. The sidecar resolves an agent's transcript by its **pinned
session id** → `<session-id>.jsonl` (`bridge.session_id_for` / `find_transcript`).
Hypothesis (prior art — recon, `claude-code-mode-control-research.md` ~line 81):
running **`/clear`** from the Console starts a fresh conversation that, on some
Claude Code builds, writes a **new `<new-id>.jsonl`** while the bridge keeps
resolving the **old** pinned id — so after a Console `/clear` the sidecar reads a
stale file and new turns land in a transcript it isn't watching (**orphaned
history**). `/compact` may differ — it might annotate the *same* file with a
`compact_boundary` (no rotation) or also rotate. This spike distinguishes them
empirically, on THIS build, by planting codewords and reading disk + the resolver
back — never from assumption.

Both outcomes are honest results: HAZARD CONFIRMED (rotation + orphaning → a
re-resolve is needed, the §19 fallback) or NO HAZARD (resolution follows the
rotation, or the id doesn't rotate on this build). The verdict rests on the live
run, not a code re-read.

Run (single file, isolation)::

    .\.venv\Scripts\python.exe -m pytest tests\test_console_clear_transcript_live.py -m integration

=============================================================================
ISOLATION RULES (parallel-safe — sibling agents may run their own live bridge
sessions AT THE SAME TIME; violating any of these can kill their work):
  * ONE new file only — this file. No other test file is touched.
  * Uniquely-named tmux session — prefixed with the slug: ``clconsole-<uuid8>``.
    Never a fixed/shared name.
  * We instantiate our OWN ``TmuxBridge()`` — NOT conftest's session-scoped
    ``bridge`` fixture, whose setup AND teardown call ``tmux kill-server`` (would
    kill every sibling agent's sessions). Teardown here closes ONLY our own
    uniquely-named session via ``close(name)`` + removes our own diag dir.
  * We inspect ONLY our OWN agent's transcript files — each session runs in its
    own unique diag-dir cwd, so its ``~/.claude/projects`` subdir is unique to us;
    we never ls/read/modify another agent's transcripts, and never ``/clear`` a
    session we didn't spawn.
  * NEVER ``tmux kill-server`` (directly or via any helper).
  * Bridge sessions stay TAB-LESS — created with ``show=False``; never ``show()``.
  * Run ONLY this file in isolation — not the whole live tier.
  * Shared files (conftest.py, pyproject.toml, tests/README.md) are NOT edited.
=============================================================================
"""

from __future__ import annotations

import logging
import posixpath
import re
import shlex
import sys
import time
import uuid
from pathlib import Path

import pytest

# Make the repo-root `bridge` package importable (mirrors the finisher's shim).
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from bridge import TmuxBridge  # noqa: E402
from bridge.transcript import find_transcript  # noqa: E402

log = logging.getLogger(__name__)

pytestmark = [pytest.mark.integration, pytest.mark.slow]

SLUG = "clconsole"


# -----------------------------------------------------------------------------
# Read-only inspection helpers (all scoped to OUR own project dir)
# -----------------------------------------------------------------------------

def _list_jsonl(bridge: TmuxBridge, project_dir: str) -> set[str]:
    """Set of ``*.jsonl`` basenames in our project dir (proven ls-glob path)."""
    try:
        out = bridge._run(
            f"ls -1 {shlex.quote(project_dir)}/*.jsonl 2>/dev/null || true", timeout=15,
        )
    except Exception:
        return set()
    return {posixpath.basename(ln.strip())
            for ln in out.splitlines() if ln.strip().endswith(".jsonl")}


def _file_has(bridge: TmuxBridge, path: str, needle: str) -> bool:
    """True if the WSL file at ``path`` contains ``needle`` (read-only grep)."""
    try:
        out = bridge._run(
            f"grep -c -- {shlex.quote(needle)} {shlex.quote(path)} 2>/dev/null || echo 0",
            timeout=15,
        )
    except Exception:
        return False
    m = re.search(r"\d+", out or "")
    return bool(m and int(m.group(0)) > 0)


def _codeword_file(bridge: TmuxBridge, project_dir: str, needle: str) -> str | None:
    """Full path of the jsonl in our project dir that contains ``needle``, or None."""
    try:
        out = bridge._run(
            f"grep -l -- {shlex.quote(needle)} '{project_dir}'/*.jsonl 2>/dev/null || true",
            timeout=15,
        )
    except Exception:
        return None
    files = [ln.strip() for ln in out.splitlines() if ln.strip()]
    return files[0] if files else None


def _assistant_codeword_file(bridge, project_dir, needle) -> str | None:
    """Basename of the jsonl whose ASSISTANT entry contains ``needle``, or None.

    Distinct from ``_codeword_file`` (any match): the codeword also appears in the
    USER prompt line ("Reply with exactly: …"), which is written immediately —
    matching that would return before the assistant actually echoed. We require a
    line that carries BOTH the needle and the ``"type":"assistant"`` marker, so we
    key off the real reply — the same thing the sidecar's resolution must surface.
    """
    for base in _list_jsonl(bridge, project_dir):
        path = f"{project_dir}/{base}"
        try:
            out = bridge._run(
                f"grep -- {shlex.quote(needle)} {shlex.quote(path)} 2>/dev/null | "
                f"grep -c '\"type\":\"assistant\"' || echo 0",
                timeout=15,
            )
        except Exception:
            continue
        m = re.search(r"\d+", out or "")
        if m and int(m.group(0)) > 0:
            return base
    return None


def _wait_assistant_codeword(bridge, project_dir, needle, timeout=150) -> str | None:
    """Poll until the ASSISTANT echo of ``needle`` lands in ANY jsonl in our
    project dir (screen-independent completion; robust to a rotation)."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        hit = _assistant_codeword_file(bridge, project_dir, needle)
        if hit:
            return hit
        time.sleep(1.0)
    return None


def _filler_turns(bridge, name, n=3):
    """Drive a few short turns so a subsequent /compact has real content to
    compact (a one-turn conversation is a /compact no-op)."""
    topics = ["the ocean", "a mountain", "a city at night", "an old library", "a train"]
    for i in range(n):
        cw = f"FILLER{i}-{uuid.uuid4().hex[:4]}"
        bridge.send(name, f"In one sentence, describe {topics[i % len(topics)]}. "
                          f"End your reply with the token {cw}.")
        deadline = time.time() + 90
        while time.time() < deadline:
            if _readlog_has(bridge, name, cw):
                break
            time.sleep(1.0)


def _assistant_texts(bridge: TmuxBridge, name: str) -> list[str]:
    """Assistant text blocks from ``read_log(name)`` — i.e. from the transcript the
    bridge's pinned-id resolution CURRENTLY points at."""
    try:
        entries = bridge.read_log(name)
    except Exception:
        return []
    texts: list[str] = []
    for e in entries:
        if e.get("type") == "assistant":
            for blk in (e.get("message") or {}).get("content") or []:
                if isinstance(blk, dict) and blk.get("type") == "text":
                    texts.append(blk.get("text") or "")
    return texts


def _readlog_has(bridge: TmuxBridge, name: str, needle: str) -> bool:
    return any(needle in t for t in _assistant_texts(bridge, name))


def _plant_codeword(bridge: TmuxBridge, name: str, needle: str, timeout=120) -> bool:
    """Drive a turn that echoes ``needle`` and wait until it is visible via
    ``read_log`` (the pinned-id-resolved transcript). Screen-independent."""
    bridge.send(name, f"Reply with exactly: {needle}")
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _readlog_has(bridge, name, needle):
            return True
        time.sleep(1.0)
    return False


# -----------------------------------------------------------------------------
# Fixtures — OUR OWN bridge + a fresh, tab-less, uniquely-named session per test
# (never conftest's kill-server `bridge` fixture).
# -----------------------------------------------------------------------------

@pytest.fixture(scope="module")
def own_bridge():
    """Our OWN TmuxBridge — no server-wide kill anywhere in its lifecycle."""
    return TmuxBridge()


@pytest.fixture
def session(own_bridge):
    """A fresh tab-less ``clconsole-<uuid8>`` session in its own diag-dir cwd.

    Function-scoped so ``/clear`` and ``/compact`` each get an independent
    conversation. Torn down to OUR session + OUR dir only — never a broad kill.
    """
    uid = uuid.uuid4().hex[:8]
    name = f"{SLUG}-{uid}"
    diag = f"/home/lester/awl-{SLUG}-{uid}"
    own_bridge._run(f"mkdir -p {diag}")
    log.debug("session create name=%s diag=%s", name, diag)
    own_bridge.create(name, cwd=diag, show=False)
    own_bridge.wait_idle(name, timeout=90, interval=1.0)
    yield {"bridge": own_bridge, "name": name, "diag": diag}
    try:
        own_bridge.close(name)
    except Exception:
        pass
    try:
        own_bridge._run(f"rm -rf {diag}")
    except Exception:
        pass


# -----------------------------------------------------------------------------
# Shared PRE-command establishment
# -----------------------------------------------------------------------------

def _establish(bridge: TmuxBridge, name: str, tag: str):
    """Plant a pre-command codeword and snapshot the resolver + file set.

    Returns (cw1, cw1_file, pinned0, path0, project_dir, snap0).
    """
    cw1 = f"ORPHAN-{uuid.uuid4().hex[:6]}"
    assert _plant_codeword(bridge, name, cw1), f"[{tag}] pre-command codeword never landed"
    pinned0 = bridge.session_id_for(name)
    path0 = find_transcript(bridge, name)
    assert path0, f"[{tag}] no transcript resolved after the pre-command turn"
    project_dir = posixpath.dirname(path0)
    snap0 = _list_jsonl(bridge, project_dir)
    cw1_file = _assistant_codeword_file(bridge, project_dir, cw1)
    assert _readlog_has(bridge, name, cw1), f"[{tag}] read_log lost the pre-command codeword"
    log.info(
        "#19 [%s] PRE: pinned=%s resolved=%s cw1_file=%s files=%s codeword=%s",
        tag, pinned0, posixpath.basename(path0), cw1_file, sorted(snap0), cw1,
    )
    return cw1, cw1_file, pinned0, path0, project_dir, snap0


# -----------------------------------------------------------------------------
# #19 — Console /clear
# -----------------------------------------------------------------------------

def test_19_clear_transcript_orphaning(session):
    """Does a Console ``/clear`` rotate the transcript, and does the pinned-id
    resolution orphan it?"""
    b: TmuxBridge = session["bridge"]
    name = session["name"]

    cw1, cw1_file, pinned0, path0, project_dir, snap0 = _establish(b, name, "clear")

    # Run the Console command exactly the way the Console does.
    b.send(name, "/clear")
    time.sleep(3)
    try:
        b.wait_idle(name, timeout=60, interval=1.0)
    except Exception as e:
        log.warning("#19 [clear] wait_idle after /clear: %s", e)

    pinned1 = b.session_id_for(name)

    # Drive a POST-clear turn planting a fresh codeword; wait for the ASSISTANT
    # echo to land in ANY jsonl in our project dir (robust to a rotation).
    cw2 = f"POSTCLEAR-{uuid.uuid4().hex[:6]}"
    b.send(name, f"Reply with exactly: {cw2}")
    landed = _wait_assistant_codeword(b, project_dir, cw2, timeout=150)

    snap1 = _list_jsonl(b, project_dir)
    new_files = sorted(snap1 - snap0)
    path1 = find_transcript(b, name)
    readlog_has_cw2 = _readlog_has(b, name, cw2)
    cw2_in_old = _file_has(b, path0, cw2) if path0 else False
    landed_base = posixpath.basename(landed) if landed else None

    log.info(
        "#19 [clear] POST: pinned=%s (was %s) resolved_path=%s new_files=%s "
        "cw1_file=%s cw2_landed_in=%s readlog_surfaces_cw2=%s cw2_in_old_file=%s",
        pinned1, pinned0, posixpath.basename(path1) if path1 else None,
        new_files, cw1_file, landed_base, readlog_has_cw2, cw2_in_old,
    )

    # Observables → verdict. Primary rotation signal (proven): the post-clear
    # codeword landed in a DIFFERENT jsonl than the pre-clear one.
    rotated = (landed_base is not None and landed_base != cw1_file) or bool(new_files)
    orphaned = rotated and (readlog_has_cw2 is False)
    if orphaned:
        verdict = (
            "HAZARD CONFIRMED: `/clear` rotated the transcript to a new "
            f"{new_files} and the pinned id ({pinned0}) still resolves the OLD "
            "file, so read_log CANNOT see the post-clear turn — history is "
            "ORPHANED. Fix (§19): re-resolve the session id after a Console "
            "/clear (re-register with the bridge) so find_transcript follows the "
            "new <id>.jsonl."
        )
    elif not rotated:
        verdict = ("NO HAZARD: `/clear` did NOT rotate the transcript on this "
                   "build (no new file; resolved path unchanged) — nothing to "
                   "orphan.")
    else:
        verdict = ("NO HAZARD: `/clear` rotated the transcript AND the pinned-id "
                   "resolution followed it (read_log surfaces the post-clear "
                   "turn) — no re-resolve needed.")
    log.info("#19 [clear] VERDICT: %s", verdict)

    # --- Assertions on the OBSERVED reality (read back from disk + resolver) ---
    assert landed is not None, "post-clear turn never landed in any transcript file"
    # `/clear` rotates the on-disk transcript to a NEW <new-id>.jsonl on this build.
    assert new_files, (
        f"expected `/clear` to create a new transcript file; snap0={sorted(snap0)} "
        f"snap1={sorted(snap1)}"
    )
    # The bridge's pinned id is unchanged (it has no knowledge of the Console /clear).
    assert pinned1 == pinned0, (
        f"pinned session id changed unexpectedly: {pinned0} -> {pinned1}"
    )
    # The post-clear turn landed in the NEW file, NOT the old pinned one.
    assert landed_base in new_files, (
        f"post-clear codeword landed in {landed_base}, not a new file {new_files}"
    )
    assert not cw2_in_old, "post-clear codeword unexpectedly written to the OLD file"
    # THE hazard: read_log (pinned old id) cannot see the post-clear turn → orphaned.
    assert not readlog_has_cw2, (
        "read_log (pinned old id) surfaced the post-clear codeword — resolution "
        "unexpectedly followed the rotation (no orphaning)."
    )
    assert orphaned, "expected the §19 orphaning hazard to reproduce"


# -----------------------------------------------------------------------------
# #19 — Console /compact
# -----------------------------------------------------------------------------

def test_19_compact_transcript_behavior(session):
    """Does a Console ``/compact`` rotate the transcript (new file → possible
    orphaning) or annotate the SAME file in place (a ``compact_boundary`` marker)?"""
    b: TmuxBridge = session["bridge"]
    name = session["name"]

    # Give /compact real conversation to compact (a one-turn convo is a no-op).
    _filler_turns(b, name, n=3)
    cw1, cw1_file, pinned0, path0, project_dir, snap0 = _establish(b, name, "compact")

    # Run /compact — this triggers a summarization pass and can take a while.
    b.send(name, "/compact")
    time.sleep(5)
    try:
        b.wait_idle(name, timeout=180, interval=1.5)
    except Exception as e:
        log.warning("#19 [compact] wait_idle after /compact: %s", e)
    time.sleep(2)

    pinned1 = b.session_id_for(name)
    snap_mid = _list_jsonl(b, project_dir)
    new_files_after_compact = sorted(snap_mid - snap0)
    path_mid = find_transcript(b, name)

    # Did /compact write a compaction marker (annotate-in-place signature)? Probe a
    # broad set of markers this build might use.
    _MARKERS = ("compact_boundary", "isCompactSummary", "compactMetadata",
                '"type":"summary"', "isCompactionSummary")
    boundary_marker = None
    for mk in _MARKERS:
        hit = _codeword_file(b, project_dir, mk)
        if hit:
            boundary_marker = mk
            break

    # Drive a POST-compact turn; wait for the ASSISTANT echo (not the user prompt).
    cw2 = f"POSTCOMPACT-{uuid.uuid4().hex[:6]}"
    b.send(name, f"Reply with exactly: {cw2}")
    landed = _wait_assistant_codeword(b, project_dir, cw2, timeout=150)

    snap1 = _list_jsonl(b, project_dir)
    new_files = sorted(snap1 - snap0)
    path1 = find_transcript(b, name)
    readlog_has_cw2 = _readlog_has(b, name, cw2)
    landed_base = landed  # already a basename from _assistant_codeword_file

    log.info(
        "#19 [compact] POST: pinned=%s (was %s) cw1_file=%s resolved_path=%s "
        "new_files_after_compact=%s new_files_total=%s compaction_marker=%s "
        "cw2_assistant_in=%s readlog_surfaces_cw2=%s",
        pinned1, pinned0, cw1_file, posixpath.basename(path1) if path1 else None,
        new_files_after_compact, new_files, boundary_marker,
        landed_base, readlog_has_cw2,
    )

    rotated = (landed_base is not None and cw1_file is not None
               and landed_base != cw1_file) or bool(new_files) \
        or (path1 is not None and path1 != path0)
    orphaned = rotated and (readlog_has_cw2 is False)
    if orphaned:
        verdict = (
            f"HAZARD: `/compact` rotated the transcript (new_files={new_files}, "
            f"cw2 assistant echo in {landed_base} ≠ pinned {cw1_file}) and the "
            "pinned id still resolves the old file — read_log cannot see the "
            "post-compact turn (ORPHANED). Fix (§19): re-resolve after /compact."
        )
    elif (not rotated) and readlog_has_cw2:
        verdict = (
            "NO HAZARD (annotate-in-place): `/compact` kept the SAME <id>.jsonl "
            f"(no new file; marker={boundary_marker}) — the pinned-id resolution "
            "still points at the current file and read_log surfaces the "
            "post-compact turn. Unlike `/clear`, no re-resolve is needed."
        )
    else:
        verdict = (
            f"MIXED/UNEXPECTED: rotated={rotated} readlog_surfaces_cw2="
            f"{readlog_has_cw2} marker={boundary_marker} — see logged observables."
        )
    log.info("#19 [compact] VERDICT: %s", verdict)

    # --- Assertions on the OBSERVED reality ------------------------------------
    assert landed is not None, "post-compact assistant echo never landed"
    assert pinned1 == pinned0, (
        f"pinned session id changed unexpectedly: {pinned0} -> {pinned1}"
    )
    # OBSERVED on this build (2.1.198): /compact does NOT rotate the transcript —
    # the post-compact turn stays in the SAME <id>.jsonl and the pinned-id
    # resolution still surfaces it (no orphaning). This is the durable regression:
    # if a future build rotates on /compact, `rotated`/`orphaned` flip and this
    # asserts the hazard instead.
    assert not rotated, (
        f"/compact rotated the transcript unexpectedly: cw1_file={cw1_file} "
        f"cw2_in={landed_base} new_files={new_files} path0={posixpath.basename(path0)} "
        f"path1={posixpath.basename(path1) if path1 else None}"
    )
    assert readlog_has_cw2, (
        "read_log lost the post-compact turn even though /compact did not rotate — "
        "unexpected orphaning; inspect the logged observables."
    )
    assert not orphaned, "unexpected /compact orphaning (see observables)"
