r"""Live spike — the Claude Code **workflow engine** (the `/workflows` / `Workflow`
tool surface), from the outside.

The single question this file answers with a REAL run: when a Claude Code
session runs a *workflow* (a JS orchestration script that fans out
``workflow-subagent`` children), what does it write to disk, is that telemetry
usable by an external observer (our Electron/FastAPI sidecar), and — the open
question from
``dev/notes/research/claude-code-workflow-orchestration-report-2026-07-04.md`` —
is the run manifest written **live** (incrementally, mid-run) or only **at
completion**? Everything here is grounded in the on-disk artifacts a workflow
drops under the session store::

    <project>/<sessionId>/
      workflows/<runId>.json                         # the RUN MANIFEST (rich state)
      workflows/scripts/<name>-<runId>.js            # the persisted script
      subagents/workflows/<runId>/journal.jsonl      # append-only live event log
      subagents/workflows/<runId>/agent-<id>.jsonl   # full per-subagent transcript
      subagents/workflows/<runId>/agent-<id>.meta.json

THE LOAD-BEARING CONSTRAINT (read this before you touch it): a workflow can only
be launched by a Claude session issuing the ``Workflow`` tool call — it is
*parent-mediated*, there is no out-of-process launch API. So **this test does not
launch anything**; it is a pure OBSERVER. A driver agent launches the subject
workflow and points the probe at the run. That is "the deal", written out step by
step in ``tests/workflow_probe/RUNBOOK.md`` — any agent can follow it cold, no
human in the loop.

  * WORKS  → the journal streams ``started``/``result`` lines incrementally while
             the run is in flight, the manifest schema matches what the dashboard
             would consume, and every manifest agent record reconciles with the
             journal + the per-subagent transcripts. Keep this as the durable
             evidence that the sidecar can render workflows from files alone.
  * NEGATIVE (after a REAL run) → e.g. the journal only appears at completion, or
             the manifest schema drifts from the documented shape. That is a
             FINDING (written to tests/log/workflow_probe_findings_latest.txt),
             NOT a fabricated green.

HOW TO RUN — two modes (see RUNBOOK.md for the full driver protocol):

  1. LIVE (answers the manifest-timing question). A driver agent launches the
     subject workflow, then IMMEDIATELY runs the probe against the transcriptDir
     the launch returned, so the probe catches the run mid-flight::

         # after Workflow({scriptPath:".../tests/workflow_probe/subject_workflow.js"})
         # returns a transcriptDir:
         $env:AWLCC_WF_TRANSCRIPT_DIR = "<that transcriptDir>"
         .\.venv\Scripts\python.exe -m pytest tests/workflow_probe -m integration

  2. POST-HOC (schema + reconciliation only; manifest-timing INCONCLUSIVE). Point
     it at any already-completed run dir — the probe validates structure without
     needing a fresh launch. If ``AWLCC_WF_TRANSCRIPT_DIR`` is unset it
     auto-discovers the most recently modified workflow run under
     ``~/.claude/projects`` (logged), and if none exists it SKIPS with the
     driver instructions.

FINDINGS (live runs `wf_e03d4702-80f`, `wf_bc9c13b5-66d` — Claude Code 2.1.201,
7/7 green; latest evidence in tests/log/workflow_probe_findings_latest.txt):
  * ``journal.jsonl`` STREAMS incrementally — the live signal. `started`/`result`
    lines appeared as agents ran, with `started` count leading `result` mid-flight.
  * The ``<runId>.json`` manifest is written **COMPLETION-ONLY** — it does not exist
    until the run reaches a terminal status. Tail `journal.jsonl` for live progress;
    treat the manifest as the final snapshot.
  * Schema (structured-output) agents store their ``result`` as a **native JSON
    object** in journal.jsonl (the manifest keeps a JSON-string `resultPreview`).
  * The approval gate is pre-authorizable via the global `skipWorkflowUsageWarning`
    setting (see RUNBOOK.md §Gate) — it is not a per-tool permission entry.

-----------------------------------------------------------------------------
SAFETY / ISOLATION
  * This probe is READ-ONLY. It never launches, edits, or deletes a workflow; it
    only reads files under the session store and writes its own findings +
    per-run logs into tests/log/ (gitignored).
  * It needs NO WSL/tmux and imports only the stdlib, so it collects cleanly in
    the hermetic run (where its integration+slow markers deselect it).
  * It is parallel-safe: it observes exactly the one run it is pointed at.
-----------------------------------------------------------------------------
"""

