r"""Live spike — WORKFLOW-APPROVAL-GATE interception (the review-before-approve question).

THE ONE QUESTION
    Can the dashboard INTERCEPT a Claude Code workflow at its approval moment —
    read the full preview (name / description / phases / full script) — and
    round-trip an Approve/Reject decision back to the agent so the workflow
    launches or aborts accordingly? (Teed up at the end of the 2026-07-04
    workflow-orchestration session; the open piece is the *plumbing*, not the
    content — the content was already known to be in the tool call.)

TWO CANDIDATE CHANNELS (mirroring what the dashboard already does elsewhere)
  * CHANNEL 1 — HOOK. A PreToolUse hook on the ``Workflow`` tool fires before the
    tool runs, carries the whole script in ``tool_input.script``, and can APPROVE
    (permissionDecision "allow") or REJECT (permissionDecision "deny") via its
    JSON response. This is the same interception the dashboard already uses for
    ``ExitPlanMode`` / ``AskUserQuestion`` (see BridgeDriver._build_hook_settings,
    sidecar/drivers/bridge.py) — except those hooks only *detect* (return {}),
    and hook-driven DENY has never been proven in this repo. That, plus the fact
    that the hooks reference (v2.1.90) does NOT list "Workflow" among the hookable
    tools, makes "does the hook even fire for Workflow, and can it deny?" the
    single load-bearing unknown. This spike answers it empirically.
  * CHANNEL 2 — SCREEN. With the built-in "Run a dynamic workflow?" dialog left
    on, scrape it off the tmux pane and answer with keystrokes (Escape / '3' =
    reject), the same primitive the dashboard uses for permission menus.

WHAT THIS PROVES / DISPROVES (records either way — a disproof is a real finding)
    Detection      — a Workflow tool call fires a PreToolUse HTTP hook we receive.
    Full preview   — the hook payload's tool_input.script carries the whole meta.
    Reject (hook)  — a "deny" verdict aborts the workflow (no run dir appears).
    Approve (hook) — an "allow" verdict lets it launch (a wf_ run dir appears).
    Screen channel — the dialog renders in a bridged pane and answers via keys().
    Gate config    — whether skipWorkflowUsageWarning is honored PER-SESSION (in
                     the agent's --settings), which decides whether the dashboard
                     ever needs to touch global config.

DESIGN — self-contained, no sidecar, no product changes
    The dashboard is stood in for by an in-test ThreadingHTTPServer (the
    "capture/verdict server") on an ephemeral port, reachable from WSL via the
    host gateway (bridge.wsl_host_ip()). The pytest process drives a REAL, tab-less
    WSL bridge Claude session to issue a Workflow tool call; the injected
    PreToolUse hook POSTs the tool_input to our server, which records it and
    replies with the verdict under test. "Did it launch?" is read from the WSL
    filesystem (a new ~/.claude/projects/*/<sid>/subagents/workflows/wf_* dir) and
    the agent's own transcript/screen. Because the bridge Claude runs INSIDE WSL2
    against its OWN ~/.claude, the popup switch is controlled per-session in the
    agent's --settings — this spike does NOT mutate your Windows global config.

SAFETY / ISOLATION (hard rules)
  * Uses its OWN TmuxBridge() with a NON-destructive teardown — NEVER the shared
    conftest ``bridge``/``live_session`` fixtures (they call ``tmux kill-server``
    and would kill sibling agents). Sessions are uniquely named ``wfgate-<uuid8>``
    and only THIS session is closed on teardown; never kill-server / shutdown().
  * Tab-less only (``show=False``) per the repo rule — no Windows Terminal tab.
  * Cost-guarded: the subject workflow is ONE trivial agent, so the worst case is a
    handful of single-agent launches (~40-80k tokens each). The Reject (deny) run
    launches nothing when deny is honored; the Approve and isolation runs each launch
    one cheap agent; the Screen run launches nothing UNLESS the built-in dialog fails
    to gate (then it may launch the one cheap agent). No fan-out is ever triggered.

HOW TO RUN (live tier)::

    tests\run.ps1 -m integration tests/workflow_approval_probe
    # or:  .\.venv\Scripts\python.exe -m pytest tests/workflow_approval_probe -m integration -v

    Requires WSL2 + the Ubuntu bridge + the Claude CLI installed in WSL. Skips
    (never fabricates green) when WSL / the host gateway / a Workflow tool call is
    unavailable. Plain-language findings are written to
    tests/log/workflow_approval_findings_latest.txt.

FINDINGS (live, Claude Code 2.1.x — 8/8 green; latest in
tests/log/workflow_approval_findings_latest.txt):
  * CHANNEL 1 WORKS. A PreToolUse HTTP hook FIRES for the ``Workflow`` tool
    (tool_name == 'Workflow') even though the hooks reference does not list it, and
    its ``tool_input.script`` carries the WHOLE preview — name / description / phases
    all recovered from the intercepted payload.
  * ROUND-TRIP WORKS BOTH WAYS. A hook 'deny' verdict ABORTS the workflow (no run
    dir; the permissionDecisionReason surfaces to the agent), a hook 'allow' LAUNCHES
    it — and the A/B contrast (same setup, opposite verdict) proves the verdict ALONE
    controls launch.
  * THE HOOK IS THE SOLE GATE. With the hook present AND the popup switch left ON
    (skipWorkflowUsageWarning:false), no built-in dialog renders and the verdict still
    controls launch — the hook PREEMPTS the 'Run a dynamic workflow?' dialog.
  * CHANNEL 2 ALSO WORKS. With no hook + skipWorkflowUsageWarning:false per-session,
    the dialog renders in the bridged pane, is readable, and Escape rejects it —
    confirming the popup switch is controllable PER-SESSION (no global config needed).
"""

