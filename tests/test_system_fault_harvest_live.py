"""System-wide fault detection — the *harvest half* spike (§10 #16).

Establishes, for each of the three **non-deterministic** system faults behind the
fleet-wide "System" Error card (docs/ARCHITECTURE.md §7.2 / §7.8), whether a
**reliable, machine-readable signal** exists that the sidecar could key a detector
on. Scope is the HARVEST HALF only — the deterministic tmux/WSL/sidecar-liveness
probes are ordinary build (body §5/§7), NOT spiked here.

This is a spike-or-omit task: per fault, the honest deliverable is either "here is
the concrete signal (matcher + source)" or "no reliable signal — surface
best-effort or omit." A confirmed negative is a finding, not a failure. Signals
found on the installed build (Claude Code 2.1.198):

  * Rate/usage-cap  — PARTIAL. The existing `inbox.classify_error` `rate_limit`
    regex reliably matches API-429-shaped copy (429 / rate limit / quota exceeded
    / too many requests) and `bridge.read()` surfaces such a line off a live pane
    (proven end-to-end below). BUT the CLI's *subscription* cap copy uses "usage
    limit" wording (live-observed banner: "weekly usage limit"), which the current
    regex does NOT match — FINDING: a detector must add a `usage limit reached`
    pattern. `claudeAiOauth.rateLimitTier` also exists in creds (proactive tier
    hint, not a cap-hit event).
  * Auth expiry    — POSITIVE (proactive creds signal). `claudeAiOauth.expiresAt`
    is a machine-readable Unix-ms timestamp in ~/.claude/.credentials.json that
    the sidecar can read read-only and compare to now. The reactive screen signal
    (re-login prompt) is a secondary candidate but is not provokable without
    expiring real auth, so it is recorded as unconfirmed-live, not asserted.
  * MCP outage     — POSITIVE (live-provoked). A bogus/unreachable MCP server
    surfaces in the `/mcp` panel as "<server> · ✘ failed" — a stable failure
    token a detector can match.

============================================================================
ISOLATION RULES (parallel-safe — sibling agents may be running their OWN live
bridge sessions at the same time; violating any of these can kill their work):
  * ONE new file only — this file. No other test file is touched.
  * We instantiate our OWN `TmuxBridge()` (the `sysfault_bridge` fixture) and NEVER
    use conftest's shared `bridge` fixture — that fixture's setup AND teardown both
    call `_kill_all_tmux()` (= `tmux kill-server`), which would kill every sibling
    agent's sessions.
  * Every tmux session is uniquely named `sysfault-<uuid8>` (never a fixed/shared
    name) and is torn down individually via `close()` / `kill-session -t <name>`.
    We NEVER call `tmux kill-server` (directly or via any helper).
  * The bogus MCP server is scoped to OUR agent only, via `create(mcp_config=…)`
    which launches with `--mcp-config <our-file> --strict-mcp-config` — it never
    touches a shared/global MCP registry other agents inherit.
  * We NEVER expire, exhaust, or tamper with the real account/auth. The auth and
    rate-cap tests are observation/sample tests; creds are read READ-ONLY and
    token values are never logged.
  * Sessions stay TAB-LESS: created with show=False; show()/show=True is never used.

Run (from repo root, ONLY this file — not the whole live tier)::

    .\\.venv\\Scripts\\python.exe -m pytest tests\\test_system_fault_harvest_live.py -m integration
    #  or:  tests\\run.ps1 tests\\test_system_fault_harvest_live.py -m integration
"""
from __future__ import annotations

import json
import logging
import shlex
import time
import uuid
from pathlib import Path
import sys

import pytest

# Make the sidecar's modules importable as top-level (it runs with its own dir on
# sys.path, not the repo root) — same shim as tests/test_bridge_finisher_live.py.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SIDECAR = _REPO_ROOT / "sidecar"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))

from bridge import TmuxBridge  # noqa: E402
import inbox  # noqa: E402  (sidecar/inbox.py — the error classifier)
import settings_io  # noqa: E402  (sidecar/settings_io.py — the creds read-path)

