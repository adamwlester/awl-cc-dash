"""Live spike — subagent pending-vs-active status (§10 item 8).

The single empirical question this file answers with a REAL live run: does a
running subagent's OWN transcript file
(``<project_dir>/<parent_sid>/subagents/agent-<agentId>.jsonl``) exist and
*advance* — file mtime (`stat -c %Y`) and/or last-event timestamp / line count —
*while the subagent is working*, so we can read back "active" vs "pending/quiet"
deterministically? A corroborating signal is the deterministic pending-tools
overlay on the subagent transcript (any `tool_use` id without a matching
`tool_result` ⇒ mid-tool ⇒ active — agent-dashboard `pending-tools.js`,
research Q2 / Q3 #3).

This is a **spike-or-omit** probe (ARCHITECTURE §10 item 8). It drives a real
Claude Code TUI parent (bridge driver) that spawns one slow, multi-step
subagent, then samples the subagent transcript's recency signal across the run.

  * WORKS  → the mtime / last-event recency (and/or pending-tools set) moves
             while the subagent is active and quiets after; keep this as a
             durable live test that unblocks item 8 toward "live pending vs
             active".
  * IMPOSSIBLE (after a REAL run) → the file only appears at completion, or its
             mtime never advances mid-run; that is a FINDING (see the DEVLOG /
             summary), NOT a fabricated green. The sampled sequence is logged at
             DEBUG in tests/log/ as the evidence.

The load-bearing risk (§3 of the build prompt): Claude Code may buffer the
subagent transcript and write ``agent-<id>.jsonl`` only on completion — then
mtime-recency yields no live active signal. That negative is a real result.

FINDINGS (first live run — Claude Code 2.1.198, WSL2/tmux, one subagent doing 5
sequential ``sleep 4`` steps). **WORKS — the live signal is real and refutes the
buffering risk.** The subagent's own ``agent-<id>.jsonl`` appeared ~3s after the
parent's turn started (NOT buffered to completion), and every recency channel
advanced monotonically WHILE the subagent worked, then froze the moment it
finished:
  * ``stat -c %Y`` mtime advanced 706→709→718→720→731→741→753→763 across the run,
    then held 763 across both post-completion samples (the cheapest reliable
    signal).
  * line count grew 3→14 and last-event ``timestamp`` advanced ~16:11:46→16:12:43,
    both freezing at completion (corroborating).
  * the deterministic pending-tools overlay (tool_use ids minus tool_result ids
    on the subagent transcript) was nonempty mid-run and 0 before the first tool
    / after completion — a clean active-vs-pending distinction on its own.
Caveat: recency is flush-lagged by a couple of seconds, so read "active" as
"mtime advanced within the last ~N seconds", not "advanced since the last poll".
This unblocks §10 item 8 toward its Desired behavior (live pending vs active).

Run (single file, in isolation — NEVER the whole live tier)::

    .\\.venv\\Scripts\\python.exe -m pytest tests/test_subagent_status_live.py -m integration

-----------------------------------------------------------------------------
ISOLATION RULES (parallel-safe — CRITICAL; sibling agents may hold live tmux
sessions at the same time). Reproduced from the build prompt §7 and obeyed here:
  * ONE new file only: this file. Nothing else is added.
  * tmux sessions are uniquely named + slug-prefixed (``substat-<uuid8>`` for the
    sidecar session id; the driver mints its own ``awl-<uuid8>`` tmux name, which
    we address ONLY via ``d.driver.tmux_name``). We touch no other session.
  * NEVER ``tmux kill-server`` (directly or via any helper). Teardown removes ONLY
    our own driver session (``d.close()`` → kills just this tmux name) and our own
    throwaway WSL dir. We do NOT use conftest's session-scoped ``bridge`` /
    ``diag_dir`` fixtures — their setup AND teardown call ``tmux kill-server``,
    which would kill sibling agents' sessions. We instantiate our OWN
    ``TmuxBridge()`` for WSL shell helpers instead.
  * We do NOT edit tests/conftest.py, pyproject.toml, or tests/README.md.
  * Bridge sessions stay TAB-LESS — never ``show=True`` / never ``show()``.
-----------------------------------------------------------------------------
"""

