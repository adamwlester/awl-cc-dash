# Design-Stream Finisher (design/)

Integrate into the `design/` files the full **design-layer (🎨) stream** of the resolved decision tracker, in one coordinated pass, and leave the design system finished and final. Deliver working, verified work, not a proposal. You have full repo and system access; use it. Scope is the **eight design-tagged decisions** — agent identity (§7.5), subagent integration (Subagents, §7.17), permissions (§7.11), the Library (§7.16), prompt composition (§7.14), settings (§7.15), Retire & Delete (§7.12), and the Console (§7.13), per the like-named sections of `docs/ARCHITECTURE.md` — limited to what is actionable now.

**The tracker is your plan, not this prompt.** `archive/notes/open-system-decisions-2026-06-29.md` (archived — the decisions are now woven into `docs/ARCHITECTURE.md`'s topical sections) holds the locked **`Decision:`** lines and the per-item **🎨 design-layer:** notes that say exactly what each touches. Follow those, and **build from `Decision:`, never `Recommended:`** (some `Recommended` lines now state the reversed/superseded policy — e.g. the Retire & Delete entry's says "keep Delete deferred," but the `Decision` ships Delete in v1). This prompt points you at context and flags the few things easy to get wrong; it deliberately does not restate the decisions — read them at the source.

## The current state of `design/` — work from the live files

The design system is being finalized in the live working tree right now and will be complete when you run. **Work directly on the live `design/` files as they stand** — they, plus `CLAUDE.md` and `design/DESIGN.md`, are the authority. Two consequences you must respect:

- **Do NOT use `git worktree`, and do NOT touch `archive/`.** The design files are mid-flight in the **working tree**: `design/behavior.js` is currently **untracked** and `design/mockup.html` / `gallery.html` / `DESIGN.md` are **modified-but-uncommitted** (only `tokens.css` and `styles.css` are committed). A fresh worktree off `HEAD` would check out the stale committed mockup and **would not contain `behavior.js` at all**. Work in the live working tree. The `archive/design/design-v11p2/` snapshot is an **older five-file structure** (no `behavior.js`, a different gallery model, a ~200KB-larger mockup) — it will mislead you; ignore it entirely.
- **Locate every anchor by content, not by line number.** The files are large and actively changing; find each component by its `data-comp` / markup, never by a cited offset.

## Parallel streams (read this)

A **separate agent is integrating the backend stream of this same tracker at the same time**, editing `sidecar/` + `bridge/`. The two streams are **disjoint by file set and must stay that way**:

- **You own the `design/` files only.** Do not touch `sidecar/`, `bridge/`, or any application code — backend wiring is the other agent's job (you draw the surface; it wires it).
- **The one shared file is `DEVLOG.md`.** Append-only at the bottom; **re-read it from disk immediately before appending** (the backend stream is appending concurrently — a stale in-memory copy will clobber its entry).
- **One cross-stream seam — the agent-identity colors.** You own the 25 `--ag-*` color tokens (names + OKLCH values) in `tokens.css`; the backend mirrors those **names** in its identity store. Define them cleanly; you are the canonical home for the palette.

## The six-file design system (this is the propagation contract)

`design/` is **one system in six files** (per `CLAUDE.md` → "Design changes"). Read `design/DESIGN.md` before touching any of them. Each owns one thing:

- **`tokens.css`** — every value (no design value lives outside it; reference via `var()`, never hardcode).
- **`styles.css`** — shared component CSS.
- **`behavior.js`** — shared component **behavior / interaction logic**, loaded by **both** `mockup.html` and `gallery.html` so they can't drift. This is the single source of truth for how controls actually act — **never duplicate behavior into the mockup or the gallery.**
- **`mockup.html`** — the working app surface; each component's `data-comp` name + `data-status` marker.
- **`gallery.html`** — the **interactive catalog**: every reusable component shown as the *real, live* component, variants side-by-side, operable controls driven by the shared `behavior.js`.
- **`DESIGN.md`** — the rules and intent + the component registry + the Open Questions register.