log = logging.getLogger(__name__)

pytestmark = [pytest.mark.integration, pytest.mark.slow]

# WSL path to the agent's real OAuth credentials (read READ-ONLY; never mutated).
_WSL_CREDS = "~/.claude/.credentials.json"


@pytest.fixture
def sysfault_bridge():
    """Our OWN TmuxBridge — deliberately NOT conftest's shared `bridge` fixture,
    whose kill-server teardown would nuke sibling agents' sessions. Construction
    has no side effects; teardown does nothing destructive (each test tears down
    only its own uniquely-named session)."""
    return TmuxBridge()


def _uniq(slug: str) -> str:
    return f"sysfault-{slug}-{uuid.uuid4().hex[:8]}"


# ============================================================================
# Fault 1 — Account rate / usage cap
# ============================================================================

def test_rate_cap_signal_classifier(sysfault_bridge):
    """The existing `inbox.classify_error` `rate_limit` regex matches API-429-shaped
    cap copy and NOT benign lines; a cap-shaped line placed on a live pane is
    recoverable via `bridge.read()` and classifies. FINDING: the CLI's subscription
    "usage limit" copy is NOT matched by the current regex — the matcher needs a
    `usage limit reached` pattern added for a real subscription-cap detector."""
    bridge = sysfault_bridge

    # (a) API-429-shaped cap copy → classifier fires with subtype rate_limit.
    api_cap_samples = [
        "API Error: 429 Too Many Requests",
        "rate_limit_error: rate limit exceeded, please retry later",
        "Error: quota exceeded for this request",
        "429 too many requests",
        "Anthropic API returned rate limit (429)",
    ]
    for s in api_cap_samples:
        res = inbox.classify_error(s)
        assert res is not None and res["subtype"] == "rate_limit", (
            f"classifier missed an API-429-shaped cap line: {s!r} -> {res!r}"
        )
        log.debug("rate_cap: API-shaped match OK  %r -> %s", s, res["subtype"])

    # (b) Clearly-benign lines → no false positive.
    benign = [
        "Reply with exactly: SYSFAULT_OK",
        "Set model to sonnet",
        "Percolating… (esc to interrupt)",
        "Created file approve.txt containing banana",
    ]
    for s in benign:
        assert inbox.classify_error(s) is None, f"false positive on benign line: {s!r}"

    # (c) FINDING — the CLI's *subscription* cap copy uses "usage limit" wording,
    #     which the current regex does NOT match. Live-observed banner on this
    #     build: "…weekly usage limit…". A subscription-cap detector needs this.
    subscription_cap_copy = [
        "Claude usage limit reached. Your limit will reset at 4pm (America/New_York).",
        "You've hit your weekly usage limit for Sonnet.",
        "up to 50% of your plan's weekly usage limit",
    ]
    unmatched = [c for c in subscription_cap_copy if inbox.classify_error(c) is None]
    assert unmatched == subscription_cap_copy, (
        "expected the current rate_limit regex to MISS all subscription 'usage "
        f"limit' copy (documenting the gap); some matched: {unmatched!r}"
    )
    log.debug(
        "rate_cap FINDING: current inbox rate_limit regex does NOT match the CLI's "
        "subscription cap copy %r. Detector must ADD a pattern e.g. "
        r"re.compile(r'\b(usage limit (reached|exceeded)|weekly usage limit)\b', re.I). "
        "Also note brittleness: the existing regex false-fires on 'rate_limit' "
        "appearing in a filename/skill name (word 'rate limit' out of error context).",
        subscription_cap_copy,
    )

    # (d) Live read-back — a cap-shaped line on a live pane is recoverable via
    #     bridge.read() and classifies. A RAW bash pane (no LLM turn) is enough:
    #     it proves read()->classify() carries a cap line end-to-end.
    name = _uniq("cap")
    capline = "API rate limit exceeded: 429 too many requests"
    inner = f"printf '%s\\n' {shlex.quote(capline)}; sleep 600"
    bridge._run(f"tmux new-session -d -s {shlex.quote(name)} {shlex.quote(inner)}")
    try:
        content = ""
        for _ in range(20):
            content = bridge.read(name, lines=20)["content"]
            if capline in content:
                break
            time.sleep(0.5)
        assert capline in content, f"cap line never surfaced on pane read: {content!r}"
        classified = inbox.classify_error(content)
        assert classified is not None and classified["subtype"] == "rate_limit", (
            f"read-back pane text did not classify as rate_limit: {classified!r}"
        )
        log.debug(
            "rate_cap: live read-back OK — bridge.read() surfaced the cap line and "
            "inbox.classify_error classified it as %s. Detector (API-429 layer): "
            "scan pane/transcript text with inbox._ERROR_PATTERNS['rate_limit'].",
            classified["subtype"],
        )
    finally:
        try:
            bridge._run(f"tmux kill-session -t {shlex.quote(name)}")
        except Exception:
            pass


