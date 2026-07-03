r"""Usage & context DATA-SOURCE probe — live, under the bridge (§10 #18 + #21).

Spike-or-confirm. One live session (plus a creds-only probe) that inspects every
candidate data source the dashboard's context + usage readouts depend on, and
records — per source — exactly what it delivers on THIS Claude Code build:

  * #18 — does a configured **statusLine** expose a machine-readable
    ``context_window`` (``context_window_size`` / ``used_percentage``) value, and
    is it observable **mid-run** (while the agent is still generating) or only at
    turn boundaries? DESIGN asserts context "can't be read mid-run"; this tests
    that empirically. (``test_18_statusline_context_window_midrun``)
  * #21 — what **account identity** the local creds actually yield via
    ``settings_io.account_band`` (email / org / plan), and what **usage / limits**
    any reachable surface (transcript, the TUI ``/usage`` command, creds tier
    labels) actually provides. (``test_21_account_band_from_creds`` +
    ``test_21_usage_limits_surface``)

A confirmed ABSENCE is a finding, not a failure — it sets an honest data boundary
the Usage/context UI must respect. We never assert a value we supplied; every
assertion reads back from the live source.

Run (single file, isolation)::

    .\.venv\Scripts\python.exe -m pytest tests\test_usage_context_sources_live.py -m integration

=============================================================================
ISOLATION RULES (parallel-safe — sibling agents may run their own live bridge
sessions AT THE SAME TIME; violating any of these can kill their work):
  * ONE new file only — this file. No other test file is touched.
  * Uniquely-named tmux session — prefixed with the slug: ``usagesrc-<uuid8>``.
    Never a fixed/shared name.
  * We instantiate our OWN ``TmuxBridge()`` — NOT conftest's session-scoped
    ``bridge`` fixture, whose setup AND teardown call ``tmux kill-server`` (would
    kill every sibling agent's sessions). Teardown here closes ONLY our own
    uniquely-named session via ``close(name)`` + removes our own diag dir.
  * NEVER ``tmux kill-server`` (directly or via any helper).
  * Creds are READ-ONLY — we never write, re-auth, or delete any credential file.
    (For the WSL agents' creds we read only KEY NAMES via a WSL one-liner — never
    copy token values to Windows disk.)
  * Any statusLine config is scoped to OUR agent only (its own ``--settings`` file
    in our per-agent diag dir), never a shared/global config.
  * Bridge sessions stay TAB-LESS — created with ``show=False``; never ``show()``.
  * Run ONLY this file in isolation — not the whole live tier.
  * Shared files (conftest.py, pyproject.toml, tests/README.md, global settings)
    are NOT edited.
=============================================================================
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import sys
import time
import uuid
from pathlib import Path

import pytest

# The sidecar runs with its own dir on sys.path (not the repo root), so add both:
# the repo root makes the `bridge` package importable; the sidecar dir makes
# `settings_io` / `drivers.bridge` importable — exactly the finisher's shim.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SIDECAR = _REPO_ROOT / "sidecar"
for _p in (_REPO_ROOT, _SIDECAR):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from bridge import TmuxBridge  # noqa: E402
import settings_io  # noqa: E402
from drivers.bridge import derive_context_usage  # noqa: E402

log = logging.getLogger(__name__)

pytestmark = [pytest.mark.integration, pytest.mark.slow]

SLUG = "usagesrc"

# The sidecar (Windows) reads these as its "local creds" for the account band.
WIN_CLAUDE_JSON = r"C:\Users\lester\.claude.json"
WIN_CREDENTIALS = r"C:\Users\lester\.claude\.credentials.json"
# The bridge AGENTS authenticate in WSL — recorded as a secondary (informational)
# source; probed by key-name only, never copied.
WSL_CLAUDE_JSON = "/home/lester/.claude.json"
WSL_CREDENTIALS = "/home/lester/.claude/.credentials.json"

# A short warmup turn establishes a NON-None context baseline (a real
# used_percentage), so a stale-vs-fresh mid-run comparison is unambiguous.
WARMUP_PROMPT = "Reply with exactly: WARMUP-OK"

# A generating turn long enough to sample the statusLine MANY times mid-run, with
# NO tools (so no permission prompt pauses it in default mode). A long creative
# write reliably streams for many seconds (models comply, unlike tedious counting
# busywork which they tend to short-circuit), giving a real generating window.
LONG_PROMPT = (
    "Do NOT use any tools. Write a vivid, richly detailed short story of about "
    "700 words about a lighthouse keeper who discovers a message in a bottle. "
    "Use long descriptive paragraphs. Write the full story in one response."
)


# -----------------------------------------------------------------------------
# Small read-only WSL / parsing helpers
# -----------------------------------------------------------------------------

def _cat(bridge: TmuxBridge, path: str) -> str:
    """Read a WSL file's contents (empty string if missing). Read-only."""
    try:
        return bridge._run(f"cat '{path}' 2>/dev/null || true", timeout=15)
    except Exception:
        return ""