import json
import logging
import re
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

# `from bridge import TmuxBridge` — the bridge package lives at the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from bridge import TmuxBridge  # noqa: E402

log = logging.getLogger(__name__)

pytestmark = [pytest.mark.integration, pytest.mark.slow]

# -----------------------------------------------------------------------------
# Constants + the deliverable (findings) accumulator
# -----------------------------------------------------------------------------
SLUG = "wfgate"
LOG_DIR = _REPO_ROOT / "tests" / "log"
SUBJECT_JS = Path(__file__).with_name("subject_workflow.js")

# The distinctive strings the subject's meta carries (single source of truth is
# subject_workflow.js; these are what a correct preview-read must recover).
SUBJECT_NAME = "wf-approval-subject"
SUBJECT_DESC_MARK = "approval-interception spike"
SUBJECT_PHASE_TITLES = ["Solo"]

# Time budgets (seconds).
CREATE_TIMEOUT = 90      # create() clears startup gates; can be slow
DRIVE_TIMEOUT = 150      # poll after send() for hook / launch / dialog
LAUNCH_SETTLE = 40       # after a decision, how long to watch for a wf_ run dir
                         # (generous so a slow allow-launch isn't misread as abort)
POLL = 3.0

# Populated by the run fixtures; written to tests/log/ at module teardown.
FINDINGS: dict = {"runs": {}, "verdicts": {}}


# -----------------------------------------------------------------------------
# The capture / verdict server — stands in for the dashboard's approval surface.
# -----------------------------------------------------------------------------
class _CaptureServer:
    """In-test HTTP receiver for PreToolUse hook POSTs. Records every hook body
    and answers with the verdict under test. The ``verdict`` gates only the
    WORKFLOW TOOL (identified by its script-bearing payload, on any matcher path);
    every ordinary tool (the ``.*`` catch-all's Read/Bash/etc.) is always allowed
    so the driven agent isn't blocked."""

    def __init__(self):
        self.posts: list[dict] = []
        self._lock = threading.Lock()
        self.verdict = "allow"          # "allow" | "deny"
        srv = self

        class _H(BaseHTTPRequestHandler):
            def log_message(self, *a):  # silence stderr access log
                pass

            def do_POST(self):
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                try:
                    body = json.loads(raw.decode("utf-8")) if raw else {}
                except Exception:
                    body = {"_unparsed": raw[:2000].decode("utf-8", "replace")}
                is_workflow_path = "/hook/workflow/" in self.path
                ti = body.get("tool_input")
                # Identify the WORKFLOW TOOL by its payload, not the matcher path:
                # a Workflow call carries a script/scriptPath (and tool_name
                # 'Workflow'). This makes the deny verdict deliverable on WHICHEVER
                # matcher fired — so if the named 'Workflow' matcher doesn't route
                # but the '.*' catch-all does, a 'deny' still aborts (no false
                # "deny is infeasible"). Ordinary tools (Read/Bash) carry no script,
                # so the catch-all keeps allowing them.
                is_wf_tool = (
                    is_workflow_path
                    or body.get("tool_name") == "Workflow"
                    or (isinstance(ti, dict) and (ti.get("script") or ti.get("scriptPath"))))
                with srv._lock:
                    srv.posts.append({
                        "path": self.path,
                        "is_workflow_path": is_workflow_path,
                        "tool_name": body.get("tool_name"),
                        "tool_input": ti,
                        "hook_event_name": body.get("hook_event_name"),
                        "permission_mode": body.get("permission_mode"),
                        "keys": sorted(body.keys()),
                        "at": time.time(),
                    })
                # Deny the workflow tool (on any matcher) only when the verdict says
                # so; never block the catch-all's ordinary tools.
                if is_wf_tool and srv.verdict == "deny":
                    payload = {"hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason":
                            "awl-cc-dash workflow-approval-interception spike: "
                            "REJECT verdict for test",
                    }}
                else:
                    payload = {"hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "allow",
                    }}
                data = json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self._httpd = ThreadingHTTPServer(("0.0.0.0", 0), _H)
        self.port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        try:
            self._httpd.shutdown()
            self._httpd.server_close()
        except Exception:
            pass

    def workflow_posts(self, agent_name):
        """Recorded POSTs that are the WORKFLOW gate for THIS agent."""
        with self._lock:
            return [p for p in self.posts
                    if p["is_workflow_path"] and agent_name in p["path"]
                    and (p.get("tool_name") in (None, "Workflow")
                         or "Workflow" in str(p.get("tool_name")))]

    def any_posts(self, agent_name):
        with self._lock:
            return [p for p in self.posts if agent_name in p["path"]]

    def script_posts(self, agent_name):
        """Posts whose tool_input looks like a workflow launch (has a ``script`` or
        ``scriptPath`` key) regardless of the matcher path or tool_name — the robust
        discovery signal that survives an unexpected tool name."""
        out = []
        for p in self.any_posts(agent_name):
            ti = p.get("tool_input")
            if isinstance(ti, dict) and (ti.get("script") or ti.get("scriptPath")):
                out.append(p)
        return out

    def tool_names(self, agent_name):
        """Distinct tool_names the catch-all saw for this agent (discovery aid)."""
        seen = []
        for p in self.any_posts(agent_name):
            tn = p.get("tool_name")
            if tn and tn not in seen:
                seen.append(tn)
        return seen


