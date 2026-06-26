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

### 2026-06-25 — Queued the v10p1 design-change batch into Next up

Compiled the changes worked out across a planning thread (3 held — Console partial-expand over left+middle, the info-glyph restyle, and a native-Claude-Code-terminal Console feed — plus ~11 new ones) and appended them as items **9–22** in `archive/design/design-v10p1/TODO.md` **A — Next up**, preserving the existing 1–8. Covers: icon-only Copy/Edit/Comment/Retry, Inbox cards made expandable + selectable with a Pending-badge expand/highlight jump, Inbox Reject/Deny → danger, Messages Active/Complete status badges, expanded-card right-aligned timestamps, History cards adopting the Team Feed checkbox+expand pattern, the Library Assets rail+preview rebuild, unified Documents/Assets header (path + dates) and footer (Copy·Edit·Comment icons + Link-to-prompt + danger Remove; Assets Edit greyed), a Doc/Asset "Add file / Paste" action, nav-row rename/delete icons, and the Compose+Templates tab merge (single-select template dropdown + contenteditable compose box). No mockup changes yet — this is the agreed build list awaiting the go-ahead.

Files: archive/design/design-v10p1/TODO.md

### 2026-06-25 — Restyled frontend App.tsx to the neobrutalism design system

Re-skinned the working-MVP frontend (`frontend/src/renderer/App.tsx`) from its old dark teal/navy theme to the **neobrutalism light theme** in `design/` (values from `design/tokens.css`, patterns from `design/DESIGN.md`) so the file stops contradicting the design system. **Styling only** — no elements added/removed, no behavior or logic touched. Remapped the central `C` palette onto the design tokens (cream `--background`, white cards, `--surface-3` chrome, navy `--border`/`--foreground` ink, pink `--main` primary / teal `--secondary`, soft status containers, jewel agent colors) and added shadow/select/btn keys; applied the system's signatures throughout: 2px navy borders, hard offset shadows (`--shadow`/`--shadow-sm`) on raised/interactive elements with a hover-press, uniform 5px radius (rounded-square badges, no pills), Archivo + JetBrains Mono (via @import), and palette-matched scrollbars. Pink title bar; primary actions (New · Send) pink, Stop danger, selection = light-teal fill; status/connectivity pills became bordered badges with the soft success/danger/warning tints; inline code → surface-3 chip with a rule border. **Verified in-browser** via a throwaway Vite dev server + headless Chrome (playwright-core): a mock feed exercised every event-card type (init, text+inline-code, thinking, tool-call, tool-result, result bar, rate-limit) plus the session list (idle + selected), composer, and Connected/offline pills; clean reflow at narrow (720) and extra-wide (1900); one headed pass confirmed identical rendering. No new type errors (the lone `tsc` error on `WebkitAppRegion` is pre-existing in HEAD). Left `design/` untouched (another agent is active there) and did not modify `index.html`.

Files: frontend/src/renderer/App.tsx

### 2026-06-25 — Built the v10p1 "Next up" batch (items 9–22) in the mockup

