"""Live spike — Plan/Decision PreToolUse hook interception (§10 item #6).

A **split** spike, DETECTION-first (Approach A — real sidecar):

* **Detection (must pass for a green).** A live bridge agent driven to call
  ``ExitPlanMode`` (plan mode) / ``AskUserQuestion`` fires the per-agent
  ``PreToolUse`` HTTP hook that ``BridgeDriver._build_hook_settings`` wires
  (``ExitPlanMode`` -> ``/internal/hooks/plan/{agent}``, ``AskUserQuestion`` ->
  ``/internal/hooks/decision/{agent}``). The hook POSTs to the sidecar over the
  WSL->Windows host gateway; the sidecar's ``hook_plan`` / ``hook_decision``
  raises a typed ``plan`` / ``decision`` inbox card (``inbox.raise_item``) and
  returns ``{}`` (allow / detect-and-surface). We stand up the REAL sidecar as a
  subprocess bound to ``0.0.0.0:7690`` (the fixed hook port), drive a standalone
  ``BridgeDriver``, then ``GET /inbox`` and assert the card appears keyed by the
  agent, with a usable ``data.tool_input``. This proves the whole detect->card
  chain the dashboard uses.

* **Answer/resume (probe + write-up, NOT a hard green).** The hook returns ``{}``
  = allow, so it does not hold-for-answer; the research is explicit the allow
  path is buggy/interactive. Open question: after detection, does the agent
  proceed on its own, or park at an interactive plan-review box that needs a
  ``keys()`` Enter to resume out of plan mode? We read the live screen/transcript
  back, record what we see (scratch file + DEBUG log), and try at most one
  guarded Enter — gated on a non-generating state per the research idle-gating
  note. The test never fails on the resume outcome; it records it.

Parallel-safe: our OWN ``TmuxBridge`` for shell/read helpers (NOT conftest's
session-scoped ``bridge`` fixture, whose setup/teardown call ``tmux kill-server``
and would kill sibling agents' live sessions); each agent's tmux session is
uniquely named ``plandec-<uuid8>`` (== its sidecar session id / inbox key);
teardown closes ONLY our own session + throwaway dir and terminates our own
sidecar subprocess. NEVER ``kill-server``. The sidecar subprocess runs with an
EMPTY ``AWL_SIDECAR_RUNTIME`` so no real/sibling record is ever visible to it
(startup itself restores nothing by default — §9.1 picker-first — so this
isolates the on-open restore point and every roster read, not a boot sweep).

* **#22 verdict endpoint (REVISE + APPROVE) — live end to end.** A third test
  (``test_plan_verdict_revise_then_approve_live``) proves the §11 #22
  ``POST /sessions/{id}/plan/verdict`` endpoint against a REAL parked
  plan-review box, on a session the sidecar subprocess itself OWNS (created via
  its ``POST /sessions``, so hooks and the endpoint land in one process). The
  revise leg was the one ⚠-assumed, never-live-driven path in the system: Escape
  dismisses the box AND keeps the agent in plan mode, and the queued feedback
  flushes as the next prompt (a second, instruction-reflecting plan card). See
  the section comment above that test for the full proof sequence.

Run::

    pytest tests/test_plan_decision_hooks_live.py -m integration   # from repo root
"""

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import pytest

