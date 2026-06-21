# UI Rockstar — Reboot Handoff (read this first)

## What this is
A previous Claude Desktop session ("UI Rockstar") was redesigning this project's agent
dashboard and producing unusually strong design work — then it **crashed before finishing**
`ui-concept-v7p1.html`. You are a **fresh session picking up that thread.** This folder exists
to put you back into that session's headspace and hand you everything it had.

## Your goal
Finish the **v7p1 redesign** to the same design quality the prior run was hitting. The task
spec is unchanged and lives in `prompts/dashboard-v7-change-instructions.md` — **that is the
source of truth for *what* to build.** This handoff is about the *how* and the *feel*.

## Prime directive: get into the rhythm before you build
The reason the old run was good wasn't a special spec — it was a sensibility: it respected the
existing design tokens exactly, explored a few coherent options with honest tradeoffs before
committing, kept things warm/rounded/clean, and didn't rush. **Absorb that before writing code —
and lean toward over-working the problem rather than under. That generosity (multiple options,
lots of thinking, full demos) is part of why it landed; don't optimize for brevity or speed.**

1. **Read `design-decisions-rationale.md` first.** It's the densest, fastest way in: what the
   human prioritizes, the taste that makes a design "land," the settled decisions and *why*, and
   the spots this project keeps snagging on. Cheap to read, highest signal — start here.
2. **Read `transcript-thinking.md` for *feel*.** It's a curated cut of the prior session. The
   design exploration (**messages 0–9**, where the four demo HTMLs were built) is the part that
   matters — read it for rhythm, not facts. The tooling/plumbing was stripped out (a short note
   marks where); messages 38–43 cover how to approach the big refactor and the agent-icon plan.
3. **Study the recovered examples in `recovered-examples/`** (see manifest below). These carry
   the resolved aesthetic better than any description.
4. **Then** read the task spec **in full** and open the current UI, and build.

## The shape of what's wanted (it's intentionally a little fuzzy)
The aesthetic direction — §A of the brief — is deliberately not pinned down. Don't wait for a
rigid spec; **infer it from the examples and the transcript.** In short: the warm "Happy Hues
17" palette (cream / navy / pink), 2px borders, rounded card framing, clean header/body/footer
panels, ghost icon buttons, segmented controls. When in doubt, match the examples and use
judgment — that's what the last run did well.

## Recovered examples (manifest)
In `recovered-examples/`:
- **`context-overlay-concepts.html`** — the early `/context` exploration: several interaction
  patterns (unified tab strip, modal, anchored popover, bottom drawer) for Context + Rewind +
  Handoff, built on the real tokens. The richest early-vibe artifact. *(You did not keep this
  one before — it's pure design-rhythm reference.)*
- **`model-context-history.html`** — the Model button-group + `/context` breakdown +
  Rewind/Handoff rail. Polished into `agent-dashboard/design/ui-snipets/agent-panel-model-context.html`.
- **`action-strip-formatting.html`** — v1 of the Revise / Response / Send action strip.
- **`action-strip-v2.html`** — v2; polished into
  `agent-dashboard/design/ui-snipets/prompt-panel-action-strip.html`.
- **`v7p1-build-partial-93k.html`** — how far the actual v7p1 build got: left + middle panes
  (incl. the ported model/context/history), **cut off mid Agent→Create**; the right-hand Prompts
  pane was never built. **Loose reference only** — glance at it for direction if it helps, but
  you're under no obligation to follow it, the reasoning behind its choices wasn't preserved, and
  it is **not** a file to continue. Build fresh from v6p3.
- **`v7p1-build-skeleton-2k.html`** — the retry's intended *full* structure as an empty
  placeholder scaffold. Shows the planned layout only; same "loose reference, don't continue"
  caveat — it may or may not tell you anything you can't already infer from v6p3 + the brief.

## Also read (project ground truth)
- `prompts/dashboard-v7-change-instructions.md` — **THE TASK and the focal point of this whole
  package.** Everything else here exists to help you execute it well. It has its own preface + the
  full change list (§A–§H). Read it in full and treat it as your checklist; it's final — don't
  rewrite it.
- `agent-dashboard/design/ui-concept-v6p3.html` — the current UI you're transforming.
- `agent-dashboard/README.md` — the design intent behind every panel.
- `agent-dashboard/design/ui-snipets/` — the two polished component snippets.

## The one hard constraint: a single full-file write *will* truncate
This isn't a style note — it's a capacity limit, and it's the thing that actually broke the
prior run. Both attempts emitted the dashboard as one giant `write_file` and were cut off at
**exactly 93,754 chars — the same number both times.** That's a deterministic ceiling on a
single write/turn. The finished file is ~120k+ chars, so it **cannot** be produced in one write.

You work best in coherent one-shot passes — keep doing that. Just **size each pass to land under
that ceiling**: e.g., write a complete base in one pass, then finish the remaining panels in a
couple more passes (the prior run's skeleton-with-placeholders scaffold is one clean way; a
straight section-by-section append is another — your call). The only failure mode to avoid is
emitting one oversized write that silently truncates and leaves a broken file. Don't fragment
into dozens of tiny edits either — that's not the lesson.

- **Start from a fresh copy of `v6p3`**, not the on-disk `ui-concept-v7p1.html` — that's just
  the empty 2.4k skeleton left by the crash.
- **Render-check as you go.** `file://` rendering works (headless), so screenshot your output
  and self-correct rather than building blind.

## Environment
Filesystem read + (approval-gated) write; headless Playwright for render+screenshot. Put scratch
in `.scratch/`; add a dated `DEVLOG.md` entry for significant changes (see `CLAUDE.md`).
