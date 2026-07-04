# DASHBOARD TODO — DESIGN BACKLOG & WORK QUEUES

> **Backlog is reference-only; the "Next up" sections are the only actionable ones.** For the backlog sections ([BD] · [BH]), agents must not implement anything, and must not treat any entry as confirmed, approved, or scoped, unless the human points them at a specific item. The exception is **Next up**: items there are approved for work, and being directed to that section is itself the signal to build them. This is otherwise a capture-and-triage doc.
>
> **One inbox, two lanes.** Rough notes land in a single **[IN] INBOX**; an agent then syncs each into the right downstream home. Downstream, work splits into two lanes: the **Design** lane (`design/` — the mockup, tokens, DESIGN.md) and the **Build** lane (the app — `sidecar/`, `bridge/`, `frontend/`; system reference in `docs/ARCHITECTURE.md`). The Design lane's backlog lives here (**[ND] → [BD]**). The **Build lane's backlog lives in `docs/ARCHITECTURE.md` §11 (Build backlog & queue)** — this doc keeps only the Build lane's approved execution queue (**[NB]**, staged from §11 when work is actually picked up) plus housekeeping & docs chores (**[BH]**). Both lanes are fed from the shared **[IN]** inbox.

## SECTIONS

> One row per section below. Backlog sections carry a two-letter tag; an item's ID is that tag + its list number (e.g. `BD2`, `BH1`). Next up / Inbox items stay untagged — they're transient (the human deletes each after reviewing the build). Notes/helper areas (this top matter, Scratch) carry no tag. The **backend/build backlog has no section here** — it lives in `docs/ARCHITECTURE.md` §11.

| Tag | Section | What lives here |
|-----|---------|-----------------|
| `[BD]` | BACKLOG — DESIGN | UI/UX work staged in the design system (`design/` — mockup, tokens, DESIGN.md). |
| `[BH]` | BACKLOG — HOUSEKEEPING & DOCS | Maintenance, config, and documentation chores. |
| `[ND]` | NEXT UP — DESIGN | Approved design queue, priority order. Build per the design path; leave finished items for the human to remove. Empty by design when idle. |
| `[NB]` | NEXT UP — BUILD | Approved build queue, priority order — staged from `docs/ARCHITECTURE.md` §11 when work is picked up. Build per the build path; leave finished items for the human to remove. Empty by design when idle. |
| `[IN]` | INBOX | Rough human notes (one per bullet) to be synced into the right Next up or backlog section later. Empty by design. |
| — | SCRATCH | Rough human ideas **not** to be used or considered by any agent. |

## HOW AGENTS MAINTAIN THIS LIST

> **Verify first.** Before adding or reordering, check the item against the current system — the design files for design items, the app code + `docs/ARCHITECTURE.md` for build items — and confirm it isn't already built. Drop anything already implemented; trim partly-built items to just the remaining gap.
>
> **Leave empty sections empty.** When a section has no items, leave it blank beneath its heading. Never add a placeholder, an "(empty)" marker, a status line, or a changelog note — the blank space *is* the signal, and that history belongs in DEVLOG, not here.
>
> **Format.** Each item is a numbered list entry — a **bold header**, then a concise description; bold only the header. E.g. `1. **Role Dropdown:** …`.
>
> **Numbering & IDs.** Within a backlog section, items are a numbered list; an item's ID is the section tag's two letters + its list number (e.g. `BD2`, `BH1`). Cross-reference related items by that ID (e.g. "see BD2"), and update those refs if you reorder. Next up / Inbox items stay unlettered — they're transient, so they don't get stable IDs.
>
> **Open questions.** An item that still needs research or a decision before it's buildable carries an **(open)** marker after its bold header. It files into whichever domain section it concerns; resolve the question (or get the human's call) and drop the marker before treating it as buildable — never build an (open) item as-is.
>
> **Next up — implementing items.** Items in a Next up section are approved for work; being directed to one is itself the signal to build it. For each:
> 1. **Build it where it belongs.** Design items → the design system (`design/`, authority `design/mockup.html`) per the CLAUDE.md design rules — propagate across all six files. Build items → the app (`sidecar/`, `bridge/`, `frontend/`) per the project's pytest conventions (hermetic where possible).
> 2. **Design path ([ND]).** Read `design/DESIGN.md` (intent, patterns) and `design/tokens.css` (single source of truth for every design value) first and let them inform the change — don't hardcode a value that belongs in tokens.css. Build in `design/` per the six-file propagation rule; if the change alters design intent or a pattern, sync DESIGN.md.
> 3. **Build path ([NB]).** `docs/ARCHITECTURE.md` — the final-intended-system reference — **leads the build**: read it first and build **toward** what it describes. Completing an item normally means clearing the matching **"⚠ Today"** marker there rather than rewriting its text; only edit the doc's actual text if the build deviated from documented intent or a new decision was made — and flag that to the human explicitly, never silently.
> 4. **Doc-sync before finishing.** DEVLOG.md always; `design/DESIGN.md` for design work; `docs/ARCHITECTURE.md` for build work; `CLAUDE.md` only if folder structure moved.
> 5. **Leave the item in place when done — do not delete it.** Log the work in DEVLOG per the project rule and report what you changed; the human reviews the build and removes the item once satisfied.
>
> **Inbox.** The human keeps rough notes as a bullet list (one per line) in the single **[IN] INBOX** — they don't sort their own notes, so an agent triages each on request. Handle each note in turn:
> 1. **Sync it** into the right downstream home — by default a backlog (design → [BD]; backend/build → the §11 build backlog in `docs/ARCHITECTURE.md`; chore → [BH]), or a **Next up** queue ([ND] / [NB]) when the human is directing it straight to work — with a concise **bold header**, plus an ID for backlog sections (Next up items get no ID).
> 2. **Minimal edits for clarity only** — tighten the wording so it reads cleanly and complete any obvious shorthand, but never change the intent or scope, and don't add ideas of your own.
> 3. **Disambiguate references.** Map any loose label or shorthand to the actual component/feature name as it appears in `design/mockup.html` (or the relevant app module). If you genuinely can't tell what's meant, keep the original wording and flag it rather than guess.
> 4. **Delete it from the [IN] inbox** once filed, so the bucket stays empty for next time.