# -----------------------------------------------------------------------------
# Small pure helpers
# -----------------------------------------------------------------------------
def _parse_meta(script: str) -> dict:
    """Recover name / description / phase-titles from a workflow script string —
    the fields a review card must display. Tolerant of ' or " quoting."""
    if not script:
        return {"has_meta": False}

    def _one(field):
        m = re.search(rf"{field}\s*:\s*(['\"])(.*?)\1", script, re.S)
        return m.group(2) if m else None

    titles = re.findall(r"title\s*:\s*(['\"])(.*?)\1", script, re.S)
    return {
        "has_meta": "export const meta" in script,
        "name": _one("name"),
        "description": _one("description"),
        "phase_titles": [t[1] for t in titles],
    }


def _compact_script(path: Path) -> str:
    """Collapse the subject script to a SINGLE LINE for reliable tmux delivery:
    drop ``//`` comment lines and blanks, join the rest with spaces. The subject is
    authored with explicit semicolons so this stays valid JS, and single-line means
    no embedded newline reaches send-keys (a newline would submit the prompt early)."""
    keep = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        s = ln.strip()
        if not s or s.startswith("//"):
            continue
        keep.append(s)
    one = " ".join(keep)
    # Guard the single-line collapse: a surviving '//' (a trailing inline comment,
    # or '//' inside a string like a URL) would comment out the rest of the joined
    # line and silently corrupt the script the agent is told to run verbatim. Fail
    # loudly instead — subject_workflow.js must stay inline-comment-free.
    if "//" in one:
        raise ValueError(
            "subject_workflow.js collapsed to a line containing '//' — an inline "
            "comment or a '//' inside a string would corrupt the compacted script. "
            "Keep the subject free of inline '//' (see its header rules).")
    return one


def _wf_run_dirs(br: TmuxBridge, sid: str) -> set:
    """The set of workflow RUN dirs (…/subagents/workflows/wf_*) that exist for
    this session id on the WSL filesystem. Empty set when none."""
    try:
        out = br._run(
            f"ls -d ~/.claude/projects/*/{sid}/subagents/workflows/wf_* "
            f"2>/dev/null || true", timeout=15)
    except Exception as e:  # noqa: BLE001
        log.debug("wf_run_dirs probe error: %s", e)
        return set()
    return {ln.strip() for ln in out.splitlines() if ln.strip()}


# Match ONLY strings unique to the actual "Run a dynamic workflow?" dialog — the
# title (with its '?') and the two distinctive option labels. Deliberately NOT the
# bare phrase "dynamic workflow", which appears in the driving prompt's echo and
# caused a false-positive "dialog on screen" in the first live run. Case-sensitive
# so a lowercase prompt echo can't match the capitalised dialog chrome.
_DIALOG_MARKERS = re.compile(r"(Run a dynamic workflow\?|Yes, run it|View raw script)")


def _screen_has_dialog(text: str) -> bool:
    return bool(text and _DIALOG_MARKERS.search(text))


def _transcript_workflow_call(br: TmuxBridge, name: str):
    """(attempted, tool_input|None) from the agent's OWN transcript — an
    independent witness that a Workflow tool_use happened even if the hook never
    fired. Best-effort (transcript can lag / not exist yet)."""
    try:
        entries = br.read_log(name, types=["assistant"])
    except Exception as e:  # noqa: BLE001
        log.debug("read_log unavailable: %s", e)
        return (False, None)
    for e in entries or []:
        for block in (e.get("message", {}) or {}).get("content", []) or []:
            if isinstance(block, dict) and block.get("type") == "tool_use" \
                    and block.get("name") == "Workflow":
                return (True, block.get("input"))
    return (False, None)


