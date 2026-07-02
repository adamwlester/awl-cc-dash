You are implementing **every item in the "Next up" section of `dev/notes/TODO.md`** by editing `design/mockup.html`. Deliver **finished, verified work** — not proposals. **Optimize for wall-clock speed: run the independent items as parallel subagents in isolated git worktrees.** Cost is not a concern; quality must match a careful single-agent pass.

## Read first

- **`dev/notes/TODO.md` — the "Next up" section is your work list (items 1–19).** Each item is self-contained: it names the exact change plus the real CSS classes / IDs / JS functions to touch. Also read the top of the file: **"How agents maintain this list" → "Next up — implementing items"** (build in `mockup.html`; work from `DESIGN.md` + `tokens.css`; keep `DESIGN.md` in sync; **leave each finished item in place — the human removes it after review, do not delete it**).
- **`design/DESIGN.md`** (design intent/patterns) and **`design/tokens.css`** (single source of truth for every value — never hardcode a value that belongs there).
- **`design/ui-snippets/`** — items **1, 2, 4, 5, 6, 7 are snippet-backed**: the design is already built in these standalone files. Your job for those is to **port the snippet into `mockup.html`, mapping its classes back onto the mockup's existing classes** (each item's text says exactly how). The other items are implemented directly.
- **`CLAUDE.md`** — especially the **UI-verification rule** and the **DEVLOG rule**. Both are mandatory below.

## Critical context (NOT obvious from the files — read carefully)

**Everything edits ONE file: `design/mockup.html`** (~4,400 lines: one `<style>` block + an HTML body + one `<script>`). It is a **static file opened directly in a browser — there is NO build step.** Therefore:

- **Do NOT split it into component HTML files.** That would require build machinery the project deliberately lacks, and the components share one CSS block + one JS scope with cross-referencing functions — splitting recreates the very collisions you're avoiding.
- **Parallelism comes from git worktrees (isolated repo copies), not from splitting the file.** "Collision" means two subagents editing the **same or adjacent lines**; git auto-merges non-overlapping hunks of the same file for free.

## The plan — 5 parallel lanes, then a serial finish

### WAVE 1 — run these 5 lanes **concurrently**, each in its own **git worktree** branched off the current branch, each editing **only `mockup.html`**, each doing its items **in the given order**, each **self-verifying** (see Verification) and **committing** its work:

- **Lane A — isolated components:** item **2** (Response popover, `#fmt-menu`/`.fmt*`), then item **5** (square agent cards, `.node`/Team Graph). These two share nothing with anything else.
- **Lane B — Context/Turns dropdowns (order matters):** item **6** first (Context turn-scope select), **then** item **1** (Turns breakdown dropdown). Both edit the shared `breakdownHTML`/`CTX` region — do 6 first so 1 reuses it. **When doing item 1, rename its new turns-data object to `TURNS_BD`** — a timeline `const TURNS` already exists (~L3450) and will clash.
- **Lane C — Library panel:** item **4** (Plans/Documents editor rail), then item **18** (Documents/Assets nav rows). Same panel, different functions — disjoint.
- **Lane D — tiny quick-wins (any order):** items **14, 15, 16, 17**. Four small, mutually-disjoint edits.
- **Lane E — the feed/card cluster (ONE agent, strict order, NEVER parallel):** item **7** → **9** → **10** → **11** → **13** → **12** → **3**. Every one of these edits the same card-render functions (`fcardHTML` / `logCardHTML` / `inboxCardHTML` / `msgCardHTML`) or adjacent feed/Compose-footer markup, so they must run sequentially in one context. For the jump pills (items **3** and **12**), **build ONE generic jump-pill implementation that serves both** the global scroll regions (3) and the feeds (12) — do not add two competing controls.

> All 19 items are covered: A=2,5 · B=6,1 · C=4,18 · D=14,15,16,17 · E=7,9,10,11,13,12,3 · Wave 2=8,19.

### WAVE 2 — after merging all 5 lanes, run these two **LAST and serially** on the merged file (they sweep regions every lane touched, so they cannot be parallelized):

- item **8** (recolour structural dividers `--rule` → `--border` globally). **Skip the `.md-*` dividers in the Plans editor — item 4 already converted those** (verify, don't re-edit). Apply the item's **"Preserve selection seams"** clause: on selected/feedback rows the rail/gutter divider must recolour to the band fill so highlights aren't sliced by a navy line.
- item **19** (standardize agent-badge sizing) — depends on items 7 & 9 having finalized the card functions, so it runs after the feed cluster is merged.

## Merge

Merge the 5 lane branches into your integration branch in any order — their hunks are region-disjoint, so git auto-merges. **Two likely micro-conflict spots, both trivial — resolve by keeping ALL changes:** (1) the `boot()` init line (~L4372) where lanes register init calls; (2) the Compose-footer DOM, lightly touched by item 2 (Lane A), item 16 (Lane D), and item 13 (Lane E) on different sub-rows.

## Open decisions — do NOT block

Item 5 lists open decisions **(a)–(e)** (does FAST grey out effort/think; subagent badge working/idle encoding; Run-% data source; pale-colour badge-text contrast; subagent badge click action). These need the human and are **not** resolved. **Build the decided parts; for the undecided ones use the honest fallback the snippet/text already shows** (e.g. the barber-pole indeterminate Run strip; badges showing identity only) and **note them in your final report — do not invent behavior or wait.**

## Verification (per `CLAUDE.md` — required, not optional)

For each lane, before calling its items done: serve `mockup.html` over **`http://localhost`** (the Playwright MCP browser blocks `file://`), drive it **HEADLESS**, **resize the affected panel(s) to both narrow and wide extremes** (this layout is resizable and that's where it breaks), **click through every control you touched**, screenshot each state, compare to the item's stated intent, and fix what's off. Each lane verifies its own work. After the full merge (Waves 1 + 2), do **one final HEADED parity pass** on the merged result at the narrow and wide extremes. Run multiple lanes' browsers on **distinct localhost ports** to avoid contention.

## Finish

- **Leave every Next-up item in place** in `dev/notes/TODO.md` (do not delete — the human removes each after review).
- **Keep `DESIGN.md` in sync** only where an item changes design intent or a pattern (the top TODO instruction governs this; there are no per-item reminders).
- **Append ONE `DEVLOG.md` entry** per the project rule, summarizing what was built and listing any item-5 open-decision fallbacks you used.
- **Report back:** what shipped, the open-decision fallbacks, any merge conflicts you resolved, and anything that needs the human.

## Mechanism

Use **git worktrees** for Wave 1 isolation (5 worktrees/branches off the current branch), run the 5 lanes as **truly concurrent** subagents (the Agent tool's `isolation: "worktree"`, or a Workflow with `isolation: 'worktree'` agents — whatever runs them in parallel), then **merge → Wave 2 serially → final headed verification → DEVLOG**. Optimize for elapsed time, not token cost.