import datetime
import json
import logging
import os
import time
from pathlib import Path

import pytest

log = logging.getLogger("tests.workflow_probe")

pytestmark = [pytest.mark.integration, pytest.mark.slow]

LOG_DIR = Path(__file__).resolve().parent.parent / "log"

# --- knobs (env-overridable) -------------------------------------------------
WATCH_SECS = float(os.environ.get("AWLCC_WF_WATCH_SECS", "180"))
POLL_SECS = float(os.environ.get("AWLCC_WF_POLL_SECS", "0.5"))
STABLE_SECS = float(os.environ.get("AWLCC_WF_STABLE_SECS", "12"))
TERMINAL_STATES = {"completed", "done", "failed", "error", "cancelled"}

# --- manifest schema the dashboard depends on (validated below) --------------
MANIFEST_TOP_FIELDS = [
    "runId", "taskId", "script", "scriptPath", "result", "agentCount", "logs",
    "durationMs", "summary", "workflowName", "status", "startTime", "phases",
    "defaultModel", "workflowProgress", "totalTokens", "totalToolCalls",
]
AGENT_RECORD_FIELDS = [
    "type", "index", "label", "phaseIndex", "phaseTitle", "agentId", "model",
    "state", "startedAt", "queuedAt", "attempt", "promptPreview",
    "lastProgressAt", "tokens", "toolCalls", "durationMs", "resultPreview",
]
PHASE_RECORD_FIELDS = ["type", "index", "title"]


# --- small helpers -----------------------------------------------------------

def _norm(s):
    """Collapse whitespace so previews and full text compare cleanly."""
    return " ".join(str(s).split())


def _read_journal(path):
    """Parse journal.jsonl into a list of dicts (skips blank/partial lines)."""
    out = []
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # a torn final line mid-append — ignore this poll
    return out


def _read_manifest(path):
    """(exists, parsed_or_None). Unparseable-but-present ⇒ (True, None) — the
    engine may be mid-write; the caller treats that as 'exists, status unknown'."""
    if not path.exists():
        return False, None
    try:
        return True, json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True, None


def _first_user_prompt(agent_jsonl):
    """The prompt a workflow-subagent was given == the content of its first user
    message. Return it as a string (joining text blocks if content is a list)."""
    try:
        with agent_jsonl.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if obj.get("type") != "user":
                    continue
                content = (obj.get("message") or {}).get("content")
                if isinstance(content, str):
                    return content
                if isinstance(content, list):
                    parts = [b.get("text", "") for b in content
                             if isinstance(b, dict) and b.get("type") == "text"]
                    return "".join(parts)
                return ""
    except (OSError, json.JSONDecodeError):
        return None
    return None


def _discover_newest_run():
    """Fallback: newest workflow run dir under ~/.claude/projects, or None."""
    base = Path.home() / ".claude" / "projects"
    candidates = list(base.glob("*/*/subagents/workflows/wf_*"))
    best, best_mtime = None, -1.0
    for d in candidates:
        if not d.is_dir():
            continue
        jr = d / "journal.jsonl"
        mt = jr.stat().st_mtime if jr.exists() else d.stat().st_mtime
        if mt > best_mtime:
            best, best_mtime = d, mt
    return best


