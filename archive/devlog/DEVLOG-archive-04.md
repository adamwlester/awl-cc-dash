# DEVLOG Archive 04 — 2026-06-26 → 2026-06-30

> Archived, immutable DEVLOG history (oldest -> newest). Rotated out of the root `DEVLOG.md` on 2026-07-01 to keep the active log small (see the **Rotation** rule in the DEVLOG header and the **Archived history** index there). Entries are **verbatim** -- original `### ...` headings and `Files:` lines preserved. Never edit archived entries; record new history in `DEVLOG.md`.
>
> Span: the design-snippet iteration (agent-card v1→v6, messages-card rail/blocks) and the Next-up batch shipping (A–L, R1–R11) into mockup.html; the Inbox 5-section severity ramp (Warning added); the bridge backend Part-1 + per-agent launch config + identity store + the three-pane UI foundation & Settings step-into; the icon-fill agent-card treatment (scrim → light tint → glyph polarity); the OD decision tracker (OD-01…OD-24 finalized); the design-system component refactor (data-comp/data-status tags, gallery, behavior.js extraction → the 6-file system); and the backend foundation Tier-1 builds (OD-23 storage, OD-03 identity) — from the 2026-06-26 02:10:00 entry through 2026-06-30 15:30:00. 112 entries.

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

### 2026-06-26 13:34:41 — Queued the item-5 + review-batch change list into TODO.md "Next up"

Filed a 12-section (A–L) cumulative change list into the **Next up** queue in `design/TODO.md` — planning only, nothing built yet. Folds the held decisions (square agent-card item #5 a–e + demo-data relocation off green agents, the DESIGN.md staleness patches at L158/L160/L62/L141, the dead `.assetnav-thumb` removal) together with this session's 7 new review items — jump-pills on the real scrollers (#1), the flush-square expand hit-target (#2, Messages now confirmed included), Plans/Docs editor-rail dividers (#3), the Team-Feed action-strip rework + select-all fix (#4), the link-icon dropdown replacing Embed/Attach chips (#5), the History→feed-model conversion (#6), the subagent-badge footer-framing polish (#7) — plus a mic-button resize to match the Settings gear. Grounded each anchor against `mockup.html` (`.sbadge`/`.node-subs`, `.fcard-chevbtn`, `.mic-btn` 30×30 vs `.topbar-gear` 27×24, `JUMP_SELECTOR`). Kept the code-block format per the human's request.

Files: design/TODO.md, DEVLOG.md

---

### 2026-06-26 13:41:59 — Revised Next-up item L: mic resize → per-editor ghost mic

Replaced queued item L in `design/TODO.md` "Next up". Instead of resizing the universal footer mic, the dictation mic now moves OUT of `.footbar` (remove `#footer-mic`) into a per-section ghost button in each Editor header — Compose, Plans, Documents — styled like the inline `.ghost-ic` buttons (22×20) and placed right after the "Editor" label; default ghost color toggling to red (`var(--danger)`, matching `.mic-btn.rec`) when recording; enabled/disabled state bound to each section's own field (Compose `#compose-field`, each Plan/Document editor) rather than one universal control. Grounded against `editHeadHTML()` (covers Plans + Documents), the Compose header (~L2991), `toggleMic()`, and `.ghost-ic`/`.mic-btn`; flagged that the Compose paperclip `#compose-attach` reuses `.mic-btn` styling but must stay. Queue edit only — no mockup changes.

Files: design/TODO.md, DEVLOG.md

### 2026-06-26 14:05:21 — Regenerated the UI-behavior question list as v5 (fresh code+design deep review)

Reworked the pre-backend UI-behavior open-questions doc via a 4-phase background workflow (11 agents: 5 parallel subsystem readers → synthesize → 4 adversarial verifiers → reconcile), re-grounded in a fresh read of the live `frontend/` + `sidecar/` + `bridge/` and the rewritten `design/TODO.md` "Next up" (now the A–L cumulative change list, superseding v4's "items 1–19"). Output `ui-behavior-questions-2026-06-26-v5.md`: 33 questions / 9 sections, each with a pre-filled `Assumed:` answer + ▶/◆/✚ confidence tag. Main shifts vs v4: the Backend-reality check is re-centered on **bridge-as-primary** (capture-pane + JSONL, ~1.0s poll, 4-value screen-state, binary permission/no always-allow, verified model/effort/resume, no-op set_fast/thinking/mode, cost=0) with sdk as the backup/fallback; **Q9 (subagents)** split into 3 sub-contracts with confidence downgraded (A2's pending/active/idle + s1/s2 ID collides with subagent opacity — coarse active/done + a dashboard-minted ID is the ceiling); **Q10 FAST** adds the Opus-only gate and flags it non-functional on every driver; **Q1** reframed as normalizing 3 disjoint status enums; **Q4** sharpened (bridge reports `total_turns:0` on the primary path; turns only in `/context`); **Q26/Q30** updated for the H link-icon dropdown + the I History feed-model + Retry; the mic exclusion corrected from "universal footer" to per-editor (L). Verify pass: 16 issues (0 blockers), 15 reconciled. Spot-checked the load-bearing code claims (screen-state enum, `set_fast` no-op, 5-value status enum, 409-on-busy) directly against source — all accurate. Net-new file; v4 left intact as the superseded baseline.

Files: .scratch/ui-behavior-questions-2026-06-26-v5.md, DEVLOG.md

---

### 2026-06-26 14:51:07 — Next-up A–L batch shipped in mockup.html (workflow: spec→serial-impl→check) + orchestrator fixes + DESIGN sync

Implemented the full A–L "Next up" change list in `design/mockup.html` via a background **workflow** (6 parallel read-only edit-spec agents → 6 serial implementers editing the one shared file in dependency order → 4 parallel static verifiers; 16 agents). **Landed:** A square agent-card tweaks (dropped the FAST override-greying so effort/think always show real values; FAST stays Opus-gated) + rectangular subagent `.sbadge` id-badges (leading run-state dot pending/active/idle reusing `--warning`/`--success`/`--muted`, navy `s1`/`s2` ids not counts, no offset shadow) with demo badges relocated off green agents onto amber/magenta/gold; **B** badge footer-band framing; **C** Messages `.mrail-wrap` inner frame dissolved (fills card surface, `.fcard-body` padding kept); **D** jump pills rewired to real scrollers (`.doc-view`→`.md`, compose contenteditable via outer overlay wrapper); **E** flush-square `.fcard-chevbtn`; **F** Plans/Docs editor-rail navy dividers; **G** feed action strip (standalone Copy removed, select-all generalized to all tabs as `feedSelectAll`/`#feed-selall-btn`, per-tab Summarize/Stop); **H** Embed/Attach chip trio → link-icon `.ea-dd` dropdown modeled on Output Export (selection-gated menu: "Embed in prompt"/"Attach as file"); **I** History adopts the feed-card model (no checkbox→header-click select, Edit moved to card header, footer select-all·Export|link-dd·Retry·Stop); **K** dead `.assetnav-thumb` CSS removed; **L** dictation mic moved out of `.footbar` (`#footer-mic` gone) into per-Editor `.ghost-ic` mics (Compose + `editHeadHTML` Plans/Docs) bound to each field via `data-micfield`, red while recording. **Orchestrator fixes after the workflow:** (1) the flush chevron rendered 16×44 — flexbox drops `aspect-ratio:1`, so set explicit `width:44px` (= the constant 44px head height) → true square; (2) **real regression** — `histCardHTML` nested a `<button>` (Edit) inside the `.fcard-exp` select `<button>`; restructured so Edit/time/chevron are siblings (valid HTML, Edit still after attach-tags/before timestamp); (3) JUMP D1 gap — added `.fcard.open .fcard-body{ max-height:340px; overflow-y:auto }` + attach a jump pill on expand in `toggleFcard`; (4) removed dead code the batch orphaned (`.ea-grp/.ea-mode/.ea-act` CSS, `feedAct`, `toggleCardSel`, a stale histCardHTML comment). **Verified** by driving the rendered UI over `http://localhost` (Playwright MCP): console-clean (only Tailwind-CDN note + favicon 404), both inline scripts pass `node --check`, and structural+behavioral assertions confirmed every item — History header non-nested, Messages framing edge-to-edge, badges rectangular/navy/dotted on non-green agents, mic recording red (a transition-timing measurement artifact, not a bug), link dropdown opens + gates correctly (Attach enabled on whole-card select), select-all 8↔0, History select/edit/expand split, per-tab strips, chevron 44×44; narrow (1150) holds with no doc/panel scroll (densest History card clips 22px gracefully via card `overflow:hidden`). **DESIGN.md synced** (20 edits) to match: subagent badges, Messages framing/footer, History feed-model, link-icon dropdown (replacing the two-mode chip prose), per-editor mics (footer mic removed), editor-rail dividers, jump-pill feed-body capping, plus the review-flagged stale spots (nav rows = per-type file icons not thumbnails + no trash; History no checkbox; Copy folded into Output Export). Next-up items left in place in `TODO.md` for the human to remove after review.

Files: design/mockup.html, design/DESIGN.md, DEVLOG.md

---

### 2026-06-26 15:48:04 — Queued follow-up review+change batch (R1–R4 + 9 requests) into TODO.md "Next up"

Added a follow-up implementation batch to `design/TODO.md` **Next up** (the human had already cleared the completed A–L block, so the section was empty). The batch captures the post-build audit of the A–L / 9a work plus new requests gathered this session. **PART 1 — review fixes R1–R4:** remove orphaned `.card-sel` CSS (dead since History dropped the checkbox); note item F's re-added navy rail-row dividers on the DESIGN.md doc-editor line; optional Attachments-heading (#16) note; and actually run the headed parity pass next round (it was reasoned away last time). **PART 2 — 9 change requests:** subagent badges → status-colour fill + bold inverse text, no dot (supersedes A2), no-wrap expandable overflow, and click-isolation from the parent card; Messages content filling the card surface (finishes C — drop the residual Messages-only `.fcard-body` padding); History header divider to match Scratch/Log; link-icon dropdown gated-when-empty + a chevron; Output Export trimmed to the 3 "selected" actions + gated; "Export selected → file" routed to Library → Documents + the Add-document (Paste) workflow; and that paste workflow creating an editable-named row with inline rename active. Spec/queue only — nothing implemented yet.

Files: design/TODO.md, DEVLOG.md

---

### 2026-06-26 16:30:00 — UI-behavior v5: inserted per-question TL;DR lines (pure-insertion pass)

Added a one-line `_**TL;DR — … Presumed: …**_` summary to the end of each of the 33 questions in `dev/notes/agent-qa/ui-behavior-questions-2026-06-26-v5.md`, immediately after each question's `Assumed:` paragraph (after Q30's Stop sub-note; before the `---` divider for the eight section-final questions). Pure insertion — no existing heading, option, Assumed line, divider, or blank line was altered. Verified 33 TL;DR lines present and each placed before its next-question heading / section divider.

Files: dev/notes/agent-qa/ui-behavior-questions-2026-06-26-v5.md, DEVLOG.md

---

### 2026-06-26 16:31:00 — Follow-up batch (R1 + items 1–9) shipped in mockup.html (+ DESIGN.md sync; headed-verified + adversarial review)

Implemented the full FOLLOW-UP BATCH from `design/TODO.md` "Next up" in `design/mockup.html`. **R1:** removed the dead `.card-sel` CSS. **Subagent badges (1–3):** `.sbadge` dropped the leading `.sdot` and is now FILLED with its run-state status colour + bold white id (new `.sb-active`/`.sb-pending`/`.sb-idle` reusing the `.nb-*` tokens; `+N` stays neutral); `.sbadges` is `flex-wrap:nowrap` and the `+N` opens a `.subs-pop` popover (`toggleSubsPop`, added to `closeAllPopups`) rather than growing the square card; every badge + the `+N` trigger `stopPropagation` so a badge click no longer selects the parent `.node`. **Feed/Messages (4–5):** `.msgcard .fcard-body{padding:0}` so the Messages rail fills all four edges (Scratch/Log/Inbox keep their inset); scoped the selection-seam recolor to `.msgcard.sel` so History/Scratch/Log/Inbox keep their navy header divider when selected (fixes the missing History divider; Messages still reads as one teal band). **Dropdowns (6–7):** chevron added to all three `ea-dd` link triggers (feed/hist/`embedAttachHTML`) + a `.exp-btn:disabled` style; both Output Export menus trimmed to the 3 selection actions (whole-feed/history dropped); new `expGate()` disables `#feed-exp`/`#hist-exp` until a whole card is selected, wired through `eaUpdate`/`switchTab`/boot. **Export→Documents (8–9):** `feedExport`/`histExport` `file-sel` now route to a new `addDocPaste()` that builds a real Documents nav-row + editor pane (wired like `renderDocs`) with the selection content and opens inline rename immediately; the Add-menu Paste action uses the same; `cardText` now returns a Messages card's full content (not just "Turn N"). **DESIGN.md synced** (R2 navy rail-row dividers, R3 Compose "Attachments" heading, + subagent/Messages/History/dropdown/Paste intent). **Verification:** drove the rendered UI in a **headed** browser at wide (1680) + narrow (1120) — 0 JS errors; every item exercised (status-fill badges, `+N` popover unclipped + click-isolated, Messages edge-fill, History navy divider, gated+chevroned link-dd, 3-item gated Export, Export→Documents→Paste→rename chain). A 5-agent adversarial review workflow then caught one real bug — `statusJump('pending')` selected an Inbox card without re-gating the feed Export/link-dd → fixed with a trailing `eaUpdate('feed')` — plus cleanups (removed dead `selectHistCard`/`selectMsgCard`, simplified now-dead `allCards`/`wantSel` branches, refreshed two stale comments, and made a doc rename also update the pane header path); all re-verified. Next-up items left in place in `TODO.md` for the human to remove after review.

Files: design/mockup.html, design/DESIGN.md, DEVLOG.md

---

### 2026-06-26 17:15:00 — Queued the round-10 cumulative change batch (11 items) into TODO.md "Next up"

Filed the next reviewed change batch into `design/TODO.md` **Next up** (section was empty — prior follow-up batch already cleared by the human). Eleven items, settled with the human over this session: (1) **Error as a 4th run state** — new `.nb-error` solid-danger/inverse badge, one demo error agent, Error-badge → Inbox via a `statusJump('error')` branch, plus restyling the existing Message-card `.db-error` badge from soft-red/red-text to solid-fill/inverse to match the other status badges, with DESIGN.md docs; (2) **dividers stay navy on hover/select** — stop recolouring the header/body, adjacent-row, and editor-gutter divider lines to the fill (fills still show behind them); (3) **subagent footer → accordion drawer** (chevron toggle, first row always visible, vertically centred) replacing the +N popover; (4) **editor gutter extends to the bottom** (empty track only, no fabricated numbers); (5) **reviewer-chip dropdown fix** (whitelist `.rev-chip` in the global click-closer); (6–10) **share/export consolidation** — merge the Embed/Attach link dropdown into one Output Export menu (Cut removed, headings "Export" / "Add to prompt"), Embed enabled whenever anything is selected, Attach-as-file creates a real Library→Documents file + prompt link + reveal, remove the standalone link dropdown from Feed/History, and repoint Plans/Documents at the merged dropdown (left-aligned, before the reviewer chip); (11) **Delete agent button** to the right of Retire — new solid-red-fill/inverse style, irreversible wipe of config + transcripts (+ roster/graph/links), behind a confirm step. Spec/queue only — nothing implemented yet.

Files: design/TODO.md, DEVLOG.md

---

### 2026-06-26 19:09:07 — Sidecar default driver flipped sdk → bridge

