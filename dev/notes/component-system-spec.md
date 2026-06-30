# Component System Spec: Gallery, Naming, Tokens, and Build Roadmap

**Purpose:** turn the component inventory audit and the prior governance decisions into a single buildable spec. This is the artifact the forthcoming coordinating-agent prompt executes against.

**Inputs:** the component inventory audit (`dev/notes/component-inventory-and-wiring.md`) and the current state of `design/mockup.html`, `design/DESIGN.md`, and `design/tokens.css`, all read directly. The live mockup is the source of truth for the exact component instances and design values; this spec fixes the conventions, the families that never co-occur, and the build order. The audit is a historical input: the building agent works from this spec plus the live mockup, not from the audit.

**Status:** the architecture below is decided. What remains is execution plus one parked Open Question (section 9). This document is governance and a roadmap; it is not a feature backlog.

**Lifecycle:** this spec is build input, not a permanent design doc. Once the build lands, its durable content migrates into the permanent design files per the distribution map in section 8, and the spec retires (it stays in `dev/notes/` as a historical planning record). The five permanent design sources after the build are `design/tokens.css`, `design/styles.css`, `design/mockup.html`, `design/gallery.html`, and `design/DESIGN.md`.

**Relationship to the existing docs:** `DESIGN.md` holds intent and rules; `tokens.css` holds every design value; `mockup.html` is where mockup changes land. This spec adds two new artifacts (`gallery.html` and `styles.css`) to that set and defines how all of them stay aligned. This spec does not reference or depend on `TODO.md`; that backlog is maintained separately and is out of scope here.

---

## 1. Goal

The mockup is the visual authority, but three gaps make it hard to govern as a design system:

1. Its component vocabulary cannot be seen all at once in the running app. The badge families and the inbox card types are the worst cases: most variants are one data state away from being invisible, so there is no single place to compare them.
2. No canonical names are attached to the components. The audit confirmed `data-comp` appears zero times, so names live only in prose and tooltips, not on the elements.
3. The design values are only partly tokenized. `tokens.css` covers color, weight, one radius, and shadow, but border-width, the badge radius, spacing, sizing, and font families are still hardcoded.

The end state this spec drives toward:

- A **component gallery** (`design/gallery.html`) that is the visual catalog: every component shown once, grouped by canonical name, each with a one-line name and purpose blurb.
- **Canonical name tags** (`data-comp`) on every component instance in the mockup, using the audit's names in slug form.
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
| Stay static for now | Keep the static HTML mockup; do not port to React or shadcn/ui yet. Flip when design churn approaches zero (see the standing condition in section 9). |
| One name tag per component | A single `data-comp` attribute on each component instance, carrying the canonical name as a **kebab-case slug**. |
| Name format is slug-only | `data-comp` is a kebab-case slug (`status-badge`), single-sourced. There is no parallel Title Case registry to maintain; where a doc or the gallery needs a readable name, it is the same name written in words, derived from the slug, not a second tracked string. |
| Status marker is an attribute | Dormant or unresolved UI is tagged with a `data-status` attribute: `planned` for shipped-but-not-wired code, `undecided` for an unresolved design question (section 9). Live, wired components carry no marker. |
| Extraction method is the agent's call | How the inline CSS is lifted into `styles.css` (one cut or incremental) is the building agent's choice. The acceptance bar is fixed: the mockup must render identically before and after (verified by driving the UI, not just reading), and no value may leave `tokens.css`. |
| No overlay, no hover-card project | No Ctrl+G overlay and no separate per-component hover-card effort; the gallery's own blurbs carry name and purpose. |
| Token expansion scope | Extend tokens beyond color to border-width, radius, spacing, sizing, and type. Semantic alias tokens are confined to padding, gaps, and spacing only; color, radius, border, and sizing use primitive tokens directly. |

## 3. Artifact map