def _resolve_run():
    """Return (transcript_dir, manifest_path, run_id) or None. Env var wins;
    else auto-discover the newest run."""
    env = os.environ.get("AWLCC_WF_TRANSCRIPT_DIR", "").strip()
    if env:
        transcript_dir = Path(env)
    else:
        transcript_dir = _discover_newest_run()
        if transcript_dir is not None:
            log.warning("AWLCC_WF_TRANSCRIPT_DIR unset — auto-discovered newest run: %s",
                        transcript_dir)
    if transcript_dir is None or not transcript_dir.exists():
        return None
    run_id = transcript_dir.name  # "wf_...."
    # session dir = transcript_dir / .. (workflows) / .. (subagents) / ..
    session_dir = transcript_dir.parent.parent.parent
    manifest_path = session_dir / "workflows" / f"{run_id}.json"
    return transcript_dir, manifest_path, run_id


# --- the one live watch, shared across the assertions ------------------------

@pytest.fixture(scope="module")
def probe():
    """Resolve the run, watch it to completion (or timeout), load final state,
    and hand every assertion one evidence dict. Writes a durable findings record
    on teardown."""
    resolved = _resolve_run()
    if resolved is None:
        pytest.skip(
            "No workflow run to observe. THE DEAL (see tests/workflow_probe/RUNBOOK.md): "
            "1) launch the subject with Workflow({scriptPath: "
            "'<repo>/tests/workflow_probe/subject_workflow.js'}); "
            "2) set AWLCC_WF_TRANSCRIPT_DIR to the transcriptDir it returns; "
            "3) re-run: pytest tests/workflow_probe -m integration. "
            "(Or point AWLCC_WF_TRANSCRIPT_DIR at any completed run dir for post-hoc "
            "schema validation.)"
        )
    transcript_dir, manifest_path, run_id = resolved
    journal_path = transcript_dir / "journal.jsonl"
    log.info("observing run_id=%s transcript_dir=%s manifest=%s",
             run_id, transcript_dir, manifest_path)

    ev = {
        "run_id": run_id,
        "transcript_dir": str(transcript_dir),
        "manifest_path": str(manifest_path),
        "polls": [],
        "watch_reason_stopped": None,
    }

    t0 = time.monotonic()
    last_journal_lines = -1
    last_change_t = t0
    saw_manifest_before_complete = False
    manifest_mtimes_before_complete = []
    first_poll = None
    while True:
        now = time.monotonic()
        elapsed = round(now - t0, 2)
        journal = _read_journal(journal_path)
        started = sum(1 for e in journal if e.get("type") == "started")
        results = sum(1 for e in journal if e.get("type") == "result")
        m_exists, m_obj = _read_manifest(manifest_path)
        m_status = (m_obj or {}).get("status") if m_obj else None
        m_mtime = manifest_path.stat().st_mtime if m_exists else None
        agent_files = sorted(transcript_dir.glob("agent-*.jsonl"))
        snap = {
            "t": elapsed, "journal_lines": len(journal), "started": started,
            "results": results, "manifest_exists": m_exists,
            "manifest_status": m_status, "manifest_mtime": m_mtime,
            "agent_files": len(agent_files),
        }
        ev["polls"].append(snap)
        log.debug("poll %s", snap)
        if first_poll is None:
            first_poll = snap

        # Terminal detection is CORROBORATED, not just the status whitelist: a run
        # is done when its manifest parses AND (status is a known terminal word OR
        # journal results == manifest.agentCount). The second clause is status-
        # vocabulary-independent, so an unknown terminal string can't make a
        # finished run look live. Warn loudly if a parsed manifest carries a status
        # outside the whitelist so TERMINAL_STATES can't silently rot.
        m_count = (m_obj or {}).get("agentCount")
        status_terminal = bool(m_status and m_status in TERMINAL_STATES)
        count_terminal = bool(m_obj is not None and isinstance(m_count, int)
                              and m_count > 0 and results >= m_count)
        if m_obj is not None and m_status and m_status not in TERMINAL_STATES and count_terminal:
            log.warning("manifest carries UNRECOGNIZED terminal status %r "
                        "(results=%s == agentCount=%s) — add it to TERMINAL_STATES",
                        m_status, results, m_count)
        terminal = status_terminal or count_terminal

        # Count a PRE-completion manifest only if it PARSED and carries a real
        # non-terminal status. A torn/partial read (m_obj is None) at the instant
        # the completion-only manifest flushes must NOT be mis-booked as evidence
        # of a live/pre-completion write — that would flip the timing verdict to a
        # false LIVE (the single most load-bearing output of this probe).
        if not terminal and m_obj is not None and m_status and m_status not in TERMINAL_STATES:
            saw_manifest_before_complete = True
            if m_mtime is not None:
                manifest_mtimes_before_complete.append(m_mtime)

        if len(journal) != last_journal_lines:
            last_journal_lines = len(journal)
            last_change_t = now

        if terminal:
            ev["watch_reason_stopped"] = f"terminal (status={m_status!r}, results={results}/{m_count})"
            break
        if results > 0 and (now - last_change_t) >= STABLE_SECS and m_exists:
            ev["watch_reason_stopped"] = "journal stable + manifest present (no terminal status seen)"
            break
        if (now - t0) >= WATCH_SECS:
            ev["watch_reason_stopped"] = f"timeout after {WATCH_SECS}s"
            break
        time.sleep(POLL_SECS)

    # --- final state -----------------------------------------------------
    final_journal = _read_journal(journal_path)
    _, final_manifest = _read_manifest(manifest_path)
    agent_files = sorted(transcript_dir.glob("agent-*.jsonl"))

    lines_seq = [p["journal_lines"] for p in ev["polls"]]
    journal_streamed = any(b > a for a, b in zip(lines_seq, lines_seq[1:]))
    saw_inflight = any(p["started"] > p["results"] for p in ev["polls"])
    # "live observed" derives from POSITIVE signals, not from 'status not in a
    # hardcoded set': we began before the (completion-only) manifest existed, OR we
    # watched the journal grow, OR we caught an agent in flight. This way an unknown
    # terminal status string can't make a finished post-hoc run masquerade as live.
    first_manifest_present = bool(first_poll and first_poll["manifest_exists"])
    live_observed = (not first_manifest_present) or journal_streamed or saw_inflight
    mtime_changed_before_complete = len(set(manifest_mtimes_before_complete)) > 1

    ev.update({
        "final_journal": final_journal,
        "final_manifest": final_manifest,
        "agent_files": [f.name for f in agent_files],
        "n_polls": len(ev["polls"]),
        "journal_streamed": journal_streamed,
        "saw_inflight": saw_inflight,
        "live_observed": live_observed,
        "manifest_seen_before_complete": saw_manifest_before_complete,
        "manifest_mtime_changed_before_complete": mtime_changed_before_complete,
    })
    # Echo the resolved run identity so a driver can confirm the probe observed the
    # run it just launched (the env var is what binds them; auto-discovery may not).
    log.info("RESOLVED run_id=%s workflowName=%r status=%s live_observed=%s",
             run_id, (final_manifest or {}).get("workflowName"),
             (final_manifest or {}).get("status"), live_observed)

    yield ev

    # --- durable findings record (teardown) ------------------------------
    try:
        _write_findings(ev)
    except Exception:  # findings are best-effort; never fail teardown
        log.exception("failed to write findings record")


