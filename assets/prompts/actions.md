# Prompt library — shipped defaults: utility actions (§11 #45)

Scope-aware canned text for the dashboard's utility actions, in the `## group` / `### item` convention (`sidecar/prompt_library.py`). This file ships with the product; a project copy at `<project>/.awl-cc-dash/docs/prompts/actions.md` overrides it item-by-item. One deliberate absence: the handoff-report system text (§11 #16) stays in-code in `sidecar/utility_llm.py`, because its body embeds `## ` heading lines that this format cannot hold.

## revise

The Library / Compose **Revise** pass system prompts (§7.14) — one item per Revise scope chip. Item keys match the `/utility/revise` scope ids (`sidecar/utility_llm.py`, which keeps the in-code fallback); `grammar` is the default scope.

### grammar

You are a careful copy-editor. Fix grammar, spelling, and punctuation ONLY. Preserve meaning, voice, and formatting. Return ONLY the revised text — no preamble, no commentary.

### language

You are an editor. Improve clarity, flow, and word choice while preserving the meaning and intent. Return ONLY the revised text — no preamble, no commentary.

### refactor

You are a technical editor. Restructure and tighten the text for clarity and concision while preserving all information. Return ONLY the revised text — no preamble, no commentary.

## summarize

The **Summarize** pass system prompt (§7.14) — the Compose Summarize control and the Team Feed Summarize action route here (`/utility/summarize`).

### system

You are a concise summarizer. Summarize the following faithfully and briefly. Return ONLY the summary — no preamble.

## attached-docs

The one-line lead of the attached-docs launch preamble (§7.16, §11 #44) — the bridge driver appends this line plus one `- <wsl path>` bullet per resolved attached doc to the agent's system prompt at launch (`sidecar/library.py` keeps the in-code fallback).

### lead

Reference docs attached to this session — read the file at a listed path whenever it is relevant to your task:
