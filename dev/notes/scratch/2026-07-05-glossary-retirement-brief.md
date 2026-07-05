# Glossary retirement: brief for concurrent sessions (2026-07-05)

> Written by the planning session that scoped the retirement run, before the run executes. Audience: any session working in [dev/notes/TODO.md](dev/notes/TODO.md), the roadmap notes, or `design/` while the run is pending or in flight. The run itself is driven by [dev/prompts/glossary-retirement-run.md](dev/prompts/glossary-retirement-run.md). The closing "Standing doctrine" section is self-contained; point any agent doing component or roadmap work at it directly.

## What is happening

The design-system glossary is being retired, not repaired. "Glossary" means two things: the interactive component catalog [design/gallery.html](design/gallery.html) and the per-component registry list in the Component system section of [design/DESIGN.md](design/DESIGN.md). Both are bloated and unmaintained; the decision was pressure-tested across multiple planning sessions and re-verified against the repo on 2026-07-05. A single dedicated run executes the retirement.

## What the run will change

- `gallery.html` leaves `design/` for a frozen, self-contained snapshot under `archive/design/` (with its own copies of `tokens.css`, `styles.css`, `behavior.js`, so it renders identically forever). The snapshot is history: it is never edited and no future work targets it.
- CLAUDE.md and design/DESIGN.md lose every gallery obligation: the six-file design system becomes five files, the "add a gallery card for every component" rule dies, and the registry list is removed. The `data-comp` name tags on components stay and remain required.
- New doctrine lands in those same docs: the `data-variants` declaration requirement (see Standing doctrine below) and the classification of dev-only view tooling (`mockup-toolkit.js` and the new label overlay) as outside the design-system propagation rules.
- A new dev-only label overlay is added: its own small file in `design/`, loaded by `mockup.html` with one script tag, toggled by a keystroke, drawing each component's `data-comp` name over the live mockup. It stores nothing per component, so it cannot go stale; renames and layout changes flow through it automatically.
- Light hygiene: stale comments in `behavior.js` and `styles.css` that point at the gallery get updated. No code or styling changes.

## What the run will NOT touch

- [dev/notes/TODO.md](dev/notes/TODO.md) and everything else under `dev/notes/`. The reconciliation sessions own those files; this brief is the only interface between the two lanes.
- `docs/ARCHITECTURE.md`, `tokens.css` values, component markup, styles, or behavior. `mockup.html` gains exactly one script tag.
- The states page (a future auto-generated page that renders every declared variant side by side) is deliberately NOT built in this run; it waits until the second design sprint settles the badge churn. Until it exists, the archived gallery snapshot is the visual record of every variant as of today.

## Rewording TODO items that reference the gallery

Known references as of 2026-07-05 (run a fresh case-insensitive grep for both "gallery" and "glossary" before relying on this list):

- **[ND] #5d** (settle badge class naming "during the gallery light cleanup"): settle the naming as part of the badge work itself; there is no gallery cleanup anymore.
- **[ND] #6a** (the Messages to Transcript rename "across all six files ... and the gallery"): across the five design files; the archived snapshot is frozen history and is never renamed into.
- **[ND] #11c** (gallery light cleanup: consolidate duplicate sections, add the missing contribution-badge specimen): drop the gallery parts entirely; the contribution badge's hidden states become a `data-variants` declaration on the component instead of a gallery specimen.
- **[BD] BD6** (Full Gallery Audit): delete the item; it is exactly the work the retirement makes unnecessary.
- **[IN] connector-health-badge note** ("register it in the glossary"): tag the component `data-comp="connector-health-badge"` in the mockup and declare its four status variants via `data-variants`.

General rule for any other hit: work formerly owed to the gallery either disappears (catalog cards, specimen upkeep, registry entries) or converts to on-element tagging (`data-comp`, `data-variants`). Nothing new should ever direct work at `gallery.html`.

## Watch-outs while the run executes

- `DEVLOG.md` is the only file both lanes write. It is append-only at the bottom of the Log; a same-moment collision is unlikely and trivially mergeable.
- The run commits per stage, in order: archive snapshot, then doc surgery, then overlay. Everything the second sprint depends on is committed at the end of the doc-surgery stage; the overlay stage is safe to overlap with anything.
- If `gallery.html` is missing from `design/` mid-run, that is expected; its snapshot lives under `archive/design/`.

## Standing doctrine: variants and tokens (for all component and roadmap work)

**Variant declarations are a requirement, not a suggestion.** Every component in [design/mockup.html](design/mockup.html) carries its canonical name as a `data-comp` attribute on its root element; JavaScript-built components emit it from inside their builders. The same discipline now extends to variants: when you build or reshape a component that has appearance states the mockup does not currently show (a verdict badge that can be Approve, Revise, or Block but only ever renders one; a disabled, empty, or error look; a status ramp), you declare those states in a `data-variants` attribute on the same element, as space-separated state names, emitted from the builder where the component is generated. One attribute, on the element you are already editing, no second file. A future auto-generated states page will render every declared variant side by side, and a lint check will make missing declarations fail loudly; the archived gallery covers the visual record until then.

**Do not create prose inventories.** Variants are defined on the element (plus at most a one-line code comment). Do not write per-component variant lists into DESIGN.md or any other doc; a hand-maintained parallel inventory is exactly the artifact that just failed and got retired.

**Tokens: new values go through tokens.css, no exceptions.** Any new color, spacing, sizing, radius, or border value belongs in [design/tokens.css](design/tokens.css) and is referenced via `var()`. Reuse an existing token before minting a new one. When you pass a hardcoded value that should be a token, flag it, or fix it if you are confident; never silently ignore it.

**The backfill is scheduled work, not ambient duty.** Two items belong in the next-phase roadmap as named tasks: (1) a variant conversion sweep that walks the existing components and adds `data-variants` declarations wherever states are hidden today, and (2) a token-hygiene audit that finds and converts hardcoded values across the mockup and styles. Do not attempt either ambiently while doing unrelated work; half-converted-everywhere is worse than scheduled-and-done.

**These requirements must live in the guiding docs.** The retirement run writes the `data-comp` and `data-variants` requirements and the token rule into CLAUDE.md's design rules and design/DESIGN.md's Component system section, each with a greppable check in the standing verify ritual, so compliance is enforced by checks rather than adjectives. Roadmap and planning docs should point at those homes rather than restating the rules in different words.