import asyncio
import json
import logging
import shlex
import sys
import time
import uuid
from pathlib import Path

import pytest

# Make the sidecar's modules importable as top-level (it runs with its own dir on
# sys.path, not the repo root), and the repo-root ``bridge`` package importable.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SIDECAR = _REPO_ROOT / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from drivers.bridge import BridgeDriver  # noqa: E402
from drivers.base import DriverConfig  # noqa: E402
from bridge import TmuxBridge  # noqa: E402
from bridge.transcript import _resolve_project_dir  # noqa: E402

log = logging.getLogger("tests.subagent_status")

pytestmark = [pytest.mark.integration, pytest.mark.slow]


# The parent must DELEGATE slow, observable, multi-step work to one subagent so
# the subagent stays alive and writes transcript entries for ~20-30s.
# NOTE: this prompt is sent through the bridge's ``send()`` (tmux send-keys), and
# the wsl.exe argv/interop layer does NOT reliably preserve single-quote
# literalness — a backtick in the text gets command-substituted by bash. An early
# live run embedded shell like ``sleep 4 && echo step1`` in backticks; bash
# actually *ran* those five sleeps during parsing (~20s) and blew send()'s 10s
# timeout. So keep this prompt free of backticks and shell metachars (`` ` `` &&
# | ; $()): describe the steps in plain English and let the subagent write its
# own Bash (the subagent's tool calls do NOT go through this quoting path). Also
# keep it PURE ASCII (non-ASCII argv is likewise mangled through wsl.exe).
_PARENT_PROMPT = (
    "Use the Agent tool to spawn ONE general-purpose subagent. Instruct that "
    "subagent to do slow sequential work as five SEPARATE Bash commands run one "
    "after another: first a Bash command that sleeps 4 seconds and then prints "
    "step1; then a second that sleeps 4 seconds and prints step2; then a third "
    "for step3; a fourth for step4; and a fifth for step5. Each of the five must "
    "sleep 4 seconds before printing, and they must run in order, not in "
    "parallel. The subagent must run all five and report DONE when finished. Do "
    "NOT run the steps yourself. You MUST delegate the whole thing to the "
    "subagent via the Agent tool."
)


class _Driven:
    """Run a BridgeDriver and pump its events in the background (so the driver
    keeps polling its transcript), exposing the driver — mirrors the finisher."""

    def __init__(self, cwd, session_id):
        self.events: list[dict] = []
        self.driver = BridgeDriver(
            # bypassPermissions so the subagent's Bash steps run without stopping
            # on a permission prompt — this spike is about status, not permissions.
            DriverConfig(cwd=cwd, permission_mode="bypassPermissions"),
            self.events.append,
            session_id=session_id,
        )
        self._task = None

    async def start(self):
        await self.driver.start()
        self._task = asyncio.create_task(self._consume())

    async def _consume(self):
        try:
            async for e in self.driver.events():
                self.events.append(e)
        except asyncio.CancelledError:
            return

    async def close(self):
        if self._task:
            self._task.cancel()
        await self.driver.close()  # kills ONLY this driver's own tmux session


# --- WSL read-back helpers (via our OWN bridge) ------------------------------

def _stat_mtime(bridge, path):
    """`stat -c %Y <file>` → int epoch mtime, or None if the file is missing."""
    out = bridge._run(f"stat -c %Y {shlex.quote(path)} 2>/dev/null || echo __MISSING__")
    out = out.strip()
    if out == "__MISSING__" or not out:
        return None
    try:
        return int(out.splitlines()[-1].strip())
    except (ValueError, IndexError):
        return None


def _read_jsonl(bridge, path):
    """cat a JSONL file and return parsed entries (empty list if missing)."""
    raw = bridge._run(f"cat {shlex.quote(path)} 2>/dev/null || true")
    entries = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def _last_timestamp(entries):
    for e in reversed(entries):
        ts = e.get("timestamp")
        if ts:
            return ts
    return None


