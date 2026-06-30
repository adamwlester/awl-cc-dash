# Component System Spec: Gallery, Naming, Tokens, and Build Roadmap

**Purpose:** turn the C2 audit and the prior governance decisions into a single buildable spec. This is the artifact the forthcoming coordinating-agent prompt will execute against.

**Inputs:** the C2 audit (`dev/notes/research/c2-audit.md`), the current state of `design/mockup.html`, `design/DESIGN.md`, `design/tokens.css`, and `design/TODO.md`, all read directly.

**Status:** the architecture below is decided. What remains is execution plus a short list of open calls (section 9). This document is governance and a roadmap; it is not a feature backlog. Feature work stays in `TODO.md`; this spec governs how the design system, the gallery, the tokens, and the naming are structured.

**Relationship to the existing docs:** `DESIGN.md` holds intent and rules; `tokens.css` holds every design value; `mockup.html` is where mockup changes land; `TODO.md` is the feature queue. This spec adds two new artifacts (`gallery.html` and `styles.css`) to that set and defines how all of them stay aligned.

---

## 1. Goal

The mockup is the visual authority, but three gaps make it hard to govern as a design system:

1. Its component vocabulary cannot be seen all at once in the running app. The badge families and the inbox card types are the worst cases: most variants are one data state away from being invisible, so there is no single place to compare them.
2. No canonical names are attached to the components. The audit confirmed `data-comp` appears zero times, so names live only in prose and tooltips, not on the elements.
3. The design values are only partly tokenized. `tokens.css` covers color, weight, one radius, and shadow, but border-width, the badge radius, spacing, sizing, and font families are still hardcoded.

The end state this spec drives toward:

- A **component gallery** (`design/gallery.html`) that is the visual catalog: every component shown once, grouped by canonical name, each with a one-line name and purpose blurb.
- **Canonical name tags** (`data-comp`) on every component instance in the mockup, using the audit's names.
- A **shared stylesheet** (`design/styles.css`) extracted from the mockup's inline CSS and linked by both the mockup and the gallery, so the two never diverge.
- **Completed tokenization**: border-width, radius, spacing, sizing, and type all driven by `tokens.css`.
- **`DESIGN.md` reduced to rules and intent**, with its per-component inventory dropped (the gallery owns that now) and the audit's reconciliation edits applied.

## 2. Governing decisions (locked)

These are settled. The roadmap in section 10 assumes them.

| Decision | Detail |
|---|---|
| Gallery is its own file | `design/gallery.html`, not a section inside `mockup.html`. |
| Styling is shared | Extract the mockup's inline CSS into `design/styles.css`; both `mockup.html` and `gallery.html` link it. |
| Values stay single-sourced | `tokens.css` remains the one source of truth for every design value; `styles.css` references tokens via `var()`. |
| `DESIGN.md` is rules only | Intent and patterns; no per-component inventory. The gallery is the visual catalog. |
| Stay static for now | Keep the static HTML mockup; do not port to React or shadcn/ui yet. Flip when design churn approaches zero (see the open call in section 9 and the related `TODO.md` Scratch note on confirming components translate to neobrutalism.dev). |
| One name tag per component | A single `data-comp` attribute on each component instance, carrying the canonical name. |
| No overlay, no hover-card project | No Ctrl+G overlay and no separate per-component hover-card effort; the gallery's own blurbs carry name and purpose. |
| Token expansion scope | Extend tokens beyond color to border-width, radius, spacing, sizing, and type. Semantic alias tokens are confined to padding, gaps, and spacing only; color, radius, and border use primitive tokens directly. |

## 3. Artifact map

| File | Role | Owns | Alignment rule |
|---|---|---|---|
| `design/tokens.css` | Values | Every raw design value (color, type, spacing, radius, sizing, border-width, shadow) | The only place values live. Never rename existing custom properties; the mockup references them in thousands of places. |
| `design/styles.css` (new) | Shared styling | All component CSS, extracted from the mockup's inline block | References tokens via `var()`; links into both the mockup and the gallery. |
| `design/mockup.html` | Working app surface | The live, wired layout and behavior; carries the `data-comp` name tags | Renders identically before and after extraction. Behavior changes land here. |
| `design/gallery.html` (new) | Visual catalog | A static showcase of every component, grouped by name, with blurbs | Shares `styles.css` and `tokens.css`; no component CSS of its own beyond gallery scaffolding. |
| `design/DESIGN.md` | Rules and intent | UI/UX intent, patterns, the design language | Describes rules; points to `tokens.css` for values and to the gallery for the visual catalog. Must agree with the mockup. |
| `design/TODO.md` | Feature queue | The mockup feature backlog and the active "Next up" queue | Out of scope for this spec to edit. Referenced for cross-links only. |
| `design/mockup-toolkit.js` | Existing tool | The Ctrl+G overlay tooling | Unchanged by this spec. |