| File | Role | Owns | Alignment rule |
|---|---|---|---|
| `design/tokens.css` | Values | Every raw design value (color, type, spacing, radius, sizing, border-width, shadow) | The only place values live. Never rename existing custom properties; the mockup references them in thousands of places. |
| `design/styles.css` (new) | Shared styling | All component CSS, extracted from the mockup's inline block | References tokens via `var()`; links into both the mockup and the gallery. |
| `design/mockup.html` | Working app surface | The live, wired layout and behavior; carries the `data-comp` name tags and the `data-status` markers | Renders identically before and after extraction. Behavior changes land here. |
| `design/gallery.html` (new) | Visual catalog | A static showcase of every component, grouped by name, with blurbs | Shares `styles.css` and `tokens.css`; no component CSS of its own beyond gallery scaffolding. |
| `design/DESIGN.md` | Rules and intent | UI/UX intent, patterns, the design language, the naming and token rules, and the Open Questions register | Describes rules; points to `tokens.css` for values and to the gallery for the visual catalog. Must agree with the mockup. |
| `design/mockup-toolkit.js` | Existing tool | The Ctrl+G overlay tooling | Unchanged by this spec. |

The alignment invariant: `mockup.html`, `gallery.html`, and `styles.css` all agree on appearance; all design values trace to `tokens.css`; `DESIGN.md` describes the rules behind them.

## 4. Canonical naming convention

- The tag is a single `data-comp` attribute on the **root element** of each component instance. Sub-parts are not tagged; they are identified by their existing classes (for example a node card carries `data-comp`, while its `node-bars` and `node-chip` sub-parts do not).
- The value is a **kebab-case slug** derived from the canonical name in Noun-Type form: `status-badge`, `export-selection-dropdown`, `agent-node-card`. This is the one canonical label per component. It is single-sourced on the element; the gallery and any doc that needs a readable name spell the same slug out in words rather than maintaining a separate string.
- This spec fixes the naming convention and enumerates the two families that never co-occur (below). The **full set of component instances to tag is read from the live mockup at build time**, not from a frozen list, since the mockup is actively edited. The audit's Part 1 is the reference for how the families were derived, not a list to copy verbatim.
- **Many components are JavaScript-generated, not static markup.** A large part of the badge catalog (the Lifecycle badge family `.db-*`, the Verdict badge, the count-chip values, and the identity badges) and all five inbox card types are emitted by template functions (`inboxCardHTML`, `verdictBadgeHTML`, `renderInbox`, `renderFeed`, over the `REQS` / `MSGS` / `db-*` data), not written as static HTML. Tagging is therefore not a grep-the-HTML pass: emit the `data-comp` slug from inside those builder functions so every rendered instance carries it. "Read the full set from the live mockup" means accounting for the JS-built variants, not only what is statically present.

**Badge names (the catalog the gallery must cover in full), shown as readable name then slug:** Status Badge `status-badge` (`.node-badge`, 4 states), Subagent Badge `subagent-badge` (`.sbadge`, 3 states), Lifecycle Badge `lifecycle-badge` (`.dbadge`, 10 states), Verdict Badge `verdict-badge` (`.vbadge`, 3 states), Count Chip `count-chip` (`.req-badge` / `.cnt-chip` / `.fmt-badge`), Connector Health Badge `connector-health-badge` (`.hbadge`, 4 states), Config-Scope Badge `config-scope-badge` (`.lc-badge`, 2 states), Identity Badge `identity-badge` (`.agtile`, 16 colors plus the user variant), Inbox Subtype Badge `inbox-subtype-badge` (`.inbox-subtype`, 2 variants), Overflow Badge `overflow-badge` (`.badge-more`).

**Inbox card type names:** Error Inbox Card `error-inbox-card`, Warning Inbox Card `warning-inbox-card`, Permission Inbox Card `permission-inbox-card`, Plan Inbox Card `plan-inbox-card`, Decision Inbox Card `decision-inbox-card` (the five typed sections, most-to-least urgent).

The user has approved these names, so they are canonical, not proposed. The building agent slugifies any additional component names it tags from the live mockup using the same kebab-case rule.

## 5. Token system: current state and expansion

**Read the live files as the authoritative state.** `tokens.css` and `mockup.html` are actively edited; the table below names the categories to tokenize, but the building agent reads the current files for the exact literals rather than trusting any frozen snapshot. As one concrete example, the recent icon-fill agent-card work added the `--node-tint` and `--node-icon-pct` knobs, the behind-content `.node-bg` SVG layer, and the `.agtile--me` human-tile cameo; those `--node-*` knobs are additional tokenization targets to fold in.