def _manifest_timing_verdict(ev):
    """Answer the open question: is the manifest written live or at completion?"""
    if not ev.get("live_observed"):
        return ("INCONCLUSIVE",
                "run was already complete at first poll — relaunch and watch to observe timing")
    if ev.get("manifest_seen_before_complete") and ev.get("manifest_mtime_changed_before_complete"):
        return ("LIVE", "manifest present AND its mtime changed while the run was still in flight")
    if ev.get("manifest_seen_before_complete"):
        return ("LIVE (present, single write)",
                "manifest file present before completion but no mid-run mtime change captured")
    return ("COMPLETION-ONLY",
            "manifest file only appeared once the run reached a terminal status; "
            "journal.jsonl is the live signal to tail")


def _write_findings(ev):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    m = ev.get("final_manifest") or {}
    timing_verdict, timing_why = _manifest_timing_verdict(ev)
    results = [e for e in ev.get("final_journal", []) if e.get("type") == "result"]
    structured = [r for r in results if isinstance(r.get("result"), (dict, list))]
    lines = [
        f"awl workflow-engine probe — findings — {stamp}",
        "=" * 68,
        f"run_id:            {ev['run_id']}",
        f"transcript_dir:    {ev['transcript_dir']}",
        f"manifest:          {ev['manifest_path']}",
        f"workflowName:      {m.get('workflowName')}",
        f"status:            {m.get('status')}   (watch stopped: {ev.get('watch_reason_stopped')})",
        f"agentCount:        {m.get('agentCount')}   (journal results={len(results)}, agent files={len(ev.get('agent_files', []))})",
        f"phases:            {[p.get('title') for p in (m.get('phases') or [])]}",
        f"durationMs:        {m.get('durationMs')}    totalTokens: {m.get('totalTokens')}",
        f"defaultModel:      {m.get('defaultModel')}",
        "",
        "OPEN-QUESTION ANSWERS (for the research report):",
        f"  • journal.jsonl streams incrementally (live signal): {ev.get('journal_streamed')}"
        f"   [saw in-flight started>results: {ev.get('saw_inflight')}]",
        f"  • manifest write timing:  {timing_verdict}",
        f"        → {timing_why}",
        f"  • live watch actually observed the run mid-flight: {ev.get('live_observed')}"
        f"   (polls={ev.get('n_polls')})",
        f"  • structured-output (schema) agents store result as a NATIVE JSON object "
        f"in journal.jsonl (not a string): {bool(structured)}  (count={len(structured)})",
        "",
        "NOTE: the approval-gate experiment is agent-driven — see RUNBOOK.md §Gate;",
        "record its outcome here by hand after running it.",
    ]
    text = "\n".join(lines) + "\n"
    (LOG_DIR / f"workflow_probe_findings_{stamp}.txt").write_text(text, encoding="utf-8")
    (LOG_DIR / "workflow_probe_findings_latest.txt").write_text(text, encoding="utf-8")
    log.info("wrote findings -> %s", LOG_DIR / "workflow_probe_findings_latest.txt")


