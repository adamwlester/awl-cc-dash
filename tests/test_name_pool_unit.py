"""Hermetic unit tests for name-pool wiring — the Create-panel draw (§7.5, §11 #40).

Decided contract (ARCHITECTURE §7.5, §11 #40; build plan
``dev/notes/2026-07-15-stage5-build-plan.md`` #40):

The curated 179-name pool ships at ``assets/names/agent-names.json`` (one-word,
3-5-letter, lowercase names, each validated to double safely as a git
commit-author name, §11 #19). The Create panel's randomize / auto-name affordance
draws an UNUSED name from it; a user-typed name is ALWAYS allowed.

What this file pins (all pure Python — no WSL/tmux/network):
  * ``identity._load_name_pool`` / ``identity.NAME_POOL`` — the shipped pool loads
    (179 names, includes known members) and degrades to a default, never crashes.
  * ``identity.draw_name`` — a random unused draw that honors the exclude set
    case-insensitively, falls back to the full pool when exhausted, returns
    ``None`` only on an empty pool, and is DETERMINISTIC when a pool + RNG are
    injected (the hermetic hook — no real randomness in the assertion).
  * ``GET /identity/random-name`` — excludes every live agent's name plus any
    comma-separated ``exclude`` query param, and returns a pool name.
"""

import asyncio
import random
import sys
from pathlib import Path

import pytest

_SIDECAR = Path(__file__).resolve().parent.parent / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))

import identity  # noqa: E402


# ---------------------------------------------------------------------------
# The shipped pool loads
# ---------------------------------------------------------------------------

class TestNamePoolLoads:
    def test_pool_is_the_shipped_179(self):
        # The real asset ships 179 names; pin the size loosely (>= 150) so an
        # accidental truncation fails loudly without pinning the exact list.
        assert isinstance(identity.NAME_POOL, list)
        assert len(identity.NAME_POOL) >= 150
        # A few known members from assets/names/agent-names.json.
        for name in ("goop", "blob", "echo", "orb"):
            assert name in identity.NAME_POOL

    def test_pool_members_are_lowercase_short_and_git_safe(self):
        # The pool's promise (§7.5): one-word, 3-5 letters, lowercase — safe as a
        # git author name. Spot-check the whole loaded set holds the shape.
        for n in identity.NAME_POOL:
            assert n == n.lower()
            assert n.isalpha()
            assert 3 <= len(n) <= 5

    def test_loader_degrades_when_asset_missing(self, monkeypatch, tmp_path):
        # A stripped asset tree never crashes the draw — falls back to a default.
        # Point the loader's __file__ at a tree with no names asset: parents[1]
        # resolves to tmp_path, which has no assets/names/agent-names.json.
        fake_file = tmp_path / "sidecar" / "identity.py"
        fake_file.parent.mkdir(parents=True)
        monkeypatch.setattr(identity, "__file__", str(fake_file))
        pool = identity._load_name_pool()
        assert pool == [identity._DEFAULT_NAME]


# ---------------------------------------------------------------------------
# draw_name — random unused draw, hermetic when pool + rng are injected
# ---------------------------------------------------------------------------

class TestDrawName:
    def test_deterministic_with_injected_pool_and_rng(self):
        pool = ["alpha", "bravo", "charlie", "delta"]
        # A seeded Random makes the choice reproducible — no real randomness.
        draw = identity.draw_name(pool=pool, rng=random.Random(0))
        again = identity.draw_name(pool=pool, rng=random.Random(0))
        assert draw == again
        assert draw in pool

    def test_excludes_taken_names(self):
        pool = ["alpha", "bravo"]
        # bravo is taken -> the only available name is alpha, every time.
        for _ in range(20):
            assert identity.draw_name(["bravo"], pool=pool) == "alpha"

    def test_exclude_is_case_insensitive(self):
        pool = ["Ivy", "rex"]
        # A user-typed "IVY" still blocks the pool's "Ivy".
        for _ in range(20):
            assert identity.draw_name(["IVY"], pool=pool) == "rex"

    def test_falls_back_to_full_pool_when_exhausted(self):
        pool = ["only"]
        # Every name excluded -> best-effort fall back to the full pool rather
        # than returning nothing (a repeat beats a failed draw).
        assert identity.draw_name(["only"], pool=pool) == "only"

    def test_empty_pool_returns_none(self):
        assert identity.draw_name(pool=[]) is None

    def test_default_pool_is_the_module_cache(self):
        # With no injected pool it draws from the shipped NAME_POOL.
        name = identity.draw_name(rng=random.Random(1))
        assert name in identity.NAME_POOL

    def test_ignores_blank_excludes(self):
        pool = ["solo"]
        # Empty / whitespace excludes are dropped, not treated as a name.
        assert identity.draw_name(["", "  ", None], pool=pool) == "solo"


# ---------------------------------------------------------------------------
# GET /identity/random-name — live-name exclusion
# ---------------------------------------------------------------------------

class TestRandomNameEndpoint:
    @pytest.fixture(autouse=True)
    def _clean(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(tmp_path / "rt"))
        import main
        main.sessions.clear()
        yield
        main.sessions.clear()

    def _seed(self, name):
        import main
        s = main.SessionState(session_id="s-" + name, agent_type=None, model="m",
                              permission_mode="acceptEdits", cwd=None,
                              system_prompt=None, driver_name="bridge",
                              identity={"role": "Agent", "number": 1, "name": name})
        main.sessions[s.session_id] = s
        return s

    def test_excludes_live_agent_names(self):
        import main
        self._seed("goop")  # a real pool name is now taken by a live agent
        out = asyncio.run(main.identity_random_name(exclude=None))
        assert out["name"] in identity.NAME_POOL
        assert out["name"] != "goop"

    def test_excludes_query_param_names(self):
        import main
        self._seed("goop")
        out = asyncio.run(main.identity_random_name(exclude="blob, ooze"))
        assert out["name"] not in {"goop", "blob", "ooze"}
        assert out["name"] in identity.NAME_POOL

    def test_returns_a_name_when_nothing_taken(self):
        import main
        out = asyncio.run(main.identity_random_name(exclude=None))
        assert out["name"] in identity.NAME_POOL
