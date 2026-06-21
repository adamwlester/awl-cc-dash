"""Shared pytest fixtures and logging setup for workspace-level tests.

Logging: every run writes a timestamped, DEBUG-level file into ``tests/log/``
(in addition to the concise console output configured in ``pyproject.toml``).
That file is the place to look when an integration test fails — it captures the
exact WSL/tmux commands the bridge ran, raw screen captures, and full tracebacks.
"""

import datetime
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

# The tmux bridge package lives at the repo root (`bridge/`). Add the repo root
# to the import path (resolved relative to this file, so cwd doesn't matter).
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from bridge import TmuxBridge  # noqa: E402

LOG_DIR = Path(__file__).parent / "log"


def pytest_configure(config):
    """Route pytest's file logging to a fresh timestamped file per run."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    # Only set if the user didn't pass --log-file explicitly.
    if not getattr(config.option, "log_file", None):
        config.option.log_file = str(LOG_DIR / f"tmux_bridge_{stamp}.log")


def _kill_all_tmux():
    """Best-effort: kill every tmux session in WSL for a clean slate."""
    subprocess.run(
        ["wsl", "-d", "Ubuntu", "--", "bash", "-c", "tmux kill-server 2>/dev/null || true"],
        capture_output=True,
        timeout=10,
    )


@pytest.fixture(scope="session")
def bridge():
    """A TmuxBridge with a clean tmux server before and after the session."""
    _kill_all_tmux()
    time.sleep(1)
    b = TmuxBridge()
    yield b
    b.shutdown()
    _kill_all_tmux()


@pytest.fixture(scope="session")
def live_session(bridge):
    """A single long-lived session ('test-1') with its TUI fully loaded.

    Created once and reused across tests so the ~10s TUI startup is paid only
    once. Torn down by the ``bridge`` fixture's shutdown.
    """
    name = "test-1"
    bridge.create(name, cwd="C:/Users/lester")
    time.sleep(10)  # let the Claude Code TUI finish loading
    return name