# -----------------------------------------------------------------------------
# The one driver: create a tab-less WSL session, induce a Workflow call, observe.
# -----------------------------------------------------------------------------
def _drive(br: TmuxBridge, cap: _CaptureServer, *, tag: str, verdict: str,
           skip_warning, matchers=("workflow", "any"), screen_answer=None) -> dict:
    """Run ONE interception scenario end-to-end and return an observations dict.
    Never raises for an expected negative — records it instead.

    ``screen_answer='reject'`` exercises CHANNEL 2: when the on-pane dialog is
    detected it is scraped and answered with a keystroke (Escape) to prove the
    screen path can read AND answer the gate."""
    gw = br.wsl_host_ip()
    if not gw:
        pytest.skip("WSL host gateway unresolved — cannot reach the capture server "
                    "from WSL; is WSL2 up? (bridge.wsl_host_ip() returned None)")

    cap.verdict = verdict
    name = f"{SLUG}-{uuid.uuid4().hex[:8]}"
    sid = str(uuid.uuid4())
    cwd_wsl = f"/home/lester/awl-{name}"
    base = f"http://{gw}:{cap.port}"

    obs = {
        "tag": tag, "verdict": verdict, "skip_warning": skip_warning,
        "session": name, "sid": sid, "base": base,
        "attempted": False, "workflow_hook": None, "preview": None,
        "launched": None, "new_run_dirs": [], "dialog_on_screen": False,
        "transcript_toolcall": False, "screen_tail": "", "error": None,
        "hook_payload_keys": None, "catch_all_tools": [],
        "dialog_scrape": None, "dialog_answered": False,
        "dialog_rejected": None, "after_reject_tail": "", "deny_reason_seen": None,
    }
    FINDINGS["runs"][tag] = obs

    pre = []
    if "workflow" in matchers:
        pre.append({"matcher": "Workflow", "hooks": [
            {"type": "http", "url": f"{base}/hook/workflow/{name}", "timeout": 30}]})
    if "any" in matchers:
        pre.append({"matcher": ".*", "hooks": [
            {"type": "http", "url": f"{base}/hook/any/{name}", "timeout": 30}]})
    settings = {"hooks": {"PreToolUse": pre}} if pre else {}
    if skip_warning is not None:
        settings["skipWorkflowUsageWarning"] = skip_warning

    # The permissionDecisionReason the capture server returns on a deny — the engine
    # surfaces it to the agent, giving POSITIVE evidence the deny was delivered.
    deny_marker = "REJECT verdict for test"

    # ONE unified try/finally so a failure ANYWHERE (mkdir, preflight, create, or the
    # drive) still tears down THIS session + its scratch dirs. `created` gates the
    # session close so we never close a session that wasn't made.
    created = False
    try:
        br._run(f"mkdir -p {cwd_wsl}")
        # Preflight: confirm WSL can actually reach our receiver, else skip clean.
        ping = br._run(
            f"curl -s -o /dev/null -w '%{{http_code}}' -m 4 -X POST "
            f"{base}/hook/preflight/{name} -d '{{}}' || echo 000", timeout=12)
        if "200" not in ping:
            pytest.skip(f"WSL could not reach the capture server at {base} "
                        f"(preflight http_code={ping!r}) — firewall/gateway issue")

        br.create(name, cwd=cwd_wsl, show=False, permission_mode="default",
                  settings=(settings or None), session_id=sid)
        created = True

        before = _wf_run_dirs(br, sid)
        # ONE line, no embedded newlines (a newline would submit early), script
        # inlined compact so the whole send is small and fast (send-keys 10s budget).
        subject = _compact_script(SUBJECT_JS)
        prompt = (
            "Use the Workflow tool now. Call it exactly once, passing this exact "
            "script as the script argument verbatim, and do nothing else (no files, "
            "no explanation): " + subject)

        # Let the freshly-created TUI settle at its idle prompt before typing.
        try:
            br.wait_idle(name, timeout=20)
        except Exception:  # noqa: BLE001
            time.sleep(3)
        br.send(name, prompt)
        deadline = time.time() + DRIVE_TIMEOUT
        launch_deadline = None
        while time.time() < deadline:
            # Prefer the Workflow-matcher post; fall back to ANY script-bearing post
            # (survives an unexpected tool_name so a real hook is never mis-read as
            # "did not fire"). Record what the catch-all saw for discovery.
            obs["catch_all_tools"] = cap.tool_names(name)
            wposts = cap.workflow_posts(name) or cap.script_posts(name)
            if wposts and obs["workflow_hook"] is None:
                obs["workflow_hook"] = wposts[0]
                obs["attempted"] = True
                obs["hook_payload_keys"] = wposts[0].get("keys")
                ti = wposts[0].get("tool_input") or {}
                script = ti.get("script") if isinstance(ti, dict) else None
                obs["preview"] = _parse_meta(script or "")
                # once we have the gate hook, give the engine a beat to (not) launch
                launch_deadline = time.time() + LAUNCH_SETTLE

            try:
                screen = br.read(name, lines=80)["content"]
            except Exception:  # noqa: BLE001
                screen = ""
            if screen:
                obs["screen_tail"] = screen[-1200:]
                # Positive deny evidence: on a deny the engine echoes our
                # permissionDecisionReason back to the agent's pane.
                if verdict == "deny" and deny_marker in screen:
                    obs["deny_reason_seen"] = True
                if _screen_has_dialog(screen):
                    obs["dialog_on_screen"] = True
                    obs["attempted"] = True
                    # CHANNEL 2: read the preview off the pane, then reject via a
                    # keystroke and confirm the dialog closed.
                    if screen_answer == "reject" and not obs["dialog_answered"]:
                        obs["dialog_scrape"] = screen[-1500:]
                        try:
                            br.keys(name, "Escape")
                            time.sleep(3)
                            after = br.read(name, lines=80)["content"]
                            obs["after_reject_tail"] = after[-800:]
                            obs["dialog_rejected"] = not _screen_has_dialog(after)
                        except Exception as e:  # noqa: BLE001
                            log.debug("screen reject error: %s", e)
                        obs["dialog_answered"] = True
                        launch_deadline = time.time() + LAUNCH_SETTLE

            new = _wf_run_dirs(br, sid) - before
            if new:
                obs["launched"] = True
                obs["attempted"] = True
                obs["new_run_dirs"] = sorted(new)
                break

            if not obs["attempted"]:
                tcall, tinput = _transcript_workflow_call(br, name)
                if tcall:
                    obs["attempted"] = True
                    obs["transcript_toolcall"] = True
                    if obs["preview"] is None and isinstance(tinput, dict):
                        obs["preview"] = _parse_meta(tinput.get("script") or "")

            # Settle-window break: once the gate hook fired (or we answered a screen
            # dialog), read the true launch state and stop — no need to burn the full
            # DRIVE_TIMEOUT. A dialog still stuck on screen (unanswered) is NOT a
            # settled state. GRACE RE-POLL before committing "not launched" so a
            # launch landing a few seconds past the window isn't misread as an abort.
            if launch_deadline and time.time() > launch_deadline \
                    and (obs["dialog_answered"] or not obs["dialog_on_screen"]):
                new = _wf_run_dirs(br, sid) - before
                if not new:
                    time.sleep(6)
                    new = _wf_run_dirs(br, sid) - before
                obs["launched"] = bool(new)
                obs["new_run_dirs"] = sorted(new)
                break
            time.sleep(POLL)

        if obs["launched"] is None:
            # Final check after the loop.
            new = _wf_run_dirs(br, sid) - before
            obs["launched"] = bool(new)
            obs["new_run_dirs"] = sorted(new)
            if not obs["attempted"]:
                tcall, tinput = _transcript_workflow_call(br, name)
                obs["attempted"] = obs["attempted"] or tcall
                obs["transcript_toolcall"] = obs["transcript_toolcall"] or tcall

        # Corroborate a deny: also scan the transcript (the permissionDecisionReason
        # may land in the agent's messages rather than the raw pane).
        if verdict == "deny" and obs["deny_reason_seen"] is not True:
            try:
                entries = br.read_log(name, types=["user", "assistant"])
                if deny_marker in json.dumps(entries):
                    obs["deny_reason_seen"] = True
            except Exception:  # noqa: BLE001
                pass
    except pytest.skip.Exception:
        raise
    except Exception as e:  # noqa: BLE001
        obs["error"] = f"drive failed: {e}"
    finally:
        if created:
            try:
                br.close(name)
            except Exception:  # noqa: BLE001
                pass
        try:
            br._run(f"rm -rf {cwd_wsl}")
        except Exception:  # noqa: BLE001
            pass

    log.info("RUN %s: attempted=%s hook=%s launched=%s dialog=%s deny_reason=%s err=%s",
             tag, obs["attempted"], obs["workflow_hook"] is not None, obs["launched"],
             obs["dialog_on_screen"], obs["deny_reason_seen"], obs["error"])
    return obs


