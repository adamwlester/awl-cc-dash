### A–B — Goal & where it lives

| ID | Rev | Me | Explanation |
|----|----|----|-------------|
| **A1** Converge-not-drift goal | ✅ | ✅ | Correct north star. Drift is the actual disease every audit in these sessions hit. |
| **B1** CLAUDE.md merged "Making & verifying" gate | ✅ | ✅ | Right home. Hard requirement: keep it to one screen, or it gets skipped like the headed-pass rule already was, twice. |
| **B2** DESIGN.md elaboration + Component Catalog | 🟡 | 🟡 | Heuristics/token-rules/hover-policy in DESIGN.md is fine. A hand-kept per-component **catalog** is the two-files drift trap relocated. Keep DESIGN.md to rules and vocabulary; the mockup (with `data-comp`) is the inventory. |

### C — Your policies

| ID | Rev | Me | Explanation |
|----|----|----|-------------|
| **C1** Three-way alignment (DESIGN/mockup/tokens) | ✅ | ✅ | Highest-value rule, but pure discipline. Only holds if D1 plus a dead-ref grep give it teeth. |
| **C2** Wire behavior, consistently | 🟡 | 🟡 | "Behave identically across instances" yes. "Wire all behavior we reasonably can" in a vanilla mockup you'll rebuild in React is double work. Scope it to behavior that **expresses a design decision** (states, gating, selection), not app logic. |
| **C3** Canonical names + shared labels | ✅ | ✅ | Tied for best item. Names port straight into React component names; shared menu labels kill the "Export prompt…/Export output…" divergence. Cheapest durable win. |
| **C4** Hover cards, broadly | ❌ | 🟡 | We both reject the breadth (paragraph-per-component rots and won't get authored). I'm softer than the reviewer because the **goal is salvageable by splitting it**: every component gets a canonical *name* (cheap, universal), only complex ones get a *prose card* (selective). That delivers "near-all coverage" without the noise. |
| **C5** mockup = max fidelity | 🟡 | 🟡 | Agree it needs the reviewer's reframe: maximize **design + state** fidelity, not behavioral/app-logic fidelity. The latter rebuilds the app in vanilla JS right before React. |
| **C6** Tokenization | ✅ | ✅ | Tied for best. `tokens.css` ports verbatim. Defining what must be a token plus auditing offenders is your highest-leverage durable work. |

### D — Your recs

| ID | Rev | Me | Explanation |
|----|----|----|-------------|
| **D1** Removal rule (CSS + entry + DESIGN.md, same pass) | ✅ | ✅ | This is what makes C1 real instead of aspirational. Fixes the recurring dead-`.card-sel`/`--rule` rot directly. |
| **D2** Naming format `<Noun> <Type>`, Title Case | ✅ | ✅ | Cheap, durable, ports to component names. Hold it loosely; a few components won't fit the pattern, don't force them. |
| **D3** Name mechanism (`data-comp`, not selector registry) | 🟡 | ✅ | **I differ from the reviewer here.** They call `data-comp` + grep "tooling that dies at the port," but it's the *enabler* of the enforcement they prize: you can't grep "same component, divergent label" without a co-located identity. And it doesn't die, in React the component boundary *becomes* the name. Loving the grep but being lukewarm on its enabler is inconsistent. Upgrade to ✅. |
| **D4** Names in the Ctrl+G annotation layer | 🟡 | ❌ | **I go further than the reviewer: drop it.** Its goal (keep internal vocab out of shipped tooltips) is already met by D3, since `data-comp` is an invisible attribute, not user-facing text. The overlay is a second annotation surface that can itself drift, for zero added benefit. |
| **D5** Status markers (`wired`/`mock`/`planned`) | ✅ | ✅ | Cheap, high-signal, and you half-have it (`*(planned)*`). Keep it lightweight. |
| **D6** States + composition | ✅ | ✅ | Both ✅, but I'd **elevate it to co-equal with tokens.** Nearly every real bug in these sessions was a state bug (jump pills on empty regions, ungated dropdowns, the digest stale at 5, highlight past the last line). These *are* your future Storybook stories. |
| **D7** Styling heuristics (color by role, never hex) | ✅ | ✅ | Ports directly, overlaps cleanly with C6/E1. Free win. |

### E — Token axes (include)

| ID | Rev | Me | Explanation |
|----|----|----|-------------|
| **E1** color roles + minimal primitives | ✅ | ✅ | You already have these informally (`--foreground`, `--border`, `--rule`). Formalize; drop the generic hue ramps and the `figma` role. |
| **E2** opacity (short flat scale) | ✅ | ✅ | Real axis. Keep the 3–4 values you actually use, not 8 cutely-named steps. |
| **E3** shadow scale + focus-ring + none | ✅ | ✅ | Keep your hard-offset `--shadow`/`--shadow-sm`; add the missing focus-ring token. Not "elevation." |
| **E4** typography (family/weight/size/line-height) | ✅ | ✅ | Genuine gaps (mono family, size scale). Define the range you use (~xs→xl), not 4xl. |
| **E5** border-width + radius | ✅ | ✅ | The **defining axis** of the look. One `--border-width`; radius base + sm (the stray 3px); no `full`/pills. |
| **E6** spacing (flat scale) | ✅ | ✅ | Both ✅, and I'd flag it as **the single highest-value add.** It's your biggest gap (all padding/gap inline today) and your most-drifted dimension. |
| **E7** size (touch-target/icon/control-height) | ✅ | ✅ | Captures the recurring magic numbers (44px hit-target, 18px icon). 2–3 sizes, not xs→2xl. |
| **E8** one breakpoint + semantic spacing aliases | 🟡 | 🟡 | Breakpoint fine. Sharper criterion than the reviewer's "keep ≤5": keep aliases that name a **thing** (`--pad-card`, `--input-h`, one unambiguous value), cut aliases that name a **relationship** (`--gap-section` vs `--gap-subsection`), which need judgment and get misapplied. |

### E — Token axes (skip)

| ID | Rev | Me | Explanation |
|----|----|----|-------------|
| **E9** skip raw hue ramps | ✅ | ✅ | Correct to skip. Importing `--blue-500` just tempts agents away from `--secondary`. |
| **E10** skip shadow-as-elevation | ✅ | ✅ | Correct. Neobrutalism shadow is fixed hard-offset, not a depth ladder. |
| **E11** skip letter-spacing/paragraph/case/decoration | ✅ | ✅ | Correct. Case and decoration are utilities, not values; letter-spacing barely varies. |
| **E12** defer composite text-style | ✅ | ✅ | Correct. A composite can't be a CSS `var()`; it's a utility class, so it waits for the React/build stage. |
| **E13** skip runtime/structural layout | ✅ | ✅ | Correct, and important: your panes are resizable/flex at runtime, so tokenizing widths would lie about how the layout behaves. |
| **E14** keep the semantic layer small | ✅ | ✅ | The meta-guardrail that keeps the whole token effort enforceable instead of 80 tokens agents ignore. Hold the line. |

### F–G — Deliverables & open question

| ID | Rev | Me | Explanation |
|----|----|----|-------------|
| **F1** Draft tokens.css structure | ✅ | ✅ | **Do first.** Most order-per-effort, fully portable, and F2/F3 both depend on the names being settled. Lead with spacing, border-width, color roles. |
| **F2** CLAUDE.md gate + DESIGN.md elaboration | 🟡 | 🟡 | Gate yes. DESIGN.md half inherits B2's caveat: write rules, not a hand-maintained catalog. |
| **F3** Refactor instructions | 🟡 | 🟡 | A refactor is necessary (rules are worthless if the code doesn't obey them), but stage it: token + naming refactor now (durable), hover-card/instrumentation refactor last or skip. |
| **G1** States gallery | 🟡 | 🟡 | Yes, but at the **React/Storybook stage**, generated from one source. A vanilla-JS version now is throwaway. |

### The addition we both rate highest (not a tracker item)

| ID | Rev | Me | Explanation |
|----|----|----|-------------|
| **NEW** Enforcement: 2–3 grep checks in the verify step | ✅ | ✅✅ | The reviewer files this as a closing note; **I'd make it structural and early, wired alongside F1.** Three checks: hardcoded hex/`px` that should be a token; a DESIGN.md reference to a class/selector absent from the mockup; two `data-comp` instances with divergent labels. These catch the exact failures every audit caught, automatically. Without teeth, C1/C6/D1 are all just "agents will remember to…", and your history says they won't. |

**Net divergence from the reviewer:** three rows (C4 softer, D3 up, D4 down), plus I'd elevate D6 and E6 within the agrees and promote the enforcement grep from addendum to organizing principle. Everything else, we're aligned.
