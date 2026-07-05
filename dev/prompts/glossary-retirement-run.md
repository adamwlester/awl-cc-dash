# Glossary retirement run

> Single session, executed on Fable 5 or Opus 4.8 at maximum effort. Work on `main`; commit at the end of each stage; never create a branch (repo rule). Every behavioral rule in [CLAUDE.md](CLAUDE.md) binds this run: DEVLOG logging, headed UI verification, `.scratch/` for transient artifacts, clarity-first reporting.

## Context

You are executing a decided, pressure-tested refactor. The design-system glossary, meaning the interactive catalog [design/gallery.html](design/gallery.html) plus the per-component registry in the Component system section of [design/DESIGN.md](design/DESIGN.md), is bloated and unmaintained and is being retired rather than repaired. The decision record, the replacement doctrine, and the interface to the concurrent TODO-reconciliation sessions all live in [dev/notes/scratch/2026-07-05-glossary-retirement-brief.md](dev/notes/scratch/2026-07-05-glossary-retirement-brief.md); read it in full and treat its Standing doctrine section as the source text for the rules you will install. Your job is execution, not re-litigation. If the repo genuinely contradicts this prompt anywhere, stop and flag it rather than improvising.

## Read first

- [CLAUDE.md](CLAUDE.md) in full, especially the design rules, DEVLOG rule, and Verifying UI changes.
- The brief above, in full.
- [design/DESIGN.md](design/DESIGN.md): the "About this doc" bullets at the top and the entire Component system section at the end.
- The tail of [DEVLOG.md](DEVLOG.md), plus `git log` since 2026-07-05, to confirm nothing has landed in `design/`, CLAUDE.md, or DESIGN.md that this prompt does not know about. The plan was verified against the repo as of 2026-07-05 (last DEVLOG entry 01:21:25).
- How the files relate: `mockup.html` and `gallery.html` both link `tokens.css` and `styles.css` and load `behavior.js`; `mockup.html` additionally loads `mockup-toolkit.js`, which is dev tooling outside the design system. `data-comp` tags appear on roughly 190 component instances in `mockup.html` and are emitted from the builder functions in `behavior.js`.

## Hard boundaries

- Do NOT edit [dev/notes/TODO.md](dev/notes/TODO.md) or anything under `dev/notes/`. Concurrent sessions own those files; the brief already tells them how to reword gallery references. The brief itself is read-only input to you.
- Do NOT build the states page and do NOT do a `data-variants` backfill sweep. This run installs the rule, not the inventory.
- Do NOT change `tokens.css` values, component markup, styles, or behavior. `mockup.html` gains exactly one script tag (stage 3); `behavior.js` and `styles.css` may only have stale gallery comments updated.
- Historical material keeps its gallery mentions untouched: `dev/prompts/`, `archive/`, existing DEVLOG entries, and everything under `dev/notes/`.
- Commit to `main` at the end of each stage, in order, so the run is cut-safe from the tail; write the stage's DEVLOG entry before its commit.

## Stage 1: archive the gallery as a frozen, self-contained snapshot

- Follow the existing whole-folder snapshot convention in `archive/design/` (see `archive/design/design-v12p5/` and siblings: full copies whose relative links resolve internally). Create a new snapshot folder named per the current lineage (check the newest existing `design-v*` folder and increment, with a suffix marking it as the gallery-retirement snapshot).
- The snapshot must contain `gallery.html` plus copies of `tokens.css`, `styles.css`, and `behavior.js` (the agent-icon sprite is already embedded in `gallery.html`). Verify the relative hrefs resolve inside the folder.
- `gallery.html` also loads two content-delivery-network (CDN) scripts: Tailwind from cdn.tailwindcss.com and Lucide from unpkg.com. Vendor local copies into the snapshot and repoint those script tags if fetching is possible from your environment; if not, record the CDN dependency in the banner instead.
- Add a prominent banner to the top of the archived `gallery.html` (visible in the rendered page, not only a code comment): frozen 2026-07-05; retired in favor of on-element tagging (`data-comp` / `data-variants`) and the label overlay; never edit; the living rules are in `design/DESIGN.md`.
- Delete `gallery.html` from `design/`.
- Verify the archived snapshot actually renders by driving it with [dev/tools/ui-verify/](dev/tools/ui-verify/README.md) (headed, parked; screenshots to `.scratch/`). Confirm specimens render with real styling and icons, not as unstyled fragments.
- DEVLOG entry, then commit.

## Stage 2: documentation surgery (the gate the second design sprint waits on)