# --- assertions --------------------------------------------------------------

def test_run_resolved_and_manifest_present(probe):
    """The run resolved and its manifest parses — the artifact exists at all."""
    m = probe["final_manifest"]
    assert m is not None, f"manifest missing/unparseable at {probe['manifest_path']}"
    assert m.get("runId") == probe["run_id"], (
        f"manifest runId {m.get('runId')!r} != dir {probe['run_id']!r}")
    assert m.get("workflowName"), "manifest has no workflowName"
    log.info("run %s status=%s agentCount=%s", probe["run_id"], m.get("status"), m.get("agentCount"))


def test_journal_incremental_and_keyed(probe):
    """journal.jsonl is the live signal: it streams, its keys are content-hashed,
    and every result reconciles to a started."""
    journal = probe["final_journal"]
    assert journal, "journal.jsonl is empty — no engine telemetry at all"
    started = [e for e in journal if e.get("type") == "started"]
    results = [e for e in journal if e.get("type") == "result"]
    assert started and results, f"journal has starts={len(started)} results={len(results)}"

    # Every AGENT event (started/result) carries a v2: content-hash key (the
    # resume/cache key) + an agentId. Scoped to agent events only — the engine may
    # legitimately write other line types (log/phase/heartbeat) that carry neither.
    for e in started + results:
        assert str(e.get("key", "")).startswith("v2:"), f"agent event missing v2: key: {e}"
        assert e.get("agentId"), f"agent event missing agentId: {e}"

    # every result's agent was announced by a started
    started_ids = {e["agentId"] for e in started}
    for r in results:
        assert r["agentId"] in started_ids, f"result for unannounced agent {r['agentId']}"

    # The LIVE signal is only meaningful if we actually caught the journal being
    # written. Because the manifest is completion-only, there is a real window where
    # the journal is already fully flushed but the manifest not yet present; if the
    # first poll lands there we're "live_observed" yet captured no growth — that is
    # INCONCLUSIVE (skip), not a failure.
    if not probe["live_observed"]:
        pytest.skip("run already complete at first poll — journal live-streaming "
                    "INCONCLUSIVE (post-hoc mode); relaunch to assert it")
    if not (probe["journal_streamed"] or probe["saw_inflight"]):
        pytest.skip("live-observed but the journal was already fully written before the "
                    "first poll captured any change — INCONCLUSIVE; relaunch to catch it "
                    f"streaming. polls={[(p['t'], p['journal_lines']) for p in probe['polls']]}")
    assert probe["journal_streamed"] or probe["saw_inflight"], (
        "no incremental journal signal captured on a live run — it may be buffered "
        f"to completion. polls={[(p['t'], p['journal_lines']) for p in probe['polls']]}")


