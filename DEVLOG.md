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

> This file is the **recent window**. Older entries (2026-03-26 → 2026-06-26 01:34:58, including all `[Reconstructed]` history) have been rotated into `archive/devlog/` — see **Archived history** below.

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

### 2026-06-26 10:59:38 — Next-up items 1–19 shipped via 5 parallel worktree lanes + serial Wave 2; full UI verification

Implemented all 19 **Next up** items in `design/mockup.html` (+ `design/DESIGN.md` sync) per `dev/prompts/nextup-parallel-execution.md`, using 5 concurrent git-worktree lanes off a clean base then a serial finish. **Lanes (each self-verified headless + committed):** A = items 2 (Response popover `#fmt-menu` rebuilt: STYLE/BEHAVIOR + segmented/toggle groups + Pace, `fitFmtMenu` height-cap) · 5 (square `aspect-ratio:1` agent cards — meta strip, opus-only FAST bolt, settings chips, run strip, marquee, subagent badges); B = 6 (Context turn-scope `<select>`, dual-denominator rescope, width-fit) → 1 (Turns by-tool accordion, demo object renamed `TURNS_BD` to avoid the timeline `const TURNS` clash); C = 4 (Plans/Docs editor rail: plain tan rail, header-over-editor, teal-only selection, footer regroup; `.md-*` dividers→navy + seams done here) · 18 (Documents/Assets nav: per-type file icons, trash removed, pencil kept); D = 14 (End-After Time removed → 2-col) · 15 (cursor-following splitter px readout) · 16 (Compose "Attachments" heading) · 17 (Plans/Inbox tab badges → teal); E = 7 → 9 → 10 → 11 → 13 → 12 → 3 (Messages contiguous-rail multi-select, Scratch/Log/Inbox selection parity + checkbox removed, expanded-timestamp fix, output Export menu, mic relocated to `.footbar`, and ONE generic jump-to-end pill serving both feeds and all scroll regions). **Merge:** all 5 into `feature/agent-console-tab` — `mockup.html` auto-merged region-disjoint (incl. the `boot()` init line + Compose footer); only DESIGN.md collided, resolved keeping every lane's intent. **Wave 2 (serial on merged file):** item 8 — structural card dividers `var(--rule)`→`var(--border)` globally (17 sites; inline code-chip + count/verdict-badge outlines kept tan; `--rule` itself unchanged; `.md-*` + Messages seams left to lanes C/E) + a `.fcard.sel .fcard-body` selection-seam rule; item 19 — agent identity badge to the full `.badge` across `fcardHTML`/`logCardHTML`/`inboxCardHTML`/`histCardHTML` + Plans `.plan-row.r1`/`.fb-top` (subagent/recipient `miniBadges` + comment-popout excepted). **Verification:** full Playwright drive over `http://localhost` — console-clean (only a favicon 404 + the Tailwind-CDN note), every item exercised at wide + narrow (scope rescope, popover, multi-select, export menu, jump pills, drag readout, End-After, nav rows, seam = one unbroken teal band proven by computed style + visually), plus a real **headed** (CDP) parity pass — render identical to headless. JS `node --check` clean throughout. **Item-5 open-decision fallbacks used (need the human):** (a) FAST greys effort/think shown as a *proposal* only; (b) subagent badges identity-only (no working/idle encoding); (c) indeterminate barber-pole Run strip (no real % source); (d) pale agent colours used directly as badge text — low-contrast, flagged; (e) subagent badges styled-clickable but click action unwired. Next-up items left in place in `TODO.md` for the human to remove after review. (Note: DEVLOG is past the ~700-line rotation threshold — rotation into `archive/devlog/` is due.)

Files: design/mockup.html, design/DESIGN.md, DEVLOG.md

---

### 2026-06-26 11:22:38 — DEVLOG rotation: archived 72 entries into DEVLOG-archive-03

Ran the size rotation — the log had reached 808 lines, past the ~700 trigger. Cut the oldest 72 entries (2026-06-21 08:33:22 Sidecar driver seam → 2026-06-26 01:34:58 link-behavior refactor stale-sweep) **verbatim** from the top into a new `archive/devlog/DEVLOG-archive-03.md`, keeping the 31 newest (2026-06-26 02:10:00 onward — the post-refactor snippet/agent-card design era). DEVLOG.md went 808 → 291 lines; entry conservation verified (72 archived + 31 kept = 103, with a byte-identical reconstruction of the moved block). Updated the recent-window pointer (end now 2026-06-26 01:34:58) and added the archive-03 digest + index row to **Archived history**.

Files: DEVLOG.md, archive/devlog/DEVLOG-archive-03.md (new)

---

### 2026-06-26 12:08:16 — Docs+code: corrected stale CLAUDE.md status notes; framed tmux bridge as the primary path, sdk as fallback

