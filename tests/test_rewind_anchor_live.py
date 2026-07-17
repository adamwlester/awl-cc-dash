"""Live proof — the §11 #46 rewind-anchor residual, end to end on a REAL agent.

THE DECIDED CONTRACT (docs/ARCHITECTURE.md §7.19/§7.14; pinned hermetically by
``tests/test_readouts_unit.py``'s #46 sections; built at afd1b9f): every
dashboard-initiated turn's Timeline record in the per-agent launch-config
``~/.awl-cc-dash-agents/<tmux-name>/turns.jsonl`` now carries ``"type": "turn"``
plus the turn's TRANSCRIPT ANCHORS — ``prompt_uuid`` (the user-prompt JSONL
entry's own ``uuid``) and ``reply_uuid`` (the turn's closing assistant entry
uuid), lifted at capture from the driver's transcript-anchored events. Each
SUCCESSFUL ``POST /sessions/{id}/rewind`` appends a typed rewind event record
(``{"type": "rewind", "timestamp", "to_prompt_index"}``) to the SAME file —
the JSONL transcript itself is append-only (a rewind writes NOTHING at rewind
time; no engine checkpoint id exists anywhere), so this event line is the only
persisted trace of the rewind. ``GET /sessions/{id}/timeline`` REPLAYS the
interleaved stream server-side (``timeline.replay_timeline``): each row gains
``rolled``, and the response gains merged ``rolled_ranges``
(exclusive-``from``: a row t is rolled iff ``from < t <= to``) + ``rewinds``.
The point of it all: ROLLED MARKING SURVIVES A RELOAD — the renderer's old
client-side ``TL_ROLLED`` memory is deleted, so the server must keep serving
the rolled truth even across its own restart.

WHAT THIS FILE PROVES LIVE (one test, six stages, on a sidecar-OWNED session —
the sidecar subprocess creates the agent via its own ``POST /sessions``, so the
capture path, the rewind endpoint, and the read surface all land in ONE real
process, exactly as the dashboard runs them):

  1. **Three real turns.** ``POST /sessions/{id}/send`` drives three trivial
     prompts (``Reply with exactly: ALPHA / BETA / GAMMA``) on a cheap sonnet
     agent; after each, the sidecar's exactly-once completion capture lands one
     timeline row (captures settle ~1.5s x up to 6 re-lifts after idle — the
     polls below allow for it).
  2. **ANCHOR TRUTH (the headline).** The agent's real ``<claude-session-id>
     .jsonl`` transcript is read raw via the bridge and each timeline row's
     ``prompt_uuid`` must EQUAL the ``uuid`` of the matching user-prompt entry
     (matched by its planted marker text), and ``reply_uuid`` must EQUAL the
     turn's CLOSING assistant entry uuid (the last non-sidechain assistant
     line before the next prompt). Null anchors or mismatched uuids = FAILURE
     — the anchors must be RIGHT, not merely present.
  3. **REWIND.** ``POST /sessions/{id}/rewind {"to_prompt_index": 1}`` -> 200;
     the typed rewind line is then read RAW out of ``turns.jsonl`` via the
     bridge (the endpoint awaits the persist before responding), and
     ``GET /timeline`` shows row 3 ``rolled: true``, rows 1-2 live, and
     ``rolled_ranges == [{"from": 2, "to": 3}]``.
  4. **RESTART SURVIVAL (the residual being closed).** The sidecar subprocess
     is KILLED and a fresh one starts on the SAME runtime dir
     (``AWL_STARTUP_RESTORE=all`` — the documented restore-everything test
     hatch; the tmux agent outlived the sidecar, so this is §9.9's warm
     rebind). The fresh process must serve the IDENTICAL rolled truth —
     per-row ``rolled`` flags, anchors, ``rolled_ranges``, and ``rewinds`` all
     equal to the pre-restart snapshot. This is the reload-amnesia proof at
     the server level.
  5. **POST-REWIND LIVE.** One more prompt (``Reply with exactly: DELTA``)
     lands as row 4, ``rolled: false``, ordinals 1..4 stable, earlier rolled
     state untouched, and its ``prompt_uuid`` equals the NEW transcript branch
     entry's uuid (the rewind restores in-place on the same session id — the
     DELTA prompt appends to the same file as a new branch tip). This stage
     waits for the restored session's HISTORY REPLAY to land in
     ``session.events`` (polled via ``GET /sessions/{id}/history`` until the
     known prompt anchors appear) before sending — the honest "adopt settled"
     gate. Sending BEFORE the first post-restore transcript poll loses a real
     race in the capture path (caught live by this test's first run,
     2026-07-16, and reported as a product finding rather than patched here):
     the flush's synthetic ``running`` sets ``_turn_start_idx`` before the
     replay burst, so the whole replayed history lands INSIDE the new turn's
     anchor/summary window — row 4 came back with ``prompt_uuid`` equal to
     the ALPHA prompt's uuid (the forward lift's first prompt-like entry) and
     a replayed reply can even satisfy ``_saw_reply_since_send``. See
     ``tests/log/rewind_anchor_findings_*`` for the captured evidence.
  6. **Findings** to ``tests/log/rewind_anchor_findings_*.txt`` (+ ``_latest``).

============================================================================
ISOLATION RULES (parallel-safe — sibling agents may be running their OWN live
bridge sessions at the same time; violating any of these can kill their work):
  * ONE test file, its OWN ``TmuxBridge()`` for reads/teardown — NEVER
    conftest's session-scoped ``bridge`` fixture (its setup/teardown call
    ``tmux kill-server``, which would kill every sibling's sessions). We never
    call kill-server.
  * The agent is sidecar-owned; its tmux name is read back authoritatively
    from the project roster (``<cwd>/.awl-cc-dash/state/agents.json``) that
    the sidecar writes through — no name-diff races with sibling spawners.
    Teardown hard-deletes through the sidecar (``DELETE /sessions/{id}?hard=
    true``), with a direct ``close()`` + launch-config ``rm -rf`` fallback.
  * The throwaway WSL cwd (``/home/lester/awl-rwanchor-<uuid8>``), its
    ``~/.claude/projects/<escaped>`` transcripts dir, and the agent's
    ``~/.awl-cc-dash-agents/<tmux-name>`` dir are all removed in teardown.
  * Sessions stay TAB-LESS (the sidecar creates them detached; ``show()`` is
    never used).
  * Port 7690 must be OURS alone: if anything answers ``/health`` before our
    subprocess launches, the test FAILS immediately rather than driving a
    foreign sidecar. Both sidecar subprocesses run on an EMPTY throwaway
    ``AWL_SIDECAR_RUNTIME`` so no real/sibling record is ever visible to them.

Run (from repo root, ONLY this file — not the whole live tier)::

    .\\.venv\\Scripts\\python.exe -m pytest tests\\test_rewind_anchor_live.py -m integration -q
"""
from __future__ import annotations