def test_manifest_schema_matches_dashboard_contract(probe):
    """The manifest carries every field the dashboard would render — top level,
    each phase record, and each agent record."""
    m = probe["final_manifest"]
    missing_top = [f for f in MANIFEST_TOP_FIELDS if f not in m]
    assert not missing_top, f"manifest missing top-level fields: {missing_top}"
    # Key-presence isn't enough for the fields the dashboard must render — a key
    # regressed to null/'' is "present" but unrenderable. Assert truthiness for the
    # non-empty subset (the rest stay presence-only, which is correct for optionals).
    for f in ("runId", "workflowName", "status", "defaultModel"):
        assert m.get(f), f"manifest field {f!r} present but empty/null (dashboard needs it)"

    prog = m.get("workflowProgress") or []
    phases = [p for p in prog if p.get("type") == "workflow_phase"]
    agents = [p for p in prog if p.get("type") == "workflow_agent"]
    assert phases, "no workflow_phase records in workflowProgress"
    assert agents, "no workflow_agent records in workflowProgress"

    for p in phases:
        miss = [f for f in PHASE_RECORD_FIELDS if f not in p]
        assert not miss, f"phase record missing {miss}: {p}"
        assert p.get("title"), f"phase record {p.get('index')} has empty title"
    for a in agents:
        miss = [f for f in AGENT_RECORD_FIELDS if f not in a]
        assert not miss, f"agent record {a.get('label')} missing {miss}"
        assert a.get("state"), f"agent record {a.get('label')} has empty state"
        assert a.get("model"), f"agent record {a.get('label')} has empty model"
        assert isinstance(a.get("tokens"), int), f"agent {a.get('label')} tokens not an int"
        assert isinstance(a.get("durationMs"), int), f"agent {a.get('label')} durationMs not an int"
    log.info("schema OK: %d phase records, %d agent records", len(phases), len(agents))