**Current state** (orientation, from `tokens.css`): brand and neobrutalism core colors, three surfaces plus a button surface and a hairline, the muted ramp, semantic signals (success, warning, danger) plus the inbox-permission heading color, soft status containers and badge tints, the 16-color identity palette, two font-weight tokens, one radius (`--radius-base` 5px), the hard-offset shadow, and the boxShadow spacing tokens. The retired `--req-*` family is already flagged "unused, pending review" at the bottom of the file.

**Hardcoded values to bring under tokens:**

| Category | Current state | Target |
|---|---|---|
| Border-width | The 2px navy border is hardcoded as `2px solid var(--border)` throughout; the splitter divider is a separate 3px rule | Add `--border-width` (2px) and a distinct token for the 3px divider; replace the literals. |
| Radius | `--radius-base` is 5px, but badges and chips use a hardcoded 3px (for example `.req-badge` and `.vbadge`) | Add a second radius token (the 3px badge/chip radius) and replace the literal. |
| Spacing | Only boxShadow spacing exists; padding and gaps are hardcoded | Add a spacing scale plus semantic aliases confined to padding and gaps, per the locked scope. |
| Sizing | Badge heights (16px, 18px, 26px), bar heights, tile sizes, and the icon-fill `--node-*` knobs are hardcoded | Add sizing tokens for the recurring component dimensions. |
| Type (families) | Font families are not in `tokens.css`; they live in the Tailwind config (`sans: Archivo`, `mono: JetBrains Mono`) and in roughly 75 inline `'JetBrains Mono', monospace` references | Add `--font-sans` (Archivo) and `--font-mono` (JetBrains Mono); replace the inline references so families are single-sourced. The mockup uses Archivo plus JetBrains Mono; there is no Space-family font in the file. |

**The alias rule:** semantic alias tokens are allowed only for padding, gaps, and spacing. Color, radius, border-width, and sizing use primitive tokens directly, with no semantic layer. How many aliases versus a raw scale is the building agent's judgment within that locked scope.

