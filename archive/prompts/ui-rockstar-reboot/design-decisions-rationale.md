# Design Decisions & Rationale — the *why* behind v7p1

## How to use this doc
The task spec (`prompts/dashboard-v7-change-instructions.md`) tells you **what** to build. The
thinking transcript (`transcript-thinking.md`) carries the **feel**. This doc is the missing
middle: **why** the design is the way it is, **what the human actually cares about**, and **where
this project keeps snagging** — so you make good calls in the fuzzy areas instead of re-deriving
(or accidentally re-opening) decisions that are already settled.

Sources synthesized: the `cc-exports/` session transcripts (the back-and-forth where decisions
were actually made), `DEVLOG.md` (the chronology, including every reversal), and
`agent-dashboard/README.md` (the durable intent). Where those disagree, **newest wins** and the
mockup owns the pixels.

---

## 1. What the human is actually after (priorities, in order)

1. **Design quality is the #1 success criterion — above feature completeness.** The whole reason
   for this reboot is that one session produced *unusually clean, coherent* design and the human
   wants that bar hit again. A v7p1 that implements every bullet but looks merely "fine" is a
   miss. A v7p1 that nails the aesthetic and gets 90% of the features is a win. Judge your own
   output against "is this genuinely beautiful and coherent?", not "did I check every box?"
2. **Apply the snippet aesthetic across the *whole* UI.** The two polished snippets
   (`agent-panel-model-context.html`, `prompt-panel-action-strip.html`) and the
   `palette-options/index.html` inspiration represent the target look. The job is to lift the
   rest of the dashboard up to that standard — cleaner, more rounded, more "designed" — not to
   bolt features onto the existing v6p3 as-is.
3. **Add the functionality** in the brief (readout cards, session save/load, token totals, the
   feed-formatting control, the vertical toggle strips, the Team Graph edges, etc.).
4. **Make it cohere as a whole.** Rounding/restyling one element in isolation is worse than not
   doing it. Coherence across the three columns is a hard constraint (see §4 friction: §A).

> The human has said explicitly: treat the prescriptive details as **guidelines, not law**;
> use your judgment; lean toward **over-working** the problem rather than under. Generosity
> (multiple options, lots of thinking, full demos) is *wanted*, not waste.

---

## 2. The taste — what makes a design "land" for this person

Distilled from what he's praised, rejected, and asked for repeatedly across sessions:

**What he likes**
- **Respect the existing design tokens exactly.** The palette, the 2px borders, the surface
  tints (`field`/`term`), the accent jobs are a *system* — work within it. The fastest way to
  lose him is to drift the palette or invent off-system colors.
- **Warm, rounded, clean.** He chose "Happy Hues 17" (cream / navy / pink) deliberately, and as
  far back as v5 asked for *"the more full round button and larger radius border styling from the
  index.html."* The rounded, illustrated, header/body/footer card feel is a long-standing pull,
  not a whim.
- **Restraint over decoration.** When colors started scattering (gold/pink/cobalt for the three
  Requests groups), he pushed to collapse them into a single **warm reddish→copper importance
  ramp** so urgency reads without a rainbow. Prefer one well-chosen ramp to many hues.
- **Legibility is non-negotiable.** "white-on-gold is low-contrast" came up more than once; the
  fix (a cream pill with a constant navy numeral, differentiated by a colored ring) is the kind
  of move he rewards — solve the legibility problem without breaking the system.
- **Options with honest tradeoffs.** His favorite session opened by exploring *four* interaction
  patterns for the `/context` overlay (inline tabs, modal, anchored popover, bottom drawer) and
  naming the tradeoffs. He likes being shown the design space before a commitment.
- **Conventional patterns.** Where something is non-standard and there's a common way (even just
  button order/placement), he'd rather you lean to the convention — especially when it improves
  appearance or UX.

**What he reacts against**
- **Sloppy / rushed work.** His read on why other attempts failed: "it's just sloppy. And I
  think part of that is it's fast." Speed-induced carelessness is the enemy. Slow down, look at
  your own renders, fix the spacing/overflow/contrast yourself.
- **Cramped controls.** "Make the Mode button group a little less cramped." Give controls room.
- **Things that break on resize.** The placeholder *pills* were killed precisely because they
  weren't truly inline and "are not formatting right with window resizing." Build things that
  survive layout changes (hence inline colored text instead of floating pills).
- **A templated, generic look.** The whole point is that this *doesn't* look like a default
  component dump. Match the established system; don't reach for stock styling that fights it.

---

## 3. Settled decisions & the reasoning the brief compresses out

These are **decided** — don't reopen them; this is the "why" so you implement them with intent.

