# AWL Agent Platform — Project Log

> **For Claude sessions:**
>
> Read this file top-to-bottom before making changes to the codebase. This file is **100% append-only** — current state is re-derived from recent entries (the latest entry touching an area is its current truth); forward intent / next steps live in `TODO.md` and planning, not here.
>
> **Log** — append-only, ordered **oldest → newest** (oldest entry at the top of the Log, newest at the bottom). Every entry's heading MUST begin with a timestamp in `YYYY-MM-DD HH:MM:SS` (24-hour clock, to the second). **Add a new entry at the BOTTOM of the Log before you end any turn that changed the repo** — created, deleted, moved, or meaningfully edited any file (code, config, docs, or design) — and before you report "done." **Default to logging:** the bar is "did the repo change?", not "was it big?" Don't let the log fall behind the code (it has happened before). If you discover something was wrong, add a new correction entry — don't edit the old one. **Template:** a `### YYYY-MM-DD HH:MM:SS — short title` heading, 1–4 lines (what changed + the observable outcome), then a `Files:` line.
>
> **General** — never strike out, rewrite, or delete existing entries in the Log. There are no in-place-editable sections; if something was wrong, add a new correction entry.
>
> **Scope** — this log covers the entire workspace: bridges, backend, dashboard design, frontend, tooling, and infrastructure. Projects under `projects/` maintain their own logs.
>
> **Rotation** — when this file grows past **~700 lines**, archive the oldest entries to keep it small. The oldest entries are at the **top** of the Log (this file is oldest → newest), so cut from the top: move them **verbatim** (cut only at `### ` headings, never mid-entry) into the newest `archive/devlog/DEVLOG-archive-NN.md`, appending in order, until this file is back under **~300 lines**; then refresh the digest + index row in **Archived history** at the bottom. Each archive file is itself oldest → newest. Never edit moved entries.

---

## Log

> This file is the **recent window**. Older entries (2026-03-26 → 2026-06-21 08:20, including all `[Reconstructed]` history) have been rotated into `archive/devlog/` — see **Archived history** below.

### 2026-06-21 08:33:22 — Sidecar driver seam (#1) + frontend render fix; live end-to-end verified

**#1 driver seam:** refactored the SDK-coupled sidecar onto a pluggable `AgentDriver` interface (`sidecar/drivers/{base,sdk,bridge}.py` + factory). `sdk` stays the default (behavior unchanged); `bridge` is a new selectable driver (`AWL_DRIVER=bridge` or per-session `driver`) that runs a real Claude Code TUI via the tmux bridge, polling the JSONL transcript → events (transcript blocks already carry Anthropic `.type`). Serialization moved to `sidecar/serialize.py` (carries the block-type fix); `main.py` is now driver-agnostic and `/health` reports the active driver.

**Frontend render fix (caught by the rendered-UI check, not the API test):** the renderer read assistant content from `event.data.message.content`, but the sidecar emits `content` at the event top level — so cards never appeared even after the block-type fix. Fixed `App.tsx` EventRenderer to read `event.content` (with the old shape as fallback). This was the *actual* reason the MVP showed no output.

**Verified live end-to-end:** installed sidecar deps into `.venv` + `npm install` the frontend; ran the live sidecar (7690, sdk driver) + the electron-vite renderer; created a session and sent a prompt — the agent used Glob/Grep/Read and the feed rendered tool-call cards, tool-result cards, and the assistant text answer, with the cost/turns result bar. Checked narrow (680px) + wide (1800px): no overflow; expand/collapse works; no console errors. Driver-seam unit checks (factory selection, bridge transcript mapping) pass. The bridge driver is implemented but its live WSL/tmux path is not yet end-to-end verified.

Files: added sidecar/serialize.py + sidecar/drivers/{__init__,base,sdk,bridge}.py; rewrote sidecar/main.py (driver-agnostic); fixed frontend/src/renderer/App.tsx (event.content)

### 2026-06-21 09:30:00 — Dashboard mockup v9p14: Plan-card resize fixes, turns bars, labels, delineation
Branched ui-concept-v9p14.html from v9p13 (full copy → targeted edits; everything else preserved) and worked a 14-item handoff with emphasis on resize/layout that needs live testing. Headline fixes (all verified in headless Chromium): (A1) the Plan nav is now a flex column that stretches to the text column's height, so the feedback cards aren't clipped when the comment UI opens — measured nav 358→487px on open, with the list scrollbar flush to the nav edge (gap 0); widened to 212px so each card's verdict + section badges sit side by side. (A2) a neutral Copy·Edit·Comment strip now sits under the text box with the comment popout/composer opening BETWEEN the text and the strip (popAboveStrip verified). (A3) footer Share·Review left / Revise·Reject·Approve right, labels sized to match. (A4/A5) selected text highlights light pink; left rail cells color-coded (pink title = select-all, dark teal section, light teal line) with re-click-to-clear (toggle + select-all logic verified). (A12/A13) agent cards + the Agent panel show TURNS as a labeled health bar (panel "History"→"Turns" with inline count·bar·%, then Rewind/Handoff). (A8/A11/A14) Mode FREE!→Bypass; Thinking→Thoughts, Metadata→Meta; full-width "Opus fast-mode"/"Thinking mode" toggles. (A10) count badges squared. (A7) resize-nub removed, 3px navy panel dividers. (A9) proposed a slash-command approach (Compose palette scoped by Target) in the changelog. All script blocks parse. Files: agent-dashboard/design/ui-concept-v9p14.html (new)

### 2026-06-21 12:00:00 — Folded loose notes into dashboard "Next up" (A1–A14)
Cleaned 16 loose notes against ui-concept-v9p13.html into Section A of docs/human-notes-misc.md as A1–A14 (numbered, bold-headered). Dropped 2 as already implemented: doc rail line/section indexing (v9p12) and flat non-interactive badges (v9p13). Loose notes bucket emptied; Scratch left untouched. Files: docs/human-notes-misc.md, DEVLOG.md

### 2026-06-21 13:10:00 — Dashboard v9p14 tweaks (Plan footer regroup, nav-card selection) + README sync
Three in-place tweaks to ui-concept-v9p14.html, each verified live in headless Chromium: (1) the Plan action strip is now FULL-WIDTH (spans under the nav pane + text), with Copy·Edit·Comment left and Share·Review pulled up from the footer and right-aligned; the footer below the divider is just the decision trio (Revise·Reject·Approve, right). (2) Feedback nav cards are now selectable like other cards — light-teal fill that persists until you deselect (re-click) or close the popout, and selecting one highlights its section in the plan text (teal, linking card↔text); verified select/toggle/close + that the nav still resizes with the comment UI (320→449px). (3) removed the nav's horizontal overflow at the root (cards were width:100% + 7px margin → overflowed; set width:auto), so no horizontal scrollbar. Then synced agent-dashboard/README.md to current design intent: mockup pointer v9p4→v9p14; rewrote the layout note; Team Graph now describes the dual Turns+Ctx labeled bars; Agent panel Mode Bypass + the "Opus fast-mode"/"Thinking mode" toggles + the Turns readout; Feed Messages toggles →Thoughts/Meta; added a full **Documentation (middle, bottom)** panel section (doc editor, plan review system, nav rail, comment popout, action strip + decision footer, Inbox cross-link); and design-system notes for the 3px panel dividers (grip nub removed), rounded-square + flat badges, and the pink/teal selection roles. Files: agent-dashboard/design/ui-concept-v9p14.html, agent-dashboard/README.md

### 2026-06-21 13:30:00 — Refreshed dashboard "Next up" against v9p14 (A1–A2)
Cleared old A1–A14 (all implemented in ui-concept-v9p14.html per its changelog) and folded 2 new loose notes into Section A of docs/human-notes-misc.md: A1 Plan Footer Grouping, A2 Nav Card Selection. Loose notes bucket emptied; Scratch left untouched. Files: docs/human-notes-misc.md, DEVLOG.md