import json
import logging
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

# Repo root on sys.path so `from bridge import ...` resolves (mirrors the spikes).
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
_SIDECAR = _REPO_ROOT / "sidecar"

from bridge import TmuxBridge  # noqa: E402

log = logging.getLogger(__name__)

pytestmark = [pytest.mark.integration, pytest.mark.slow]

SLUG = "rwanchor"
SIDECAR_URL = "http://127.0.0.1:7690"
SCRATCH = _REPO_ROOT / ".scratch"
LOG_DIR = Path(__file__).resolve().parent / "log"

TURN_TIMEOUT = 240        # send -> completed turn -> settled timeline row
IDLE_TIMEOUT = 180
READY_TIMEOUT = 180       # sidecar boot (restart pays the warm-rebind inside startup)


# --------------------------------------------------------------------------- #
# HTTP + poll helpers
# --------------------------------------------------------------------------- #

def _http(method, path, body=None, timeout=30):
    """Minimal JSON round-trip against the sidecar -> (status, payload)."""
    data = None
    headers = {}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(SIDECAR_URL + path, data=data, headers=headers,
                                 method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8")
            return r.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode(errors="replace")
        try:
            payload = json.loads(raw) if raw else None
        except Exception:  # noqa: BLE001
            payload = raw
        return e.code, payload


def _poll(fn, timeout, interval=1.0):
    """Call ``fn`` until truthy or timeout; returns the last value."""
    end = time.time() + timeout
    val = fn()
    while not val and time.time() < end:
        time.sleep(interval)
        val = fn()
    return val


def _health_ok():
    try:
        with urllib.request.urlopen(f"{SIDECAR_URL}/health", timeout=3) as r:
            data = json.loads(r.read().decode("utf-8"))
        return isinstance(data, dict) and data.get("status") == "ok"
    except Exception:
        return False


def _session_status(sid):
    code, s = _http("GET", f"/sessions/{sid}", timeout=10)
    return (s or {}).get("status") if code == 200 else None


def _get_timeline(sid):
    code, data = _http("GET", f"/sessions/{sid}/timeline", timeout=15)
    return data if code == 200 else None


# --------------------------------------------------------------------------- #
# Sidecar subprocess controller — restartable on ONE runtime dir (the crux of
# stage 4: the second process must rebuild the rolled truth from persisted
# state alone).
# --------------------------------------------------------------------------- #

class _SidecarCtl:
    def __init__(self, runtime_dir: str):
        self.runtime_dir = runtime_dir
        self.proc: subprocess.Popen | None = None
        self._logf = None
        self._n = 0
        self.log_paths: list[Path] = []

    def start(self):
        assert self.proc is None, "previous sidecar still tracked — stop() first"
        self._n += 1
        SCRATCH.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["AWL_SIDECAR_RUNTIME"] = self.runtime_dir  # OUR empty throwaway store
        env["AWL_SIDECAR_HOST"] = "0.0.0.0"            # WSL-reachable (hooks)
        # The documented restore-everything test hatch (§9.1): boot restores
        # every persisted record — on run 1 the store is empty (restores
        # nothing); on run 2 it warm-rebinds OUR still-alive tmux agent.
        env["AWL_STARTUP_RESTORE"] = "all"
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        log_path = SCRATCH / f"{SLUG}_sidecar_{self._n}.log"
        self.log_paths.append(log_path)
        self._logf = open(log_path, "w", encoding="utf-8")
        self.proc = subprocess.Popen(
            [sys.executable, "main.py"], cwd=str(_SIDECAR), env=env,
            stdout=self._logf, stderr=subprocess.STDOUT,
        )
        deadline = time.time() + READY_TIMEOUT
        while time.time() < deadline:
            if self.proc.poll() is not None:
                self._logf.flush()
                tail = log_path.read_text(encoding="utf-8", errors="replace")[-1500:]
                pytest.fail(f"sidecar #{self._n} exited early (rc="
                            f"{self.proc.returncode}). log tail:\n{tail}")
            if _health_ok():
                log.debug("sidecar #%d ready on %s (runtime=%s)",
                          self._n, SIDECAR_URL, self.runtime_dir)
                return
            time.sleep(0.5)
        self.stop()
        pytest.fail(f"sidecar #{self._n} did not become ready on :7690 "
                    f"within {READY_TIMEOUT}s")

    def stop(self):
        """Kill the current subprocess and wait for :7690 to actually free."""
        if self.proc is not None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait(timeout=10)
            self.proc = None
        if self._logf is not None:
            self._logf.close()
            self._logf = None
        assert _poll(lambda: not _health_ok(), 30, 0.5), \
            "port 7690 still answers /health after our sidecar was killed"

    def alive(self):
        return self.proc is not None and self.proc.poll() is None


@pytest.fixture
def br():
    """Our OWN TmuxBridge — read/teardown helpers only. NEVER conftest's shared
    ``bridge`` fixture (kill-server) and never ``show()``/kill-server here."""
    return TmuxBridge()


@pytest.fixture
def diag_dir(br):
    """A fresh, empty WSL throwaway cwd; removed (with its transcripts project
    dir) after the test."""
    path = f"/home/lester/awl-{SLUG}-{uuid.uuid4().hex[:8]}"
    proj = "~/.claude/projects/-home-lester" + \
        path[len("/home/lester"):].replace("/", "-")
    br._run(f"mkdir -p {shlex.quote(path)}")
    yield path
    br._run(f"rm -rf {shlex.quote(path)}")
    br._run(f"rm -rf {proj}")


@pytest.fixture
def sidecar_ctl():
    """A restartable REAL-sidecar controller on ONE throwaway runtime dir.

    Refuses to run if a FOREIGN server already answers :7690 (we must own the
    port exclusively — driving someone else's sidecar would be wrong). Teardown
    stops whatever subprocess is current and removes the runtime dir.
    """
    if _health_ok():
        pytest.fail(
            "port 7690 already answers /health before we launched our sidecar "
            "— a foreign sidecar is running; STOPPING rather than driving it. "
            "Stop it and re-run this test in isolation.")
    runtime_dir = tempfile.mkdtemp(prefix=f"awl-{SLUG}-rt-")
    ctl = _SidecarCtl(runtime_dir)
    try:
        yield ctl
    finally:
        try:
            ctl.stop()
        finally:
            shutil.rmtree(runtime_dir, ignore_errors=True)


# --------------------------------------------------------------------------- #
# Transcript + roster helpers (raw reads via the bridge — the ground truth)
# --------------------------------------------------------------------------- #

def _roster_record(br_, diag, sid):
    """The sidecar-written project-roster record for ``sid`` — read raw from
    ``<cwd>/.awl-cc-dash/state/agents.json`` (write-through per §8.3), or None."""
    raw = br_._run(
        f"cat {shlex.quote(diag + '/.awl-cc-dash/state/agents.json')} "
        "2>/dev/null || true")
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError, TypeError):
        return None
    agents = data.get("agents") if isinstance(data, dict) else None
    return (agents or {}).get(sid)