# The sidecar's modules import as top-level (it runs with its own dir on
# sys.path, not the repo root); the bridge package lives at the repo root. Put
# both on sys.path so `from drivers.bridge import BridgeDriver` and
# `from bridge import TmuxBridge` resolve.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SIDECAR = _REPO_ROOT / "sidecar"
for _p in (str(_SIDECAR), str(_REPO_ROOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from drivers.bridge import BridgeDriver  # noqa: E402
from drivers.base import DriverConfig  # noqa: E402
from bridge import TmuxBridge  # noqa: E402

log = logging.getLogger(__name__)

pytestmark = [pytest.mark.integration, pytest.mark.slow]

SLUG = "plandec"                 # tmux-name + sidecar-session-id + dir prefix
SIDECAR_URL = "http://127.0.0.1:7690"
DETECT_TIMEOUT = 120            # seconds to poll /inbox for a card
SCRATCH = _REPO_ROOT / ".scratch"


# -----------------------------------------------------------------------------
# Fixtures — our OWN bridge/runtime, and a real sidecar subprocess on :7690.
# -----------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _runtime_to_tmp(tmp_path, monkeypatch):
    """Keep THIS process's driver runtime records out of sidecar/runtime/."""
    monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(tmp_path / "runtime"))


@pytest.fixture
def br():
    """Our OWN TmuxBridge — teardown does NOTHING destructive to the tmux server
    (no kill-server / shutdown). Used for the throwaway dir + resume-probe reads."""
    b = TmuxBridge()
    yield b


@pytest.fixture
def diag_dir(br):
    """A fresh, empty WSL throwaway dir; removed after the test."""
    path = f"/home/lester/awl-{SLUG}-{uuid.uuid4().hex[:8]}"
    br._run(f"mkdir -p {path}")
    yield path
    br._run(f"rm -rf {path}")


def _inbox_ok():
    """True if something answers GET /inbox with the expected shape."""
    try:
        with urllib.request.urlopen(f"{SIDECAR_URL}/inbox", timeout=3) as r:
            data = json.loads(r.read().decode("utf-8"))
        return isinstance(data, dict) and "inbox" in data
    except Exception:
        return False


@pytest.fixture(scope="module")
def sidecar_proc():
    """Start the REAL sidecar (sidecar/main.py, exactly as start-dashboard.bat
    does) bound to 0.0.0.0:7690 so in-WSL agents' hooks reach it over the host
    gateway. Isolated with an EMPTY AWL_SIDECAR_RUNTIME so no real/sibling
    record is visible to it (startup restores nothing by default — §9.1; the
    empty runtime isolates every roster read and the on-open restore point).
    Yields the base URL; terminates on teardown. Never touches the tmux
    server."""
    SCRATCH.mkdir(parents=True, exist_ok=True)

    # Refuse to run Approach A if a FOREIGN server already holds :7690 — reading
    # its inbox would be wrong. (We keep our own agent ids unique, so the worst
    # case is a clean failure/None, never a false pass.)
    if _inbox_ok():
        pytest.fail(
            "port 7690 already answers /inbox before we launched our sidecar — "
            "a foreign sidecar is running; cannot run Approach A safely. Stop it "
            "and re-run this test in isolation."
        )

    runtime_dir = tempfile.mkdtemp(prefix="awl-plandec-rt-")
    env = os.environ.copy()
    env["AWL_SIDECAR_RUNTIME"] = runtime_dir      # empty -> isolated records (no boot restore by default, §9.1)
    env["AWL_SIDECAR_HOST"] = "0.0.0.0"           # WSL-reachable (the default)
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"

    log_path = SCRATCH / "plandec_sidecar.log"
    logf = open(log_path, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [sys.executable, "main.py"],
        cwd=str(_SIDECAR),
        env=env,
        stdout=logf,
        stderr=subprocess.STDOUT,
    )

    # Readiness: OUR proc must be alive AND /inbox must answer.
    ready = False
    deadline = time.time() + 40
    while time.time() < deadline:
        if proc.poll() is not None:
            logf.flush()
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-1500:]
            pytest.fail(
                f"sidecar subprocess exited early (rc={proc.returncode}) — could "
                f"not bind :7690 or crashed. log tail:\n{tail}"
            )
        if _inbox_ok():
            ready = True
            break
        time.sleep(0.5)

    if not ready:
        proc.terminate()
        logf.flush()
        pytest.fail("sidecar did not become ready on :7690 within 40s")

    log.debug("sidecar subprocess ready on %s (runtime=%s)", SIDECAR_URL, runtime_dir)
    try:
        yield SIDECAR_URL
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
        logf.close()