The alignment invariant: `mockup.html`, `gallery.html`, and `styles.css` all agree on appearance; all design values trace to `tokens.css`; `DESIGN.md` describes the rules behind them.

## 4. Canonical naming convention

- The tag is a single `data-comp` attribute on the **root element** of each component instance. Sub-parts are not tagged; they are identified by their existing classes (for example a node card carries `data-comp`, while its `node-bars` and `node-chip` sub-parts do not).
- The value is the canonical name in **Title Case, Noun Type format** (for example `Status Badge`, `Export Selection Dropdown`, `Agent Node Card`), matching the convention already used in tooltips and references.
- The authoritative name registry is the C2 audit Part 1. The contested families are reproduced compactly below so this spec is self-contained on them; the audit remains the full list.

**Badge names (the catalog the gallery must cover in full):** Status Badge (`.node-badge`, 4 states), Subagent Badge (`.sbadge`, 3 states), Lifecycle Badge (`.dbadge`, 10 states), Verdict Badge (`.vbadge`, 3 states), Count Chip (`.req-badge` / `.cnt-chip` / `.fmt-badge`), Connector Health Badge (`.hbadge`, 4 states), Config-Scope Badge (`.lc-badge`, 2 states), Identity Badge (`.agtile`, 16 colors plus the user variant), Inbox Subtype Badge (`.inbox-subtype`, 2 variants), Overflow Badge (`.badge-more`).

**Inbox card type names:** Error Inbox Card, Warning Inbox Card, Permission Inbox Card, Plan Inbox Card, Decision Inbox Card (the five typed sections, most-to-least urgent).

The user has approved these names, so they are canonical, not proposed.

## 5. Token system: current state and expansion

**Current state** (from `tokens.css`): brand and neobrutalism core colors, three surfaces plus a button surface and a hairline, the muted ramp, semantic signals (success, warning, danger) plus the inbox-permission heading color, soft status containers and badge tints, the 16-color identity palette, two font-weight tokens, one radius (`--radius-base` 5px), the hard-offset shadow, and the boxShadow spacing tokens. The retired `--req-*` family is already flagged "unused, pending review" at the bottom of the file.

**Hardcoded values to bring under tokens** (from the audit plus a direct read of `tokens.css` and the mockup):

| Category | Current state | Target |
|---|---|---|
| Border-width | The 2px navy border is hardcoded as `2px solid var(--border)` throughout; the splitter divider is a separate 3px rule | Add `--border-width` (2px) and a distinct token for the 3px divider; replace the literals. |
| Radius | `--radius-base` is 5px, but badges and chips use a hardcoded 3px (for example `.req-badge` and `.vbadge`) | Add a second radius token (the 3px badge/chip radius) and replace the literal. |
| Spacing | Only boxShadow spacing exists; padding and gaps are hardcoded | Add a spacing scale plus semantic aliases confined to padding and gaps, per the locked scope. |
| Sizing | Badge heights (16px, 18px, 26px), bar heights, and tile sizes are hardcoded | Add sizing tokens for the recurring component dimensions. |
| Type (families) | Font families are not in `tokens.css`; they live in the Tailwind config (`sans: Archivo`, `mono: JetBrains Mono`) and in roughly 75 inline `'JetBrains Mono', monospace` references | Add `--font-sans` (Archivo) and `--font-mono` (JetBrains Mono); replace the inline references so families are single-sourced. The mockup uses Archivo plus JetBrains Mono; there is no Space-family font in the file. |

**The alias rule:** semantic alias tokens are allowed only for padding, gaps, and spacing. Color, radius, border-width, and sizing use primitive tokens directly, with no semantic layer.

