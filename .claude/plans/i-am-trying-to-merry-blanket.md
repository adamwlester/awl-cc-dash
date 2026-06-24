# Plan — Author the design-docs refactor prompt

## Context

The design documentation in `design/` has grown tangled: `DESIGN.md` mixes UX-intent prose with
the visual design system, color values are scattered across two tables and three prose runs (plus a
JS object in the mockup), and there is no single source of truth for tokens. The real app
(`frontend/App.tsx`) already diverges, but that's deferred.

Through discussion we settled on a lean, standard, best-practice structure for the `design/` folder
and a workflow where the human drives changes via the mockup and tells agents to sync the rest. The
task now is to **author a single agent prompt** that performs the whole refactor in one pass, and
save it to `dev/prompts/`. This plan file holds the exact prompt content for review; once approved,
it gets written to `dev/prompts/design-docs-refactor.md`.

### Decisions already locked in
- **Target `design/` file set:** `tokens.css` (new, single source of truth) · `mockup.html`
  (renamed from `ui-concept-v9p14.html`) · `mockup-toolkit.js` (renamed from `design-tools.js`) ·
  `DESIGN.md` (intent/behavior, design-system section rewritten). `TODO.md` untouched.
- **No separate styleguide/showcase page** — the mockup's own Palette Reference block (now fed by
  `tokens.css`) is the visual reference.
- **Latest-only mockup** (no version suffix); human archives + git hold history.
- **Freedom vs. constraint:** agent has full latitude to restructure the *docs* into optimal form
  (preservation rule lifted there); `mockup.html` must be appearance- and behavior-faithful to the
  source version.
- **Out of scope:** `frontend/`, `sidecar/`, any app code (token-sync to the real app is future).

## Deliverable

A single file: `dev/prompts/design-docs-refactor.md`, matching the house prose style of the existing
prompts in that folder. Full content below.

---

## Prompt content (to be written to `dev/prompts/design-docs-refactor.md`)

This is a refactor of the design documentation in `design/` into a cleaner, best-practice structure
that's easy for agents to maintain and for the human to reason about. Deliver a **finished, working
version** — not a proposal. Work from the current `design/` folder.

**Read first:** the design-related parts of `CLAUDE.md` (the folder map, the Key-files table, and —
important — the UI-verification rule and the DEVLOG rule); `design/DESIGN.md` in full; and open
`design/ui-concept-v9p14.html` to understand its structure — note the inline `:root{}` token block,
the JS object holding the 16 agent-identity colors, and the **Palette Reference** block at the
bottom.

**Target structure — the `design/` folder should end as:**
- **`tokens.css`** *(new)* — the single source of truth for every raw design value: all colors
  (including the 16 agent-identity colors), the type family/weights, spacing, radius, and shadows.
  One file, logically grouped with comments, so "all our colors / all our tokens" is visible in one
  place. Anything that belongs here must not live anywhere else.
- **`mockup.html`** — renamed from `ui-concept-v9p14.html`. Consumes `tokens.css` via a
  `<link rel="stylesheet">` instead of an inline `:root{}` block.
- **`mockup-toolkit.js`** — renamed from `design-tools.js`.
- **`DESIGN.md`** — stays the UX intent/behavior reference. Rewrite its design-system section so the
  *rules and conventions* remain as prose (the emphasis ladder, inline-vs-menu selector rules, the
  neobrutalism conventions, etc.) while all *values* move to `tokens.css` and are referenced by a
  pointer, not duplicated.

We are deliberately **not** adding a separate styleguide/showcase page — the mockup's own Palette
Reference block, now rendering from `tokens.css`, is the visual reference. Do not introduce one.

**Where you have freedom, and where you do not — read carefully:**
- **Freedom:** you have full latitude over the *form and structure* of `DESIGN.md` and `tokens.css`
  and how they cross-reference — reorganize, rewrite, and restructure them into whatever is cleanest
  and most best-practice, with the explicit aim of making them intuitive for agents to work with.
  For these docs, `CLAUDE.md`'s "preserve everything you weren't asked to change" rule is **lifted** —
  optimal structure beats verbatim preservation. Likewise, *how* the mockup's JS sources the agent
  colors is your call, as long as there is a single source of truth and behavior is unchanged.
- **Hard constraint:** `mockup.html` must faithfully preserve the **appearance and functionality**
  of `ui-concept-v9p14.html`. The only permitted changes are plumbing — pointing at `tokens.css`,
  referencing the renamed `mockup-toolkit.js`, and any wiring needed for the JS to read agent colors
  from CSS. Nothing visual or behavioral may shift.

**Rules that keep it maintainable:**
- **Single source of truth.** After the refactor, no design value (hex, spacing number, radius,
  shadow) is duplicated — it lives once in `tokens.css` and everything else references it. No stray
  hardcoded values left inline in the mockup; promote any into `tokens.css`.
- **Do not rename the existing CSS custom-property names** (`--main`, `--background`, `--secondary`,
  `--radius-base`, etc.). The mockup references them in thousands of places — *relocate* them into
  `tokens.css`, don't rename them.
- **Consolidate the scattered palette.** Today colors are split across two tables and three prose
  runs in `DESIGN.md` plus a JS object in the mockup; gather and group them in `tokens.css`.
- **Fix every reference to the renamed files.** Search the whole repo (not just `design/`) for
  `ui-concept-v9p14` and `design-tools` — the mockup's `<script>` include, `DESIGN.md`, `CLAUDE.md`,
  any README, `start-dashboard.bat`, `.vscode/`, etc. — and update them all.
- **Out of scope — do not touch:** `frontend/` (especially `App.tsx`), `sidecar/`, or any
  application code. Syncing the real app to these tokens is deliberately future work; this task is
  the `design/` docs only.

**HARD GATE — mockup fidelity (verify by rendering, per the CLAUDE.md UI rule).** Before declaring
done, render the original (the pre-edit `ui-concept-v9p14.html`) and the new `mockup.html` over
`http://localhost` (the Playwright MCP browser blocks `file:`) and confirm they are **visually
identical**. Resize the panels to both narrow and wide extremes and confirm layout parity. Then
confirm the toolkit still works in `mockup.html`: `Ctrl+G` toggles it, and Pin / Measure / Grid /
Clear All / Copy Notes all function. Do the iteration headless; finish with one headed parity pass.
If the new mockup differs from the original in any visible or behavioral way that isn't intended
plumbing, it is not done — fix it before reporting back.

**Finish:**
- Append a `DEVLOG.md` entry per the CLAUDE.md rule — the renames, the new single-source structure,
  the observable outcome, and a `Files:` line.
- Report back with the final `design/` file list and a one-paragraph summary of how the new
  structure is meant to be maintained (which file owns what), so it can serve as the working
  contract.

## Verification (of this task — authoring the prompt)
- The file exists at `dev/prompts/design-docs-refactor.md` and reads cleanly in the house style.
- It states the target file set, the freedom/constraint split, the single-source rule, the rename
  reference-sweep, the out-of-scope boundary, and the mockup-fidelity hard gate.
