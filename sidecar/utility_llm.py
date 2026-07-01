"""OD-16 utility-LLM passes (Revise / Summarize) — the `sdk`-driver carve-out.

Exactly **two** consumers use the `sdk` engine: **Revise** (scope chip
Grammar · Language · Refactor, default Grammar) and **Summarize**. Both run as
non-interactive **one-shot** passes via the in-process Claude Agent SDK `query()`
— NOT the bridge. Everything else multi-agent (stream, queue, hooks, console,
scratchpad, linking, Plan/Decision detection) stays on the bridge.
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

DEFAULT_SCOPE = "grammar"


def revise_system(scope: str | None) -> str:
    """The system prompt for a Revise scope (defaults to Grammar for unknown)."""
    return REVISE_SYSTEMS.get((scope or DEFAULT_SCOPE).lower(), REVISE_SYSTEMS[DEFAULT_SCOPE])


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
    text. Reserved for the two OD-16 consumers only."""
    from claude_agent_sdk import query, ClaudeAgentOptions  # local import: sdk-only
    opts = ClaudeAgentOptions(
        system_prompt=system_prompt, model=model, max_turns=1,
        permission_mode="bypassPermissions",
    )
    parts: list[str] = []
    async for message in query(prompt=prompt, options=opts):
        parts.extend(_text_of(message))
    return "".join(parts).strip()


async def revise(text: str, scope: str = DEFAULT_SCOPE, model: str | None = None) -> str:
    return await _one_shot(text, revise_system(scope), model)


async def summarize(text: str, model: str | None = None) -> str:
    return await _one_shot(text, SUMMARIZE_SYSTEM, model)
