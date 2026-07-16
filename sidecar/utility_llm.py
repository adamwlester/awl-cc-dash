"""Utility-LLM passes (Revise / Summarize / Handoff report) — the `sdk`-driver carve-out.

A small, closed set of consumers use the `sdk` engine: **Revise** (scope chip
Grammar · Language · Refactor, default Grammar), **Summarize**, and the
**Handoff report** (§11 #16 — the structured summary layered on Handoff's plain
context carry-over). All run as non-interactive **one-shot** passes via the
in-process Claude Agent SDK `query()` — NOT the bridge. Everything else
multi-agent (stream, queue, hooks, console, scratchpad, linking, Plan/Decision
detection) stays on the bridge.

System-prompt texts resolve through the scope-aware prompt/UI-text markdown
library (§11 #45, :mod:`prompt_library`): the shipped defaults at
``assets/prompts/actions.md`` (groups ``revise`` / ``summarize``, seeded
VERBATIM from the constants below) with a per-project override at
``<project>/.awl-cc-dash/docs/prompts/``, and the in-code constants as the
fallback when neither scope has the item — the library must never be the
reason a utility pass fails. The **handoff-report system text is the deliberate
exception**: its body embeds ``## `` heading lines the ##/### file convention
cannot hold, so it stays in-code only.
"""
from __future__ import annotations

REVISE_SYSTEMS = {
    "grammar": ("You are a careful copy-editor. Fix grammar, spelling, and "
                "punctuation ONLY. Preserve meaning, voice, and formatting. "
                "Return ONLY the revised text — no preamble, no commentary."),
    "language": ("You are an editor. Improve clarity, flow, and word choice while "
                 "preserving the meaning and intent. Return ONLY the revised text "
                 "— no preamble, no commentary."),
    "refactor": ("You are a technical editor. Restructure and tighten the text for "
                 "clarity and concision while preserving all information. Return "
                 "ONLY the revised text — no preamble, no commentary."),
}
SUMMARIZE_SYSTEM = ("You are a concise summarizer. Summarize the following "
                    "faithfully and briefly. Return ONLY the summary — no preamble.")

# Handoff report (§11 #16): a utility-LLM pass over an agent's recent transcript
# that distills a short, structured hand-off — what the agent was doing, the key
# decisions it made, and the current state / what's still pending — so a forked
# or picking-up agent (or the operator) can continue without re-reading the whole
# conversation. Structured markdown (⚠ assumed format, doc-consistent with the
# operator's TL;DR style, §7.14). Return ONLY the report body — no preamble.
HANDOFF_SYSTEM = (
    "You are writing a concise HANDOFF report for another agent (or a human) who "
    "will pick up this work. From the transcript excerpt, produce SHORT structured "
    "markdown with exactly these three sections and nothing else:\n"
    "## What was being done\n"
    "## Key decisions\n"
    "## Current state & what's pending\n"
    "Use terse bullet points. Be faithful — do not invent facts not in the "
    "transcript. Return ONLY the report body, starting at the first heading — no "
    "preamble, no closing commentary.")

DEFAULT_SCOPE = "grammar"


def _library_text(group: str, key: str, cwd: str | None) -> str | None:
    """The §11 #45 markdown-library text for ``group``/``key``, or ``None``.

    ``None`` when no scope carries the item OR the library is unavailable —
    never raises (a broken/missing library degrades to the in-code constants)."""
    try:
        import prompt_library  # sidecar dir on sys.path — lazy, fault-isolated
        return prompt_library.resolve(group, key, cwd)
    except Exception:
        return None


def revise_system(scope: str | None, cwd: str | None = None) -> str:
    """The system prompt for a Revise scope (defaults to Grammar for unknown).

    Resolves through the §11 #45 prompt library (group ``revise``, item = the
    scope key; project scope for ``cwd``, then the shipped defaults), with the
    in-code ``REVISE_SYSTEMS`` constant as the non-empty fallback."""
    key = (scope or DEFAULT_SCOPE).lower()
    if key not in REVISE_SYSTEMS:
        key = DEFAULT_SCOPE
    return _library_text("revise", key, cwd) or REVISE_SYSTEMS[key]


def summarize_system(cwd: str | None = None) -> str:
    """The Summarize system prompt (§11 #45: group ``summarize``, item
    ``system``; in-code ``SUMMARIZE_SYSTEM`` as the non-empty fallback)."""
    return _library_text("summarize", "system", cwd) or SUMMARIZE_SYSTEM


def _text_of(message) -> list[str]:
    """Extract text from an SDK message (AssistantMessage.content blocks / str)."""
    parts: list[str] = []
    content = getattr(message, "content", None)
    if isinstance(content, str):
        parts.append(content)
    elif content:
        for block in content:
            t = getattr(block, "text", None)
            if isinstance(t, str):
                parts.append(t)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
    return parts


async def _one_shot(prompt: str, system_prompt: str, model: str | None = None) -> str:
    """Run a single non-interactive SDK pass and return the collected assistant
    text. Reserved for the two utility-LLM consumers (Revise / Summarize) only."""
    from claude_agent_sdk import query, ClaudeAgentOptions  # local import: sdk-only
    opts = ClaudeAgentOptions(
        system_prompt=system_prompt, model=model, max_turns=1,
        permission_mode="bypassPermissions",
    )
    parts: list[str] = []
    async for message in query(prompt=prompt, options=opts):
        parts.extend(_text_of(message))
    return "".join(parts).strip()


async def revise(text: str, scope: str = DEFAULT_SCOPE, model: str | None = None,
                 cwd: str | None = None) -> str:
    return await _one_shot(text, revise_system(scope, cwd), model)


async def summarize(text: str, model: str | None = None,
                    cwd: str | None = None) -> str:
    return await _one_shot(text, summarize_system(cwd), model)


async def handoff_report(text: str, model: str | None = None) -> str:
    """Distill a short structured handoff report from a transcript excerpt (§11 #16).

    A third utility-LLM consumer alongside Revise / Summarize — the summary that
    layers on Handoff's plain context carry-over (#15). Returns the report body."""
    return await _one_shot(text, HANDOFF_SYSTEM, model)