**What stays out of `tokens.css`:** tokens are for global, reused design values only. Do not tokenize per-instance bindings (for example `--nc`, the per-card custom property that binds one of the 16 `--ag-*` identity colors to a single agent) or data-driven and runtime values (for example a progress bar's inline `width:68%`, resizable pane widths, or anything that reflects state rather than design). Those stay inline. The `--node-*` knobs named above are global and do belong in `tokens.css`; `--nc` and the bar fills do not. The render-identical gate catches a binding collapsed to one value, but a wrongly tokenized data value can render identically and still be wrong, so apply the global-versus-instance test deliberately.

**Unused-token audit:** the `--req-*` family (six tokens) is the known retired set, confirmed by the audit, `DESIGN.md`, and the in-file note. The token pass should decide remove versus retain and record the choice.

**Naming continuity:** do not rename existing custom properties. New tokens are additive.

## 6. Gallery contents and structure

- The gallery shows every component in the registry **once**, in a representative state, grouped by canonical name, each with a one-line name and purpose blurb and its `data-comp` slug visible.
- It must **exhaustively** enumerate the two families that never co-occur in the running app: the full Badge catalog (all roughly 30 variants across the 11 families) and the 5 inbox card types. These are the gallery's core reason to exist.
- **Author static specimens for the JavaScript-generated variants.** Because the Lifecycle and Verdict badges, the count chips, and the inbox card types are produced by template functions from data arrays, they will not land in the gallery by copying static markup; the build renders or hand-writes a static specimen of each JS-only variant (styled by the same `styles.css`) so the full catalog is visible at once.
- It should also present the composites with their sub-parts labeled (the Agent Node Card is the key one) and the cross-cutting primitives (buttons, split buttons, the merged Export control, segmented controls, tabs, dropdowns and pickers, toggles, steppers, progress bars, accordions, chips, the jump-to-end pill, timeline, marquee, toast, slide-overs).
- Layout is the building agent's call, provided every registry name appears exactly once. A reasonable order is primitives, then the badge catalog, then the inbox types, then composites, but clarity wins over any fixed order.
- The gallery shows only what exists. Planned components (the Team Graph link edges) are marked `planned`; components tied to an open design question are marked `undecided`. Neither is faked.
- The gallery is a static showcase. It does not need the mockup's interactivity; it renders states, not behaviors.

## 7. Behavior policy (wired versus planned in the mockup)

The mockup keeps the wired-behavior categories the audit identified as real: tab switching, the column-tie selection, select-to-act, dropdown open and close, accordions, empty-state gating, cross-panel hand-off, live form state, data-driven rendering, resize and layout, and transient toast feedback.

The not-wired surface carries the **`data-status="planned"`** marker so dormant code and UI are not mistaken for live behavior. The marker is the attribute alone (optionally with a short plain-language code comment naming what it is); it does not cross-reference any external backlog.

Items that should carry the marker (from the audit):

- Link edges (`drawEdges`, `LINKS`, the removed `#edge-layer` host): shipped but draws nothing.
- Link Agents drawer Save and Delete (`linkSave`, `linkDelete`): toast plus counter only.
- Subagent badge click (`event.stopPropagation()` no-op): also an Open Question (section 9), so it additionally carries `undecided`.
- MCP and plugin enable switch (`setSwitch`): scripted demo.
- Console run (`runConsoleCmd`): mock line plus toast.
- Review, citation, and attachment routing (`sendReview`, `gotoCitation`, `composeAttach`, `openAttachment`): toast or navigation only.

## 8. DESIGN.md reconciliation and doc distribution

**Reconciliation edits** the audit surfaced (part of this spec's scope):

| Edit | Detail |
|---|---|
| Document four badge families | Add Connector Health Badge (`hbadge`), Config-Scope Badge (`lc-badge`), Verdict Badge (`vbadge`), and Inbox Subtype Badge (`inbox-subtype`) to the documented badge set. They are real and in use but absent from the current badge section. |
| Rename the count chip | The per-card inbox request-type badge is retired; the class `.req-badge` now serves as the teal tab count chip. Rename it to a count-chip name in the docs (and consider the class itself during the build). The `--req-*` tokens are already flagged unused. |
| Remove dead splitter markup | The grip nub is `display:none` ("nub removed"); the `.rz-grip` div is vestigial and should be removed from the mockup. The divider is the 3px `.rz-handle::before`. |
| Mark dormant link-edge code | `drawEdges` plus `LINKS` ship but draw nothing (the SVG host was removed). Mark `planned`. |
| Record the subagent error state | Status badges define 4 states; subagent badges define only 3 (no `sb-error`). This is unresolved, so record it in the Open Questions register (section 9) rather than forcing a decision. |
| Drop the per-component inventory | Per the locked decision, `DESIGN.md` no longer carries a component inventory; it points to the gallery. |

**Doc distribution (so the spec can fully retire).** When the build completes, the spec's durable content lands in the permanent files as follows; nothing of value is left only in the spec:

| Spec content | Permanent home |
|---|---|
| Design values (tokens, the new border/radius/spacing/sizing/type tokens) | `design/tokens.css` |
| Component CSS (the extracted, tokenized styling) | `design/styles.css` |
| `data-comp` slugs and `data-status` markers on elements | `design/mockup.html` |
| The visual catalog and each component's name and purpose blurb | `design/gallery.html` |
| The naming convention, the token rules and alias rule, the `data-status` convention, the behavior-wiring policy, and the Open Questions register | `design/DESIGN.md` |

Concretely, the section 2 governing rules and the section 4, 5, 7, and 9 conventions are absorbed into `DESIGN.md` prose during reconciliation. After that, the spec is purely historical.

## 9. Open Questions register (undecided)

The mechanism for items that are deliberately not yet decided, kept distinct from planned-but-dormant code:

- Each item gets a stable ID, a one-line question, and `status: undecided`.
- Where the question attaches to a concrete element, that element (and its gallery specimen) carries `data-status="undecided"`, mirroring the `planned` marker, so the open item is visible both as a scannable list and as a tag on the thing itself.
- The register's durable home is `DESIGN.md` (it migrates there at reconciliation). Resolving an item means deleting its register line and removing the element marker; nothing forces a resolution to ship.

**Open items:**

- **OQ-1: subagent error state and subagent-click behavior.** Status badges have an error state but subagent badges have no `sb-error`; separately, clicking a subagent badge is a deliberate no-op. Both are unresolved and tied together (what, if anything, an errored or clicked subagent should show or do). Parked as `undecided`; the subagent badge carries the marker.

**Standing condition (not an open question, a deferred trigger):** the React/shadcn migration flips when design churn approaches zero. It is a condition on timing, not an undecided design call, so it lives here as a note rather than as a register item.

## 10. Build roadmap

Dependency-ordered phases with acceptance criteria, structured so a coordinating agent can fan the work out and order it. Phase 0 is foundational and blocking; phases 1 and 2 can run in parallel after it; phase 3 follows; phase 4 is last; phase 5 is flexible.

**Phase 0: Extract the shared stylesheet (blocking).**
Move the mockup's inline component CSS into `design/styles.css` and link it from `mockup.html`.
- Acceptance: the mockup renders identically (verified by driving the UI, not just by reading); no value is moved out of `tokens.css`; `styles.css` references tokens via `var()`.
- Dependency: none. Blocks the gallery, which shares this file.

**Phase 1: Complete tokenization (parallel with phase 2).**
Add the border-width, second radius, spacing scale plus aliases, sizing (including the `--node-*` knobs), and font-family tokens to `tokens.css`; replace the hardcoded literals in `styles.css`; resolve the unused `--req-*` family.
- Acceptance: for the covered categories, no hardcoded 2px or 3px border or radius literals, no inline font-family references, and no untokenized recurring padding, gap, or sizing values remain in `styles.css`; the render is unchanged; the `DESIGN.md` token rules are updated to match.
- Dependency: phase 0 (the edits land in `styles.css`).

**Phase 2: Add canonical name tags (parallel with phase 1).**
Add `data-comp` slug tags to every component instance in `mockup.html`, reading the live mockup for the full instance set and slugifying per section 4.
- Acceptance: every name in the registry appears on at least one element; slugs follow the kebab-case convention; there is no behavior or render change.
- Dependency: phase 0 preferred (tags land in the post-extraction mockup); the coordinating agent sequences this against phase 1.

**Phase 3: Reconcile DESIGN.md and absorb the spec rules.**
Apply the section 8 reconciliation edits (document the four badge families, rename the count chip, remove the dead `.rz-grip` markup, mark the dormant link-edge code `planned`, record `sb-error`/subagent-click in the Open Questions register, drop the per-component inventory). Then absorb the spec's governing rules and conventions into `DESIGN.md` per the section 8 distribution map, and seed the Open Questions register.
- Acceptance: `DESIGN.md` and the mockup agree; `DESIGN.md` holds rules and intent only and points to the gallery for the catalog; the naming, token, `data-status`, and behavior rules plus the Open Questions register are present in `DESIGN.md`.
- Dependency: phases 1 and 2 (names and tokens settled).

**Phase 4: Build the gallery.**
Create `design/gallery.html` linking `styles.css` and `tokens.css`; render every registry component once, grouped by name, with name and purpose blurbs and the `data-comp` slug visible; enumerate the full badge catalog and the five inbox types; label the composite sub-parts; mark `planned` and `undecided` components.
- Acceptance: every registry name is shown exactly once; the roughly 30 badge variants and the 5 inbox types are all visible; the gallery shares styling with the mockup with no divergent component CSS; planned and undecided items are marked, not faked.
- Dependency: phases 0 through 3.

**Phase 5: Status-marker pass on the mockup (flexible).**
Apply `data-status="planned"` to the not-wired items in section 7 and `data-status="undecided"` to the open-question elements in section 9.
- Acceptance: every not-wired item carries the `planned` marker; every open-question element carries the `undecided` marker; no external backlog is referenced.
- Dependency: phase 2 (naming), loosely; can run alongside phase 3.

**Invariants across all phases:**
- The mockup's render stays unchanged through extraction and tokenization (the value layer explicitly aims for byte-for-byte stability).
- The name registry and the gallery are both exhaustive.
- No design value lives anywhere but `tokens.css`.
- Nothing in this build references `TODO.md`.
- **Verification, after Phase 3:** confirm that `dev/notes/coverage-map.md`'s citations of `DESIGN.md` sections still resolve, since the reconciliation reorganizes `DESIGN.md`. This is the one seam with the separate build-status workstream; fix any stale section pointers.