## [BD] BACKLOG — DESIGN

1. **Drag-in Files:** Drag files from the VS Code explorer tree into the UI to load their paths for reference.
2. **Link Edges:** Add link-related UI to the Team Graph (directed graph edges) so you can see how agents are linked (replaces the old hand-drawn link lines, since removed). The grouped link-list in the Link drawer now exists (the grouped link-list decision — `docs/ARCHITECTURE.md` §7.6 *Links*, "Tracking"); the on-graph edges themselves remain deferred (`link-edges`, `planned`).
3. **Dense Link Graphs (open):** Once links render as directed edges (see BD2), decide how to keep many overlapping links readable and how to distinguish links sharing the same configuration.
4. **Save Response Summary:** Add a save action for summaries — the Summarize slide-over is copy-only today (the Export control saves raw selections, not generated summaries).
5. **Notes Hub:** Centralize my own notes somewhere in the dashboard — a project `notes.md` exists in Library → Documents, but there's no dedicated notes surface.

## [BH] BACKLOG — HOUSEKEEPING & DOCS

1. **npm Binary:** Update npm to the native binary.
2. **PowerShell Strings:** Find a better set of strings for PowerShell permissions.
3. **Dashboard README:** Update the Dashboard README.
4. **CLAUDE.md Trim:** Optimize my CLAUDE.md files — index other files instead of a full context dump.
5. **Doc Date/ID Tagging:** Better tagging of dates and IDs for document creation and editing.
6. **System Details Doc:** Document and maintain my system details — OS, Claude install, plugins, etc.
7. **Config SOPs:** Write SOPs for all major system-config activities (agent, hook, skills setup).
8. **Over-Scoped Absolute-Language Audit:** Sweep the guiding docs (`docs/ARCHITECTURE.md`, `design/DESIGN.md`) for categorical wording — "never", "always", "only", "read-only", "no X exists", "cannot" — and test each rule against the *actual* intent it protects. Where the wording over-reaches that intent it manufactures false contradictions (with DESIGN, the code, or a sibling section) and gets re-litigated every session; narrow those to their real invariant, but leave genuinely-absolute invariants intact (the goal is right-sizing, not blanket-softening). Two already surfaced in the Phase-5 discussion and slated for that reconciliation: §7.16/§8.5 "the dashboard **never writes into a content file**" (real rule: the *review layer* never embeds annotations in agent content — create/delete/explicit user-directed edits are fine) and §7.5 identity "**read-only in v1**" (identity is editable). Same doc-reconciliation family as the coverage audit.

## [ND] NEXT UP — DESIGN