def test_manifest_reconciles_with_journal_and_files(probe):
    """The three telemetry sources agree: manifest agent records == journal
    results == per-agent transcript files, and result text matches the preview."""
    m = probe["final_manifest"]
    agents = [p for p in (m.get("workflowProgress") or []) if p.get("type") == "workflow_agent"]
    assert agents, "no workflow_agent records to reconcile"
    results = {e["agentId"]: e for e in probe["final_journal"] if e.get("type") == "result"}
    file_ids = {name[len("agent-"):-len(".jsonl")] for name in probe["agent_files"]}

    assert m.get("agentCount") == len(agents), (
        f"agentCount {m.get('agentCount')} != {len(agents)} agent records")
    assert len(agents) == len(results), (
        f"{len(agents)} agent records != {len(results)} journal results")

    previews_compared = 0
    for a in agents:
        aid = a["agentId"]
        assert aid in results, f"agent {a.get('label')} has no journal result"
        assert aid in file_ids, f"agent {a.get('label')} has no agent-{aid}.jsonl transcript"
        jr = results[aid].get("result")
        rp = a.get("resultPreview", "")
        # An agent that produced a non-empty result MUST carry a non-empty preview —
        # else the content cross-check below would no-op silently.
        if jr not in (None, "", {}, []):
            assert rp, f"agent {a.get('label')} produced a result but resultPreview is empty"
        if isinstance(jr, (dict, list)):
            # Structured-output agent: journal.jsonl stores a NATIVE JSON object, the
            # manifest a JSON-string preview (possibly truncated). Compare on the
            # de-quoted head so truncation can't turn the check into a no-op.
            jr_str = _norm(json.dumps(jr, ensure_ascii=False, separators=(",", ":")))
            head = _norm(rp).split("…")[0][:30]
            if head:
                assert head in jr_str, (
                    f"structured resultPreview head {head!r} not found in the journal "
                    f"object for {a.get('label')}")
                previews_compared += 1
        else:
            # Plain-text agent: lenient whitespace-normalized prefix match.
            rpn = _norm(rp).split("…")[0][:40]
            rjn = _norm(jr)
            if rpn:
                assert rjn.startswith(rpn) or _norm(rp).startswith(rjn[:40]), (
                    f"resultPreview and journal result diverge for {a.get('label')}")
                previews_compared += 1
    assert previews_compared > 0, (
        "no agent's resultPreview was actually content-compared — the manifest↔journal "
        "content cross-check ran vacuously (all previews empty/untruncatable)")


def test_per_agent_transcripts_are_workflow_subagents(probe):
    """Each subagent has a full transcript + meta tagging it a workflow-subagent,
    and its first user message is the prompt the script gave it."""
    m = probe["final_manifest"]
    agents = [p for p in (m.get("workflowProgress") or []) if p.get("type") == "workflow_agent"]
    assert agents, "no workflow_agent records — nothing to check (would pass vacuously)"
    tdir = Path(probe["transcript_dir"])
    for a in agents:
        aid = a["agentId"]
        jsonl = tdir / f"agent-{aid}.jsonl"
        meta = tdir / f"agent-{aid}.meta.json"
        assert jsonl.exists(), f"missing transcript {jsonl.name}"
        assert meta.exists(), f"missing meta {meta.name}"
        meta_obj = json.loads(meta.read_text(encoding="utf-8"))
        assert meta_obj.get("agentType") == "workflow-subagent", (
            f"{meta.name} agentType={meta_obj.get('agentType')!r}")
        assert meta_obj.get("spawnDepth") == 1, f"{meta.name} spawnDepth={meta_obj.get('spawnDepth')}"
        prompt = _first_user_prompt(jsonl)
        assert prompt, f"{jsonl.name} had no first user prompt"
        pv = _norm(a.get("promptPreview", ""))[:40]
        if pv:
            assert _norm(prompt).startswith(pv), (
                f"transcript prompt for {a.get('label')} does not match promptPreview")


