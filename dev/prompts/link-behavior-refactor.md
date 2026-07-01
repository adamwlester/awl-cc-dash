# Link-behavior & dashboard refactor — implementation brief

This is a multi-part refactor of the dashboard mockup, `design/mockup.html` (the single-file UI mockup and the build target), plus the design docs it must stay in sync with. **Deliver a finished, working version — not a proposal.** It is one coordinated run, internally **staged P0 → P4**; because everything lands in one file, the phases run **sequentially**, each verified by rendering and logged to `DEVLOG.md` before the next begins.

The through-line: today content is shared to agents three different ways (a **Share** send-group, a **Review** send-group, and a **Link to prompt** button). This refactor collapses content-sharing into **one Embed/Attach control that routes everything through the prompt editor**, rebuilds the **Inbox** around typed sections (including a new **Error** type), and clears out some accumulated cruft (Ultraplan, the old toggle style). Two shared abstractions — an **inserted-block primitive** and a **select-to-act model** — are built once in P1 and reused everywhere downstream.

---

## Read first (do not skip)

- **`CLAUDE.md`** — the design-related parts: the folder map, the Key-files table, and especially the **UI-verification rule** (drive the rendered UI; resize narrow+wide; click every control; headless loop then one headed pass), the **DEVLOG rule** (log every repo change before ending the turn), and the **editing-discipline rule** (*preserve everything you weren't asked to change* — reproduce untouched markup/JS exactly).
- **`design/DESIGN.md`** — in full. It is the design reference (intent + patterns). Pay attention to: *Prompts (right, bottom)* + *The Templates flow*; *Library (middle, bottom)* incl. the shared doc editor + comment popout; *Team Feed* + *The Inbox tab*; the *Agent (left pane)* Mode block; *Linking & context-sharing*; and the *Design system* surface/color tables.
- **`design/tokens.css`** — the **single source of truth** for every design value. Use `var(--token)`; never hardcode a color/space/radius/shadow. If you need a new value, add it here, grouped with a comment.
- **`dev/notes/DESIGN_TODO.md`** — the Inbox notes driving this work (the ones about Embed/Attach, the Error badge, the feed relabels, Templates→Editor) and the backlog items it closes. See **Docs to keep in sync** at the end.
- **Open `design/mockup.html` and serve it over `http://localhost`** (the Playwright MCP browser blocks `file:`) before changing anything — study the Prompts panel, Library, Team Feed/Inbox, and the Agent Mode block as they behave today.
- Reference-only (do not edit): **`archive/design/design-v10p6/mockup.html`** — the frozen older version you'll pull the labeled-toggle style from in P0.

## Ground rules (apply to every phase)

1. **Build in `design/mockup.html`.** Keep `design/DESIGN.md` in sync as intent changes (named per phase below), and source every value from `design/tokens.css`. Confirm DESIGN.md and the mockup agree before calling a phase done; if a change needs no DESIGN.md edit, say so explicitly.
2. **Preserve everything you weren't asked to change.** This file is large and dense — reproduce untouched regions exactly. The usual failure is dropping/altering adjacent code, not over-editing.
3. **Neobrutalism conventions** (2px navy borders, hard offset shadows, flat fills, tight radius, Archivo/JetBrains Mono) — match the existing surface; reuse existing component classes rather than inventing parallel ones.
4. **Verify by rendering, per phase.** After each phase, render the touched surface over `http://localhost`, resize the affected panel(s) to **both narrow and wide extremes**, and **click through every control you added or changed**. Screenshot each state, compare to intent, fix what's off. Iterate **headless**; finish each phase with a quick **headed** parity pass on the touched states.
5. **`DEVLOG.md` per phase** — append an entry (what changed, observable outcome, `Files:` line) as each phase completes. Don't batch all five into one entry.
6. **Naming discipline.** The two content-delivery modes are **Embed** and **Attach** — never "Link." The word *Link* is reserved for inter-agent links (Link Config / Link Agents / link triggers). Don't overload it.

## Two foundational abstractions — design these once (in P1), reuse everywhere

- **The inserted-block primitive.** Everything that drops into the editor body is one block component with a `kind`:
  - `embed` — **frozen** quoted content (a doc section, a message body/block). Muted, small font, a static **"from \<source\>"** header line, **click-to-source**, a remove (×) affordance, **clamp + expand** when long. Not editable.
  - `template` — **interactive**. Same muted/header/removable shell, but **selectable**: selecting a template block makes it the *active* one whose placeholder pills fill from the Templates section.
  - `citation` — an inline pill in the prose pointing at an attachment chip (see P4).
  Build one block primitive with variants, **not three bespoke widgets** — this is the single highest-leverage decision for the eventual ~1:1 React port.
- **The select-to-act model.** One selection language shared by **Library content** and **Team Feed message cards**: whole = pink, section/line/block = teal (the existing rail colors). A selection gates the Embed/Attach control. Library already implements this via the rail (`mdEditorHTML`/`railClick`/`SELby`); P1 generalizes it so feed message cards can be selected the same way.

---

## P0 — Agent-panel cleanup (Ultraplan removal + Mode-toggle revert)

Independent and low-risk; do it first to clear complexity before touching shared surfaces.

**Anchors** (`design/mockup.html` unless noted):
- Ultraplan footprint: ~8 references in the mockup, 2 in `design/DESIGN.md`. Includes the Mode-block toggle, its plan-mode gating (`syncUltraGate`, wired near the init call `document.querySelectorAll('.seg.mode-seg').forEach(syncUltraGate)`), any `ultra` field in demo data (e.g. `PLANS` entries carry `ultra:false`) and any Ultraplan **tag** rendered on plan cards/graph cards.
- Current Mode toggles: the `.swh` slider-switch row (CSS at the `.swh` / `.swh.on` rules ~line 1637-1639) carrying **Fast · Thinking · Ultraplan**, in **both** the Agent → **Details** and **Create** tabs. Gating today: *Fast gated to Opus*, *Ultraplan gated to Plan mode*.
- Revert target: `archive/design/design-v10p6/mockup.html` — the older **labeled toggle-button** style (reads "Opus fast-mode Off/On" / "Thinking mode off/on"). Pull its exact markup + CSS.
- `dev/notes/DESIGN_TODO.md` **B4** — remove the "*must support the new native ultraplan functionality*" clause.

**Changes:**
- Remove Ultraplan entirely: the toggle, its gating logic, any badge/tag, the `ultra` demo-data fields, and all mentions (mockup + DESIGN.md + the TODO B4 clause). All planning uses the default path now.
- Replace the `.swh` Fast/Thinking/Ultraplan row with the **v10p6 labeled-toggle style**, **two toggles only**, relabeled **"Opus Fast-Mode"** and **"Thinking Mode"** — in both Details and Create.
- Keep **Opus Fast-Mode gated to the Opus model** (it's a real `/fast` constraint). Thinking has no gate.

**Acceptance:** no "ultraplan" string anywhere in `design/`; the Mode block shows two labeled toggles in both tabs; Opus Fast-Mode dims/enables with the Model = Opus condition; nothing else in the Agent panel shifts.

**Docs sync:** update the Agent-panel Mode description in `design/DESIGN.md` (the paragraph listing Fast/Thinking/Ultraplan) and remove the other Ultraplan mention.

---

## P1 — Foundations (block primitive · select-to-act for Library + Feed · badge tightening)

The backbone. Get these right; P2–P4 lean on them.

### P1a — The inserted-block primitive
Stand up the block component described above (`embed` / `template` / `citation` variants) as a reusable renderer the editor can hold inline. It is consumed in P2 (the Reply reference block), P3 (templates, the editor body), and P4 (embeds, citations). Style it from `tokens.css` (muted text, a hairline/own-outline boundary, small heading). **Use the card-outline color for the block boundary, not the tan divider color.**

### P1b — Select-to-act, generalized to the Team Feed
**Anchors:** Library rail — `mdEditorHTML` (~3498), `railClick` (~3514), `SELby` (~3511), `clearSel`/`setCmtCtl` (~3512-3513); classes `md-rail` / `md-row` / `rsel` / `rsel-sec` / `is-sec` / `is-title`. Feed — `fcardHTML` (the message card, ~3755), `renderFeed` (~3831), the typed content **blocks** in `MSGS` (`blocks:[{k:'think'|'read'|'write'|'bash'|'diff'|'meta', t:'…'}]`, ~3778-3807), `applyMsgFilters` + the six Include toggles (Thoughts/Read/Write/Bash/Diffs/Meta), and the current selection control `toggleCardSel` / `.card-sel` (~3838) + the shared feed action strip (`feedAct` ~3839, the "SHARED FEED ACTION STRIP" markup ~2415).

**Changes:**
- Replace the per-card **checkbox/`.card-sel`** with **click-to-select the card** (the pink "whole" analogue) plus a **global select-all** control in the feed action strip. Keep the **expand chevron** as a *separate* trigger so **select ≠ expand**. *(Scope: the **Messages** tab only — **Scratch and Log are out of scope** for selection and Embed/Attach.)*
- Give each **message card a block rail**: the **default message text** is one selectable block and **each included block** (thoughts, tool calls, diffs, meta…) is its own selectable block, using the same teal/pink select language as Library. **The rail updates with the active Content/Type filter** — only currently-visible blocks are selectable.
- Relabel the Team Feed controls: **"Filter" → "From/To"**, **"Show" → "Type"**, **"Include" → "Content"**.
- Selection feeds the Embed/Attach control in P4 (section/block → Embed; whole card/doc or an Asset → Attach).

### P1c — Tighten dropdown agent badges
**Anchors:** `badgeHTML` (~3481) → `<span class="badge badge-c [badge-sm] …">` + `agtileHTML(a)` + `.b-lab`/`.b-role`/`.b-name`; CSS `.badge` (height:32px, ~1074), `.badge-c .agtile` (height:100%; width:28px; ~1076), `.badge-sm` (height:26px, ~1088). Compare against the standard footer action buttons (`.btn` / `.btn-sm` / `.btn-secondary` / `.icon-btn`).

**Changes:** tighten the dropdown badges so they sit in the **same height footprint as standard footer action buttons**, and **remove the white strips above/below the agent icon** (inspect `agtileHTML` + `.agtile` — the icon is inset within the tile; make it fill the tile's height). This is a global improvement to every agent selector (From/To, the reviewer select, target popovers) and is what lets the new **Review** trigger (P4) show a full badge without being taller than its neighbors.

**Acceptance:** Library and Feed share one selection model (click-to-select, select-all, teal/pink language); message cards expose per-block selection that respects the Content filter; dropdown agent badges match footer-button height with no white strips. Resize both panels to extremes and confirm the rails/selection don't break.

**Docs sync:** update *The Templates flow* / Library shared-doc-editor and *Team Feed* descriptions in `design/DESIGN.md` to describe the shared select-to-act model and the feed relabels; note the badge convention in the Design-system section.

---

## P2 — Inbox restructure (sections · Error · relabels · Plan cards · Reply-block · status colors)

**Anchors:** `REQ_META` (~3889: `permission`/`approval`/`decision` → `{cls,ic,lab,edge}`), `REQS` demo data (~3894), `inboxCardHTML` (~3904), `inboxReplyHTML`/`replyTo` (~3902), `reviewPlan` (the Review→Plans cross-link), `pickDecision`/`inboxDecision` (~2942/3925), `inboxResolve` (~3922), `renderInbox`/`refreshInbox` (~3918), the `inbox-badge` count. Type badge = `.dbadge` + `.db-permission`/`.db-approval`/`.db-decision`; edges = `var(--req-permission|approval|decision)` (the reddish→copper ramp in `tokens.css`). Status colors: `.nb-pending` uses `--warning` (~818). The **Error seed** already exists: `MSGS` has a `status:'failed'` card (drew, 14:48, `ECONNREFUSED`, ~3803) with a `{k:'meta',t:'auto-stop: run ended on error…'}` block.

**Changes:**
- **Group Inbox cards into sections by type** — **Permission · Plan · Decision · Error** — instead of per-card type badges. The **section header carries the label** (light color-coding in the header *only if it stays clean*); **remove the per-card type badge** (`.dbadge`). This supersedes the reddish→copper attention ramp (TODO **C7**).
- **Relabels:** **Approval → Plan**. Keep **Permission**. Keep **Decision**, and document it as the **`AskUserQuestion`** surface — **one question per card** (the choice mechanism + Reply both need a single subject; related questions simply cluster in the Decision section).
- **Plan cards drop Approve/Reject** — keep only **Review** (the labeled button that jumps to Library → Plans via `reviewPlan`) and the shared **Reply**. All plan approval and the agent-review verdicts live in the Plans tab. *(Keep the Inbox Plan card's "Review" labeled; the Plans-tab "Review" chip from P4 is icon-only — same word, two jobs, kept visually distinct.)*
- **New Error type + section.** See **Error card spec** below. Wire the existing `status:'failed'` drew message → an **Error** `REQS` entry so the agent-card→Inbox path has a live example (this is the long-standing "Failed → Error, wired example" note).
- **Reply, generalized.** `Reply` now (for every card type) **pre-fills the Editor with a reference block of the card's contents** at the top, *and* pre-selects the agent as target. **This reference block is a frozen `embed` block — the P1a primitive, not a bespoke widget.** For a **Decision** card the reference block embeds the **question + its options**; for **Plan/Permission/Error**, the request/error detail.
- **Status-color rework.** **Error owns the danger color**; move **Pending off danger** (`.nb-pending` currently uses `--warning`, but reconcile the whole status set so Error/danger reads as the alarm and Pending/Permission/etc. don't collide). Adjust `tokens.css` as needed (single source of truth).

**Acceptance:** the Inbox renders four typed sections; Plan cards show only Review + Reply; a Decision card shows one question + options + Approve + Reply; an Error card renders inline error text with Retry · Dismiss · Reply; the drew failed message produces a matching Error card; Reply lands in the Editor with a reference block; status colors are coherent with Error = danger.

**Docs sync:** rewrite *The Inbox tab* in `design/DESIGN.md` (the type table → sections, Error added, Approval→Plan, Plan cards lose Approve/Reject, the generalized Reply-reference-block), and update the Design-system color table for the status rework.

---

## P3 — Compose → Editor (rename · templates-as-blocks · attachment strip · Library editor header)

**Anchors:** the Compose tab markup (~2505-2517): `#prompt-compose`, the `sec-h` "Templates" header, `#tpl-select`, `#tpl-fill-input` + `.fill-btn`s, the **"Compose"** heading span (~2515), `#compose-field` (the `contenteditable` `.compose-rich`), `copyCompose`/`clearCompose`. Template engine: `applyTemplate` (~3082), `composeField`, `saveComposeRange` (~3079), `buildTemplateOptions` (~3075), `TEMPLATES` (~3071), the placeholder pills (`phSpan`). Library footers: `libFootHTML` (~3017) + `libLink` ("Link to prompt", ~3030) on Documents/Assets. Attachment-chip pattern to reuse: `att-chip`/`attPopHTML`/`openAttachment` (~3767-3775, currently History-only).

**Changes:**
- **Rename the "Compose" heading to "Editor"** (TODO note 118).
- **Move the Templates section *below* the editor** (the picker dropdown + fill input). Picking a template **inserts a `template` block** into the editor (not inline raw text); **selecting** a template block makes it the active one whose placeholder pills the fill input drives. Templates stay interactive; other embeds are frozen.
- Embeds/templates **stack vertically as delimited blocks** in the editor body (via the P1a primitive), each with its muted header + remove (×) + (for embeds) click-to-source.
- **Add a horizontal attachment-chip strip *above* the editor** (TODO note 109): small cards/badges styled like the Library nav cards, laid out horizontally, each with a **remove ×** and **click-to-open in the Library** (reuse the `att-chip`/`openAttachment` pattern). Final vertical order: **attachment strip → editor → Templates section**.
- The Library Documents/Assets footer's **"Link to prompt" becomes the Embed/Attach control** (wired in P4).
- **Library Plans & Documents: match the Editor-header treatment** (TODO note 119). Add an **"Editor" header** above the content field in the **Plans and Documents** tabs, and move their **Copy · Edit · Comment** buttons up to sit **inline with that header, right-aligned** — mirroring the Compose Editor header and **reusing the same ghost icon-buttons** as Compose's copy/clear (not a new style). **Assets** simply **drops** these three buttons (an image isn't text-editable; no header there). Each tab's remaining footer keeps its sharing/decision controls (the Plans decision trio + the Embed/Attach control from P4).

**Acceptance:** the heading reads "Editor"; templates insert as selectable/removable blocks below which the fill input operates; the editor holds frozen embed blocks + interactive template blocks with clear boundaries (card-outline color); an attachment strip sits above the editor with removable, click-to-Library chips. The Library **Plans & Documents** tabs show an **"Editor" header** with **right-aligned Copy · Edit · Comment ghost icons** (Assets has neither the header nor those buttons).

**Docs sync:** update *Prompts (right, bottom)* and *The Templates flow* in `design/DESIGN.md` (Editor rename, templates-as-blocks, the attachment strip, the block model). Also update the **Library** *Documents and Assets share a card shape* paragraph (and the Plans description) for the new **"Editor" header** + relocated **Copy · Edit · Comment** (Assets loses them).

---

## P4 — Content-sharing capstone (Embed/Attach · Review chip · citations · comment fix)

**Anchors:** `sendGrpHTML` (~3682) + `sendTo` (~3930) — the **Share/Review** "agent dropdown + paper-airplane" groups on the Feed (Messages, ~2421) and Plans footer (~3688-3697, `sendGrpHTML('share',…)` + `sendGrpHTML('review',…)`); the target-popover machinery `toggleSrcPop`/`agAllNone`/`fillAgLists`/`agrowHTML`. Library footer `libLink`. Comment system — `railBadge` (~3496), `openCmtPop` (~3557), `fbCountsBySec` (~3495), `VERDICT` (~3531), `thumbsHTML` (~3534), `selectMatchingCards`/`navCardClick` (~3552-3554).

### P4a — The Embed/Attach control (replaces Share + Link-to-prompt)
- One control on **Library** (Plans/Documents/Assets footers) **and Team Feed** message cards, replacing the **Share** group and the old **Link to prompt** button. Action button is the **link icon, no label**.
- **Selection-gated** via P1's model: **disabled until there's a selection**; a **section/line/block** selection enables **Embed** (Attach greyed); a **whole-doc/title** selection or an **Asset** enables **Attach** (Embed greyed). Both modes stay visible, just context-enabled.
- **Embed** → drops a frozen `embed` block into the Editor (P1a) — the selected text, with a "from \<source\>" header + click-to-source.
- **Attach** → adds a chip to the P3 attachment strip. **Attach delivers a path reference + a hardcoded "read this" instruction** to the receiving agent. For content with no real file path (a message, a multi-block selection), the model is **materialize-the-selection-to-a-temp-file-and-reference-it** — so Attach works uniformly, including bundling **the whole reply from the active blocks**. *In the mock, represent this as a chip with a representative path* (a real path for real files, a temp-style path for materialized content) — **do not build real temp files**.

### P4b — Inline citations
From a chip's **ghost link icon**, with the cursor in the editable prose, insert an inline **`citation` pill** pointing at that attachment (carrying its path — same payload as Attach). Rules: **deleting a citation does not delete its attachment**; **deleting an attachment cascades to remove its citations**; you can only cite something already attached.

### P4c — The Review chip (single-agent reviewer select)
Replace the Plans-tab multi-select **Review** send-group with a **single-agent reviewer select**: the trigger shows the chosen reviewer's **full agent badge** (now tightened by P1c so it's no taller than the other controls), paired with an **icon-only, "review"-evocative button (no text)**. Picking *who* reviews is the only choice; the icon sends. *(This is groundwork for the single-reviewer-agent model — the deeper review/verdict formalization stays deferred, see Out of scope.)*

### P4d — Fix the rail-badge comment bug
Today `railBadge` counts **all** verdicts on a section (`n = approve+revise+block`) but `openCmtPop` filters items by `sec` **and the single worst verdict** — so a "2" badge can open **1** comment. Make the rail badge a **section anchor**: a click opens **one popout listing all comments for that section** (every verdict), each row carrying **its own verdict badge** and keeping **its own thumbs up/down** (`thumbsHTML`). Drop verdict from the open filter + the popout header; simplify the card↔text↔popout linking (`selectMatchingCards`/`highlightFbSection`) to the section anchor.

**Acceptance:** one icon-only Embed/Attach control on Library + Feed, selection-gated with the right mode enabled; Embed yields a frozen editor block, Attach yields a strip chip (representative/temp path); citations insert/delete per the cascade rules; the Review chip is a single-agent badge select + review icon; clicking a section's rail badge shows *all* its comments with per-row verdict + thumbs, count matching contents. Resize Library and Feed to extremes; click every mode/state.

**Docs sync:** update the Library footer + *Linking & context-sharing*-adjacent sharing descriptions in `design/DESIGN.md` (Share/Link-to-prompt → Embed/Attach; the Review chip; Embed vs Attach payloads; the temp-file note), and correct the comment-popout description to the section-anchored behavior.

---

## Error card — full spec (P2)

**Purpose:** capture **any abnormal block to execution** (distinct from the expected Permission prompt, Decision question, and Lifecycle auto-stop). One **Error** type carrying a short **subtype label**, so the section holds varied errors legibly.

**Subtypes to model** (label + a representative seeded example is enough for the mock):
- **API / model** — rate-limit / usage cap, overloaded (529), expired auth/billing, context overflow, network timeout.
- **Tool / MCP** — a tool crash the loop can't recover from, file-op failure (permission/path/disk), MCP server down/disconnected.
- **Environment / connection** — the agent's process/terminal died (bridge tmux session dropped / SDK session lost), OOM/killed, repo state broke.
- **Config** — invalid settings/hook, missing MCP config or env/secret, malformed skill/plugin/agent file.

**Boundary calls (agreed):** auto-stop limit reached = **Lifecycle**, *not* Error; model refusal/safety stop = *not* Error (a normal message); a **stall / no-progress timeout** = **Error** (subtype "Stalled"); a hard permission denial = not Error unless it actually crashes the run.

**Card shape:** renders the **error text inline** in the body (so no "View"). Actions: **Retry** · **Dismiss**, plus the shared **Reply**.
- **Retry** — populates the **Editor** with the **last command** (consistent with the other actions routing through the Editor; *not* the Console). For API/connection subtypes with no discrete command, populate the last command/action when one exists.
- **Dismiss** — clears the card.
- **Reply** — the shared button: Editor + error-info reference block, target defaulted to this agent (change **To** to forward — which is why there is **no separate Forward**).
- **No View, no Forward.**

**Wiring:** rename the Messages `status:'failed'` (drew/`ECONNREFUSED`) to read **Error**, and add a matching Error `REQS` entry so the agent card and Inbox are linked.

---

## Out of scope — do not build (note as deferred)

- **The Review / Inbox *formalization*** — the single-reviewer-agent model, how agent verdicts resolve, and how the human gate relates to agent review. P4c only restyles the Review *control*; the workflow stays as-is. This is the real **TODO B13** — leave a one-line marker in `DEVLOG.md` (and ensure B13 captures it) so it isn't lost.
- **Real backend** — temp-file materialization, actual message sending, real plan/review state. Everything here is mock behavior in `design/mockup.html`.
- **Other Inbox notes not discussed** — `dev/notes/DESIGN_TODO.md` Inbox also lists items this refactor does **not** cover (turns-bar dropdown, removing the Library nav trash ghost, divider-line color, Team-Feed timestamp alignment, removing "Time" from the Link Config End-After). **Leave those Inbox notes untouched** — don't implement or file them.
- **Team Feed Scratch & Log tabs** — the new select-to-act selection rail and the Embed/Attach control are **Messages-only**; Scratch and Log are untouched in this pass.

## Docs to keep in sync / TODO.md housekeeping

- **`design/DESIGN.md`** — updated per-phase as listed above; confirm it agrees with the mockup before finishing.
- **`design/tokens.css`** — any new/!changed values (status colors, block boundary) live here, grouped + commented.
- **`dev/notes/DESIGN_TODO.md`** — **remove the Inbox notes this refactor implements** (the Embed/Attach behavior incl. "all of this new behavior needs to be wired up", the compose linked-docs/assets cards, the Failed→Error + Error-in-Inbox + status-color note, the Filter→From/To and Show/Include relabels, the Templates-below + Compose→Editor note, the Plans/Documents "Editor" header + inline-buttons note). **Remove the Ultraplan clause from B4.** Treat **C7** (attention ramp) as closed by the Inbox sections. **Leave** the out-of-scope Inbox notes (above) in place.

## Finish

1. Each phase: render-verify the touched surface (narrow + wide, click every changed control, headless then one headed pass) and append its `DEVLOG.md` entry.
2. Final pass: a full headed walk of the Prompts (Editor), Library, Team Feed/Inbox, and Agent Mode surfaces at both width extremes — confirm nothing outside the requested changes regressed.
3. Report back with: the phases completed, the new Embed/Attach + Inbox + Editor behavior in a short paragraph each, and confirmation that `DESIGN.md`/`tokens.css`/`TODO.md` are in sync — so it can serve as the working contract.
