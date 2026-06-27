"""Agent identity — dashboard-owned per-agent role / number / name / color / icon.

The backend knows only ``agent_type`` + ``model``; the dashboard needs a richer
identity to render agent cards. This is the MINIMAL store: identity is assigned
at create time, persisted in the runtime record (so it survives a sidecar
restart), and surfaced on the session's ``to_dict`` so the UI reads it everywhere.

Color is round-robin over the 16 ``--ag-*`` "Jewel" tokens (``design/tokens.css``)
in the mockup's interleaved order, so adjacent agents get visually distinct hues.
Icon is round-robin over the recolorable game-icon set (``assets/icons/agents/``).

DEFERRED (explicitly out of scope this run): the past-16 color/icon uniqueness
algorithm and the human-name pools. Past 16 agents the color simply repeats.
"""

from __future__ import annotations

from pathlib import Path

# The 16 agent colors as (name, hex), in the mockup's round-robin order — the
# `agent:{...}` map in design/mockup.html resolved against the --ag-* values in
# design/tokens.css. The order is interleaved (not the tokens.css declaration
# order) so two agents created back-to-back get well-separated hues.
AG_COLORS: list[tuple[str, str]] = [
    ("crimson", "#aa3a61"), ("emerald", "#008149"), ("cobalt", "#006bbb"),
    ("amber", "#aa4600"), ("fern", "#387b12"), ("violet", "#7152b5"),
    ("vermilion", "#af3c3a"), ("cyan", "#007f91"), ("gold", "#9d5400"),
    ("citron", "#876300"), ("orchid", "#8b48a0"), ("azure", "#0076ab"),
    ("teal", "#008370"), ("lime", "#687100"), ("indigo", "#4d5ebe"),
    ("magenta", "#9e3f84"),
]

_DEFAULT_ICON = "android-mask"


def _discover_icons() -> list[str]:
    """Sorted game-icon names from ``assets/icons/agents/`` (repo root).

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
    return {
        "role": (req.get("role") or "Agent"),
        "number": req["number"] if req.get("number") is not None else ordinal + 1,
        "name": (req.get("name") or ""),
        "color": (req.get("color") or color_hex),
        "icon": (req.get("icon") or AG_ICONS[ordinal % len(AG_ICONS)]),
    }