**Propagate every change to all the files it touches.** A **value** → `tokens.css`; **component CSS** → `styles.css`; a component's **behavior / interaction logic** → `behavior.js`; a **new/changed component** → tag it in `mockup.html` (`data-comp`, plus `data-status` if dormant) **and** add a `gx-card` to `gallery.html` with its *real markup* **and** register it in `DESIGN.md`; a **rule/intent** → `DESIGN.md`. A change that lands in only one file when it owes others is unfinished.

**The gallery is interactive, not a per-state grid.** A `gx-card` shows the component's real markup; its behavior comes free from `behavior.js`. Show **every variant** side-by-side, and give a **standing/labeled specimen only to data-states that can't be reached by interacting** (disabled / empty / error / just-attached). Do **not** fabricate hover/focus/active/open/selected specimens — those are reached by driving the live specimen.

**Reuse before adding.** Check `tokens.css` and `styles.css` for an existing token/class before introducing a new one (the subagent-integration item reuses the `accordion` primitive, the run-state tokens, and the select-to-act model; the agent-identity item reuses the picker components, `--icon-fg`, the per-card `--nc` binding, and the OKLCH recipe). New tokens are **additive — never rename an existing one.**

## In scope — pointers, not restated decisions

Read each item's `Decision:` + `🎨 design-layer:` in the tracker for the actual scope, and enumerate the live components from the mockup. Sort each into **confirm/finalize** (verify it matches the decision, flip status, don't rebuild) vs **net-new** (real new surface):