def _transcript_entries(br_, transcript_path):
    """Every parseable JSONL entry of the agent's REAL transcript, in file
    order — the uuid ground truth the anchors are asserted against."""
    raw = br_._run(f"cat {shlex.quote(transcript_path)} 2>/dev/null || true")
    entries = []
    for ln in (raw or "").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            obj = json.loads(ln)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(obj, dict):
            entries.append(obj)
    return entries


def _is_operator_prompt(entry):
    """A REAL operator prompt entry: type user, not sidechain/meta, content a
    plain string or blocks with no tool_result (mirrors timeline._prompt_like,
    but applied to the RAW transcript shape)."""
    if entry.get("type") != "user":
        return False
    if entry.get("isSidechain") or entry.get("isMeta"):
        return False
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, list):
        return not any(isinstance(b, dict) and b.get("type") == "tool_result"
                       for b in content)
    return isinstance(content, str)


def _prompt_entry_for(entries, marker):
    """The single operator-prompt entry whose text carries ``marker``."""
    hits = [e for e in entries
            if _is_operator_prompt(e) and marker in json.dumps(e.get("message"))]
    assert len(hits) == 1, (
        f"expected exactly one operator-prompt transcript entry containing "
        f"{marker!r}, found {len(hits)}")
    return hits[0]


