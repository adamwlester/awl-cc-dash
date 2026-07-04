"""Shared pytest fixtures and logging setup for workspace-level tests.

Logging: every run writes a timestamped, DEBUG-level file into ``tests/log/``
(in addition to the concise console output configured in ``pyproject.toml``).
That file is the place to look when an integration test fails — it captures the
exact WSL/tmux commands the bridge ran, raw screen captures, and full tracebacks.
"""

import datetime
import os
import platform
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
REPO_ROOT = Path(__file__).resolve().parent.parent

# Retention: keep only the newest N bulky DEBUG logs (tmux_bridge_*.log). The
# small durable results_*.{xml,txt} artifacts are NOT pruned — they are the
# verification record. All of tests/log/ is gitignored, so this is local-disk
# housekeeping only.
DEBUG_LOG_KEEP = 20

# The live/integration tier. Detection is CONVENTION-based: any ``*_live.py`` file
# is live, plus the legacy ``test_tmux_bridge.py`` (which predates the ``_live.py``
# suffix). Used to decide whether to capture WSL/CLI env info in the results
# summary and to label the tier correctly (only meaningful when the live tier
# actually ran). This tuple is the explicit-match set for files that don't carry
# the suffix; the suffix rule itself lives in ``_is_live_nodeid`` so the list can't
# rot as new ``*_live.py`` spikes are added.
LIVE_TEST_FILES = ("test_tmux_bridge.py", "test_bridge_finisher_live.py")


def pytest_configure(config):
    """Per run: route the DEBUG file log + a durable JUnit XML results file into
    tests/log/, stash run metadata for the summary, and prune old DEBUG logs."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    config._awl_stamp = stamp
    config._awl_start = time.time()

    # Verbose DEBUG file log (bridge commands, raw screens) — existing behavior.
    if not getattr(config.option, "log_file", None):
        config.option.log_file = str(LOG_DIR / f"tmux_bridge_{stamp}.log")

    # Durable machine-readable results (pass/fail/skip + timing). Set the junitxml
    # plugin's option before it configures; the human-readable companion is
    # written in pytest_terminal_summary. A user-supplied --junitxml wins.
    if not getattr(config.option, "xmlpath", None):
        config.option.xmlpath = str(LOG_DIR / f"results_{stamp}.xml")

    _prune_debug_logs(DEBUG_LOG_KEEP)


def _prune_debug_logs(keep):
    """Delete all but the newest `keep` tmux_bridge_*.log files. Best-effort."""
    try:
        logs = sorted(LOG_DIR.glob("tmux_bridge_*.log"))
        stale = logs[:-keep] if keep > 0 else logs
        for old in stale:
            try:
                old.unlink()
            except OSError:
                pass
    except Exception:
        pass


def _git_sha():
    """Short HEAD sha (+ '-dirty' if the tree has uncommitted changes)."""
    try:
        rev = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=5,
        ).stdout.strip() or "unknown"
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=REPO_ROOT, capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        return rev + ("-dirty" if dirty else "")
    except Exception:
        return "unknown"


def _claude_cli_version():
    """Best-effort Claude Code CLI version inside WSL (live runs only)."""
    try:
        r = subprocess.run(
            ["wsl", "-d", "Ubuntu", "--", "bash", "-lc", "claude --version"],
            capture_output=True, text=True, timeout=20,
        )
        return (r.stdout.strip() or r.stderr.strip() or "unknown").splitlines()[0][:120]
    except Exception:
        return "unknown"


def _is_live_nodeid(nodeid):
    """True if a test nodeid belongs to the live/integration tier — any ``*_live.py``
    file (the suffix convention) or one of the explicit ``LIVE_TEST_FILES``."""
    fname = nodeid.split("::", 1)[0].replace("\\", "/").rsplit("/", 1)[-1]
    return fname.endswith("_live.py") or fname in LIVE_TEST_FILES


def _live_ran(terminalreporter):
    for key in ("passed", "failed", "error", "skipped", "xfailed", "xpassed"):
        for rep in terminalreporter.stats.get(key, []):
            if _is_live_nodeid(getattr(rep, "nodeid", "")):
                return True
    return False


def _one_line_reason(rep):
    try:
        lr = getattr(rep, "longrepr", None)
        if lr is None:
            return "(no detail)"
        crash = getattr(getattr(lr, "reprcrash", None), "message", None)
        return (crash or str(lr)).strip().splitlines()[0][:200]
    except Exception:
        return "(unparseable)"


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Write a durable, human-readable results record next to the JUnit XML:
    outcome + counts + the commit / selection / env it was verified against."""
    try:
        if getattr(config.option, "collectonly", False):
            return
        stamp = getattr(config, "_awl_stamp", None)
        if not stamp:
            return
        tr = terminalreporter
        stats = tr.stats

        def c(k):
            return len(stats.get(k, []))

        passed, failed, errors = c("passed"), c("failed"), c("error")
        skipped, deselected = c("skipped"), c("deselected")
        xfailed, xpassed = c("xfailed"), c("xpassed")
        if passed + failed + errors + skipped == 0:
            return  # nothing actually ran

        start = getattr(config, "_awl_start", None)
        duration = f"{time.time() - start:.1f}s" if start else "unknown"
        markexpr = getattr(config.option, "markexpr", "") or "(none)"
        keyword = getattr(config.option, "keyword", "") or "(none)"
        live = _live_ran(tr)
        result = "PASS" if (failed == 0 and errors == 0) else "FAIL"
        xml_name = Path(getattr(config.option, "xmlpath", "") or "").name or "(none)"

        lines = [
            f"AWL test results — {stamp}",
            f"Result:     {result}  (pytest exit {exitstatus})",
            f"Commit:     {_git_sha()}",
            f"Tier:       {'live (WSL2/tmux)' if live else 'hermetic'}",
            f"Selection:  -m {markexpr!r}  -k {keyword!r}",
            f"Counts:     passed={passed} failed={failed} errors={errors} "
            f"skipped={skipped} xfailed={xfailed} xpassed={xpassed} deselected={deselected}",
            f"Duration:   {duration}",
            f"Python:     {platform.python_version()}",
        ]
        if live:
            lines.append("WSL distro: Ubuntu")
            lines.append(f"Claude CLI: {_claude_cli_version()}")
        lines.append(f"JUnit XML:  {xml_name}")

        fails = stats.get("failed", []) + stats.get("error", [])
        if fails:
            lines.append("")
            lines.append("Failures:")
            for rep in fails:
                lines.append(f"  - {getattr(rep, 'nodeid', '?')}: {_one_line_reason(rep)}")

        text = "\n".join(lines) + "\n"
        (LOG_DIR / f"results_{stamp}.txt").write_text(text, encoding="utf-8")
        try:
            (LOG_DIR / "results_latest.txt").write_text(text, encoding="utf-8")
        except Exception:
            pass
        tr.write_line(f"[awl] durable results -> {LOG_DIR / f'results_{stamp}.txt'}")
    except Exception:
        pass


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
