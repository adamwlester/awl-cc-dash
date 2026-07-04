# [ND] DESIGN queue — parallel-lane execution plan

## Context

**Goal:** implement the `[ND] NEXT UP — DESIGN` queue (8 items) in `design/`, optimizing for parallel work within ~1 hour where possible.

**Why this shape:** you asked whether item 1 can be parallelized, or the "Next up" queue restructured for parallel work (other agents used temp branches / git worktrees). Findings from a full read of the design system:

- **Item 1 is *not* meaningfully parallelizable.** It's one coherent refactor of tightly-coupled builders (`planCardHTML` / `planNavHTML` / `planFootHTML` / `mdEditorHTML` / `renderDocView`) in the same `behavior.js` functions. A worktree isolates the working tree *physically* but not the *logical* coupling — same-region edits become a merge conflict, not parallelism. Only its DESIGN.md prose sync is cleanly separable (small).
- **The queue *is* restructurable for parallelism — by disjoint file/surface, not by priority order.** Mapping each item to the files it touches yields **3 file-disjoint lanes** that run in parallel worktrees and auto-merge.
- **Honest ceiling:** parallelism cuts *total* wall-clock and lets the independent lanes land alongside the big one — it does **not** make item 1 an hour job. ~1-hour outcome: items **6, 7, 8 done + verified**, item **1 in progress**; items 1–5 continue as a multi-hour serial effort after.

## The 3 lanes (file-disjoint → worktree-safe)

| Lane | Items | Owns (files / regions) | Runs where |
|------|-------|------------------------|-----------|
| **L — Library spine** (serial long pole) | 1 → 2 → 3 → 4 → 5, + 7d reseed | `behavior.js` Library builders (~1464–1746) + `PLANS[]` (1598–1678); `mockup.html` Library panel (1208–1364) + doc textareas (1276–1349); `styles.css` Library classes (~1025–1560); DESIGN.md Library § (153–165) | **main session (me)** |
| **I — Inbox** | 6 | `behavior.js` Inbox (2095–2163); `mockup.html` Inbox mount; `styles.css` `inbox-sec` classes; DESIGN.md Inbox § (115, 408) | worktree subagent |
| **Q — Quick wins** | 7a, 7b, 7c, 8 | `gallery.html` (exclusive: ToC + chrome leaks 59/65/78/80/85); `behavior.js` `recipientsHTML` (1767); `styles.css` radius leaks (89/1249/1331/1406/1738) + `.rcpt-to` (686); `mockup.html` inline 2px borders (489/683/1498/1723–1725) + drawer button (862) + heading (1378); `tokens.css` | worktree subagent |

Lane I's only tie to Lane L is `6a`'s Review action → `switchTab('doc','documents')`, which works regardless of Lane L internals. Lane Q is entirely non-Library regions → 3-way-merges cleanly against Lane L. Worktrees are the right tool precisely because Q and L both touch `styles.css`/`mockup.html` (different regions) and concurrent same-file edits on one working tree would clobber.

## Folded decisions (were going to ask; using recommended defaults — override if wrong)

- **Item 8 radius near-misses (4px/6px on `.vrow`/`.att-item`/`.exp-mi`/`.con-perm`/`.ghost-ic`):** no radius token matches (scale is 5/3/2px). **Default: normalize to `var(--radius-base)` (5px)**, accepting a 1px shift on those 5 selectors — this fulfills the item's stated purpose (edit the radius tokens → whole UI updates). Flag the shift in DEVLOG. *Alt if you prefer pixel-identical:* leave 4px/6px, only tokenize exact matches (the six inline `2px`→`var(--border-width)`, gallery `3px`→`var(--divider-width)`).
- **Item 6 accordions:** item text already specifies "accordions … expanded by default." Build that; it resolves the deferred open question OQ-2 (DESIGN.md line 408 fold-vs-catalog) — sync that line.
- **Item 1 overturns "approval is Plans-only":** primary edit DESIGN.md **line 163** (the "approval is a Plans concept — never 'approved'" parenthetical); reconcile supporting lines **162, 118, 115**.

