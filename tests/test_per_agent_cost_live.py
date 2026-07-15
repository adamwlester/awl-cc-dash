r"""Live spike — Per-agent cost harvest (§10 item #11, Priority: Low).

Probes whether a NON-FABRICATED per-agent cost/usage figure can be harvested for a
`bridge` agent, head-to-head across two candidate paths, and records the honest state
live (the code currently ships an "honest blank" — §7.15; `GET /usage`: "Per-agent
cost stays out of scope (the bridge emits none)").

  * Path (a) — JSONL usage fields. `derive_context_usage` (via `get_context_usage()`)
    harvests a real *token* number off the latest assistant `message.usage`. That is
    *usage*, NOT *cost*: there is no cost field and no price table in the JSONL. The
    test asserts the usage number is real AND that no cost key exists — the usage-vs-cost
    distinction (conflating them would itself be the fabrication we guard against).
  * Path (b) — `/cost` scraped via the console path. `send("/cost")` then read the
    screen and parse the per-session cost panel.

LIVE FINDING (Claude CLI 2.1.198, Max/Pro subscription — STRONGER than the build
prompt's "subscription shows no dollar figure" hypothesis):
  `/cost` opens the unified Usage dialog and DOES render a per-SESSION cost panel:
        Session
           Total cost:            $0.2127
           Total duration (API):  3s / (wall): 7s
           Usage by model:
               claude-haiku-4-5:  1.0k in, 25 out ...           ($0.0012)
               claude-sonnet-5:   4.3k in, 7 out, 33.1k cache write ($0.2116)
        Current session  ██▌ 55% used  ·  Current week  █▌ 11% used
  So a defensible, non-fabricated **per-agent cost IS harvestable via the `/cost`
  console scrape** — labeled "Session · Total cost", with a per-model $ breakdown.
  Caveats (kept honest): it is Claude Code's OWN estimate (tokens × model price), a
  point-in-time, idle-gated on-demand pull (not a passive feed), and it prices the
  whole `claude` session (which for a bridge agent == that one agent). JSONL (path a)
  still yields usage-not-cost; the cost lives only on the `/cost` screen.
  RECOMMENDATION (flagged, NOT applied — I did not edit ARCHITECTURE.md): the shipped
  "honest blank" (§7.15 / §10 #11) can be REVISITED — a per-agent cost estimate is
  available via a `/cost` scrape; if wired, show it as an idle-time on-demand estimate
  with a "Claude Code estimate" caveat, not a live per-turn feed.

Read-back is the crux: proving a number is trustworthy is the whole test — so path (b)
parses the *specific* "Session / Total cost: $X" line (not merely any `$` on screen),
plus the per-model breakdown; and a fabricated/guessed number is never asserted.

Run (ONLY this file, in isolation — never the whole live tier)::

    .\.venv\Scripts\python.exe -m pytest tests\test_per_agent_cost_live.py -m integration

=============================================================================
ISOLATION RULES (parallel-safe — CRITICAL; reproduced from the build prompt):
  * ONE new file only — tests/test_per_agent_cost_live.py. Create nothing else.
  * Unique tmux session names — prefix every session with the slug (`pacost-<uuid8>`)
    so it can't collide with a sibling agent's session.
  * NEVER call `tmux kill-server` (directly or via a fixture that does) in teardown.
  * Do NOT depend on conftest's session-scoped `bridge` fixture — its setup AND
    teardown both call `_kill_all_tmux()` (= `tmux kill-server`), which kills sibling
    agents' live sessions. This module instantiates its OWN `TmuxBridge()` for the WSL
    shell helpers + `/cost` read-back, and removes ONLY its own session + throwaway dir.
  * Do NOT edit tests/conftest.py, pyproject.toml, or tests/README.md.
  * Bridge sessions stay TAB-LESS — never `show=True`, never `show()`.
=============================================================================
"""

import asyncio
import logging
import re
import sys
import uuid
from pathlib import Path

import pytest

# Make the sidecar's modules importable as top-level (it runs with its own dir on
# sys.path, not the repo root) — mirrors tests/test_bridge_finisher_live.py.
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SIDECAR = _REPO_ROOT / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))
# ...and the repo root, so `from bridge import TmuxBridge` resolves for the read-back.
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from drivers.bridge import BridgeDriver  # noqa: E402
from drivers.base import DriverConfig  # noqa: E402
from bridge import TmuxBridge  # noqa: E402

log = logging.getLogger(__name__)

pytestmark = [pytest.mark.integration, pytest.mark.slow]

SLUG = "pacost"

# The per-SESSION total, e.g. "Total cost:            $0.2127" (the defensible per-agent
# number — NOT merely any `$` on the screen, which would include incidental figures).
_TOTAL_COST = re.compile(r"Total cost:\s*\$\s?(\d+(?:\.\d+)?)")
# Per-model breakdown parentheses, e.g. "($0.0012)".
_PER_MODEL_COST = re.compile(r"\(\$\s?\d+(?:\.\d+)?\)")


@pytest.fixture(autouse=True)
def _runtime_to_tmp(tmp_path, monkeypatch):
    """Keep restart-survival records out of sidecar/runtime/ during tests."""
    monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(tmp_path / "runtime"))


@pytest.fixture
def shell_bridge():
    """Our OWN TmuxBridge — WSL shell helpers + the `/cost` read-back. NOT conftest's
    `bridge` fixture (whose teardown does `tmux kill-server`)."""
    return TmuxBridge()