# ============================================================================
# Fault 2 — Auth expiry
# ============================================================================

def test_auth_expiry_signal(sysfault_bridge, tmp_path):
    """Probe the two candidate auth-expiry signals. PROACTIVE creds signal
    (primary): `claudeAiOauth.expiresAt` is a machine-readable Unix-ms timestamp in
    the real creds file — read it READ-ONLY and confirm it is present + usable, and
    prove the sidecar's `settings_io` read-path traverses the `claudeAiOauth`
    wrapper. REACTIVE screen signal (secondary): recorded as a candidate but NOT
    provoked (we never expire real auth). Never logs token values."""
    bridge = sysfault_bridge

    # --- (a) PROACTIVE: real creds carry a readable expiry timestamp. -----------
    raw = bridge._run(f"cat {_WSL_CREDS} 2>/dev/null || echo __MISSING__")
    if raw.strip() == "__MISSING__" or not raw.strip():
        # Signed-out / no creds on this host: record the absence as a finding
        # rather than fabricate a signal.
        log.debug("auth_expiry FINDING: no creds file at %s (signed out?) — the "
                  "proactive expiry signal is unavailable on this host.", _WSL_CREDS)
        pytest.skip(f"no creds at {_WSL_CREDS} — proactive auth signal unavailable")

    creds = json.loads(raw)
    # Mirror settings_io's wrapper-traversal (_NEST_KEYS already includes
    # 'claudeAiOauth') to locate the OAuth object without hardcoding one spelling.
    oauth = {}
    for key in settings_io._NEST_KEYS:
        nested = creds.get(key)
        if isinstance(nested, dict):
            oauth = nested
            break
    expires_at = oauth.get("expiresAt", creds.get("expiresAt"))
    assert expires_at is not None, (
        "no expiresAt in creds — proactive auth-expiry detection would be "
        "infeasible on this build (record as finding)"
    )
    assert isinstance(expires_at, (int, float)), (
        f"expiresAt is not a numeric timestamp: {type(expires_at).__name__}"
    )
    # Unix-ms in this build (~13 digits). Compare to now for expiry.
    now_ms = time.time() * 1000
    hours_left = (expires_at - now_ms) / 3_600_000
    state = "EXPIRED" if expires_at <= now_ms else "valid"
    log.debug(
        "auth_expiry: PROACTIVE signal present — claudeAiOauth.expiresAt=%s "
        "(Unix-ms) is %s, ~%.1fh from now. Detector: read %s read-only, compare "
        "expiresAt to now (warn within a window, raise System card when past). "
        "subscriptionType=%r rateLimitTier present=%s. (token values NOT logged.)",
        expires_at, state, hours_left, _WSL_CREDS,
        oauth.get("subscriptionType"), "rateLimitTier" in oauth,
    )

    # --- (b) Prove the sidecar's read-path on a SYNTHETIC creds file (no secrets).
    synth = tmp_path / "creds.json"
    synth.write_text(json.dumps({
        "claudeAiOauth": {
            "email": "probe@example.com",
            "subscriptionType": "max",
            "expiresAt": int(now_ms) + 3_600_000,
        }
    }), encoding="utf-8")
    band = settings_io.account_band(str(synth))
    assert band.get("email") == "probe@example.com", (
        f"settings_io.account_band failed to read the claudeAiOauth wrapper: {band!r}"
    )
    assert band.get("plan") == "max", f"plan not read from wrapper: {band!r}"
    # And confirm a sibling expiry-extractor (the harvest detector's new read) finds
    # the timestamp via the same read_json + wrapper traversal.
    doc = settings_io.read_json(str(synth))
    got = (doc.get("claudeAiOauth") or {}).get("expiresAt")
    assert isinstance(got, (int, float)) and got > now_ms, got
    log.debug(
        "auth_expiry: sidecar read-path OK — account_band() reads the wrapper; a "
        "harvest detector adds a creds_expiry() reading claudeAiOauth.expiresAt via "
        "the same read_json path. NOTE: account_band() itself surfaces only "
        "email/org/plan today — expiry needs a small sibling reader (build item)."
    )

    # --- (c) REACTIVE screen signal — candidate, NOT provoked. ------------------
    log.debug(
        "auth_expiry FINDING (secondary): a reactive screen signal (a re-login / "
        "'session expired' / OAuth-refresh prompt) is a plausible candidate but is "
        "NOT provokable without expiring real auth, so it is left unconfirmed on "
        "this build. The PROACTIVE creds-timestamp read above is the reliable "
        "detector; the screen signal would be a best-effort supplement."
    )


