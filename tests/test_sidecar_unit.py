"""Hermetic unit tests for the sidecar's session bookkeeping.

Pure: no driver, no WSL2/tmux, no model. Feeds plain event dicts through
``SessionState.handle_event`` to prove the permission wiring — a
``permission_request`` event flips ``has_pending_permission`` and stores the
detail; a ``permission_resolved`` event clears it. These carry neither the
``integration`` nor the ``slow`` mark.
"""

import sys
from pathlib import Path

# The sidecar runs with its own dir on sys.path (not the repo root).
_SIDECAR = Path(__file__).resolve().parent.parent / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))

from main import SessionState  # noqa: E402
from drivers import default_driver_name  # noqa: E402


def _session():
    return SessionState(
        session_id="s1", agent_type=None, model=None,
        permission_mode="default", cwd=None, system_prompt=None,
        driver_name="bridge",
    )


def test_permission_request_sets_pending_flag():
    s = _session()
    assert s.to_dict()["has_pending_permission"] is False

    detail = {"question": "Do you want to create x.txt?",
              "options": [{"index": 1, "label": "Yes"}]}
    s.handle_event({"type": "permission_request", "data": detail})

    assert s.pending_permission == detail
    assert s.to_dict()["has_pending_permission"] is True
    # The event is also fanned out to subscribers/history.
    assert s.events[-1]["type"] == "permission_request"


def test_permission_resolved_clears_pending_flag():
    s = _session()
    s.handle_event({"type": "permission_request", "data": {"question": "?"}})
    assert s.pending_permission is not None

    s.handle_event({"type": "permission_resolved"})
    assert s.pending_permission is None
    assert s.to_dict()["has_pending_permission"] is False
    assert s.events[-1]["type"] == "permission_resolved"


def test_status_enum_untouched_by_permission_events():
    # Pending reads off the flag, not a new status value — status stays as-is.
    s = _session()
    s.status = "running"
    s.handle_event({"type": "permission_request", "data": {"question": "?"}})
    assert s.status == "running"
    s.handle_event({"type": "permission_resolved"})
    assert s.status == "running"


# ---------------------------------------------------------------------------
# Default driver selection
#
# Policy: `bridge` is the primary path the dashboard is built around, so an
# unnamed session must run on `bridge`. `sdk` is a reserved, explicit-only
# backup engine. These guard the default (and that explicit `sdk` still works).
# ---------------------------------------------------------------------------

def test_default_driver_is_bridge_when_unset(monkeypatch):
    # Nothing named (no AWL_DRIVER, no per-session driver) -> the primary path.
    monkeypatch.delenv("AWL_DRIVER", raising=False)
    assert default_driver_name() == "bridge"


def test_awl_driver_env_still_selects_sdk(monkeypatch):
    # sdk stays reachable as an explicit choice (case/whitespace tolerant).
    monkeypatch.setenv("AWL_DRIVER", " SDK ")
    assert default_driver_name() == "sdk"


def test_unnamed_session_reports_bridge(monkeypatch):
    # The API surface (to_dict, used by /health and session listing) reports the
    # default for a not-yet-connected session that named no driver.
    monkeypatch.delenv("AWL_DRIVER", raising=False)
    s = SessionState(
        session_id="s2", agent_type=None, model=None,
        permission_mode="default", cwd=None, system_prompt=None,
        driver_name=None,
    )
    assert s.to_dict()["driver"] == "bridge"


def test_explicit_sdk_session_preserved(monkeypatch):
    # Per-session sdk selection is preserved regardless of the default/env.
    monkeypatch.delenv("AWL_DRIVER", raising=False)
    s = SessionState(
        session_id="s3", agent_type=None, model=None,
        permission_mode="default", cwd=None, system_prompt=None,
        driver_name="sdk",
    )
    assert s.to_dict()["driver"] == "sdk"