@pytest.fixture
def diag_dir(shell_bridge):
    """A fresh, empty WSL throwaway dir; removes ONLY its own dir after the test."""
    path = f"/home/lester/awl-{SLUG}-{uuid.uuid4().hex[:8]}"
    shell_bridge._run(f"mkdir -p {path}")
    yield path
    shell_bridge._run(f"rm -rf {path}")


async def _wait_for_marker(driver, marker, timeout=120):
    """Poll the JSONL transcript until an assistant entry carries the marker (so
    `message.usage` exists to harvest). Mirrors the finisher's `_send_marker_and_wait`."""
    for _ in range(int(timeout * 2)):
        try:
            entries = await asyncio.to_thread(driver._bridge.read_log, driver.tmux_name)
        except Exception:
            entries = []
        if any(
            e.get("type") == "assistant"
            and marker in str((e.get("message") or {}).get("content"))
            for e in entries
        ):
            return True
        await asyncio.sleep(0.5)
    return False


def test_per_agent_cost_harvest(shell_bridge, diag_dir):
    """Drive a real bridge turn, then harvest head-to-head: (a) JSONL usage yields a real
    token number but NO cost key; (b) a `/cost` console scrape yields a defensible
    per-session Total cost + per-model breakdown. Asserts the honest, non-fabricated
    state — usage from JSONL, cost from `/cost` — and degrades to the usage-only boundary
    (xfail FINDING) if a future build/account shows no per-session cost."""

    async def flow():
        events: list[dict] = []
        # Unique, slug-prefixed tmux name (the driver defaults to `awl-<uuid8>`; we set a
        # `pacost-<uuid8>` name so the session is identifiable and can't be confused with
        # a sibling/dashboard `awl-*` session). Same id doubles as the sidecar session id.
        sid = f"{SLUG}-{uuid.uuid4().hex[:8]}"
        driver = BridgeDriver(
            DriverConfig(cwd=diag_dir, permission_mode="default"),
            events.append,
            session_id=sid,
        )
        driver._name = sid  # slug-prefixed, unique tmux session name
        await driver.start()  # show=False path — TAB-LESS. Never show=True.
        tmux = driver.tmux_name
        try:
            # --- Drive a real turn so the transcript has message.usage to harvest. ---
            await driver.send("Reply with exactly: COST_OK")
            assert await _wait_for_marker(driver, "COST_OK"), \
                "marker turn never landed in the transcript"

            # --- Path (a): JSONL usage — a real token number, but NOT cost. ---
            usage = await driver.get_context_usage()
            log.debug("Path (a) usage dict: %s", usage)
            assert usage is not None, "get_context_usage returned None after a real turn"
            assert isinstance(usage.get("tokens"), int) and usage["tokens"] > 0, \
                f"usage tokens not a positive int: {usage!r}"
            # The usage-vs-cost distinction, proven in code: usage carries tokens/
            # work_steps but NO cost/dollar key — JSONL is usage, not cost.
            assert "cost" not in usage and "total_cost_usd" not in usage, \
                f"usage dict unexpectedly carries a cost key: {sorted(usage)}"
            assert not any("cost" in str(k).lower() or "usd" in str(k).lower()
                           for k in usage), f"usage dict has a cost-like key: {sorted(usage)}"
            # The driver NOW advertises the on-demand cost capability — §11 #32
            # wired this spike's WORKS finding (driver.get_cost / GET
            # /sessions/{id}/cost). The JSONL usage dict itself stays cost-free
            # (asserted above): cost comes only from the /cost scrape.
            assert "cost" in BridgeDriver.CAPABILITIES, BridgeDriver.CAPABILITIES

            # --- Path (b): `/cost` scraped via the console path. ---
            shell_bridge.send(tmux, "/cost")
            await asyncio.sleep(3)  # /cost opens the Usage dialog (not a generating turn)
            screen = shell_bridge.scrollback(tmux, max_lines=150)["content"]
            log.debug("=== /cost screen ===\n%s", screen[-4000:])
            # Dismiss the dialog (defensive; the session is killed in teardown anyway).
            try:
                shell_bridge.keys(tmux, "Escape")
            except Exception as e:  # pragma: no cover - best effort
                log.debug("Escape after /cost failed: %s", e)

            assert screen.strip(), "/cost produced an empty screen (nothing to adjudicate)"
            total_m = _TOTAL_COST.search(screen)
            per_model = _PER_MODEL_COST.findall(screen)
            log.debug("per-model cost figures: %s", per_model)

            if total_m is None:
                # Honest usage-only boundary (the build prompt's hypothesised outcome):
                # no per-session cost figure — usage tokens are the only per-agent number.
                pytest.xfail(
                    "FINDING (usage-only boundary): `/cost` showed no per-session "
                    "'Total cost: $X' line; a per-agent COST is not harvestable, so the "
                    "shipped 'honest blank' (§7.15) + total_cost_usd==0.0 is correct. "
                    f"Screen head:\n{screen[:1000]}"
                )

            # WORKS — a defensible, non-fabricated per-session cost IS harvestable.
            total = float(total_m.group(1))
            log.info(
                "Path (b) WORKS: /cost per-session Total cost = $%.4f; per-model figs=%s",
                total, per_model,
            )
            # Assert it is the SESSION panel's total (per-agent), with a real numeric
            # value and a per-model breakdown — a Claude-Code-computed estimate, not ours.
            assert "Session" in screen, "no 'Session' cost panel on the /cost screen"
            assert total >= 0.0, f"nonsensical per-session Total cost: {total}"
            assert per_model, "expected a per-model $ breakdown alongside the Total cost"

        finally:
            await driver.close()  # kills ONLY this session's tmux; never kill-server

    asyncio.run(flow())
