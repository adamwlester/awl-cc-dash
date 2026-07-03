"""Rewind / Handoff spike (§10 #15) — live proof of conversation truncate-and-resume
and fork-from-point on a real Claude Code session.

MECHANISM (research → implemented). The gating research
(`dev/notes/research/s10-research-15-rewind-handoff.md`) verdict was **PARTIAL YES**
for both Rewind (A) and Fork/Handoff (B), and named these mechanisms:
  * Rewind (A): native TUI **`/rewind`** — restore CONVERSATION to a prior prompt
    checkpoint (interactive menu, driven over tmux). Automation was flagged as the
    open risk. This test proves the automation works on Claude Code 2.1.198.
  * Fork/Handoff (B): the research's **path 1** — full fork via
    `claude --resume <src> --fork-session`, then `/rewind` inside the fork to the
    target point. (Path 2, the TypeScript-SDK `resumeSessionAt`, is NOT used: this
    repo's SDK driver is the Python Agent SDK, which the research confirmed lacks a
    `resume_session_at` equivalent, and wiring a TS-SDK step would require shared
    tooling changes outside this single-file spike.)

WHAT WAS OBSERVED (why these are durable assertions, not hopes). Both mechanisms
were probed live before this test was written:
  * `/rewind` menu on 2.1.198: opens "Rewind — restore … to the point before…",
    lists one checkpoint per user prompt with `(current)` selected at the bottom;
    `Up`×k highlights "before the k-th-from-last prompt"; Enter opens a confirm
    dialog ("The conversation will be forked. The code will be unchanged."); Enter
    again performs **Restore conversation**; the selected prompt is restored into
    the input field (cleared here with Ctrl-U before interrogating).
  * `/rewind` restore-conversation rewinds IN-PLACE on the same session-id (no new
    <id>.jsonl at rewind time; old lines stay as history, live model context drops
    them) — so it is a clean REWIND but not, by itself, a fork. `--fork-session`
    supplies the independent second session for the Fork proof.

THE §4 OBSERVABLE (read back from the live agent, never asserted on injected text):
  * Rewind: plant ordered codewords ALPHA-1/2/3; rewind to "before ALPHA-3"; the
    resumed agent knows ALPHA-1 & ALPHA-2 but has genuinely LOST ALPHA-3; the
    transcript still parses.
  * Fork: fork the seeded session and rewind the fork to "before ALPHA-3"; the fork
    knows ALPHA-1/2 but not ALPHA-3, AND the original session is untouched (still
    knows ALPHA-1/2/3, still live).

============================================================================
ISOLATION RULES (parallel-safe — sibling agents may be running their OWN live
bridge sessions at the same time; violating any of these can kill their work):
  * ONE new file only — this file. No other test file is touched.
  * We instantiate our OWN `TmuxBridge()` (the `rewind_bridge` fixture) and NEVER
    use conftest's shared `bridge` fixture — that fixture's setup AND teardown both
    call `_kill_all_tmux()` (= `tmux kill-server`), which would kill every sibling
    agent's sessions.
  * Every tmux session is uniquely named (`rewind-<uuid8>` / `rewind-src-<uuid8>` /
    `rewind-fork-<uuid8>`) — never a fixed/shared name. A fork is a SECOND uniquely
    named session; both are torn down individually via `close()`. We NEVER call
    `tmux kill-server`.
  * We operate only on OUR OWN sessions' transcript files, inside our own throwaway
    WSL diag dir and its matching `~/.claude/projects/<escaped-cwd>/` project dir
    (both removed in teardown). We never touch another agent's transcript or a
    shared record we didn't create.
  * Sessions stay TAB-LESS: created with show=False; show()/show=True is never used.

Run (from repo root, ONLY this file — not the whole live tier)::

    .\\.venv\\Scripts\\python.exe -m pytest tests\\test_rewind_handoff_live.py -m integration
    #  or:  tests\\run.ps1 tests\\test_rewind_handoff_live.py -m integration
"""
from __future__ import annotations

import logging
import shlex
import sys
import time
import uuid
from pathlib import Path

import pytest

# Repo root on sys.path so `from bridge import ...` resolves (mirrors the finisher).
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from bridge import TmuxBridge  # noqa: E402
from bridge.paths import CLAUDE_BIN  # noqa: E402  (absolute WSL claude binary)

log = logging.getLogger(__name__)

pytestmark = [pytest.mark.integration, pytest.mark.slow]

_INTERROGATE = ("Reply with ONLY a comma-separated list of every codeword you "
                "currently remember. Nothing else.")


@pytest.fixture
def rewind_bridge():
    """Our OWN TmuxBridge — deliberately NOT conftest's shared `bridge` fixture,
    whose kill-server teardown would nuke sibling agents' sessions. Construction
    has no side effects; each test tears down only its own uniquely-named
    session(s)."""
    return TmuxBridge()


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _project_dir(diag: str) -> str:
    """The `~/.claude/projects/<escaped-cwd>/` dir Claude uses for `diag`'s
    transcripts (cwd path with '/' -> '-')."""
    return "~/.claude/projects/-home-lester" + diag[len("/home/lester"):].replace("/", "-")