# -----------------------------------------------------------------------------
# Fixtures — own bridge (non-destructive), capture server, and one run per scenario
# -----------------------------------------------------------------------------
@pytest.fixture(scope="module")
def br():
    """Our OWN TmuxBridge. Teardown does NOTHING destructive (no kill-server)."""
    if sys.platform != "win32":
        pytest.skip("workflow-approval spike drives a Windows->WSL2 bridge; not this OS")
    yield TmuxBridge()


@pytest.fixture(scope="module")
def cap():
    s = _CaptureServer()
    s.start()
    yield s
    s.stop()


@pytest.fixture(scope="module")
def deny_run(br, cap):
    """HOOK channel, REJECT verdict, dialog suppressed per-session. Launches
    NOTHING when deny is honored."""
    return _drive(br, cap, tag="hook_deny", verdict="deny", skip_warning=True)


@pytest.fixture(scope="module")
def allow_run(br, cap):
    """HOOK channel, APPROVE verdict, dialog suppressed per-session. Launches the
    single-agent subject when allow is honored."""
    return _drive(br, cap, tag="hook_allow", verdict="allow", skip_warning=True)


@pytest.fixture(scope="module")
def screen_run(br, cap):
    """SCREEN channel — NO hook gate (a hook verdict would preempt the dialog), so
    the built-in 'Run a dynamic workflow?' dialog is the only gate. Forces it on
    per-session and rejects it with a keystroke. Records whether it rendered."""
    return _drive(br, cap, tag="screen", verdict="allow",
                  skip_warning=False, matchers=(), screen_answer="reject")


@pytest.fixture(scope="module")
def preempt_run(br, cap):
    """ISOLATION run — hook present AND the popup switch left ON (skip_warning=False).
    This is the ONLY run that can tell "the hook preempted the dialog" apart from
    "skipWorkflowUsageWarning:true suppressed it" (a confound in deny_run/allow_run,
    which both suppress). Verdict=allow: if the hook preempts, no dialog renders and
    the workflow launches; if it does NOT, both gates fire and the agent parks at the
    unanswered dialog (no launch)."""
    return _drive(br, cap, tag="preempt", verdict="allow",
                  skip_warning=False, matchers=("workflow", "any"))


@pytest.fixture(scope="module", autouse=True)
def _write_findings():
    yield
    try:
        _emit_findings()
    except Exception as e:  # noqa: BLE001
        log.debug("findings write failed: %s", e)


# -----------------------------------------------------------------------------
# Tests — CHANNEL 1 (hook): detect, read preview, reject, approve
# -----------------------------------------------------------------------------
def test_agent_issued_a_workflow_call(deny_run):
    """Precondition: the driven WSL agent actually issued a Workflow tool call.
    If it never did (tool absent / agent refused / drive failed) we cannot answer
    the interception question — skip, don't fabricate a green."""
    if deny_run.get("error"):
        pytest.skip(f"deny run errored before an answer: {deny_run['error']}")
    if not deny_run["attempted"]:
        pytest.skip("could not induce a Workflow tool call in the bridged session "
                    "(no hook POST, no transcript tool_use, no dialog) — a drive/env "
                    "issue, not a channel finding. See the findings file + RUNBOOK.")
    FINDINGS["verdicts"]["workflow_call_issued"] = True