def test_structured_output_agent_returned_object(probe):
    """If the subject had a schema agent, its journal result is a JSON object with
    the schema's required keys — proving the structured-output path works."""
    agents = [p for p in (probe["final_manifest"].get("workflowProgress") or [])
              if p.get("type") == "workflow_agent"]
    # Match only our subject's schema agent (label starts "typed"). Post-hoc runs
    # against arbitrary workflows won't have one — skip rather than false-fail.
    typed = [a for a in agents if (a.get("label") or "").lower().startswith("typed")]
    if not typed:
        pytest.skip("no schema agent (label 'typed…') in this run — structured-output "
                    "check applies to subject_workflow.js runs only")
    results = {e["agentId"]: e for e in probe["final_journal"] if e.get("type") == "result"}
    a = typed[0]
    raw = results.get(a["agentId"], {}).get("result")
    # The engine stores a schema agent's result as a NATIVE object in the journal
    # (not a stringified one) — accept either an object or a JSON string.
    if isinstance(raw, dict):
        obj = raw
    else:
        try:
            obj = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            pytest.fail(f"schema agent {a.get('label')} result is neither an object "
                        f"nor JSON text: {str(raw)[:120]!r}")
    assert isinstance(obj, dict), f"schema agent returned {type(obj).__name__}, not an object"
    for key in ("headline", "sceneCount", "mood"):
        assert key in obj, f"structured result missing required key {key!r}: {obj}"
    log.info("structured output OK: %s", obj)


def test_subject_pipeline_stage_signature(probe):
    """Pin the `pipeline()` stage-callback signature `(prevResult, originalItem,
    index)` for the subject run — the one place the script API's arity is verified.
    Evidence: stage labels `draft#0..2` / `tighten#0..2` prove the `index` arg
    reached BOTH stages (drift would yield `tighten#undefined`), and each draft
    prompt carrying its topic proves `originalItem` reached stage 1. Subject-only;
    post-hoc runs of other workflows skip."""
    m = probe["final_manifest"]
    if m.get("workflowName") != "wf-probe-subject":
        pytest.skip("not the wf-probe-subject run — pipeline-signature check is subject-specific")
    agents = [p for p in (m.get("workflowProgress") or []) if p.get("type") == "workflow_agent"]
    chain_labels = {a.get("label") for a in agents if a.get("phaseTitle") == "chain"}
    expected = {f"draft#{i}" for i in range(3)} | {f"tighten#{i}" for i in range(3)}
    assert chain_labels == expected, (
        f"pipeline stage labels {sorted(chain_labels)} != expected {sorted(expected)} — "
        "the pipeline stage-callback signature (prevResult, originalItem, index) may have "
        "drifted (e.g. index arg missing → 'tighten#undefined')")
    # originalItem reached stage 1: each draft prompt carries its topic verbatim.
    topics = ["a quiet harbor at dawn", "a crowded night market", "a snowfield under stars"]
    draft_prompts = " ".join(a.get("promptPreview", "") for a in agents
                             if (a.get("label") or "").startswith("draft#"))
    for t in topics:
        assert t in draft_prompts, (
            f"draft prompts missing topic {t!r} — originalItem not threaded to pipeline stage 1")


def test_manifest_write_timing_finding(probe):
    """Assert the established ground truth: on a live-observed run the manifest is
    written COMPLETION-ONLY (journal.jsonl is the live signal). This is a real,
    falsifiable check — a failure means either (a) the engine genuinely started
    writing the manifest live [a FINDING: update the research report §11 #2 and
    this assertion], or (b) a torn-read false LIVE slipped past the watch-loop
    guard [a probe bug]. It is NOT a tautology: verdict can be LIVE here."""
    verdict, why = _manifest_timing_verdict(probe)
    log.info("MANIFEST WRITE TIMING: %s — %s", verdict, why)
    if not probe["live_observed"]:
        pytest.skip(f"manifest-timing INCONCLUSIVE ({why}); relaunch live to settle it")
    assert verdict.startswith("COMPLETION-ONLY"), (
        f"manifest-timing verdict is {verdict!r}, expected COMPLETION-ONLY — {why}. "
        "manifest_seen_before_complete="
        f"{probe.get('manifest_seen_before_complete')}, mtime_changed="
        f"{probe.get('manifest_mtime_changed_before_complete')}. If the engine now "
        "genuinely writes the manifest live, update research report §11 #2 + this test; "
        "otherwise investigate a torn-read false LIVE in the watch loop.")
