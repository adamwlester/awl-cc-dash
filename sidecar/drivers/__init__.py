"""Session drivers for the AWL sidecar.

The dashboard is built around the `bridge` driver (a real Claude Code TUI in
tmux/WSL2) — that is the primary, intended path and the default when no driver
is named (see below). The `sdk` driver (in-process Claude Agent SDK) is a
backup / limited-use engine reserved for specific non-interactive tasks; it is
never the implicit default — select it explicitly.

`create_driver()` picks the implementation. Selection order:
  1. explicit `driver_name` argument (e.g. from the create-session request),
  2. the `AWL_DRIVER` environment variable,
  3. default `"bridge"` when neither is set.

(An explicitly-named *unknown* driver still falls back to `sdk` rather than
crashing the session — see `create_driver`. This is the error path, not the
"nothing named" path, which now lands on `bridge`.)

Driver modules are imported lazily so selecting `sdk` never imports the bridge
(and vice-versa) — each has different runtime requirements.
"""

from __future__ import annotations

import os

from .base import AgentDriver, DriverConfig, EventCallback

__all__ = ["AgentDriver", "DriverConfig", "EventCallback", "create_driver", "default_driver_name"]


def default_driver_name() -> str:
    # `"bridge"` is the default when no driver is named: the product is built
    # around the `bridge` driver (a real Claude Code TUI in tmux/WSL2), so an
    # unnamed session runs on it. `sdk` is the in-process backup / limited-use
    # engine reserved for specific non-interactive tasks — select it explicitly
    # with `AWL_DRIVER=sdk` or the per-session `driver` field.
    return (os.environ.get("AWL_DRIVER") or "bridge").strip().lower()


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