def test_hook_fires_for_workflow_gate(deny_run):
    """CHANNEL-1 crux: a PreToolUse HTTP hook fires for the Workflow tool. A green
    here confirms the dashboard can intercept the gate via a hook; a red IS the
    finding that channel 1 is infeasible and only the screen channel can work."""
    if deny_run.get("error"):
        pytest.skip(f"deny run errored: {deny_run['error']}")
    if not deny_run["attempted"]:
        pytest.skip("no Workflow tool call issued — see test_agent_issued_a_workflow_call")
    hook = deny_run["workflow_hook"]
    FINDINGS["verdicts"]["hook_fires_for_workflow"] = hook is not None
    assert hook is not None, (
        "the agent issued a Workflow tool call but NO PreToolUse hook POST arrived "
        "for it — CHANNEL 1 (hook interception) is INFEASIBLE on this build; the "
        "workflow gate is not routed to PreToolUse. Fall back to the SCREEN channel. "
        "(See the findings file for the full per-run detail.)")
    assert hook.get("tool_name") in (None, "Workflow") or "Workflow" in str(hook.get("tool_name")), \
        f"hook fired but tool_name is unexpected: {hook.get('tool_name')!r}"


def test_hook_payload_carries_full_preview(deny_run):
    """The intercepted hook payload carries the WHOLE preview a review card needs:
    the full script (with meta) so name / description / phases are recoverable."""
    if deny_run.get("error"):
        pytest.skip(f"deny run errored: {deny_run['error']}")
    if not deny_run["attempted"]:
        pytest.skip("no Workflow tool call issued")
    hook = deny_run["workflow_hook"]
    if hook is None:
        pytest.skip("hook did not fire (see test_hook_fires_for_workflow_gate) — "
                    "no payload to inspect on this channel")
    ti = hook.get("tool_input") or {}
    assert isinstance(ti, dict) and ti.get("script"), \
        f"workflow hook fired but tool_input.script is missing/empty: keys={list(ti)}"
    meta = deny_run["preview"] or {}
    FINDINGS["verdicts"]["preview_readable"] = bool(meta.get("name"))
    assert meta.get("has_meta"), "tool_input.script does not contain an `export const meta` block"
    assert meta.get("name") == SUBJECT_NAME, \
        f"preview name mismatch: {meta.get('name')!r} != {SUBJECT_NAME!r}"
    assert SUBJECT_DESC_MARK in (meta.get("description") or ""), \
        f"preview description did not survive: {meta.get('description')!r}"
    for t in SUBJECT_PHASE_TITLES:
        assert t in (meta.get("phase_titles") or []), \
            f"phase title {t!r} not recovered from the intercepted preview: {meta.get('phase_titles')}"


def test_hook_deny_rejects_and_aborts_workflow(deny_run):
    """ROUND-TRIP (reject): a 'deny' verdict from the hook ABORTS the workflow —
    no run dir appears. Proves Reject is deliverable through the hook channel.
    Corroborated by positive deny evidence (the permissionDecisionReason surfacing
    to the agent) recorded in findings, and by the A/B test's allow leg launching."""
    if deny_run.get("error"):
        pytest.skip(f"deny run errored: {deny_run['error']}")
    if not deny_run["attempted"]:
        pytest.skip("no Workflow tool call issued")
    if deny_run["workflow_hook"] is None:
        pytest.skip("hook did not fire — reject-via-hook is untestable on this channel")
    if deny_run["dialog_on_screen"]:
        pytest.skip("per-session skipWorkflowUsageWarning:true was NOT honored — the "
                    "built-in dialog blocked before the hook verdict could act; the "
                    "deny round-trip is confounded (see findings). Screen channel applies.")
    FINDINGS["verdicts"]["hook_deny_aborts"] = deny_run["launched"] is False
    FINDINGS["verdicts"]["deny_reason_surfaced"] = deny_run["deny_reason_seen"] is True
    assert deny_run["launched"] is False, (
        "the hook returned permissionDecision 'deny' but the workflow LAUNCHED anyway "
        f"(run dirs: {deny_run['new_run_dirs']}) — a PreToolUse deny does NOT abort the "
        "Workflow tool on this build. Reject must use the SCREEN channel (Escape/'3').")


def test_hook_allow_approves_and_launches_workflow(allow_run):
    """ROUND-TRIP (approve): an 'allow' verdict lets the workflow LAUNCH (a wf_ run
    dir appears). Proves Approve is deliverable through the hook channel."""
    if allow_run.get("error"):
        pytest.skip(f"allow run errored: {allow_run['error']}")
    if not allow_run["attempted"]:
        pytest.skip("no Workflow tool call issued in the allow run")
    # CRITICAL guard (mirrors the deny leg): if the hook never fired, a launch here
    # is the DEFAULT no-gate behavior (skipWorkflowUsageWarning:true + no gate), NOT
    # the hook channel — so it must NOT be reported as "approve via hook works".
    if allow_run["workflow_hook"] is None:
        pytest.skip("allow run: hook did not fire — a launch here would be default "
                    "no-gate behavior, not the hook channel; approve-via-hook untestable")
    if allow_run["dialog_on_screen"]:
        pytest.skip("per-session skipWorkflowUsageWarning:true was NOT honored — the "
                    "dialog blocked launch; approve round-trip confounded (see findings).")
    FINDINGS["verdicts"]["hook_allow_launches"] = (
        allow_run["workflow_hook"] is not None and allow_run["launched"] is True)
    assert allow_run["launched"] is True, (
        "the hook returned permissionDecision 'allow' but NO workflow run dir appeared "
        f"within {LAUNCH_SETTLE}s — approve did not launch the workflow. "
        f"screen tail:\n{allow_run['screen_tail'][-500:]}")