def _pending_tool_ids(entries):
    """Deterministic pending-tools overlay on a subagent transcript.

    Collect `tool_use` ids from assistant entries minus `tool_result`
    `tool_use_id`s from user entries; a nonempty set ⇒ the subagent is mid-tool
    = active (agent-dashboard `pending-tools.js`; research Q2 / Q3 #3).
    """
    tool_use_ids: set = set()
    tool_result_ids: set = set()
    for e in entries:
        msg = e.get("message") or {}
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        if e.get("type") == "assistant":
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("id"):
                    tool_use_ids.add(b["id"])
        elif e.get("type") == "user":
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_result" and b.get("tool_use_id"):
                    tool_result_ids.add(b["tool_use_id"])
    return tool_use_ids - tool_result_ids


def _resolve_subagents_dir(bridge, driver):
    """``<project_dir>/<parent_sid>/subagents`` for the driver's session, or None.

    Resolves the way ``find_transcript`` does: pane cwd → ~/.claude/projects
    subdir; the parent sid is the claude ``--session-id`` the driver launched
    with (``driver._claude_session_id``). The subagents live under
    ``<project_dir>/<parent_sid>/subagents/`` (bridge.py ``derive_subagents``).
    """
    sid = getattr(driver, "_claude_session_id", None)
    if not sid:
        return None
    try:
        cwd = bridge._tmux(
            f"display-message -t '{driver.tmux_name}' -p '#{{pane_current_path}}'"
        ).strip()
    except Exception:
        return None
    if not cwd:
        return None
    project_dir = _resolve_project_dir(bridge, cwd)
    if not project_dir:
        return None
    return f"{project_dir}/{sid}/subagents"


def _list_agent_files(bridge, subagents_dir):
    out = bridge._run(f"ls {subagents_dir}/agent-*.jsonl 2>/dev/null || true")
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


# -----------------------------------------------------------------------------

