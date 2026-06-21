# Dashboard README — Authoring Prompt

**Task:** Write `agent-dashboard/README.md` as the ground-truth reference for the
dashboard's UI/UX intent — clear, concise, and maintainable.

## Most authoritative source — the current mockup
Review the latest UI concept mockup — the **highest-numbered** `agent-dashboard/design/ui-concept-*.html`
(expected to be `v6p1`; confirm it's the newest before you start). Older versions live in
`archive/agent-dashboard/`. This HTML is the most up-to-date ground truth; wherever it conflicts
with older docs, the mockup wins.

## Chronology / "what changed when"
Start with `DEVLOG.md` (repo root) — dated, distilled entries tracking the design's
evolution (v4 → current), more reliable than reconstructing chronology from raw transcripts.
Use it to order events and settle "which idea came later" — newest wins.

## Mine the chat transcripts for intent — this is the real gap
The mockup shows *what* the UI is; `ui-plan-v2.md` is an early *what we want*. But the **design
intent and purpose** — why a panel exists, what problem a feature solves, why an approach was
reversed — lives mostly in the back-and-forth of the session exports in `cc-exports/`. Treat them
as the **primary source for UX rationale**: the user's own words, the debates, and especially the
**reversals** (they reveal what was rejected and why). Weight by recency; later sessions win.

**Infer freely — don't be anxious about being exact.** A plausible, clearly-marked inference of
intent is far more useful than a blank. When you're reading between the lines, just flag it briefly
("intent appears to be…") rather than omitting it or over-hedging. Capturing the *why* is the goal,
not being provably right — and anything you're genuinely unsure of becomes a question for me (see
the end of the prompt).

## Older references — out of date; mine for intent, not specifics
- `archive/agent-dashboard/ui-plan-v2.md` — the GUI/Electron **Vision Spec** (3-pane model,
  link Trigger/Payload/End-After, Team Feed, inter-agent message format, naming). The fullest
  written statement of *intent* — mine it for the "why" the mockup can't show. Ignore UI
  graphics already shown in the mockup.
- `briefs/2026-04-02-multi-agent-dashboard.md` — early vision brief.

## Read carefully, but don't be misled (important)
- **Newest wins.** The design went through many reversals (corner radius, where approvals
  live, scratchpad behavior, palette). Early cc-exports contain superseded ideas — trust
  the latest mockup and latest sessions, not the first ones.
- **`ui-plan-v2.md` is intent, not current state** — it predates the wireframes, so where it
  conflicts with the mockup (agent naming, where approvals live, scratchpad behavior, etc.),
  the mockup wins. It evolved from an abandoned Python/Textual TUI spec (`ui-plan-v1.md` — do
  not use), so it may carry occasional TUI-era phrasing; ignore that framing.
- **`v4` is the prior (dark) base, not current.** `v5p1`+ are point releases of the current
  warm "Happy Hues" design. Don't present v4 as current.
- **The in-file title-bar version badge (e.g. "v0.8") does NOT match the filename** point
  release — ignore it for versioning.

## Scope & structure (a suggestion — adapt freely, you have full context)
Focus on UX/UI *intent*, not implementation code. A workable shape: purpose/vision →
target platform in a line or two → overall layout (the 3-pane model) → each panel and what
it's for → the interaction/communication model (agent links with Trigger / Payload /
End-After, the Team Feed, the shared scratchpad, the per-agent Requests/approvals surface,
Prompts) → the design system (palette, agent-identity colors, surface tints, core
components) → known open questions. Keep it scannable — this is the doc people will read
to understand the dashboard's design.

**Keep it modular and low-maintenance** (this doc will outlive many mockup revisions):
- **One source of truth per thing.** Describe each panel/concept in exactly one place; elsewhere
  refer to it by name, don't restate it. Duplicated descriptions drift out of sync.
- **Capture durable intent, not volatile specifics.** Favor *why it exists / how it behaves*
  (stable) over exact pixels, hex values, sizes, labels, and counts (change constantly). Let the
  **mockup** own the precise visuals — the README shouldn't try to be a pixel spec.
- **Centralize the few specifics you do keep.** Palette/token values belong only in the design-
  system section; prose elsewhere names them ("the gold permission accent"), never re-quotes hexes.
- **Minimize cross-references**, especially to small, change-prone details. If two sections relate,
  link by heading rather than repeating contents.

## Flag what you're unsure of — as answerable questions
Use your best guesses in the README so the draft is usable now (mark inferred intent as inferred
where it matters). But wherever you're genuinely unsure of the **intent** behind something, capture
it as a question for me rather than silently committing to a guess. Collect these into a single
numbered list at the **end of your response** (not inside the README):
- Number each question; give 2–4 **lettered** options (A/B/C…) — concrete, mutually exclusive
  candidate intents, not vague yes/no.
- Mark your best guess with ★ so a non-answer still defaults sensibly.
- One or two lines each; group related ones.

Format it so I can answer tersely — e.g. `1B, 2A, 3★ (take your default), 4C`:

```
1. <short question> — A) <option>   B) <option> ★   C) <option>
2. <short question> — A) <option>   B) <option>     C) <option> ★
```

(This is separate from the README's own "open questions" section: that documents unresolved
*design* decisions for readers; this list is *your* interpretation uncertainties, for me to resolve.)