def test_hook_verdict_alone_controls_launch(deny_run, allow_run):
    """AUTHORITATIVE round-trip proof (A/B): identical setup, opposite verdict —
    'allow' LAUNCHES and 'deny' ABORTS. This one contrast kills BOTH false-green
    traps at once: 'the hook is ignored / default-allows' (refuted by the deny leg
    aborting) and 'the built-in dialog blocked it, not our deny' (refuted by the
    allow leg launching). Green here = the dashboard's Approve/Reject verdict ALONE
    decides whether the workflow runs — the interception round-trip is real."""
    for r, nm in ((deny_run, "deny"), (allow_run, "allow")):
        if r.get("error"):
            pytest.skip(f"{nm} run errored: {r['error']}")
        if not r["attempted"]:
            pytest.skip(f"{nm} run did not issue a Workflow call — A/B untestable")
        if r["workflow_hook"] is None:
            pytest.skip(f"{nm} run: hook did not fire — A/B untestable")
    FINDINGS["verdicts"]["hook_verdict_controls_launch"] = (
        allow_run["launched"] is True and deny_run["launched"] is False)
    assert allow_run["launched"] is True and deny_run["launched"] is False, (
        "the Approve/Reject verdict did NOT cleanly control launch — "
        f"allow.launched={allow_run['launched']} (want True), "
        f"deny.launched={deny_run['launched']} (want False). If BOTH launched, the "
        "hook verdict is being ignored; if NEITHER, something else (e.g. an unanswered "
        "dialog) is gating instead of our verdict. See findings.")


def test_hook_preempts_builtin_dialog(preempt_run):
    """ISOLATION: with the hook present AND the popup switch left ON
    (skipWorkflowUsageWarning:false), does the hook verdict PREEMPT the built-in
    'Run a dynamic workflow?' dialog — so the dashboard hook can be the SOLE gate —
    or do BOTH gates fire? This is the ONLY run that disentangles preemption from
    the skipWorkflowUsageWarning:true suppression present in deny_run/allow_run.
    Either outcome is a valid finding; only skips if the hook never fired."""
    if preempt_run.get("error"):
        pytest.skip(f"preempt run errored: {preempt_run['error']}")
    if not preempt_run["attempted"]:
        pytest.skip("no Workflow tool call issued in the preempt run")
    if preempt_run["workflow_hook"] is None:
        pytest.skip("hook did not fire — dialog preemption is untestable on this run")
    preempts = (preempt_run["dialog_on_screen"] is False
                and preempt_run["launched"] is True)
    FINDINGS["verdicts"]["hook_preempts_dialog"] = preempts
    if preempts:
        return  # proven: hook overrode the gate with the popup ON → sole gate
    # NOT preempted → both gates fired → the agent should be parked at the
    # (unanswered) dialog and NOT launched. Assert that self-consistent state so a
    # weird third outcome (dialog gone AND not launched, or dialog shown AND
    # launched) surfaces as a real failure instead of a quiet "NO".
    assert preempt_run["dialog_on_screen"] is True and preempt_run["launched"] is not True, (
        "hook fired with the popup ON but the outcome is neither 'preempted (no "
        "dialog, launched)' nor 'both gates (dialog shown, not launched)': "
        f"dialog_on_screen={preempt_run['dialog_on_screen']} "
        f"launched={preempt_run['launched']} — investigate the gate ordering.")


# -----------------------------------------------------------------------------
# Test — CHANNEL 2 (screen): dialog renders in the pane; answerable by keys
# -----------------------------------------------------------------------------
def test_screen_dialog_renders_and_is_answerable(screen_run, br):
    """SECOND channel: with the built-in gate forced on per-session, the 'Run a
    dynamic workflow?' dialog renders in the bridged pane and can be read + rejected
    with a keystroke. Records (not fails) when the dialog can't be forced on —
    that outcome answers whether per-session skipWorkflowUsageWarning is honored."""
    if screen_run.get("error"):
        pytest.skip(f"screen run errored: {screen_run['error']}")
    if not screen_run["attempted"]:
        pytest.skip("no Workflow tool call issued in the screen run")
    FINDINGS["verdicts"]["screen_dialog_rendered"] = screen_run["dialog_on_screen"]
    if not screen_run["dialog_on_screen"]:
        pytest.skip("the 'Run a dynamic workflow?' dialog did NOT render in the pane "
                    "even with skipWorkflowUsageWarning:false in the agent --settings — "
                    "either the per-session override is not honored (dialog is global-only) "
                    "or it does not surface under tmux. Screen channel INCONCLUSIVE here; "
                    "the hook channel is the reliable path. (Recorded in findings.)")
    # Dialog rendered — the preview (title/options) is readable off the pane.
    assert _screen_has_dialog(screen_run["dialog_scrape"] or ""), \
        "dialog detected but its markers were not in the captured scrape"
    FINDINGS["verdicts"]["screen_preview_readable"] = True
    # …and it is answerable by keystroke. `dialog_rejected` is None only when the
    # Escape keystroke path itself raised — that is INCONCLUSIVE (skip), never a pass.
    if screen_run["dialog_rejected"] is None:
        pytest.skip("reject keystroke inconclusive — keys()/read() raised during the "
                    "Escape, so answerability is indeterminate (see findings)")
    FINDINGS["verdicts"]["screen_reject_by_keys"] = screen_run["dialog_rejected"] is True
    assert screen_run["dialog_rejected"] is True, (
        "sent Escape to the workflow dialog but its markers were still on the pane "
        f"afterward — the screen-channel reject keystroke did not take. "
        f"after tail:\n{screen_run['after_reject_tail'][-400:]}")
    # And the reject actually ABORTED it — no workflow run dir appeared.
    assert screen_run["launched"] is not True, (
        "Escape appeared to close the dialog, but a workflow run dir still appeared — "
        "the keystroke did not actually reject the launch")