**Unused-token audit:** the `--req-*` family (six tokens) is the known retired set, confirmed by the audit, `DESIGN.md`, and the in-file note. The token pass should decide remove versus retain and record the choice. The standing "Need to standardize our badge sizes better" note in `TODO.md` Scratch is the same concern as the sizing-token work and should be satisfied by it.

**Naming continuity:** do not rename existing custom properties. New tokens are additive.

## 6. Gallery contents and structure

- The gallery shows every component in the registry **once**, in a representative state, grouped by canonical name, each with a one-line name and purpose blurb and its `data-comp` name visible.
- It must **exhaustively** enumerate the two families that never co-occur in the running app: the full Badge catalog (all roughly 30 variants across the 11 families) and the 5 inbox card types. These are the gallery's core reason to exist.
- It should also present the composites with their sub-parts labeled (the Agent Node Card is the key one) and the cross-cutting primitives (buttons, split buttons, the merged Export control, segmented controls, tabs, dropdowns and pickers, toggles, steppers, progress bars, accordions, chips, the jump-to-end pill, timeline, marquee, toast, slide-overs).
- Layout is the building agent's call, provided every registry name appears exactly once. A reasonable order is primitives, then the badge catalog, then the inbox types, then composites, but clarity wins over any fixed order.
- The gallery shows only what exists. Planned components (the Team Graph link edges) are marked as planned, not faked.
- The gallery is a static showcase. It does not need the mockup's interactivity; it renders states, not behaviors.

## 7. Behavior policy (wired versus planned in the mockup)

The mockup keeps the wired-behavior categories the audit identified as real: tab switching, the column-tie selection, select-to-act, dropdown open and close, accordions, empty-state gating, cross-panel hand-off, live form state, data-driven rendering, resize and layout, and transient toast feedback.

The not-wired surface carries a **planned-status marker** so dormant code and UI are not mistaken for live behavior. The marker form is an open call (section 9); the proposal is a `data-status="planned"` attribute plus a short code comment cross-referencing the relevant `TODO.md` ID.

Items that should carry the marker (from the audit), with cross-links:

- Link edges (`drawEdges`, `LINKS`, the removed `#edge-layer` host): planned, see `TODO.md` B17.
- Link Agents drawer Save and Delete (`linkSave`, `linkDelete`): toast plus counter only.
- Subagent badge click (`event.stopPropagation()` no-op): see the `TODO.md` Scratch open item on what clicking the subagent icon should do.
- MCP and plugin enable switch (`setSwitch`): scripted demo.
- Console run (`runConsoleCmd`): mock line plus toast.
- Review, citation, and attachment routing (`sendReview`, `gotoCitation`, `composeAttach`, `openAttachment`): toast or navigation only.

## 8. DESIGN.md reconciliation

The audit surfaced these edits. They are part of this spec's scope.

| Edit | Detail |
|---|---|
| Document four badge families | Add Connector Health Badge (`hbadge`), Config-Scope Badge (`lc-badge`), Verdict Badge (`vbadge`), and Inbox Subtype Badge (`inbox-subtype`) to the documented badge set. They are real and in use but absent from the current badge section. |
| Rename the count chip | The per-card inbox request-type badge is retired; the class `.req-badge` now serves as the teal tab count chip. Rename it to a count-chip name in the docs (and consider the class itself during the build). The `--req-*` tokens are already flagged unused. |
| Remove dead splitter markup | The grip nub is `display:none` ("nub removed"); the `.rz-grip` div is vestigial and should be removed from the mockup. The divider is the 3px `.rz-handle::before`. |
| Mark dormant link-edge code | `drawEdges` plus `LINKS` ship but draw nothing (the SVG host was removed). Mark as planned, cross-reference B17. |
| Resolve the subagent error state | Status badges define 4 states; subagent badges define only 3 (no `sb-error`). Decide whether a subagent can error and either add the variant or record that it is intentionally omitted. |
| Drop the per-component inventory | Per the locked decision, `DESIGN.md` no longer carries a component inventory; it points to the gallery. |

## 9. Open decisions (to confirm, not invented here)

These are the genuinely unresolved calls. Each has a recommendation, but the choice is yours.

