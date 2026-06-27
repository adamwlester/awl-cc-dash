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