# -----------------------------------------------------------------------------
# Findings writer — the plain-language deliverable an agent pastes back
# -----------------------------------------------------------------------------
def _emit_findings():
    if not FINDINGS["runs"]:
        return
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    v = FINDINGS["verdicts"]
    runs = FINDINGS["runs"]

    # The RIGOROUS proof is the A/B contrast: identical setup, opposite verdict.
    # allow→launched AND deny→not-launched (both with the hook firing) means the
    # hook's verdict ALONE decides launch — ruling out "default-allow ignores the
    # hook" (allow leg) and "the dialog blocked it" (deny leg) at once.
    deny, allow = runs.get("hook_deny", {}), runs.get("hook_allow", {})
    if deny.get("workflow_hook") and allow.get("workflow_hook"):
        v.setdefault("hook_verdict_controls_launch",
                     allow.get("launched") is True and deny.get("launched") is False)
    # NOTE: 'hook_preempts_dialog' is set ONLY by test_hook_preempts_builtin_dialog
    # (the isolation run with the popup ON). It is deliberately NOT computed from the
    # deny/allow runs here — those suppress the popup (skip_warning=True), so their
    # dialog-absence is confounded and cannot support a preemption claim.

    def yn(key):
        return {True: "YES", False: "NO"}.get(v.get(key), "— (inconclusive/not reached)")

    lines = [
        "WORKFLOW-APPROVAL-GATE INTERCEPTION — spike findings",
        f"  generated: {stamp}",
        "",
        "THE QUESTION: can the dashboard intercept a workflow at its approval gate,",
        "read the full preview, and round-trip Approve/Reject back to the agent?",
        "",
        "ANSWERS (empirical, this run):",
        f"  • a Workflow tool call was induced in a bridged session ...... {yn('workflow_call_issued')}",
        f"  • CHANNEL 1 — a PreToolUse hook FIRES for the Workflow gate .... {yn('hook_fires_for_workflow')}",
        f"  • the hook payload carries the FULL preview (name/desc/phases) . {yn('preview_readable')}",
        f"  • REJECT round-trip: a hook 'deny' ABORTS the workflow ......... {yn('hook_deny_aborts')}",
        f"    (corroborated: the deny reason surfaced to the agent ....... {yn('deny_reason_surfaced')})",
        f"  • APPROVE round-trip: a hook 'allow' LAUNCHES the workflow ..... {yn('hook_allow_launches')}",
        f"  • A/B PROOF: the hook VERDICT ALONE controls launch ........... {yn('hook_verdict_controls_launch')}",
        f"    (allow→launches, deny→aborts, same setup — rules out default-allow)",
        f"  • the hook verdict PREEMPTS the built-in dialog (sole gate) .... {yn('hook_preempts_dialog')}",
        f"    (isolated: hook present with the popup switch left ON)",
        f"  • CHANNEL 2 — the 'Run a dynamic workflow?' dialog renders ..... {yn('screen_dialog_rendered')}",
        f"    (per-session skipWorkflowUsageWarning:false honored)",
        f"  • the dialog preview is readable off the pane ................. {yn('screen_preview_readable')}",
        f"  • the dialog is answerable by keystroke (Escape rejects) ...... {yn('screen_reject_by_keys')}",
        "",
        "PER-RUN DETAIL:",
    ]
    for tag, o in FINDINGS["runs"].items():
        hook = o.get("workflow_hook")
        prev = o.get("preview") or {}
        lines += [
            f"  [{tag}] verdict={o['verdict']} skip_warning={o['skip_warning']} "
            f"session={o['session']}",
            f"      attempted={o['attempted']}  hook_fired={hook is not None}  "
            f"launched={o['launched']}  dialog_on_screen={o['dialog_on_screen']}  "
            f"transcript_toolcall={o['transcript_toolcall']}",
            f"      preview: name={prev.get('name')!r} phases={prev.get('phase_titles')}",
        ]
        if hook is not None:
            lines.append(f"      hook payload keys: {o.get('hook_payload_keys')}")
        if o.get("catch_all_tools"):
            lines.append(f"      tool_names the catch-all hook saw: {o['catch_all_tools']}")
        if o.get("dialog_answered"):
            lines.append(f"      screen dialog: answered=True rejected={o.get('dialog_rejected')}")
        if o.get("verdict") == "deny":
            lines.append(f"      deny reason surfaced to agent: {o.get('deny_reason_seen')}")
        if o.get("new_run_dirs"):
            lines.append(f"      run dirs: {o['new_run_dirs']}")
        if o.get("error"):
            lines.append(f"      ERROR: {o['error']}")
    text = "\n".join(lines) + "\n"

    (LOG_DIR / f"workflow_approval_findings_{stamp}.txt").write_text(text, encoding="utf-8")
    (LOG_DIR / "workflow_approval_findings_latest.txt").write_text(text, encoding="utf-8")
    log.info("findings written to tests/log/workflow_approval_findings_latest.txt")