def _jsonl_ids(bridge, proj: str) -> set[str]:
    out = bridge._run(
        f"ls -1 {proj}/*.jsonl 2>/dev/null | xargs -n1 basename 2>/dev/null || echo"
    )
    return {x for x in out.split() if x.endswith(".jsonl")}


def _plant_codewords(bridge, name: str, n: int = 3) -> None:
    """Drive n turns, each planting an ordered, distinguishable codeword."""
    for i in range(1, n + 1):
        bridge.send(name, f"Remember this codeword: ALPHA-{i}. Reply with exactly: GOT-{i}")
        bridge.wait_idle(name, timeout=90)
        time.sleep(1)


def _rewind_to_before_last(bridge, name: str, ups: int) -> None:
    """Drive the `/rewind` menu to "the point before the ups-th-from-last prompt"
    and perform Restore-conversation. `ups=1` => discard only the last prompt.
    (Menu navigation confirmed live on 2.1.198 — see module docstring.)"""
    bridge.send(name, "/rewind")
    time.sleep(3)
    screen = bridge.read(name, lines=45)["content"]
    assert "Rewind" in screen and "Restore the code" in screen, (
        f"/rewind menu did not render as expected:\n{screen[-600:]}"
    )
    for _ in range(ups):
        bridge.keys(name, "Up")
        time.sleep(1)
    bridge.keys(name, "Enter")          # open the confirm dialog for this checkpoint
    time.sleep(2)
    confirm = bridge.read(name, lines=45)["content"]
    assert "Confirm you want to restore" in confirm, (
        f"rewind confirm dialog did not appear:\n{confirm[-600:]}"
    )
    bridge.keys(name, "Enter")          # confirm default = Restore conversation
    time.sleep(3)
    bridge.keys(name, "C-u")            # clear the restored prompt from the input
    time.sleep(0.5)


def _last_reply_screen(bridge, name: str) -> str:
    """The agent's most recent reply, scraped from the pane (the last line that
    begins with the assistant bullet '●', joined with any wrapped continuation)."""
    content = bridge.read(name, lines=40)["content"]
    lines = content.split("\n")
    idx = None
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].lstrip().startswith("●"):
            idx = i
            break
    if idx is None:
        return content[-300:]
    reply = [lines[idx].lstrip()[1:].strip()]
    for j in range(idx + 1, len(lines)):
        s = lines[j].strip()
        if not s or s.startswith(("✻", "─", "❯", "?")):
            break
        reply.append(s)
    return " ".join(reply).strip()


def _last_assistant_log(bridge, name: str) -> str:
    """The last assistant message from the structured transcript (bridge-tracked
    sessions only). Doubles as a transcript-integrity check: read_log must parse."""
    entries = bridge.read_log(name, types=["assistant"])
    if not entries:
        return ""
    return str((entries[-1].get("message") or {}).get("content"))


# --------------------------------------------------------------------------- #
# Rewind (A) — truncate-and-resume, same session
# --------------------------------------------------------------------------- #

def test_rewind_truncate_and_resume(rewind_bridge):
    """Native `/rewind` restore-conversation genuinely truncates the live context:
    after rewinding to "before ALPHA-3", the agent knows ALPHA-1/2 but has LOST
    ALPHA-3, and the transcript still parses. (§4 rewind observable.)"""
    bridge = rewind_bridge
    name = f"rewind-{uuid.uuid4().hex[:8]}"
    diag = f"/home/lester/awl-rewind-{uuid.uuid4().hex[:8]}"
    proj = _project_dir(diag)
    bridge._run(f"mkdir -p {shlex.quote(diag)}")
    try:
        info = bridge.create(name, cwd=diag, model="sonnet", show=False)
        log.debug("rewind: source session %s sid=%s", name, info.get("session_id"))
        _plant_codewords(bridge, name, 3)

        # Rewind to the point before ALPHA-3 (discard only the last prompt/turn).
        _rewind_to_before_last(bridge, name, ups=1)

        # Interrogate the resumed conversation.
        bridge.send(name, _INTERROGATE)
        bridge.wait_idle(name, timeout=90)
        time.sleep(1)

        reply_log = _last_assistant_log(bridge, name)   # also proves transcript parses
        reply_scr = _last_reply_screen(bridge, name)
        log.debug("rewind: interrogation reply (log=%r / screen=%r)", reply_log, reply_scr)

        assert reply_log, "read_log returned no assistant message (transcript unreadable)"
        assert "ALPHA-1" in reply_log and "ALPHA-2" in reply_log, (
            f"resumed agent lost the retained prefix (ALPHA-1/2): {reply_log!r}"
        )
        assert "ALPHA-3" not in reply_log, (
            f"rewind did NOT truncate — agent still remembers ALPHA-3: {reply_log!r} "
            "(mechanism failed the §4 observable)"
        )
        # Cross-check the live pane agrees (belt and suspenders).
        assert "ALPHA-3" not in reply_scr, f"screen reply still shows ALPHA-3: {reply_scr!r}"
        log.debug(
            "rewind: WORKS — /rewind restore-conversation over tmux dropped ALPHA-3 "
            "from live context while retaining ALPHA-1/2; transcript still parses. "
            "Detector/endpoint (§7.5/§9.2): /rewind -> Up*k -> Enter -> Enter "
            "(Restore conversation) -> Ctrl-U, keyed to prompt checkpoints."
        )
    finally:
        try:
            bridge.close(name)
        except Exception as e:
            log.debug("rewind: close(%s) raised (non-fatal): %s", name, e)
        bridge._run(f"rm -rf {shlex.quote(diag)}")
        bridge._run(f"rm -rf {proj}")