Flipped the no-driver-named default in `default_driver_name()` from `sdk` to `bridge`, per policy that bridge is the primary path and sdk is a reserved explicit-only engine. This is a real behavior change for the shipped app: `start-dashboard.bat` sets no `AWL_DRIVER` and the frontend sends no `driver` field, so unnamed sessions (and `/health`/session listing's reported driver) now resolve to `bridge` instead of `sdk`. `sdk` stays selectable via `AWL_DRIVER=sdk` or the per-session `driver` field; the *unknown*-driver error path still falls back to `sdk` (out of scope). Updated the now-stale "sdk is the no-driver-named fallback" docstrings in `drivers/__init__.py`, `drivers/sdk.py`, and `main.py`, and added 4 hermetic default-selection tests. Ran `pytest tests/ -m "not integration and not slow"` → **36 passed, 33 deselected** (live tmux/WSL2 suites). Flag: project `CLAUDE.md` still calls sdk the "no-driver-named fallback" — now lags the code; left unedited pending the human's call.

Files: sidecar/drivers/__init__.py, sidecar/drivers/sdk.py, sidecar/main.py, tests/test_sidecar_unit.py, DEVLOG.md

---

### 2026-06-26 19:14:43 — Doc sync: bridge-as-default reflected across CLAUDE.md, DESIGN.md, agent-qa note

Followed the driver-default flip by updating the prose docs that still called `sdk` the no-driver-named fallback (the prior entry had flagged CLAUDE.md). The CLAUDE.md `sidecar/` row and `design/DESIGN.md` "What it physically is" now state that `bridge` is the default when no driver is named and `sdk` is an explicit-only backup reserved for specific non-interactive tasks; the current `dev/notes/agent-qa/ui-behavior-questions-2026-06-26-v5.md` QA note's selection-order claims (lines 8, 31) were corrected from `→ "sdk"` to `→ "bridge"`. Surgical edits only — the sdk = backup/limited-use framing is preserved. `archive/*` and prior DEVLOG entries left verbatim (historical / append-only).

Files: CLAUDE.md, design/DESIGN.md, dev/notes/agent-qa/ui-behavior-questions-2026-06-26-v5.md, DEVLOG.md

---

### 2026-06-26 19:28:23 — Doc cleanup: SDK framing fully task-scoped (no whole-system fallback) in CLAUDE.md + DESIGN.md

Tightened the SDK-driver framing to match policy: the SDK is sanctioned only for task-scoped non-interactive jobs (e.g. the Revise / Summarize utility-LLM passes), never as a whole-system fallback. In CLAUDE.md's `sidecar/` row, dropped the "no WSL2/tmux available" example (that's the ruled-out run-everything-on-SDK scenario) and the "backup" descriptor, leaving "limited-use engine reserved for specific non-interactive tasks". In `design/DESIGN.md` "What it physically is", replaced the bridge/SDK sentence with the policy wording ("…not a whole-system fallback; …reserved for specific non-interactive tasks that need no real terminal… Agents themselves always run on the bridge."). Swept both files for `fallback`/`backup`/`limited-use`/`no WSL2` leaks — remaining hits are all intended: the sanctioned invalid-driver `falls back to sdk`, DESIGN's "not a whole-system fallback" negation, the UI barber-pole "honest fallback", and "delimited" substrings. Bridge stays stated as the default / the path agents run on. Docs only; edited on disk, not committed.

Files: CLAUDE.md, design/DESIGN.md, DEVLOG.md

---

### 2026-06-26 19:30:15 — Round-10 change batch (11 items) shipped in mockup.html (+ DESIGN.md sync; browser-verified)

Implemented all 11 "Next up" items from `design/TODO.md` in `design/mockup.html`. **(1) Error = 4th run state:** new `.nb-error` solid-danger/inverse badge + `.run-error` strip; the demo `auditor-01-drew` graph card now reads **Error** (red run strip + "run failed — see Inbox" marquee) and its badge routes to the Inbox via a new `statusJump('error')` branch (mirrors `'pending'`); the Messages/History `.db-error` badge restyled soft-red → **solid danger + white** to match. **(2) Dividers stay navy:** removed every `border-*-color:var(--select|--rail-section)` seam-blend — the Messages header/body divider, the divider between stacked selected rows, and the editor gutter↔text + per-row dividers all **stay navy** on hover/select (the fill shows behind). **(3) Subagent accordion:** the `+N` popover is gone — the strip is now an in-flow **accordion drawer** (`.subs-acc`, chevron toggle, first row centred, `.has-more` set by JS wrap-measure on a `graph-grid` ResizeObserver; `.node.subs-open` drops the square so the card grows downward); the demo card bumped 6→8 subagents so it wraps + shows the drawer at the default width. **(4) Editor gutter to bottom:** the height cap moved from `.md` (max-height) to the editor **row** (`.plan-rev{max-height:346px}`) so `.md` flex-fills and `.md-fill` runs the rail to the bottom even when the Outline/Feedback nav is taller than the plan text (browser-confirmed: gap 0, card bounded ~509px; Documents already filled). **(5) Reviewer-chip dropdown:** added `&& !e.target.closest('.rev-chip')` to the global click-closer — its `.src-pop`-classed menu no longer instant-closes. **(6-10) Export consolidation:** the separate Output Export + Embed/Attach (`.ea-dd`) dropdowns merged into ONE `expMenuHTML()` control (headings **Export**: Copy · Export→file; **Add to prompt**: Embed · Attach — **Cut removed**), reused on Feed/History (mounted via `[data-expmount]`) + Plans/Documents/Assets footers; `eaUpdate()` now gates all four items per selection (**Embed = any selection** incl. whole cards [item 7, `embedWholeCards`], Attach = whole-only, Copy/File = whole feed/hist cards or editor selection, Assets attach-only); **Attach now saves a real Documents doc** (factored `createDoc`) + chips it + switches to Compose and **flashes** the chip (item 8); the standalone `.ea-dd` was deleted from Feed/History (item 9); Plans footer is now `[Export][reviewer chip]…[Revise/Reject/Approve]` and Documents/Assets `[Export]…[Remove]`, both left-aligned (item 10). **(11) Delete agent:** new `.btn-danger-solid` (solid-red/white) **Delete agent** button right of Retire, behind a shared `footConfirm` inline **"can't be undone"** danger confirm; on confirm it removes the node from the graph. **DESIGN.md synced** (Error 4th state + run strip; navy-divider rule; subagent accordion; editor fill-to-bottom; the merged Export control section + every footer reference; Delete in the Details footer + danger accent). **Verification:** drove the rendered UI (Playwright MCP, headed) at **wide 1680 + narrow 1100** — 0 console errors (only the pre-existing Tailwind-CDN warning); measured/exercised every item (status-fill badges, navy dividers via computed styles, accordion wrap→open→grow→close, plan gutter gap=0, reviewer chip stays open, 4-item gated menu across feed/hist/plans/docs/assets, whole-card embed + attach→doc+chip+flash, no footer overflow at narrow, Delete confirm + node removal). Next-up items left in place in `TODO.md` for the human to remove after review.

Files: design/mockup.html, design/DESIGN.md, DEVLOG.md

---

### 2026-06-26 19:48:20 — Live-verified bridge default flip through the UI; fixed EventRenderer crash on bridge user-prompt events

Verified the `sdk → bridge` default flip on the real live path, not just unit tests. Started the sidecar the normal way (`python main.py`, **no `AWL_DRIVER`**, no per-session `driver`); served the real renderer standalone via Vite (`:5199`, talks pure HTTP to the sidecar, `window.awl` falls back) and drove it with Playwright headless to avoid stealing focus. Created an agent via the UI "+ New": `/health` **and** the new session both reported **`driver: "bridge"`**, a real Claude Code TUI spawned in tmux/WSL2 (`awl-e909c374`, `attached: no` — no tab popped), and the agent ran genuine turns (replied `READY`, then `DONE`; transcript-confirmed). Deleting via the UI killed the tmux session cleanly. **Bug found + fixed:** the bridge driver replays a user's own prompt straight from the transcript as `content: "<string>"` (not a block list), but `EventRenderer` called `content.map()` unconditionally → `TypeError: content.map is not a function` → with no error boundary the **entire UI blanked** every time an agent ran on the now-default driver. Added a `toBlocks()` normalizer (string → single text block) used by both the Assistant and User message branches; re-verified the same history renders the feed (`READY`/`DONE`) with zero console errors at narrow (760) and wide (1680). The flip itself was already correct — this was a pre-existing render bug the bridge path exposed. Left as-is (separate UX call for the user): user prompts are still not echoed in the feed — the User branch ignores text blocks, matching prior SDK behavior — so only the crash was fixed, no new UI added.

Files: frontend/src/renderer/App.tsx, DEVLOG.md

---

### 2026-06-26 20:01:43 — CLAUDE.md: bridge UI end-to-end path now marked proven (was "unproven")

Updated the `sidecar/` row in `CLAUDE.md` to reflect the live-verification above. The row had claimed the bridge was "live-verified below the UI … only the end-to-end path *through the dashboard UI* is still unproven" — which the 19:48:20 pass disproved. Reworded that clause to **"now proven end-to-end through the dashboard UI"** (create with no driver named → `bridge` → real tmux session, no tab → live turns render in the feed), noting the verifying pass also caught & fixed the `EventRenderer` string-content crash. No other major doc needed changes: `DESIGN.md` carries design intent, not run-state, and made no such "unproven" claim.

Files: CLAUDE.md, DEVLOG.md

---

### 2026-06-26 21:09:52 — Frontend renders correctly on the bridge driver: 3 SDK-shape fixes (App.tsx), live-verified

Closed out the remaining SDK-shape assumptions in `frontend/src/renderer/App.tsx` so a normally-launched dashboard runs bridge agents cleanly. (1) **User prompts now echo** — the `UserMessage` branch only rendered `tool_result` blocks, silently dropping the bridge's string-content prompt replay; added a `UserPromptBlock` (pink left-accent + "You" label) for `text` blocks. (2) **No blank fresh-session feed** — non-rendering `status_change` events inflated `events.length`, suppressing the "Session ready" hint; gated it on a new `hasRenderable` predicate (assistant/user/result/init/rate_limit) instead of raw length. (3) **Empty tool output no longer dropped** — loosened the `&& block.content` guard to render `tool_result`s with falsy content (`?? ''`). Live-verified through the real UI (headless Playwright) against a sidecar started normally (no `AWL_DRIVER`, `/health` → `bridge`): created an agent with no driver named → came up on `bridge` (real tmux, no tab); prompts echo beside responses; a clean end-to-end round-trip (UI send → `user` string + `assistant` PONG render, status returns to idle); narrow (720) and wide (1680) both render correctly. An adversarial 3-lens audit (workflow) cross-confirmed the fix set. **Reported, not changed** (architectural / out-of-lane): bridge `total_cost_usd` is always 0 → SessionList shows `$0.000` (bridge transcript exposes no USD cost — needs a design call: hide / "n/a" / show context-%); and `bridge/transcript.py:find_transcript` only does `cwd.replace("/", "-")` while Claude Code also maps `.`→`-`, so a cwd containing a dot (e.g. `.scratch`) mis-hashes the project dir and finds no transcript (one-line bridge-layer fix, surfaced during testing).

Files: frontend/src/renderer/App.tsx, DEVLOG.md

---

### 2026-06-27 04:45:00 — Inbox: 5-section severity ramp (added Warning), heading-label colours, count-badge fix; +token audit

