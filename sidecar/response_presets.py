"""Response-format presets — a per-agent reply-format menu (§7.14, §11 #39).

A small catalog of canned reply-format instructions the operator picks ONCE per
agent (in the Create panel or the Agent panel). The chosen preset's instruction
is appended to that agent's system prompt at launch (``claude
--append-system-prompt``, wired through the bridge driver), so every reply the
agent writes follows the format — the choice reaches and persists to the agent
(``state/agents.json``). A per-message override is a later nicety, deferred
(§7.14).

This module is the single home for the actual instruction text. The scope-aware
prompt/UI-text markdown library (§11 #45) will later absorb canned text like
this; until it lands, the catalog lives here as plain Python. Each preset is
``{label, description, instruction}`` keyed by a stable id; ``default`` is the
no-op — the agent's own natural style, nothing appended. The lean across the
non-default presets is the §7.14 / §11 #46 preamble: agents lead every reply with
a one-line summary, so Timeline / Team-Feed one-line previews have a clean source.

Contract (pinned by ``tests/test_response_presets_unit.py``):
  * ``catalog()``  — the ordered menu as ``[{id, label, description}]`` (the
    instruction text is an implementation detail of the launch injection, not
    part of the menu payload).
  * ``instruction_for(id)`` — the exact string to append; ``""`` for ``default``,
    an unknown id, or ``None`` (a missing/unknown preset injects NOTHING rather
    than erroring, so the agent simply keeps its natural style).
  * ``is_valid(id)`` / ``get(id)`` — membership + the full preset dict.
"""

from __future__ import annotations

DEFAULT_PRESET = "default"

# Ordered catalog. `instruction` is appended verbatim to the agent's system
# prompt at launch; keep each self-contained and FORMAT-only (never task content).
_PRESETS: dict[str, dict[str, str]] = {
    "default": {
        "label": "Default",
        "description": "The agent's own natural style — no format instruction added.",
        "instruction": "",
    },
    "tldr_table": {
        "label": "TL;DR + table",
        "description": "Lead with a one-line TL;DR, lay structured items out in a "
                       "compact table, and mark status with sparing emoji. The "
                       "operator's house style.",
        "instruction": (
            "Response format for every reply:\n"
            "- Open with a one-line TL;DR that states the outcome in plain language.\n"
            "- When you report multiple items, statuses, or options, lay them out "
            "in a compact Markdown table rather than long prose.\n"
            "- Use status emoji sparingly to mark state: ✅ done / good, "
            "⚠️ needs attention, ❌ failed / blocked — at most "
            "one per row or line, never decoratively.\n"
            "- Keep prose tight; prefer tables and short lines over paragraphs.\n"
            "- Lead with the conclusion first, supporting detail after."
        ),
    },
    "concise": {
        "label": "Concise",
        "description": "Terse — a one-line summary up front, then only the "
                       "essential detail, minimal prose.",
        "instruction": (
            "Response format for every reply: be concise. Open with a single "
            "one-line summary of the outcome, then give only the essential detail "
            "in as few words as clarity allows — no filler, no restating the "
            "request. Prefer short lines and lists over paragraphs."
        ),
    },
    "bullets": {
        "label": "Bulleted",
        "description": "Structured bullet points under short headings, led by a "
                       "one-line summary.",
        "instruction": (
            "Response format for every reply: lead with a one-line summary, then "
            "present the substance as structured bullet points, grouped under "
            "short bold headings where that helps. Avoid long unbroken paragraphs."
        ),
    },
    "overview_first": {
        "label": "Overview first",
        "description": "A plain-language high-level overview first (outcomes, not "
                       "mechanism), then the technical detail.",
        "instruction": (
            "Response format for every reply: open with a short, plain-language, "
            "high-level overview framed in outcomes — what happened or what "
            "you propose, understandable without technical background — and "
            "only then give the technical specifics. Lead with the one-line "
            "takeaway."
        ),
    },
    "narrative": {
        "label": "Narrative",
        "description": "Plain running prose — clear sentences and short "
                       "paragraphs, no tables or bullet scaffolding.",
        "instruction": (
            "Response format for every reply: write in plain running prose — "
            "clear, complete sentences in short paragraphs. Still open with a "
            "one-line summary sentence, but avoid tables and bullet-point "
            "scaffolding; explain in words."
        ),
    },
}


def catalog() -> list[dict]:
    """The preset menu as an ordered list of ``{id, label, description}`` rows.

    The ``instruction`` text is intentionally omitted from the menu payload (it
    is an implementation detail of the launch injection); read it via
    :func:`instruction_for`.
    """
    return [
        {"id": pid, "label": p["label"], "description": p["description"]}
        for pid, p in _PRESETS.items()
    ]


def is_valid(preset_id: str | None) -> bool:
    """True if ``preset_id`` names a known preset."""
    return preset_id in _PRESETS


def get(preset_id: str | None) -> dict | None:
    """The full preset dict (``{label, description, instruction}``) or ``None``."""
    if preset_id is None:
        return None
    p = _PRESETS.get(preset_id)
    return dict(p) if p is not None else None


def instruction_for(preset_id: str | None) -> str:
    """The system-prompt instruction to append for ``preset_id``.

    Empty string for ``default``, an unknown id, or ``None`` — a missing/unknown
    preset injects NOTHING (the agent keeps its natural style) rather than
    erroring. This is exactly what the bridge driver appends via
    ``--append-system-prompt``.
    """
    p = _PRESETS.get(preset_id or "")
    return (p or {}).get("instruction", "") or ""