- **Permissions** — net-new but trivial (subtractive): remove "Always allow" from the Permission card + its builder; keep binary Approve/Deny (+Reply).
- **Console** — confirm/finalize: flip the Console surface / 6-cluster catalog / run bar from `data-status="planned"` → built (the surface is fully drawn; backend wires the feed/route).
- **Retire & Delete** — confirm/finalize: the Retire/Delete footer already exists (Delete ships in v1); touch only if the confirm wording needs a tweak (plain dialog, not type-to-confirm).
- **Library** — confirm/finalize: Library v1 (read+render) is fully drawn. **Do NOT scope new Library design** — write-back / Assets-media / richer-plans are deferred and would exceed the decided v1 cut.
- **Prompt composition** — confirm/finalize (verify-don't-rebuild): the whole prompt composer is already drawn; the work here is backend plumbing, not design. Touch only if you find a missing block variant or polish gap.
- **Settings** — mostly confirm (Account band + Limits band + write affordances exist as `planned`), plus **one net-new:** per-agent MCP-servers + plugins + permission-rule scoping controls in the Create form / Agent panel (their interactivity is a `behavior.js` edit).
- **Agent identity** — net-new (additive), mechanically simple: extend the identity pools **16→25** named `--ag-*` colors and **29→50** icons (new `<symbol>` sprite entries + `AGENT_ICONS` rows in `behavior.js`; the picker count auto-updates off `.length`).
- **Subagent integration** — net-new, the **largest** item: badge relabel `s1`→`A2` (group+member); nested From/To filter tree; Details "Subagents" accordion; Messages nesting. The badge **click behavior** (replace the deliberate `stopPropagation` no-op so a click focuses the parent + opens the Details Subagents accordion + sets the feed filter) is a **`behavior.js`** rewrite. **This item resolves OQ-1 — delete OQ-1 from DESIGN.md's Open Questions register.**

## Guardrails (the tracker carries the detail; these are the ones not to miss)

- **`behavior.js` is where the interactivity lives.** The subagent badge-click and the identity icon-count/picker are `behavior.js` edits, not markup-only — wire them there, shared, or they land dead in the mockup or hardcoded in one file.
- **The gallery's `subagent-badge` and `node-subagents` specimens already exist** (currently marked `undecided`, flat `s0…s4`). The subagent-integration item must **update their markup AND their `data-status`/marker** to the `A2` form + OQ-1 resolution — flip the existing live specimens, don't just append new ones.
- **Subagents are filter-only senders, never addressable targets** — they appear in the From/To *filter* tree but must NOT appear in the Prompt **compose-To** (To stays parents + User). Subagent create/config is out of v1.
- **One DESIGN.md contradiction to reconcile when you touch the From/To description:** it currently says the feed-filter persists "across all four tabs, Inbox included," but the subagent decision's model is "applies universally; tabs with no subagent traffic (Scratch, Inbox) simply match nothing." Make the wording match that inert-on-Inbox model. (DESIGN.md may also still describe the gallery in the older states-catalog terms in places — reconcile to the interactive-catalog model where you touch it.)
- **The Library / prompt-composition items are verify-only** — resist adding Library write-back or new composer pieces; that exceeds the decided v1 cut.
- **The `--ag-*` identity tokens are NAMED, not numbered** (spectral ROYGBIV family, same OKLCH Jewel recipe) — continue the naming convention for the +9; never mint `--ag-17…25`. 25 = unique-color ceiling, 50 = unique-icon ceiling; past ~16 colors the icon is the primary disambiguator and color a soft "family" signal.
- **Two scope-creep traps that are NOT this pass:** the identity picker → sidecar `GET /assets/agent-icons` convergence (that's the parked React-port work — keep the embedded sprite for the static mockup); the Console's `--term-*` → `tokens.css` move (DESIGN documents it as a deliberate scoped exception that stays inline on `.con-feed` — leave it inline).
- **No reference to `TODO.md`** anywhere you write; it is not a decision source, and `design/` references it nowhere (it is also part of the current uncommitted churn — don't mistake its dirty state for in-scope work).

## Exclusions

- **PARKED — the React port:** NO React port, no library-migration work (neobrutalism.dev/shadcn). This is the static-mockup design system only — keep the hand-rolled `tokens.css`/`styles.css`/`behavior.js` and the embedded sprite.
- **Backend wiring belongs to the other stream.** Feed/route endpoints (Console), file/side-store endpoints (Library), path-normalization + sdk passes + stores (prompt composition), write endpoints + live API bands (Settings), wipe/tombstone (Retire & Delete), subagent ingest (subagent integration) — all backend. You draw the surface; you do not wire it. This is the `design/` layer only.

## Working style (ultracode)

**Work in the live working tree — do not spin up isolated git worktrees** (the uncommitted/untracked design baseline would not carry into them; see "current state" above). Most items are independent and touch disjoint regions of the six files, so you may still fan independent research and region-disjoint edits out as concurrent subagents — but they share one working tree, so **partition strictly by file/region to avoid write collisions** and serialize any edit to a shared hotspot (`mockup.html`, `behavior.js`, `DESIGN.md`). Subagent integration is the largest and touches the most files — give it its own lane and land it carefully. You own the sequencing, the integration, and the final verification. Optimize for elapsed time; quality must match a careful single-agent pass.

## Verification (per CLAUDE.md, required — this renders, so static checks are never enough)

Serve over `http://localhost` (the Playwright MCP browser blocks `file:`). Iterate **headless** through the resize-and-click loop at the **narrow and wide extremes** for every surface you touch, and **drive every control you changed** — the new Create-form scoping controls, the nested From/To tree, the Details Subagents accordion, the subagent-badge click (parent-focus + accordion-open + feed-filter), the Console run bar, the identity pickers, the gallery's live specimens. Screenshot each state, compare to the stated intent, fix what's off — then finish with **one headed parity pass** re-screenshotting the touched states at both extremes.

If the Playwright MCP browser drops mid-session (the DEVLOG shows it happening), fall back to headless Chrome over `http://localhost` and keep going — preserve a real rendered comparison; do not degrade to static checks (`node --check`/grep/diff) alone. The gallery must be exhaustive: every touched component present as a live `gx-card`, every variant shown, and any unreachable data-state (disabled/empty/error) labeled.

## Finish

- Append one `DEVLOG.md` entry per the project rule (re-read the file from disk first — the backend stream is appending too): what the design stream produced, the observable outcome, and a `Files:` line.
- Report back with: the per-decision outcome (confirm/finalize vs net-new, and what landed) for all eight; the final list of which `design/` files each item touched; confirmation that OQ-1 is deleted from DESIGN.md's Open Questions register and the From/To Inbox-behavior contradiction is reconciled; and anything you left `data-status="planned"` or `undecided` and why.
