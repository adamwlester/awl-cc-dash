# Plan: Port the dashboard backlog to `design/TODO.md` (reformat only)

## Context

The `# Dashboard Add / Update Notes` section (lines 427–498 of
[dev/notes/human-notes-misc.md](dev/notes/human-notes-misc.md)) is a ui-concept backlog the user
maintains by hand (drop rough notes → an agent folds them into A–E). The earlier idea of a
restructured, multi-agent, status-spine backlog is **dropped as too complex.** Keep the doc exactly
as it is in scope and structure — just give it its own home and cleaner formatting.

Goal: move the section verbatim into a new **`design/TODO.md`**, with **clearer header labels** and
the agent-maintenance guidance reformatted into the clean blockquote style. **No content is
restructured, reordered, or rewritten** — same A–E sections, same items, same maintenance model.

## Changes

### 1. Create `design/TODO.md`

Port the whole section, applying formatting (not content) changes:

- **Title + guidance blockquote** at top: a `> **What** / **Maintained by**` block stating it's the
  ui-concept backlog for `design/ui-concept-v9p14.html` and that the user drops rough notes which an
  agent folds into the sections.
- **`## How agents maintain this list`** — the existing "For agents maintaining this list" bullets
  (Verify first / Format / Numbering / Group by effort / Loose notes), reformatted as a clean
  guidance blockquote. Wording preserved.
- **Clean section headers** — pull the descriptive subtitle out of each heading into its own
  one-line blockquote under it (the convention the user liked):
  - `## A — Next up` → `> Current work queue — priority order, mixed effort.`
  - `## B — Quick wins` → `> Small changes to the current mockup.`
  - `## C — Big picture` → `> Larger features needing real backend/runtime.`
  - `## D — Needs research / decisions` → `> Open questions to resolve before they become build items.`
  - `## E — Housekeeping & docs` → `> Maintenance, config, and documentation chores.`
- **Items A1–A2, B1–B2, C1–C27, D1–D5, E1–E7** — reproduced **exactly** (bold header + description,
  IDs unchanged). Plus the **Loose notes** bucket (incl. the "session → project" note) and the
  **Scratch** bullets, carried over verbatim under their own clean headers + blockquotes.
- **One factual fix:** the intro's stale path `agent-dashboard/design/ui-concept-v8pN.html` →
  `design/ui-concept-v9p14.html` (current authority per DEVLOG/CLAUDE.md). Flag this in the summary.

### 2. Remove the moved section from `dev/notes/human-notes-misc.md`

Delete lines 427–498 (the section through `## Scratch`, stopping before `# General notes`) and leave
a one-line pointer: `> Dashboard backlog moved to `design/TODO.md`.` Everything else in the file
stays byte-identical.

### 3. Clean up abandoned planning artifact

Delete `.claude/plans/todo-structure-example.md` (the now-moot mock) so it doesn't linger.

### 4. Log it

Append a `DEVLOG.md` entry (timestamp + 1–4 lines + `Files:`) recording the move + path fix.

## Files

- **New:** `design/TODO.md`
- **Edit:** [dev/notes/human-notes-misc.md](dev/notes/human-notes-misc.md) — remove section, add pointer
- **Delete:** `.claude/plans/todo-structure-example.md`
- **Edit:** [DEVLOG.md](DEVLOG.md) — append entry

## Verification

- Diff `design/TODO.md` items against original lines 440–498 — confirm every A–E item, ID, and
  description carried over verbatim; Loose notes + Scratch present; only intended change is the
  corrected `ui-concept-v9p14.html` path and the formatting/headers.
- Confirm human-notes-misc.md lost only that section and gained the pointer line.
- Docs only — no build/UI check needed. User reviews `design/TODO.md` and we edit from there.