- [CLAUDE.md](CLAUDE.md): the `design/` folder-map row, the "Design changes" rule block, and the propagation rule all describe a six-file system with gallery obligations. Rewrite them to the five-file system (`tokens.css`, `styles.css`, `behavior.js`, `mockup.html`, `DESIGN.md`). Keep everything about `data-comp` tagging and token discipline. Remove every gallery duty (the gx-card rule and the gallery leg of verification). Add the `data-variants` requirement and classify dev-only view tooling (`mockup-toolkit.js`, the new label overlay) as outside the propagation rule.
- [design/DESIGN.md](design/DESIGN.md): sweep the whole file, not just the tail. The "About this doc" six-file bullet near the top, the badge-catalog paragraph ("shown once in gallery.html"), the token-check ritual (its grep targets `design/gallery.html`), and the entire Component system section all reference the gallery. Rewrite the Component system section so that: the catalog is retired and archived (link the snapshot); the mockup plus its `data-comp` tags IS the component inventory; the registry list is removed; `data-variants` declarations are the home for states the mockup does not show; the states page is planned for after the second design sprint (one line, no build instruction); and the label overlay is documented as dev tooling.
- The three gallery-only components (`comment-split`, `verdict-chip`, `verdict-popover`, per DESIGN.md's "Gallery-only" paragraph) lose their only rendered home. Disposition them explicitly; do not silently drop them. Default: keep their CSS/JS untouched and note in DESIGN.md that they are defined in `styles.css` / `behavior.js` with their rendered form preserved in the archive snapshot. Delete their code only if you can prove it is unreferenced. Record the disposition in the stage's DEVLOG entry.
- Install the Standing doctrine from the brief, preserving its meaning exactly: `data-variants` is required whenever a component with hidden states is built or reshaped, emitted from builders for generated components; no prose variant inventories anywhere; new design values go through `tokens.css`; the two backfill efforts (variant conversion sweep, token-hygiene audit) are named next-phase roadmap work, not ambient duty.
- Add a greppable check to the standing verify ritual, next to the existing token-check: one runnable line that surfaces `data-comp` roots and their `data-variants` coverage for review, plus the instruction to declare on touch. Keep it one line an agent can actually run.
- Update the stale gallery-pointing comments in `behavior.js` and `styles.css` (file headers and inline notes) to reflect the retirement; change no code.
- Completeness gate: grep the repo case-insensitively for "gallery" and "glossary"; classify every hit as live rule (must be fixed), history (stays: `archive/`, DEVLOG, `dev/prompts/`), or other-lane (`dev/notes/`, stays). Zero live-rule hits may remain in CLAUDE.md, `design/`, or `docs/`.
- DEVLOG entry (include the trio disposition and the grep-gate result), then commit.

## Stage 3: the label overlay

- New standalone file in `design/` (suggested name `label-overlay.js`; your call), loaded by `mockup.html` with one script tag after `mockup-toolkit.js`. Its own toggle keystroke (suggest Ctrl+L; verify it collides with nothing in `mockup-toolkit.js`, `behavior.js`, or common browser bindings). It is dev tooling, the same class as `mockup-toolkit.js`: outside the five-file design system, exempt from the propagation rule, documented as such in DESIGN.md.
- Behavior: on toggle, query every `[data-comp]` element on the live page and draw a small labeled tag showing its slug; position by recomputing from the live layout (getBoundingClientRect) and redraw on resize, scroll, and splitter drag; second toggle removes everything. Store nothing per component; the tags on the elements are the single source, so renames and layout changes flow through automatically.
- Density is the real design problem: roughly 190 tagged instances, many repeated (list rows, cards). Handle clutter simply and legibly (collision nudging, one label per component with an instance count, or a hover-to-expand mode; your call, favor simplicity). Labels show the slug only, no variant names.
- Verify per CLAUDE.md's Verifying UI changes with [dev/tools/ui-verify/](dev/tools/ui-verify/README.md): headed pass; toggle on and off; drag the splitters to narrow and wide extremes with labels on; scroll a labeled panel; screenshot each state to `.scratch/`; fix what is off before reporting.
- DEVLOG entry, then commit.

## Wrap-up

Report plain-language first, then detail, per the CLAUDE.md working style. Cover: what changed in each stage, the gallery-only trio disposition, the CDN vendoring outcome, where the screenshots are, and the completeness-gate result (the classified grep). Cite every file you discuss as a clickable markdown link. If anything in the repo contradicted this prompt, say exactly what and what you did about it.
