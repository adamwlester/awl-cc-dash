# Glossary retirement & variant conversion: brief for concurrent sessions (2026-07-05)

> Written by the planning session that scoped the retirement run; updated later on 2026-07-05, after that run executed and committed, to cover the follow-on variant run. Audience: any session working in [dev/notes/TODO.md](dev/notes/TODO.md), the roadmap notes, or `design/` while this lane's runs are pending or in flight. The retirement was driven by [dev/prompts/glossary-retirement-run.md](dev/prompts/glossary-retirement-run.md) (now a historical record); the follow-on run is driven by [dev/prompts/variant-sweep-states-page-run.md](dev/prompts/variant-sweep-states-page-run.md). The closing "Standing doctrine" section is self-contained; point any agent doing component or roadmap work at it directly.

## Where this lane stands

The glossary retirement is DONE and committed to `main` (2026-07-05, DEVLOG 02:09 → 03:05, verified against the repo). What landed: `gallery.html` is a frozen, self-contained snapshot at `archive/design/design-v12p7-gallery-retirement/` (all CDN scripts and fonts vendored; renders offline forever; never edited); CLAUDE.md and [design/DESIGN.md](../../../design/DESIGN.md) now describe the five-file design system with the `data-comp` and `data-variants` rules and a runnable Variant-check; the label overlay ([design/label-overlay.js](../../../design/label-overlay.js), Ctrl+L on the mockup) is live. Zero `data-variants` declarations exist yet, by design — closing that gap is exactly what the follow-on run does.

## Next in this lane: the variant sweep + states page run

One further single session (scoped 2026-07-05, operator-approved) executes the two named remainders together, staged and committed per stage in this order:

- **Stage 1 — variant conversion sweep:** every existing component with appearance states the mockup doesn't show gets its `data-variants` declaration, on the element (static markup) or emitted from its builder (JS-generated). The frozen gallery snapshot's labeled specimens are the mining inventory — the reason it was archived self-contained. Attribute-only edits: no visual, styling, or behavioral change is intended anywhere.
- **Stage 2 — states page:** a new dev-tooling page in `design/` (same class as the overlays: outside the five-file system, exempt from propagation) that auto-generates itself from the live tags and renders every declared state side by side. Nothing hand-curated per component, so it structurally cannot drift the way the gallery did.
- **Stage 3 — lint + doc-sync:** a runnable lint that fails loudly on malformed or doctrine-violating declarations, wired into the verify ritual beside the Token-check and Variant-check, plus the doc pass that flips CLAUDE.md's and DESIGN.md's "scheduled sweep / future states page" wording to done.

**Timing decision to be aware of:** DESIGN.md currently says the states page is planned for *after* the second design sprint. On 2026-07-05 the operator deliberately moved it ahead, bundled with the sweep, accepting that sprint 2's badge rework will churn some declarations (each redo is a one-attribute edit). The run updates that DESIGN.md line in stage 3 — a decided change, not a contradiction for anyone to flag.

## What the follow-on run will NOT touch

- [dev/notes/TODO.md](dev/notes/TODO.md) and everything else under `dev/notes/`. The reconciliation sessions own those files; this brief remains the only interface between the two lanes.
- `docs/ARCHITECTURE.md`, `tokens.css`, `styles.css`, component markup structure, or any interaction logic. `mockup.html` gains only `data-variants` attributes on existing `data-comp` roots; `behavior.js` gains only the matching attribute emissions inside builders that already emit `data-comp`.
- The archive snapshot: it is a read-only mining source; the never-edit freeze holds.

## Rewording TODO items that reference the gallery — still pending as of this update

The reconciliation lane owns these rewrites and has not landed them yet. Known references as of 2026-07-05 (run a fresh case-insensitive grep for both "gallery" and "glossary" before relying on this list):

