# Restructure the `## Behavioral rules` section in CLAUDE.md

## Context

The project `CLAUDE.md` (`c:\Users\lester\MeDocuments\AppData\Anthropic\awl-cc-dash\CLAUDE.md`) ends with a `## Behavioral rules` section that is one flat list mixing five unrelated concerns — safety/scope, communication style, scratch artifacts, DEVLOG bookkeeping, editing discipline, and a UI-test procedure. The list is also uneven: two of the items (DEVLOG logging, DEVLOG rotation) and two more (preserve-untouched, UI verification) are paragraph-length, while the rest are one-liners. That makes the section hard to scan and hard to find a specific rule in.

Two concrete problems found during exploration:
- **DEVLOG rules are duplicated.** The two fat DEVLOG bullets restate the format + rotation procedure that already lives — near-verbatim — in the `DEVLOG.md` header (lines 3–15). Both bullets even point there ("Full rules live in the DEVLOG header"). Two copies will drift.
- **UI verification has no other home.** `design/DESIGN.md` covers design *intent*, not the testing *procedure*, so that rule is genuinely standalone — it just doesn't belong inline with one-liners.

**Outcome:** the same rules, grouped by concern under `###` subsections, easier to scan and maintain, with DEVLOG tightened (intent fully preserved) so the `DEVLOG.md` header stays the source of truth for the fine print.

## Decisions (confirmed with user)

- **Organization:** keep a single `## Behavioral rules` heading; add `###` subsections beneath it.
- **DEVLOG:** keep the same intent as today — reorganize and tighten wording, but do **not** drop any substance (trigger, default-to-logging bar, format, append-only rule, rotation thresholds + procedure).
- **UI verification:** stays in CLAUDE.md as its own `###` subsection (not moved to a separate doc).

## The change

One file edited: `CLAUDE.md` — replace the entire current `## Behavioral rules` list with the structured version below. No other files change. This is a pure reorganization: every rule's intent is carried forward; nothing is added or removed in substance.

Five subsections, mapping the existing bullets:

| Subsection | Absorbs current bullets |
|---|---|
| `### Scope & safety` | "stay inside project directory", "global config — explain first" |
| `### Working style` | "direct, low-ceremony", "transient artifacts → `.scratch/`" |
| `### Editing discipline` | "preserve everything you weren't asked to change" |
| `### DEVLOG — project memory` | the two DEVLOG bullets (logging + rotation), compressed, intent intact |
| `### Verifying UI changes` | the UI-verification rule + its headless/headed sub-bullet |

### Proposed replacement text

```markdown
## Behavioral rules

### Scope & safety
- Stay inside the project directory for all operations unless explicitly told otherwise.
- When touching global config (`~/.claude/`, etc.), explain the change before making it.

### Working style
- Be direct, practical, low-ceremony. Lead with action, follow with a brief explanation.
- Write all transient artifacts (screenshots, scratch HTML, debug dumps, ad-hoc server logs) into `.scratch/` — never the repo root or other project folders. Prefix any `filename` you pass to screenshot/export tools with `.scratch/`. One-off files may be deleted when done; accumulation in `.scratch/` is acceptable.

### Editing discipline
- **Preserve everything you weren't asked to change.** When you edit a file or produce a new version of an existing artifact (for example, a new UI mockup branched from the prior one), reproduce the untouched parts exactly as they were. Carrying them forward in full is real work, and that work is part of the task: don't skip, summarize, simplify, restyle, or drop sections just because faithfully reproducing them is tedious. The usual failure here is cutting corners, not over-editing, so when in doubt, keep the prior version intact. Before finishing, look back over the result and confirm nothing outside the requested change was lost or quietly altered.

### DEVLOG — project memory (not optional)
`DEVLOG.md` is the project's memory; an unlogged change is, to the next session, a change that never happened.
- **Log every repo change.** Before you end any turn in which you created, deleted, moved, or meaningfully edited a file (code, config, docs, or design) — and before you tell the user you're "done" — append a new entry at the **bottom** of the Log (it runs oldest → newest). Default to logging: the bar is "did the repo change?", not "was it significant?" — if you're unsure, it qualifies.
- **Format** (append-only; never edit or delete past entries — the Status block is the only in-place exception): a `### YYYY-MM-DD HH:MM:SS — short title` heading, 1–4 lines on what changed and the observable outcome, then a `Files:` line.
- **Rotate when long.** Past ~700 lines, move the oldest entries (top of the Log) **verbatim** — cut only at `### ` headings, never mid-entry — into the newest `archive/devlog/DEVLOG-archive-NN.md`, appending in order, until `DEVLOG.md` is back under ~300 lines; then refresh the digest + index row in **Archived history**. Never edit archived entries.
- Full rules and the rotation procedure live in the `DEVLOG.md` header — follow those.

### Verifying UI changes
- **Drive the rendered UI — never hand back on static checks alone.** For anything that renders (the dashboard mockups above all), `node --check` / grep / reading the diff is necessary but NOT sufficient — it says nothing about layout, wrapping, overflow, or whether a control actually works.
- **Before you call a UI change done:** open it in a browser (serve over `http://localhost` — the Playwright MCP browser blocks `file:`), **resize the affected panel(s) to both narrow and wide extremes** (this layout is resizable, and that's where it breaks), and **click through every control you touched** — expand/collapse, toggles, each dropdown/menu, the whole flow. Screenshot each state, compare it to the stated intent, and fix what's off — all before reporting back.
- **Iterate headless; finish with one headed pass.** Run the Playwright MCP browser `--headless` for the whole resize/click/screenshot loop so it doesn't steal focus or windows. Then, once the change looks done, do a **single headed pass** to confirm the rendering is identical to what you saw headless. This headed parity check is a **hard rule, not a judgment call** — run it for every UI change, not only when you suspect a difference. Keep it light: re-screenshot the touched states at the narrow and wide extremes and compare; it interferes only briefly, once, at the very end.
```

## Notes on intent preservation

- Every behavioral mandate from the current list survives. The DEVLOG subsection keeps: the "memory / unlogged = never happened" framing, the precise logging trigger, the "default to logging / did the repo change?" bar, the exact heading + `Files:` format, the append-only rule with the Status-block exception, and the full ~700→~300-line rotation procedure with verbatim-cut-at-`###` detail.
- Only wording is tightened; no thresholds, paths, or conditions are changed.

## Verification

This is a docs-only edit — verify by reading, not by running code:
1. Re-read the new `## Behavioral rules` section top-to-bottom and confirm each of the original eight bullets is represented (use the mapping table above as a checklist).
2. Diff the old vs new section and confirm no rule's *substance* was dropped — only grouping and wording changed.
3. Confirm the DEVLOG subsection's rotation thresholds (~700 / ~300) and format string match the `DEVLOG.md` header exactly (lines 9 and 15).
4. Per the DEVLOG rule itself: append a dated entry to `DEVLOG.md` recording this CLAUDE.md edit before finishing.
```