1. **`data-comp` value format.** Recommendation: the Title Case canonical name (for example `data-comp="Status Badge"`), matching the existing tooltip and reference convention. Alternative: a kebab-case slug. Confirm before the naming pass.
2. **Planned-status marker form.** Recommendation: `data-status="planned"` plus a cross-referencing comment. Confirm before the planned-status pass.
3. **`styles.css` extraction style.** Recommendation: one clean cut, verified by byte-identical render (drive the UI and compare, not just read). Alternative: incremental extraction.
4. **Spacing alias granularity.** The scope is locked (aliases confined to padding and gaps), but how many semantic aliases versus a raw scale is a judgment call left to the building agent.
5. **`sb-error` and subagent-click behavior.** Tied together; both are open in `TODO.md`. Resolve as part of section 8 or defer explicitly.
6. **React migration trigger.** Stated as a condition, not a date: flip when design churn approaches zero. The `TODO.md` Scratch note on confirming neobrutalism.dev translation is the gating check.
7. **Where the roadmap is tracked.** Whether to promote section 10 into `TODO.md` Next up or to drive it solely through the forthcoming coordinating-agent prompt.

## 10. Build roadmap

Dependency-ordered phases with acceptance criteria, structured so a coordinating agent can fan the work out and order it. Phase 0 is foundational and blocking; phases 1 and 2 can run in parallel after it; phase 3 follows; phase 4 is last; phase 5 is flexible.

**Phase 0: Extract the shared stylesheet (blocking).**
Move the mockup's inline component CSS into `design/styles.css` and link it from `mockup.html`.
- Acceptance: the mockup renders byte-identically (verified by driving the UI, not just by reading); no value is moved out of `tokens.css`; `styles.css` references tokens via `var()`.
- Dependency: none. Blocks the gallery, which shares this file.

**Phase 1: Complete tokenization (parallel with phase 2).**
Add the border-width, second radius, spacing scale plus aliases, sizing, and font-family tokens to `tokens.css`; replace the hardcoded literals in `styles.css`; resolve the unused `--req-*` family.
- Acceptance: for the covered categories, no hardcoded 2px or 3px border or radius literals, no inline font-family references, and no untokenized recurring padding, gap, or sizing values remain in `styles.css`; the render is unchanged; the `DESIGN.md` token rules are updated to match.
- Dependency: phase 0 (the edits land in `styles.css`).

**Phase 2: Add canonical name tags (parallel with phase 1).**
Add `data-comp` tags to every component instance in `mockup.html`, using the audit registry names and the confirmed value format.
- Acceptance: every name in the registry appears on at least one element; names follow the Title Case convention; there is no behavior or render change.
- Dependency: phase 0 preferred (tags land in the post-extraction mockup); the coordinating agent sequences this against phase 1.

**Phase 3: Reconcile DESIGN.md.**
Apply the section 8 edits: document the four badge families, rename the count chip, remove the dead `.rz-grip` markup, mark the dormant link-edge code as planned, resolve or flag `sb-error`, and drop the per-component inventory.
- Acceptance: `DESIGN.md` and the mockup agree; `DESIGN.md` holds rules and intent only and points to the gallery for the catalog.
- Dependency: phases 1 and 2 (names and tokens settled).

**Phase 4: Build the gallery.**
Create `design/gallery.html` linking `styles.css` and `tokens.css`; render every registry component once, grouped by name, with name and purpose blurbs and the `data-comp` name visible; enumerate the full badge catalog and the five inbox types; label the composite sub-parts; mark planned components.
- Acceptance: every registry name is shown exactly once; the roughly 30 badge variants and the 5 inbox types are all visible; the gallery shares styling with the mockup with no divergent component CSS; planned items are marked, not faked.
- Dependency: phases 0 through 3.

**Phase 5: Planned-status pass on the mockup (flexible).**
Apply the confirmed planned-status marker to the not-wired items in section 7, with cross-references to the relevant `TODO.md` IDs in comments.
- Acceptance: every not-wired item carries the marker; the cross-references are present.
- Dependency: phase 2 (naming), loosely; can run alongside phase 3.

**Invariants across all phases:** the mockup's render stays unchanged through extraction and tokenization (the value layer explicitly aims for byte-for-byte stability); the name registry and the gallery are both exhaustive; and no design value lives anywhere but `tokens.css`.