def _count_lines(bridge: TmuxBridge, path: str) -> int:
    """Count lines in a WSL file (0 if missing). Used to detect statusLine fires."""
    out = ""
    try:
        out = bridge._run(f"wc -l < '{path}' 2>/dev/null || echo 0", timeout=10)
    except Exception:
        return 0
    m = re.search(r"\d+", out or "")
    return int(m.group(0)) if m else 0


def _find_ctx_window(payload) -> dict | None:
    """Locate the statusLine ``context_window`` object in a parsed payload.

    Prefers ``payload['context_window']``; falls back to a recursive scan for any
    dict carrying ``context_window_size`` or ``used_percentage`` so a field-name
    or nesting difference on this build is still found (or provably absent).
    """
    if not isinstance(payload, dict):
        return None
    cw = payload.get("context_window")
    if isinstance(cw, dict) and (
        "context_window_size" in cw or "used_percentage" in cw
    ):
        return cw
    found: list[dict] = []

    def walk(o):
        if isinstance(o, dict):
            if "context_window_size" in o or "used_percentage" in o:
                found.append(o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(payload)
    return found[0] if found else None


def _latest_ctx(bridge: TmuxBridge, diag_dir: str):
    """(raw_payload_dict_or_None, ctx_window_dict_or_None) from sl-latest.json.

    Swallows a partial read (statusLine truncate+rewrites the file each fire).
    """
    raw = _cat(bridge, f"{diag_dir}/sl-latest.json")
    if not raw.strip():
        return None, None
    try:
        payload = json.loads(raw)
    except Exception:
        return None, None
    return payload, _find_ctx_window(payload)


# -----------------------------------------------------------------------------
# Fixtures — OUR OWN bridge + ONE uniquely-named, tab-less, statusLine-configured
# session (never conftest's kill-server `bridge` fixture).
# -----------------------------------------------------------------------------

@pytest.fixture(scope="module")
def own_bridge():
    """Our OWN TmuxBridge — no server-wide kill anywhere in its lifecycle."""
    return TmuxBridge()


@pytest.fixture(scope="module")
def probe_session(own_bridge):
    """One tab-less session whose statusLine command captures the piped payload.

    The statusLine ``command`` receives Claude Code's status JSON on stdin each
    time the status bar renders; we ``cat`` it to ``sl-latest.json`` (overwrite),
    append an epoch to ``sl-fires.log`` (one line per fire → mid-run fire count),
    and keep a delimited ``sl-history.log`` for post-hoc analysis. All inside OUR
    per-agent diag dir; passed via ``--settings`` so it is scoped to this agent.
    """
    uid = uuid.uuid4().hex[:8]
    name = f"{SLUG}-{uid}"
    diag = f"/home/lester/awl-{SLUG}-{uid}"
    own_bridge._run(f"mkdir -p {diag}")

    # Single-line shell command (JSON-encoded into the --settings file, then run
    # by Claude Code's shell). date's %3N may print literally under dash — we only
    # COUNT fire lines, never parse the time, so that is harmless.
    sl_cmd = (
        f"d='{diag}'; p=\"$(cat)\"; t=\"$(date +%s.%3N)\"; "
        f"printf '%s' \"$p\" > \"$d/sl-latest.json\"; "
        f"echo \"$t\" >> \"$d/sl-fires.log\"; "
        f"{{ echo \"----8<---- $t\"; printf '%s' \"$p\"; echo; }} >> \"$d/sl-history.log\"; "
        f"echo awl-ctx-probe"
    )
    settings = {"statusLine": {"type": "command", "command": sl_cmd, "padding": 0}}

    log.debug("probe_session create name=%s diag=%s", name, diag)
    own_bridge.create(name, cwd=diag, show=False, settings=settings)
    own_bridge.wait_idle(name, timeout=90, interval=1.0)

    yield {"bridge": own_bridge, "name": name, "diag": diag}

    # Teardown: OUR session + OUR dir only. Never a broad kill.
    try:
        own_bridge.close(name)
    except Exception:
        pass
    try:
        own_bridge._run(f"rm -rf {diag}")
    except Exception:
        pass


# -----------------------------------------------------------------------------
# #18 — statusLine context_window as a live mid-run context source
# -----------------------------------------------------------------------------

def test_18_statusline_context_window_midrun(probe_session):
    """Confirm the statusLine emits a numeric ``context_window_size``, then probe
    whether it is observable/fresh MID-RUN (while status == generating)."""
    b: TmuxBridge = probe_session["bridge"]
    name = probe_session["name"]
    diag = probe_session["diag"]

    # (1) SOURCE confirmation — after the session reached idle the statusLine has
    # fired at least once; its payload must carry a numeric context_window_size.
    idle_payload, idle_ctx = None, None
    for _ in range(20):  # allow a couple seconds for the first fire to land
        idle_payload, idle_ctx = _latest_ctx(b, diag)
        if idle_ctx is not None:
            break
        time.sleep(0.5)
    assert idle_payload is not None, (
        "statusLine command never wrote sl-latest.json — check the statusLine "
        "schema (settings.statusLine.type/command) on this build."
    )
    log.debug("#18 idle payload top-level keys: %s", sorted(idle_payload.keys()))
    assert idle_ctx is not None, (
        f"no context_window object in statusLine payload; top-level keys="
        f"{sorted(idle_payload.keys())}"
    )
    size = idle_ctx.get("context_window_size")
    log.info("#18 statusLine context_window (idle) = %s", idle_ctx)
    assert isinstance(size, (int, float)) and size > 0, (
        f"context_window_size not present/numeric: {idle_ctx!r}"
    )

    # (1b) Warmup turn → a real, non-None context baseline (used_percentage), so
    # the mid-run staleness check has an unambiguous prior value to compare to.
    b.send(name, WARMUP_PROMPT)
    try:
        b.wait_idle(name, timeout=90, interval=1.0)
    except Exception as e:
        log.warning("#18 warmup wait_idle: %s", e)
    time.sleep(1.0)  # let the turn-boundary statusLine fire land
    _, base_ctx = _latest_ctx(b, diag)
    base_used = (base_ctx or {}).get("used_percentage")
    log.info("#18 baseline context_window (post-warmup) = %s", base_ctx)

    # (2) MID-RUN probe — drive a long generating turn and sample the statusLine
    # THROUGHOUT the turn. We deliberately do NOT gate on the screen 'generating'
    # heuristic: during long prose streaming the bottom-15-line detector returns
    # 'unknown' (the "esc to interrupt" hint clips at the pane's right edge — see
    # bridge._detect_state's own docstring). The robust, screen-independent signal
    # is the statusLine FIRE COUNT over the whole turn: if the command fires only
    # ~once for a multi-minute generation (at the boundary), the context_window is
    # NOT a live mid-run feed. NOTE: used_percentage is INPUT-only (per the Usage
    # research), so an output-heavy turn won't move it even at the boundary — the
    # fire count, not the percentage, is the discriminating signal.
    def _last_assistant() -> tuple[int, int]:
        """(char-length of the last main-line assistant text, assistant count).

        Screen-independent turn tracking: the story's completion is detected by a
        genuinely long assistant message landing in the transcript — no reliance
        on the prose-flaky screen 'generating'/'idle' heuristic.
        """
        try:
            entries = b.read_log(name)
        except Exception:
            return -1, -1
        texts = []
        for e in entries:
            if e.get("type") == "assistant" and not e.get("isSidechain"):
                for blk in (e.get("message") or {}).get("content") or []:
                    if isinstance(blk, dict) and blk.get("type") == "text":
                        texts.append(blk.get("text") or "")
        return (len(texts[-1]) if texts else 0), len(texts)

    base_len, base_count = _last_assistant()
    fires_before = _count_lines(b, f"{diag}/sl-fires.log")
    b.send(name, LONG_PROMPT)

    samples: list[dict] = []
    fired_during_turn = False       # statusLine fired again after the turn started
    numeric_size_during_turn = False    # numeric context_window_size readable in-turn
    used_values: set = set()        # distinct used_percentage seen across the turn
    turn_complete = False
    story_len = 0
    prev_len = -1
    stable = 0
    start = time.time()
    deadline = start + 240
    while time.time() < deadline:
        fires_now = _count_lines(b, f"{diag}/sl-fires.log")
        _, ctx = _latest_ctx(b, diag)
        up = ctx.get("used_percentage") if ctx else None
        cw_size = ctx.get("context_window_size") if ctx else None
        cur_len, cur_count = _last_assistant()
        samples.append({
            "t": round(time.time() - start, 1), "fires": fires_now,
            "used_percentage": up, "context_window_size": cw_size,
            "last_assistant_len": cur_len, "assistant_count": cur_count,
        })
        if fires_now > fires_before:
            fired_during_turn = True
        if isinstance(cw_size, (int, float)) and cw_size > 0:
            numeric_size_during_turn = True
        if up is not None:
            used_values.add(up)
        # Completion: a NEW, long assistant message (the story, >500 chars) has
        # landed and stopped growing for two consecutive polls.
        if cur_count > base_count and cur_len > 500:
            if cur_len == prev_len:
                stable += 1
                if stable >= 2:
                    turn_complete = True
                    story_len = cur_len
                    break
            else:
                stable = 0
            prev_len = cur_len
        time.sleep(1.0)

    # Settle and read the final payload (after the boundary statusLine fire).
    try:
        b.wait_idle(name, timeout=120, interval=1.0)
    except Exception as e:
        log.warning("#18 wait_idle after long turn: %s", e)
    time.sleep(1.5)
    final_payload, final_ctx = _latest_ctx(b, diag)

    total_fires = _count_lines(b, f"{diag}/sl-fires.log")
    fires_delta = total_fires - fires_before
    final_out = (final_ctx or {}).get("total_output_tokens")
    log.info(
        "#18 mid-run probe: samples=%d turn_complete=%s story_len=%d "
        "fires_before=%d total_fires=%d fires_delta=%d fired_during_turn=%s "
        "numeric_size_during_turn=%s distinct_used_pct=%s final_output_tokens=%s",
        len(samples), turn_complete, story_len, fires_before, total_fires,
        fires_delta, fired_during_turn, numeric_size_during_turn,
        sorted(used_values), final_out,
    )
    log.debug("#18 mid-run samples: %s", samples)
    log.info("#18 statusLine context_window (final) = %s", final_ctx)

    # ---- Verdict (logged per the prompt; each branch is an honest #18 result) --
    # 'Continuous live feed' would mean many statusLine fires spread across the
    # generation; 'boundary-only' means the fire count barely moves across a long,
    # CONFIRMED multi-hundred-char generation (story_len).
    if fires_delta >= 4:
        verdict = ("MID-RUN CAPABLE: the statusLine fired repeatedly across the "
                   f"turn (fires_delta={fires_delta}, story_len={story_len}) → "
                   "context_window is emitted more than once per turn; a near-live "
                   "mid-run source. Reconcile DESIGN if the values also refresh.")
    else:
        verdict = ("BOUNDARY: across a confirmed long generation (story_len="
                   f"{story_len} chars, final_output_tokens={final_out}) the "
                   f"statusLine fired only {fires_delta} extra time(s) — the "
                   "context_window is a PER-TURN snapshot emitted at the turn "
                   "boundary, NOT a continuous mid-run feed. A numeric "
                   "context_window_size is READABLE at any moment (last-boundary "
                   "value persists), but it does not refresh mid-run. DESIGN's "
                   "'can't read (fresh) mid-run' holds; context stays JSONL/"
                   "`/context`-derived per §10-9.")
    log.info("#18 VERDICT: %s", verdict)

    # ---- Assertions (read back from the live source, never a supplied value) --
    # SOURCE confirmed: the statusLine delivers a numeric context_window_size
    # (idle AND final) — the durable #18 finding regardless of mid-run freshness.
    assert final_ctx is not None and isinstance(
        final_ctx.get("context_window_size"), (int, float)
    ), f"final statusLine payload lost the context_window object: {final_ctx!r}"
    # A real, long turn executed (screen-independent proof): a genuinely long
    # assistant message landed in the transcript. This is what makes the fire-count
    # verdict meaningful — we measured fires across a CONFIRMED long generation.
    assert turn_complete and story_len > 500, (
        f"the long turn did not produce a long response (turn_complete="
        f"{turn_complete}, story_len={story_len}, final_output_tokens={final_out})"
    )
    assert samples, "no samples captured across the turn"
    # 'present and numeric mid-run' — a numeric context_window_size is readable
    # while the turn is in progress (its FRESHNESS is characterized in the verdict
    # above via the fire count, not asserted — either outcome is a valid finding).
    assert numeric_size_during_turn, (
        "no numeric context_window_size was readable during the turn; "
        f"samples={samples}"
    )


# -----------------------------------------------------------------------------
# #21 — account identity from local creds (account_band)
# -----------------------------------------------------------------------------

def test_21_account_band_from_creds(own_bridge):
    """Exercise ``account_band`` against the REAL local creds and record which of
    {email, org, plan} each source actually yields (absences are findings)."""
    results: dict[str, dict] = {}

    # (A) Windows creds — the sidecar's own "local creds".
    for label, path in (("win:.claude.json", WIN_CLAUDE_JSON),
                        ("win:.credentials.json", WIN_CREDENTIALS)):
        if not os.path.exists(path):
            results[label] = {"exists": False, "band": {}}
            continue
        band = settings_io.account_band(path)  # read-only
        # band only ever contains email/org/plan — safe to log (no tokens).
        results[label] = {
            "exists": True, "band": band, "fields": sorted(band.keys()),
        }

    # (B) The tier fields that live in .claude.json's oauthAccount but are NOT
    # matched by account_band._PLAN_FIELDS — the concrete "missing plan" finding.
    tier_fields_unmatched: list[str] = []
    if results["win:.claude.json"]["exists"]:
        try:
            oa = (settings_io.read_json(WIN_CLAUDE_JSON) or {}).get("oauthAccount", {})
            tier_like = [k for k in oa
                         if re.search(r"tier|plan|subscription|billing|seat", k, re.I)]
            matched = set(settings_io._PLAN_FIELDS)
            tier_fields_unmatched = [k for k in tier_like if k not in matched]
            log.info("#21 .claude.json oauthAccount tier-like keys=%s ; "
                     "UNMATCHED by _PLAN_FIELDS=%s", tier_like, tier_fields_unmatched)
        except Exception as e:
            log.warning("#21 oauthAccount tier introspection failed: %s", e)

    # (C) WSL agents' creds — informational, KEY-NAMES ONLY (never copy values).
    wsl_probe = (
        "import json;"
        "d=json.load(open('/home/lester/.claude.json'));"
        "a=d.get('oauthAccount',{}) if isinstance(d,dict) else {};"
        "c=json.load(open('/home/lester/.claude/.credentials.json'));"
        "o=c.get('claudeAiOauth',{}) if isinstance(c,dict) else {};"
        "print(json.dumps({"
        "'claude_json_has_email':'emailAddress' in a,"
        "'claude_json_has_org':'organizationName' in a,"
        "'creds_has_subscriptionType':'subscriptionType' in o,"
        "'creds_has_rateLimitTier':'rateLimitTier' in o}))"
    )
    try:
        raw = own_bridge._run(f"python3 -c {json.dumps(wsl_probe)}", timeout=20)
        results["wsl(keys-only)"] = json.loads(raw.strip().splitlines()[-1])
    except Exception as e:
        results["wsl(keys-only)"] = {"probe_error": str(e)[:120]}

    # Merge the Windows sources — what the account band can show if it reads both.
    merged: dict = {}
    for label in ("win:.claude.json", "win:.credentials.json"):
        merged.update(results[label].get("band", {}))

    log.info("#21 account per-source: %s", results)
    log.info("#21 account MERGED band (across both Windows files): %s", merged)
    single_full = any(
        all(k in r.get("band", {}) for k in ("email", "org", "plan"))
        for r in results.values()
    )
    log.info(
        "#21 VERDICT (account): email+org come from .claude.json oauthAccount "
        "(emailAddress/organizationName); plan comes ONLY from .credentials.json "
        "claudeAiOauth.subscriptionType. No single file yields all three "
        "(single_full=%s). .claude.json's own tier fields %s are NOT surfaced as "
        "'plan' by account_band._PLAN_FIELDS — the Usage UI must read BOTH files "
        "(or _PLAN_FIELDS must be extended).",
        single_full, tier_fields_unmatched or "(none found)",
    )

    # ---- Assertions on what IS present (read back from the real creds) --------
    b1 = results["win:.claude.json"]
    assert b1["exists"], f"{WIN_CLAUDE_JSON} not found"
    assert b1["band"].get("email"), "no email from .claude.json oauthAccount"
    assert "@" in str(b1["band"]["email"]), "email doesn't look like an address"
    assert b1["band"].get("org"), "no org from .claude.json oauthAccount"
    # plan is NOT expected here — record the boundary explicitly.
    assert "plan" not in b1["band"], (
        "unexpected: .claude.json now yields 'plan' — account_band._PLAN_FIELDS "
        "may have changed; update the #21 finding."
    )

    b2 = results["win:.credentials.json"]
    assert b2["exists"], f"{WIN_CREDENTIALS} not found"
    assert b2["band"].get("plan"), "no plan from .credentials.json claudeAiOauth"

    # The merged band covers all three — the account band is fully sourceable,
    # but only across BOTH files (the boundary this test documents).
    assert all(k in merged for k in ("email", "org", "plan")), (
        f"merged account band missing a field: {merged}"
    )
    assert not single_full, (
        "a single creds file now yields email+org+plan — the split-source "
        "boundary changed; update the #21 finding."
    )


# -----------------------------------------------------------------------------
# #21 — usage / limits surface boundary
# -----------------------------------------------------------------------------

def test_21_usage_limits_surface(probe_session):
    """Probe every reachable usage/limits surface and record whether live
    usage/limit NUMBERS are obtainable as structured data, or confirm the honest
    boundary that they are not locally derivable."""
    b: TmuxBridge = probe_session["bridge"]
    name = probe_session["name"]

    # (A) Transcript / driver surface — gives context tokens, NOT account limits.
    entries = b.read_log(name)
    ctx = derive_context_usage(entries)
    log.info("#21 transcript-derived context usage keys=%s (tokens=%s window=%s)",
             sorted(ctx.keys()), ctx.get("tokens"), ctx.get("window"))
    assert "tokens" in ctx and "window" in ctx, (
        "derive_context_usage lost its tokens/window shape"
    )
    limit_keys = [k for k in ctx if re.search(r"limit|reset|quota|remaining", k, re.I)]
    assert not limit_keys, (
        f"transcript unexpectedly exposes limit fields {limit_keys} — the usage "
        "boundary changed; update the #21 finding."
    )

    # (B) TUI `/usage` command surface — human-readable, if it exists on this build.
    b.send(name, "/usage")
    time.sleep(5)
    screen = b.scrollback(name, max_lines=250)["content"]
    usage_rendered = bool(re.search(
        r"usage|limit|resets?|current\s+session|weekly|week|%", screen, re.I,
    ))
    no_such_cmd = bool(re.search(r"no commands? match|unknown command", screen, re.I))
    log.info("#21 /usage: rendered_usage_signal=%s no_such_command=%s",
             usage_rendered, no_such_cmd)
    log.debug("#21 /usage screen tail:\n%s", screen[-1800:])
    # Close any panel `/usage` opened so the session is left clean.
    try:
        b.keys(name, "Escape")
        time.sleep(1)
    except Exception:
        pass

    # (C) Creds tier LABELS — static, not live numbers.
    plan_band = settings_io.account_band(WIN_CREDENTIALS) if os.path.exists(
        WIN_CREDENTIALS) else {}
    log.info("#21 creds tier label (static, not live limits): %s", plan_band)

    # ---- Verdict --------------------------------------------------------------
    log.info(
        "#21 VERDICT (usage/limits): the transcript yields context tokens but NO "
        "limit/reset fields; the TUI `/usage` command is the only surface that "
        "renders usage/limit info (rendered_signal=%s) and it is SCREEN-ONLY "
        "(human-readable, not structured data); creds carry a static tier label "
        "(%s), not live limit numbers. Live usage/limit NUMBERS are NOT locally "
        "derivable as structured data — an honest data boundary for the Usage UI.",
        usage_rendered, plan_band or "(none)",
    )

    # ---- Assertions -----------------------------------------------------------
    # `/usage` was recognized as a command (it rendered a usage view rather than
    # "no commands match"); if this build lacks it, that itself is recorded.
    assert not no_such_cmd, (
        "`/usage` reported 'no commands match' — record that this build has no "
        "/usage command (the finding), not a code bug."
    )
    assert usage_rendered, (
        "`/usage` produced no usage/limit-looking screen text; screen tail was "
        "logged for inspection."
    )