Reviewed the flagged CLAUDE.md status notes against the actual repo (5 parallel readers + a direct driver-seam read) and corrected the stale ones: the `bridge` driver is now **"live-verified below the UI"** — run-state, permission round-trips, resume, model/effort — with only the dashboard end-to-end path unproven (was "not yet live-verified"); `tests/` now names its four real suites (was "currently the bridge integration suite"); `export(mode="log")` marked untested (was "lightly tested"). Removed every `archive/mvp` reference from CLAUDE.md (per decision — agents don't need it). Re-languaged the driver framing across CLAUDE.md, `design/DESIGN.md` ("What it physically is"), and the sidecar docstrings/comments (`drivers/__init__.py` incl. `default_driver_name()`, `sdk.py`, `main.py`) so the **tmux bridge reads as the primary path the dashboard is built around** and `sdk` as a backup / limited-use fallback, not the strategic default. Comment/prose only — runtime default unchanged (still falls back to `sdk` so the MVP UI runs without WSL2/tmux).

Files: CLAUDE.md, sidecar/drivers/__init__.py, sidecar/drivers/sdk.py, sidecar/main.py, design/DESIGN.md, DEVLOG.md

---

## Archived history

Older entries are rotated into `archive/devlog/` (see the **Rotation** rule in the header) to keep this file small. Archived entries stay full-fidelity and **verbatim** — open the relevant archive only when you need the detail; the digest below is enough for most context.

**Digest — [`DEVLOG-archive-01.md`](archive/devlog/DEVLOG-archive-01.md) (2026-03-26 → 2026-06-13, 21 entries):** the sandbox-era origin story. Workspace + MCP-server setup; the tmux **bridge** built from first draft to a stable 20-method package with a 30-test suite; the **HTTP bridge** (VS Code extension, port 7483); dashboard inception and the **TUI → Electron/React pivot**; the wireframe lineage **v1 → v4** with the palette exploration (Vintage Teal → Warm Dark); the architecture pivot where the Agent **SDK + `stream-json`** replaced xterm/ttyd terminal embedding; the **FastAPI sidecar** (port 7690) + React single-file scaffold; the **E2E pipeline proof**; the design-system / event-feed component specs; and the early file reorganizations (`ui/` → `awl-dashboard/testing/` → `agent-dashboard/design/`).

**Digest — [`DEVLOG-archive-02.md`](archive/devlog/DEVLOG-archive-02.md) (2026-06-13 → 2026-06-21, 117 entries):** the dashboard design push and the start of the `awl-cc-dash` migration. The bulk is the **UI mockup iteration** — the ui-concept lineage from the v5 wireframes through **v9p13** (3-pane layout, the Warm-Dark palette, the Team Graph / Team Feed / Agent panels, and the Documentation/Plan review system with its nav rail + comment popout and the neobrutalist badge/shadow rules), plus the `human-notes-misc.md` "Next up" backlog churn and the `design/DESIGN.md` syncs. It closes with the **migration into `awl-cc-dash`** on 06-21: fresh git history, un-nesting `frontend/`+`sidecar/` to the root, the `tools/ → bridge/ + dev/` split and bridge-import refactor (suite green), repo config (permission allowlist, cc-exports/plans routing), and the run-up to the **sidecar driver seam #1**. (Two 06-13 entries — the v5p5–v5p9 backfills — are `[Reconstructed]`.)

**Digest — [`DEVLOG-archive-03.md`](archive/devlog/DEVLOG-archive-03.md) (2026-06-21 → 2026-06-26, 72 entries):** the working-MVP backend hardening and the big design build-out. Backend: the **sidecar driver seam** (pluggable `sdk`/`bridge` drivers + `serialize.py`) with the frontend render-path fix → live E2E; the **`archive/mvp` parity sync**; and the **bridge backend** brought to trustworthy run-state — screen-state detection, startup gates, context/turns, the permission round-trip, restart survival, and live `/model`+`/effort` controls — plus the **WT-tab opt-in** (no focus theft). Design: the **`design/` single-source refactor** (`tokens.css` as sole source of truth; `ui-concept-v9p14.html` → `mockup.html`, `design-tools.js` → `mockup-toolkit.js`; `DESIGN.md` de-versioned, forward material → `TODO.md`) and the mockup iteration **v9p14 → v1.2** (Library panel rework, Agent **Console** tab, mode toggles, behavior-wiring audit), closing with the **link-behavior refactor P0→P4** (Ultraplan removal, the inserted-block primitive, feed select-to-act, the **typed Inbox + Error type**, **Compose→Editor** with templates-as-blocks + attachment strip, the **Embed/Attach** capstone + citations + Review chip) and its stale-sweep. Housekeeping: the markdown **unwrap pass** and the DEVLOG **append-only + single-timeline** conversion.

| Archive file | Date range | Entries | Summary |
|---|---|---|---|
| [DEVLOG-archive-01.md](archive/devlog/DEVLOG-archive-01.md) | 2026-03-26 → 2026-06-13 | 21 | Sandbox-era origin: tmux/HTTP bridges, dashboard design lineage v1→v4, the SDK architecture pivot, the FastAPI sidecar + React scaffold, and the E2E pipeline proof. |
| [DEVLOG-archive-02.md](archive/devlog/DEVLOG-archive-02.md) | 2026-06-13 → 2026-06-21 | 117 | Dashboard UI mockup lineage (v5 → v9p13) + the start of the awl-cc-dash migration (git reset, root un-nest, bridge split, repo config). |
| [DEVLOG-archive-03.md](archive/devlog/DEVLOG-archive-03.md) | 2026-06-21 → 2026-06-26 | 72 | Working-MVP backend hardening (sidecar driver seam; bridge run-state / permissions / restart; WT-tab opt-in) + the design build-out (`tokens.css` single-source refactor, mockup v9p14 → v1.2, the Console tab, and the link-behavior refactor P0→P4: typed Inbox, Editor, Embed/Attach). |