# --------------------------------------------------------------------------- #
# Fork / Handoff (B) — fork-from-point, original preserved
# --------------------------------------------------------------------------- #

def test_handoff_fork_from_point(rewind_bridge):
    """Research path 1: `claude --resume <src> --fork-session` creates an
    independent fork; `/rewind` in the fork to "before ALPHA-3" yields a branch
    that knows ALPHA-1/2 but not ALPHA-3, WHILE the source stays untouched (still
    knows ALPHA-1/2/3). (§4 fork observable: prefix-shared, diverges, original
    intact.)"""
    bridge = rewind_bridge
    src = f"rewind-src-{uuid.uuid4().hex[:8]}"
    fork = f"rewind-fork-{uuid.uuid4().hex[:8]}"
    diag = f"/home/lester/awl-rewind-{uuid.uuid4().hex[:8]}"
    proj = _project_dir(diag)
    bridge._run(f"mkdir -p {shlex.quote(diag)}")
    try:
        info = bridge.create(src, cwd=diag, model="sonnet", show=False)
        src_sid = info.get("session_id")
        log.debug("fork: source session %s sid=%s", src, src_sid)
        _plant_codewords(bridge, src, 3)
        ids_before = _jsonl_ids(bridge, proj)

        # Full fork via the native flag (absolute binary; a raw `claude` isn't on
        # tmux's non-login PATH). Same cwd -> same project dir for discovery.
        fork_cmd = (f"{shlex.quote(CLAUDE_BIN)} --resume {shlex.quote(src_sid)} "
                    f"--fork-session --model sonnet")
        bridge._run(
            f"tmux new-session -d -s {shlex.quote(fork)} -c {shlex.quote(diag)} "
            f"{shlex.quote(fork_cmd)}"
        )
        time.sleep(12)  # fork TUI load (resumes the source prefix)
        assert fork in bridge._run(
            "tmux list-sessions -F '#{session_name}' 2>/dev/null || echo"
        ).split(), "the --fork-session process exited immediately (fork not created)"
        bridge.keys(fork, "Enter")  # clear any startup/trust gate (harmless if none)
        time.sleep(3)

        # Rewind the FORK to before ALPHA-3.
        _rewind_to_before_last(bridge, fork, ups=1)
        bridge.send(fork, _INTERROGATE)
        bridge.wait_idle(fork, timeout=90)
        time.sleep(1)
        fork_reply = _last_reply_screen(bridge, fork)   # fork is raw-launched (no read_log)
        log.debug("fork: fork interrogation reply=%r", fork_reply)

        # A new independent transcript id should now exist for the diverged fork.
        new_ids = _jsonl_ids(bridge, proj) - ids_before
        log.debug("fork: new forked transcript id(s)=%s (source=%s.jsonl)", new_ids, src_sid)

        assert "ALPHA-1" in fork_reply and "ALPHA-2" in fork_reply, (
            f"fork lost the shared prefix (ALPHA-1/2): {fork_reply!r}"
        )
        assert "ALPHA-3" not in fork_reply, (
            f"fork was not rewound — still remembers ALPHA-3: {fork_reply!r}"
        )

        # The ORIGINAL session must be untouched: still knows all three codewords.
        bridge.send(src, _INTERROGATE)
        bridge.wait_idle(src, timeout=90)
        time.sleep(1)
        src_reply = _last_assistant_log(bridge, src)    # bridge-tracked -> structured
        log.debug("fork: source interrogation reply=%r", src_reply)
        assert "ALPHA-3" in src_reply, (
            f"forking MUTATED the original — source lost ALPHA-3: {src_reply!r} "
            "(that would make it a rewind-in-disguise, not a fork)"
        )
        assert "ALPHA-1" in src_reply and "ALPHA-2" in src_reply, src_reply
        log.debug(
            "fork: WORKS — --fork-session + /rewind-in-fork produced an independent "
            "branch (knows ALPHA-1/2, lost ALPHA-3) while the source stayed intact "
            "(knows ALPHA-1/2/3). Endpoint (§7.5/§9.9 /handoff): fork the session, "
            "rewind the fork to N, return to the normal tmux `--resume <new-id>` path."
        )
    finally:
        for s in (fork, src):
            try:
                for _ in range(2):
                    bridge.keys(s, "Escape")
                    time.sleep(0.2)
            except Exception:
                pass
            try:
                bridge.close(s)
            except Exception as e:
                log.debug("fork: close(%s) raised (non-fatal): %s", s, e)
        bridge._run(f"rm -rf {shlex.quote(diag)}")
        bridge._run(f"rm -rf {proj}")