- **[ND] #5d** (settle badge class naming "during the gallery light cleanup"): settle the naming as part of the badge work itself; there is no gallery cleanup anymore.
- **[ND] #6a** (the Messages to Transcript rename "across all six files ... and the gallery"): across the five design files; the archived snapshot is frozen history and is never renamed into.
- **[ND] #11c** (gallery light cleanup: consolidate duplicate sections, add the missing contribution-badge specimen): drop the gallery parts entirely; the contribution badge's hidden states become a `data-variants` declaration on the component instead of a gallery specimen.
- **[BD] BD6** (Full Gallery Audit): delete the item; it is exactly the work the retirement makes unnecessary.
- **[IN] connector-health-badge note** ("register it in the glossary"): tag the component `data-comp="connector-health-badge"` in the mockup and declare its four status variants via `data-variants`.

General rule for any other hit: work formerly owed to the gallery either disappears (catalog cards, specimen upkeep, registry entries) or converts to on-element tagging (`data-comp`, `data-variants`). Nothing new should ever direct work at `gallery.html`.

## Watch-outs while the variant run executes

- `mockup.html` and `behavior.js` receive broad but attribute-only edits during stage 1. If you have concurrent work touching either file, coordinate or wait for the stage-1 commit; merging around a many-line attribute sweep is avoidable pain.
- The run commits per stage, in order: sweep, then states page, then lint + doc-sync. After the stage-1 commit the declarations exist repo-wide; until the stage-3 commit, CLAUDE.md/DESIGN.md still describe the sweep and page in the future tense — expected, not drift.
- A new states-page file appearing in `design/` is expected, not scope creep; it is dev tooling like the overlays.
- `DEVLOG.md` remains the only file both lanes write. It is append-only at the bottom of the Log; a same-moment collision is unlikely and trivially mergeable.

## Standing doctrine: variants and tokens (for all component and roadmap work)

**Variant declarations are a requirement, not a suggestion.** Every component in [design/mockup.html](../../../design/mockup.html) carries its canonical name as a `data-comp` attribute on its root element; JavaScript-built components emit it from inside their builders. The same discipline now extends to variants: when you build or reshape a component that has appearance states the mockup does not currently show (a verdict badge that can be Approve, Revise, or Block but only ever renders one; a disabled, empty, or error look; a status ramp), you declare those states in a `data-variants` attribute on the same element, as space-separated state names, emitted from the builder where the component is generated. One attribute, on the element you are already editing, no second file. Interaction states (hover, focus, active, open/expanded, selected) are reachable by interacting with the live component and are never declared — see DESIGN.md's state ladder for the full split. The auto-generated states page renders every declared variant side by side and a lint check makes missing declarations fail loudly (both delivered by the follow-on run above); the archived gallery covers the visual record of everything as of the retirement date.

**Do not create prose inventories.** Variants are defined on the element (plus at most a one-line code comment). Do not write per-component variant lists into DESIGN.md or any other doc; a hand-maintained parallel inventory is exactly the artifact that just failed and got retired.

**Tokens: new values go through tokens.css, no exceptions.** Any new color, spacing, sizing, radius, or border value belongs in [design/tokens.css](../../../design/tokens.css) and is referenced via `var()`. Reuse an existing token before minting a new one. When you pass a hardcoded value that should be a token, flag it, or fix it if you are confident; never silently ignore it.

**The backfill is scheduled work, not ambient duty.** Of the two named next-phase roadmap items, (1) the variant conversion sweep is now the scoped follow-on run described above, and (2) the token-hygiene audit stays queued until after the second design sprint (sprint 2 recolors and restructures the palette; auditing before it would mint token debris that can never be renamed away). Do not attempt either ambiently while doing unrelated work; half-converted-everywhere is worse than scheduled-and-done. Declare on the components you touch, and leave the rest to the sweep.

**These requirements live in the guiding docs.** The retirement run wrote the `data-comp` and `data-variants` requirements and the token rule into CLAUDE.md's design rules and design/DESIGN.md's Component system section, each with a greppable check in the standing verify ritual, so compliance is enforced by checks rather than adjectives. Roadmap and planning docs should point at those homes rather than restating the rules in different words.
