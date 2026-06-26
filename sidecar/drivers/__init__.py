"""Session drivers for the AWL sidecar.

The dashboard is built around the `bridge` driver (a real Claude Code TUI in
tmux/WSL2) — that is the primary, intended path. The `sdk` driver (in-process
Claude Agent SDK) is a backup / limited-use engine, and is also what
`create_driver()` lands on when no driver is named (see below): it's the
code-level fallback, not the strategic default.

`create_driver()` picks the implementation. Selection order:
  1. explicit `driver_name` argument (e.g. from the create-session request),
  2. the `AWL_DRIVER` environment variable,
  3. fallback `"sdk"` (the in-process Claude Agent SDK path) when neither is set.

Driver modules are imported lazily so selecting `sdk` never imports the bridge
(and vice-versa) — each has different runtime requirements.
"""

from __future__ import annotations

import os

from .base import AgentDriver, DriverConfig, EventCallback

__all__ = ["AgentDriver", "DriverConfig", "EventCallback", "create_driver", "default_driver_name"]


def default_driver_name() -> str:
    # `"sdk"` here is the no-driver-named *fallback*, not the strategic default:
    # the product is built around the `bridge` driver (set AWL_DRIVER=bridge to
    # use it). It stays `sdk` so the working-MVP UI keeps running even without a
    # WSL2/tmux environment.
    return (os.environ.get("AWL_DRIVER") or "sdk").strip().lower()


def create_driver(
    config: DriverConfig,
    on_event: EventCallback,
    driver_name: str | None = None,
) -> AgentDriver:
    name = (driver_name or default_driver_name()).lower()
    if name == "bridge":
        from .bridge import BridgeDriver
        return BridgeDriver(config, on_event)
    if name not in ("sdk", "", None):
        # Unknown driver — fall back to sdk rather than crash the session.
        import logging
        logging.getLogger("awl-sidecar").warning(
            "Unknown AWL_DRIVER %r; falling back to 'sdk'", name
        )
    from .sdk import SDKDriver
    return SDKDriver(config, on_event)
