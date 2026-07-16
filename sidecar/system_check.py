"""System-check aggregation (§11 #49) — one honest JSON over the EXISTING probes.

The pieces already exist — the §7.2 tmux/WSL liveness probe (the ~10 s System
`infra` card loop rides the same raising ``TmuxBridge.ping`` — ``list`` folds
outages into "zero sessions" and cannot signal one), the console-attach
ttyd resolution, the §11 #33 split-source account/auth read
(:func:`settings_io.account_band_split`), and the driver capability sets. This
module composes them into ``GET /system-check`` (see ``main.py``): each check
is ``{"status": "ok" | "fail" | "skipped", "detail": str}`` — *skipped* means
"could not honestly probe" (e.g. no creds file found, WSL unreachable so ttyd
can't be resolved), never a quiet pass — and the aggregate ``ok`` is true only
when NO check failed (skipped checks don't fail the aggregate; they're visible
in the payload).

Every check takes its probe as an injected callable/value, so the unit tier
tests them hermetically (no WSL/tmux/network) while ``main.py`` binds the real
ones. The easy-run half of §11 #49 is the product-shipped agent definition at
``assets/agents/system-check.md``, which drives this endpoint.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import settings_io

STATUSES = ("ok", "fail", "skipped")


def result(status: str, detail: str) -> dict[str, str]:
    """One check result — ``{"status", "detail"}`` with a validated status."""
    if status not in STATUSES:
        raise ValueError(f"status must be one of {STATUSES}, not {status!r}")
    return {"status": status, "detail": str(detail)}


def ok_result(detail: str) -> dict[str, str]:
    return result("ok", detail)


def fail_result(detail: str) -> dict[str, str]:
    return result("fail", detail)


def skipped_result(detail: str) -> dict[str, str]:
    return result("skipped", detail)


def check_tmux(list_sessions: Callable[[], Any]) -> dict[str, str]:
    """tmux/WSL2 backbone liveness — the same signal the §7.2 probe loop rides.

    ``list_sessions`` is the probe and MUST raise on a real outage. The bare
    registry-bridge ``list`` does NOT satisfy that contract — it deliberately
    folds every failure into "zero sessions", so a dead WSL would read as ok —
    which is why ``main.py`` binds a probe that calls the raising
    ``TmuxBridge.ping`` first and only then reads the session list.
    """
    try:
        sessions = list_sessions()
    except Exception as e:
        return fail_result(f"tmux/WSL2 unreachable: {e}")
    try:
        count = len(sessions)
    except TypeError:
        count = 0
    return ok_result(f"tmux answers ({count} live tmux session(s))")


def check_ttyd(resolve_ttyd: Callable[[], Any]) -> dict[str, str]:
    """ttyd presence in WSL — the §11 #29 console streaming-attach dependency.

    ``resolve_ttyd`` is ``TmuxBridge.resolve_ttyd`` (absolute path or None).
    A raising probe (WSL itself unreachable) is *skipped*, not failed — the
    tmux check already reports that outage; double-failing one cause would lie
    about how many things are broken.
    """
    try:
        path = resolve_ttyd()
    except Exception as e:
        return skipped_result(f"could not probe ttyd (WSL unreachable?): {e}")
    if path:
        return ok_result(f"ttyd installed at {path}")
    return fail_result(
        "ttyd not installed in WSL — console streaming attach unavailable")


def default_auth_candidates() -> list[tuple[str, str]]:
    """Well-known ``(claude_json_path, creds_path)`` pairs to try, in order.

    Windows-side ``~/.claude.json`` + ``~/.claude/.credentials.json`` first,
    then the WSL-side pair over the ``\\\\wsl.localhost`` UNC bridge (built from
    ``bridge.paths.WSL_HOME`` when the bridge package is importable — it is at
    sidecar runtime; best-effort otherwise). The check degrades to *skipped*
    when none of the files exist.
    """
    home = Path.home()
    candidates = [(str(home / ".claude.json"),
                   str(home / ".claude" / ".credentials.json"))]
    try:
        import sys as _sys
        repo_root = str(Path(__file__).resolve().parents[1])
        if repo_root not in _sys.path:
            _sys.path.insert(0, repo_root)
        from bridge.paths import WSL_HOME  # type: ignore[import-not-found]
        unc = Path(r"\\wsl.localhost\Ubuntu") / WSL_HOME.lstrip("/")
        candidates.append((str(unc / ".claude.json"),
                           str(unc / ".claude" / ".credentials.json")))
    except Exception:  # pragma: no cover - bridge package unavailable
        pass
    return candidates


def check_auth(candidates: list[tuple[str, str]],
               read_band: Callable[[str, str], dict] | None = None
               ) -> dict[str, str]:
    """Account/auth read via the §11 #33 split-source reader (read-only).

    Tries each ``(claude_json_path, creds_path)`` candidate whose files exist
    (either of the pair). First candidate yielding an account identity → ok
    with email/plan/auth-expiry in the detail. Files found but none readable
    as an account → fail (something is there and it doesn't parse — worth
    surfacing). No candidate files at all → skipped (nothing to probe; the
    agents may still auth via the env-var token path, §6.4).
    """
    read_band = read_band or settings_io.account_band_split
    tried: list[str] = []
    for claude_json, creds in candidates:
        try:
            exists = Path(creds).is_file() or Path(claude_json).is_file()
        except OSError:  # pragma: no cover - unreachable UNC path etc.
            exists = False
        if not exists:
            continue
        tried.append(creds)
        try:
            band = read_band(claude_json, creds)
        except Exception as e:  # pragma: no cover - reader is tolerant by design
            return fail_result(f"account read failed on {creds}: {e}")
        if band.get("signed_out"):
            continue
        email = band.get("email") or "unknown account"
        plan = band.get("plan") or "plan unknown"
        expiry = band.get("auth_expiry") or "no expiry recorded"
        return ok_result(f"signed in as {email} ({plan}); "
                         f"auth expiry: {expiry}")
    if tried:
        return fail_result(
            f"credentials present but no account identity readable "
            f"(tried: {', '.join(tried)})")
    return skipped_result(
        "no local Claude credentials file found to read (agents may still "
        "authenticate via the CLAUDE_CODE_OAUTH_TOKEN env path)")


def check_drivers(default_name: str,
                  capability_map: dict[str, Any]) -> dict[str, str]:
    """Driver availability + capabilities.

    ``capability_map`` maps driver name → a capability list (available) or a
    ``{"unavailable": <reason>}`` dict (import/instantiation failed). Fails
    only when the DEFAULT driver is unavailable — a missing opt-in backup
    engine is stated in the detail, not a system failure.
    """
    parts: list[str] = []
    default_available = False
    for name, caps in capability_map.items():
        if isinstance(caps, dict) and "unavailable" in caps:
            parts.append(f"{name}: unavailable ({caps['unavailable']})")
        else:
            if name == default_name:
                default_available = True
            listed = ", ".join(str(c) for c in caps)
            parts.append(f"{name}: {listed}")
    detail = f"default driver '{default_name}'; " + "; ".join(parts)
    if not default_available:
        return fail_result(detail)
    return ok_result(detail)


def aggregate(checks: dict[str, dict[str, str]]) -> dict[str, Any]:
    """Fold the named checks into the endpoint payload.

    ``ok`` is true only when no check has ``status == "fail"`` — a *skipped*
    check never fails the aggregate (it is an honest "couldn't probe", visible
    in the payload for the operator to judge).
    """
    return {
        "ok": all(c.get("status") != "fail" for c in checks.values()),
        "checks": checks,
        "generated_at": datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"),
    }