# -----------------------------------------------------------------------------
# Driver harness + inbox polling
# -----------------------------------------------------------------------------

class _Driven:
    """Run a standalone BridgeDriver with a slug-prefixed, uniquely-named tmux
    session whose name == the sidecar session id == the inbox key (1:1), so a
    raised card is trivially attributable to THIS agent."""

    def __init__(self, diag, session_id, permission_mode):
        self.session_id = session_id
        self.events: list[dict] = []
        self.driver = BridgeDriver(
            DriverConfig(cwd=diag, permission_mode=permission_mode),
            self.events.append,
            session_id=session_id,
        )
        # Force the tmux session name to the slug-prefixed session id (must be set
        # BEFORE start()/create()). BridgeDriver would otherwise name it
        # `awl-<uuid8>`; pinning it to `plandec-<uuid8>` honors the isolation rule
        # exactly and makes tmux-name == inbox-key.
        self.driver._name = session_id
        self._task = None

    async def start(self):
        await self.driver.start()
        self._task = asyncio.create_task(self._consume())

    async def _consume(self):
        try:
            async for e in self.driver.events():
                self.events.append(e)
        except asyncio.CancelledError:  # pragma: no cover - teardown
            raise

    @property
    def tmux_name(self):
        return self.driver.tmux_name

    async def close(self):
        if self._task:
            self._task.cancel()
        await self.driver.close()  # kills ONLY this session's tmux session


def _get_inbox(base_url):
    with urllib.request.urlopen(f"{base_url}/inbox", timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))