### 2026-06-21 14:20:00 — Dashboard v9p14: Plan footer back to one strip, Comment→button, 3-indicator sync
Reverted the separate upper action strip (the grouping wasn't working): **all plan actions live in the one shared footer again** — Copy · Edit · Comment · Share · Review left-aligned, the decision trio (Revise · Reject · Approve) right-justified; wraps to a 2nd row on the narrow Documentation column (verified). The **Comment** control is now a plain icon button (the upload action + verdict split are gone); the verdict moved INTO the composer as a **"Mark as" dropdown** (Approve/Revise/Block, color-coded) — Save reads it. Made the three feedback indicators move in lockstep: openCmtPop is the single sync point, so selecting a Feedback card OR clicking the in-text rail-gutter badge fills the card (teal) + highlights its section (teal) + opens the popout; closing/deselecting clears all three; a different comment switches all three (added data-fbsec/fbverdict + selectMatchingCards; verified from both entry points incl. switch + toggle). Synced the README Documentation bullets (shared footer, Comment button + Mark-as dropdown, the linked three-indicator selection). All script blocks parse. Files: agent-dashboard/design/ui-concept-v9p14.html, agent-dashboard/README.md

### 2026-06-21 14:30:00 — Removed root-README to-do notes (decided not needed; CLAUDE.md covers it)
Per decision that no root README is needed (CLAUDE.md handles orientation), cleaned the root-README to-dos from dev/notes/repo-migration.md: dropped README.md from the target tree, repointed the design-reference mapping to design/DESIGN.md (its actual home), and marked the "README handling" open question RESOLVED (design/DESIGN.md; no root README). Left legit references to other READMEs (tests/, bridge/, context-extractor, the dashboard's readme-reading feature) untouched. Files: dev/notes/repo-migration.md, DEVLOG.md

### 2026-06-23 18:11:14 — CLAUDE.md currency: driver seam + working-MVP labeling

Brought CLAUDE.md's Folder map in line with reality before a bridge-streaming handoff to another agent. Sidecar row now describes the **driver seam** (`drivers/` base/sdk/bridge + `serialize.py`; `sdk` default, `bridge` selectable via `AWL_DRIVER`, not yet live-verified) instead of the stale "SDK-direct; bridge swap planned." Labeled root `frontend/`+`sidecar/` as the **working MVP** (built in place) and `archive/mvp/` as the **frozen original** (do not edit). Also refreshed the Status block. This commit additionally sweeps in in-flight user edits: `dev/notes/human-notes-misc.md` and the move of `dev/notes/repo-migration.md` → `archive/dev/notes/`.

Files: edited CLAUDE.md, DEVLOG.md (+ user edits: dev/notes/human-notes-misc.md, dev/notes/repo-migration.md → archive/dev/notes/)

### 2026-06-23 20:08:14 — Fixed vibe-guide plan-mode tools by removing its tools allowlist
Diagnosed the recurring "question and plan-exit tools are disabled in this context" complaint: not the plansDirectory move (`.claude/plans` works — plans write fine), but the project default agent. `.claude/settings.json` sets `agent: vibe-guide`, and that agent's frontmatter had an explicit `tools:` allowlist that omitted `AskUserQuestion` and `ExitPlanMode` (an explicit list disables everything not named). Deleted the `tools:` line so vibe-guide inherits all tools — plan mode now has its question/exit tools. Left echo.md's restricted list intact (intentional read-only distiller, not a main agent). Files: .claude/agents/vibe-guide.md, DEVLOG.md

---

### 2026-06-23 21:02:14 — Synced frozen `archive/mvp/` to behavioral parity with the working root MVP

Brought the frozen reference up to date with the root `frontend/`+`sidecar/` build so it runs and renders the same — the archive previously carried the two known render bugs (content blocks lost their `type`; renderer read the wrong content path), so tool-call/text/thinking cards never appeared. Diffed both trees: deps (`requirements.txt`), lockfiles, and all build configs were already identical; the only behavioral gaps were the sidecar serialization/driver-seam and the `App.tsx` content path. This task authorized editing `archive/mvp/` (normally do-not-edit); nothing outside it changed.

**Ported into `archive/mvp/` (verbatim from root):** `sidecar/serialize.py` (the `_BLOCK_TYPE_MAP` type injection) and the whole `sidecar/drivers/` package (`__init__`, `base`, `sdk`, `bridge`). Replaced the old monolithic SDK-coupled `sidecar/main.py` with root's driver-agnostic v0.3.0 main. Applied the `App.tsx` EventRenderer fix in both spots (read flattened `event.content`, fall back to `event.data.message.content`). **Kept the archive's port 7691** in all three spots (sidecar uvicorn, preload `sidecarUrl`, App.tsx fallback) — final diff vs root is *only* those three port lines; every other source file is byte-identical. Updated `archive/mvp/README.md`: sidecar description now reflects the driver seam (with a note that the `bridge` driver's repo-root `bridge` package isn't bundled in this frozen copy), and the "render gap" known-limitation was replaced with a "Parity with the live build" section.

**Verified it runs (port 7691):** sidecar imports clean (`AWL Dashboard Sidecar 0.3.0`, default driver `sdk`); `/health` ok. End-to-end via API (opus, bypassPermissions): a Glob+Bash prompt produced typed content blocks — `thinking` / `tool_use` / `text` / `tool_result` — plus the result bar (cost/turns/duration). **UI driven via Playwright** over the built renderer (`electron-vite build` → served static at :5180, sidecar :7691): the feed renders session-init, Glob/Bash tool-call cards, thinking, tool-result, the assistant text answer, and the result bar — i.e. the previously-broken cards now appear. Resized to 680px (no overflow, clean wrap) and 1800px (holds); exercised the collapsible Session-init card and the "Show all (101 lines)" toggle (both work); did a live UI send ("PONG") that streamed and rendered with a fresh result bar + updated session cost. Only console noise is the favicon 404. Note: the Playwright MCP browser's headless/headed mode is fixed at server launch (not switchable per call), so iteration + the final narrow/wide re-screenshot parity pass ran through that single configured browser. Background sidecar/static servers were torn down after; the `out/` build artifact is gitignored.

Files: added archive/mvp/sidecar/serialize.py + archive/mvp/sidecar/drivers/{__init__,base,sdk,bridge}.py; rewrote archive/mvp/sidecar/main.py (driver-agnostic, port 7691); edited archive/mvp/frontend/src/renderer/App.tsx (event.content, ×2); edited archive/mvp/README.md; DEVLOG.md

### 2026-06-23 21:19:41 — Moved dashboard backlog into `design/TODO.md`

Ported the `# Dashboard Add / Update Notes` backlog out of `dev/notes/human-notes-misc.md` into a new `design/TODO.md` — same ui-concept scope, same A–E structure and items, same hand-maintained loose-notes→section workflow. Reformatting only: clean header labels (descriptive subtitles pulled into their own one-line blockquotes) and the agent-maintenance guidance rendered as a blockquote. One factual fix: the stale intro path `agent-dashboard/design/ui-concept-v8pN.html` → current authority `design/ui-concept-v9p14.html`. Left a one-line pointer where the section used to live; deleted the abandoned `.claude/plans/todo-structure-example.md` mock.

Files: `design/TODO.md` (new), `dev/notes/human-notes-misc.md` (section removed + pointer), `.claude/plans/todo-structure-example.md` (deleted), `.claude/plans/i-need-your-help-nested-island.md` (plan)

### 2026-06-23 21:25:45 — Clarified `design/TODO.md` intent (reference-only + loose-note filing)

Added a top "⚠ Reference only — do not work from this unless explicitly directed" warning so agents don't implement entries or treat them as confirmed/approved without the human handing over a specific item; reworded the "How it's used" note to spell out the capture → file → cut-into-prompt flow. Also clarified the Loose-notes guidance (both the maintenance rule and the section blockquote): file each note into the best-fit section by topic/effort, or whatever section the human names.

Files: `design/TODO.md`

### 2026-06-23 21:29:33 — CLAUDE.md: archive/mvp now "reference MVP at parity"; committed the sync

Follow-up to the parity sync below. Updated CLAUDE.md's folder map: `archive/mvp/` is now described as the **frozen reference MVP** "kept at behavioral parity with root — only its port differs, 7691" instead of the **frozen original MVP**, since its sidecar is no longer the literal pre-driver-seam original (the "do not edit" instruction is unchanged). Committed this session's `archive/mvp/` parity changes + the two doc updates as one commit on `main`; left unrelated in-flight edits (`.claude/plans/*`, `dev/notes/human-notes-misc.md`, `design/TODO.md`) unstaged. Not pushed.

Files: CLAUDE.md, DEVLOG.md

### 2026-06-23 21:32:08 — Unwrapped hard line breaks in `design/TODO.md` blockquotes

Per user preference: collapsed the mid-sentence hard-wraps in the guidance blockquotes (top warning, What/How-it's-used, the maintenance rules, Loose-notes note) so each logical statement is a single line — easier to edit. No content changed; section subtitles and numbered items were already one line.

Files: `design/TODO.md`

### 2026-06-23 22:23:13 — DEVLOG rotation: archived the sandbox-era block; added a size-based rotation rule

Stood up size-triggered log rotation so this file stops eating session context (it had reached ~2,178 lines / ~34K tokens, and CLAUDE.md tells every agent to read it). Moved the 21 pre-2026-06-13 `[Reconstructed]` sandbox-era entries (2026-03-26 → 06-13 04:43) **verbatim** into a new `archive/devlog/DEVLOG-archive-01.md`; DEVLOG.md went 2,178 → 2,012 lines. (Those entries are short, so this safe first cut is a modest trim — establishing the mechanism, not the size drop, is the win this pass; the bulk weight is the recent verbose dashboard entries.) Entry conservation verified: 131 carried + 21 archived = the original 152. Added a **Rotation** rule to the header (archive oldest verbatim when >~700 lines, down to ~300) and an **Archived history** digest + index at the bottom; updated CLAUDE.md (Key Files row + a Behavioral rotation bullet) so agents read the recent window by default and open archives on demand. The file's older interleaved-ordering tangle (two concatenated logs) was left untouched — only the clearly-old reconstructed block was rotated.

Files: DEVLOG.md, archive/devlog/DEVLOG-archive-01.md (new), CLAUDE.md, .claude/plans/our-devlog-md-is-getting-merry-wirth.md

### 2026-06-23 22:36:54 — Reordered the Log to a single oldest → newest timeline

Fixed the log's split ordering. The file had two stretches in opposite directions — a newest-first block prepended on top and the original oldest-first block below — so same-day entries sat at both ends. Sorted all 132 entries by timestamp into one **oldest → newest** timeline (oldest at the top, newest at the bottom); entry text untouched, heading multiset identical before/after (132 = 132), uniform CRLF. Lifted the reconstruction note to a preamble at the top of the Log. Updated the instructions to match in both the DEVLOG header and CLAUDE.md: the **Log** is declared oldest → newest, **new entries append at the bottom**, and **Rotation now cuts from the top** (the oldest end). The archive (`DEVLOG-archive-01.md`) was already oldest → newest and its range still sits cleanly before this file's first entry — left as-is.

Files: DEVLOG.md, CLAUDE.md

### 2026-06-23 22:43:37 — First real size rotation: trimmed the Log to a ~300-line recent window

Ran the rotation rule for real now that the Log is a clean oldest → newest timeline. Cut from the top: moved the oldest 117 entries (2026-06-13 07:50 → 2026-06-21 08:20) **verbatim** into a new `archive/devlog/DEVLOG-archive-02.md`, keeping the 16 newest (2026-06-21 08:33 driver-seam keystone onward). DEVLOG.md went 2,031 → ~300 lines; entry conservation verified (117 archived + 16 kept = 133, and 21 + 117 + 16 across both archives + this file = every entry accounted for). Added the archive-02 digest + index row to **Archived history**, and replaced the now-stale reconstruction preamble (its `[Reconstructed]` entries moved to the archives) with a one-line pointer. Both archive files are oldest → newest and their ranges chain cleanly (…06-13 04:43 | 06-13 07:50… | 06-21 08:20 | 06-21 08:33…).

Files: DEVLOG.md, archive/devlog/DEVLOG-archive-02.md (new)

---

### 2026-06-24 00:22:10 — Bridge backend foundation: trustworthy run-state, startup gates, context/turns

Wired the proven bridge capabilities (from the 06-23 diagnostic) through into reliable run-state. Rewrote `_detect_state` to read the bottom status bar instead of the always-"idle" input line: a turn is **generating** when the animated spinner line is present (a sparkle-glyph line ending in an ellipsis, e.g. "✻ Percolating…", and/or "esc to interrupt"); **idle** when the input box is rendered (rule + ❯) and not generating; **permission_prompt** only when the real menu marker ("Do you want …?" + a numbered "1. Yes") is present — killing the old keyword false-positives. `create()` now clears the startup gates (folder-trust always; bypass-mode via `keys("2")`+Enter when present) and waits for genuine idle before returning. Added `derive_context_usage()` (pure: overall context tokens/percent over a 1M window + string-content turn count) to the bridge driver, wired `get_context_usage()`, and added "context" to its `CAPABILITIES` so the `/context` endpoint serves it. Two live findings beyond the diagnostic, both captured as hermetic regression tests: in normal (non-bypass) mode "esc to interrupt" is clipped so the spinner glyph is the real signal, and the completed-turn summary line ("✻ Cooked for 1s") reuses the glyph without an ellipsis — hence the ellipsis requirement. 15 hermetic unit tests (no live env) pass; full live `test_tmux_bridge.py` green (29 passed), including a turn streaming generating→idle and a fresh untrusted dir coming up to idle with the gate cleared. Permission approve/deny, model/mode switching, and restart recovery are deliberately left for the next pass.

Files: bridge/bridge.py, sidecar/drivers/bridge.py, tests/test_bridge_unit.py (new), tests/test_tmux_bridge.py

---

### 2026-06-24 00:50:19 — Design-docs refactor prompt authored

Wrote a single-pass agent prompt to refactor the `design/` docs into a maintainable, single-source structure: a new `tokens.css` (sole source of truth for all design values incl. the 16 agent colors), the mockup renamed `ui-concept-v9p14.html` → `mockup.html` (consuming `tokens.css` via `<link>`), `design-tools.js` → `mockup-toolkit.js`, and `DESIGN.md`'s design-system section reduced to rules-only with values deferred to tokens. Prompt grants the agent freedom to restructure the docs but holds `mockup.html` appearance/behavior faithful to the source (hard render-gate), and bounds scope to `design/` only (no `frontend/`/`sidecar/` token-sync — that's deferred). No refactor executed yet; this is the brief. Planning discussion captured the file-set, naming, and freedom/constraint split.

Files: dev/prompts/design-docs-refactor.md, .claude/plans/i-am-trying-to-merry-blanket.md

---

### 2026-06-24 01:00:38 — Unwrapped hard line breaks throughout CLAUDE.md

Per user preference (moving away from hard-wrapped markdown, which is painful to edit), reflowed every hard-wrapped paragraph and list item in `CLAUDE.md` to single continuous lines, letting the editor soft-wrap (`editor.wordWrap` already on). Headings, both folder-map tables, code blocks, the nested sub-bullet under the UI-verification rule, blank lines, and all wording/punctuation preserved exactly — only mid-sentence newlines removed.

Files: CLAUDE.md

---

### 2026-06-24 01:08:32 — Unwrapped hard line breaks in DESIGN.md and DEVLOG.md

Continued the move away from hard-wrapped markdown (after CLAUDE.md): reflowed every hard-wrapped paragraph, list item, and blockquote in `design/DESIGN.md` and `DEVLOG.md` to single continuous lines. Done with a one-pass unwrap script guarded by a char-stream invariant (only whitespace + blockquote-continuation `>` markers removed — verified the non-whitespace character stream was byte-identical before/after). Preserved exactly: headings, all tables (incl. the indented Trigger/Payload tables under list items), the ASCII layout diagram in its code fence, ordered/nested lists, blockquote internal blank lines, and each file's line endings (DESIGN = LF, DEVLOG = CRLF).

Files: design/DESIGN.md, DEVLOG.md

---

### 2026-06-24 01:12:32 — Unwrapped hard line breaks in the DEVLOG archives

Extended the markdown unwrap to the rotated history: reflowed `archive/devlog/DEVLOG-archive-01.md` and `DEVLOG-archive-02.md` to single continuous lines, same char-stream-guarded one-pass script (non-whitespace bytes verified identical before/after) and CRLF endings preserved. These are immutable archives, but this is a whitespace-only reflow (no entry text touched), consistent with the now-unwrapped active `DEVLOG.md`. Committed and pushed this session's doc unwraps (CLAUDE.md, DESIGN.md, DEVLOG.md, both archives) to `main`.

Files: archive/devlog/DEVLOG-archive-01.md, archive/devlog/DEVLOG-archive-02.md, DEVLOG.md

---

### 2026-06-24 01:22:45 — Bridge backend: permission round-trip, restart survival, live-confirmed model/effort controls

Finished the backend tmux path's three remaining capabilities (Prompt A had landed run-state/context/turns). Permission prompts are now a distinct stop-event: added a pure `parse_permission_prompt()` in `bridge/bridge.py` that anchors on the numbered menu at the BOTTOM of the capture (so a long diff pushing the "Do you want…?" question off a short window, or a stale answered menu in scrollback, can't fool it), rewired `_detect_state` to use it, and widened `status()` to re-read 40 lines for the question detail. The `BridgeDriver` now emits `permission_request` (carrying question+options+raw) on entering the prompt and `permission_resolved` on leaving it by any means; `answer_permission(approve)` uses the proven keys (Enter=yes, Escape=no; always-allow omitted, never verified). `main.py` sets `pending_permission` off those events (status enum untouched) and exposes POST `/permission`. Restart survival: a gitignored sidecar-owned runtime record (`sidecar/runtime/sessions.json`, via new `runtime_store.py`) persists tmux-name+config per session; the driver gained a resume-or-create start path, and the sidecar reconnects live tmux sessions (pruning dead ones) on startup. Live discovery of the 5 controls on CC 2.1.187: `/model <name>` and `/effort <level>` set directly on Enter (confirmed → WIRED + capability-flagged, with POST endpoints); `/fast` opens an interactive panel with no reliably-scrapeable toggle, `/thinking` doesn't exist, and permission mode is Shift+Tab-cycle-only (relative) — all three left unwired and reported rather than faked. Tests: +14 hermetic (permission parser incl. long-diff/stale-menu cases, runtime_store, sidecar pending-flag wiring) green with no live env; +4 live round-trips (approve→file written, deny→rejected+absent, resume-after-simulated-restart→history replays, model/effort take) all pass. Note: the pre-existing `test_turn_streams_generating_then_idle` flaked in the full-suite run from shared-`test-1` input contamination by earlier ordered tests (passes in isolation) — unrelated to these changes.

Files: bridge/bridge.py, bridge/__init__.py, sidecar/drivers/bridge.py, sidecar/drivers/base.py, sidecar/main.py, sidecar/runtime_store.py (new), tests/test_bridge_unit.py, tests/test_sidecar_unit.py (new), tests/test_bridge_finisher_live.py (new), .gitignore

---

### 2026-06-24 01:26:01 — Restructured CLAUDE.md "Behavioral rules" into scoped subsections

Reorganized the flat 8-bullet `## Behavioral rules` list (which mixed safety, working style, editing discipline, DEVLOG bookkeeping, and a UI-test procedure) into five `###` subsections: Scope & safety, Working style, Editing discipline, DEVLOG, Verifying UI changes. Pure reorganization — every rule's intent preserved, only grouping and wording tightened. The two fat DEVLOG bullets were compressed (log-trigger / format / rotation) with the ~700→~300 thresholds and verbatim-cut detail intact, still deferring fine print to the DEVLOG.md header. Section is now scannable by concern instead of a wall of uneven bullets.

Files: CLAUDE.md

---

### 2026-06-24 01:27:30 — Design docs refactor: single-source `tokens.css`, file renames, values out of prose

Restructured `design/` into a maintainable single-source layout. **Renames (via `git mv`):** `ui-concept-v9p14.html` → `mockup.html`, `design-tools.js` → `mockup-toolkit.js`. **New `tokens.css`** is now the one place every raw design value lives — the full neobrutalism `:root` token set (names unchanged: `--main`, `--secondary-background`, `--border`, `--shadow`, `--radius-base`, …) **plus** the 16 agent-identity "Jewel" colours promoted to `--ag-crimson … --ag-magenta`, which had been duplicated across a JS object, the Tailwind config, two colour pickers, the agent tiles, and the Palette Reference. `mockup.html` now links `tokens.css` (inline `:root{}` removed) and references everything via `var()`: the Tailwind `agent{}` map, the `AG` identity JS (each agent's colour reads from a `--ag-*` token), both pickers, the static tiles, and all Palette-Reference swatches — no duplicated values and zero agent-hex style literals left (verified 0). `DESIGN.md`'s Design-system section rewritten so the *rules* stay as prose (emphasis ladder, inline-vs-menu, neobrutalism conventions) while every *value* is a token-name pointer into `tokens.css` (0 hex literals remain). Added the `mockup-toolkit.js` `<script>` include so the `Ctrl+G` overlay loads. Fixed all live refs (`DESIGN.md`, `CLAUDE.md`, `design/TODO.md`); historical records (DEVLOG, `.claude/plans/`, test logs) left as-is. **Verified by rendering over http://localhost:** new `mockup.html` is pixel-identical to the pre-edit baseline at 1600 / 1100 / 1920 widths (only delta = the toolkit's floating button, the one intended addition); all tokens resolve from `tokens.css`; agent tiles resolve to the correct hexes; no real console errors; toolkit `Ctrl+G` + Pin / Measure / Grid / Clear All / Copy Notes all functional.

Files: design/tokens.css (new), design/mockup.html (was ui-concept-v9p14.html), design/mockup-toolkit.js (was design-tools.js), design/DESIGN.md, design/TODO.md, CLAUDE.md

---

### 2026-06-24 01:54:30 — DESIGN.md: softened "no popups" into an on-screen *bias*

Reframed the absolute "**Everything visible, no popups**" guiding principle (which the mockup never actually followed — it's full of anchored dropdowns, pickers, comment popouts, and split-button menus) into a soft preference: "**Bias toward on-screen, not floating** — prefer a pane or step-into view; anchored, transient bits (menus, pickers, hover popovers, quick confirms) are fine; avoid movable or stateful floating windows." Removed the peppered single-exception callouts ("the only overlay is the Link Config drawer," "not a floating dialog") so the rule no longer enumerates exemptions and stays maintainable. Realigned the Settings section's back-reference (it had restated the old "everything-visible, no-popups principle" with now-stale link text) to point at the new bias and read "not a floating window." Swept the rest of the doc: remaining `drawer` mentions are plain feature descriptions, the `#purpose--vision` anchor still resolves, and no other text references the old absolute. No mockup/behavioral change — doc intent only.

Files: design/DESIGN.md

### 2026-06-24 02:04:28 — `design/TODO.md`: expanded the Loose-notes handling guidance

Turned the **Loose notes** maintenance rule into a 4-step list so an agent doesn't just file + ID + header a note, but also (2) makes minimal edits for clarity / completes obvious shorthand without changing intent or scope, and (3) disambiguates references — mapping a wrong term or loose label to the real component name as it appears in `design/mockup.html`, or flagging rather than guessing when unclear. Trimmed the Loose-notes section blockquote to point at that rule and confirmed the bucket stays a one-note-per-bullet list. Guidance only; no backlog items changed.

Files: design/TODO.md

---

### 2026-06-24 02:22:00 — Moved DESIGN.md "Open questions" + "Future directions" into the TODO backlog

Centralized the forward-looking material so it stops getting buried in the design reference: deleted both the **Open questions** and **Future directions** sections from `design/DESIGN.md` (DESIGN.md now describes only the design as it stands) and relocated their items into `design/TODO.md`. Open questions → **D — Needs research / decisions** (D6 Transcript Payload, D7 Inbox Attention Ramp, D8 Dense Link Graphs w/ xref to C17). Future directions → **C — Big picture**, deduped against existing items: Handoff Artifacts (C28) and Native Agent-Teams Messaging (C29) added new; "Scratchpad post-level interaction" dropped as already-present C18; "Image paste from clipboard" folded into the existing C8 Attachments & Clipboard. Each moved item tagged with its origin. Fixed every inbound reference: the "About this doc" bullet now points undecided/deferred ideas at `TODO.md`, and the two inline *(future direction)* links (shared scratchpad, Handoff) now read "deferred — see TODO.md". Verified zero residual `#open-questions`/`#future-directions` anchors or "future direction/open question" mentions remain in DESIGN.md, and no inbound links to those anchors exist elsewhere in the repo. Doc/backlog reorganization only — no mockup or behavioral change.

Files: design/DESIGN.md, design/TODO.md

---

### 2026-06-24 02:59:20 — DESIGN.md: stripped version-history asides for a static, present-tense reference

Made `design/DESIGN.md` read as "what the design is," not "how it got here." Removed 22 chronology bits — the "renamed from / was X before vN / removed in vN / replaces the former" asides (Requests→Inbox, Clean→Revise, Clone/Fork→Handoff, Outgoing/Incoming tabs, Activity Log, v7 upper-right pane, v9p14 grip nub, etc.) — and the two `DEVLOG.md` cross-pointers (agents already get that path from `CLAUDE.md`), which also disposed of a broken `archive/agent-dashboard/ui-plan-v2.md` link. Kept design *rationale* (de-versioned: dropped the "v9p2" tag but kept the Material 3 / Carbon grounding) and the sanctioned forward-looking flags (`(planned)` edges, the Transcript `(intent: … TBD)`). No mockup or token changes. Two known mockup-side stragglers remain parked: the `FREE!`→`Bypass` leftover at mockup.html:2500 and a few hardcoded hexes.

Files: design/DESIGN.md

### 2026-06-24 03:17:15 — design/TODO.md: filed Loose notes into section A

Per the human's direction, moved all 7 Loose notes into **A — Next up** as A1–A7 (Team Graph card order, Feed→"Team Feed" rename, remove footer Save/Load, Setup tab first, inline fast/thinking-mode buttons, idle-badge restyle, header version badge v1.1) with bold headers + minimal clarity edits, then cleared the Loose-notes bucket.

Files: design/TODO.md

### 2026-06-24 03:20:00 — design/TODO.md: filed one new Loose note into section B

Filed the new Loose note into **B — Quick wins** as B3 (**Remove Token Palette** — drop the bottom `.ref-section` "Token Palette" design-reference legend from the mockup, now documented elsewhere); disambiguated "token palette section" to the actual `mockup.html` component name, then cleared the Loose-notes bucket.

Files: design/TODO.md

---

### 2026-06-24 03:25:15 — mockup.html: tokenised stray status-tint hexes + fixed FREE!→Bypass

Closed out the two parked mockup-side stragglers. Added a **soft-container / status-tint** token group to `tokens.css` (Material-3-style container roles the design already cites): `--success/warning/danger-soft` + on-text, `--warning-soft-pale`, the `--status-*` History/Plan badge family, `--rail-section`, `--req-*-soft`, `--link-hover`. Replaced 25 hardcoded hexes across `mockup.html` with `var()` — the status/lifecycle/health badges, inline confirms/banners, Inbox request tints, and the context-donut chart colours (which were duplicating agent/semantic tokens) — and fixed the stale `FREE!` → `Bypass` in the Settings permission-mode row. All values preserved exactly. Verified in-browser over http: every new token resolves to its prior hex, affected elements compute identical colours, no broken vars, render unchanged at wide (1840) + narrow (720), and the Config tab shows `…Auto · Bypass`. Remaining hexes are intentional (the Palette Reference legend labels — slated for removal per TODO B3 — changelog comments, and vestigial unused template `data-color`s).

Files: design/tokens.css, design/mockup.html

---

### 2026-06-24 03:36:06 — bridge: Windows Terminal tab now opt-in (stops create() stealing focus)

Made the WT tab opt-in so sessions stop popping a window that steals desktop focus and captures the user's keystrokes mid-task. `create()` gained `show=False` and only calls `_open_wt_tab()` when `show` is true; `batch_create` threads `show` per agent (default false); `resume()` inherits tab-less via `create()`; `show()` and `_open_wt_tab()` are unchanged, so on-demand manual attach still works. The CLI `create` keeps today's human behaviour — it opens a tab by default, with a new `--no-show` opt-out. Net: tests and the sidecar now create sessions tab-less. **Pane-size dependency (recorded, not pinned):** the WT attach used to widen panes to ~200 cols; tab-less sessions render at tmux's default 80×24. Verified the screen-scrapers hold there — the finisher live suite (permission approve/deny + resume) passed 4/4 tab-free and streaming generating→idle still detects — so no `-x/-y` was added; if a future width regression appears, pin it on `new-session`. `test_wt_tab_attached` was left asserting `attached is True` (it validates `show()`'s tab opened by the preceding `test_show`, not `create()`'s) with a clarifying comment. The flaky `test_turn_streams_generating_then_idle` was simplified from the dedicated-session + 3× resubmit + split-send scaffolding (a valid focus-theft-era workaround, now retired) back to the warm shared `test-1` + Ctrl+U clear + split-send. It is **still ~1/3 flaky** in full-suite runs — root-caused via capture-pane logs to EXTERNAL keystroke contamination (human-typed text landing in `test-1`'s input box), not `create()`'s tab and not a send-keys race; left under investigation pending a keyboard-idle clean-room verification.

Files: bridge/bridge.py, bridge/cli.py, tests/test_tmux_bridge.py

### 2026-06-24 03:50:00 — DEVLOG now 100% append-only (Status block removed)

Removed the in-place-editable **Status** block (the "Current state" paragraph + global "Next step" line) and made `DEVLOG.md` fully append-only. Rationale: "current state" is re-derivable from recent entries (latest entry per area = current truth), and the must-be-overwritten block kept going stale — it was still naming the pre-rename `ui-concept-v9p14.html`. A global "next step" also can't represent parallel workstreams; forward intent now lives in `TODO.md`/planning, not the log. Updated the header rules (dropped the Status bullet; the General rule now states there are no in-place-editable sections) and synced `CLAUDE.md`'s DEVLOG Format rule to match.

Files: DEVLOG.md, CLAUDE.md

---

### 2026-06-24 03:50:16 — streaming test flake confirmed external (clean-room run green)

Follow-up to the entry above. Ran one full-suite pass with the user keyboard-idle: **29/29 passed**, including `test_turn_streams_generating_then_idle`. Since `create()` is now tab-less, nothing is attached to `test-1` during the streaming test (`test_show`'s tab opens later), so the only variable removed versus the flaky runs was the user typing. This confirms the residual ~1/3 flake was EXTERNAL keystroke contamination (human-typed text landing in the session's input box), not a defect in the simplified test or a tmux send-keys race. The simplified warm-session + Ctrl+U + split-send test stands as the final form; no retry guard was needed. WT opt-in fix + streaming simplification verified complete.

Files: (none — verification only)

### 2026-06-24 03:55:00 — design/TODO.md: filed one new Loose note into section A

Filed the new Loose note into **A — Next up** as A9 (**Remove Doc Todo Tab** — remove the "Todo" tab from the Documentation panel, leaving Plan · Readme · Claude); disambiguated "Todo tab" to the `data-tab="todo"` button in `mockup.html`, then cleared the Loose-notes bucket.

Files: design/TODO.md

### 2026-06-24 04:05:00 — design/TODO.md: restructured — "Next up" is now an unlettered action queue

Reworked how the doc operates. **Next up** moved out of the A–E effort scheme to its own unlettered section placed right above the capture bucket, and given an instruction block: agents directed there implement each item and delete it once done — building in `mockup.html`, working from `DESIGN.md` + `tokens.css`, keeping `DESIGN.md` in sync (or confirming no change needed). Relettered the backlog Quick wins/Big picture/Needs-research/Housekeeping B–E → **A–D** and updated the cross-refs (C6→B6, C12→B12, C17→B17). Renamed **Loose notes → Inbox**. Updated the intro warning (backlog reference-only; Next up is the actionable exception) and the "How agents maintain this list" Numbering/Group-by-effort/Inbox guidance to match. The 9 queued items and all backlog/Scratch content carried over verbatim.

Files: design/TODO.md

### 2026-06-24 11:30:00 — design/mockup.html: v1.1 — implemented the 9 "Next up" items + DESIGN.md sync

Built all nine queued items in the mockup (now **v1.1**, version scheme reset from v9p14): (1) graph-card status bars reordered to **Ctx over Turns**; (2) right panel renamed back to **Team Feed**; (3) **Save setup / Load removed from the footer** (that flow lives in Settings → Setups; token pill + clock remain); (4) **Setups** is now the first and default-shown Settings tab; (5) the **Opus fast-mode / Thinking-mode toggles are inline** (side-by-side 2-col grid like the Color/Icon pickers, in Details + Create) with a new `.tog-cell` rule (ellipsis on narrow); (6) the **idle status badge** is now a solid `--muted` slate fill with white text, matching active/pending; (7) the **title-bar version badge reads v1.1**; (8) the bottom **"Token Palette" reference legend removed** (`.ref-section` block + its CSS — values live in `tokens.css`); (9) the Documentation **"Todo" tab removed** (Plan · Readme · Claude remain; pruned its pane, the `renderDocs` loop, and `DOC_FB` entry). Synced **DESIGN.md** for items 1, 3, 4, 5, 6, 8, 9 (the layout schematic, panel/Settings/doc-tab prose, status-badge spec, and the Palette-Reference mentions). Removed the nine items from TODO.md → Next up. Verified in the rendered browser (served over http): 0 JS errors, all 13 cards read Ctx→Turns with correctly-paired values, Settings opens to Setups, toggles fit at default and ellipsis-truncate without spill at a 240px narrow extreme, idle badge computed `rgb(91,95,134)`/white, doc tabs switch cleanly with no Todo remnants. (Caught and repaired a malformed first-pass regex swap that had crossed the card bar values.)

Files: design/mockup.html, design/DESIGN.md, design/TODO.md

### 2026-06-24 11:45:00 — design/TODO.md: moved Next-up instructions into the maintenance section + anti-placeholder rule

Relocated the long **Next up** implementation steps (build in `mockup.html`; work from `DESIGN.md`+`tokens.css`; keep `DESIGN.md` in sync; remove + DEVLOG when done) into "How agents maintain this list" as a numbered **Next up — implementing items** block, leaving the Next up section itself a one-line helper that points back to it. Added a **"Leave empty sections empty"** rule forbidding placeholder/"(empty)"/status/changelog notes in empty sections — and removed the stray `_(Empty — the v1.1 batch …)_` line a prior pass had left in Next up (that history lives here in DEVLOG).

Files: design/TODO.md

---

### 2026-06-24 04:57:37 — design/TODO.md: queued send-trigger "Inject" + "Next turn"→"Next" rename in Next up

Promoted two approved send-trigger changes into the **Next up** action queue: add an **Inject** option directly after "Now" in the split menu (one-shot steering message that feeds a running agent without stopping it — established model only, not the B12 dynamic-doc approach), and rename **"Next turn" → "Next"** to match the sibling `.seg` control. Filed and cleared the matching Inbox note ("Change the send option from 'Next turn' to…"). Nothing built yet — these are queued items, not mockup changes.

Files: design/TODO.md

---

### 2026-06-24 04:59:15 — design/TODO.md: queued Documentation→Library panel rework in Next up

Added four coordinated **Next up** items (3–6) for the Documentation-panel rework agreed in discussion: rename the panel **Documentation → Library** with tabs **Plan · Documents · Assets**; collapse Readme + Claude into one **Documents** tab that reuses the existing doc editor plus a doc-switcher (icon · name · path; defaults README + project & user `CLAUDE.md`); a new **Assets** tab (thumbnail-grid nav, paste/upload, link-to-prompt) as the single source of truth for media; and in Prompts, rename the **Library** tab → **Templates** and add a paperclip **attach** button after the mic on Compose + Templates. Nothing built yet — queued items only. Left the originating rough notes in TODO's Scratch section untouched (human's space).

Files: design/TODO.md

---

### 2026-06-24 05:20:13 — Library panel rework + send-trigger Inject: built all 6 "Next up" items

Implemented the queued Documentation→Library rework in `design/mockup.html` and synced `design/DESIGN.md`. **Send menu:** added **Inject** after Now and renamed **Next turn → Next**. **Panel:** Documentation → **Library**, tabs now **Plan · Documents · Assets**. **Documents tab** folds the old Readme/Claude tabs into one, driven by a new left **doc-switcher** (icon · name · path; defaults README + project & user `CLAUDE.md`) that swaps docs through the *existing* shared editor — added a user-level `CLAUDE.md` and a `docPick()` handler; `renderDocs()` now covers `claudeuser`; `switchTab` remaps stale stored `readme`/`claude` tabs so returning users don't hit a blank pane. **Assets tab** is new: a thumbnail grid (gradient placeholders) with Paste/Upload + a selected-tile preview/action strip (Link to prompt · Remove), via `assetPick()`/mock handlers. **Prompts:** the **Library** tab is renamed **Templates** and a paperclip **attach** button sits after the mic (Compose + Templates, hidden on History). Verified in-browser at wide (1600) + narrow (1120) extremes — tab switches, doc-switcher, asset selection, send menu (Now·Inject·Next·Queue), and attach visibility all correct; grid reflows 4→3 cols; console clean. Removed all 6 items from TODO's Next up (now empty).

Files: design/mockup.html, design/DESIGN.md, design/TODO.md

---

### 2026-06-24 05:36:58 — design/TODO.md: queued 5 new Next-up items (Plans tab, History attachments, Ultraplan toggle, Trigger Inject)

Filed five approved changes from discussion into the (now-empty) **Next up** queue: (1) rename the Library **Plan** tab → **Plans** (label only, keep `data-tab="plan"`); (2) add a "new plans" count badge to that tab, mirroring the Inbox `req-badge` (new = unreviewed plans); (3) a **History-only** attachment chip + popover on `histCardHTML` cards (paperclip + count, click → popover list → opens item in Library Assets/Documents by type via the `reviewPlan` cross-link pattern; `stopPropagation` since the header is an expand button) built as a reusable component for later Messages reuse; (4) add an **Ultraplan** toggle to the agent-panel Mode block — go to a 3-col grid and shorten labels (drop "Opus" + the redundant Off/On words → Fast · Thinking · Ultraplan), gate it to Plan mode, mind the Effort-seg "Ultra" name collision; (5) add **Inject** after "Now" in the Link Config **Trigger** seg (the compose send split menu already has it). Verified against the modified mockup first — the send-menu Inject/Next rename was already built, so not re-queued. Nothing built this turn; queue only.

Files: design/TODO.md

---

### 2026-06-24 05:56:09 — Built all 6 Next-up items in mockup.html (+ a 7th: History timestamp fix) + DESIGN.md sync

Implemented the whole Next-up queue in `design/mockup.html` and synced `design/DESIGN.md`. **Plans tab:** Library "Plan" → **Plans** with a `req-badge` count of unreviewed plans (review/draft → 2; hides at 0), populated in `renderPlans()`; `data-tab="plan"` kept so cross-links survive. **History attachments:** new `attTrigHTML`/`attPopHTML` render a paperclip+count chip in `histCardHTML` headers (only when `o.att` present) and a popover (rendered as a `.fcard` sibling so its buttons aren't nested in the header's expand `<button>`; card gets `att-open` → `overflow:visible` so it isn't clipped); clicking an entry calls `openAttachment()` → `switchTab('doc', assets|documents)` by type; added `att` arrays to 2 HIST rows; chip uses `event.stopPropagation()`; `closeAllPopups()` now also clears `.att-pop`/`att-open`. **History timestamp:** added a `flex-1` spacer + dropped the time's `margin-left:auto` so it pins flush-right like Messages (was floating mid-row from two competing auto-margins). **Ultraplan toggle:** Mode toggles went 2-col → **3-col**, labels shortened to **Fast · Thinking · Ultraplan** (state now reads from the `.on` fill, not words; `toggleFast/Think` no longer rewrite labels); new `toggleUltra` + `syncUltraGate` gate Ultraplan to **Plan mode** (dimmed/inert otherwise). Applied to **both** Mode instances (Details + Create) via a shared `.mode-seg` class — caught the second (Create) instance that still had the old labels; gating is per-instance (`seg.parentElement`). **Trigger seg:** added **Inject** after Now in Link Config → `Now / Inject / Next / Queue / Hold`. Tightened `.tog-cell` padding/gap to reduce label clipping at narrow widths. **Verified in-browser** (served on :8777) at wide (1500/1600) and narrow (980/1024): 0 console errors; Plans badge, 3-col toggles + gating (both tabs), attachment chip→popover→Library routing (Assets + Documents), right-aligned times, and the 5-segment Trigger all correct. Known: at extreme-narrow (~1024px window) "Thinking"/"Ultraplan" ellipsis-truncate — graceful (icons + tooltips disambiguate) and better than the prior long labels; full labels show at normal widths. Cleared all items from TODO Next up.

Files: design/mockup.html, design/DESIGN.md, design/TODO.md

### 2026-06-24 — Queued "Agent Console Tab" in TODO Next up

Filed an approved design item into `design/TODO.md` → **Next up** after a design discussion: a new **Console** tab in the Agent panel (Details · Create · Console), scoped to the focused agent. Holds the agent's **raw Claude Code terminal feed** + a grouped, filterable **slash-command catalog** (all commands in one place; runs on the focused agent via a bottom run bar) and an **Expand → step-into** full-window view for width (Settings-gear pattern). Cross-referenced B6 (Slash Commands) / B7 (Slash Shortcuts); flagged that building the feed reverses the DESIGN.md "Out of scope" live-CLI/terminal note, to be updated during implementation. No mockup/code changes yet — capture only.

Files: design/TODO.md

### 2026-06-24 — Built the Agent Console tab in mockup.html (v1.2) + DESIGN.md sync

Implemented the "Agent Console Tab" Next-up item in `design/mockup.html` (version bumped v1.1 → v1.2, title-bar badge too) and cleared it from TODO Next up. **New tab:** Agent panel is now Details · Create · **Console**, scoped to the focused agent (static = researcher · 01 sandy, matching Details). **Raw feed:** white bordered monospace terminal surface filling the tab body, color-coded line classes (l-cmd/l-tool/l-out/l-think/l-asst/l-sys) built by `renderConsole()` from `CON_FEED`. **Command catalog:** `CON_CMDS` → grouped, filterable list (6 clusters, 26 commands), each row = command + one-line description; `/model`→Details, `/mcp`/`/config`/`/stats`/`/plugin`→Settings carry a teal "⤴ also-in-X" tag. Picking stages into the run bar (`pickCmd`); Run/Enter appends to the feed (`runConsoleCmd`, mock). **Width via Expand:** `openConsole()` pops a step-into full-window view (`#console-view`, mirrors `.settings-view`) — catalog as a slide-up panel in-column (`toggleCmdPanel`), as a persistent left rail when expanded; run bar lives in `#mid-foot-console` (reuses the existing tab+footer machinery). Esc closes it after Settings. This **supersedes** the v9p14 A9 "slash commands in Prompt → Compose" proposal (multi-select To made the target ambiguous) and **reverses** the DESIGN.md out-of-scope "no dedicated live-CLI/terminal pane" note — now an on-demand surface, not always-on. **DESIGN.md synced:** layout schematic (Details·Create·Console), out-of-scope reversal, new Console subsection under Agent (left pane), and a Core-components entry. **Verified in-browser** (served :8777) headless at narrow (1040) + wide (1700): 0 console errors (only favicon 404); confirmed tab switch, in-column feed, catalog slide-up, pick→stage→close, Expand step-into reflow, rail filter (compact→1 row), Run append (in-column Enter + full-view button), and Close. Fixed one defect found mid-verify: the step-into header agent badge had `width/height:100%` on the `.agtile`, breaking the badge — removed so `.badge-c .agtile` sizes it (28px).

Files: design/mockup.html, design/DESIGN.md, design/TODO.md

### 2026-06-24 — Console command-catalog formatting cleanup (scannability)

Reworked the slash-command catalog rows in `design/mockup.html` after feedback that they were sloppy — the "also-in" badges dwarfed the text and command/description didn't segregate when scanning. Now each row is **two lines**: the command in **bold mono** (11px, the scan anchor) over its description in **muted body text** (9.5px, weight 500) — strong type hierarchy so the eye tracks the mono command column. Group headers are sticky uppercase labels (muted-2) with a **trailing hairline rule** (`--rule`) to band the clusters. The **also-in-X tag** is now faint, flat metadata (8px, `--muted-2`, no border/background/chrome, right-aligned) instead of a heavy bordered teal chip. Row hover is the light-teal select fill (`--select`) with no border/shadow jump. Updated `renderConsole()` to emit `.cmd-row-top` (name + tag) over `.cmd-desc`. **Verified in-browser** (:8777) at narrow (1060, in-column slide-up) + wide (1680, expanded rail): 0 console errors (favicon only); computed styles confirm the hierarchy (mono/800 command, muted/500 desc, borderless 8px tag). Synced the v1.2 changelog bullet + DESIGN.md Core-components entry. (Aside: cleared a stale locked MCP-chrome profile mid-task to relaunch the browser.)

Files: design/mockup.html, design/DESIGN.md

### 2026-06-24 — Mockup behavior audit + wiring pass (selection-drives-the-app keystone, dead-control demos, Messages data blocks, hover cards)

Ran a 9-agent parallel audit workflow over `mockup.html` + the design docs → a synthesized brief (`.scratch/mockup-behavior-audit-brief.md`): ~33 clear fixes, 18 genuine open questions (each with options + an assumed answer), 13 example-content gaps, and the doc-sync list. Then implemented the high-confidence, ungated fixes in `design/mockup.html`. **Keystone:** `selectNode()` now repaints the whole Agent panel from the clicked card — identity band (tile/role/name/status badge), the editable identity config fields (role/no/name/color/icon), model·mode·effort·think readouts, the Ctx/Turns bars, and the Console identity bar — so selection genuinely drives the app (was a visual-only retint). **Stale renames:** internal `requests`→`inbox` and prompt `library`→`templates` (ids, `data-tab`, comments, `switchTab` remaps), `DOCUMENTATION`→`LIBRARY` comment, and the Inbox Review tooltip → "Library → Plans". **Wired the dead primary controls** as labeled scripted demos: Create/Reset/Cancel, confirm-gated Retire, Random-name, Handoff/Rewind **proceed** buttons (the confirm had only Cancel), Inbox Approve/Deny/Reject/Decision (toast + remove + live fleet-badge decrement), Plans decision trio + real Copy + live comment-save (appends feedback + re-renders), Link Save/Delete, Send/Revise, History Retry/Stop, MCP switch, console attach. **Count honesty:** single-sourced Turns to 34/50 (timeline was 60/60), Plans count badge derives, icon-picker placeholder reflects the real sprite count. **Example content:** Team Feed → Messages now carry typed content blocks (thinking / Read / Write / Bash / unified Diff / Meta + one agent→agent relay), and the six **Include** toggles + Sent/Received actually filter them. **Hover cards:** built one reusable neobrutalism `data-hc` popover primitive (hybrid trigger — info-glyph seeded on all six panel headers, whole-element hover on the status badge + Mode block); pure documentation, the "documentation-through-design" surface. Inbox request-type badges moved to token-driven `.db-permission/.db-approval/.db-decision` classes. **Verified in-browser** (:8799, Playwright MCP) at wide (1600) + narrow (820): 0 console errors (favicon only); evaluated the keystone repaint, plan-approve/inbox-decrement state mutations, Include-toggle filtering, and hover-card seeding — all pass; layout holds at both extremes. Synced `DESIGN.md` (Console-now-wired line, hover-card pattern, badge-family taxonomy; the Console out-of-scope reversal was edited in concurrently). Deferred (still in the brief, pending the 18 answers): Templates left-rail rebuild (Q4), Link-drawer side (Q12), shared Filter narrowing, Settings deep-wiring (Setups/global-edit/Usage), Assets/+Add-document data-driving, and the remaining example-content enrichment.

Files: design/mockup.html, design/DESIGN.md

### 2026-06-25 — Restyled frontend App.tsx to the neobrutalism design system

Re-skinned the working-MVP frontend (`frontend/src/renderer/App.tsx`) from its old dark teal/navy theme to the **neobrutalism light theme** in `design/` (values from `design/tokens.css`, patterns from `design/DESIGN.md`) so the file stops contradicting the design system. **Styling only** — no elements added/removed, no behavior or logic touched. Remapped the central `C` palette onto the design tokens (cream `--background`, white cards, `--surface-3` chrome, navy `--border`/`--foreground` ink, pink `--main` primary / teal `--secondary`, soft status containers, jewel agent colors) and added shadow/select/btn keys; applied the system's signatures throughout: 2px navy borders, hard offset shadows (`--shadow`/`--shadow-sm`) on raised/interactive elements with a hover-press, uniform 5px radius (rounded-square badges, no pills), Archivo + JetBrains Mono (via @import), and palette-matched scrollbars. Pink title bar; primary actions (New · Send) pink, Stop danger, selection = light-teal fill; status/connectivity pills became bordered badges with the soft success/danger/warning tints; inline code → surface-3 chip with a rule border. **Verified in-browser** via a throwaway Vite dev server + headless Chrome (playwright-core): a mock feed exercised every event-card type (init, text+inline-code, thinking, tool-call, tool-result, result bar, rate-limit) plus the session list (idle + selected), composer, and Connected/offline pills; clean reflow at narrow (720) and extra-wide (1900); one headed pass confirmed identical rendering. No new type errors (the lone `tsc` error on `WebkitAppRegion` is pre-existing in HEAD). Left `design/` untouched (another agent is active there) and did not modify `index.html`.

Files: frontend/src/renderer/App.tsx

---

## Archived history

Older entries are rotated into `archive/devlog/` (see the **Rotation** rule in the header) to keep this file small. Archived entries stay full-fidelity and **verbatim** — open the relevant archive only when you need the detail; the digest below is enough for most context.

**Digest — [`DEVLOG-archive-01.md`](archive/devlog/DEVLOG-archive-01.md) (2026-03-26 → 2026-06-13, 21 entries):** the sandbox-era origin story. Workspace + MCP-server setup; the tmux **bridge** built from first draft to a stable 20-method package with a 30-test suite; the **HTTP bridge** (VS Code extension, port 7483); dashboard inception and the **TUI → Electron/React pivot**; the wireframe lineage **v1 → v4** with the palette exploration (Vintage Teal → Warm Dark); the architecture pivot where the Agent **SDK + `stream-json`** replaced xterm/ttyd terminal embedding; the **FastAPI sidecar** (port 7690) + React single-file scaffold; the **E2E pipeline proof**; the design-system / event-feed component specs; and the early file reorganizations (`ui/` → `awl-dashboard/testing/` → `agent-dashboard/design/`).

**Digest — [`DEVLOG-archive-02.md`](archive/devlog/DEVLOG-archive-02.md) (2026-06-13 → 2026-06-21, 117 entries):** the dashboard design push and the start of the `awl-cc-dash` migration. The bulk is the **UI mockup iteration** — the ui-concept lineage from the v5 wireframes through **v9p13** (3-pane layout, the Warm-Dark palette, the Team Graph / Team Feed / Agent panels, and the Documentation/Plan review system with its nav rail + comment popout and the neobrutalist badge/shadow rules), plus the `human-notes-misc.md` "Next up" backlog churn and the `design/DESIGN.md` syncs. It closes with the **migration into `awl-cc-dash`** on 06-21: fresh git history, un-nesting `frontend/`+`sidecar/` to the root, the `tools/ → bridge/ + dev/` split and bridge-import refactor (suite green), repo config (permission allowlist, cc-exports/plans routing), and the run-up to the **sidecar driver seam #1**. (Two 06-13 entries — the v5p5–v5p9 backfills — are `[Reconstructed]`.)

| Archive file | Date range | Entries | Summary |
|---|---|---|---|
| [DEVLOG-archive-01.md](archive/devlog/DEVLOG-archive-01.md) | 2026-03-26 → 2026-06-13 | 21 | Sandbox-era origin: tmux/HTTP bridges, dashboard design lineage v1→v4, the SDK architecture pivot, the FastAPI sidecar + React scaffold, and the E2E pipeline proof. |
| [DEVLOG-archive-02.md](archive/devlog/DEVLOG-archive-02.md) | 2026-06-13 → 2026-06-21 | 117 | Dashboard UI mockup lineage (v5 → v9p13) + the start of the awl-cc-dash migration (git reset, root un-nest, bridge split, repo config). |