Reworked the Team Feed → Inbox section headings. **Token audit first** (subagent): grepped all 60 `tokens.css` custom properties against `mockup.html`; only the 6 orphaned `--req-*` (+`-soft`) tokens were dead — moved them verbatim under a new `UNUSED` banner at the foot of the `:root` block (move-only, count unchanged). **Then the Inbox change:** added a 5th section type **Warning** and reordered sections most→least urgent — **Error · Warning · Permission · Plan · Decision**. The section **heading label + its matching count badge** now carry an escalating ramp via two new tokens — `--inbox-permission:#7a4e24` (blackish-orange) and `--inbox-warning:#c06a1a` (burnt orange) — with **Error** on `--danger` (red) and **Plan/Decision** on neutral `--muted`; the count badge was switched off the barely-visible `--muted-2`/`--rule` to match its label. Error stays the single alarm (only section with a danger left-edge; Warning + the rest are heading-coloured only). Added a sample `warning`-type REQ (rowan, "context window 92%") + a `warning` render branch (Acknowledge · Reply) so the section actually renders; updated the stale "4 open Inbox requests" digest to 5. **Live-verified headless** (Playwright over http://localhost): computed label colours exact on all 5 sections, tab badge → 5, Warning card expands with correct body + actions (no Error styling), narrow (1100) + wide (2200) extremes both clean, console 0 errors; final headed-size confirm identical. `design/DESIGN.md` synced (Inbox tab section list + controls table + the "typed sections" paragraph — now an escalating heading ramp).

Files: design/tokens.css, design/mockup.html, design/DESIGN.md, DEVLOG.md

---

### 2026-06-27 05:10:00 — bridge: robust transcript project-dir resolution (full non-alphanumeric encoding) + unit tests

Fixed `find_transcript` mis-deriving the `~/.claude/projects/` subdir for cwds containing non-slash punctuation. Claude Code encodes a cwd into its project-dir name by replacing **every** non-alphanumeric char with `-` (so `.scratch` → `--scratch`, dots/underscores/spaces too), but the old code only swapped `/`. New `_encode_cwd()` does the full `[^a-zA-Z0-9]→-` substitution; new `_resolve_project_dir()` confirms the encoded name against the real `ls` listing (fast `test -d` path first, then a dash-collapsed fallback match) and returns `None` cleanly when nothing matches. Added 8 hermetic unit tests (`TestEncodeCwd`, `TestResolveProjectDir` with a `_FakeBridge` stub) — suite green (37 passed). Also dropped the per-session `$total_cost_usd` line from the frontend SessionList row (now shows just the model). Logged here to satisfy the every-change rule; committed alongside the bridge fix.

Files: bridge/transcript.py, tests/test_bridge_unit.py, frontend/src/renderer/App.tsx, DEVLOG.md

---

### 2026-06-27 06:25:00 — Inbox ramp colours finalized: reuse --warning/--danger, one dedicated Permission token

Revised the Inbox heading ramp values from the earlier 04:45 entry's placeholders to reuse existing semantic tokens (per user direction — no new signal colours minted). **Audited `var(--warning)` first**: 39 uses, load-bearing (Pending status badges `.sb-pending`/`.nb-pending` with white text, every Context/Turns health-bar mid-zone via `ctxColor()`, the `.v-revise` verdict colour, the set-warn banner border, the "N pending" legend dot) — so it can't be darkened for text without muddying all of those. Resolution: **Error reuses `--danger`, Warning reuses `--warning`** (the existing amber #d98a2b — user accepted its softer-as-text read over minting a near-duplicate), and **only Permission keeps a dedicated token** — retargeted `--inbox-permission` #7a4e24 → **#a9710f** (the old `--req-decision` value, the user's "blackish-orange") and **deleted the now-unused `--inbox-warning`**. Final ramp: Error `--danger` red → Warning `--warning` amber → Permission `--inbox-permission` ochre → Plan/Decision neutral `--muted`; each section's colour drives its label + the trailing count badge's outline + counter text. **Live-verified headless** (Playwright, http://localhost): computed colours exact on all 5 sections (#d23b6a / #d98a2b / #a9710f / #5b5f86), Warning vs Permission visibly distinct (amber brighter than ochre), narrow (1100) clean. `DESIGN.md` updated (removed the stale "`--inbox-warning` distinct from `--warning`" note; now documents the reuse).

Files: design/tokens.css, design/mockup.html, design/DESIGN.md, DEVLOG.md

---

### 2026-06-27 06:55:00 — TODO.md: filed 6 Inbox-bucket notes into a fresh Next up (incl. the gutter "item 4" finding)

Triaged the `design/TODO.md` Inbox bucket into the now-cleared **Next up** queue (human emptied it first). Verified each against the live mockup before filing (per the doc's "verify first" rule): the jump-pill dead-selector bug I'd flagged earlier is **already fixed** (`JUMP_SELECTOR` uses the real `.md` scroller, ~4293) so it was not re-added; the Warning section + colour ramp are **already built**, so its note was trimmed to the remaining gap. Filed **6 items**: (1) Warning card header badge ("Max turns"/limit) mirroring the Error "Connection" badge — generalise the `type==='error'`-only subtype render (~5034) + add a `--warning`/`--warning-soft` variant of `.inbox-subtype` (~1159) + a pending limit-crossed example; with the inbox token mapping (label+count badge: Error `--danger` / Warning `--warning` / Permission `--inbox-permission` / Plan·Decision `--muted`) integrated. (2) remove the navy divider before Reply in `inboxReplyHTML()` (~5012). (3) **gutter "item 4" finding** — the `.md-fill` filler rail already extends but is invisible (tan-on-cream); raise contrast + seed a short doc. (4) clamp editor selection so it doesn't highlight past the last text line (~1655). (5) footer popover menus (`.rev-pop`/`.ea-dd`/`.vpop`) as a raised, unclipped overlay. (6) rename the Export menu heading → "Copy & Export" (`expMenuHTML`, ~3735). **Held & flagged** the 7th note ("remove Copy ghost buttons from History header") — no Copy ghost button exists in `histCardHTML` (only Edit), so it's parked in the Inbox bucket pending clarification. No mockup/DESIGN.md change — backlog triage only.

Files: design/TODO.md, DEVLOG.md

---

### 2026-06-27 07:05:00 — Moved archive/mvp → archive/_human-only/mvp (deny-read)

Relocated the retired MVP snapshot (`frontend/`, `sidecar/`, `requirements.txt`, `start-mvp.bat`) from `archive/mvp/` into a new `archive/_human-only/mvp/`, putting it behind the same human-only deny-read fence as `dev/notes/_human-only/`. Added matching `Read(./archive/_human-only/**)` + `Read(./archive/_human-only)` deny rules to `.claude/settings.json`. Files relocated verbatim; the folder stays tracked in git (deny-read only, not gitignored).

Files: .claude/settings.json, archive/_human-only/mvp/** (moved from archive/mvp/**), DEVLOG.md

---

### 2026-06-27 07:33:00 — Bridge data layer: transcript work-step count + by-tool Turns breakdown (additive); control surface + capability map confirmed live

Extended `derive_context_usage` (additive, no frontend/render-path change) so the already-curl-proven `/context` endpoint now also serves **`work_steps`** — the agentic-work-step count the `--max-turns`/Lifecycle cap actually limits (distinct main-line assistant `message.id`; a streamed thinking+tool split shares one id → counts once) — plus a **`tools`** by-tool breakdown (read/edit/bash/mcp/subagent/web/other) from `tool_use` blocks, with `tool_total`. The old `turns` field (user string-content = *prompt rounds*) is kept for compat but documented as the wrong unit (it's also polluted by slash-command/meta entries). Subagent sidechains are excluded from every count. **Fixed a real classifier bug found live**: this Claude Code build spawns subagents via the **`Agent`** tool (not `Task`), so the Subagent slice was mis-bucketed as "other" — now both `Agent` and `Task` map to subagent. +13 hermetic tests (57 pass). Live-verified end-to-end on a real bridge agent (no `AWL_DRIVER`): `/context` matched the transcript exactly through tool work, a subagent spawn, and a sidecar restart (`subagent:1`, `other:1`=ToolSearch, `bash:3`, `tool_total:7`).
Control surface re-confirmed live (real tmux effect, not just HTTP): **model/effort/interrupt/permission(round-trip)/resume = work**; **mode = silent stub** (HTTP 200 + reports `plan` while the TUI stays `accept edits on`); **fast/thinking = honest HTTP 400**. Capability findings (report-only, nothing built): **subagent detection is fully derivable** — the parent transcript records the `Agent` spawn (type/description/prompt) + a result with `agentId` and a `<usage>` summary (subagent_tokens/tool_uses/duration), and the subagent's full transcript persists at `<project>/<parent-uuid>/subagents/agent-<id>.jsonl`; **context-per-category is scrape-only** via the `/context` TUI grid (Memory/Skills/Messages/Free space/MCP/Custom agents…), not in the transcript (aggregate tokens only) → design decision; **config readback**: model + permission-mode are clean from the transcript, effort/fast are intermittent screen-scrape, thinking not recoverable. (`design/mockup.html` shows modified in the tree — that's the parallel design session's work, deliberately left unstaged.)

Files: sidecar/drivers/bridge.py, tests/test_bridge_unit.py

---

### 2026-06-27 07:55:00 — Round-11 Next-up batch (6 items) shipped in mockup.html (+ DESIGN.md sync; browser-verified)

Implemented all 6 items filed into `design/TODO.md` Next up at 06:55. Mapped each first with a parallel read-only agent pass (per-item edit recipes + a cross-item reconciler that confirmed items 3+4 compose and flagged item 6 was already in the file). **(1) Warning header badge:** generalised the `type==='error'`-only subtype emitter (~5034) to any card with `o.subtype`, tagging a new `.inbox-subtype--warning` variant (`--warning` text+border, `--warning-soft` fill — matches the Warning section heading; Error keeps the `--danger` base); rewrote the rowan REQS sample to a real limit-crossed, now-pending case (`subtype:'Max turns'`, 50/50). For coherence with the TODO's "now pending" (the prior round wired drew's Error across graph+inbox+feed), also flipped rowan's **graph node-5**: Active→**Pending** badge (`statusJump('pending')`), Turns 41/50→**50/50** (danger), `run-active run-indet`→`run-pending`, marquee → "max turns reached — paused for your input", + the forensics digest line. **(2) Reply divider:** dropped the 2px navy `<span>` in `inboxReplyHTML()` (~5021); `ml-auto` moved onto the Reply button keeps its right-alignment. **(3) Visible gutter:** gave `.md-rail--fill` a repeating **navy (`--border`) 1px hairline** gradient over `--surface-3` at the ~20px row pitch (echoes the real per-row navy dividers, lighter to read as "empty continuation" — switched from `--rule` to navy after a browser A/B, the tan hairline was too faint and mismatched), + seeded a short **`notes.md`** doc (nav row + pane + `renderDocs`) so the extended rail is demonstrable. **(4) Selection clamp:** added `:not(.md-fill)` to the two `.md-row.rsel/.rsel-sec` fill selectors (~1655) — CSS-only, leaves `SELby`/`railClick` untouched (the filler still gets the class but never paints); composes with #3 (filler keeps its gradient base). **(5) Raised footer popovers:** the reviewer dropdown was clipped by `.plan-card{overflow:hidden}` AND ran ~444px past the panel scroll-bottom opening downward — fixed by opening it **upward** as a raised overlay like the neighbouring Export menu (`.src-pop.rev-pop` 2-class override of top/bottom), plus a general `.plan-card.pop-open` overflow-release wired into `toggleRevPop`/`toggleExport` and cleared by `closeAllPopups` (defensive — also covers the downward verdict `.vpop`, which is **not currently instantiated**; raised its z-index 30→70 too). The Export `.ea-dd` was already unclipped (opens upward). **(6) Heading rename:** `expMenuHTML`'s first section heading "Export" → "Copy &amp; Export" (~3735; entity decodes to `&`). **DESIGN.md synced:** Inbox subtype sentence + Warning row (#1), doc-editor empty-track wording (#3), Review-chip raised-overlay note (#5), the merged-Export heading in two places (#6); #2 + #4 need no design change (cosmetic / a bugfix preserving the documented "selected rows = teal" rule). **Verified by driving the rendered UI** (Playwright, headed — the only mode in this env, so it is the headed-parity pass) at wide **1680** + narrow **1100**: rowan **MAX TURNS** badge amber (#d98a2b) mirroring drew's red **CONNECTION**, Reply divider-less + right-aligned, `notes.md` filler ruled to the bottom, whole-doc + last-section select stop at the last line (filler stays tan, not teal), **COPY & EXPORT** heading, rev-pop opens upward **fully unclipped (zero clippers)** at both extremes, `.plan-card.pop-open` clears on close; console 0 errors. Items left in place in TODO.md Next up per the workflow (human removes after review).

Files: design/mockup.html, design/DESIGN.md, DEVLOG.md

---

### 2026-06-27 08:05:00 — R11 cross-check: the three design docs confirmed in alignment; batch committed + pushed

Cross-checked `mockup.html` ↔ `DESIGN.md` ↔ `tokens.css` before committing the 07:55 Round-11 batch. **tokens.css:** no change needed — every value the new CSS uses is an existing token (`--warning`/`--warning-soft` for the Warning subtype badge, `--border`/`--surface-3`/`--rule`→navy for the filler hairlines, `--select` for the clamp, `--danger*` for the Error base); a full `var(--…)`-resolves audit of `mockup.html` (77 referenced tokens) found **zero undefined references**, and the concurrently-deleted `--inbox-warning` is not referenced anywhere (clean). **DESIGN.md:** synced for items 1 (subtype sentence + Warning row), 3 (doc-editor empty-track → continued navy hairlines), 5 (Review-chip picker opens upward), 6 (merged-Export heading ×2); items 2 + 4 confirmed to need no design change (cosmetic / a bugfix preserving the documented "selected rows = teal" rule). **mockup.html:** all 13 R11 markers present; JS `node --check` clean. Committed the 4 uncommitted design files (DEVLOG, DESIGN.md, mockup.html, + one stray human TODO backlog note) and pushed.

Files: design/mockup.html, design/DESIGN.md, design/TODO.md, DEVLOG.md

---

### 2026-06-27 09:15:00 — Part 1 backend builds: honest set_mode, permission-mode-at-launch, subagents endpoint (additive, bridge-first, live-verified)

Three additive backend builds (no frontend/render-path change). **(1) Honest `set_mode`** — `POST /sessions/{id}/mode` previously returned `{"status":"ok"}` while the bridge driver no-op'd, falsely claiming success; it now mirrors `set_fast`/`set_thinking` and returns **HTTP 400 "Driver has no mode control"** when the driver doesn't advertise `set_mode` (bridge doesn't; sdk still works). Interim only — real mid-run mode change stays under separate research. **(2) Permission mode at launch** — the bridge launch ignored the session's `permission_mode` (create used only cwd+model). Added a `permission_mode` kwarg to `TmuxBridge.create()` that appends claude's `--permission-mode <mode>` (guarded by a new `VALID_PERMISSION_MODES` allow-list from `claude --help`: acceptEdits/auto/bypassPermissions/default/dontAsk/plan — unknown values dropped, TUI launches default), and wired `self.config.permission_mode` through the bridge driver's `start()`; the existing `_clear_startup_gates` already clears the bypassPermissions warning gate. **(3) Subagents endpoint** — new `GET /sessions/{id}/subagents` + `derive_subagents()` (pure, in the bridge driver) + a `subagents` capability + `get_subagents()` on base/bridge drivers. Pairs each main-line `Agent`/`Task` `tool_use` with its `tool_result` by id; reads the structured `toolUseResult` (agentId/status/totalTokens/totalToolUseCount/totalDurationMs/resolvedModel) with a `<usage>`/agentId text fallback; mints stable s1/s2 ids; status = running (no result yet) / done / error. **Live-verified the normal way** (sidecar started with no `AWL_DRIVER` → bridge; real tmux agents; curl): plan-mode agent shows `⏸ plan mode on`; bypassPermissions agent clears the gate and reaches **idle** showing `⏵⏵ bypass permissions on`; `/mode` returns 400; create→send→render(user+assistant blocks)→idle→delete round-trips clean; an agent that actually spawned a subagent returned `{count:1, s1, agent_id:a53b…, type:general-purpose, status:done, usage:{tokens:11670,tool_uses:0,duration_ms:1646,model:claude-sonnet-4-6}}`, with the empty case returning `{count:0}`. Cleaned up sessions/tmux/port. **+13 hermetic tests** (11 `derive_subagents` incl. running/done/error/Task-name/text-fallback/sidechain-exclusion, 2 `VALID_PERMISSION_MODES`); full hermetic suite **69 passed**.

Files: sidecar/main.py, sidecar/drivers/bridge.py, sidecar/drivers/base.py, bridge/bridge.py, tests/test_bridge_unit.py, DEVLOG.md

---

### 2026-06-27 09:35:00 — Master functionality-coverage map (whole-surface capability inventory, ranked) — planning doc

Created `dev/notes/coverage-map.md`: the single master checklist inventorying **every capability the intended UI commits to**, each mapped to its backend reality (data needed + source[transcript/screen/synthesized/filesystem] + status; control needed + status; build state). It **extends** the partial capability map from the 07:33 "Bridge data layer" entry out to the **whole** surface — Team Graph, Team Feed, Agent panel, Prompt, Library, Settings, and the cross-cutting features (linking/context-sharing as the defining feature, scratchpad, Embed/Attach, send-queue, lifecycle caps, identity, event-stream architecture, Rewind/Handoff, utility passes). Built by **parallelizing the research** (6 general-purpose agents, one per panel area, each grounded in DESIGN.md + mockup.html for intent and the live sidecar/bridge code + the v5 QA doc for reality, with a shared status taxonomy [`proven`/`derivable-not-built`/`needs-investigation`/`impossible`] and reality-anchors block), then **synthesizing** their structured tables into one document with a single consistent ranking — a **Phase 0→5 MVP build order**, a "backend reality in one screen" summary (proven floor · hard bridge ceilings · the net-new buckets), and a status rollup. Captures the named findings correctly: total context % live from transcript (built); per-category context proven-available-not-built (scrape `/context`, queue til idle, never interrupt); mid-run permission-mode change blocked/under-research; mode·effort·interrupt·permission·resume proven; plus this round's Part 1 builds (mode-at-launch, honest set_mode, /subagents). Key synthesis call: most MVP P0s are "backend proven, frontend not-started" (the live App.tsx is a 2-pane stub), so the MVP is largely a UI build over a proven bridge floor + three foundational backend pieces (aggregated identity-tagged event stream · prompt queue + boundary detection · agent-identity store), after which linking becomes tractable. Planning doc only — no code changed. (Two of the six research agents incidentally spawned their own subagents, an extra live confirmation that the Part-1 `/subagents` machinery holds under real load.)

Files: dev/notes/coverage-map.md, DEVLOG.md

---

### 2026-06-27 11:45:00 — Per-agent launch config + Settings registry reads + Usage aggregate (additive backend, bridge-first, live-verified)

Three additive backend builds (no frontend/render-path change), all applied **at launch** because a running claude TUI can't be re-scoped. **First confirmed the native mechanisms live on the actual `2.1.195` binary** (the handoff/research said 2.1.187 — version drift, noted): `--disallowedTools` removes a tool from the toolset in **every** mode incl. `bypassPermissions` (the reliable hard-block), `--allowedTools` is **ignored under bypassPermissions** (the documented claude bug — print-mode probe: bypass+allow-only-Read still ran Bash), `--settings` (file or inline) honors `permissions.{allow,deny,ask}` (deny hard-blocks), `--mcp-config`+`--strict-mcp-config` scope to a subset, and `enabledPlugins` (a documented settings key) injected via `--settings` gives **per-session plugin enable/disable** (probe: enabling globally-disabled superpowers made its skills appear).

**(1) Per-agent permissions / plugins / MCP.** Extended `DriverConfig` + `CreateSessionRequest` + `TmuxBridge.create()` + `SessionState.to_dict` with `allowed_tools`/`disallowed_tools` (→ `--allowedTools`/`--disallowedTools`), a `permission_rules` {allow,deny,ask} object and `enabled_plugins` {`"id@mkt"`:bool} (both composed into a per-agent `--settings` file), and `mcp_servers` (a chosen subset → a per-agent `--mcp-config` + `--strict-mcp-config`; `None`=inherit global, `[]`=strict-none). Per-agent config files are written to a WSL path (`~/.awl-agents/<name>/`, new `WSL_AWL_DIR`) via the stdin/`cat >` pattern (dodges the ~32 KB Windows cmdline limit); `create()` rebuilt to shell-quote the launch argv robustly (`shlex`) so tool specs with spaces/parens/globs survive bash→tmux→sh; `close()` now `rm -rf`s the per-agent dir; the applied config is surfaced on `to_dict.launch_config` and persisted to the runtime record. **(2) Settings reads** — new `bridge/registry.py` + `GET /settings/{mcp,plugins,config}` (`?project=<path>`): MCP servers user+project with enabled-state (env values **masked** to `env_keys`), installed plugins (authoritative `enabled` from `claude plugin list --json`) + marketplaces, Config global+project (model/effort/mode/sandbox/env/hooks/perms/plansDirectory/CLAUDE.md) each tagged **Live vs New-session**. **(3) Usage** — `GET /usage` (per-agent tokens/window/percent/work_steps + fleet totals + footer token-pill value); folded in the research-flagged fix making the context window **model-aware** (`context_window_for_model`: 200K default, 1M only for 1M-context models — was hardcoded 1M).

**Live-verified the normal way** (sidecar on bridge, no `AWL_DRIVER`, real tmux agents, curl): an agent launched with `disallowed_tools=[Bash]` + `permission_rules.deny=[Glob]` + `enabled_plugins{superpowers:true}` answered **`Bash=no, Glob=no, Read=yes, Edit=yes`** and listed **superpowers:** skills (its written `settings.json` = `{permissions:{deny:[Glob]},enabledPlugins:{...}}`); an agent with `mcp_servers=[exa]` showed **only `exa` (1 server)** in `/mcp`; `/usage` returned per-agent context (a distinct-cwd agent read **24506** tokens vs **38618** for two same-cwd agents — see caveat) with the correct model-aware 200K window for sonnet; the vanilla **create→send→render→idle→delete** flow still passes; sessions/tmux/`~/.awl-agents`/port all cleaned. **Caveat surfaced (pre-existing, out of scope):** `find_transcript` resolves one transcript per cwd, so agents sharing a cwd read the same transcript (identical `/usage` + wrong `/history`) — the research doc's PID→session-file fix is the remedy; flagged, not fixed. Removed a dead `WSL_CLAUDE_DIR` import. **+12 hermetic tests** (registry reads, MCP subset builder, settings/plugins composition, model-aware window); full hermetic suite **81 passed**.

Files: bridge/paths.py, bridge/bridge.py, bridge/registry.py, sidecar/drivers/base.py, sidecar/drivers/bridge.py, sidecar/main.py, tests/test_bridge_unit.py, DEVLOG.md

---

### 2026-06-27 11:52:00 — coverage-map: reflect this round's built backend (per-agent config, Settings reads, Usage)

Updated `dev/notes/coverage-map.md` to mark what the 11:45 builds moved off the not-started/partial pile. Added a **"✅ Built this round"** block to the one-screen summary (per-agent permissions/MCP/plugins at launch + the bypass-allowlist caveat; the three `/settings/*` reads; `/usage`; the model-aware window) and corrected the prior "hardcoded 1,000,000 window" line. Rewrote bucket #9 (Settings) and the Settings-section intro (the "no /settings route exists" note is now false — reads are built; what's net-new is the **writes** + the Usage plan/limits band). Flipped the changed rows: Agent-panel **Tools multi-select** (per-agent allow/deny at launch, `partial`); Settings **MCP user/project registry** (`built`), **Plugins installed list** + **enable/disable** (read built; per-agent enable via `--settings enabledPlugins` proven; global toggle still a write), **Config default-model** (read built; global write net-new), **Usage token Σ** (`built`), **footer token pill** (value built). Refined the **Usage account/limits** rows with the Part-4 source finding: plan/tier IS local (`~/.claude/.credentials.json claudeAiOauth` + `~/.claude.json oauthAccount`), but the live rate-limit %/resets are **API-only**, not in any local file. Doc only.

Files: dev/notes/coverage-map.md, DEVLOG.md

---

### 2026-06-27 11:55:00 — Fix transcript collision: per-agent transcript via claude `--session-id`

Fixed the collision caveat flagged in the 11:45 entry: `find_transcript` resolved one transcript per cwd, so two agents sharing a dir read each other's transcript (identical `/usage`, wrong `/history`). **Verified the research doc's PID→`~/.claude/sessions/{PID}.json` mapping is DEAD on this build** — 2.1.195 no longer writes those files (newest was Jun 13; two fresh live runs wrote none) — so used the native **`--session-id <uuid>`** flag instead (confirmed in `--help`; print-mode probe: two agents in one cwd with distinct ids wrote two distinct `<id>.jsonl`, each carrying only its own content). `TmuxBridge.create()` now launches with a pinned `--session-id` and tracks it in `_session_uuids`; `find_transcript` resolves each session's own `<id>.jsonl` (and returns None rather than falling through to "newest" when that file isn't written yet, so a co-located sibling can't be cross-read); the legacy newest-file fallback is kept for non-dashboard sessions. For restart-survival the id is persisted in the runtime record and re-registered on resume (`register_session_id`) — deterministic, replacing a fragile `/proc`-cmdline recovery that mangled through `wsl.exe` arg-passing. **Live-verified the normal way**: two real bridge agents in one cwd resolved to distinct transcripts (ALPHA-only / BRAVO-only), and a fresh bridge re-registering the persisted id resolved each correctly. +6 hermetic tests; full hermetic suite **86 passed**.

Files: bridge/bridge.py, bridge/transcript.py, sidecar/drivers/bridge.py, sidecar/main.py, tests/test_bridge_unit.py, DEVLOG.md

---

### 2026-06-27 12:05:00 — Minimal agent-identity store (role/number/name/color/icon, persisted)

Added a dashboard-owned per-agent identity so agent cards / the Agent panel have a real identity beyond `agent_type`+`model`. New `sidecar/identity.py`: `assign_identity(requested, ordinal)` resolves `{role, number, name, color, icon}` — **color** round-robin over the 16 `--ag-*` Jewel tokens (`design/tokens.css`, in the mockup's interleaved order so adjacent agents get distinct hues), **icon** round-robin over the 167 `assets/icons/agents/` game-icons, **number** sequential, **role** default "Agent", **name** empty; every field overridable via the create payload. Wired through: `CreateSessionRequest.identity` (new `IdentityInput`) → `SessionState` (holds + surfaces on `to_dict.identity`) → `DriverConfig.identity` (passthrough) → the bridge driver's runtime record (persisted) → `reconnect_sessions` (restores persisted identity and advances the round-robin counter past reconnected numbers so a new agent never reuses a live one's color). A monotonic `_identity_ordinal` drives the round-robin. **DEFERRED per scope:** the past-16 color/icon uniqueness algorithm and human-name pools (past 16, color simply repeats). **Live-verified** (sidecar on bridge, curl): agent 1 → `crimson #aa3a61 / alien-bug / #1`, agent 2 → `emerald #008149 / alien-skull / #2` (round-robin advanced), agent 3 with `{role:Reviewer,name:Ada,color:#112233}` honored (icon still round-robin `alien-stare`); all three persisted in `sessions.json` and surfaced on `GET /sessions`; the **create→send→render→idle→delete** flow still passes (send→idle 4 s, history rendered the reply). +6 hermetic tests; full hermetic suite **92 passed**.

Files: sidecar/identity.py, sidecar/drivers/base.py, sidecar/drivers/bridge.py, sidecar/main.py, tests/test_sidecar_unit.py, DEVLOG.md

---

### 2026-06-27 12:58:00 — UI foundation: real three-pane dashboard wired to the proven bridge floor

The first real UI build — replaced the ~571-line two-pane `App.tsx` stub with a modular three-pane dashboard (title bar · Agent | Team-Graph/Library | Team-Feed/Prompt · footer), refactored into 11 renderer modules (`tokens`, `api`, `events` [extracted render components], `ui` [neobrutalism primitives], `AgentTile`, `Splitter`, `TeamGraph`, `AgentPanel`, `TeamFeed`, `PromptPanel`, `App`), inline-styled from a token object mirroring `tokens.css` (no Tailwind/shadcn introduced). **Everything rendered is backed by a proven endpoint; unproven mockup elements are honestly absent or disabled.** Built: resizable **splitters** (3px navy, min/max clamped); **Team Graph** cards (derived 4-state badge active/idle/pending/error; recolorable game-icon identity tiles; Ctx% health bar from `/usage`; Turns count from `/context` work_steps — NOT `total_turns`, which is 0 on bridge; subagent strip from `/subagents`; created-time + auto-scaling "ago"; grid that scrolls); **selection drives the app** (card → Agent panel + Feed + Prompt); **Agent Details** (identity/status/created header; set-model + set-effort [proven]; Mode shown as the launched value with the segmented control **disabled** [mid-run change 400s]; Fast/Thinking **disabled** [400 on bridge]; Ctx bar + Turns by-tool; Retire w/ inline confirm); **Agent Create** (`POST /sessions` — role/name, 16-swatch color picker, icon, model, mode-at-launch, cwd, per-agent disallowed-tools; Create/Reset/Cancel); **Team Feed Messages** (focused agent's rendered stream) + **Inbox** (per-agent Permission cards w/ the parsed question/options + Approve/Deny → `/permission`; fleet pending-count badge); **Prompt Compose** (fire-now `/send` + Stop `/interrupt`) + **History**. Honest fallbacks: Run strip = barber-pole when active (no real %); Marquee omitted (no source); Library/Console/Scratch/Log/Settings/linking/send-timing **absent** (each needs net-new backend), each surfaced with a one-line note. **Small backend support for the UI** (`sidecar/main.py`): a recolorable identity-icon route (`GET /assets/agent-icons/<name>?color=#hex`, hex-validated, serves the existing `assets/icons/agents/` set), and `permission_request` + `cwd` added to `to_dict`. Added a standalone Vite config (`frontend/vite.standalone.config.mjs`) to serve the renderer over http for verification. **Live-verified the normal way** (sidecar on bridge, real agents, Vite over http://localhost, Playwright **headed**): create→send→**render**→idle (Team Feed rendered the reply; card Ctx filled 13%, Turns 1; panel 25.5K tokens / 200K model-aware window; footer token pill updated); selection focus; set-model→opus round-trip; the Create form spawned a real agent (auto-number 03, picked violet tile); the Inbox Permission card showed a real prompt and Approve drove the round-trip (file written); Stop interrupted a run (ACTIVE→idle, green barber-pole rendered); History/Inbox tabs; **resize to 1080 (narrow) and 2400 (wide)** + dragging splitters to both extremes — layout reflows/wraps/scrolls, no breakage, clamps hold. Fixed a real bug found in verification (the create-time roster race that left a new agent unselected — now optimistically added) and split the `/subagents` poll onto a slower cadence to cut the per-agent `read_log` fan-out that was transiently saturating the sidecar's WSL-subprocess thread pool. **Known pre-existing backend/bridge characteristics (not UI defects), flagged:** (1) heavy poll load (N×`read_log`/cycle, each spawns `wsl.exe`) can transiently drop a request — GETs degrade gracefully, an action call may need a retry; (2) an intermittent bridge keystroke-landing flake on permission Approve (the events loop re-flags pending until the Enter lands); (3) concurrent control sends collide at the bridge keystroke level (sequential clicks are fine). The mockup/DESIGN/tokens remain the forward target — unchanged.

Files: frontend/src/renderer/{App,AgentPanel,AgentTile,PromptPanel,Splitter,TeamFeed,TeamGraph}.tsx, frontend/src/renderer/{api,tokens}.ts, frontend/src/renderer/{events,ui}.tsx, frontend/vite.standalone.config.mjs, sidecar/main.py, DEVLOG.md

---

### 2026-06-27 13:08:00 — UI stretch: Settings step-into view (proven registry reads)

The core three-pane UI landed clean and verified, so wired the stretch: a **Settings step-into view** (new `Settings.tsx`) opened from a **title-bar gear**, replacing the 3-pane body and returning on Close (the title bar + footer stay). Four tabs over the **proven read endpoints**, read-only: **Usage** (`/usage` — fleet total tokens + per-agent table joined with identity for tile/role/name, each with model/tokens/ctx%/turns; the plan/limits band is honestly noted absent, API-only); **MCP** (`/settings/mcp`, user/project scope segment — each server's name, enabled pill, transport, command/url, and **masked env keys**); **Plugins** (`/settings/plugins` — installed name@marketplace · version · scope · enabled pill + the marketplaces list); **Config** (`/settings/config`, global/project scope segment — model/effort [tagged **Live**], permission-mode/sandbox/plans-dir [tagged **New session**], permissions.allow/deny/ask, env, hooks, + the CLAUDE.md paths, with a standing global-edit warning that writes are gated/later). Added `settingsMcp`/`settingsPlugins`/`settingsConfig` to the api client. **Reads only** — the enable/disable toggles and the confirm-gated global edit are explicitly a later run (surfaced, not faked). **Setups** tab omitted (no blueprint store exists) and **Delete (permanent wipe)** still deferred (Retire only — no wipe backend). **Live-verified headed** (Playwright over http://localhost): the gear opens Settings; all four tabs render real WSL-side data (25.7K fleet tokens; 13 user MCP servers with masked env; 5 installed plugins + 5 marketplaces; global config model=opus/effort=medium with Live/New-session tags + CLAUDE.md paths); Close returns to the 3-pane.

Files: frontend/src/renderer/Settings.tsx, frontend/src/renderer/api.ts, frontend/src/renderer/App.tsx, DEVLOG.md

---

### 2026-06-27 10:24:00 — Impulse mockup pass: icon-fill agent cards + avatar screenprint on the human tile + badge overhang restored

Three user-requested changes to `design/mockup.html` (lock-checked first: the design doc was git-clean, untouched ~9.5h, no parallel session mid-edit). (1) **Icon-fill agent cards** — each Team Graph `.node` carries its agent colour via a per-card `--nc` var, plus a behind-content `.node-bg` `<svg><use href="#ag-*"></svg>` layer (z-index:-1, contained by `isolation:isolate`); the symbol's colour-square is knocked out (`color:transparent`) so only the white glyph shows at `--node-icon-alpha:0.30` — a single knob. Card text flipped to white-ink (with a soft shadow) so it stays legible on the colour. (2) **Human-tile screenprint** — generated a photo-derived white-ink cameo from the GitHub avatar (handle `adamwlester`, pulled from the git remote), radial-vignetted to drop the foliage background; saved as `assets/icons/ui/user-screenprint.png` and applied via a NEW `.agtile--me` class added only to genuine human tiles + the JS `agtileHTML` helper — the reused `.agtile--user` tiles (azure Scratch source, dashed New-agent slot) are deliberately untouched. (3) **Badge overhang** — removed the meta-strip de-pin override so `.node-badge` returns to its base `position:absolute; top:-8px; right:-8px` corner overhang (the old "ledge"); `.node` switched `overflow:hidden`→`visible` to let it overhang; date re-aligned high in the header, bottom toward the badge.

Verified in-browser (Playwright/localhost, headless + fresh-reload parity) at 760→1760px: icon-fill, badge overhang, and the avatar cameo all hold at both extremes; selection-ring move, subagent-drawer growth (the `overflow` change), and status-badge click all work; 0 JS errors (favicon-404 only). All `--nc`/icon-alpha values stayed in the mockup (no `tokens.css` change). A background adversarial audit workflow (3 requirement skeptics + a regression critic) was launched. **Impulse "try it" pass — knobs to tune next: `--node-icon-alpha`, the white-ink text contrast, the date's exact vertical alignment, and screenprint punch (v1 smooth vs v2 punchy).**

Files: design/mockup.html, assets/icons/ui/user-screenprint.png, DEVLOG.md

---

### 2026-06-27 10:40:00 — Correction: human-tile avatar inlined as a data URI (was a gitignored PNG)

The background adversarial audit's regression critic caught a real packaging gap in the prior entry: the `assets/icons/ui/user-screenprint.png` it referenced is matched by `.gitignore` (`*.png` line 44 — and `*.svg` line 49, so the **entire `assets/icons` tree is gitignored / 0 files tracked**; that's exactly why the mockup inlines its agent icons as SVG symbols rather than linking the files). A committed `mockup.html` pointing at that PNG would render a **broken human avatar on any fresh checkout**. Fixed by **inlining the screenprint as a base64 data URI** in the `.agtile--me` rule (matching the mockup's established self-contained pattern) and deleting the now-unreferenced PNG copy from `assets/icons/ui/`. Re-verified in-browser: all 10 human tiles render the cameo from the data URI, 0 console errors, and the card/badge changes are unaffected. Net: the change is now fully self-contained — the only tracked file touched is `design/mockup.html`. Audit verdict was 4/4 PASS; the remaining notes are tuning nits (idle-text contrast on the blue/purple cards, cameo softening below ~24px, date only roughly bottom-aligned).

Files: design/mockup.html, DEVLOG.md

---

### 2026-06-29 18:31:00 — Icon-fill cards: navy scrim overlay for contrast (`--node-scrim`)

Per the contrast review, **darkened** the icon-fill agent cards (vs lightening + dark text). Added a `--node-scrim` knob (navy `rgba(0,24,88,0.42)`) painted as a `<rect class="node-scrim" width="100%" height="100%"/>` inside each of the 13 `.node-bg` layers, after the `<use>` — so it covers BOTH the colour fill and the glyph but sits behind the white text (the layer is z-index:-1). The whole card background now reads much darker while the inverse light text stays bright; the bold colour-as-identity look is preserved (hues deepened into one band, not turned pastel). Two knobs now: `--node-scrim` (darkness) and `--node-icon-alpha` (glyph strength). Verified via headless Chrome at 1480px (the Playwright MCP browser had dropped mid-session): emerald/cobalt/fern/amber all deepen uniformly, white text is crisp, the icon watermark still reads, no rendering breakage. Pure colour overlay — no layout change, so the prior 760→1760px extremes + interaction verification still holds.

Files: design/mockup.html, DEVLOG.md

---

### 2026-06-29 18:45:00 — Icon-fill cards flipped to a LIGHT tint + standard navy text (dropped the dark scrim)

The dark-scrim version read too dark against the rest of the light UI, so switched to the light treatment. Card background is now a **light tint** of the agent colour — `color-mix(in srgb, var(--nc) var(--node-tint,15%), var(--secondary-background))`; the glyph is the agent colour as a soft watermark — `--icon-fg: color-mix(in srgb, var(--nc) var(--node-icon-pct,30%), transparent)`; and **all the white-ink text/border overrides were removed** so text and borders inherit the standard navy/token colours and match every other surface. Removed the 13 `<rect class="node-scrim">` overlays plus the `--node-scrim`/`.node-scrim` CSS. Selected = a stronger 26% tint + teal ring + hard shadow. Two knobs: `--node-tint` (card lightness) and `--node-icon-pct` (watermark strength). Verified via headless Chrome at 1480px (Playwright MCP browser still down): pale tinted cards, crisp navy text, soft colour watermark, identity tiles still solid — integrates cleanly with the UI. Colour-only change, no layout impact, so the prior extremes/interaction verification still holds.

Files: design/mockup.html, DEVLOG.md

---

### 2026-06-29 19:02:00 — Icon-fill cards: flipped icon polarity (darker field + lighter glyph), both pale & close

Per the tweak, matched the real identity tiles' polarity in the pale register: the icon FIELD is now the slightly darker tint and the GLYPH the lighter tint (was reversed — the glyph had been the darker part via a translucent colour overlay). Field `--node-tint` 15%→22%; glyph switched from a translucent overlay `color-mix(--nc 30%, transparent)` to an OPAQUE lighter tint `color-mix(--nc 15%, var(--secondary-background))` (= the value the field used before). The two tints are now close and both fairly light, with the glyph lighter than the field (like the white-on-colour tiles, dialled pale). Selected bumped 26%→33% to stay distinct from the new 22% base; navy text/borders untouched. Verified via headless Chrome at 1480px: icons read as lighter glyphs on a marginally darker tinted field — subtle and light as asked. Knobs unchanged in spirit: `--node-tint` (field), `--node-icon-pct` (glyph).

Files: design/mockup.html, DEVLOG.md

---

### 2026-06-29 19:20:00 — Icon-fill cards: glyph lightened to near-white for negative/positive contrast

Per the contrast tweak, increased separation between the background-icon's negative space (field) and positive space (glyph) by **lightening the glyph** rather than darkening the field — keeps the cards light/on-brand (darkening the field would re-risk the "too dark vs the UI" problem). `--node-icon-pct` 15%→5% (near-white glyph); field stays `--node-tint` 22%. Mirrors the real identity tiles' white-on-colour glyph, just in the pale register. Verified via headless Chrome @1480px: glyphs read crisply as near-white shapes on the tint, navy text unaffected, overall card tone stays light. Knob: `--node-icon-pct` (drop toward 0% for pure white).

Files: design/mockup.html, DEVLOG.md

---

### 2026-06-29 20:05:00 — User-icon rendering options gallery (pre-decision) → design/ui-snippets/

Built a standalone review gallery `design/ui-snippets/user-icon-options.html` (self-contained, inline data URIs) showing 6 ways to render the human user avatar on the `--ag-user` slate tile, each at the actual UI sizes (24–40px) + enlarged (96/200px): **A** tight-crop pure-white stencil, **B** same with soft edges, **C** pure-white + navy keyline, **D** white + navy shadows (2-tone, most identifiable), **E** looser crop, **REF** the current graded baseline. No mockup changes yet — awaiting the user's pick. Two follow-ups already scoped for when they decide: (1) inline the chosen treatment into `design/mockup.html`; (2) one-line badge fix — `.badge.ag-user-badge .agtile` ([mockup.html:1373](design/mockup.html#L1373)) uses the `background` shorthand which wipes the avatar `background-image` in the card badges (Messages/History/etc.), so it currently shows just the slate fill; switching it to `background-color` lets the avatar render in every user badge. Generator: `.scratch/avatar/make_options.py`.

Files: design/ui-snippets/user-icon-options.html, DEVLOG.md

---

### 2026-06-29 20:30:00 — User-icon: option C (pure-white + navy keyline) inlined + badge fill fix (avatar now in ALL user badges)

Picked option C with a looser crop. Regenerated the screenprint as a 1-bit pure-white stencil + a thin navy keyline on a **compromise crop** `(45,13,246,214)` — the midpoint of the tight A–D crop and the looser E crop — so the **head is no longer clipped**; inlined it as the `.agtile--me` data URI in `design/mockup.html` (replacing the prior graded one). Also fixed the badge bug the user flagged: `.badge.ag-user-badge .agtile` ([mockup.html:1373](design/mockup.html#L1373)) used the `background` **shorthand**, which wiped the avatar's `background-image`, so user badges inside cards (Messages / History / To-From) showed only the slate fill — switched it to `background-color`, so the photo now renders in **every** user badge. Verified headless @1480px: the FROM/TO tile and the Messages "HUMAN User" card badge now show the face (pure-white stencil, full head, legible ~24–32px); agent badges still show their game-icons. Generator: `.scratch/avatar/make_C_comp.py`.

Files: design/mockup.html, DEVLOG.md

---

### 2026-06-29 21:30:00 — Design-system reconciliation: spec updated + audit/spec relocated to dev/notes, ui-snippets moved to .scratch

Prep for the one-shot design-system refactor (no product code or `design/` primary docs touched). (1) Reconciled `component-system-spec.md` to the decisions settled in the 06-27 and 06-29 planning chats and moved it out of `design/` into `dev/notes/` (it is build input that retires after the build, so `design/` now holds only primary design docs). Key spec changes: `data-comp` is now a kebab-case slug (one label, no parallel Title-Case registry); dormant or unresolved items are tagged via a `data-status` attribute (`planned` or `undecided`); stylesheet-extraction method is the building agent's call with render-identical as the acceptance bar; added a doc-distribution map (values to tokens.css, component CSS to styles.css, slugs and markers to mockup.html, catalog and blurbs to gallery.html, rules to DESIGN.md) so the spec can fully retire; decoupled from `TODO.md` entirely (no cross-references in the spec, mockup, gallery, or DESIGN.md); re-based the value snapshot on the live mockup as source of truth (naming the new icon-fill knobs `--node-tint` / `--node-icon-pct` and the `.agtile--me` / `.node-bg` additions as tokenization targets); replaced the old open-decisions list with an Open Questions register (OQ-1: `sb-error` and the subagent-click no-op parked as `undecided`, not forced); added a post-Phase-3 verification that `coverage-map.md`'s DESIGN.md citations still resolve. (2) Renamed and moved the audit `dev/notes/research/c2-audit.md` to `dev/notes/component-inventory-and-wiring.md` and dropped 'C2' from its H1 (the audit retires; agents work from the spec plus the live mockup, not the audit). (3) Moved `design/ui-snippets/` to `.scratch/ui-snippets/` (incremental design scratch, relocated out of `design/` to avoid confusion; now under the gitignored `.scratch`, so it is local-only and no longer tracked). Note: the audit and spec were created 06-27 but never logged; this entry backfills their existence as part of the relocation. Next: write the one-shot ultracode prompt against the updated spec.

Files: dev/notes/component-system-spec.md, dev/notes/component-inventory-and-wiring.md, .scratch/ui-snippets/user-icon-options.html, DEVLOG.md

---

### 2026-06-29 21:45:00 — Build prompt authored: dev/prompts/component-system-refactor.md

Wrote the one-shot build prompt `dev/prompts/component-system-refactor.md` for the design-system refactor (to be run in ultracode). By design it points the building agent at `dev/notes/component-system-spec.md` as the authoritative plan rather than restating it, lists the required-reading context (the CLAUDE.md UI-verification and DEVLOG rules, the live `design/` files as current-state truth, the inventory audit as background only), and surfaces the guardrails that are easy to miss: the spec's decisions are final (the earlier tractability review in `.claude/cc-exports/` is superseded), the render must stay identical through extraction and tokenization (verified by driving the UI, not reading diffs), single-source tokens with no renames of existing custom properties, `data-comp` kebab slugs plus `data-status` planned/undecided markers, no `TODO.md` references anywhere, absorb-then-retire the spec into the five permanent design files, and the post-Phase-3 check that `coverage-map.md`'s DESIGN.md citations still resolve. Mechanism: parallel subagents in isolated git worktrees per the repo's existing `nextup-parallel-execution.md` pattern, with the agent owning sequencing, merges, and final headed verification. Prompt authoring only; no code or design files changed.

Files: dev/prompts/component-system-refactor.md, DEVLOG.md

---

### 2026-06-29 22:00:00 — Review-driven refinements to the design-system spec + build prompt

Folded in a second session's review of the build prompt (five accepted items). Spec (`dev/notes/component-system-spec.md`): (1) called out that much of the catalog is JavaScript-generated, not static markup (the `.db-*` Lifecycle family, the Verdict badge, the count chips, the identity badges, and all five inbox card types come from `inboxCardHTML` / `verdictBadgeHTML` / `renderInbox` / `renderFeed` over the `REQS` / `MSGS` / `db-*` data), so `data-comp` slugs must be emitted from inside the builder functions and the gallery must author static specimens for the JS-only variants; (2) added a 'what stays out of `tokens.css`' boundary so per-instance bindings (`--nc`) and data or runtime values (a bar's inline `width:68%`, resizable pane widths) are not tokenized, while the global `--node-*` knobs are. Prompt (`dev/prompts/component-system-refactor.md`): added an exclusive-ownership-of-`design/` launch precondition; in verification, told the agent to capture a baseline screenshot set before Phase 0 and diff later renders against it (lanes run in worktrees that mutate the file), and to fall back to headless Chrome over localhost if the Playwright MCP browser drops rather than stalling (preserving a real rendered parity pass, not static checks); and a one-line note that `design-docs-refactor.md` is superseded. Docs only; no code or `design/` primary files touched.

Files: dev/notes/component-system-spec.md, dev/prompts/component-system-refactor.md, DEVLOG.md

---

### 2026-06-29 22:30:00 — Component-system Phases 2 + 5: data-comp / data-status tags on mockup.html

Additively annotated `design/mockup.html` (no render/behavior change): added `data-comp="<slug>"` to the root of every component instance per the registry, and `data-status` markers for not-wired/open-question items. Builder-generated families (identity/verdict/lifecycle/count/overflow/inbox-subtype badges, message/scratch/log/history/plan/asset cards, all five inbox-card types, doc-editor, export-control, attachment-chip, jump-pill, agree-toggle) got the attribute inside the returned HTML string so every rendered instance carries it; the five inbox slugs come from a per-type `_inboxComp` map; toast is set via `setAttribute`. Static/repeated families (status-badge ×14, connector-health ×21, config-scope ×19, registry-row ×26, settings-row ×38, subagent-badge ×11, switch ×23, agent-node-card ×13) were tagged on every instance via a one-off scratch script; cross-cutting primitives got one representative each. Pass B: `data-status="planned"` on the dormant edge layer (host `#graph-wrap` + comments at `LINKS`/`drawEdges`), Link Save/Delete, MCP/plugin switches, Console run+input (both views), and Review/citation/attachment routing (`sendReview`/`gotoCitation`/`composeAttach`/`openAttachment`); `data-status="undecided"` on every `.sbadge` (OQ-1, carries both attrs). Verified: all 53 registry slugs present, both inline scripts pass `node --check`, and stripping every added attribute reproduces the pre-edit file byte-for-byte (purely additive).

Files: design/mockup.html, DEVLOG.md

---

### 2026-06-29 22:35:00 — Open System Decisions tracker created (dev/notes/agent-qa)

Created `dev/notes/agent-qa/open-system-decisions-2026-06-29.md` — a shared tracker inventorying every unaddressed **system/product** decision (the band between the finished mockup and the proven bridge floor), kept distinct from the in-flight design-system refactor. 23 stable-ID'd items (`OD-01…OD-23`) in four tiers (Foundation · Linking · Feature-area · Strategic), each with a kind tag (`OPEN` / `BLOCKED` / `DECIDED‑UNBUILT`), a one-screen index table up top, and a blank `Decision:` line to fill as we resolve them together. Synthesized from `dev/notes/coverage-map.md`, `design/TODO.md` (incl. section C + Inbox), the two 06-27 cc-export planning sessions (ui-spec-3, build-2b), and the refactor spec's OQ-1. Read/think artifact only — **no `design/` files touched** (the refactor agent owns them mid-run); items that touch the design layer are flagged 🎨 to hold until that pass lands.

Files: dev/notes/agent-qa/open-system-decisions-2026-06-29.md, DEVLOG.md

---

### 2026-06-29 22:45:00 — Open System Decisions tracker: added agent recommendation + confidence per entry

Reworked `dev/notes/agent-qa/open-system-decisions-2026-06-29.md` so every one of the 23 `OD-*` entries now carries a **Recommended:** line (my suggested call) and a **Confidence:** tag, reusing the v5 QA doc's convention (▶ Confident / ◆ Leaning / ✚ Can't infer) for consistency. Added a **Conf** column to the index table and a confidence legend to "How to use." Recommendations are grounded in the existing notes where a prior decision settles it (e.g. OD-10 lifecycle caps = notify-only per ui-spec Q5b → ▶; OD-19 Delete-deferred per build-2b → ▶; OD-17 scratchpad write-in/read-out per QA Q22 → ▶) and honestly tagged ✚ where it's genuinely the user's product/taste call (OD-07 default cap value, OD-21 library commitment, OD-22 scope items, OD-23 palette direction). Content-only addition; no entries removed, no `design/` files touched.

Files: dev/notes/agent-qa/open-system-decisions-2026-06-29.md, DEVLOG.md

---

### 2026-06-29 23:00:00 — OD-01 finalized: aggregated event-stream design + event-id scheme

Filled the **Decision** field for OD-01 (cross-agent event stream) in `dev/notes/agent-qa/open-system-decisions-2026-06-29.md` and flipped its index Status to `decided` (Recommended left as-is per the session rule). The decision records: a single sidecar-owned aggregated **SSE** stream all panels subscribe to (replaces the 800 ms `/history` poll); lightweight per-event envelopes `{id, agent_id, seq, type, ts, payload|pointer}` with heavy content fetched on demand; a **bounded bus, not a stored mega-log** (on-disk per-agent JSONL stays source of truth; sidecar keeps a rolling ring buffer, UI virtualizes/backfills, From/To filters server-side); a deterministic composite **event id** `{agent_id}:{source}:{anchor}[:{block}]` (session-uuid · `t`/`s` · transcript-entry `uuid` or synth trigger key · block index) for dedup/replay; and a separate monotonic `seq` for ordering. Re-read the doc first (no parallel changes this round). Tracker-only edit; no `design/` or product code touched.

Files: dev/notes/agent-qa/open-system-decisions-2026-06-29.md, DEVLOG.md

---

### 2026-06-29 23:30:00 — Component-system Phase 4: design/gallery.html visual catalog created

New static component gallery `design/gallery.html` — the visual catalog for the design system. Links the **same** `tokens.css` + `styles.css` (and identical Tailwind config + lucide CDN) as `mockup.html`, so specimens render identically to the live components; only page-layout scaffolding is added inline, all `gx-`-prefixed (no component CSS redefined). Shows every registry slug **exactly once** grouped into Primitives → Badge catalog → Inbox cards → Composites: all **53 `data-comp` slugs** present (1 each) plus a 54th `link-edges` group (`data-status="planned"` SVG placeholder); badges are exhaustive (status 4 · subagent 3 (marked `undecided`, OQ-1 note) · lifecycle 10 · verdict 3 · count-chip 3 forms · connector-health 4 · config-scope 2 · identity 3+user · inbox-subtype 2 · overflow 1) and all **5 inbox card types** are hand-authored from the real builder markup. `agent-node-card` shows its 6 sub-parts with labeled callouts. Verified in-browser (headless, served over localhost) at wide + narrow extremes: 0 console errors, 77 lucide icons resolved, tokens/styles applied, no horizontal overflow after two fixes (added `.gx-stage--col > * { min-width:0; max-width:100% }` so live nowrap titles ellipsize, and `minmax(min(Npx,100%),1fr)` on the grids so cards never exceed the viewport). Headed parity pass not run — the Playwright MCP in this env is headless-only with no per-call headed toggle and no standalone Playwright installed.

Files: design/gallery.html, DEVLOG.md

---

### 2026-06-29 23:55:00 — Component-system refactor LANDED: `design/` is now the 5-file design system (capstone)

The one-shot `dev/prompts/component-system-refactor.md` pass is complete; `design/` is final, with the five permanent sources (`tokens.css` · `styles.css` · `mockup.html` · `gallery.html` · `DESIGN.md`) as the sole design source. This capstone covers the orchestrator-owned phases (Phases 2+5 and 4 are logged at 22:30 and 23:30). **Phase 0 (extract):** lifted both inline `<style>` blocks verbatim into the new `design/styles.css` (≈180 KB) and linked it from `mockup.html` right after `tokens.css`; proven **render-identical** by an objective per-element computed-style fingerprint over all **7514** body elements (hash matched the pre-extraction baseline exactly). **Phase 1 (tokenize):** added to `tokens.css` — `--border-width`/`--divider-width`/`--ring-width`, `--radius-sm`/`--radius-xs`, `--font-sans`/`--font-mono`, a primitive `--size-*` scale (27 small component dims, ≥2 uses, ≤64px) and a `--space-*` scale (15 padding/gap steps), and the global icon-fill knobs `--node-tint`/`--node-tint-selected`/`--node-icon-pct`; **removed** the retired `--req-*` family (6 tokens, confirmed unreferenced). `styles.css` now references everything via `var()` (2182 refs) — **zero** residual 2px/3px border or radius literals, **zero** inline font-family strings, **zero** recurring untokenized padding/gap/size values. Render-identical re-proven by computed-style diff: the only deltas vs baseline were the intended, visually-inert font-family normalization (the 3-part `…ui-monospace…` stack collapsed to `--font-mono` where JetBrains Mono always wins) plus the live clock; confirmed visually wide+narrow. (Per-instance `--nc` and data/runtime values like bar `width:%` were deliberately left inline, per the token-scope rule.) **Reconciliation:** removed the vestigial `.rz-grip` dead markup (4 `display:none` spans + the dead CSS rule — render-identical, the divider is the `::before`) and stripped the 4 literal `TODO.md` references from `mockup.html`'s changelog comments. **Phase 3 (DESIGN.md):** added a new **Component system** section (the `data-comp` naming convention + full registry, the `data-status` planned/undecided convention, the wired-vs-planned behavior policy, and the **Open Questions register** seeding **OQ-1**: subagent error-state/click); rewrote the token rules for the new categories + the primitive-vs-alias rule + the `--req-*` removal; documented the four previously-undocumented badge families (connector-health, config-scope, verdict, inbox-subtype) and the `req-badge`→count-chip rename; dropped the per-component inventory in favor of the gallery; and removed all 6 `TODO.md` cross-references (kept the "deferred"/"planned" intent without the external link). **Seam check (post-Phase-3):** every `dev/notes/coverage-map.md` citation of `DESIGN.md` still resolves — no section was renamed/removed (only added). **Spec retired:** `dev/notes/component-system-spec.md` now carries a RETIRED banner at its top (fully absorbed into the five files). **Verification:** Playwright MCP (served over `http://localhost`) **plus** an independent headless-Chrome render — both engines render the mockup and gallery identically (parity), at wide (1680) and narrow (1180/620) extremes, with the Inbox-tab interaction exercising the JS builders post-tagging (5 typed cards render correctly). Mechanism: the disjoint-file lanes (mockup-attributes vs tokens/styles vs gallery) ran as concurrent background subagents rather than git worktrees, since region-disjointness made isolation unnecessary; left uncommitted for review per the repo commit rule. **Maintenance contract:** `tokens.css`=every value · `styles.css`=shared component CSS (mockup+gallery) · `mockup.html`=working app surface + `data-comp`/`data-status` · `gallery.html`=visual catalog · `DESIGN.md`=rules & intent. Open: **OQ-1** stays `undecided`.

Files: design/styles.css (new), design/gallery.html (new), design/tokens.css, design/mockup.html, design/DESIGN.md, dev/notes/component-system-spec.md, DEVLOG.md

### 2026-06-29 23:58:00 — OD-02 finalized: prompt queue + dual-channel delivery (send-keys + hook-pull Inject)

Filled the **OD-02** Decision in the open-system-decisions tracker (Status → `decided`). Call: sidecar owns a per-agent **ordered** queue driven by the bridge's `generating→idle` signal, with **two delivery channels** — **send-keys-on-idle** for Now/Next/Queue (clean user turns) and a **`PostToolUse`+`Stop` HTTP-hook inbox** for **true mid-run Inject**, chosen over degrade-to-Next per the user's "full functionality in v1"; **Hold** (link-only) = payload staged for manual release into the target's Editor. Hook path validated against the hooks reference (`PostToolUse` `additionalContext` mid-turn + `Stop` `decision:block` backstop for no-tool turns); flagged build risks — tool/turn-boundary granularity, WSL2→Windows sidecar reachability, a durable ack-on-2xx inbox, and a one-agent spike to confirm mid-turn `additionalContext` on the installed Claude build. Read/think artifact — no product code changed.

Files: dev/notes/agent-qa/open-system-decisions-2026-06-29.md, DEVLOG.md

---

### 2026-06-30 00:30:00 — Subagent badge: added the `sb-error` 4th run-state (resolves OQ-1's error half)

Per user request, gave the subagent badge an **error** state, mirroring the graph status badge's 4th state. Added `.sbadge.sb-error{ background:var(--danger); color:#fff }` to `styles.css` (the exact `.nb-error` / `.db-error` solid-danger + inverse-ink treatment); a live errored subagent (`s6`) now renders red in the SCRIBE 01 fen card's expanded subagent strip in `mockup.html`; and the gallery's **Subagent Badge** group now shows **4** variants (`.sb-active` · `.sb-idle` · `.sb-pending` · `.sb-error`). `DESIGN.md` synced: the registry now reads "Subagent Badge (4 states)", the Team Graph subagent description lists active / pending / idle / **error** → `--success` / `--warning` / `--muted` / `--danger`, and **OQ-1 was narrowed** to only the subagent-badge **click** no-op (still `undecided` — the badge keeps `data-status="undecided"` for the click; the error-state half is now resolved, as the user OK'd leaving the click open). Verified in-browser (Playwright over localhost): `.sb-error` computes to `rgb(210,59,106)` / white in both the gallery specimen and the live mockup `s6`; 0 console errors. A deliberate, additive design state (not render-identical) — the only visible delta is the new red error badge.

Files: design/styles.css, design/mockup.html, design/gallery.html, design/DESIGN.md, DEVLOG.md

---

### 2026-06-30 00:35:00 — OD-03 (agent identity store) decided in the QA tracker

Filled OD-03's `Decision:` in `dev/notes/agent-qa/open-system-decisions-2026-06-29.md` and flipped its index status to `decided` (left `Recommended:` as-is per the session rule). Decision: identity = role+number+name+color+icon, **read-only in v1**; pools = **25 colors** (`--ag-*` 16→25) + a **curated 50 icons** (29→50), assigned round-robin `color = n%25` / `icon = n%50` → every (color,icon) pair unique for the first 50 agents, reused beyond 50; icon source becomes a **single source of truth** — the picker indexes `assets/icons/agents/` (167 on disk) and recolors via the sidecar `/assets/agent-icons/{name}` endpoint, retiring the mockup's hardcoded `AGENT_ICONS` array + embedded sprite sheet (converge at React-port time, OD-21). The +9 colors / +21 icons are `design/` edits held until the in-flight refactor finishes. Notes-only; no `design/` or app code touched.

Files: dev/notes/agent-qa/open-system-decisions-2026-06-29.md, DEVLOG.md

---

### 2026-06-30 00:45:00 — CLAUDE.md: added a "Design changes" behavioral rule (reuse-first + propagate-across-five-files)

Added a new **### Design changes** subsection under **Behavioral rules** in `CLAUDE.md` (just before *Verifying UI changes*), so any agent modifying the design is steered to the right context. It states the five-file ownership map (tokens.css=values · styles.css=shared CSS · mockup.html=surface + data-comp/data-status · gallery.html=catalog · DESIGN.md=rules), points to `design/DESIGN.md` as required reading, and adds two enforceable rules: **reuse before adding** (check tokens.css/styles.css for an existing token/class; never hardcode a tokenizable value; new tokens additive, never rename) and **propagate every change to all files it touches** (value→tokens.css; CSS→styles.css; new/changed component→tag in mockup + add gallery specimen + register in DESIGN.md; rule→DESIGN.md). Docs only; uncommitted.

Files: CLAUDE.md, DEVLOG.md

---

### 2026-06-29 23:15:00 — OD-13 re-scoped to the live OQ-1 (subagent click only)

Trimmed OD-13 in `dev/notes/agent-qa/open-system-decisions-2026-06-29.md` to match the now-current DESIGN OQ-1, which narrowed since the tracker was written: the subagent **error state is resolved** (`sb-error` added as the 4th run-state) and **what-info/where is settled** in DESIGN (the strip shows id + run-state colour + type/status/usage via a chevron→accordion drawer), so both are labelled resolved-for-context rather than open; **spawn/manage-in-UI** is noted as a separate backlog item (TODO B16), not this OQ. The single remaining open question is **what clicking a subagent badge does** (deliberate no-op today); Recommended trimmed to just that (click → expand the subagent detail). Index Topic updated to "Subagents — click action (OQ-1) 🎨". Re-read the tracker first (OD-02/03 now show `decided` from parallel work; no conflict). Tracker-only edit; no `design/` files touched.

Files: dev/notes/agent-qa/open-system-decisions-2026-06-29.md, DEVLOG.md

### 2026-06-30 01:00:00 — OD-09 finalized: typed Inbox detection (Error/Warning v1, Plan/Decision via hooks, spike-gated)

Filled the **OD-09** Decision in the open-system-decisions tracker (Status → `decided`). All five Inbox sections, built by detection tractability over **two raise mechanisms** — screen-state for what the bridge can see, the **OD-02 hook channel** for what it can't. **v1 = Permission (done) + Error + Warning**: Error via structural (session-gone) + no-output stall watchdog + best-effort text pattern-match, **sticky** until Retry/Dismiss (Retry needs a net-new last-command store); Warning is the visible output of **OD-10's** cap loop (Max-turns/context-% local; rate/usage subtype gated on **OD-18**). **Plan + Decision** resolved via the OD-02 hooks intercepting the agent's `ExitPlanMode`/`AskUserQuestion` **tool calls** (visible to hooks though screen-blind) — answer routed back via `updatedInput` / allow-deny the plan-exit, which also sidesteps the old plan-mode-resume block; **pursue-but-prove-first**, spike-gated with a detect-and-surface fallback if the round-trip fails. Tracker-only edit; no `design/` or product code touched.

Files: dev/notes/agent-qa/open-system-decisions-2026-06-29.md, DEVLOG.md

### 2026-06-30 01:15:00 — OD-24 added + decided: message addressing schema (source + recipients[])

Added a new entry **OD-24** to the open-system-decisions tracker (index + body; Status `decided`, Tier 1 / cross-cutting, placed after OD-23 with a heading note since it pairs with OD-01). It pins the message/event **addressing envelope**: every message carries `source` (the OD-01 `agent_id` stamp) **and** a typed `recipients[]` list — `user | <agent-id> | scratch` — **defaulting to `[user]`**; normal agent turn → `[user]`, user send → the To/Target multi-select, link fire → `[B]` (OD-04/05), scratch post → `[scratch]`. Records that `recipients` is **addressed-to (routing/From-To/direction), not visibility** (everything still shows in the operator feed), and that building the field now avoids a later migration for linking/multi-target sends. Re-read the tracker first (OD-09 now `decided` from a parallel agent; no conflict). Tracker-only edit; no `design/` or product code touched.

Files: dev/notes/agent-qa/open-system-decisions-2026-06-29.md, DEVLOG.md

### 2026-06-30 01:20:00 — OD-10 finalized: lifecycle caps = notify-only (Warning card; no auto-kill)

Filled the **OD-10** Decision in the open-system-decisions tracker (Status → `decided`), user-confirmed. v1 = **notify-only**: when an agent crosses its stored **max-turns** or **context-%** cap, the sidecar lets the turn finish then raises a **Warning** card (Continue / Raise cap / Stop) — **never auto-kills**. Build = cap storage (set on Create, editable in the Lifecycle band) + a sidecar poll-loop comparing live work-step count / context-% to the caps — the **same loop that feeds OD-09's Warning section**, not separate work. Caps are user-set per agent (no system default to decide). **Deferred post-v1:** the optional per-agent **auto-shutdown toggle** (graceful wind-down on cap-hit, TODO B19). Re-read the tracker first (OD-24 added by a parallel agent; no conflict). Tracker-only edit; no `design/` or product code touched.

Files: dev/notes/agent-qa/open-system-decisions-2026-06-29.md, DEVLOG.md

### 2026-06-30 01:30:00 — OD-10 trimmed to Warning-only (removed the deferred auto-shutdown / B19 note)

Per user direction, stripped **OD-10** of all forward-looking / auto-kill references — the deferred per-agent auto-shutdown toggle and its `TODO B19` citation are gone from the Decided / Open / Source / Recommended / Decision lines. OD-10 now reads **Warning-only**: a cap-cross raises a Warning card and the run continues until the user chooses; nothing about killing. Root cause: that note had leaked in from `design/TODO.md` item **B19**, which is **reference-only** per TODO's top-of-file rule (backlog A–D must not be treated as scoped unless the human points at it). Flagged for follow-up: the tracker's **Authority line** cites `design/TODO.md`, and several entries are backlog-sourced (OD-06/08/13/15/19/21/22/23) — pending user approval to drop TODO from Authority + audit those + archive the superseded v5 QA doc. Tracker-only edit; no `design/` or product code touched.

Files: dev/notes/agent-qa/open-system-decisions-2026-06-29.md, DEVLOG.md

### 2026-06-30 01:45:00 — QA tracker de-TODO'd: removed backlog harvest, renumbered, archived v5

Followed through on the approved cleanup (root cause: `design/TODO.md` is a reference-only backlog that should never have been mined for decisions). **(1)** Dropped `design/TODO.md` from the tracker's **Authority line** and added an explicit guard — *"`design/TODO.md` is NOT a source; never harvest decisions from it."* **(2)** Deleted the two wholly-backlog entries — **OD-22** (product-scope research, TODO §C) and **OD-23** (fresh design tweaks, TODO Inbox). **(3)** Renumbered **OD-24** (message addressing) → **OD-22** so IDs run 1–22 with no gap. **(4)** Stripped TODO citations from OD-06/08/13/15/19/21 and **re-sourced OD-08** (its only source was TODO C7/B17 → now "follows OD-04/05; coverage-map"). Also **archived** the superseded **v5 QA doc** to `archive/agent-qa/` (git mv) and repointed the tracker's one citation. History note: this DEVLOG's earlier "OD-24" references now map to the renumbered **OD-22** (append-only entries left intact). Tracker edit + a doc move; no `design/` or product code touched.

Files: dev/notes/agent-qa/open-system-decisions-2026-06-29.md, archive/agent-qa/ui-behavior-questions-2026-06-26-v5.md (moved from dev/notes/agent-qa/), DEVLOG.md

### 2026-06-30 02:00:00 — OD-11 finalized: run-strip progress = agent-published per-run checklist (barber-pole floor)

Filled the **OD-11** Decision (Status → `decided`). Run-strip % is resolved by **agent self-report**, not an outside estimate: a **system-prompt mandate** has each agent **publish a short ordered checklist of its major operations up front** and mark items done as it goes (trivial runs declare ~1 step, keeping the cost proportionate). The sidecar reads the checklist from the transcript (rides on the OD-01 stream + OD-02 parsing — no new channel) and renders **done ÷ total** as a **segmented bar with a vertical separator per step**; the current in-progress item doubles as the **OD-12 marquee** text (one signal, two panels). **Barber-pole stays the honest floor** for runs with no checklist. **Rejected** a background LLM estimator (heavy input-token cost re-reading large/growing transcripts × cadence × fleet, and less informed than the agent = worse number); a tool-count-vs-baseline heuristic is allowed only as an optional noisy fallback; turns-used ÷ max-turns cap explicitly not used (that's distance to the safety limit, not completion). Caveat recorded: the denominator can grow mid-run so the bar can step backward (bounded, accepted). Tracker-only edit; no `design/` or product code touched.

Files: dev/notes/agent-qa/open-system-decisions-2026-06-29.md, DEVLOG.md

### 2026-06-30 02:15:00 — OD-04 + OD-05 finalized (reply-to fire; trigger vocabulary)

Filled both Decisions (Status → `decided`), user-confirmed. **OD-04 (fire contract):** a link fires on the **reply-to** model — when the source finishes the turn answering a linked peer's inbound message (detected at the `generating→idle` boundary, OD-02), the sidecar routes *that turn's output* back to the inbound's source (`recipients:[peer]`, OD-22) by enqueuing it on the peer's inbound queue. A fire = completion-of-a-reply, not a blind broadcast on idle; strict one-inbound-in-flight per agent keeps the inbound↔reply pairing unambiguous; no handoff marker needed (Hold covers human-gated sends). **OD-05 (triggers):** ship the full vocabulary **Now · Next · Queue · Inject · Hold**, default **Queue**; Inject has no safe bridge injection point so it transparently degrades to Next/Queue; Hold = the human review-gate; Send-from-Prompt reuses the vocabulary minus Hold. Also renamed the linking relationship **"Interactive" → "Direct messaging"** per user. **Concurrency note:** a parallel agent renumbered the tracker mid-edit (old OD-24 message-addressing → **OD-22**, deleted old 22/23); re-verified my edits landed on the right entries and **fixed OD-04's now-stale cross-refs** (OD-24→OD-22; dropped a dangling OD-25 ref — the serialized reply-to model is still pending its own entry). Tracker-only edit; no `design/` or product code touched.

Files: dev/notes/agent-qa/open-system-decisions-2026-06-29.md, DEVLOG.md

### 2026-06-30 02:30:00 — OD-12 finalized + OD-11 decoupled (marquee = transcript-output liveness)

Filled the **OD-12** Decision (Status → `decided`), user-clarified: the per-card **marquee is just a low-fidelity scrolling tail of the agent's transcript output** — a pure **liveness** signal ("it's running and moving"), **not** an audit surface (auditing lives in the Messages feed). Source = the agent's slice of the OD-01 stream; **no new backend**; raw recent output by default, lightly-derived activity verbs ("→ Read X") optional polish; goes quiet / holds last line when idle. Also **amended the already-decided OD-11**: removed the over-coupling that piped the checklist's current step into the marquee — a discrete step label doesn't suit a scrolling ticker, so the current step now **labels the progress bar** and the marquee stays its own continuous output stream. Tracker-only edit; no `design/` or product code touched.

Files: dev/notes/agent-qa/open-system-decisions-2026-06-29.md, DEVLOG.md

### 2026-06-30 02:45:00 — OD-06 reframed (relationship model) + OD-07 finalized (Exchanges, default 25)

**OD-06:** reframed from "Link payload" to the **link relationship model + config drawer** (Status → `decided`). Payload field removed; what's sent is *derived* from the relationship. Drawer order top→bottom: **(1) agent pair + direction** (two single-select agent dropdowns + an A→B/B→A/A↔B direction arrow between them, static for now); **(2) Relationship** — a **multi-select** (both allowed): *Direct messaging* = reply-to (OD-04), *Shared context* = content-type multi-select filter (reuses the Messages Thoughts/Read/Write/Bash/Diffs/Meta taxonomy) + "share all prior context" backfill toggle (default off, ideally summarized), delivered **piggybacked** on the receiver's next prompt (user or agent) with a per-(source→target) **watermark** sharing only the delta since last share (also dedups across both channels); **(3) Trigger** (OD-05); **(4) End After** (OD-07); **(5) action strip**. Dropped Message/Transcript/Manual. **OD-07:** finalized (Status → `decided`) — End After is counted in **Exchanges** (a round-trip = one message each direction), explicitly **not** internal agentic turns/steps (lifecycle scope, OD-10); two independent caps (Exchanges + Tokens), **default 25 exchanges**, strict one-in-flight A↔B alternation as backstop. Established the vocabulary split **turn/step = internal agentic iteration · exchange = inter-agent round-trip** (matches DESIGN's existing "End After bounds an inter-agent exchange"). Re-read tracker first (OD-12 decided + OD-11 amended by a parallel agent; no conflict). Tracker-only edit; no `design/` or product code touched.

Files: dev/notes/agent-qa/open-system-decisions-2026-06-29.md, DEVLOG.md

### 2026-06-30 03:00:00 — OD-08 finalized: link tracking = grouped list in Link Config (no graph edges yet)

Filled the **OD-08** Decision (Status → `decided`), user-scoped to "keep it simple, basic functionality." **No on-graph edges and no per-card link badges for now** (both deferred — no room on the cards). All link tracking lives in the **Link Config panel**: a **new section at the bottom** lists **all links grouped by agent** (agent = group header); since a link joins two agents, **each link appears under both agents' groups** (deliberate double-listing). Each entry shows the **other agent** + a **direction arrow relative to that group's agent** — → to / ← from / ↔ both — reusing the same arrow indicator as the agent-pair row at the top (OD-06). Panel now reads: agent-pair+direction → Relationship → Trigger → End After → action strip → all-links list. Noted as a non-v1 extension: click a list entry to load it into the fields above (master/detail edit). This closes Tier 2 except the still-pending serialized reply-to entry. Re-read tracker first (no parallel conflict). Tracker-only edit; no `design/` or product code touched.

Files: dev/notes/agent-qa/open-system-decisions-2026-06-29.md, DEVLOG.md

---

### 2026-06-30 03:05:00 — OD-13 expanded + finalized: full subagent integration model

Expanded **OD-13** from the lone OQ-1 "what does the badge click do" into the full **subagent integration model** (heading + index topic retitled "Subagent integration model"; Status → `decided`; `Recommended:`/`Confidence:` left verbatim per the session rule). Core: a subagent is a **sub-identity of its parent** (`coder-01 › A2`) riding OD-01 (sender) + OD-22 (addressing), so Messages/filter/identity inherit it with no new subsystem. The Decision settles, with the user: **(1)** sidecar ingests each subagent's own `subagents/agent-<id>.jsonl` transcript (same parser, tagged under parent) — **real-time, not deferred**, via folder-watch + tail joined to its spawn by first-message match, reconciled on result; **(2)** naming = **group-letter + member** (`A2`, no `s` prefix), group = a parent run that spawned subagents; **(3)** badge click = focus parent → open Details Subagents accordion to that row **and** filter Messages to it (replaces the `stopPropagation` no-op); **(4)** a read-only **Subagents accordion** at the bottom of Agent→Details (below Timeline, above footer) with a total-count badge, rows grouped by run (type · task · status · usage · model · transcript link); **(5)** nested 2-level From/To filter (sender-side only — subagents filterable everywhere, inert where N/A, **never** in the compose-To); **(6)** Messages shows subagent events nested under parent (always Received), with a collapse-chatter fast-follow. Out of v1: subagent create/config; Scratch/Inbox treatment. 🎨 design-layer edits (badge relabel, nested-filter tree, Details accordion) wait on the refactor + per-item approval. Grounded against `derive_subagents` ([sidecar/drivers/bridge.py](sidecar/drivers/bridge.py)). Re-scanned tracker first (other agents retired; no conflict). Tracker-only edit; no `design/` or product code touched.

Files: dev/notes/agent-qa/open-system-decisions-2026-06-29.md, DEVLOG.md

---

### 2026-06-30 03:30:00 — gallery refactor: mockup.html data-comp/data-status tagging (contract §9)

First build step of the gallery states-catalog refactor (contract at `.scratch/component-refactor/contract.md`): tagged the §9 component roots in `mockup.html` that lacked `data-comp` — ~40 static-markup + JS-builder roots (e.g. `settings-gear`, `model-selector`, `agent-tile`, `edit-lock`, `text-input`, `console-feed`/`-runbar`/`command-palette`, `node-subagents`, `link-drawer`, `inbox-section`, `format-popover`, `hover-card`, `markdown-row`, `message-rail-row`, `msg-block`, etc.), adding `data-status="planned"`/`"undecided"` where the contract marks a root dormant. **Attribute-only edits**: every changed line inserts only `data-comp`/`data-status` into existing markup; the two `hover-card` roots are `createElement`-built so they get a `setAttribute('data-comp','hover-card')` (same attribute, runtime). Adversarial-verified: `styles.css` + `tokens.css` byte-unchanged (no diff); no `[data-comp]`/`[data-status]` selector exists in `styles.css`, so the added attributes cannot affect rendering. Not yet tagged (no live markup instance — CSS-only): `comment-split` (`.cmt-ctl`), `verdict-popover` (`.vpop`), `verdict-chip` (`.vchip`). Remaining contract work (gallery.html states-catalog rebuild, DESIGN.md registry + §6/§10 reconciliations) is a separate step.

Files: design/mockup.html, DEVLOG.md

---

### 2026-06-30 03:35:00 — OD-14 finalized: "Always allow" fully removed (binary approve/deny)

Filled **OD-14** Decision (Status → `decided`; index retitled + 🎨; `Recommended:`/`Confidence:` left verbatim per the session rule). Per user: **fully remove "Always allow"** from the UI and all present/future implementation — permissions are a clean **binary Approve / Deny** (+ Reply); drop the button from the Inbox Permission card and build **no** always-allow rule-persistence path (a persisted "always" rule is a silent auto-approve surface we don't want). Carried the unchanged reality so the entry is self-sufficient: permission **mode** stays **launch-only** (mid-run change BLOCKED, not pursued); per-agent scoping is **deny-based** (`--allowedTools` ignored under bypass — a claude bug). Also corrected the OD-09 cross-reference ("Always allow" now *removed*, was "deferred"). 🎨 the Permission-card button removal is a `design/` edit held until the refactor + approval. Re-scanned tracker first (no conflict). Tracker-only edit; no `design/` or product code touched.

Files: dev/notes/agent-qa/open-system-decisions-2026-06-29.md, DEVLOG.md

---

### 2026-06-30 06:10:00 — gallery refactor: states-catalog rebuild + DESIGN.md registry/rules sync (contract §2–§10)

Completed the gallery states-catalog refactor (contract at `.scratch/component-refactor/contract.md`, building on the 03:30 mockup-tagging step). **`gallery.html` rebuilt** from a one-specimen-per-component catalog into a **STATIC STATES CATALOG**: 113 cards across the five contract groups (Primitives · **Form fields** (new #fields group) · Badge catalog · Inbox cards · Composites), each reusable component + basic building block shown **once per visual state** with the precise class combo labeled (the `gx-` scaffold reused verbatim; head/sprite/closing-script carried 1:1). Added a **gallery-only `gx-force-*` helper set** (`-hover`/`-focus`/`-disabled`) in the page's own `<style>` that mirrors `styles.css`'s live `:hover`/`:focus`/`:disabled` token-deltas so a static specimen renders the interaction states identically — the two `rgba(0,24,88,…)`/`rgba(210,59,106,…)` tints are copied verbatim from the live rules (not minted as tokens); **no component CSS copied in, no new tokens**. Applied the orchestrator's locked decisions: kept the new #fields group; catalogued composite-internal primitives (`node-subagents`, `markdown-row`, `message-rail-row`, `msg-block`) as their own cards; catalogued `inbox-section` (undecided) but **EXCLUDED `subbar`** (removed its gallery card **and** untagged `data-comp="subbar"` in `mockup.html` — now treated as excluded scaffolding); catalogued `settings-gear`; error-inbox-card shows the collapse/select state trio, the other four inbox cards expanded-only with a "shell behaviour identical" note; added `link-edges` (planned) + `link-drawer` (planned) cards. **`DESIGN.md`**: rewrote the gallery rule as a states-catalog (group order + the ordered **state vocabulary** + the `gx-force-*` forced-state explanation), and replaced the registry with the full §5 slug set grouped by the five sections + `link-edges`, plus a new **excluded-scaffolding** subsection (incl. `subbar`, the title bar, panel shells, the Settings/Console view hosts). Adversarial-verified: **ZERO** `TODO.md` references in any of the five design files; `styles.css` + `tokens.css` **byte-unchanged** (no git diff); the gallery `<style>` carries only `gx-`-prefixed page/scaffold + `gx-force-*` rules (no shared component CSS, no hardcoded hex); every gallery slug is registered in `DESIGN.md` and the mockup↔gallery slug sets reconcile (the only gallery-only slugs are `comment-split`/`verdict-chip`/`verdict-popover` — no live root to tag). UI-verified in a served browser (localhost): rendered all five sections, drove forced hover/focus/disabled + open-popover states (computed styles match the live tokens), confirmed **zero horizontal overflow at the 550px narrow extreme** and a clean wide pass, 0 console errors, all 295 lucide icons rendered. *(The `design/TODO.md` working-tree change in this commit is a pre-existing human backlog edit, not part of this task — left untouched.)*

Files: design/gallery.html, design/mockup.html, design/DESIGN.md, DEVLOG.md

---

### 2026-06-30 10:35:00 — gallery: filled 13 minor state-coverage gaps (specimens + callouts), additive only

Remediated missing visual states in `gallery.html` (states catalog) without touching any other file. **Added 10 new specimens**: `split-menu--right` (right-anchored split menu), `exp-menu--right` (right-anchored export menu), `picker-pop.open.up` (color-picker upward), `.node` default/unselected (placed before the `.selected` representative) + `.node.subs-open` (drawer-grown card, real specimen — card height grows past the square, 5-badge drawer open), `.doc-edit` raw-edit textarea, decision-inbox **no-pick default** (disabled Approve, placed before the picked variant — picked variant kept), `.fmt-menu.up.left` + `.fmt-reset:hover` (forced), `.docnav-add:hover` (forced), `.aglist.aglist-scroll` (scrollable, 6 rows over a 120px cap). **Added 3 gx-callouts** (toast/jump-pill pattern) for invisible-default states: `.ver-panel` closed (`display:none`), `.feed-overlay` closed (off-screen/`opacity:0`), `#hcpop` hidden (`opacity:0`). One supporting additive tweak: extended the gallery-only `gx-force-hover` surface-3 selector list to include `.docnav-add` so its forced-hover renders the live `--surface-3` delta. All classes verified against `styles.css` (no invented classes); `data-comp` count unchanged at 112 (stays on the representative specimen only). **Browser-verified** (served localhost, headed): computed-style audit of all 13 confirms each renders the intended CSS (right-anchored `left:auto`; subs-open `aspect-ratio:auto` h≈180px; doc-edit = mono textarea; fmt-reset hover = `--link-hover`; docnav-add hover = `--surface-3`; aglist-scroll `overflow-y:auto` + actually scrollable); decision card order correct (no-pick first, Approve disabled); **zero horizontal overflow at the 700px narrow extreme**, no page h-scroll, only console error is a pre-existing favicon 404. (Edits are strictly additive — no prior specimen/callout removed; `git diff` vs HEAD shows large churn only because HEAD predates the uncommitted gallery rebuild this builds on.)

Files: design/gallery.html, DEVLOG.md

---

### 2026-06-30 10:40:00 — OD-23 added (storage & scoping model); OD-15 + OD-17 decided against it; OD-18 storage piece resolved

Captured the storage/scoping model the user settled in dev-qa-1c as a new cross-cutting **OD-23 · Storage & scoping model** (Tier 1; index row + body) and resolved the three items that were blocked on it. **OD-23 Decision:** one rule — dashboard data lives with the dashboard, project data with the project, teams are reusable and live with the dashboard. Three homes: 🏠 **dashboard** (own repo + the `sidecar/runtime/` store — per-agent identity, sessions, saved **Setups**/rosters; project-agnostic); 📁 **project** (its repo = the agents' `cwd`; all docs **plus** the scratchpad + plan-review side-store under `<project>/.awl/`, WSL-reachable, travels with the code); 👥 **Setup** = roster only (agents/roles/models/identities/links), no docs/project baked in, loaded onto any project. Claude's own `~/.claude` / `<project>/.claude` config is **surfaced, not owned**. Code keys off each agent's `cwd`, never a fixed path; dev-time footnote — projects live under a gitignored **`projects/`** dir now and graduate to their own repos at release (just a different `cwd`). **OD-15 (Library) → decided:** v1 = read+render Plans/Documents from the project dir + a filename-keyed **plan-review side-store** at `<project>/.awl/plan-reviews.json` (carries plan↔agent owner); deferred write-back/Assets/rich-plans; plan-approve→resume still bridge-**BLOCKED** (OD-09 hook path may unblock later); 🎨 the panel UI waits on the refactor, the endpoints are free now. **OD-17 (scratchpad) → decided:** confirmed v1 write-in/read-out only (no auto-read, QA Q22), materialized at `<project>/.awl/scratchpad.md`. **OD-18:** storage piece resolved (Setups → dashboard runtime store); **gated writes / account band / usage-limits live-fetch stay open**. `Recommended:`/`Confidence:` left verbatim per the session rule; implementation (creating `projects/`, the `.gitignore` add, endpoints) held — tracker-only paper edit, no `design/` or product code touched. Re-scanned the tracker first (no conflict; the refactor agent is active on `design/` only).

Files: dev/notes/agent-qa/open-system-decisions-2026-06-29.md, DEVLOG.md

---

### 2026-06-30 11:00:00 — gallery refactor: closing doc sync + independent verification (capstone)

Finishing touches + an independent verification pass over the whole states-catalog build. **CLAUDE.md** "Design changes" rule updated to the states-catalog model — `gallery.html` is now described as the static **states catalog** (every component shown once *per visual state*; behaviour lives in the mockup), and the propagate bullet now says "add a specimen *per state*". **DESIGN.md** gained a "Gallery-only (no mockup root)" note flagging the 3 CSS-only slugs (`comment-split`, `verdict-chip`, `verdict-popover`) that carry no `data-comp` in the mockup. **Independent verification:** a 6-agent read-only audit checked all 113 cards against the build contract → 0 high / 3 med / 14 low defects, all remediated (the 13 gaps logged at 10:35 + these two doc notes); confirmed no fabricated markup, no dropped baseline specimens, correct group placement, a complete DESIGN.md registry, zero `TODO.md` leaks, and `styles.css`/`tokens.css` byte-unchanged. **Own browser pass** (served localhost, narrow 720 + wide 1600): 113 cards across 5 sections render clean; computed-style audit confirms the forced-state helpers apply (hover `translate(2px,2px)`, disabled dim, focus ring), right-anchored menus resolve `left:auto`, the open-upward picker is visible, all 4 agent-node-card states present incl. the grown `subs-open`; **zero horizontal overflow**, no card overflows its container, console noise is only the pre-existing Tailwind-CDN notice + favicon 404. Net: the gallery is a complete, verified states catalog (113 components across Primitives · Form fields · Badges · Inbox · Composites), mockup tagging is attribute-only (render-identity preserved), and all five `design/` files + CLAUDE.md are in sync.

Files: CLAUDE.md, design/DESIGN.md, DEVLOG.md

---

### 2026-06-30 11:05:00 — OD-16 finalized: full prompt-composition set (no cut; solve the plumbing)

Filled **OD-16** Decision (Status → `decided`; index retitled "Prompt extras — full mockup set, no cut (solve plumbing)" + 🎨; `Recommended:`/`Confidence:` left verbatim per the session rule). Per the user's reframe — *the tracker records what we want, including things that still need plumbing solved, not just the safe subset* — OD-16 now captures the **entire** mockup prompt-composition surface with **nothing deferred**, each item tagged with the plumbing it requires: Editor + the `embed`/`template`/`citation` inserted-block primitive; **Embed** (write path into the Editor); **Attach** (the load-bearing solve = file materialization + Windows↔WSL2 path normalization, `mcp_sync` as precedent); **Citations** (built with Attach, delete-cascade); **Templates** (storage = the OD-23 dashboard store, reusable/project-agnostic); **Revise** + **Summarize** (the `sdk`-driver utility-LLM passes — the SDK support the user OK'd wiring); **Send-as-agent** (rides OD-22 source/recipients via the OD-02 queue); **response-format preamble** popover; plus voice mic, History/Retry, and the merged Export control. Build order framed as **dependencies, not cuts** — Attach's path-normalization and the sdk utility-LLM pass are the two solves that gate the rest. 🎨 the Editor/blocks/Templates/attach-strip/Export-control UI wait on the refactor + per-item approval; the backend plumbing is free to build now. Grounded against `design/mockup.html` (Prompts panel) + `design/DESIGN.md`. Re-scanned the tracker first (no conflict). Tracker-only edit; no `design/` or product code touched.

Files: dev/notes/agent-qa/open-system-decisions-2026-06-29.md, DEVLOG.md

---

### 2026-06-30 11:10:00 — OD-17 corrected: scratchpad is an always-live auto-read channel (not explicit-send-only)

**Reversed** OD-17's earlier read policy at the user's direction. The prior fill (no-auto-read / write-in-read-out, from QA Q22) was wrong for the product intent — the scratchpad is meant to be the team's **always-current shared comms channel**, so **every agent auto-reads it**. Kept the `Decided:`/`Recommended:`/`Confidence:` lines **verbatim as the pre-correction record** (per the leave-`Recommended`-as-is rule) and added a visible **Correction note**; rewrote the **Decision** + retitled the index topic ("always-live auto-read channel"; Status stays `decided`, Kind `DECIDED‑UNBUILT`). Corrected model: delivered as a **per-agent delta off a read watermark** (same machinery as OD-06 shared-context) so context stays bounded — agents see only what's new since their pointer; old history lives in their own transcript. Per the user's calls: **(b) live mid-run push** via the **OD-02 inject hook** (PostToolUse `additionalContext`, passive/non-triggering) so a running agent gets an **early collision signal** while working — with a **fallback to start-of-run injection** if the spike-gated hook doesn't prove out; **idle agents catch up at run-start** (push only reaches running agents); **first run = full board** snapshot; **include the agent's own posts** (positional context, no echo since reads don't post); **no delta cap** (full diff, not managed in v1). Write side unchanged (append API + attribution; `recipients:[scratch]` per OD-22; storage `<project>/.awl/scratchpad.md` per OD-23). Re-scanned the tracker first (no conflict). Tracker-only edit; no `design/` or product code touched.

Files: dev/notes/agent-qa/open-system-decisions-2026-06-29.md, DEVLOG.md

---

### 2026-06-30 11:15:00 — OD-19 finalized: Retire + permanent Delete both in v1 (hard-wipe private, tombstone shared)

Filled **OD-19** Decision (Status → `decided`; index retitled "Retire + Delete both in v1 (hard-wipe private, tombstone shared)"; `Recommended:`/`Confidence:` left verbatim per the session rule — the Decision opens by noting it **changes** the prior "Retire only" scope). Per the user, **both tiers ship in v1**: **Retire** = soft/reversible (stop + archive config/transcript), **Delete** = hard/irreversible under one rule — **wipe the agent's private footprint, tombstone everything shared.** The six calls: **(1)** scope-b full on-disk wipe — `runtime_store.remove_record` + `bridge.close`(`kill-session`) + delete the agent's CC transcript **and** subagent transcripts (deliberately destroys CC's own JSONLs — what distinguishes Delete from Retire); **(2)** Delete from **any state** (a running agent is interrupted+closed first, no forced two-step); **(3)** a **plain confirm** dialog (not type-to-confirm); **(4/5)** **tombstone everything shared** — scratchpad posts (OD-17), feed events/messages (OD-01), and link history (OD-08) stay attributed to the deleted identity and marked inactive, so Delete never rewrites the shared record or corrupts peers' watermarks/stream; link edges become inactive tombstones, not silent removals; the agent's own transient queue/inbox (OD-02/09) is cleared as moot; **(6)** **no number recycling** — the identity number is permanently retired (monotonic) so old `coder-03` history never collides with a future agent (color/icon still cycle per OD-03). Mechanics already exist (`remove_record`, `bridge.close`), so this is policy not new infra. 🎨 the existing Retire/Delete footer's wording/confirm tweak waits on the refactor + approval; the wipe/tombstone backend is free now. Grounded against `sidecar/runtime_store.py` + `bridge/bridge.py` (`close`/`kill-session`). Re-scanned the tracker first (no conflict). Tracker-only edit; no `design/` or product code touched.

Files: dev/notes/agent-qa/open-system-decisions-2026-06-29.md, DEVLOG.md

---

### 2026-06-30 11:20:00 — OD-18 finalized: Settings fully interactive (write everything feasible) + account & usage bands in

Filled **OD-18** Decision (Status → `decided`; index retitled "Settings — write everything feasible + account & usage bands" + 🎨; `Recommended:`/`Confidence:` left verbatim per the session rule; the earlier Storage line kept). Per the user: **make the Settings surface fully interactive — expose a write for everything the engine can actually set, read-display the rest.** Calls: **(1)** the Config · MCP · Plugins tabs become **editable** (toggles / add-remove-enable / config edits to the real `~/.claude` + `<project>/.claude` files), and **per-agent scoping** (MCP/plugins/tools/permissions) is **surfaced in the Create form / Agent panel** (today accepted-but-unexposed, coverage-map B6/G7) — all **confirm-gated** (plain confirm, heavier for global/destructive). **(2) account band IN** (email/org/plan from local creds, "signed out" if absent). **(3) usage-limits band IN** (session/weekly % + resets, fetched **live from the API**, on open + light poll, **graceful "unavailable"** fallback so the API dependency can't break the screen). Baked in the honest **feasibility boundary**: mid-run permission-mode stays engine-BLOCKED (OD-14, launch-only); per-agent MCP/model/plugins take effect at launch/restart (live where the engine allows, at-launch where not); tool scoping is deny-based (`--allowedTools` ignored under bypass) — anything not live-settable is shown as launch-time/blocked, never a fake-live toggle. Setups storage already resolved → dashboard runtime store (OD-23). 🎨 the write controls + two bands + per-agent Create-form controls are `design/` edits held until the refactor + approval; the endpoints are backend, free now. Grounded against the Settings read-only state (coverage-map A2/B6/G7) + OD-14. Re-scanned the tracker first (no conflict). Tracker-only edit; no `design/` or product code touched.

Files: dev/notes/agent-qa/open-system-decisions-2026-06-29.md, DEVLOG.md

---

### 2026-06-30 11:25:00 — OD-20 finalized: adopt the Console as already designed; only backend wiring remains

Filled **OD-20** Decision (Status → `decided`; index retitled "Console — adopt design (per-agent tab + slash-runner IN); wire backend" + 🎨; `Recommended:`/`Confidence:` left verbatim per the session rule). Checked the mockup + DESIGN against OD-20's "open" questions and found **the design already settled both** — the OD-20 framing was stale. **Surface:** a per-agent Console **tab** in the Agent panel (single focused agent), with an **Expand → partial step-into** covering left+middle columns only (right column stays visible) — a reasoned choice against modal/always-on, distinct from Settings' full-body step-into; feed faithfully mimics a real CC terminal via a self-contained `--term-*` palette (documented `tokens.css` exception). **Slash-command runner: IN** (first-class, not deferred) — a complete catalog grouped into 6 clusters with filter, pick→stage→run-on-focused-agent→output-in-feed; commands with a home elsewhere still listed, tagged also-available-there. The mockup already tags the run bar `data-comp="console-runbar" data-status="planned"` (`runConsoleCmd` is a mock over a static `CON_FEED`), so the **only residue is backend, not a product call**: (1) wire the live raw-terminal feed (`capture-pane`/`scrollback` already proven at the bridge → connect to `console-feed`); (2) slash-command send/route via the bridge's existing `send`/`keys` + `capture-pane`, with the **interactive-command caveat** (`/model`, `/clear` drop into a sub-prompt — the runner must handle the follow-on, not blind-send). 🎨 nothing new; planned→built waits on the refactor + approval, the feed/route backend is free now. Grounded against `design/DESIGN.md` "Console" + `design/mockup.html` (console-feed / command-palette / console-runbar). Re-scanned the tracker first (no conflict). Tracker-only edit; no `design/` or product code touched.

Files: dev/notes/agent-qa/open-system-decisions-2026-06-29.md, DEVLOG.md

---

### 2026-06-30 11:30:00 — OD-21 parked → QA decision tracker fully addressed (23/23)

Resolved the last open item, **OD-21** (React port + library choice), as a **park** rather than deleting it (Status → `decided`; index retitled "React port + library choice — PARKED (revisit at churn→zero)"; `Recommended:`/`Confidence:` left verbatim). Decision: **not yet** — defer the React port until **design churn reaches zero**, which per the user is **after** the QA-doc UI changes are integrated into the mockup and the component-system refactor lands (churn is not there yet). The coupled **port-timing** + **library-commitment** (neobrutalism.dev / shadcn vs. the hand-rolled `tokens.css`/`styles.css` system) calls are a dedicated future discussion gated on a **translation spike** + the user's maintenance preference; nothing to build now — it's the convergence milestone where the parallel frontend/backend tracks meet, so it stays parked until both are stable. Kept (not deleted) so the item + trigger aren't lost and OD-22/OD-23 cross-references stay intact. **With this, all 23 OD items are addressed** (22 decided + OD-21 parked). Context: the user's next steps are to integrate the QA-doc 🎨 UI changes into the mockup once the refactor finishes, then build the confirmed backend (bare-minimum UI as needed) — the QA doc's 🎨-vs-backend tagging is the seam that lets those two tracks proceed in parallel. Re-scanned the tracker first (no conflict). Tracker-only edit; no `design/` or product code touched.

Files: dev/notes/agent-qa/open-system-decisions-2026-06-29.md, DEVLOG.md

---

### 2026-06-30 12:10:00 — design: behavior.js extracted + gallery rebuilt as an INTERACTIVE catalog (5→6-file system)

Reworked the gallery from a static states-catalog (which had real defects: force-opened menus overlapping and spilling into neighbouring cards, a marquee + tickers bleeding past their cards, progress bars rendering as bare bullets, ragged grid whitespace) into an **interactive catalog**, and split the shared **behavior layer** out so it can't drift.

- **New `design/behavior.js`** — extracted **byte-exact** (deterministic slice script) from `mockup.html`'s inline behavior block (1828 lines of interaction logic), now the **single source of truth** for component behavior, loaded by **both** the mockup and the gallery. The mockup's inline `<script>` collapsed to `<script src="behavior.js">` (3711→1882 lines); the **only** semantic change is a one-line guard so `boot()` no-ops when there's no `.app` root (inert on the gallery). Mockup verified **pixel-identical** to its pre-extraction baseline, 0 console errors, all 12 behavior fns live, split-menu/tab-switch still work. `tokens.css` config kept inline (config, not behavior).
- **Rebuilt `design/gallery.html`** (113 cards, 5 sections) — every operable specimen is now the **real, live component** driven by the shared `behavior.js`: variants shown side-by-side, controls you actually click/open (menus open *contained* and dismiss on outside-click, not frozen-open), inbox cards shown expanded, sub-popovers shown open+contained, non-interactive data-states (disabled/empty/error) as labelled instances. Bootstrapped by harvesting each `data-comp` instance's real markup out of the live mockup DOM + the curated variant specimens (generator kept in `.scratch/component-refactor/`, a one-time bootstrap; the gallery is hand-maintainable going forward). **Verified in-browser**: 0 console errors, **0 empty cards, 0 spill/overflow**, interactivity confirmed (split/segmented/source/tab), responsive at 720px and 1920px extremes.
- **Design system 5→6 files** (added `behavior.js`). Propagated: `CLAUDE.md` (folder-map `design/` row + the "Design changes" rule, five→six + the behavior-layer propagation line) and `DESIGN.md` (read-once file list, the Component-system governance intro, the gallery section rewritten static→interactive, and the obsolete `gx-force-*` paragraph replaced with the `behavior.js`-share model).

Files: design/behavior.js (new), design/mockup.html, design/gallery.html, design/DESIGN.md, CLAUDE.md, DEVLOG.md

---

### 2026-06-30 14:05:00 — dev: two integration prompts derived from the OD tracker (backend + design streams)

Reviewed the four `dev-qa-1a..1d` QA transcripts and the 23-item decision tracker (`dev/notes/agent-qa/open-system-decisions-2026-06-29.md`, all ODs resolved), compared it against the current backend (`sidecar/` + `bridge/`, via `coverage-map.md`) and design state, and split the implied work into two self-contained ultracode build prompts written to `dev/prompts/`. **Backend** (`backend-decision-integration.md`): foundation-first (OD-01/02/22/23) with the OD-02 hook spike gated first, the linking chain, then Tier-3 features; excludes parked OD-21 and the bridge-blocked pieces; sdk carve-out for OD-16 Revise/Summarize. **Frontend/design** (`design-stream-finisher.md`): the eight 🎨 items across the six-file design system (incl. `behavior.js` + the interactive-catalog gallery), working the live tree (no worktrees, no archive). The two prompts run concurrently, are disjoint by file set (sidecar+bridge vs design/), and coordinate only on appended `DEVLOG.md` + the OD-03 `--ag-*` color names. Derived via a 9-agent workflow (map → synthesize → draft → adversarial critique); the critique caught a stale five-file framing, corrected against ground truth.

Files: dev/prompts/backend-decision-integration.md (new), dev/prompts/design-stream-finisher.md (new), DEVLOG.md

---

### 2026-06-30 15:30:00 — backend: OD-23 storage homes + OD-03 identity finish (foundation tier-1, hermetic)

First backend slice of `dev/prompts/backend-decision-integration.md` — the two small, independent foundation items, TDD with hermetic tests, no `design/` touched (the 🎨 stream owns it).

- **OD-23 storage & scoping homes** — new `sidecar/storage.py`: the one canonical model for *where data lives*, three homes all keyed off each agent's `cwd` (never a fixed path). 🏠 Dashboard store = `runtime_store.runtime_dir()` (Setups/templates), exposed as a public accessor so locations can't diverge; 📁 Project home = `<project>/.awl/` (scratchpad OD-17, plan-reviews OD-15), WSL-reachable via the proven `bridge.paths.win_to_wsl` (reused, with a local fallback so the module always imports); 👥 Setup = a roster in the dashboard store. The consumers (OD-15/17/18/16) import these resolvers. Added public `runtime_store.runtime_dir()` (single source of truth).
- **OD-03 identity finish** — `sidecar/identity.py`: curated **50 icons** from the 167 on disk (distinct/recognizable, category-interleaved) as the auto-assignment pool; round-robin now `icon = n mod 50`, `color = n mod len(AG_COLORS)` (already ready for `mod 25` — the +9 color names/values are the design stream's; the cross-stream seam is documented, not invented). Full 167 set kept for the manual picker/recolor endpoint.
- **Verified:** 108 hermetic tests green (`tests/test_storage_unit.py` new, 14; `tests/test_sidecar_unit.py` updated to the curated-icon contract + curated-pool drift guards; existing bridge unit tests unaffected). No live env needed. DEVLOG rotation (>700 lines) remains deferred to avoid clobbering the concurrent design-stream appends.

Files: sidecar/storage.py (new), sidecar/identity.py, sidecar/runtime_store.py, tests/test_storage_unit.py (new), tests/test_sidecar_unit.py, DEVLOG.md

---