# ============================================================================
# Fault 3 — Global MCP outage (the provokable one)
# ============================================================================

def test_mcp_outage_signal_live(sysfault_bridge):
    """Provoke live: spawn a tab-less, uniquely-named session configured with a
    deliberately unreachable MCP server (scoped to OUR agent via --mcp-config
    --strict-mcp-config), open the `/mcp` panel, and read back how the outage
    surfaces. Assert a machine-readable failure signal exists."""
    bridge = sysfault_bridge
    name = _uniq("mcp")
    diag = f"/home/lester/awl-sysfault-{uuid.uuid4().hex[:8]}"
    server_key = "awl_sysfault_bogus"
    bogus_mcp = {"mcpServers": {server_key: {
        "type": "stdio",
        "command": "/nonexistent/awl-sysfault-bogus-mcp-binary",
        "args": [],
    }}}

    bridge._run(f"mkdir -p {shlex.quote(diag)}")
    try:
        info = bridge.create(name, cwd=diag, show=False, mcp_config=bogus_mcp)
        log.debug("mcp_outage: created tab-less session %s (sid=%s) with bogus MCP "
                  "server scoped via --strict-mcp-config", name, info.get("session_id"))

        # Open the MCP manager panel and read it back.
        bridge.send(name, "/mcp")
        content = ""
        found = False
        for _ in range(30):  # up to ~15s for the panel to render
            content = bridge.read(name, lines=50)["content"]
            if server_key in content and "failed" in content.lower():
                found = True
                break
            time.sleep(0.5)

        assert found, (
            "no machine-readable MCP-outage signal in the /mcp panel; last read:\n"
            + content[-800:]
        )
        # Characterize the exact matcher for the detector.
        has_glyph = ("✘" in content) or ("✗" in content) or ("×" in content)
        log.debug(
            "mcp_outage: SIGNAL CONFIRMED live — /mcp panel shows the bogus server "
            "as failed (server_key=%r present, 'failed' token present, cross-glyph "
            "present=%s). Detector: open/parse `/mcp` (or its data) and match a "
            "server row carrying a failure token — regex candidate "
            r"re.compile(r'(✘|✗|×)\s*failed|\bfailed\b', re.I) on the server line. "
            "Note inbox.classify_error already has a `tool_mcp` pattern for "
            "'mcp … fail/error' in transcript text as a complementary source.",
            server_key, has_glyph,
        )
    finally:
        try:
            bridge.close(name)
        except Exception as e:
            log.debug("mcp_outage: close(%s) raised (non-fatal): %s", name, e)
        try:
            bridge._run(f"rm -rf {shlex.quote(diag)}")
        except Exception:
            pass