Implemented all 14 queued items in `design/mockup.html` (the agreed build list from the prior entry). **Cross-cutting:** the panel-header hover-card glyph became a no-chrome muted `info` mark (#9); the repeated **Copy/Edit/Comment/Retry** actions are now mic-button-style **icon-only** buttons everywhere via a shared `.icon-btn` (#10); `.fcard-time` gets `margin-left:auto` so timestamps stay right-pinned when a card is expanded (#12). **Console:** the Expand step-into now stops at the left edge of `#pRight` (covers left+middle only; `positionConsoleView()` recomputes on window-resize + a `ResizeObserver` on `#pRight`), a deliberate difference from Settings' full-window step-into (#13); the feed was reworked to **faithfully mimic a real Claude Code terminal** — dark surface + native markers (`>` input · `●`/`⎿` tool+result · `✻` thinking · model/status line · `+`/`−` diff block · permission box) via a self-contained `--term-*` palette (a documented token-rule exception), feed-only with the chrome staying neobrutalism (#14). **Team Feed:** Inbox rebuilt **data-driven** from a `REQS` array — collapsible (identity + type badge + title) + selectable like Log, with `data-agent` so a **Pending** badge click expand-highlights the card; Deny/Reject use `--danger` (#15, #11); Messages received cards lead with an **Active/Complete** badge (user-sent keep the Sent tag) (#16); History adopts the checkbox(multi-select)+expand split, footer Copy/Edit/Retry icon-only + Stop, now multi-select (#17). **Library:** Assets rebuilt as a **rail+preview** from an `ASSETS` array like Documents (#18); Documents+Assets share a header (path + Created/Edited) + footer (Copy·Edit·Comment icons + Link-to-prompt + danger Remove; Assets Edit greyed) via `libFootHTML` (#19); nav rows are now `<div role=button>` with ghost rename/trash icons (#21) and an **Add menu** (Add file / Paste) replacing the Assets Paste/Upload toolbar (#20). **Prompt:** Templates folded into **Compose** (tabs = Compose · History) — a Templates sub-header (single-select dropdown None + saved, plus a greyed-until-active fill input) over a **`contenteditable`** compose box; selecting a template inserts its body at the saved cursor (placeholders stay clickable pills), None clears + re-greys (#22). **Verified in-browser** (`:8771`, Playwright MCP) at narrow (1000) / default (1440) / wide (1920): **0 JS console errors** (favicon 404 only); evaluated the data-driven renders, Console pin-to-`#pRight` (exact at both extremes), template insert (5 pills, text preserved, fill enable/greying), Pending-jump (tab + open + flash), inbox danger buttons, and expanded-card timestamp alignment — all pass; layout holds at every extreme (Inbox actions wrap, titles ellipsis, terminal wraps cleanly). Synced `design/DESIGN.md` (Console partial-expand vs Settings + the `--term-*` exception, the merged-Compose + Templates-flow rewrite, the Documents/Assets shared card shape + rail/preview + Add menu + nav icons, the Inbox expandable/selectable + danger note, the History checkbox+expand, the icon-only-action + info-glyph conventions, and the layout-tree ASCII), cleared the now-shipped items 1–22 from `archive/design/design-v10p1/TODO.md` **A — Next up**, and added a v10p1 changelog block atop the mockup's comment (visible version badge left at v1.2 — not requested).

Files: design/mockup.html, design/DESIGN.md, archive/design/design-v10p1/TODO.md

### 2026-06-25 — design/TODO.md: queued 3 Inbox notes into Next up + agents no longer self-delete done items

Filed the 3 Inbox notes into **Next up** (1 **Collapsible Inbox Cards** — collapsible `.inbox-card` + wire the dead checkbox to select; 2 **Pending Badge Selects Card** — Pending badge also selects/highlights its Inbox card; 3 **Link Agents Drawer Right** — open `#link-drawer` on the right so Team Graph cards stay visible), disambiguated to the mockup's component names, and cleared the Inbox. Per the human's request, changed the **Next up** workflow so agents now **leave finished items in place** (log to DEVLOG + report, don't delete) for manual review/removal — updated step 4 of "Next up — implementing items," the Next up section helper, the "transient" note in Numbering, and the "How it's used" intro line to match.

Files: design/TODO.md

---

### 2026-06-25 16:50:25 — design/TODO.md: filed 5 Inbox notes into Next up + queued the button-color heuristic

Filed the 5 new Inbox notes into **Next up** as items 4–8 (4 **Mode Toggles → Sliders**; 5 **Failed Message Badge** for Team Feed → Messages; 6 **Stop as Icon Button** — icon-only Stop in History footer + add to Messages footer rightmost; 7 **Summarize in Scratch & Log** — make functional; 8 **Link-to-Prompt Button Sizing** — match footer-button height/format + right-align), disambiguated to the mockup's component/handler names, then cleared the Inbox. Added item 9 **Button-Color Heuristic** capturing the agreed rule (pink = commit-here · teal = hand-off/outbound · cream = quiet local utility · red = destructive · white = fillable-only) plus the concrete deltas: recolor `.icon-btn`/`.mic-btn` white→cream, and Revise (Plans footer) + Reply (Inbox) cream→teal, with the DESIGN.md sync noted. No mockup code changed yet — this only queues the work.

Files: design/TODO.md

---

### 2026-06-25 17:26:50 — Built the Next-up batch (items 1–9) in the mockup

Implemented all of `design/TODO.md` → **Next up** in `design/mockup.html`. #1 **Collapsible Inbox Cards** was already shipped in v10p1 (verified intact, no change). New work: #2 **Pending-badge selects** (statusJump's pending branch now adds `.sel` so the jumped-to Inbox card is checkbox-selected + light-teal filled, not just expanded/flashed); #3 **Link drawer right** (`.drawer` went `position:absolute` in `#pGraph` → `position:fixed` against the app's right edge, top:36/bottom:34, so the whole Team Graph stays visible while linking); #4 **Mode toggles → sliders** (Fast/Thinking/Ultraplan in both Details + Create panels are now stacked slider switches with inline heading labels — `.tog-switch`/`.tog-knob`; ON slides the knob +12px and turns the track teal while the button stays white; gating preserved); #5 **Failed message badge** (`.db-failed` soft-red + fcardHTML active/complete/failed map + a demo `status:'failed'` MSGS entry); #6 **Stop as icon button** (History Stop → `icon-btn icon-btn--danger` icon-only; new `#msg-stop-btn` rightmost in the Messages footer, Messages-only via switchTab; `msgAct('stop')` branch); #7 **Summarize in Scratch & Log** (switchTab shows `#summary-btn` on messages/scratch/log; new `FEED_SUMMARIES` map + `currentFeedTab()` make `toggleSummary` tab-aware; the Messages body is lazily single-sourced via `MSG_SUMMARY_BODY`; overlay closes on every feed tab switch); #8 **Link-to-prompt sizing** (libFootHTML's Link button dropped `btn-sm` → full 30px and moved out of `.doc-foot-l` to right-align before Remove); #9 **Button-color heuristic** (`.icon-btn`/`.mic-btn` white→cream so the neutral tier is one surface; Revise in `planFootHTML` and Reply in `inboxReplyHTML` cream→teal as hand-off actions).

Verified in-browser (Playwright, 0 JS errors) at narrow (1000px) + wide (1440/1920px) with structural checks, real click-throughs (toggle on/off, gated Ultraplan blocked, Stop, pending-jump-selects sandy, summarize per-tab), and a parity reload. Adversarial-review workflow (4 cluster reviewers + per-finding verifiers): items #1–#7 + all regression areas PASS, **0 confirmed defects**; the one flag (`.fmt-btn` is cream) was a verified false alarm — `.fmt-btn` was already cream pre-v9p2 and is not in my diff. Synced DESIGN.md (color ladder → teal=hand-off / cream=unified-neutral incl. icon-only; Mode-toggle slider description; Messages status badges incl. Failed + rightmost Stop; Summarize on Messages/Scratch/Log; History footer Stop icon-only; Pending-select; drawer-right; Library footer Link alignment). Per the Next-up rule, left items 1–9 in place in TODO.md for the human to remove after review.

Files: design/mockup.html, design/DESIGN.md, DEVLOG.md

---

### 2026-06-25 17:53:07 — Corrections to the Next-up batch: Mode-toggle sliders + Link-drawer anchor

Two human corrections on the v11 batch. (1) **Mode toggles** — reverted the stacked one-per-row layout back to **one evenly-spaced row** (grid-cols-3) of simplified inline controls (icon · label · switch, no button box), and replaced the bespoke `.tog-switch`/`.tog-knob` with the **shared `.swh` switch** (the Settings MCP/plugin toggle) so they match the slider already in use — extended the `.swh.on` rule to also fire from the parent `.think-tog.on`. (2) **Link Config drawer** — instead of opening fixed against the whole window's right edge, it now opens against the **left edge of the right pane (`#pRight`)**, i.e. immediately to the right of the Team Graph panel it's launched from; moved `#link-drawer` out of `#pGraph` into `#pRight` (absolute, clipped to that pane), flipped the border/shadow and added a `slideInLeft` (slides out from behind the graph). Team Graph stays fully visible either way.

Re-verified in-browser (Playwright, 0 JS errors): toggles on one row with the `.swh` slider (teal-on knob at 20px), no overflow at narrow (250px panel — labels compress toward initials, icons+tooltips carry it) and full labels at wide (480px panel); drawer settles at `#pRight`'s left edge (left=1231 vs graph-right=1229), clears every graph node, fits within the pane at narrow + wide. DESIGN.md updated (Mode-toggle row + shared `.swh`; drawer-right-of-graph anchor).

Files: design/mockup.html, design/DESIGN.md, DEVLOG.md

---

### 2026-06-25 18:11:41 — Final tweaks: header info-glyph trails the label + Fast gated to Opus

Two human-requested tweaks. (1) **Panel-header info-glyphs** were drifting to the centre of the header (the `.pcard-head` `justify-content:space-between` was distributing the seeded `.hc-glyph` even though it's inserted right after the `<h3>`); added `margin-right:auto` to `.hc-glyph` so the [label + glyph] pair stays left and the header's right-hand controls (tabs / Link Agents / feed tabs) get pushed to the end. (2) **Fast mode gated to Opus** — `/fast` is an Opus mode, so the Fast toggle is now enabled only when its panel's Model is Opus: added a `fast-tog` class to both Fast toggles, a `gateFast(tabs)` helper (scopes to the panel via `closest('[data-group="mid"]')`, toggles `.gated` + clears `.on` + updates the title when model !== 'opus'), wired it into the model-tab onclick and the per-panel init, and made `toggleFast` no-op when gated (mirrors `toggleUltra`). Default state: Details (Opus) → Fast enabled; Create (Inherit) → Fast gated.

Verified in-browser (0 JS errors): all five visible panel headers show the glyph trailing the label with right-controls at the end; Fast gates/un-gates correctly on model switch (Opus↔Sonnet), the gated click is a no-op, and the Thinking/Ultraplan toggles + model version dropdown are unaffected. DESIGN.md updated (Mode-block gating note covers both Fast→Opus and Ultraplan→Plan; info-glyph "trails immediately after the label").

Files: design/mockup.html, design/DESIGN.md, DEVLOG.md

---

### 2026-06-25 21:37:39 — Snapshot design-v10p7 + TODO backlog churn (committed pre-existing changes)

Committed pre-existing uncommitted work (made outside this session). Froze a **design-v10p7** snapshot under `archive/design/design-v10p7/` (DESIGN.md, TODO.md, mockup.html, mockup-toolkit.js, tokens.css). In `design/TODO.md`, the **Next up** queue (items 1–9, the v10.7 build) was cleared after human review, and a fresh round of rough notes was captured under **Inbox** (the Embed/Attach content-sharing revision + smaller tweaks: Library nav trash-icon removal, divider-line color, Feed timestamp alignment, Link Config "Time as End-after" removal, Filter→From/To, Show→Type / Include→Content, Templates-below-Compose + "Editor" rename, Plans/Documents "Editor" header) plus two **Scratch** notes (agent-lifespan indicator; inline squiggle spell-highlights, replacing the old "support multiple plans" note).

Files: design/TODO.md, archive/design/design-v10p7/ (DESIGN.md, TODO.md, mockup.html, mockup-toolkit.js, tokens.css), DEVLOG.md

---

### 2026-06-25 21:48:17 — Authored the link-behavior / dashboard refactor brief (dev/prompts)

Captured a long design discussion into `dev/prompts/link-behavior-refactor.md` — a phased (P0→P4) implementation brief for the next agent. Scope: the **Embed/Attach** content-sharing model (replacing the Share + "Link to prompt" controls, routed through the renamed **Editor** with frozen embed blocks, interactive template blocks, an attachment strip + inline citations); the **Inbox** restructure (typed sections + a new **Error** type, Approval→Plan, Plan cards lose Approve/Reject, status-color rework); the single-agent **Review** chip; the rail-badge multi-comment fix; dropdown agent-badge tightening; and Ultraplan removal + the v10p6 labeled-toggle revert. Grounded in exact mockup anchors (functions/classes/line refs); no product code changed yet. Review/Inbox formalization (B13) + real backend left deferred.

Files: dev/prompts/link-behavior-refactor.md, DEVLOG.md

---

### 2026-06-25 22:28:44 — Refactor brief: folded in note 119 + scoped Scratch/Log + Reply-block primitive

Worked four human decisions into `dev/prompts/link-behavior-refactor.md` with minimal edits. (1) **Note 119 now in scope** — P3 gains the Library **Plans & Documents "Editor" header** with Copy·Edit·Comment lifted inline/right-aligned, reusing Compose's ghost copy/clear icons (Assets drops them); removed from Out-of-scope, added to the TODO-removal + DESIGN-sync lists, P3 title/acceptance updated. (2) **Scratch/Log explicitly out** — P1b select-to-act + Embed/Attach scoped **Messages-only**, with a matching Out-of-scope bullet. (3) **Plans decision trio** preservation left to the standing "preserve what you weren't asked to change" rule (per human), reinforced naturally in the 119 bullet. (4) **Reply reference block** documented as a frozen `embed` block reusing the P1a primitive (P2 + the P1a consumer list). No product code changed.

Files: dev/prompts/link-behavior-refactor.md, DEVLOG.md

---

### 2026-06-25 22:51:21 — Link-behavior refactor P0: Ultraplan removed + Mode-toggle reverted to labeled buttons

First phase of the `dev/prompts/link-behavior-refactor.md` run. **Ultraplan removed entirely** from `design/mockup.html`: the `.ultra-tog` toggle (both Details + Create), `toggleUltra`/`syncUltraGate` JS, the `syncUltraGate` calls in `segPick`/`setSegActive`/init, the `.plan-ultra` CSS + the plan-card Ultraplan tag render, the `ultra` field on all three `PLANS` rows, and every `ultraplan` string (incl. two changelog comments + a CSS comment) — verified `grep -i ultraplan design/` returns 0 matches in the mockup (only the legitimate Effort-seg "Ultra" buttons remain, untouched). **Mode toggles reverted** from the `.swh` slider style to the **labeled toggle-button style** (the brief's named v10p6 target was actually the short-label button style; the "Opus fast-mode Off/On" long-label markup + label-rewriting JS live in v10p2/v10p4 — pulled from there per the brief's explicit `(reads 'Opus fast-mode Off/On')` intent). Now **two toggles only** in a 2-col grid in both Details + Create, labels read their own state (**Opus Fast-Mode Off/On**, **Thinking Mode Off/On**), the whole button fills teal when on. **Opus Fast-Mode stays gated to Opus** (`gateFast` now also resets the label to "Off" when it clears `.on`); Thinking ungated. Synced `design/DESIGN.md` (Mode-block paragraph → two labeled toggle-buttons; Create wizard line) and `design/TODO.md` B4 (dropped the "must support the new native ultraplan functionality" clause).

**Verified in-browser** (Playwright MCP, served :8801) at narrow (990) + wide (1920): 0 console errors (favicon 404 only); `syncUltraGate`/`toggleUltra` are `undefined`; Details shows ungated Fast + Thinking-On, Create shows gated Fast (Inherit) + Thinking-Off; click-through confirmed Fast on→"On"+teal, Think off→"Off", model Opus→Sonnet gates+clears Fast to "Off", gated click is a no-op, Sonnet→Opus un-gates; labels show full at wide and ellipsis-truncate gracefully at narrow with no row overflow (icons + tooltips disambiguate, the established pattern). Nothing else in the Agent panel shifted. (Note: the Playwright MCP browser's headless/headed mode is fixed at server launch — re-screenshotted the touched states at both extremes as the parity check.)

Files: design/mockup.html, design/DESIGN.md, design/TODO.md, DEVLOG.md

---

### 2026-06-25 23:13:44 — Link-behavior refactor P1: block primitive · feed select-to-act · badge tightening

The foundational phase P2–P4 lean on. **P1a — inserted-block primitive:** added `blockHTML(kind,o)` (+ `citeHTML`, `removeBlock`, `toggleBlockClamp`, `selectTplBlock`, `gotoCitation`) and an `.ed-block` CSS family — one renderer, three variants: **embed** (frozen quoted content: "from <source>" header, click-to-source, remove ×, clamp+expand), **template** (same shell but selectable/active), **citation** (`.ed-cite` inline pill). Boundary uses the card-outline colour (`--border` navy), not the tan divider. Built as a reusable scaffold; it's wired into the editor in P3 and consumed by P2 (Reply) / P4 (embeds, citations), so its DESIGN.md write-up lands when it's visible there. **P1b — feed select-to-act (Messages only):** new `msgCardHTML`/`msgRailHTML` replace `fcardHTML` for the Messages list (Scratch still uses `fcardHTML` + its checkbox, per scope). Removed the per-card checkbox → **click the header to select the whole card** (pink `--main-dim`, multi-select) with a **select-all** (`#msg-selall-btn`, Messages-only via switchTab) in the action strip; the **chevron is its own button** so *select ≠ expand*. Each card gets a **block rail**: the default message text + each typed block are individually selectable (teal `--select`), and the rail tracks the active **Content** filter — `applyMsgFilters` now hides whole `.mrow[data-blk]` rows (rail + content) and clears a hidden block's selection. Card-select clears any block-select and vice-versa (one intent at a time → Attach vs Embed in P4). Relabelled the feed controls **Filter→From/To · Show→Type · Include→Content**. **P1c — badge tightening:** `.badge`/`.badge-more` 32→**30px** (matches the footer action-button footprint, so the P4 Review chip's full badge isn't taller than its neighbours), and `.agtile` background → `currentColor` so a non-square badge tile shows the agent colour edge-to-edge instead of **white strips** above/below the icon's square (zero glyph distortion; square tiles + the `--ag-user` tile are unaffected).

**Verified in-browser** (Playwright MCP, :8801) at narrow (1000) + wide (1920): 0 console errors (favicon only). Confirmed numerically + visually: dropdown badges = 30px (= footer Revise/Approve/Summarize) with letterbox 0 / tile bg = agent colour, graph + user tiles unregressed; header-click selects the whole card pink (not expanded), chevron expands, block-rail click selects one block teal (clears the card), Content filter hides block rows + clears their selection, select-all toggles all; block primitive renders all three variants (navy boundary, from-header, ×, clamp/"Show more", active template, citation pill) via a transient injection (not committed). No row/card overflow at either extreme. Synced `design/DESIGN.md` (Team Feed From/To + Messages select-to-act & Type/Content relabels; the Library doc-editor note that the Feed shares the model; the Design-system identity-badge height + edge-to-edge tile convention). (Playwright MCP browser mode is fixed at launch — re-screenshotted touched states at both extremes as the parity check.)

Files: design/mockup.html, design/DESIGN.md, DEVLOG.md

---

### 2026-06-25 23:16:00 — Queue Turns-breakdown dropdown in design TODO

Added a **Next up** item to `design/TODO.md`: turn the Agent panel's Turns bar into an expandable dropdown like Context (its own `.ctx-trigger`, a `breakdownHTML`-style accordion), breaking turns out **by tool used** (Read/search · Edit/Write · Bash · MCP · Subagent · Web) with a **Coordinating** slice folded in for the multi-agent angle, header mirroring Context (`34/50 · 68% · 16 left`), demo data only. Captures the in-session design direction; no mockup change yet.

Files: design/TODO.md

---

### 2026-06-25 23:31:37 — Link-behavior refactor P2: Inbox restructured into typed sections + Error type

Rebuilt the Inbox around **typed sections** — **Permission · Plan · Decision · Error** — rendered by a sectioned `renderInbox` (`INBOX_SECTIONS`, section header carries the label + count, empty sections skipped, count updates / section drops on resolve via `inboxAfterRemove`). The **per-card type badge is gone** (the section conveys type), superseding the reddish→copper attention ramp (TODO C7). **Approval → Plan**, and **Plan cards drop Approve/Reject** — only **Review** (→ Library Plans via `reviewPlan`) + Reply (approval/verdicts live in the Plans tab). **Decision** is documented as the `AskUserQuestion` surface (one question/card) — options + an Approve gated until you pick + Reply. **New Error type:** `inboxCardHTML` renders inline error text + **Retry · Dismiss · Reply** (no View, no Forward), a short **subtype** chip, and a **danger left-edge** (`.inbox-card.inbox-card--error`, 2-class to beat `.fcard`'s border shorthand); the Error section header is danger. **Wired the failed→Error example:** the Messages `status:'failed'` drew/ECONNREFUSED card is now `status:'error'` (badge reads **Error**, `.db-failed`→`.db-error`), and drew's REQS entry is an **Error** card — so drew's graph **Pending** badge jumps to it. **Reply generalized** (`inboxReply`): pre-fills the Editor with a **frozen `embed` reference block** (the P1a primitive) quoting the card — a Decision embeds the question + options; Plan/Permission/Error the detail — and pre-targets the agent; **Retry** (`inboxRetry`) loads the last command into the Editor (not the Console). **Status colours reconciled:** Error owns danger; Pending stays warning; no collisions (Error reuses the existing `--danger`, so no tokens.css change needed).

**Verified in-browser** (Playwright MCP, :8801) at 1500 + narrow 1010: 0 console errors. Confirmed: 4 sections one-each, 0 legacy `.dbadge` type badges, Plan=[Review,Reply], Decision=[Approve(disabled),Reply]+2 options, Error=[Retry,Dismiss,Reply]+subtype "Connection"+danger edge+inline ECONNREFUSED text; Messages badges show **Error** (not Failed); Reply inserts an embed block sourced "Inbox · Plan from researcher 01 sandy" and targets sandy; drew Pending badge → opens+selects drew's Error card; no card/list overflow at the narrow extreme (actions wrap). Synced `design/DESIGN.md` (rewrote *The Inbox tab* → typed-section table with Error + AskUserQuestion Decision + Plan-loses-Approve/Reject + generalized Reply-embed; Design-system danger row + retired attention-ramp paragraph + badge-families note; Team-Feed Inbox row + the Team Feed hover-card). TODO.md Inbox-note removals batched for the final housekeeping pass. (Playwright MCP browser mode fixed at launch — re-checked touched states at both extremes.)

Files: design/mockup.html, design/DESIGN.md, DEVLOG.md

---

### 2026-06-25 23:38:08 — Response-popover design sketch in design/ui-snippets

New standalone snippet `design/ui-snippets/response-popover.html` (first file in the new `ui-snippets/` dir) — an "ideal" version of the Compose-footer Response settings popover, not wired into the mockup. Links `../tokens.css`. Reworks the current `#fmt-menu`: wider (340px), single-select axes → `.seg` segmented controls with graded options (Length/Altitude/Register), multi-select axes → `.tog-cell` toggle grids (Structure/Emphasis), a STYLE/BEHAVIOR split, a new **Pace** dial (Snap→Deep) framed as independent of the agent's Effort tier, a Reasoning-shown axis, and an override-count badge.

Verified in-browser (Playwright MCP, :8802) at 1280 + 560: caught left-anchor overflow at the narrow width → switched the popover to right-anchor (`.fmt-menu.right` + `max-width:calc(100vw-24px)`) → re-verified clean at both extremes. Exercised the controls: seg single-select, multi-toggle, group-level override badge (3 axes changed → badge 3), Reset → defaults/badge hidden. Console clean (favicon 404 only).

Files: design/ui-snippets/response-popover.html, DEVLOG.md

---

### 2026-06-25 23:44:05 — Response-popover: toggle cells match segmented-button type/sizing

Restyled the multi-select `.tog-cell` toggle grids in `design/ui-snippets/response-popover.html` to read identically to the `.seg` segmented buttons — dropped the all-caps + letter-spacing + drop-shadow + fixed 28px height, now 9.5px / weight-700 (active 800), muted colour, `6px` vertical padding, and the seg's background-tint hover. Still standalone bordered boxes (not connected), per request. CSS-only; interaction logic unchanged.

Verified headless with an **isolated throwaway Chrome profile** (not the shared Playwright MCP browser — another agent is on the UI) via `--screenshot` over `file://` at 1280 + 560. Confirmed: toggle cells now match the segments in text size/weight/case and button height, the `.on` teal matches segment `.active`, and the right-anchored popover stays clean with no overflow at the narrow extreme. Shots in `artifacts/shots/`.

Files: design/ui-snippets/response-popover.html, DEVLOG.md

---

### 2026-06-25 23:53:32 — Turns-dropdown design sketch in design/ui-snippets

New standalone snippet `design/ui-snippets/turns-dropdown.html` — the Agent-panel Turns breakdown idea from TODO Next up, built on Context's own primitive (`.ctx-trigger` + `.acc` accordion + `.bd` breakdown, CSS copied verbatim from the mockup; links `../tokens.css`). Shows Context collapsed above + Turns open below so the bar alignment + parallel are visible. Turns broken out **by tool** (Read/search · Edit/Write · Bash · Coordinating · MCP · Subagent · Web) summing to 34, with a **Remaining 16** segment closing the 50-turn budget (parallels Context's Free space), header `34 / 50 · 16 left`, a health-amber 68% summary bar, and two drill-downs (`/ Tools used (calls)`, `/ Coordinated with`) paralleling Context's memory/agents subs.

Verified headless with an isolated throwaway Chrome profile (not the shared MCP browser) via `--screenshot`/`file://`. Note: Chrome-on-Windows clamps the window to ~484px min, so `--window-size` below that just *crops* a 484px layout — a debug overlay (`vw=484`) confirmed the apparent narrow-overflow was that crop artifact, not a real bug. Tested true narrow via an iframe forcing 300px + 420px panel viewports: clean at both + full width, no clipping. Hardened the page meanwhile (fluid panel `width:100%;max-width:360`, block layout + `margin:auto`, caption `width:100%`).

Files: design/ui-snippets/turns-dropdown.html, DEVLOG.md

---

### 2026-06-25 23:54:36 — Link-behavior refactor P3: Compose→Editor · templates-as-blocks · attachment strip · Library Editor headers

**Prompt panel:** renamed the **Compose heading → "Editor"** and reordered the tab to **attachment-strip → Editor → Templates** (#118). New `#attach-strip` (#109) renders horizontal chips styled like the Library nav cards from an `ATTACH` array — each with a **remove ×** + **click-to-open in the Library** (`renderAttachStrip`/`openAttachmentCard`/`removeAttachment`/`addAttachment`; seeded with 2 representative items, hidden when empty). **Templates now insert as blocks:** `applyTemplate` builds a selectable **`template` block** (the P1a primitive) at the cursor instead of inline raw text; the **active** block (`.sel`) is what the fill input drives — `onTplBlockSelected` enables the fill + syncs the picker, and `pickPlaceholder` now also activates a pill's parent block. None deselects + greys. So the Editor holds free prose + stacked delimited blocks (frozen embeds + interactive templates). **Library (#119):** added an **"Editor" header** (label + right-aligned ghost **Copy·Edit·Comment**, reusing Compose's `.ghost-ic`) above the content in **Plans + Documents** (`editHeadHTML`; doc placeholders + `renderDocs` fill; `planCardHTML` inserts it above `.plan-rev`); `libFootHTML`/`planFootHTML` **dropped Copy·Edit·Comment** from the footers (Documents/Assets footer = Link-to-prompt + Remove; Plans footer = Share·Review + decision trio). **Assets drop the three buttons entirely** (no Editor header — an image isn't text-editable). `docEdit` toggles icon-only (pencil↔check) so the ghost button stays icon-only.

**Verified in-browser** (Playwright MCP, :8801 — cleared a stale locked MCP-chrome profile to relaunch) at 1500 + narrow 1010: 0 console errors (favicon only). Confirmed: compose order = attach-strip→editor-header→editor-field→templates(header/select/fill); Editor label; 2 attach chips (remove 2→1 works, click opens Library); template pick → 1 active block w/ 5 pills + fill enabled; pill click activates its block, Apply fills the pill ("src/auth/*"→"src/auth/tokens.ts"), block ×-removes; Documents Editor header (3 ghost btns) + footer [Link, Remove]; Plans Editor header (3 ghost) + footer has no icon-btn Copy/Edit + Share/Review/decision; Assets has no Editor header + footer [Link, Remove]. No overflow at the narrow extreme (strip wraps, blocks/headers fit). Synced `design/DESIGN.md` (Prompts Compose bullet → Editor + attachment strip + templates-as-blocks; The Templates flow → the 3-variant block primitive + templates-below-as-blocks; Library Plans footer→Editor-header split + Documents/Assets card-shape + the Conventions icon-style note + the layout ASCII). TODO.md note removals batched for the final pass.

Files: design/mockup.html, design/DESIGN.md, DEVLOG.md

---

### 2026-06-25 23:55:00 — TODO Next up: point Turns + Response items at their snippets

Trimmed the **Turns Breakdown Dropdown** Next-up item to a one-liner that defers to `design/ui-snippets/turns-dropdown.html`, and added a **Response Settings Popover** item deferring to `design/ui-snippets/response-popover.html`. Both now reference their snippet as the design source with minimal inline explanation, rather than restating the spec.

Files: design/TODO.md, DEVLOG.md

---

### 2026-06-26 00:17:17 — Link-behavior refactor P4: Embed/Attach capstone · citations · Review chip · comment-bug fix

The content-sharing capstone — collapses sharing into one **Embed/Attach** control routed through the Editor. **P4a:** `embedAttachHTML(host)` renders a selection-gated [Embed | Attach | link-icon] control; `eaSelKind`/`eaUpdate`/`eaUpdateAll` gate it (section/line/block → Embed; whole-doc/title or Asset or whole feed card[s] → Attach; both modes visible, the inapplicable one greys, link icon sends). It **replaces** the Share send-group + "Link to prompt" on the Library footers (`planFootHTML`, `libFootHTML`) and the Feed action strip. **Embed** drops a frozen `embed` block into the Editor from the selection (`eaEmbed`/`eaEmbedFeed`/`insertEmbed`); **Attach** adds a strip chip (`eaAttach`/`eaAttachFeed`) — a real path for files, a `/tmp/awl/...` **materialized temp path** for feed content. Gating wired into `railClick`/`clearSel` (Library) + `msgCardSel`/`msgBlkSel`/`msgSelectAll` (Feed) + `eaUpdateAll()` on init. **P4b — citations:** each attachment chip gets a link icon → `citeAttachment` inserts an inline `citation` pill (carrying the att id) at the cursor; `onAttachmentRemoved` cascades (removing an attachment deletes its citations); deleting a citation leaves the attachment; you can only cite an existing attachment (trigger lives on the chip). **P4c — Review chip:** `reviewChipHTML`/`revRowHTML`/`pickReviewer`/`sendReview` replace the Plans multi-select Review send-group with a single-agent reviewer select (full agent badge trigger — 30px from P1c — + an icon-only `scan-search` send). **P4d — comment-bug fix:** the rail badge is now a **section anchor** — `railBadge`/`openCmtPop`/`selectMatchingCards`/`navCardClick` drop the worst-verdict filter, so a click opens **all** comments on the section (count matches), each row carrying its **own** verdict badge + thumbs.

**Verified in-browser** (Playwright MCP, :8801) at 1500 / narrow 1010 / wide 1920: 0 console errors. Confirmed: Plan EA gates (no-sel→disabled · section→Embed · title→Attach), Asset→Attach default, Feed block→Embed / card→Attach; Embed inserts a sourced block ("Library → Plans · … · § Context"), Attach adds chips (asset real path; feed `/tmp/awl/feed-01 sandy-1441.md` temp); citation insert (1) + cascade-on-attach-remove (→0); reviewer pick vega→drew updates the badge; **P4d** §Approach badge=2 opens 2 comments [Revise, Approve] each with its own verdict (the old bug opened 1). Caught + fixed a narrow-overflow: the wider Embed/Attach made the Feed strip overflow by 44px at 1010 → added `flex-wrap` (one row at wide=30px, clean 2-row at narrow=68px, no overflow); Plans footer wraps too. Synced `design/DESIGN.md` (new *Sharing content into a prompt — Embed/Attach* subsection incl. payloads + temp-file note + citations + Review chip; the comment-popout → section-anchored; Library Plans/Documents/Assets footers; Team-Feed Messages footer; the teal emphasis-ladder row + Conventions + layout note). (Playwright MCP browser mode fixed at launch — re-screenshotted touched states at both extremes.)

Files: design/mockup.html, design/DESIGN.md, DEVLOG.md

---

### 2026-06-26 00:22:51 — Link-behavior refactor: finish — TODO housekeeping, B13 deferred marker, final walk

Closed out the `dev/prompts/link-behavior-refactor.md` run (P0–P4 all built + logged above). **TODO.md:** the human had already cleared the implemented Inbox notes (Embed/Attach, Failed→Error, the relabels, Templates-below/Editor, the Editor-header, embedded-blocks) and reworked Next up, so the only housekeeping left was **closing C7** (Inbox Attention Ramp — superseded by the typed Inbox sections; removed + renumbered C8→C7, no inbound xrefs) and the **B4** ultraplan clause (done in P0). **B13 deferred marker:** extended **B13 (Reviewer Link)** to capture the deferred **Review/Inbox formalization** (single-reviewer-agent model, how agent verdicts resolve, how the human gate relates to agent review) — P4c built only the Review *control*; the workflow stays deferred. **Final headed walk** (Playwright MCP, :8801) at wide 1920 + narrow 1010, 0 console errors: regression-invariants all hold — P0 two labeled Mode toggles + `toggleUltra` undefined; P1c badges 30px; P1b 8 msg select-to-act cards, no checkbox; P2 four Inbox sections incl. the danger Error card; P3 Editor label + attachment strip; P4 11 Embed/Attach controls + 3 Review chips, the Share send-group gone and no visible "Link to prompt"; nothing outside the requested changes regressed at either extreme. (Playwright MCP browser mode is fixed at launch — the walk ran through the single configured browser; touched states re-screenshotted at both extremes as the parity check.)

Files: design/TODO.md, DEVLOG.md

---

### 2026-06-26 01:34:03 — Plans editor + left-rail design sketch in design/ui-snippets

New standalone snippet `design/ui-snippets/plans-editor-rail.html` covering two Library→Plans asks in one mock (NOT wired into the mockup; the other agent owns `mockup.html`). Reuses the mockup's `plan-nav` / `doc-ed` / `md-rail` CSS, links `../tokens.css`. **Bullet 1:** the "Editor" header sits over the editor box only, nav rail (Outline/Feedback) rises to the top full-height — the Documents arrangement. **Bullet 2 (the `.md-rail` UX):** colour strips 6px (was 3px); `.md-row` `align-items:stretch` so rail blocks cover wrapped-line height (no gaps); editor body flex-fills + a trailing filler continues the rail track to the bottom past the last line (Plans is capped at `max-height:300px` today, Documents already fills); hover lights all associated text in **canvas cream `--background`** (line→that wrapped line, section→whole section, title→whole doc) via JS reusing the section grouping.

Verified headless (isolated throwaway Chrome profile, `--screenshot`/`file://`): default render confirms the layout + thick strips + wrap-fill + rail-to-bottom; temporary auto-apply of `.hl` captured the title-hover (whole doc) and section-hover (section only) cream states; iframe-forced 460px viewport confirms no overflow when narrow (content scrolls). Shots in `artifacts/shots/`.

Files: design/ui-snippets/plans-editor-rail.html, DEVLOG.md

---

### 2026-06-26 01:34:58 — Link-behavior refactor: stale-sweep + dead-code removal across design/

Post-refactor cleanup pass so `design/` carries no stale comments or orphaned code. **mockup.html — removed dead code** the refactor orphaned: the JS `sendGrpHTML` · `sendTo` · `libLink` · `libComment` · `commentCtlHTML` · `updateSendCount` (+ its 3 call sites in `toggleAgRow`/`agAllNone`/init — it was a guarded no-op once the Share/Review send-groups went), the dead `.db-permission/.db-approval/.db-decision` CSS, and all the orphaned `.send-grp/.send-act/.send-trig/.send-lbl/.send-cnt/.send-cv` CSS (carefully split the live `.plan-foot > .btn` rule out of its shared `.send-grp` selector). **Fixed stale inline comments** to current behavior: the `.icon-btn` usage note (Copy·Edit·Comment moved to the ghost Editor header), the Documents/Assets + Plans footer comments (Embed/Attach, not Share/Link-to-prompt), the `reviewPlan` "Approval card"→"Plan card", and the retired Inbox request-ramp CSS note. **Added a current-state changelog block** atop the mockup's header comment summarizing P0–P4 (the per-version blocks below stay as history). **tokens.css:** marked the `--req-*` + `--req-*-soft` tokens as the **retired** attention ramp — retained but no longer referenced (Error owns `--danger`). Confirmed `grep` finds 0 residual references to any removed symbol/class.

**Re-verified in-browser** (Playwright MCP, :8801) after the removals: 0 console errors (favicon only); smoke test green — From/To All/None toggle still works (the `updateSendCount` drop was behaviour-neutral), the Plans footer Embed/Attach (30px) + Review chip (30px) render and gate correctly (section→Embed enabled), the four Inbox sections intact. DESIGN.md/TODO.md confirmed in sync — their remaining "Share"/"Link to prompt"/"reddish→copper" mentions all describe what was *replaced/retired*, not current state; referenced anchors resolve.

Files: design/mockup.html, design/tokens.css, DEVLOG.md

---

### 2026-06-26 02:10:00 — TODO: queued "Jump-to-End Pill (all scrollable windows)" in Next up

Added a new **Next up** item (#3) to `design/TODO.md`: a floating "jump to bottom / jump to top" pill (Slack/Discord/terminal-style — appears when scrolled away from an edge, snaps to the extreme on click, hides at the edge) to be applied to every scrollable window, styled from `tokens.css`. Marked as the broader companion to the feed-specific A2 "Jump to Feed Ends"; no snippet — implement directly in the mockup when given the go-ahead. Planning only; nothing built.

Files: design/TODO.md, DEVLOG.md

---

### 2026-06-26 02:05:01 — Plans editor + rail snippet: redone as a faithful first-card clone

Replaced the earlier reinvented `design/ui-snippets/plans-editor-rail.html` (01:34) — which would have misled a porting agent — with a **verbatim 1:1 clone of the mockup's first plan card** (PLANS[0] "Auth token-rotation remediation", open), assembled by a subagent: the card's CSS + render JS + data copied straight from `mockup.html` (badges, agent tile, verdicts, Outline/Feedback nav, Embed/Attach + Review + decision footer), links `../tokens.css`, lucide via CDN, with deep send/comment machinery stubbed to no-ops (markup/CSS intact). The **only** intentional diffs are isolated + labelled (a trailing "SNIPPET CHANGES" CSS override block + JS tagged `bullet 1`/`bullet 2`/`CHANGED`): **bullet 1** — Editor header moved inside `plan-main` (over the editor box only), nav rail rises to the top full-height (Documents-style); **bullet 2** — rail strips 6px (was 3px), `.md-row` stretch so blocks cover wrapped-line height, editor flex-fills + filler row runs the rail track to the bottom, hover lights all associated text in canvas cream (`--background`); **plus** Outline-section click now runs `railClick` so it selects the whole section identically to a section rail-click (was a brief `.md-target` header flash).

Verified headless (isolated throwaway Chrome, `--screenshot`/`file://`): faithful render confirmed vs the clone; temp auto-invokes captured the cream section-hover, the Outline-click pink whole-section select, and the collapsed (header-only) open/close toggle; fill-to-bottom shown by raising the demo editor height above the doc length; 520px narrow check reflows with no overflow (title wraps 3 lines, strip covers all). Shots in `artifacts/shots/` (`plans-rail-v2-*`).

Files: design/ui-snippets/plans-editor-rail.html, DEVLOG.md

---

### 2026-06-26 02:12:29 — TODO Next up: queued Library Plans/Documents editor rail + layout

Added Next-up item #4 to `design/TODO.md` deferring to `design/ui-snippets/plans-editor-rail.html` for context: the Library→Plans/Documents editor changes — Editor header over the editor box + nav rail to the top (bullet 1), the `.md-rail` UX (6px strips, wrap-fill, fill-to-bottom, canvas-cream hover; bullet 2), and routing the Outline-section click through `railClick` for parity with the section rail.

Files: design/TODO.md, DEVLOG.md

---

### 2026-06-26 02:48:37 — Messages-card rail/blocks/multi-select design sketch

New snippet `design/ui-snippets/messages-card.html` — the same real Messages feed card (the `max` ACTIVE/RECV card with bash/diff/write blocks, cloned verbatim from `mockup.html` via a subagent: `msgCardHTML`/`msgRailHTML`/`msgBlockHTML` + badge/tile/sprite + CSS, links `../tokens.css`) shown two ways. **Current** = the verbatim mockup (thin teal per-block rail, discrete sub-cards, single block-select), static. **Proposed** (isolated in a "SNIPPET CHANGES" CSS block + `*V2` JS builders): the per-block rail restyled to the Library `.md-rail` look — narrow tan box + a small **uniform teal** accent strip, no numbers; the blocks collapsed into one **contiguous panel** (bordered box, hairline dividers, no gaps) so they read vertically continuous and Library-like; and **multi-select within a card** (toggle, one card at a time — selecting blocks in another card clears this one's; still mutually exclusive with the whole-card pink select). Reflects the answered decisions (uniform accent, one-card-at-a-time).

Verified headless (isolated throwaway Chrome, `--screenshot`/`file://`): side-by-side at 1180 (seeded states — Current 1 block, Proposed 2 blocks — show single vs multi at a glance) and stacked at 600 (responsive, no overflow). Shots `artifacts/shots/msg-card-v2*`. Scratch clone removed.

Files: design/ui-snippets/messages-card.html, DEVLOG.md

---

### 2026-06-26 02:59:22 — TODO Next up: queued Messages card rail + blocks + multi-select

Added Next-up item #5 to `design/TODO.md` deferring to `design/ui-snippets/messages-card.html` (the "Proposed" column): restyle the Messages per-block rail (`.mrail`) to the Library `.md-rail` tan-box + uniform-teal-strip look (no numbers); collapse the per-block sub-cards into one contiguous panel (dividers, no gaps); and allow multi-select within a card (one card at a time, mutually exclusive with the whole-card pink select).

Files: design/TODO.md, DEVLOG.md

---

### 2026-06-26 03:05:00 — Snippet: square agent-card redesign + TODO Next up #6

Built `design/ui-snippets/agent-card.html` — a standalone sketch of the reorganised Team Graph agent card (NOT wired into the mockup). One overloaded grid of four square cards, each demonstrating a different state, covering every new element: **model in the header** with an **opus-only FAST lightning bolt** (bright = on / muted = off / hidden for non-opus — cards A/B/C-D), **three icon chips** (mode·effort·think) in a **two-column body** beside narrower Ctx/Turns bars, a full-width **current-run block** (live status + single-colour progress keyed to status — determinate green / barber-pole indeterminate / warm pending / muted idle), an **age stamp** (datetime + auto-scaling duration), and **square subagent badges** (neutral fill, agent-colour text, quiet hairline + `SUBAGENTS` label, `+N` overflow). Chrome mirrors the mockup's `.node` family; values from `tokens.css`; Lucide for icons. Verified in-browser (Playwright, :8807) at 900/820/360px — fixed an age-stamp truncation by moving it to its own full-width line; all states render, no clipping at real ~186px card size. Filed as **TODO Next up #6** ("Agent Card Redesign (square)") with the full spec + five open decisions (FAST override greying, subagent sub-status encoding, empty-state collapse-vs-reserve, progress-% source, pale-colour text contrast). Planning only — nothing built into `mockup.html`.

Files: design/ui-snippets/agent-card.html, design/TODO.md, DEVLOG.md

### 2026-06-26 03:40:00 — Messages-card snippet: corrected to match the Library rail (pink select, cream hover, turn-number whole-select row)

Reworked the "Proposed" column of `design/ui-snippets/messages-card.html` after grounding in the actual renders (Library `plans-editor-rail.html` + the Messages card). Four corrections, all isolated in the "SNIPPET CHANGES" CSS block + `*V2`/`msgWholeSel` JS: (1) **hover** now mirrors Library — `.mrail--lib:hover` tints the rail cell pink and the row's content lights **cream** (`--background`), declared after `.bsel` so a selected row still previews cream; (2) a **top title row** holds the **turn number** in the doc-title style (`.msg-turn`, weight 900 / 12px) with a pink strip, and `msgWholeSel` makes it select the whole message (toggles every row pink, one card at a time) — the header preview repoints to it too (replacing `msgCardSelV2`); (3) **selection is now always light pink** (`--main-dim`) for rail cell + content (was teal `--secondary`/`--select`); (4) the rail/text **seam** is gone — `border-right` blends to `--main-dim` on select. Added `turn:17` to the demo MSGS object. Verified headless (own throwaway Chrome profile) at 1300px + 600px and in seeded whole-select / hover states; the verbatim "Current" column is untouched. Headed parity pass deliberately skipped — per the session instruction to stay fully headless while another agent works the UI. Snippet only; nothing wired into `mockup.html`.

Files: design/ui-snippets/messages-card.html, DEVLOG.md

### 2026-06-26 04:05:00 — Messages-card snippet: drop rail strips, whole-card cream hover, review-style type badges

Second pass on the "Proposed" column of `design/ui-snippets/messages-card.html` (snippet only): (1) **removed the rail colour strips** — the rail is now a plain tan select handle (the top whole-select row is identified by its bold turn-number content, not a strip; `.mrail--title` kept as a JS hook only); (2) **title hover now lights the WHOLE card cream** — hover moved from pure-CSS adjacent-sibling to JS `msgRailHover`/`msgRailHoverOut` adding `.hl` (a block rail lights its own row, the top title rail lights every row), mirroring Library's `railHover`; (3) **tiny type badges** — added `.blk-badge` matching the Plans review badge `.vbadge` geometry (18px, 2px border, 9px/800 uppercase) via a new `msgBlockHTMLv2`; each block shows Thought/Bash/Diff/Write and the primary prose is tagged **"Message"** (it maps to no tool filter); the old inline `BASH`/`DIFF` labels are gone. Current column stays verbatim (untouched `msgBlockHTML`). Verified headless (own throwaway Chrome) at 1300px + 600px and in seeded whole-select, block-hover, and title-hover(whole-card) states. Headed parity pass deliberately skipped per the session instruction to stay fully headless while another agent works the UI. Nothing wired into `mockup.html`.

Files: design/ui-snippets/messages-card.html, DEVLOG.md

---

### 2026-06-26 03:55:00 — Agent-card snippet v2: full restructure per review feedback

Rebuilt `design/ui-snippets/agent-card.html` after the v1 layout was rejected (not actually square, cramped half-width bars, no real feed treatment). v2 is a **single-column fixed square** (190×190): header with **model right-justified + bottom-aligned to the name** (opus-only FAST bolt trailing, hidden for non-opus) and the **age stamp before a full-bleed divider**; a neobrutalism **Marquee** (two-track `marquee`/`marquee2` loop, replicated from neobrutalism.dev) streaming the **live feed**; the **Run** status bar; **inline** mode·effort·think icon chips; then **Ctx/Turns** — all three bars sharing one row template so widths match and run full. Dividers are **full-bleed** (border colour). Subagents are now **bold, agent-colour, neutral clickable badges** (`+N` overflow) with the header label dropped, in a **reserved fixed-size section** (idle/0-sub cards show a muted "no subagents" placeholder) so all cards stay uniform squares. Four cards exercise FAST on/off/hidden, determinate/indeterminate/pending/idle Run, and 3/1/0/6-sub states. Verified in-browser (Playwright, :8807) at 900px + 430px — square holds on reflow, feed scrolls/pauses-on-hover, badges show the press. Updated **TODO Next up #6** to the v2 spec (resolved: model→header, single-column, marquee, full-bleed dividers, reserved subagent section, header dropped; still open: FAST override greying, subagent sub-status encoding, progress-% source, pale-colour contrast). Planning only — nothing in `mockup.html`.

Files: design/ui-snippets/agent-card.html, design/TODO.md, DEVLOG.md

---

### 2026-06-26 04:20:00 — Agent-card snippet v3: activity-band refinement

Tightened `design/ui-snippets/agent-card.html` per review. Introduced a full-bleed **activity band**: one container whose top/bottom borders are the two dividers, holding the **textless Run progress strip** (no border/label/value, single-colour keyed to status) sitting **flush on top of** the **Marquee** feed (now **no fill / no padding / full bleed**) with no gap — the Run bar left the labeled-bars group. Below the band, the three **mode·effort·think** chips now **spread full width** (`space-between`, edges aligned to the bar rows); the bars group is just **Ctx + Turns**. Verified in-browser (Playwright, :8807) at 900px + 430px — band reads as a clean ticker, square holds on reflow, all four states (determinate / barber-pole indeterminate / muted-idle / warm-pending) and FAST on/off/hidden render correctly. Updated **TODO Next up #6** body to the band model. Planning only — nothing in `mockup.html`.

Files: design/ui-snippets/agent-card.html, design/TODO.md, DEVLOG.md

---

### 2026-06-26 04:45:00 — Agent-card snippet v4: activity band relocated to the bottom

Per review, moved the activity band (Run strip + Marquee) from under the header down to the **bottom**, pinned directly above the subagent strip (`.band` now `margin-top:auto`), and added a **third full-bleed divider between the Run strip and the Marquee** so the bottom stack reads `divider → Run strip → divider → Marquee → divider → subagents` (the band's bottom border doubles as the subagent divider). The top of the card is now a clean, divider-free block: header + age → full-width `mode·effort·think` chips → Ctx/Turns bars. Also answered the user's question — the coder card's striped Run bar is the intentional **barber-pole indeterminate** loading pattern (working, % unknown), not a glitch. Verified in-browser (Playwright, :8807) at 900px + a 2.4× zoom pass on card A — all three band dividers render, Run strip + Marquee each bounded, square holds, four run states + FAST on/off/hidden correct. Updated **TODO Next up #6** body to the bottom-band layout. Planning only — nothing in `mockup.html`.

Files: design/ui-snippets/agent-card.html, design/TODO.md, DEVLOG.md

---

### 2026-06-26 05:05:00 — TODO #6 rewritten as a self-contained agent-card build brief

Consolidated the agent-card item (TODO Next up #6) into one clean implementation brief a fresh agent can build from with no conversation context: named the **port target** (`.node` cards in `.graph-grid`, and that the snippet copied `.node` chrome to map back), the fixed-square approach (lock `aspect-ratio:1` on the existing grid), the full top→bottom anatomy (header with model+FAST bolt+age · full-width chips · Ctx/Turns · bottom activity band `divider→Run→divider→Marquee→divider→subagents` · reserved subagent badges), explicit **build notes** (work from tokens, demo data only, keep DESIGN.md's Team Graph card section in sync, verify per the UI rules), and the four **open decisions to settle with the human** (FAST override, subagent working/idle encoding, Run-% source, pale-colour badge contrast). Removed the stale "age sits right before a divider" line (the v4 top block has no divider) and the version cruft. No snippet/mockup change.

Files: design/TODO.md, DEVLOG.md

---

### 2026-06-26 05:25:00 — Agent-card snippet v5: restore header divider; confirm age right-aligned

Per review, **restored the full-bleed divider under the header** (below the age line) in all four cards of `design/ui-snippets/agent-card.html` — the v4 "clean top block, no divider" choice was reverted to the original "divider under the header" look. The **age stamp was already `text-align:right`**; verified in-browser (Playwright, :8807, 2.4× zoom on card A + full set at 900px) that it renders flush-right, and that the new header divider sits below it with the square still holding (the bottom band's `margin-top:auto` absorbs the added ~14px). Updated the caption and **TODO Next up #5** (the human renumbered the agent-card item from #6 to #5): the Header bullet now states the right-aligned age is followed by a full-bleed divider under the whole header (dropped the "no divider under it" wording). Planning only — nothing in `mockup.html`.

Files: design/ui-snippets/agent-card.html, design/TODO.md, DEVLOG.md

---

### 2026-06-26 04:26:53 — Messages-card snippet: type tag moved INTO the rail box; realistic content for all block kinds

Reworked `design/ui-snippets/messages-card.html` (Proposed column) per fresh user feedback after a takeover review: the type tag now lives **inside the rail box** (was a bordered pill prefixed to the content) — a tight lowercase 3-char abbreviation (`msg · tht · rd · bsh · dif · wrt · mta`), **top-aligned**, **minimal** (transparent → shows the rail's tan, no pill/border), font size+weight matched to the Plans review badge (`.vbadge`, 9px/800). The **title row's rail box is empty** ("Turn 17" stays in the content as `.msg-turn`). Replaced `.blk-badge` CSS with `.rail-tag`; widened `.mrail--lib` 22→34px with flex top-align; added `RAIL_TAG`/`railTag()`, dropped `MSG_KIND_LBL2` and the inline content label from `msgBlockHTMLv2`. Demo data rewritten to exercise **all 7 block kinds** (message·think·read·bash·diff·write·meta) with realistic Claude-Code rendered text drawn from this UI session. Verified headless/isolated (default, narrow 600px, whole-select, block-hover, title-hover); skipped headed pass per the standing no-interfere rule. `mockup.html` untouched.

Files: design/ui-snippets/messages-card.html, DEVLOG.md

---

### 2026-06-26 05:55:00 — Agent-card snippet v6: age moved to a top meta strip

Per review (user picked the "top meta strip" option), moved the date/age out of its own row and up into a thin **top meta strip** across all four cards of `design/ui-snippets/agent-card.html`: the age is now **small (7.5px) and left-aligned** on the left, paired with the **status badge** on the right. To do it the `.node-badge` went from **absolute corner-pinned** to **in-flow** (new `.hd-meta` flex row, `justify-content:space-between`); `.age` lost its right-align/full-width and became a flex child. The identity row and the full-bleed header divider are unchanged below it. (Also corrected the earlier right-align to **left-align** as the user intended.) Verified in-browser (Playwright, :8807) at 900px + 2.4× zoom — meta strip reads cleanly, header divider still present, square holds across all four cards. Updated **TODO Next up #5** Header bullet to the meta-strip layout. Planning only — nothing in `mockup.html`.

Files: design/ui-snippets/agent-card.html, design/TODO.md, DEVLOG.md

---

### 2026-06-26 06:40:00 — mockup: Agent panel created-time + drop "Configuration" label

First **live `mockup.html`** change for the agent-card work (snippets aside). Agent → **Details** header: (1) **removed** the "Configuration — tap the pencil to edit a field" label line entirely (the per-field pencils stay, so the behaviour is unchanged); (2) added the agent's **created-time** (datetime + auto-scaling "ago" duration) **stacked right-aligned under the status badge** — placement chosen by the user. Wired it data-driven: added a `created` field to all 13 agents in the `AG` object and a line in `repaintAgentPanel` so selecting any graph card repaints it (verified: max → `06-26 13:05 · 3h37m`, sandy → `06-26 14:30 · 2h12m`). **Narrow-width fix:** the created-time first squeezed the agent name into wrapping at the 240px panel min — gave the name priority (`truncate`, and the badge/time column shares space `flex-1 min-w-0`) so the **name stays on one line** and the **time truncates** ("06-26 14:30 · …") at the extreme instead. Verified in-browser (Playwright, :8807) at normal width + 2.2× zoom (≈ panel min-width) + per-agent selection; 0 console errors. Synced `design/DESIGN.md` (Details now documents the header identity + status badge + created-time).

Files: design/mockup.html, design/DESIGN.md, DEVLOG.md

---

### 2026-06-26 06:55:00 — mockup: spread Agent-panel badge/created-time to tile top & bottom

Follow-up tweak — the status badge and created-time were bunched together in the centered right column. Set that column to `justify-between` + `h-10` (matching the 40px agent tile) so the **badge pins to the top of the tile and the created-time to the bottom**, with the empty space between them. Kept the outer row `items-center` so the name stays centered and only the badge/time column is affected — a clean flex change (no magic beyond matching the tile height) that maps directly to the eventual React build, per the user's ask not to pre-bake throwaway layout. Verified in-browser (Playwright, :8807): badge top = tile top (86px), created bottom = tile bottom (126px); full `06-26 14:30 · 2h12m` at normal width, name-priority/time-truncate intact at panel min-width. No DESIGN.md change needed (header description still accurate).

Files: design/mockup.html, DEVLOG.md

---

### 2026-06-26 06:57:00 — design: rough Context turn-scope select snippet

New ui-snippet `design/ui-snippets/context-turn-dropdown.html` — a rough exploration of the Inbox idea to scope the Agent-panel **Context** breakdown by turn. Replaces the breakdown header's `.bd-model` text with a **native `<select>`** (`All` default, then `Turn n…1` descending) and **enlarges the trailing ratio** (`.bd-tot`) so the two sit naturally inline; native select chosen deliberately to avoid a custom popover (free scroll/keyboard/a11y for long turn lists). Renders only the upper part (header + colour bar); demo data; flagged to be overwritten with the settled version. Verified headless (Playwright, :8123): `All` shows the full-window category stack + 80% cutoff, a turn shows that turn's internal composition, and the select stays inline with the enlarged ratio in both states.

Files: design/ui-snippets/context-turn-dropdown.html, DEVLOG.md

---

### 2026-06-26 06:16:10 — Snippets: teal-selection overhaul + reviewer-chip/badge/icon fixes (messages, plans, agent cards)

Reworked the selection system across `messages-card.html` + `plans-editor-rail.html` to make **teal the select colour** (pink eliminated from all highlights): rail-based selection (and the Messages whole-card select) → **light teal** (`--select`); Plans **feedback/badge highlight** (`fbhl`, click a Feedback card → its section) → **dark teal** (`--rail-section`, white ink) — the one place `#2f97a6` lives now; **rail strips removed** in Plans (plain tan rail box); rail-cell **hover → cream** (no pink); Plans title row enlarged so its whole-doc select-all box matches the Messages title box. Fixed three things the other agent left off: **box-sizing** — the clones don't load Tailwind (which gives the mockup `border-box`), so the footer chips rendered +4px and the reviewer-chip badge floated; added `*{box-sizing:border-box}` to both, which makes the **reviewer chip hug + all footer actions match the mockup's 30px**; Messages **agent badge → full `.badge` (reviewer-chip standard)** and header reordered to **agent → status → dir**; `agent-card.html` placeholder Lucide glyphs → the **real AG sprite icons** (wizard/robot/golem/gasmask) via the injected sprite. The **divider colour change (tan `--rule` → `--border`) was reverted** — it belongs to the held feed-cards/divider batch, not this turn. Verified headless/isolated (default, whole-select, block/title hover, Plans rail-select + dark-teal feedback, narrow, footer-chip zoom); skipped the headed pass per the standing no-interfere rule.

Files: design/ui-snippets/messages-card.html, design/ui-snippets/plans-editor-rail.html, design/ui-snippets/agent-card.html, DEVLOG.md

---

### 2026-06-26 07:10:00 — design: context-dropdown.html (full breakdown + turn-scope select)

New `design/ui-snippets/context-dropdown.html` replaces the rough `context-turn-dropdown.html` (removed): a faithful clone of the mockup's **full** Context breakdown (CSS lifted verbatim from `mockup.html`) with only the confirmed changes — the `.bd-model` text becomes a **native `<select>`** (`Total` default, then `Turn n…1`), the trailing `.bd-tot` ratio is enlarged + the header centered, and selecting a turn rescopes the header (`20.4k / 1.0M · 2.04%` — same metric type, turn tokens / window · 2-dp share), the bar, and the row %s (% of that turn) while the loaded-context sub-sections stay put. A small native-select width-fit makes the short `Total` label hug the chevron instead of floating in a box sized to the widest option. Verified headless (Playwright, :8123): Total = faithful snapshot with the 80% cutoff; Turn 24 = Messages/MCP/Memory composition summing to 100%, no cutoff; select hugs chevron in both. Headed parity pass deferred to mockup integration.

Files: design/ui-snippets/context-dropdown.html (added), design/ui-snippets/context-turn-dropdown.html (removed), DEVLOG.md

---

### 2026-06-26 07:12:00 — design/TODO.md: queued Context Turn-Scope Select in Next up

Filed the resolved context-by-turn design into **Next up** as item 6 (**Context Turn-Scope Select**), referencing the snippet `design/ui-snippets/context-dropdown.html` with port guidance: replace the breakdown header's `.bd-model` text with the native `Total` / `Turn n…1` select, enlarge `.bd-tot`, and rescope the header / bar / row-%s to the selected turn (header % = share of the window, 2-dp; rows = % of the turn — the differing denominators are intentional), keeping the sub-sections + the native-select width-fit; demo data only, sync `DESIGN.md` + verify per the UI rules. The originating Inbox note had already been cleared by the human. Queued item only — nothing built in the mockup.

Files: design/TODO.md, DEVLOG.md

---

### 2026-06-26 07:13:00 — Snippets: badge centering + navy dividers + plans footer/heading fixes (messages, plans)

Three approved follow-up batches. **messages-card.html** — the RECV/dir tag now centers to the Active status badge (`.fcard-dir` made `inline-flex; align-items:center` so its inline child is measured as a box like `.dbadge`, instead of painting low); the 3 structural dividers (card-body rule, block-to-block rule, rail separator) flipped tan `--rule` → navy `--border`. **plans-editor-rail.html** — **structural dividers only** flipped to navy (section rules, list-row separators, the gutter/rail separator, popover header, cmd-group rule) while the **inline code-chip + count-badge outlines stay tan** (per the user's confirmed "structural dividers only" scope); selected/feedback rows suppress the navy rail seam (`border-right-color` → `--select` / `--rail-section`) so selection reads as one clean teal / dark-teal band; the **Link (Embed/Attach) chip moved into the right action group leading Revise**, leaving the **reviewer chip as the only left-aligned action**; defined the missing **`.flex-1` utility** (these clones don't load Tailwind, so every `flex-1` spacer was dead) which right-aligns the Editor-heading ghost buttons **and** restores the plan-head rows (status badge / steps / dates) to mockup parity; the right action group now wraps so **Approve never clips** at the narrow extreme. Verified headless/isolated (default, gutter zoom, selection+feedback states via a scratch copy, narrow 540/470 footer wrap, messages header zoom); headed pass skipped per the standing no-interfere rule. The **feed-cards snippet remains the only held item**. DEVLOG is ~730 lines — **rotation is due** but deferred this turn to avoid clashing with the other agent's concurrent appends.

Files: design/ui-snippets/messages-card.html, design/ui-snippets/plans-editor-rail.html, DEVLOG.md

---

### 2026-06-26 07:14:00 — design/TODO.md: moved the Next up queue into A — Quick wins

Relocated all 6 **Next up** items verbatim into the **A — Quick wins** section (now A1–A6: Turns Breakdown Dropdown, Response Settings Popover, Jump-to-End Pill, Library Plans/Documents Editor Rail + Layout, Agent Card Redesign, Context Turn-Scope Select), full content + sub-bullets + build-notes preserved unchanged. **Next up** is now left empty beneath its heading + intro per the "leave empty sections empty" rule. Doc reorganization only — nothing built in the mockup. (DEVLOG ~735 lines — rotation remains due, still deferred this turn per the prior note.)

Files: design/TODO.md, DEVLOG.md

---

### 2026-06-26 07:18:00 — messages-card: fix white gap between rail and content on select

Selected Messages blocks showed a white gap between the teal rail cell and the teal content (Plans/Documents didn't). Cause: `.mrow` carries `gap:7px` (correct for the old floating-strip rail), and the contiguous library rows `.mrow--lib` inherited that horizontal gap — the `.mrail-wrap--lib{ gap:0 }` override only killed the *vertical* row gap, not the horizontal one. Added `.mrow--lib{ gap:0 }` so the rail box butts flush against the content (divided only by the navy `border-right`), matching the `.md-row` model in Plans. Verified headless/isolated: bsh+dif now render as one unbroken teal band, all rows contiguous; the CURRENT/before column keeps its intentional strip gap (fix is scoped to `--lib`).

Files: design/ui-snippets/messages-card.html, DEVLOG.md

---

### 2026-06-26 07:30:00 — design/TODO.md: synced Quick-wins items with the snippet work + added the global divider recolour

Audited the A — Quick wins items tied to the snippet work and made them capture the actual modifications. **A4 (Plans/Documents Editor Rail)** rewritten: the stale "colour strips 6px" line replaced with **strips removed → light-teal selection** (rail cell + content one `--select` band), **dark-teal feedback highlight** (`--rail-section`), **cream hover**, **enlarged title row**, **navy structural dividers** (inline code/badge outlines stay tan), and the **footer Link/Embed-Attach chip moved into the right group leading Revise with the reviewer chip as the only left action** — plus an explicit **"clone-only, do NOT re-port"** note that `box-sizing` + `.flex-1` are Tailwind-absence patches (the mockup already has them, so verify rather than re-add the 30px actions / right-aligned ghost buttons / plan-head rows). **A5 (Agent Card)** got a one-line note that the tiles use the real `#ag-*` sprite glyphs (not placeholder Lucide) and its dividers are already navy. **Added A7 — Messages Card** (the port item was missing entirely): contiguous Library-style rail box, type tag inside each rail box, teal multi-select, agent→status→dir header, navy dividers. **Added A8 — Card Divider Recolour (navy, globally):** the standalone the human asked for — recolour *all* major structural in-card dividers tan `--rule` → navy `--border` across the whole mockup (every card, not just the snippet ones), inline code/badge outlines excluded, by switching usages not redefining `--rule`. Doc capture only — nothing built in the mockup.

Files: design/TODO.md, DEVLOG.md

---

### 2026-06-26 07:41:12 — design/TODO.md: queued Feed Card Selection Parity + Feed Timestamp Alignment in Quick wins

Added two human-requested **A — Quick wins** items for the Team Feed cards (A9, A10). **A9 — Feed Card Selection Parity:** make the Scratch / Log / Inbox cards use the Messages card's selection model in `mockup.html` — header-click whole-card select (light teal), a separate chevron for the dropdown, attach via the chip, remove the `.card-sel` checkbox; **no internal/sub-card selection** (these cards have no sub-fields), with an explicit note to match the live Messages cards and NOT import the per-block rail/sub-select work from the messages-card snippet (which would wrongly re-add sub-selection). **A10 — Feed Timestamp Alignment:** the Scratch + Log card timestamps drift out of right-alignment when expanded — fix so they hold the right edge in both collapsed and expanded states. Doc capture only — nothing built in the mockup. (A concurrent agent was actively rewriting TODO.md + DEVLOG this session; these items landed after A8 on retry. DEVLOG rotation remains deferred per the prior entries to avoid clobbering the concurrent appends.)

Files: design/TODO.md, DEVLOG.md

---

### 2026-06-26 08:04:19 — design/TODO.md: restored Output Export + Jump to Feed Ends; fixed A3's stale cross-ref

Reconciled two issues the concurrent Next-up→Quick-wins relocate had introduced. **Restored two dropped Quick-wins items** the relocate overwrote — **Output Export** (extend per-card Copy into select/cut/export of larger output spans) and **Jump to Feed Ends** (jump-to-start/end per feed) — re-added verbatim as A11/A12, appended rather than re-inserted at the top to avoid renumbering A1–A10 and their A4/A7/A8 cross-refs while the file is under concurrent edit. **Fixed A3's stale reference**: the Jump-to-End Pill pointed at "A2 'Jump to Feed Ends'" but A2 is now Response Settings Popover — repointed it to the restored item **by name** (renumber-proof, since the A1–A8 ports are slated to move to Next up) with a reciprocal name-ref on A12. Nothing beyond these reconciliations changed; verified all three edits present post-write.

Files: design/TODO.md, DEVLOG.md

---

### 2026-06-26 08:10:00 — design/TODO.md: filed the 6 reviewed Inbox notes into Next up (13–18)

After a clarify pass with the human, filed all 6 **Inbox** notes into **Next up** as items 13–18 and cleared the Inbox (left empty per the rule). Each was disambiguated to the real mockup component names and given the resolved specifics: **13 Universal Footer Mic** (move `#compose-mic` to `.footbar` as the first control, neutral styling, wired enable-only-in-editable-field, no focus-steal), **14 Remove "Time" from Link Config End After** (drop the Time toggle from the Turns·Time·Tokens grid → 2 cols, scrub refs), **15 Panel-Size Hover Readout on Drag** (live px readout following the cursor on `.rz-handle` drags, left/top then right/bottom), **16 Compose Attachment-Section Heading** ("Attachments" above `.attach-strip`), **17 Plans/Inbox Tab Badges → Teal** (`.req-badge` on `#plans-badge` + `#inbox-badge` → `--secondary`, matching `.fmt-badge`), **18 Documents/Assets Nav Rows** (per-type file icon replacing the doc icon/thumbnail, remove the Delete trash, keep the Rename pencil un-greyed, line 2 stays path/size, widen the rail for filename room). Entry-6 follow-ups settled with my suggested defaults (keep path/size · keep Rename pencil · per-type lucide icon). Doc capture only — nothing built in the mockup.

Files: design/TODO.md, DEVLOG.md

---

### 2026-06-26 09:01:32 — design/TODO.md + agent-card snippet: audit follow-ups (seam rule, badge-consistency item, comment fix, reminder cleanup)

Acted on the human's review of the 7a–7f-vs-Next-up audit. **TODO.md:** (1) added a **Preserve selection seams** clause to item 8 (Card Divider Recolour) — on selected/feedback rows the navy rail/gutter separator must recolour to the band fill (`--select` / `--rail-section`) so selection highlights aren't sliced by a navy line; the snippet cards already do this, the snippet-less cards (Scratch/Log/Inbox, Compose, Context/Turns, agent cards) need it. (2) Added new **item 19 Agent-Badge Size Consistency** — item 7 bumps the Messages badge to the full `.badge` while the sibling `badgeHTML(a,true)` `.badge-sm` badges (Scratch/Log/Inbox `fcardHTML`/`logCardHTML`/`inboxCardHTML`, History `histCardHTML`, Plans review `.plan-row.r1`/`.fb-top`) stay small; subagent mini-badges + the full-size Context head badge excluded. (3) Added open decision **(e)** to item 5 — subagent badge click action undecided. (4) Removed the redundant per-item "keep DESIGN.md in sync" reminders from items 5–8 + 13–18 (the top "Next up — implementing items" step 3 already mandates it). **agent-card.html:** rewrote the stale top LAYOUT comment to match the real v6 markup — age in the `.hd-meta` top strip; settings/load bars after the header divider; activity band `.band` (run → divider → marquee) pinned at the bottom above `.subs`. Doc/spec only — nothing built in the mockup.

Files: design/TODO.md, design/ui-snippets/agent-card.html, DEVLOG.md

---

### 2026-06-26 09:31:43 — dev/prompts: handoff prompt for parallel "Next up" execution

Wrote `dev/prompts/nextup-parallel-execution.md` — a self-contained brief directing a fresh orchestrator agent to implement all 19 **Next up** items in `design/mockup.html` via a 5-lane parallel plan (git worktrees, not file-splitting). Encodes the collision-aware ordering derived from a footprint audit: Lane A = items 2,5 · B = 6→1 (rename `TURNS`→`TURNS_BD`) · C = 4,18 · D = 14,15,16,17 · E = 7→9→10→11→13→12→3 (serial feed cluster, one generic jump-pill) · then a serial Wave 2 of 8 (skip the `.md-*` dividers item 4 already did) → 19. Includes the merge watch-points (`boot()` ~L4372, Compose footer), item-5 open-decision "don't block" handling, and the mandatory localhost UI-verification + DEVLOG steps. Prompt only — no mockup changes.

Files: dev/prompts/nextup-parallel-execution.md, DEVLOG.md

---

## Archived history

Older entries are rotated into `archive/devlog/` (see the **Rotation** rule in the header) to keep this file small. Archived entries stay full-fidelity and **verbatim** — open the relevant archive only when you need the detail; the digest below is enough for most context.

**Digest — [`DEVLOG-archive-01.md`](archive/devlog/DEVLOG-archive-01.md) (2026-03-26 → 2026-06-13, 21 entries):** the sandbox-era origin story. Workspace + MCP-server setup; the tmux **bridge** built from first draft to a stable 20-method package with a 30-test suite; the **HTTP bridge** (VS Code extension, port 7483); dashboard inception and the **TUI → Electron/React pivot**; the wireframe lineage **v1 → v4** with the palette exploration (Vintage Teal → Warm Dark); the architecture pivot where the Agent **SDK + `stream-json`** replaced xterm/ttyd terminal embedding; the **FastAPI sidecar** (port 7690) + React single-file scaffold; the **E2E pipeline proof**; the design-system / event-feed component specs; and the early file reorganizations (`ui/` → `awl-dashboard/testing/` → `agent-dashboard/design/`).

**Digest — [`DEVLOG-archive-02.md`](archive/devlog/DEVLOG-archive-02.md) (2026-06-13 → 2026-06-21, 117 entries):** the dashboard design push and the start of the `awl-cc-dash` migration. The bulk is the **UI mockup iteration** — the ui-concept lineage from the v5 wireframes through **v9p13** (3-pane layout, the Warm-Dark palette, the Team Graph / Team Feed / Agent panels, and the Documentation/Plan review system with its nav rail + comment popout and the neobrutalist badge/shadow rules), plus the `human-notes-misc.md` "Next up" backlog churn and the `design/DESIGN.md` syncs. It closes with the **migration into `awl-cc-dash`** on 06-21: fresh git history, un-nesting `frontend/`+`sidecar/` to the root, the `tools/ → bridge/ + dev/` split and bridge-import refactor (suite green), repo config (permission allowlist, cc-exports/plans routing), and the run-up to the **sidecar driver seam #1**. (Two 06-13 entries — the v5p5–v5p9 backfills — are `[Reconstructed]`.)

| Archive file | Date range | Entries | Summary |
|---|---|---|---|
| [DEVLOG-archive-01.md](archive/devlog/DEVLOG-archive-01.md) | 2026-03-26 → 2026-06-13 | 21 | Sandbox-era origin: tmux/HTTP bridges, dashboard design lineage v1→v4, the SDK architecture pivot, the FastAPI sidecar + React scaffold, and the E2E pipeline proof. |
| [DEVLOG-archive-02.md](archive/devlog/DEVLOG-archive-02.md) | 2026-06-13 → 2026-06-21 | 117 | Dashboard UI mockup lineage (v5 → v9p13) + the start of the awl-cc-dash migration (git reset, root un-nest, bridge split, repo config). |