async def _wait_for_card(base_url, agent_id, itype, timeout):
    """Poll GET /inbox until an item of `itype` appears under `agent_id`, or None
    on timeout. Returns the matching item dict."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            data = await asyncio.to_thread(_get_inbox, base_url)
        except Exception as e:  # noqa: BLE001
            log.debug("inbox poll error (retrying): %s", e)
            data = None
        if data:
            for it in data.get("inbox", {}).get(agent_id, []):
                if it.get("type") == itype:
                    return it
        await asyncio.sleep(2.0)
    return None


async def _probe_answer_resume(d, note_name):
    """Read the live pane/transcript back after detection and record whether the
    agent proceeded on its own or parked at an interactive review box; try at most
    one guarded Enter (gated on a non-generating state). Records a finding to a
    scratch file + the DEBUG log and returns a result dict:

        {"parked": bool, "drove_enter": bool, "resumed": True|False|None,
         "finding": str}

    ``resumed`` is None when we did NOT drive the box (nothing to claim), True
    when the guarded Enter left the review box (agent resumed), False when Enter
    did NOT change the screen (the mechanism failed). The test asserts only
    ``resumed is not False`` — durable proof that never flakes on wording drift."""
    lines = [f"# plan/decision answer-resume probe — {note_name}"]
    result = {"parked": None, "drove_enter": False, "resumed": None, "finding": None}
    try:
        br = d.driver._bridge
        name = d.tmux_name
        st = await asyncio.to_thread(br.status, name)
        screen = (await asyncio.to_thread(br.read, name, 40))["content"]
        state = st.get("state")
        lines.append(f"state={state}")
        lines.append("screen_tail:\n" + screen[-800:])

        parked_markers = bool(re.search(
            r"(Would you like to proceed|keep planning|Yes,|❯\s|\b1\.\s)",
            screen, re.I,
        ))
        result["parked"] = parked_markers
        lines.append(f"parked_markers={parked_markers}")

        if state != "generating" and parked_markers:
            # Single guarded accept — Enter selects the highlighted option, the
            # same key the bridge uses to answer numbered prompts.
            await asyncio.to_thread(br.keys, name, "Enter")
            await asyncio.sleep(3.0)
            after = (await asyncio.to_thread(br.read, name, 40))["content"]
            result["drove_enter"] = True
            result["resumed"] = after != screen
            lines.append(f"after_enter_changed={result['resumed']}")
            lines.append("after_tail:\n" + after[-800:])
        else:
            lines.append("no guarded Enter sent (generating, or no review box on screen)")

        # Transcript-side signal: did the turn progress past the tool call?
        try:
            usage = await d.driver.get_context_usage()
            lines.append(f"context_usage={usage}")
        except Exception as e:  # noqa: BLE001
            lines.append(f"context_usage unavailable: {e}")

        finding = (
            "PARKED at interactive review box (needs Enter to resume)"
            if parked_markers else
            "PROCEEDED on its own after allow (no review box seen)"
        )
        if result["resumed"] is True:
            finding += "; guarded keys(Enter) resumed the agent out of the box"
        elif result["resumed"] is False:
            finding += "; guarded keys(Enter) did NOT change the screen"
        result["finding"] = finding
        lines.append(f"FINDING: {finding}")
        log.debug("answer-resume finding (%s): %s | state=%s", note_name, finding, state)
    except Exception as e:  # noqa: BLE001
        lines.append(f"probe error (non-fatal): {e}")
        log.debug("answer-resume probe error (%s): %s", note_name, e)
    finally:
        try:
            SCRATCH.mkdir(parents=True, exist_ok=True)
            (SCRATCH / f"plandec_resume_probe_{note_name}.txt").write_text(
                "\n".join(lines), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    return result


# -----------------------------------------------------------------------------
# Detection — Plan (ExitPlanMode)
# -----------------------------------------------------------------------------

def test_detection_plan_card_raised(sidecar_proc, br, diag_dir):
    """A plan-mode agent driven to present its plan via ExitPlanMode fires the
    PreToolUse(ExitPlanMode) hook; a `plan` card with a usable tool_input appears
    at GET /inbox keyed by the agent. (Then: probe answer/resume, write-up only.)"""
    agent_id = f"{SLUG}-{uuid.uuid4().hex[:8]}"

    async def flow():
        d = _Driven(diag_dir, agent_id, permission_mode="plan")
        await d.start()
        try:
            assert d.tmux_name == agent_id and agent_id.startswith(f"{SLUG}-"), \
                f"tmux session not slug-named as expected: {d.tmux_name!r}"

            await d.driver.send(
                "Make a short plan to create a file called hello.txt containing "
                "the word world, then use the ExitPlanMode tool to present your "
                "plan. Do not write anything yet."
            )

            # THE CRUX: read the card back from the sidecar's inbox over HTTP.
            card = await _wait_for_card(sidecar_proc, agent_id, "plan", DETECT_TIMEOUT)
            if card is None:
                screen = br.read(d.tmux_name, lines=40)["content"]
                raise AssertionError(
                    f"no `plan` card at /inbox for {agent_id} within "
                    f"{DETECT_TIMEOUT}s — the PreToolUse(ExitPlanMode) hook did "
                    f"not surface. live screen tail:\n{screen[-800:]}"
                )
            tool_input = (card.get("data") or {}).get("tool_input") or {}
            assert tool_input, (
                f"plan card raised but tool_input is empty/unusable: {card!r}"
            )
            assert (card.get("data") or {}).get("tool") in (None, "ExitPlanMode") \
                or "ExitPlanMode" in str(card.get("data")), \
                f"plan card tool mismatch: {card!r}"
            log.debug("DETECTION(plan) OK: card=%s", card)

            # Answer/resume probe. Durable-but-robust: only asserts when we
            # actually drove the plan-review box — proven live that keys(Enter)
            # resumes the agent out of plan mode. Degrades to no-op (resumed=None)
            # if a future TUI changes the box wording, so it can't flake.
            probe = await _probe_answer_resume(d, "plan")
            assert probe["resumed"] is not False, (
                "drove keys(Enter) on the plan-review box but the agent did NOT "
                f"resume (screen unchanged) — resume mechanism broke: {probe}"
            )
        finally:
            await d.close()

    asyncio.run(flow())


# -----------------------------------------------------------------------------
# Detection — Decision (AskUserQuestion)  [second detection, same file]
# -----------------------------------------------------------------------------

def test_detection_decision_card_raised(sidecar_proc, br, diag_dir):
    """An agent driven to call AskUserQuestion fires the
    PreToolUse(AskUserQuestion) hook; a `decision` card with a usable tool_input
    appears at GET /inbox keyed by the agent."""
    agent_id = f"{SLUG}-{uuid.uuid4().hex[:8]}"

    async def flow():
        d = _Driven(diag_dir, agent_id, permission_mode="acceptEdits")
        await d.start()
        try:
            assert d.tmux_name == agent_id, \
                f"tmux session not slug-named as expected: {d.tmux_name!r}"

            await d.driver.send(
                "Before doing anything, use the AskUserQuestion tool to ask me "
                "whether I prefer option A or option B."
            )

            card = await _wait_for_card(sidecar_proc, agent_id, "decision", DETECT_TIMEOUT)
            if card is None:
                screen = br.read(d.tmux_name, lines=40)["content"]
                raise AssertionError(
                    f"no `decision` card at /inbox for {agent_id} within "
                    f"{DETECT_TIMEOUT}s — the PreToolUse(AskUserQuestion) hook did "
                    f"not surface. live screen tail:\n{screen[-800:]}"
                )
            tool_input = (card.get("data") or {}).get("tool_input") or {}
            assert tool_input, (
                f"decision card raised but tool_input is empty/unusable: {card!r}"
            )
            log.debug("DETECTION(decision) OK: card=%s", card)

            probe = await _probe_answer_resume(d, "decision")
            assert probe["resumed"] is not False, (
                "drove keys(Enter) on the AskUserQuestion box but the agent did "
                f"NOT resume (screen unchanged) — resume mechanism broke: {probe}"
            )
        finally:
            await d.close()

    asyncio.run(flow())


# -----------------------------------------------------------------------------
# §11 #22 — the plan/verdict ENDPOINT live-proven end to end: REVISE (the
# ⚠-assumed Escape leg), then APPROVE — on a sidecar-OWNED session.
# -----------------------------------------------------------------------------
#
# The two detection tests above run their BridgeDriver in THIS test process, so
# the sidecar subprocess never owns the session — a direct
# ``POST /sessions/{id}/plan/verdict`` for those agents would 404. This test
# instead creates the agent THROUGH the sidecar subprocess's own HTTP API
# (``POST /sessions`` with ``permission_mode: "plan"``): the subprocess owns the
# session, the agent's PreToolUse(ExitPlanMode) hook lands in the SAME process's
# inbox, and the REAL endpoint drives the REAL parked TUI — the strongest
# possible proof of the two never-live-driven assumptions in `plan_verdict`:
#
#   (a) Escape on a real parked plan-review box DISMISSES it and KEEPS the
#       agent in plan mode (rather than aborting plan mode or being swallowed);
#   (b) the revise feedback queued as a disposition-"next" prompt actually
#       FLUSHES into the agent, which revises and re-presents — a SECOND plan
#       card whose plan reflects the instruction.
#
# The approve leg (already mechanism-proven by `_probe_answer_resume` above)
# then rides the same endpoint on the second box: Enter resumes the agent OUT
# of plan mode, read back off the screen's mode indicator.
#
# This test's screen reads go through our OWN TmuxBridge (read-only:
# ``read``/``permission_mode``/``list`` — never keys; the ENDPOINT owns every
# keystroke). Teardown deletes ONLY our own session via the sidecar
# (``DELETE /sessions/{id}?hard=true``), with a direct `close()` of our one
# tmux session as the fallback. Findings:
# ``tests/log/plan_verdict_revise_findings_*.txt`` (+ ``_latest``).

# The plan-review box's own wording — unlike the broader parked-marker regex in
# `_probe_answer_resume`, this must NOT match an idle input box (no `❯`/"1. "
# alternates), because the revise assertions key on its absence after Escape.
# Matched over a WHITESPACE-NORMALIZED capture (`_norm`): the TUI wraps the
# question mid-phrase ("Would you like to \n proceed?" — live-caught on
# 2.1.212). Alternates cover the menu's wording drift across CC builds: the
# 2.1.198-era "Would you like to proceed" / "keep planning", and 2.1.212's
# "ready to execute" + "Tell Claude what to change" menu (whose approve option
# is now "Yes, and use auto mode" — so an approved agent lands in AUTO mode,
# not acceptEdits, on that build).
PLAN_BOX_RE = re.compile(
    r"Would you like to proceed|ready to execute|keep planning|"
    r"Tell Claude what to change", re.I)


def _norm(text):
    """Collapse all whitespace (incl. the TUI's mid-phrase line wraps) so the
    box-wording regex can't be defeated by render width."""
    return re.sub(r"\s+", " ", text or "")
VERDICT_TIMEOUT = 300   # revise leg: idle-gated queue flush + a full plan turn
LOG_DIR = Path(__file__).resolve().parent / "log"


def _http(method, path, body=None, timeout=30):
    """Minimal JSON round-trip against the sidecar subprocess -> (status, payload)."""
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


def _session_status(sid):
    code, s = _http("GET", f"/sessions/{sid}", timeout=10)
    return (s or {}).get("status") if code == 200 else None


def _open_cards(sid, itype):
    """This agent's OPEN inbox cards of `itype` (GET /inbox lists open only,
    so a card the endpoint resolved disappears from here)."""
    code, data = _http("GET", "/inbox", timeout=10)
    if code != 200 or not isinstance(data, dict):
        return []
    return [it for it in (data.get("inbox") or {}).get(sid, [])
            if it.get("type") == itype]


def _screen(br_, name, lines=40):
    try:
        return br_.read(name, lines=lines)["content"]
    except Exception as e:  # noqa: BLE001 — session gone / transient read error
        log.debug("screen read failed for %s: %s", name, e)
        return ""


def _mode(br_, name):
    """Read-only mode-indicator parse off the live screen; None on any miss."""
    try:
        return br_.permission_mode(name)
    except Exception:  # noqa: BLE001
        return None


def _write_verdict_findings(lines):
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    text = "\n".join(lines) + "\n"
    (LOG_DIR / f"plan_verdict_revise_findings_{stamp}.txt").write_text(
        text, encoding="utf-8")
    (LOG_DIR / "plan_verdict_revise_findings_latest.txt").write_text(
        text, encoding="utf-8")


def test_plan_verdict_revise_then_approve_live(sidecar_proc, br, diag_dir):
    """#22 REVISE leg, live end to end: `POST /sessions/{id}/plan/verdict
    {"verdict": "revise", "text": ...}` on a REAL parked plan-review box
    dismisses the box (Escape), KEEPS the agent in plan mode, resolves the open
    plan card, and delivers the feedback as the next prompt — proven by a SECOND
    plan card whose plan reflects the instruction. Then the approve leg on the
    second box takes the agent OUT of plan mode (screen mode read-back)."""
    findings = [
        "#22 plan/verdict REVISE leg — live proof (sidecar-owned session)",
        f"date: {time.strftime('%Y-%m-%d %H:%M:%S')}",
    ]
    sid = None
    tmux = None
    pre_names = {s["name"] for s in br.list()}
    try:
        # -- 1. Create THROUGH the sidecar so the subprocess OWNS the session --
        code, created = _http("POST", "/sessions", {
            "permission_mode": "plan",
            "cwd": diag_dir,
            "model": "sonnet",                    # cheap plan turns
            "identity": {"name": f"{SLUG}-verdict"},
        }, timeout=90)
        assert code == 200 and created, f"POST /sessions failed: {code} {created!r}"
        sid = created["session_id"]
        findings.append(f"created sidecar-owned session {sid} (cwd={diag_dir})")

        # Attribute OUR tmux session: the driver names it `awl-<uuid8>`, so the
        # one new `awl-*` name since the pre-create snapshot is ours. Exactly one
        # is required — run this test in isolation from other spawners.
        def _new_names():
            fresh = {s["name"] for s in br.list()} - pre_names
            return {n for n in fresh if n.startswith("awl-")}

        news = _poll(_new_names, 30)
        assert news and len(news) == 1, (
            f"could not attribute the sidecar-owned tmux session (new awl-* "
            f"names: {news!r}) — run this test in isolation")
        tmux = next(iter(news))
        findings.append(f"tmux session: {tmux}")

        assert _poll(lambda: _session_status(sid) == "idle", 180), \
            f"agent never reached idle (status={_session_status(sid)!r})"
        assert _poll(lambda: _mode(br, tmux) == "plan", 30), (
            "launched with permission_mode=plan but the screen mode indicator "
            f"reads {_mode(br, tmux)!r}")
        findings.append("launch mode read-back: plan")

        # -- 2. Drive to the FIRST parked plan-review box ----------------------
        code, _ = _http("POST", f"/sessions/{sid}/send", {
            "prompt": ("Make a short plan to create a file called hello.txt "
                       "containing the word world, then use the ExitPlanMode "
                       "tool to present your plan. Do not write anything yet."),
        }, timeout=30)
        assert code == 200, f"send failed: {code}"

        card1 = _poll(lambda: next(iter(_open_cards(sid, "plan")), None),
                      DETECT_TIMEOUT, 2.0)
        assert card1, (
            f"no `plan` card at /inbox for {sid} within {DETECT_TIMEOUT}s — "
            f"screen tail:\n{_screen(br, tmux)[-800:]}")
        findings.append(f"first plan card: id={card1.get('id')}")

        assert _poll(lambda: PLAN_BOX_RE.search(_norm(_screen(br, tmux))), 45), (
            "plan card raised but the plan-review box never parked on screen — "
            f"screen tail:\n{_screen(br, tmux)[-800:]}")
        findings.append("first review box parked; screen excerpt:\n"
                        + _screen(br, tmux)[-600:])
        findings.append(f"sidecar status while parked: {_session_status(sid)!r}")

        # -- 3. THE CRUX — the REVISE leg through the REAL endpoint ------------
        revise_text = ("Revise the plan: add a step that also creates a "
                       "README.md file containing the word docs. Then present "
                       "the revised plan again with the ExitPlanMode tool. "
                       "Do not write anything yet.")
        code, body = _http("POST", f"/sessions/{sid}/plan/verdict",
                           {"verdict": "revise", "text": revise_text}, timeout=30)
        assert code == 200 and (body or {}).get("verdict") == "revise", \
            f"plan/verdict revise failed: {code} {body!r}"
        findings.append("POST plan/verdict {verdict: revise, text: ...} -> 200")

        # (a) Escape DISMISSED the parked box…
        assert _poll(lambda: not PLAN_BOX_RE.search(_norm(_screen(br, tmux))), 30,
                     interval=0.5), (
            "⚠ ASSUMPTION BROKEN: Escape did NOT dismiss the parked plan-review "
            f"box — screen tail:\n{_screen(br, tmux)[-800:]}")
        findings.append("Escape dismissed the review box (box wording gone)")

        # (b) …and KEPT the agent in plan mode (the abort/swallow hazard).
        assert _poll(lambda: _mode(br, tmux) == "plan", 45), (
            "⚠ ASSUMPTION BROKEN: after the revise Escape the mode indicator "
            f"reads {_mode(br, tmux)!r}, not 'plan' — screen tail:\n"
            + _screen(br, tmux)[-800:])
        findings.append("agent STILL IN PLAN MODE after Escape (indicator read-back)")

        # (c) The endpoint resolved the first card (open-only /inbox drops it).
        open_ids = {c.get("id") for c in _open_cards(sid, "plan")}
        assert card1.get("id") not in open_ids, \
            f"first plan card still open after the verdict: {open_ids!r}"
        findings.append("first plan card resolved by the endpoint")

        # (d) The feedback DELIVERED: a SECOND plan card arrives, reflecting it.
        def _second_card():
            for c in _open_cards(sid, "plan"):
                if c.get("id") != card1.get("id"):
                    return c
            return None

        card2 = _poll(_second_card, VERDICT_TIMEOUT, 2.0)
        assert card2, (
            "queued revise feedback never produced a second plan card within "
            f"{VERDICT_TIMEOUT}s — status={_session_status(sid)!r}, screen "
            f"tail:\n{_screen(br, tmux)[-800:]}")
        findings.append(f"second plan card: id={card2.get('id')}")
        card2_json = json.dumps(card2)
        assert "readme" in card2_json.lower(), (
            "second plan card does not reflect the revise instruction (no "
            f"'README' anywhere in the card): {card2_json[:600]}")
        findings.append("revised plan reflects the instruction (README step present)")
        plan_text = ((card2.get("data") or {}).get("tool_input") or {}).get("plan")
        if plan_text:
            findings.append("revised plan text (first 500 chars):\n"
                            + str(plan_text)[:500])

        assert _poll(lambda: PLAN_BOX_RE.search(_norm(_screen(br, tmux))), 45), (
            "second plan card raised but no parked box on screen — screen "
            f"tail:\n{_screen(br, tmux)[-800:]}")
        findings.append("second review box parked on screen")

        # -- 4. APPROVE on the second box: the agent leaves plan mode ----------
        code, body = _http("POST", f"/sessions/{sid}/plan/verdict",
                           {"verdict": "approve"}, timeout=30)
        assert code == 200 and (body or {}).get("verdict") == "approve", \
            f"plan/verdict approve failed: {code} {body!r}"
        assert _poll(lambda: not PLAN_BOX_RE.search(_norm(_screen(br, tmux))), 30,
                     interval=0.5), (
            "approve Enter did not clear the review box — screen tail:\n"
            + _screen(br, tmux)[-800:])

        def _mode_after():
            m = _mode(br, tmux)
            return m if (m and m != "plan") else None

        m2 = _poll(_mode_after, 60)
        assert m2, ("approve did not take the agent out of plan mode — the "
                    f"indicator still reads {_mode(br, tmux)!r}")
        findings.append(f"approve leg: box cleared, mode left plan -> {m2!r}")

        # Bonus (recorded, not asserted): the approved plan actually executes.
        ran = _poll(lambda: "hello.txt" in (br._run(f"ls {diag_dir}") or ""),
                    120, 5.0)
        findings.append(f"post-approve execution observed (hello.txt in cwd): {bool(ran)}")
        findings.append("VERDICT: revise leg PROVEN live — Escape dismisses + "
                        "keeps plan mode; queued feedback delivers; approve "
                        "resumes out of plan mode.")
    finally:
        if sid:
            code, _ = _http("DELETE", f"/sessions/{sid}?hard=true", timeout=30)
            findings.append(f"teardown: DELETE /sessions/{sid}?hard=true -> {code}")
        if tmux:
            if _poll(lambda: tmux not in {s["name"] for s in br.list()}, 20):
                findings.append("teardown: tmux session gone after DELETE")
            else:
                try:
                    br.close(tmux)  # kills ONLY our own session
                    findings.append("teardown: DELETE left the tmux session "
                                    "alive; closed it directly")
                except Exception as e:  # noqa: BLE001
                    findings.append(f"teardown: direct close failed: {e}")
        _write_verdict_findings(findings)
