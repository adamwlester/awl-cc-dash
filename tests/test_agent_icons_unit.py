"""Hermetic unit tests — the agent-icon asset routes (§11 #56, NU items 4/5).

The decided contract this file encodes:

  * ``GET /assets/agent-icons/{name}`` serves a shipped
    ``assets/icons/agents/*.svg`` tile as ``image/svg+xml``. A valid
    ``?color=#rrggbb`` recolors the full-bleed background rect (the default
    black ``<path d="M0 0h512v512H0z"/>``) with that fill EXACTLY once — the
    white glyph stays a knockout; an invalid ``color`` is ignored (the icon
    is served unrecolored, byte-identical to disk — the SVG-injection guard).
    Traversal-shaped names (``..``, any ``/`` or ``\\``) and unknown stems are
    honest 404s.
  * The 11 curated stems whose raw file names historically mismatched the
    renderer's sprite map (the "fnord has no icon" bug — NU item 4) all serve
    200 through the recolor route, pinning that the curated auto-assign pool
    stays servable end to end.
  * ``GET /assets/agent-icons`` (the NU item 5 listing) returns the FULL
    discovered set for the manual icon picker: ``{"icons": identity.AG_ICONS,
    "count": len(...)}`` — sorted stems, every one an existing ``.svg`` on
    disk. The set is discovered once at sidecar import (identity module
    import), so icons added mid-run appear only after a restart — the
    documented limitation, not a bug.

No WSL, no network — the async endpoint functions are driven directly via
``asyncio.run`` (the suite's unit-tier convention); the on-disk assets are
repo-shipped source, not runtime state.
"""

import asyncio
import sys
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parent.parent
_SIDECAR = _REPO / "sidecar"
if str(_SIDECAR) not in sys.path:
    sys.path.insert(0, str(_SIDECAR))

from fastapi import HTTPException  # noqa: E402

import identity  # noqa: E402
import main  # noqa: E402

_ICONS_DIR = _REPO / "assets" / "icons" / "agents"

# The 11 curated stems the renderer's sprite map historically spelled
# differently (NU item 4) — each must stay servable through the endpoint.
_FORMERLY_MISMATCHED = [
    "dragon-head__lorc", "devil-mask", "t-rex-skull", "deer-head",
    "burning-skull", "doctor-face", "barbarian", "horned-helm",
    "diving-helmet", "ram-profile", "egyptian-profile",
]


@pytest.fixture(autouse=True)
def _clean(tmp_path, monkeypatch):
    monkeypatch.setenv("AWL_SIDECAR_RUNTIME", str(tmp_path / "rt"))
    yield


def _get_icon(name: str, color: str | None = None):
    return asyncio.run(main.agent_icon(name, color=color))


# ---------------------------------------------------------------------------
# GET /assets/agent-icons/{name} — serve + recolor
# ---------------------------------------------------------------------------

class TestAgentIconRoute:
    def test_real_stem_serves_svg(self):
        resp = _get_icon("wizard-face")
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("image/svg+xml")
        assert b"<svg" in resp.body

    def test_valid_color_recolors_bg_path_exactly_once(self):
        resp = _get_icon("wizard-face", color="#aa3a61")
        body = resp.body.decode("utf-8")
        recolored = '<path d="M0 0h512v512H0z" fill="#aa3a61"/>'
        # The fill landed, exactly once, and the original unfilled bg is gone.
        assert body.count(recolored) == 1
        assert '<path d="M0 0h512v512H0z"/>' not in body

    def test_invalid_color_is_ignored_not_injected(self):
        # A non-#rrggbb value (the SVG-injection guard) serves the icon
        # unrecolored — byte-identical to the shipped file.
        on_disk = (_ICONS_DIR / "wizard-face.svg").read_text(encoding="utf-8")
        for bad in ("red", "#zzzzzz", '"><script>', "#aa3a6"):
            resp = _get_icon("wizard-face", color=bad)
            assert resp.status_code == 200
            assert resp.body.decode("utf-8") == on_disk

    def test_traversal_names_404(self):
        for name in ("..", "../identity", "a/b", "a\\b", "..\\secrets"):
            with pytest.raises(HTTPException) as ei:
                _get_icon(name)
            assert ei.value.status_code == 404

    def test_unknown_stem_404(self):
        with pytest.raises(HTTPException) as ei:
            _get_icon("no-such-icon-stem")
        assert ei.value.status_code == 404

    @pytest.mark.parametrize("stem", _FORMERLY_MISMATCHED)
    def test_formerly_mismatched_curated_stems_serve(self, stem):
        # Each of the 11 curated stems the sprite map used to misname (NU
        # item 4) serves 200 — and stays in the curated auto-assign pool.
        assert stem in identity.AG_ICONS_CURATED
        resp = _get_icon(stem)
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("image/svg+xml")


# ---------------------------------------------------------------------------
# GET /assets/agent-icons — the full-set listing (NU item 5)
# ---------------------------------------------------------------------------

class TestAgentIconListing:
    def test_listing_matches_discovered_set(self):
        out = asyncio.run(main.list_agent_icons())
        assert out["count"] == len(out["icons"])
        assert out["icons"] == identity.AG_ICONS

    def test_listing_is_sorted(self):
        out = asyncio.run(main.list_agent_icons())
        assert out["icons"] == sorted(out["icons"])

    def test_every_listed_stem_exists_on_disk(self):
        out = asyncio.run(main.list_agent_icons())
        assert out["icons"]  # never empty — degrade floor is one default
        for stem in out["icons"]:
            assert (_ICONS_DIR / f"{stem}.svg").is_file(), stem