## Model & token strategy (hybrid — no user model-switching needed)

**Fable stays primary as orchestrator; Opus subagents execute.** The user is on Max 20x with Fable capped at 50% of weekly credits, wants no model check-ins, and wants reasonable wall-clock.

- **Fable (main loop):** owns the plan, dispatches subagents with `model: "opus"`, reviews each chunk's diff/report at chunk boundaries, makes judgment calls, resolves merges, writes DEVLOG. Does NOT inline-grind edits or run verification loops in its own context.
- **Opus (subagents):** all bulk work — file edits, browser verification (headless loop + headed pass), screenshots, gallery/DESIGN.md propagation drafts.
- **Deviation rule (binding on every subagent):** if execution requires deviating from this spec — a coupling the spec missed, a design decision not pre-decided here — STOP and report back to the orchestrator; do not improvise a fix. Orchestrator escalates to the user only if it overturns a design decision.
- **Lane L runs as 3 sequential Opus subagent phases** (L1: items 1+2 · L2: item 3 · L3: items 4+5+7d), orchestrator review between phases. Lanes I and Q are 1 Opus subagent each, in worktrees.

## Execution

1. **Permission gate (needs your go-ahead):** create **2 git worktrees** off `main` (Lane I, Lane Q). `git worktree add` is `ask`-gated by CLAUDE.md and binds subagents — this plan's approval is that go-ahead.
2. **Dispatch** Lane I and Lane Q (Opus, worktrees) concurrently with Lane L phase L1 (Opus, on `main`). Each lane follows the six-file propagation rule; Lane L defers full propagation/verification to the end of its batch (see below).
3. **Merge** Q and I back to `main` as they finish (they're quick); Lane L continues L2→L3. DESIGN.md sections touched are disjoint (Library § vs Inbox § vs editor prose) → mostly auto-merge; orchestrator resolves any overlap by hand.
4. **DEVLOG entry per lane**; DESIGN.md synced per lane per the design rules.

## Detailed execution spec (pre-decided so execution is mechanical)

### Phase L1 — items 1 + 2 (unify Plans/Documents + nav columns)

Build the item-2 target layout directly (don't build an intermediate Documents-cards-without-nav state).

1. **`DOCS[]` array** (behavior.js, beside `PLANS[]` 1598): 4 entries (readme, claude, claudeuser, notes) in plan shape — `{id:'doc-readme', file, status, title, owner, created/edited(+Ago), open, md, feedback, authors}`. `md` seeded from the current mockup.html textarea contents (1276–1349); fold `DOC_FB` (1532–36) into `.feedback`; statuses: give a mix (≥1 draft, ≥1 review, ≥1 approved) so the badge and lifecycle render meaningfully.
2. **`entryById(id)`** helper = `PLANS.concat(DOCS).find(...)`; swap it into every `PLANS.find`-style lookup: `planAct` (137–142), `reopenPlan`, `planJump`, `planNavMode` (1741–46), `saveComment` (1586–94, doc-branch merges into the unified path), `getFeedback`/`getAuthors` (1470/1478 — getAuthors' doc-hosts-return-[] special case is DELETED; docs now have authors).
3. **`renderDocs()`** → mirrors `renderPlans()` (1737): `#doc-list`.innerHTML = DOCS.map(planCardHTML); add `docs-badge` count chip on the Documents tab button (mockup 1213) with the same draft+review count rule; retire `renderDocView`-as-pane / `docPick` single-doc switching; `docEdit`'s toggle mechanic is retained but rehosted per-card (see L3.5d — shared by plans and docs).
4. **Documents pane rebuild** (mockup 1233–1353): two-column — left `.docnav`-derived **entry-nav** (each row a mini-card: row 1 icon+name+path, row 2 lifecycle `.dbadge`), right `#doc-list` card stack. **Plans pane** (1221–27) gets the same entry-nav column (listing PLANS) at the same width (`.docnav`'s current width; the in-card rail keeps its 184px). Remove the hardcoded "3 plans · 1 awaiting review" subtitle (1225) or make it live — make it live off the same counts.
5. **Bidirectional sync:** nav-row click → open + scrollIntoView + `plan-flash` the card (reuse `reviewPlan`'s mechanics 122–125, generalized to `openEntry(id)`); `togglePlan` open → `.on` the matching nav row.
6. **Footer:** docs get full `planFootHTML` (Export + Reviewer chip + Revise·Reject·Approve). Per the item's "only intended divergences" clause the old doc footer's **Remove** button is dropped — **flag this removal in the completion report.**
7. **DESIGN.md:** rewrite line 163 (docs share the full lifecycle + decision trio; drop "approval is a Plans concept"); reconcile 162, 155 (badge on both tabs), 158 (defer — L3 rewrites it for the 2-row header). Registry: rename/retag `doc-switcher` → entry-nav component.

### Phase L2 — item 3 (nested TOC, boundary helper, rosters)

1. **Level-generic heading parse:** `/^(#{2,4})\s+(.*)/` → `level = hashes.length`; rows get `data-hlevel` + a **unique anchor** `data-secid` keyed on line index (not heading text — repeated sub-headings collide). `.md-h2-row` generalizes to `.md-h-row`; add `md-h3`/`md-h4` text styles (styles.css, sized via existing tokens).
2. **`sectionRows(host, secid)`** helper — the single boundary rule: a level-L heading's section runs to the next heading of level ≤ L. Used by outline build, `railClick` (1500–11), `railHover` (1514), `highlightFbSection` (1543).
3. **Captions:** "Sections" → "Table of contents" (`ol-cap`, 1683); Feedback body caption "Responses" → "Feedback".
4. **TOC indent:** driven off the level number (e.g. `padding-left: calc((var(--hl) - 2) * var(--space-8))`) so deeper levels are a threshold bump.
5. **Rosters:** after the TOC in the outline body — **Authors** and **Reviewers** headings, each with a count badge; rows = identity `badgeHTML`; each Reviewer row shows its worst revise/block verdict badge right-aligned, or a lone Approved badge when that reviewer has only approvals. Derived by grouping `p.feedback` by agent.
6. **Drop the per-section approve gutter chip:** feedback-lens `railBadge` renders only revise/block; outline `ol-dot` approve state → neutral/none.
7. **Comment rules:** in the comment/verdict UI, revise/block require a non-empty comment (disable submit); approve is comment-optional and surfaces only in the roster.
8. **Seed data:** every PLANS/DOCS entry ≥1 author on the document-wide (title) cell; plan-1 gets one section carrying both a revise AND a block comment; readme.md md gains real `###`/`####` levels.
9. **DESIGN.md:** document the two-level model (reviewer verdicts ≠ document lifecycle), the TOC/caption changes, the comment-required rule.

### Phase L3 — items 4 + 5 + 7d (header 2-row, popover parity, prose unwrap)

1. **`planCardHTML` header → 2 rows:** r1 = owner badge · title · **steps count inline with title** (promoted; hidden when `stepN===0` — naturally Plans-only) · spacer · `cnt-strip` count chips · lifecycle `.dbadge`. r2 = filename · spacer · Created/Edited. Delete r3. Update DESIGN.md line 158.
2. **`openAuthorPop` rows:** row 1 = agent badge + Drafted/Edited/Revised action badge + right-aligned timestamp; row 2 = wrapping summary text. `authors[]` entries gain `{action, summary}` — seed accordingly. No thumbs.
3. **`openCmtPop`:** timestamp becomes the right-aligned tail of row 1 (badge · verdict · thumbs · spacer · time). *(Judgment call pre-decided: thumbs stay left of the spacer; flag in report if it reads badly in situ.)*
4. **Selectable box entries:** `.cmt-pop-item` rows click-to-select (`.sel` toggle), feeding the existing per-host selection store (`SELby`) → merged Export control — extends the existing multi-select→export pattern, no new pattern.
5. **Plans edit parity (5d):** plan cards gain the `docEdit`-style raw-markdown toggle — hidden textarea seeded from `p.md`, Edit ghost icon flips view⇄textarea, save writes back to `p.md` + re-renders. One shared `editToggle(host)` used by both kinds.
6. **7d prose unwrap:** remove the ~14 mapped intra-paragraph breaks (PLANS md: behavior.js 1603–05, 1608–09, 1620–21, 1624–25, 1646–47, 1663–64, 1674–75; doc md: readme 1278–80, 1290–91; claude 1302–03, 1306–07; claudeuser 1324–25). Keep all structural newlines. Add the one-line authoring convention (soft-wrap prose, one line per paragraph) to DESIGN.md beside the line-number guarantee (line 157) with the per-line-anchor rationale.
7. **Batched Lane-L propagation + full verification** (per the Verification section): gallery cards for changed/new components (plan-card, entry-nav, rosters, TOC), DESIGN.md registry, `data-comp` tags — then the one full headless cycle + one headed parity pass.

### Lane I brief — item 6 (Inbox), Opus, worktree

1. `INBOX_SECTIONS` (behavior.js 2095–2102): `{type:'plan'}` label → **"Plans & Docs"**; single unified card type (no new-vs-revise split).
2. `reviewPlan` → route by entry kind: plan → Plans tab, doc → Documents tab (`switchTab('doc','documents')` + open/flash the card — coordinate with L1's `openEntry`; the worktree merge point is this one function, orchestrator reconciles).
3. Seed one REQS doc-review example card.
4. **Accordions:** `.inbox-sec-head` becomes a toggle — full-width band one tint-step off the panel fill (`--surface-3` over white), leading chevron, label + count badge, hairline (`--rule`) into content; expanded by default; styled deliberately distinct from `.fcard` content accordions. Remove `data-status="undecided"`.
5. **DESIGN.md:** line 115 (section rename + doc routing), resolve OQ-2 (line 408) as "folds — decided", registry line 375. Gallery: update the inbox-section gx-card.
6. Own verification pass (headless + headed) on the Inbox surface.

### Lane Q brief — items 7a/7b/7c + 8, Opus, worktree

1. **7a:** `recipientsHTML` (behavior.js 1770): `→` text glyph → `<i data-lucide="arrow-right">` in `.rcpt-to`; resize via styles.css 686 (icon-sized, not 9px font).
2. **7b:** mockup 862: "Link Agents" → "Link Config" (matches drawer heading 1378).
3. **7c:** gallery.html sticky left ToC — gallery-local CSS/JS only: sectioned nav from the 5 existing `sec-*` anchors + nested per-card entries (`data-card` slugs), scroll-to on click; existing top `.gx-nav` may be absorbed into it.
4. **Item 8 sweep:** styles.css 89/1249/1331/1406/1738 radii → `var(--radius-base)` (accepting the 1px shift — pre-decided; the whole point is the human's upcoming radius edit propagating); mockup inline `2px` borders ×6 (489, 683, 1498, 1723–25) → `var(--border-width)`; gallery chrome 59/78/80 `4px`→`var(--radius-base)`, 85 `3px`→`var(--radius-sm)`, 65 `3px` border→`var(--divider-width)`. Leave all documented exceptions (50% circles, pills, zeros, `--nc`, `--term-*`, font-sizes, 1px/1.5px borders). Optionally note a one-line grep check (`border-radius:[0-9]`) in DESIGN.md's workflow prose.
5. Verification: before/after screenshot compare = nothing moved except the intended 1px radius shift; 7a/7c clicked through.

## Status cadence (automatic — user never prompts)

The orchestrator is auto-re-invoked on every background-agent completion. At each checkpoint — Lane Q done · Lane I done · L1→L2 · L2→L3 · L3 done · final merge — post a short status update: what landed, what's running, revised ETA, any flagged judgment calls. Expect one every ~30–60 min. On long phases, set a fallback wakeup so a hung subagent is detected and reported instead of stalling silently.

## Judgment calls pre-decided (so Opus doesn't improvise)

1. Doc footer **Remove** button is dropped (item 1's "only intended divergences" clause) — flag in report.
2. Radius near-misses normalize to `--radius-base` (1px visual shift accepted).
3. Section anchors key on **line index**, not heading text.
4. Inbox accordions resolve **OQ-2 → folds**.
5. Doc statuses seeded as a mix so lifecycle renders; content of docs otherwise unchanged.
6. `openCmtPop` row-1 order: badge · verdict · thumbs · spacer · timestamp.
7. Anything outside this list → STOP and report, don't improvise.

## Batched compliance & verification (the key timeline lever)

The six-file propagation + headless-then-headed verify rules are charged **once per surface, not once per item**:

- **Lane L (items 1–5 = one Library rebuild):** spot-check in the browser while building, but run the full propagation (gallery cards, DESIGN.md sync, `data-comp` tags) and the full verification cycle (headless resize narrow/wide + click-through every touched control + screenshots, then ONE headed parity pass) **once, at the end of the batch** — not five times.
- **Lanes I and Q:** one propagation + one verify cycle each (they're single-surface already).
- **Item 8:** "confirm nothing moved" — before/after compare of touched components (note the intended 1px radius shift from normalizing).
- **Final (serial):** after merging worktrees to `main`, one light integration pass on merged `mockup.html` + `gallery.html`.
- Serve `design/` over `http://localhost` (distinct port per worktree); Playwright MCP headless for the loop; screenshots → `.scratch/`.

## Timeline (revised — batched model)

**~4–6 h wall-clock total; good outcome ≈ 4 h.**

| Chunk | Estimate | Nature |
|---|---|---|
| Item 1 (data unification + card convergence) | 1.5–2.5 h | ~half genuinely new (DOCS[] data model, generalize `PLANS` lookups), half reuse |
| Item 2 (nav column both tabs) | 0.75–1.25 h | mostly reuse (`docnav` generalized) |
| Item 3 (nested TOC, boundary helper, rosters) | 1.5–2 h | genuinely new logic |
| Items 4 + 5 (header re-layout, popover/edit parity) | ~1–1.5 h | mostly reuse |
| Batched Lane-L propagation + full verify | ~1 h | fixed compliance tail, paid once |
| Lane I (item 6) + Lane Q (items 7–8) | hidden | run in parallel worktrees under Lane L |
| Merge + final integration pass | 0.5 h | serial tail |

(Earlier "6–8 h / budget a day" estimate charged the compliance tail per-item ×8; batching it per-surface is what recovers the difference. The irreducible new work is item 1's data model + item 3's parsing/roster logic.)

## Critical files

- `design/behavior.js` — Library builders ~1464–1746, `PLANS[]` 1598–1678, Inbox 2095–2163, `recipientsHTML` 1767, `cycleDir` 111
- `design/mockup.html` — Library panel 1208–1364, doc textareas 1276–1349, inline 2px borders 489/683/1498/1723–1725, "Link Agents" button 862, Link Config drawer 1377–1397
- `design/styles.css` — Library classes ~1025–1560, radius leaks 89/1249/1331/1406/1738, `.rcpt-to` 686
- `design/gallery.html` — sections `sec-*` (existing anchors), chrome leaks 59/65/78/80/85
- `design/tokens.css`, `design/DESIGN.md` (Library 153–165, Inbox 115/408, shared doc editor 157)
