# Prompt library — shipped defaults: response formats (§11 #45)

Scope-aware canned text for the dashboard, in the `## group` / `### item` convention (`sidecar/prompt_library.py`). This file ships with the product; a project copy at `<project>/.awl-cc-dash/docs/prompts/responses.md` overrides it item-by-item. Prose like this paragraph (before the first `## `, or between a `## ` and its first `### `) is documentation space the parser ignores.

## response-structure

The per-agent Response (Structure) preset instructions (§7.14, §11 #39) — the chosen preset's text is appended verbatim to the agent's system prompt at launch. Item keys match the `sidecar/response_presets.py` catalog ids (that module stays the engine: menu labels/descriptions, validation, and the in-code fallback). The `default` preset is a hard engine-side no-op — nothing is appended — and deliberately has no item here.

### tldr_table

Response format for every reply:
- Open with a one-line TL;DR that states the outcome in plain language.
- When you report multiple items, statuses, or options, lay them out in a compact Markdown table rather than long prose.
- Use status emoji sparingly to mark state: ✅ done / good, ⚠️ needs attention, ❌ failed / blocked — at most one per row or line, never decoratively.
- Keep prose tight; prefer tables and short lines over paragraphs.
- Lead with the conclusion first, supporting detail after.

### concise

Response format for every reply: be concise. Open with a single one-line summary of the outcome, then give only the essential detail in as few words as clarity allows — no filler, no restating the request. Prefer short lines and lists over paragraphs.

### bullets

Response format for every reply: lead with a one-line summary, then present the substance as structured bullet points, grouped under short bold headings where that helps. Avoid long unbroken paragraphs.

### overview_first

Response format for every reply: open with a short, plain-language, high-level overview framed in outcomes — what happened or what you propose, understandable without technical background — and only then give the technical specifics. Lead with the one-line takeaway.

### narrative

Response format for every reply: write in plain running prose — clear, complete sentences in short paragraphs. Still open with a one-line summary sentence, but avoid tables and bullet-point scaffolding; explain in words.
