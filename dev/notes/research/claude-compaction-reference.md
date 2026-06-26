# Claude Compaction & Context-Editing Reference

Verified against official Anthropic docs (Compaction, Context editing, How Claude Code works) and the context-engineering cookbook, mid-2026. Entry 1 is the Claude Code CLI default. Entries 2-5 are API / Agent-SDK strategies that are **not** configurable through the Claude Code CLI or `settings.json` (open feature request #26215).

## Mental model

"Compaction" is not one operation. It is a family of context-management moves with different mechanics:

- **Summarize-and-replace** (compaction) is a hard boundary. Everything before the boundary collapses into one summary block; everything after continues verbatim. It is not an age gradient.
- **Clearing** (tool results, thinking blocks) is surgical and age-graded: drop the oldest, keep the N most recent, leave a placeholder so the model knows something was removed.
- **Memory tool** is external note-taking: durable state lives outside the context window.

These compose. A common pattern is clearing on a higher trigger plus compaction, so the two split the work.

---

## 1. Bare `/compact` (Claude Code CLI default)

**Label:** `/COMPACT DEFAULT` | **Surface:** Claude Code CLI interactive session (not the API strategy)

Running `/compact` with no argument summarizes the entire conversation into one dense summary and replaces the live context with it, with the model having full discretion over what to keep. Mechanically it clears older tool outputs first, then summarizes.

| | |
|---|---|
| **Kept** | Your requests, key code snippets, recent context |
| **Dropped or degraded** | Old tool outputs, early-session detail |

This is a fixed built-in behavior, **not** the parameterized `compact_20260112` strategy. There is no `trigger` / `keep` / `instructions` / `pause` param here.

**Steering levers (the only two):**

1. Inline argument, e.g. `/compact retain the error handling patterns and current test failures`.
2. A `Compact Instructions` section in `CLAUDE.md`, which persists and also applies to automatic compactions. This is the closest thing to a durable default override.

**Detection:** compaction emits a `compact_boundary` system message carrying `compact_metadata.pre_tokens` and `compact_metadata.trigger` (the `trigger` field distinguishes manual vs auto). Useful for a bridge/TUI driver that needs to observe compaction events.

**Related commands:** `/clear` wipes history entirely (context to zero); `/compact` preserves a summary. `/context` shows current token usage; `/rewind` (v2.1.191+) can undo a `/clear` and restore prior context.

---

## 2. Summarize And Replace

**Label:** `SUMMARIZE` | **Type:** `compact_20260112` | **Beta header:** `compact-2026-01-12`

Summarizes everything before a boundary into one block, drops the rest. **Age-graded:** No (hard boundary).

| Param | Default | Notes |
|---|---|---|
| `trigger` | 150K tokens | Minimum 50K |
| `instructions` | null | Replaces the default summary prompt entirely (does not supplement) |
| `pause_after_compaction` | false | Pauses after the summary so you can insert content (e.g. preserve recent messages verbatim) before continuing |

Summarization always uses the request's own model; there is no cheaper-model option. The docs ship a `pause_after_compaction` example that preserves the prior exchange plus the current user message (3 messages total) verbatim instead of summarizing them.

**Supported models:** Opus 4.6, 4.7, 4.8; Sonnet 4.6; Mythos 5, Fable 5, Mythos Preview.

---

## 3. Clear Old Tool Results

**Label:** `CLEAR TOOLS` | **Type:** `clear_tool_uses_20250919` | **Beta header:** `context-management-2025-06-27`

Drops old tool results in chronological order while keeping the record that the call happened; cleared content is replaced with placeholder text. **Age-graded:** Yes (keeps N most recent).

| Param | Notes |
|---|---|
| `trigger` | When to fire, e.g. `{type: input_tokens, value: 30000}` |
| `keep` | How many recent tool uses to retain, e.g. `{type: tool_uses, value: 3}` |
| `clear_at_least` | Minimum tokens to clear so cache invalidation is worthwhile |
| `exclude_tools` | Exempt specific tools (useful when the memory tool is active) |
| `clear_tool_inputs` | Set true to also clear the tool call inputs, not just results |

---

## 4. Clear Old Thinking Blocks

**Label:** `CLEAR THINKING` | **Type:** `clear_thinking_20251015` | **Beta header:** `context-management-2025-06-27`

Drops old extended-thinking blocks, optionally preserving recent ones. **Age-graded:** Yes (keeps N most recent, or `all`).

| Param | Notes |
|---|---|
| `keep` | e.g. `{type: thinking_turns, value: 2}` or `"all"` |

**Requirements:**

- Thinking must be enabled, or the API returns 400.
- Must be the **first** entry in the `edits` array when combined with tool clearing, or the API returns 400.

Tip: setting `keep: "all"` is sometimes used deliberately to prevent thinking-block removal from invalidating the KV cache on cache-eligible turns.

---

## 5. External Memory Tool

**Label:** `MEMORY` | **Type:** `memory_20250818` | **Beta header:** `context-management-2025-06-27`

Writes durable notes to external storage instead of holding everything in-context. **Age-graded:** N/A (external). Passed as a **tool** (`type: memory_20250818`), not as a `context_management` edit.

Note: confirm current model support before relying on it; the published support list predates the latest Opus releases.

---

## Operational gotchas

- **Tool-call failure during summarization.** When tools are defined, the model occasionally calls a tool during the internal summarization step instead of writing a summary, yielding a compaction block with `content: null`. Fix: set `instructions` that explicitly forbid tool calls (respond with text only).
- **Usage accounting.** Top-level `input_tokens` / `output_tokens` exclude the compaction iteration. To get the true billed total, sum across `usage.iterations`. Re-applying an existing compaction block incurs no new compaction cost.
- **Prompt caching.** Clearing invalidates cached prefixes, so clear enough tokens (`clear_at_least`) to make it worthwhile. For compaction, add a `cache_control` breakpoint at the end of the system prompt so the system prompt stays cached separately and only the new summary is written to cache.
- **Thrashing stop.** If a single file or tool output is so large that context refills immediately after each summary, Claude Code stops auto-compacting after a few attempts and shows an error instead of looping.
- **Block pairing.** Compaction and clearing never split a `tool_use` from its matching `tool_result`; that pairing is preserved across the boundary.

---

## Claude Code coarse levers (the CLI surface)

Since entries 2-5 are not exposed in the CLI, the only knobs on the Claude Code surface are:

| Lever | What it does | Caveat |
|---|---|---|
| `/compact [instructions]` | Steer what a manual compaction keeps | Per-call only |
| `CLAUDE.md` Compact Instructions section | Persistent preservation policy, applies to auto-compaction too | Durable but coarse |
| `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` | Set auto-compaction threshold (decimal 0-1) | Lower-only; capped around 0.83 due to a Math.min bug |
| `PreCompact` hook | Conditional blocking and state capture before compaction fires | The main programmatic lever; use `async: true` |

Disabling auto-compaction outright (`autoCompactEnabled: false`, `DISABLE_AUTO_COMPACT`) is reported as unreliable across versions. Best-practice guidance is to compact intentionally around 60% utilization rather than waiting for the late auto-trigger, since a summary built from clean context is higher quality than one built from an already-degraded view.

---

## Driver implication (two-driver architecture)

- **SDK / sidecar driver** (direct Messages API or Agent SDK): can use entries 2-5 with full parameter control. This is where rich, typed compaction controls belong in a UI.
- **tmux / bridge driver** (Claude Code CLI): gets only entry 1 plus `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE` and the `PreCompact` hook. Observe-and-nudge, not fine control. A project `memory.md` pattern is the practical substitute for the durable-state job the CLI will not expose knobs for.

---

## Sourcing and confidence

- **Official (high confidence):** the clear-then-summarize ordering, keep/drop behavior, all API strategy types and their parameters, beta headers, the two 400 requirements for `clear_thinking`, the usage-accounting and tool-call-failure gotchas, the `compact_boundary` metadata.
- **Community reverse-engineering (treat as plausible, not version-stable):** the internal tiering (Session Memory then Microcompact then Traditional Compaction) and the roughly nine-section default summary schema (Current State, Goals, Recent Changes, Key Decisions, Active Work, Key Files, Learnings, Important Context, Next Steps). The exact default summary prompt is not published; capture it by running `/compact` on a throwaway session and reading the summary block.