1. **Unify Plans & Documents into one reviewable-document component:** Converge the Library → Plans and Documents tabs onto one shared expandable-card component used in both. Documents becomes card-based like Plans (a list of expandable cards replacing the current single-doc `renderDocView` pane), and each doc card gains the full Plans treatment: the within-card Outline/Feedback/Authors nav rail (`planNavHTML`), commenting, the same footer action strip, and the full Draft → In review → Approved lifecycle with the Approve · Revise · Reject decision trio (`planFootHTML`) — this overturns the "approval is Plans-only" rule, so sync `design/DESIGN.md` to match. Give the Documents tab a pending-count badge mirroring Plans (`renderPlans`/`plans-badge`: count entries that are draft or in-review; drop from the count only on approved). Lifecycle stays three states — no new "Revising/Editing" state (In review already covers it) — and the Revise button keeps its name (reused deliberately, consistent with Compose's Revise). Only intended divergences left between the tabs: Plans carry a steps-done count (docs have no checklist), and the Inbox Review action routes to the matching tab.
2. **Tab-level nav column on both tabs:** Give both tabs a two-column layout — a left "all entries" nav bar (the existing Documents tab nav list, now on Plans too, listing every plan/doc) beside the right card list. Each nav entry is a mini-card with a second row carrying its state badge (Draft / In review / Approved). Wire bidirectional selection sync: clicking a nav entry opens/scrolls to its card, and opening a card highlights its nav entry. Reuse existing widths — the nav column takes the current Documents nav-list width and the within-card rail keeps its current width (no new widths).
3. **Rail, Outline & review-surface overhaul:** (a) Feedback tab caption "Responses" → "Feedback" (so the caption echoes the icon-only tab); Outline caption "Sections" → "Table of contents". (b) Make the Table of contents nested — render `##`/`###`/`####` with level-driven indent, built level-generically (read the level from the `#`-count into a `data-hlevel` number; a single `sectionRows()` helper bounds a level-L heading at the next heading of level ≤ L; indent driven off the level number) so deeper levels are a threshold bump, not a refactor; key section anchors on a unique path/id, not bare heading text (repeated sub-headings otherwise collide); seed example `readme.md` with real `###`/`####` levels. (c) Add nested section selection — apply that same boundary helper in `railClick`/`railHover`/`highlightFbSection`. (d) After the TOC, add two Outline rosters — Authors and Reviewers — each rendered as identity badges with a count badge on its heading; each Reviewer row shows its revise/block verdict badge inline and right-aligned, or a lone Approved badge if that reviewer left no further feedback. This encodes a two-level model: reviewer verdicts (the Reviewers roster) are distinct from the document's own lifecycle (the header badge / footer Approve). (e) Drop the per-section Approve gutter chip — absence of a revise/block chip implies approved (frees rail space). (f) Reviewers must leave a comment on a revise or block verdict; approve is comment-optional and surfaces only in the roster. (g) Seed every example Plans/Documents entry with at least one author badge in the first (document-wide) rail cell, and seed the default-open example plan with a section carrying both a revise and a block comment — the densest realistic gutter cell after the approve-chip drop.
4. **Card header re-layout to two rows:** Collapse the plan/doc card header (`planCardHTML`) from three rows to two — move the review count-chips (`cnt-strip`) inline, trailing the main status chip (e.g. "In review") on the top-right of row 1, and promote the progress step count inline with the title (more prominent). Steps-done stays Plans-only (hide it when a doc has no checklist).
5. **Editor box detail & Plans edit parity:** (a) Author box rows (`openAuthorPop`): row 1 = agent badge + a Drafted / Edited / Revised badge + the timestamp right-aligned; row 2 = the summary text (wraps multi-line) — same layout grammar as the comment box, minus the thumbs. (b) Right-align the timestamp in the existing Feedback/Comments box (`openCmtPop`) too. (c) Make the box content entries selectable (click to select) so they feed the merged Export control — chiefly to link a comment/author entry to a prompt for follow-up clarification (extends the existing multi-select → export pattern). (d) Fix the Plans editor to switch to editable raw markdown on the Edit ghost icon, matching how Documents already toggles (`renderDocView`/`docEdit`).
6. **Inbox: Documents workflow + accordion sections:** (a) Support the Documents review flow in Team Feed → Inbox: rename the "Plan" typed section to "Plans & Docs" (`INBOX_SECTIONS`), keep a single unified card type (no separate new-vs-revise section or action) whose Review action routes to the matching Library tab (Plans or Documents), and seed one example Inbox card for a document-editing/review flow. (b) Convert all Inbox sections to accordions styled neutral/blended and deliberately distinct from the content-card accordions (agent/feed/history): a full-width band one tint-step off the panel fill, a leading chevron, the section label + count badge, and a hairline into the content; expanded by default in the mockup for scanning.
7. **Small tweaks, gallery nav & example cleanup:** (a) Message-card arrow — replace the sender→receiver arrow in the message card header with the Link Config panel's right-arrow icon, restyled to fit (need not match its size/weight). (b) Rename the "Link Agent" drawer button to "Link Config" (matching the drawer heading). (c) Gallery section-nav — add a sticky, sectioned left ToC to `gallery.html` (derived from the existing `gx-card` section groups, nested entries, scroll-to on click); dev-only, doesn't touch tokens or the product. (d) Strip intra-paragraph hard line breaks from all example plans (`PLANS[].md`) and docs (the `mockup.html` doc textareas) so prose wraps to the container — keep structural newlines (headings, list/checklist items, paragraph gaps, code) — and add a one-line authoring convention to DESIGN.md's Library editor section (soft-wrap prose, one line per paragraph) with the per-line-anchor rationale.
8. **Token-compliance sweep:** Migrate hardcoded design values that duplicate an existing token to `var(--…)` so every value routes through `tokens.css`. Known leaks: hardcoded radii in `styles.css` (`4px`/`6px` on `.vrow`/`.att-item`/`.exp-mi`/`.con-perm` + a ghost button) and `gallery.html`'s own `4px`/`3px` chrome, plus stray inline `2px` borders that should be `var(--border-width)`. Scope strictly to values matching an existing token — leave font-sizes inline (no font-size token exists, by design) and preserve the intentional exceptions (circles `50%`, pills, squares `0`, the per-instance `--nc`, the local `--term-*` terminal theme); exclude `mockup-toolkit.js` (the dev overlay, not a product component). A clean swap is visually identical, so verification is confirm-nothing-moved. The guidelines already exist (CLAUDE.md / DESIGN.md / tokens.css / TODO.md) — the gap is enforcement, so optionally add a lightweight grep/regex check to the design workflow. Run before the human's radius edit: once the leaks are tokenized, changing the three `--radius-*` values updates the whole UI (and the gallery) correctly on reload.

## [NB] NEXT UP — BUILD

## [IN] INBOX

## SCRATCH

> Rough human design ideas and notes not to be used or considered by any agent.

### General
- I want to switch from the cream background (#fef6e4) to something darker, like a charcoal. I want to keep the lighter cream for the main footer and the panel headers but for subheader within the panels I want to move to a darker charcoal (or whatever we use for the new main surface fill/background). 
- We need to standardize our count chips better. I am partial to just using teal for all these, not including the ones related to editing (approve, revise, etc). 
- I want to decrease the border radius for all of our components. I want to move to a more sharp neobrutalism style in terms of radiuses.

### Big picture and/or Needs more research 
- We need to make sure we build both the ui and other elements in a modular enough way that we can easily modify and add features.
- Need to build in more visual elements in plans like charts, mockups and diagrams
- Consider including an Artifacts tab in Library
- Need to come up with a way to support injectable reused snippets into the prompts.
- Need to add ToDo functionality back into UI eventually.
- Find a way to to support highlighting words and terms in text and having it defined in context.
- I want inline squiggle spelling highlights in any large text areas like in Prompt->Compose or the Library editors.
- I want to be able to select any or sections of text anywhere and right click (or something) to be able to get a definition in context for that term.
- Need to support a mode where agents can track real time desktop activity.
- Need to confirm that the current UI components etc translate to neobrutalism.dev. Acceptable if they do not, but leaning towards using a consistent library for maintenance.
- Need to determine what files should stay markdown vs what files would actually work better as JSON given they will be handled by agents and can be rendered in the UI however we want.
- I want to work out how to build in more visual elements in Plans like charts, mockups and diagrams. I am thinking a few things. We could have a separate tab in Library or put these in the Assets tab, but we will need a way to comment them with visual markers etc. We might utilize what we have already in this tool: design\mockup-toolkit.js. If we put it in the Assets, we may want to structure the nav bar with headings, like something for stock images
- Plans should utilize mermaid diagrams in markdown.
- Add some voice reading feature and, ideally, an option to change speed from normal up to 2-3x
- Need a string search feature for text fields.
- Need to turn compact into a multiselect with the 5 built in options.
- Need to track compaction history in context dropdown. Count and what type and when based on turns and time. Maybe put in the rewind/handoff list
- Output options should include tldr tables with tests/checks and emojis signaling status.
- I suspect we need support for "workflows" but I need to research these more.
- All commits need to include an agent id.
- We need a shared roster of agents and their state and current work that all agents have access to as part of their ongoing context. This might be subserved just by scratch
- Need to research if it is possible to directly render a terminal in the dashboard. Like actually embed a terminal so we could potentially cut down latency and generally have more direct ground truth regarding underlying terminal output.
- For our Decisions type entries in inbox, we need to have a way for me to get more detailed info for a given option. Either agents need to embed more detailed summaries of each option, a smaller support agent needs to be able to generate summaries as needed and/or there needs to be some type of small scoped qa feature for these. 
- Need to consider if we want to track all document/plans (possibly assets tab content) revisions. Ideally we would have a means of doing this by integrating minimal tracking metadata stored locally with git version control.
- We need to clearly track fork and handoff lineage including original transcript access and it should be visible to all agents so they can reference their ancestors transcripts as needed.