| Decision | Why |
|---|---|
| **Placeholder pills → inline colored text** (bold = placeholder, bold+italic = filled) | The floating pills broke on window resize and didn't sit inline with text. Inline colored text is a true string that wraps correctly; style (not shape) carries the filled/unfilled tell. |
| **Action strip: dropdown leads, icon action follows; icons not words** | Cleaner, denser, and matches the polished `prompt-panel-action-strip.html`. The chip (not the main label) should carry the timing/scope. |
| **"Clean" → "Revise"; strengths reworked** (Minimal/Med/Max → Grammar/Language/Refactor) | "Clean" undersold it (it's an AI rewrite pass). The old strength levels were acknowledged placeholders; scope-named options are clearer. |
| **Requests colors: gold/pink/cobalt → single warm reddish→copper ramp** | Three unrelated hues read as noise. A single urgency ramp (Permissions → Approvals → Decisions) communicates *importance* without scattering color. |
| **Count badges: filled, larger, legible** (cream pill, navy numeral, colored ring) | white-on-gold failed contrast. Keep the number constant and legible; let a ring carry the section tone. |
| **Rollback → Rewind; Clone/Fork → Handoff** | Settled vocabulary. Rewind = roll *this* agent back; Handoff = branch *a new* agent from a point (opens Create prepopulated). Both act on the same Timeline point-list. |
| **Per-tab footers, tops aligned** | Details = Retire only; Create = Create/Reset/Cancel; Requests reply moved in-content. The Agent and Prompts footers must share a baseline so divider lines are collinear across columns — alignment is a visible quality signal he checks. |
| **Model is editable, not locked** | An agent's model can change mid-run; the per-model button-group with version dropdowns (Inherit·Opus·Sonnet·Haiku·Fable) is the agreed form. |
| **Lifecycle limits ≠ link End-After limits** | Deliberately distinct scopes: Lifecycle bounds *one agent's run*; End-After bounds *an inter-agent exchange*. Keep them separate; don't merge. |
| **No popups; everything visible** | The 3-pane layout keeps all state on screen. The only allowed overlay is the anchored Link Config drawer. Don't introduce modals/dialogs. |
| **Compose-first; one identity per agent** | The compose surface is the primary action (it replaces typing in a raw CLI). Each agent's color+icon appears everywhere so the UI is scannable — keep identity consistent across graph/feed/log/CLI/chips. |
| **CLI is read-only** | It's a window onto the agent's real terminal; *all* input goes through Prompts/links. Don't add an input affordance to the CLI. |

---

## 4. Where this project keeps getting hung up (the friction log)

These are the genuinely sticky spots. Treat them with care — some are *open*, some are *sensitive
because we've been burned*. Don't naively re-litigate the closed ones or repeat the painful ones.

- **§A — how far to round (OPEN, the big one).** The human *wants* the rounded card aesthetic
  (header/body/footer, softer corners) from the snippets and `palette-options/index.html` applied
  broadly — but is unsure where it stops without the three columns looking inconsistent or the
  layout breaking. This is explicitly a **direction to prototype and report back on, not a locked
  spec.** Prototype it, judge coherence with your own eyes, and *show where you'd stop the rounding*
  rather than forcing it everywhere or doing it timidly. This is the single highest-value place to
  exercise taste.
- **Badge contrast / count-badge styling (recurring).** Legibility on the warm tones has bitten us
  repeatedly. The ramp hexes are "current, not final" — treat the *ramp concept* as fixed, the
  exact values as tunable, and never ship an illegible numeral.
- **Textarea sizing (resolved but easy to get wrong).** Policy differs by purpose on purpose:
  primary inputs resize with a max-height; short config fields auto-grow/hug; full-height views
  fill vertically. Don't make them all behave the same.
- **The write-ceiling crash (mechanical, already cost us two runs).** Both prior attempts emitted
  the whole file in one giant write and were truncated at *exactly* 93,754 chars. See HANDOFF.md
  — size your passes under that ceiling. This is the concrete reason the build never finished, not
  a design problem.
- **`/context` payload + dense link graphs (OPEN, README "Open questions").** The Transcript
  payload's exact source and how to keep many overlapping link-edges readable are unresolved —
  fine to leave as reasonable defaults; don't over-invest.
- **DEVLOG/README drift.** The README intentionally runs slightly *ahead* of the mockup (it
  describes agreed-but-undrawn things as `(planned)`). If the README and an old mockup disagree,
  the README + this brief win.

---

## 5. How he wants to be worked with (calibration)

Direct asks he's made — following these is part of hitting the mark:

- **Don't optimize for brevity/speed.** Over-work it. Explore, think, build full demos. The good
  run was generous; the bad runs were rushed.
- **Don't fragment into dozens of tiny edits.** He's observed (correctly) that models do cleaner
  work in coherent one-shot passes. The *only* reason to split work is the write ceiling — so do
  a few **large** coherent passes, each sized to land under it. Not death-by-a-thousand-edits.
- **Be your own eyes.** Render and screenshot your output and self-correct. Don't hand back
  spacing/overflow/contrast problems you could have caught.
- **Guidelines, not law.** If a prescriptive detail conflicts with making the whole thing
  coherent and clean, use judgment and say what you changed and why.
- **Ask only what's genuinely unclear**, in the numbered/lettered/★-default format the brief
  specifies — then wait. But if you're confident, proceed in one shot.

---

## 6. The samples — what's good in each, specifically

Point yourself at these (in `recovered-examples/`, and the two polished snippets in
`agent-dashboard/design/ui-snipets/`) and notice *what* makes them work — that's the bar:

- **`context-overlay-concepts.html`** — the clearest display of the instinct he loves: several
  coherent interaction patterns for one problem, each honest about its tradeoffs, all built on the
  real tokens. Read it for *approach*, not just visuals.
- **`model-context-history.html` / `agent-panel-model-context.html`** — the resolved Model
  button-group, the `/context` breakdown, and the Rewind/Handoff rail. He's "happy with this as-is
  — adopt it, don't re-derive it."
- **`action-strip-formatting.html` (v1) → `action-strip-v2.html` / `prompt-panel-action-strip.html`**
  — watch the refinement from v1 to v2: tighter, icon-led, the header/body/footer card framing
  that §A wants to spread. The destination quality for a control cluster.
- **`v7p1-build-partial-93k.html` / `v7p1-build-skeleton-2k.html`** — *loose reference only.* They
  show where the last build was heading (left+middle panes, the rounded `.pcard` framing) and the
  intended overall structure (the skeleton's placeholders). The reasoning behind their specific
  choices was **not** preserved, so weigh them against this doc and the brief — don't treat them as
  a blueprint, and don't continue them as files. Build fresh from `v6p3`.
