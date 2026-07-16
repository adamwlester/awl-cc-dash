"""Agent identity — dashboard-owned per-agent role / number / name / color / icon.

The backend knows only ``agent_type`` + ``model``; the dashboard needs a richer
identity to render agent cards. Identity is assigned at create time, persisted in
the runtime record (so it survives a sidecar restart), and surfaced on the
session's ``to_dict`` so the UI reads it everywhere.

Round-robin assignment:
  * ``color = n mod len(AG_COLORS)`` — over the ``--ag-*`` "Jewel" palette.
  * ``icon  = n mod len(AG_ICONS_CURATED)`` — over a **curated 50** of the 167
    recolorable game-icons on disk.

So every ``(color, icon)`` pair is unique for the first ``len(AG_COLORS) × …``
agents and, once the palette is 25, every pair is unique for the first 50 agents
(25-color cycle vs 50-icon cycle), then reuses beyond — supported, not capped.
Past ~16 colors the **icon** is the primary disambiguator and color becomes a
soft "family" signal.

CROSS-STREAM SEAM (agent colors). ``AG_COLORS`` mirrors the ``--ag-*`` token
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

import json
import random
import re
from collections.abc import Iterable
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
# lands the +9. The live round-robin keys off len(AG_COLORS), so this is
# documentation / a target the curation tests can reference — not a hard modulo.
COLOR_POOL_TARGET = 25

_DEFAULT_ICON = "android-mask"

# Icon curation — a **curated 50** of the 167 game-icons in
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


# --- Name pool (§7.5, §11 #40) — the Create-panel randomize / auto-name draw ---
#
# The curated 179-name pool ships at assets/names/agent-names.json — one-word,
# 3-5-letter, lowercase names, each validated to double safely as a git
# commit-author name (§11 #19). The Create panel's randomize affordance draws an
# UNUSED name from it; a user-typed name is ALWAYS allowed (the pool is a
# convenience, never a constraint). Loaded once and cached, exactly like the icon
# set above — a stripped/unreadable asset tree degrades to a single default so a
# name draw never crashes.

_DEFAULT_NAME = "agent"


def _load_name_pool() -> list[str]:
    """The shipped curated name pool from ``assets/names/agent-names.json``.

    Returns the JSON's ``names`` list (179 lowercase names), each stripped and
    non-empty. Falls back to ``[_DEFAULT_NAME]`` when the file is
    missing/unreadable/mis-shaped, so drawing a name never fails on a stripped
    asset tree (mirrors :func:`_discover_icons`).
    """
    try:
        repo_root = Path(__file__).resolve().parents[1]
        pool_path = repo_root / "assets" / "names" / "agent-names.json"
        data = json.loads(pool_path.read_text(encoding="utf-8"))
        raw = data.get("names") if isinstance(data, dict) else None
        cleaned = [str(n).strip() for n in raw if str(n).strip()] \
            if isinstance(raw, list) else []
        return cleaned or [_DEFAULT_NAME]
    except Exception:
        return [_DEFAULT_NAME]


# The cached pool — the randomize/auto-name draw reads this.
NAME_POOL: list[str] = _load_name_pool()


def draw_name(
    exclude: Iterable[str] | None = None,
    *,
    pool: list[str] | None = None,
    rng: random.Random | None = None,
) -> str | None:
    """Draw a random UNUSED name from the pool (§7.5, §11 #40).

    ``exclude`` is the set of names already taken (live / known agents) — matched
    **case-insensitively**, so a user-typed ``"Ivy"`` still blocks the pool's
    ``"ivy"``. The draw is over the names NOT excluded; when every pool name is
    excluded it falls back to the FULL pool (a best-effort duplicate beats
    returning nothing — the 179-name pool makes true exhaustion unlikely, and a
    user-typed name is always allowed regardless). Returns ``None`` only when the
    pool itself is empty.

    Hermetic by construction: inject ``pool`` and/or ``rng`` (a
    :class:`random.Random`) so a unit test pins a deterministic draw with no real
    randomness in the assertion.
    """
    names = pool if pool is not None else NAME_POOL
    if not names:
        return None
    taken = {str(e).strip().lower() for e in (exclude or []) if str(e).strip()}
    available = [n for n in names if n.lower() not in taken]
    if not available:
        available = list(names)  # exhausted — best-effort, allow a repeat
    chooser = rng or random
    return chooser.choice(available)


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


# --- Per-agent git attribution (ARCHITECTURE §7.5, §11 #19) -----------------
#
# Every dashboard agent commits under its OWN git author name + a synthetic
# per-agent email on a FIXED, guaranteed-non-deliverable domain, so "what did
# AI touch" is a pure git query with no maintained ledger:
#     git log --author='@agents.awl-cc-dash.invalid'
# `.invalid` is the RFC-2606 reserved TLD (never routable); the domain is fixed
# so the query catches the whole fleet. Attribution is injected as per-launch
# GIT_* env (see BridgeDriver._create_session -> TmuxBridge.create), NOT
# repo-local `git config`: agents in one repo share a single `.git/config`, so
# repo-local `user.*` would collide/race across the fleet, while env vars are
# per-process and inherited by any `git` the agent runs — collision-free.

# The fixed synthetic-email domain (RFC-2606 `.invalid` — guaranteed
# non-deliverable). The AI-touched query keys off this exact suffix.
AGENT_EMAIL_DOMAIN = "agents.awl-cc-dash.invalid"


def _slugify(text: str) -> str:
    """Lowercase, safe slug for an email local-part.

    Lowercases, maps every run of non-alphanumeric chars to a single hyphen,
    and trims leading/trailing hyphens. Falls back to ``"agent"`` when the
    input slugs to nothing (e.g. all-punctuation), so an email is always valid.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug or "agent"


def git_author(identity: dict | None) -> tuple[str, str]:
    """Derive an agent's ``(author_name, synthetic_email)`` for git attribution.

    Author name = the identity ``name`` (the human-facing name, validated to
    double safely as a git commit-author name, §7.5); when the agent is unnamed
    it falls back to ``"<role>-<number>"`` (e.g. ``"Agent-3"``) so an author is
    always present. The synthetic email is ``<slug>-<number>@<domain>`` where
    the slug is derived from the name (or the role, when unnamed) and the domain
    is the fixed ``agents.awl-cc-dash.invalid`` (see module notes) — so an
    unnamed agent still lands on the AI-touched domain.

    Examples::

        {"name": "zippy", "number": 3}                  ->
            ("zippy", "zippy-3@agents.awl-cc-dash.invalid")
        {"role": "researcher", "name": "", "number": 2} ->
            ("researcher-2", "researcher-2@agents.awl-cc-dash.invalid")
        {"name": "Nova Prime!", "number": 5}            ->
            ("Nova Prime!", "nova-prime-5@agents.awl-cc-dash.invalid")

    Pure function (no I/O) so it unit-tests hermetically.
    """
    ident = identity or {}
    name = str(ident.get("name") or "").strip()
    role = (str(ident.get("role") or "").strip()) or "Agent"
    number = ident.get("number")
    if name:
        author_name = name
        slug = _slugify(name)
    else:
        # Unnamed: the role (+ number) doubles as the commit-author name.
        author_name = f"{role}-{number}" if number is not None else role
        slug = _slugify(role)
    local = f"{slug}-{number}" if number is not None else slug
    return author_name, f"{local}@{AGENT_EMAIL_DOMAIN}"


def git_env(identity: dict | None) -> dict[str, str]:
    """The four GIT_* env vars that attribute an agent's commits (§11 #19).

    Both the AUTHOR and the COMMITTER identity are set to the same per-agent
    name + synthetic email — the agent both writes and records its own commits.
    Injected onto the agent's launch command (per-process, inherited by every
    ``git`` the agent runs). See ``git_author`` for the derivation.
    """
    author_name, email = git_author(identity)
    return {
        "GIT_AUTHOR_NAME": author_name,
        "GIT_AUTHOR_EMAIL": email,
        "GIT_COMMITTER_NAME": author_name,
        "GIT_COMMITTER_EMAIL": email,
    }