def test_subagent_live_active_signal():
    """Prove (or disprove) a live active-vs-pending signal for a running subagent.

    Drives a real parent that delegates slow multi-step work to one subagent,
    then samples the subagent transcript's mtime / last-event / pending-tools
    recency across the run. Asserts the file appeared DURING the run AND a live
    signal moved (mtime strictly advanced across consecutive samples, or the
    pending-tools set was nonempty at some sample). If neither moves, the
    assertion fails by design — that is the IMPOSSIBLE finding, with the raw
    sampled sequence in tests/log/ as the evidence.
    """
    my_bridge = TmuxBridge()
    suffix = uuid.uuid4().hex[:8]
    wsl_dir = f"/home/lester/awl-substat-{suffix}"
    my_bridge._run(f"mkdir -p {wsl_dir}")

    result: dict = {}

    async def flow():
        d = _Driven(wsl_dir, f"substat-{suffix}")
        # Record the driver's own minted tmux name (awl-<uuid8>) up front so the
        # outer teardown can close exactly it even if start() throws mid-way.
        result["tmux_name"] = d.driver.tmux_name
        await d.start()
        tmux = d.driver.tmux_name
        log.debug("parent tmux=%s claude_sid=%s cwd=%s",
                  tmux, d.driver._claude_session_id, wsl_dir)
        try:
            await d.driver.send(_PARENT_PROMPT)

            # 1) Resolve the subagents dir (retry as the project dir appears).
            subagents_dir = None
            for _ in range(60):
                subagents_dir = _resolve_subagents_dir(my_bridge, d.driver)
                if subagents_dir:
                    break
                await asyncio.sleep(1.0)
            log.debug("subagents_dir=%s", subagents_dir)
            assert subagents_dir, "could not resolve the subagents dir for the parent session"

            # 2) Poll for the subagent's own transcript file to appear.
            agent_file = None
            first_seen_t = None
            t0 = time.monotonic()
            while time.monotonic() - t0 < 120:
                files = _list_agent_files(my_bridge, subagents_dir)
                if files:
                    agent_file = files[0]
                    first_seen_t = round(time.monotonic() - t0, 1)
                    break
                await asyncio.sleep(1.5)
            log.debug("subagent file appeared=%s at t+%ss file=%s",
                      agent_file is not None, first_seen_t, agent_file)

            samples: list[dict] = []
            seen_advance = False  # defined here so the derivation is safe if the
            #                       subagent file never appears (samples stays []).
            if agent_file:
                # 3) Sample the recency signal repeatedly, DRIVEN OFF THE SUBAGENT
                # TRANSCRIPT ITSELF (not the parent transcript — that flush-lags,
                # which made an earlier version flaky). mtime advancing between two
                # polls means the subagent wrote entries between them = active;
                # mtime holding steady for several polls means it went quiet. Stop
                # once we've seen it advance and then hold for 3 consecutive polls.
                prev_mtime = None
                stable = 0
                for i in range(35):
                    mtime = _stat_mtime(my_bridge, agent_file)
                    entries = _read_jsonl(my_bridge, agent_file)
                    pend = _pending_tool_ids(entries)
                    sample = {
                        "i": i,
                        "t": round(time.monotonic() - t0, 1),
                        "mtime": mtime,
                        "lines": len(entries),
                        "last_ts": _last_timestamp(entries),
                        "pending": len(pend),
                    }
                    samples.append(sample)
                    log.debug("sample %s", sample)

                    if prev_mtime is not None and mtime is not None:
                        if mtime > prev_mtime:
                            seen_advance = True
                            stable = 0
                        elif mtime == prev_mtime:
                            stable += 1
                    prev_mtime = mtime

                    if seen_advance and stable >= 3:
                        break  # advanced, then quiet for 3 polls → subagent done
                    await asyncio.sleep(3.0)

            # 4) Derive the signals from the sampled sequence (subagent-file only).
            mtimes = [s["mtime"] for s in samples]
            mtime_advanced = any(
                a is not None and b is not None and b > a
                for a, b in zip(mtimes, mtimes[1:])
            )
            lines_seq = [s["lines"] for s in samples]
            lines_grew = any(b > a for a, b in zip(lines_seq, lines_seq[1:]))
            # The pending-tools overlay on the subagent's OWN transcript: nonempty
            # at any sample ⇒ the subagent was mid-tool = active at that moment.
            pending_nonempty_midrun = any(s["pending"] > 0 for s in samples)
            # Quiet-after: the trailing samples share one mtime after the last
            # advance (the file stopped being written once the subagent finished).
            went_quiet = (
                seen_advance and len(mtimes) >= 2
                and mtimes[-1] is not None and mtimes[-1] == mtimes[-2]
            )

            result.update({
                "file_appeared": agent_file is not None,
                "first_seen_t": first_seen_t,
                "n_samples": len(samples),
                "mtime_advanced": mtime_advanced,
                "lines_grew": lines_grew,
                "pending_nonempty_midrun": pending_nonempty_midrun,
                "went_quiet_after": went_quiet,
                "samples": samples,
            })
            log.debug("RESULT SUMMARY: %s", {k: v for k, v in result.items() if k != "samples"})

            # 5) The assertions — the crux is MOVEMENT of a live signal, not the
            # file's mere eventual presence.
            assert agent_file is not None, (
                "subagent transcript never appeared during the run — the parent "
                "may not have spawned a subagent, or the path assumption is wrong. "
                f"subagents_dir={subagents_dir}"
            )
            summary = {k: v for k, v in result.items() if k != "samples"}
            assert mtime_advanced or pending_nonempty_midrun, (
                "no live active signal: the subagent transcript's mtime never "
                "advanced across consecutive live samples AND the pending-tools "
                "set was never nonempty mid-run — i.e. no readable active-vs-"
                f"pending distinction. summary={summary}"
            )
        finally:
            await d.close()

    try:
        asyncio.run(flow())
    finally:
        # Belt-and-suspenders: ensure ONLY our own session is gone, then our dir.
        # ``d.close()`` in flow() already kills it; this covers a start() failure.
        name = result.get("tmux_name")
        if name:
            try:
                my_bridge.close(name)  # raises if already gone → swallowed
            except Exception:
                pass
        try:
            my_bridge._run(f"rm -rf {wsl_dir}")
        except Exception:
            pass