def _closing_assistant_for(entries, prompt_entry):
    """The CLOSING (last) non-sidechain assistant entry of the turn opened by
    ``prompt_entry`` — the window runs from that prompt to the next operator
    prompt (or EOF)."""
    start = entries.index(prompt_entry)
    closing = None
    for e in entries[start + 1:]:
        if _is_operator_prompt(e):
            break
        if e.get("type") == "assistant" and not e.get("isSidechain"):
            closing = e
    return closing


def _write_findings(lines):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    text = "\n".join(str(x) for x in lines) + "\n"
    (LOG_DIR / f"rewind_anchor_findings_{stamp}.txt").write_text(
        text, encoding="utf-8")
    (LOG_DIR / "rewind_anchor_findings_latest.txt").write_text(
        text, encoding="utf-8")


def _rolled_view(tl):
    """The comparable rolled-truth projection of a timeline response."""
    return {
        "count": tl.get("count"),
        "rows": [(r.get("turn"), bool(r.get("rolled")), r.get("prompt_uuid"),
                  r.get("reply_uuid")) for r in tl.get("turns", [])],
        "rolled_ranges": tl.get("rolled_ranges"),
        "rewinds": [(w.get("to_prompt_index")) for w in tl.get("rewinds", [])],
    }


# --------------------------------------------------------------------------- #
# THE PROOF — six stages, one sidecar-owned agent
# --------------------------------------------------------------------------- #

