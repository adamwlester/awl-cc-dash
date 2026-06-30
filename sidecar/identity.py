"""Agent identity — dashboard-owned per-agent role / number / name / color / icon.

The backend knows only ``agent_type`` + ``model``; the dashboard needs a richer
identity to render agent cards. Identity is assigned at create time, persisted in
the runtime record (so it survives a sidecar restart), and surfaced on the
session's ``to_dict`` so the UI reads it everywhere.

Round-robin assignment (OD-03):
  * ``color = n mod len(AG_COLORS)`` — over the ``--ag-*`` "Jewel" palette.
  * ``icon  = n mod len(AG_ICONS_CURATED)`` — over a **curated 50** of the 167
    recolorable game-icons on disk.

So every ``(color, icon)`` pair is unique for the first ``len(AG_COLORS) × …``
agents and, once the palette is 25, every pair is unique for the first 50 agents
(25-color cycle vs 50-icon cycle), then reuses beyond — supported, not capped.
Past ~16 colors the **icon** is the primary disambiguator and color becomes a
soft "family" signal.

CROSS-STREAM SEAM (OD-03 colors). ``AG_COLORS`` mirrors the ``--ag-*`` token
**names** in ``design/tokens.css`` — it is NOT a parallel palette. The design
stream owns the palette and is extending it **16 → 25** (the +9 names + OKLCH
values are theirs). When those land, add the 9 ``(name, hex)`` pairs here in the
same interleaved order to complete the ``n mod 25`` round-robin; the modulo is
already ``n mod len(AG_COLORS)``, so it becomes ``n mod 25`` automatically. Do
**not** invent the +9 here.

DEFERRED (out of scope this run): the past-50 (color, icon) uniqueness algorithm,
the human-name pools, and in-panel identity editing (v1 is read-only).
"""

from __future__ import annotations

from pathlib import Path

# The agent colors as (name, hex), in the mockup's interleaved round-robin order
# (NOT the tokens.css declaration order) so two agents created back-to-back get
# well-separated hues. Mirrors the `--ag-*` token NAMES in design/tokens.css.
# Currently 16; grows to 25 when the design stream lands the +9 (see the
# CROSS-STREAM SEAM note above) — additive only, never rename an existing entry.
AG_COLORS: list[tuple[str, str]] = [
    ("crimson", "#aa3a61"), ("emerald", "#008149"), ("cobalt", "#006bbb"),
    ("amber", "#aa4600"), ("fern", "#387b12"), ("violet", "#7152b5"),
    ("vermilion", "#af3c3a"), ("cyan", "#007f91"), ("gold", "#9d5400"),
    ("citron", "#876300"), ("orchid", "#8b48a0"), ("azure", "#0076ab"),
    ("teal", "#008370"), ("lime", "#687100"), ("indigo", "#4d5ebe"),
    ("magenta", "#9e3f84"),
]

# The number of colors the palette is intended to reach once the design stream
# lands the +9 (OD-03). The live round-robin keys off len(AG_COLORS), so this is
# documentation / a target the curation tests can reference — not a hard modulo.
COLOR_POOL_TARGET = 25

_DEFAULT_ICON = "android-mask"

# OD-03 icon curation — a **curated 50** of the 167 game-icons in
# assets/icons/agents/ (the manual icon picker still indexes all 167; this is the
# auto-assignment pool only). Chosen for distinctiveness + recognizability and
# ordered so adjacent ordinals look clearly different (categories interleaved:
# mage/robot/animal/warrior/skull/mythic/…). Every stem here exists on disk —
# guarded by tests/test_sidecar_unit.py (curation drift fails loudly).
AG_ICONS_CURATED: list[str] = [
    "wizard-face", "robot-helmet", "bear-head", "spartan-helmet", "death-skull",
    "dragon-head__lorc", "cyborg-face", "fox-head", "ninja-head", "devil-mask",
    "wolf-head", "astronaut-helmet", "witch-face", "tiger-head", "centurion-helmet",
    "t-rex-skull", "mecha-head", "eagle-head", "samurai-helmet", "medusa-head",
    "monk-face", "deer-head", "android-mask", "minotaur", "pirate-captain",
    "elephant-head", "viking-head", "burning-skull", "squid-head", "doctor-face",
    "rabbit-head", "black-knight-helm", "oni", "metal-golem-head", "parrot-head",
    "plague-doctor-profile", "troll", "samus-helmet", "stag-head", "barbarian",
    "goblin-head", "clown", "raccoon-head", "horned-helm", "spectre",
    "diving-helmet", "ram-profile", "egyptian-profile", "tribal-mask", "imp-laugh",
]


def _discover_icons() -> list[str]:
    """Sorted game-icon names from ``assets/icons/agents/`` (repo root).

    The full set (167) backs the manual icon **picker** + the recolor endpoint.
    Falls back to a single default when the directory is unreadable, so identity
    assignment never fails on a missing asset tree.
    """
    try:
        repo_root = Path(__file__).resolve().parents[1]
        agents_dir = repo_root / "assets" / "icons" / "agents"
        names = sorted(p.stem for p in agents_dir.glob("*.svg"))
        return names or [_DEFAULT_ICON]
    except Exception:
        return [_DEFAULT_ICON]


# Full discovered set (167) — the manual picker / recolor endpoint use this.
AG_ICONS: list[str] = _discover_icons()


def assign_identity(requested: dict | None, ordinal: int) -> dict:
    """Resolve a full identity for a new agent.

    Args:
        requested: optional caller-provided fields (``role`` / ``number`` /
            ``name`` / ``color`` / ``icon``); any omitted field gets a default.
        ordinal: a monotonic 0-based counter driving the round-robin
            color / icon / number.

    Returns:
        ``{role, number, name, color, icon}`` — every field populated.
    """
    req = requested or {}
    _color_name, color_hex = AG_COLORS[ordinal % len(AG_COLORS)]
    icon = AG_ICONS_CURATED[ordinal % len(AG_ICONS_CURATED)]
    return {
        "role": (req.get("role") or "Agent"),
        "number": req["number"] if req.get("number") is not None else ordinal + 1,
        "name": (req.get("name") or ""),
        "color": (req.get("color") or color_hex),
        "icon": (req.get("icon") or icon),
    }
