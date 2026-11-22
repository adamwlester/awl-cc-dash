# Design changes

How to change anything in `design/`: reuse first, then propagate across all five design-system files. Read [design/DESIGN.md](../design/DESIGN.md) before changing any of them; verify the result as in [ui-verification.md](ui-verification.md).

## The five files

`design/` is one system in five files, each owning one thing:

| File          | Owns                                                       |
| ------------- | ---------------------------------------------------------- |
| `tokens.css`  | Every design value                                         |
| `styles.css`  | Shared component Cascading Style Sheets (CSS)              |
| `behavior.js` | Shared component behavior and interaction logic            |
| `mockup.html` | The working app surface and the component inventory        |
| `DESIGN.md`   | The rules and intent                                       |

`behavior.js` is the single source of truth for how controls actually act. In `mockup.html`, each component's canonical `data-comp` name, its `data-variants` hidden-state declarations and its `data-status` markers live on the elements themselves.

Dev-only view tooling is outside this system: `mockup-toolkit.js`, `label-overlay.js` and `states.html` are development tools that read the mockup. The propagation rule below does not apply to them; `DESIGN.md` documents them as tooling.

## Reuse before adding

- Check `tokens.css` for an existing token and `styles.css` for an existing class or pattern before introducing a new one.
- Never hardcode a value that belongs in `tokens.css` (colour, type, spacing, sizing, radius, border width); reference it with `var()`.
- New tokens are additive; never rename an existing one.
- When you pass a hardcoded value that should be a token, flag it, or fix it if you are confident; never silently ignore it. This is separate from the scheduled token passes: the 2026-07-05 token run did the systematic conversion sweep, and colour-token minting and the palette revisit remain named future passes.

## Propagate every change

- A **value** goes in `tokens.css`.
- **Component CSS** goes in `styles.css`.
- A component's **behavior or interaction logic** goes in `behavior.js` (shared; never duplicate it into the mockup).
- A **new or changed component** is tagged in `mockup.html`: `data-comp` on the root element, plus `data-status` if dormant or undecided. Declare its hidden states too: if it has appearance states the mockup does not currently show (a badge that renders only one of its colour states, a disabled, empty or error look, a status ramp), declare them in a `data-variants` attribute on that same root, as space-separated state names placed immediately after `data-comp`, and emitted from the builder for components generated in JavaScript.
- A **rule or intent** goes in `DESIGN.md`.

A change that lands in only one file when it owes others is unfinished.

**No prose variant inventories anywhere.** The element is the single home; a hand-maintained parallel inventory is exactly what the retired gallery and registry proved fails.

**Declare on touch; do not backfill ambiently.** The variant conversion sweep landed 2026-07-05 (every earlier component is declared), and `node dev/tools/variant-lint/variant-lint.mjs` enforces the declarations (see the verify ritual in `DESIGN.md`). The token-hygiene audit's conversion pass also landed 2026-07-05 (hardcoded values converted to tokens, the badge and chip S/M/L size standard, the inventory re-trued and dead CSS removed; per-decision record in `DEVLOG.md`). Colour-token minting, the palette revisit and the badge visual-consolidation pass remain named future work, not ambient duty while doing unrelated work.

## Exceptions and boundaries

- **No design value lives outside `tokens.css`** except where `DESIGN.md` documents an exception. As of 2026-07: the Console's self-contained `--term-*` palette, the per-instance `--nc` agent-colour binding, and runtime values such as progress-bar widths and the resizable panes' default divider positions (their inline `flex:` ratios). The panes' minimum and maximum size constraints, the fixed dev-window size and the pinned column widths are tokens: the `--win-*`, `--col-*` and `--pane-*` layout set.
- **Nothing in `design/` references any backlog.** The build backlog lives in [ARCHITECTURE](ARCHITECTURE.md) §11, and all backlogs stay out of `design/` so the design system stays at its five files.