def test_rewind_anchor_truth_and_restart_survival_live(sidecar_ctl, br, diag_dir):
    """#46 rewind anchors live: real anchors on every row (headline), the typed
    rewind event persisted to turns.jsonl, server-replayed rolled state, rolled
    truth IDENTICAL across a sidecar kill+restart, and a post-rewind turn that
    lands live with a correct new-branch anchor."""
    findings = [
        "#46 rewind-anchor live proof — sidecar-owned session",
        f"date: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"commit under proof: afd1b9f (feature) @ repo HEAD",
    ]
    ctl = sidecar_ctl
    sid = None
    tmux = None
    words = ["ALPHA", "BETA", "GAMMA"]
    try:
        # ---- 0. Our sidecar #1 owns :7690 (foreign-server guard ran in the
        # fixture before this line). --------------------------------------
        ctl.start()
        findings.append(f"sidecar #1 up on :7690 (runtime={ctl.runtime_dir})")

        # ---- 1. Sidecar-owned agent + three trivial turns -----------------
        code, created = _http("POST", "/sessions", {
            "model": "sonnet",                      # cheap model
            "cwd": diag_dir,                        # default permissions
            "identity": {"name": f"{SLUG}-proof"},
        }, timeout=120)
        assert code == 200 and created, f"POST /sessions failed: {code} {created!r}"
        sid = created["session_id"]
        findings.append(f"created sidecar-owned session {sid} (cwd={diag_dir})")

        # Authoritative tmux name from the write-through project roster —
        # no awl-* name-diff races with sibling spawners.
        rec = _poll(lambda: _roster_record(br, diag_dir, sid), 60, 2.0)
        assert rec and rec.get("tmux_name"), (
            f"project roster never showed session {sid} with a tmux_name — "
            f"record: {rec!r}")
        tmux = rec["tmux_name"]
        findings.append(f"tmux session (from roster): {tmux}")

        assert _poll(lambda: _session_status(sid) == "idle", IDLE_TIMEOUT), \
            f"agent never reached idle (status={_session_status(sid)!r})"

        for i, w in enumerate(words, 1):
            code, _ = _http("POST", f"/sessions/{sid}/send",
                            {"prompt": f"Reply with exactly: {w}"}, timeout=30)
            assert code == 200, f"send #{i} ({w}) failed: {code}"
            # The row lands only at the exactly-once completion capture, which
            # settles ~1.5s x up to 6 re-lifts after idle — poll the timeline,
            # not just the status.
            got = _poll(lambda: (_get_timeline(sid) or {}).get("count") == i,
                        TURN_TIMEOUT, 2.0)
            assert got, (
                f"timeline row {i} ({w}) never landed within {TURN_TIMEOUT}s — "
                f"timeline: {_get_timeline(sid)!r}")
            assert _poll(lambda: _session_status(sid) == "idle", 30), \
                f"agent not idle after turn {i}"
            findings.append(f"turn {i} ({w}): completed; timeline count={i}")

        tl = _get_timeline(sid)
        rows = tl["turns"]
        assert [r["turn"] for r in rows] == [1, 2, 3], f"ordinals wrong: {rows!r}"
        assert tl["rolled_ranges"] == [] and tl["rewinds"] == [], (
            f"pre-rewind timeline already claims rolled state: {tl!r}")
        assert all(r.get("rolled") is False for r in rows), \
            f"pre-rewind rows must all be live: {rows!r}"

        # ---- 2. ANCHOR TRUTH (headline): rows vs the RAW transcript -------
        rec = _roster_record(br, diag_dir, sid) or {}
        transcript_path = rec.get("transcript_path")
        if not transcript_path:
            csid = rec.get("claude_session_id")
            assert csid, f"roster record has neither transcript_path nor claude_session_id: {rec!r}"
            proj = "~/.claude/projects/-home-lester" + \
                diag_dir[len("/home/lester"):].replace("/", "-")
            transcript_path = f"{proj}/{csid}.jsonl"
        findings.append(f"transcript: {transcript_path}")
        entries = _transcript_entries(br, transcript_path)
        assert entries, f"could not read the transcript at {transcript_path}"

        for i, w in enumerate(words, 1):
            row = rows[i - 1]
            assert row.get("prompt_uuid") and row.get("reply_uuid"), (
                f"NULL anchor on row {i} ({w}) — anchors must be real: {row!r}")
            p = _prompt_entry_for(entries, f"Reply with exactly: {w}")
            assert row["prompt_uuid"] == p.get("uuid"), (
                f"row {i} ({w}) prompt_uuid MISMATCH: timeline "
                f"{row['prompt_uuid']!r} != transcript user entry {p.get('uuid')!r}")
            closing = _closing_assistant_for(entries, p)
            assert closing is not None, (
                f"no assistant entry found in turn {i}'s transcript window")
            assert row["reply_uuid"] == closing.get("uuid"), (
                f"row {i} ({w}) reply_uuid MISMATCH: timeline "
                f"{row['reply_uuid']!r} != closing assistant entry "
                f"{closing.get('uuid')!r}")
            findings.append(
                f"ANCHOR TRUTH row {i} ({w}): prompt_uuid={row['prompt_uuid']} "
                f"reply_uuid={row['reply_uuid']} — both equal the transcript")

        # ---- 3. REWIND: endpoint -> typed line in turns.jsonl -> replay ---
        code, body = _http("POST", f"/sessions/{sid}/rewind",
                           {"to_prompt_index": 1}, timeout=180)
        assert code == 200 and (body or {}).get("status") == "ok", \
            f"rewind failed: {code} {body!r}"
        findings.append(f"POST /rewind {{to_prompt_index: 1}} -> 200 {body!r}")

        def _raw_turns_lines():
            return [ln for ln in (br.turns_read(tmux) or "").splitlines()
                    if ln.strip()]

        # The endpoint awaits the persist, but allow a short window for the
        # transient-failure re-drain path.
        assert _poll(lambda: any('"type":"rewind"' in ln.replace(" ", "")
                                 for ln in _raw_turns_lines()), 15, 1.0), (
            "no typed rewind line in turns.jsonl after a 200 rewind — raw "
            f"file:\n{br.turns_read(tmux)}")
        raw_recs = [json.loads(ln) for ln in _raw_turns_lines()]
        rewind_recs = [r for r in raw_recs if r.get("type") == "rewind"]
        turn_recs = [r for r in raw_recs if r.get("type") in (None, "turn")]
        assert len(rewind_recs) == 1 and \
            rewind_recs[0].get("to_prompt_index") == 1 and \
            rewind_recs[0].get("timestamp"), (
            f"malformed/duplicated rewind record(s): {rewind_recs!r}")
        assert len(turn_recs) == 3 and \
            all(r.get("prompt_uuid") for r in turn_recs), (
            f"turns.jsonl turn records wrong/anchorless: {turn_recs!r}")
        findings.append(f"turns.jsonl raw rewind line: {json.dumps(rewind_recs[0])}")

        tl_rolled = _get_timeline(sid)
        assert [(r["turn"], r["rolled"]) for r in tl_rolled["turns"]] == \
            [(1, False), (2, False), (3, True)], (
            f"replayed rolled flags wrong after rewind: {tl_rolled['turns']!r}")
        assert tl_rolled["rolled_ranges"] == [{"from": 2, "to": 3}], (
            f"rolled_ranges wrong: {tl_rolled['rolled_ranges']!r}")
        assert len(tl_rolled["rewinds"]) == 1 and \
            tl_rolled["rewinds"][0]["to_prompt_index"] == 1, (
            f"rewinds list wrong: {tl_rolled['rewinds']!r}")
        findings.append(
            f"post-rewind replay: rolled=[F,F,T], ranges={tl_rolled['rolled_ranges']}, "
            f"rewinds={tl_rolled['rewinds']}")
        before = _rolled_view(tl_rolled)

        # ---- 4. RESTART SURVIVAL: kill sidecar, fresh proc, same truth ----
        ctl.stop()
        findings.append("sidecar #1 KILLED (port verified freed)")
        ctl.start()   # same runtime dir; AWL_STARTUP_RESTORE=all warm-rebinds
        findings.append("sidecar #2 up on the SAME runtime dir (restore=all)")

        code, s2 = _http("GET", f"/sessions/{sid}", timeout=15)
        assert code == 200, (
            f"fresh sidecar did not re-adopt session {sid}: GET /sessions/"
            f"{sid} -> {code} {s2!r}")
        tl_after = _poll(lambda: _get_timeline(sid), 30, 1.0)
        assert tl_after, "fresh sidecar serves no timeline for the adopted session"
        after = _rolled_view(tl_after)
        assert after == before, (
            "ROLLED TRUTH DID NOT SURVIVE THE RESTART —\n"
            f"before: {before!r}\nafter:  {after!r}")
        findings.append(
            "RESTART SURVIVAL: fresh sidecar serves IDENTICAL rolled truth "
            f"(rows/anchors/ranges/rewinds): ranges={tl_after['rolled_ranges']}")

        # ---- 5. POST-REWIND LIVE: DELTA lands live on the new branch ------
        assert _poll(lambda: _session_status(sid) == "idle", IDLE_TIMEOUT), \
            f"re-adopted agent never idle (status={_session_status(sid)!r})"
        # Adopt-settled gate: wait for the restored driver's FIRST transcript
        # poll to replay the history into session.events (all three known
        # prompt anchors visible via /history) BEFORE sending. A send that
        # beats the replay races the capture window — the replay burst lands
        # inside the new turn's window and the anchor lift picks the replayed
        # ALPHA prompt (live-caught on this test's first run; reported as a
        # product finding, not masked: with this gate the contract path is
        # exercised, without it the race path is).
        known_prompts = {r[2] for r in before["rows"]}

        def _replay_settled():
            code2, evs = _http("GET", f"/sessions/{sid}/history", timeout=15)
            if code2 != 200 or not isinstance(evs, list):
                return False
            anchors = {e.get("anchor") for e in evs if isinstance(e, dict)}
            return known_prompts <= anchors

        assert _poll(_replay_settled, 60, 1.0), (
            "restored session never replayed its transcript history into "
            "events (adopt-settled gate) — /history lacks the known prompt "
            "anchors")
        findings.append("adopt-settled gate: history replay landed "
                        "(all 3 prompt anchors visible in /history)")
        code, _ = _http("POST", f"/sessions/{sid}/send",
                        {"prompt": "Reply with exactly: DELTA"}, timeout=30)
        assert code == 200, f"post-rewind send failed: {code}"
        got = _poll(lambda: (_get_timeline(sid) or {}).get("count") == 4,
                    TURN_TIMEOUT, 2.0)
        assert got, (
            f"post-rewind DELTA row never landed — timeline: {_get_timeline(sid)!r}")
        tl4 = _get_timeline(sid)
        assert [(r["turn"], r["rolled"]) for r in tl4["turns"]] == \
            [(1, False), (2, False), (3, True), (4, False)], (
            f"post-rewind rows/flags wrong: {tl4['turns']!r}")
        assert tl4["rolled_ranges"] == [{"from": 2, "to": 3}], (
            f"rolled_ranges drifted after the live turn: {tl4['rolled_ranges']!r}")
        row4 = tl4["turns"][3]
        assert row4.get("prompt_uuid") and row4.get("reply_uuid"), \
            f"DELTA row has null anchors: {row4!r}"
        entries2 = _transcript_entries(br, transcript_path)
        p4 = _prompt_entry_for(entries2, "Reply with exactly: DELTA")
        assert row4["prompt_uuid"] == p4.get("uuid"), (
            f"DELTA prompt_uuid MISMATCH: timeline {row4['prompt_uuid']!r} != "
            f"new-branch transcript entry {p4.get('uuid')!r}")
        closing4 = _closing_assistant_for(entries2, p4)
        assert closing4 is not None and row4["reply_uuid"] == closing4.get("uuid"), (
            f"DELTA reply_uuid MISMATCH: timeline {row4['reply_uuid']!r} != "
            f"closing assistant {closing4 and closing4.get('uuid')!r}")
        findings.append(
            f"POST-REWIND LIVE: DELTA row 4 rolled=false, prompt_uuid="
            f"{row4['prompt_uuid']} == new branch entry; reply_uuid="
            f"{row4['reply_uuid']} == closing assistant entry")
        findings.append(f"DELTA row summary (evidence): {row4.get('summary')!r}")
        findings.append(
            "VERDICT: #46 anchors are REAL (all four rows match the raw "
            "transcript uuids), the typed rewind event persists, the replay "
            "rolls exactly row 3, and the rolled truth is byte-identical "
            "across a sidecar kill+restart — reload amnesia closed at the "
            "server level.")
    finally:
        # ---- 6. Teardown: hard-delete through the sidecar; direct fallback -
        if sid and _health_ok():
            code, _ = _http("DELETE", f"/sessions/{sid}?hard=true", timeout=60)
            findings.append(f"teardown: DELETE /sessions/{sid}?hard=true -> {code}")
        if tmux:
            still = _poll(
                lambda: tmux not in {s["name"] for s in br.list()}, 20)
            if not still:
                try:
                    br.close(tmux)   # kills ONLY our own session
                    findings.append("teardown: hard-delete left tmux alive; "
                                    "closed it directly")
                except Exception as e:  # noqa: BLE001
                    findings.append(f"teardown: direct close failed: {e}")
            else:
                findings.append("teardown: tmux session gone")
            # Belt-and-suspenders: the launch-config dir (turns.jsonl home).
            br._run(f"rm -rf ~/.awl-cc-dash-agents/{shlex.quote(tmux)}")
        _write_findings(findings)
