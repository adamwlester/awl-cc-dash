# Component System Refactor (design/)

Execute the full design-system refactor defined in `dev/notes/component-system-spec.md`, in one coordinated pass, and leave `design/` finished and final. Deliver working, verified work, not a proposal. You have full repo and system access; use it.

**Precondition:** this run assumes exclusive ownership of `design/` for its duration. Nothing else should edit `mockup.html`, `tokens.css`, or `DESIGN.md` while it is in flight, or the render-identical baseline shifts and the worktree merges collide.

**The spec is your plan, not this prompt.** `dev/notes/component-system-spec.md` holds the locked decisions, the artifact map, the naming / token / status-marker conventions, the doc-distribution map, the Open Questions mechanism, and a dependency-ordered roadmap (Phases 0 through 5) with per-phase acceptance criteria. Follow it. This prompt only points you at context and flags the few things that are easy to get wrong; it deliberately does not restate the spec.

## Read first

- `dev/notes/component-system-spec.md` — the authoritative plan and acceptance criteria. Start here.
- `CLAUDE.md` — the repo rules. The **"Verifying UI changes"** rule and the **DEVLOG** rule are mandatory (see below). Note the editing-discipline rule as well.
- `design/DESIGN.md`, `design/mockup.html`, `design/tokens.css` — the live design system. These, not any snapshot, are the source of truth for the current component instances and values; the mockup is actively edited.
- `dev/notes/component-inventory-and-wiring.md` — background only: how the component families and the wired-versus-static behavior were derived. Do not copy it as a list; tag and enumerate from the live mockup.

## Guardrails (the spec carries the detail; these are the ones not to miss)

- **The spec's decisions are final.** If you encounter the earlier tractability review in `transcripts/cli/` (formerly `.claude/cc-exports/`), treat it as superseded history. Do not relitigate the gallery, the naming, or the token scope.
- **Render must not change** through the stylesheet extraction and the tokenization. The value layer aims for byte-for-byte stability. Prove it by driving the UI (per CLAUDE.md), not by reading diffs.
- **Single-source every value in `tokens.css`, and never rename an existing custom property** (the mockup references them in thousands of places). New tokens are additive.
- **Naming and status markers are exactly as the spec fixes them:** `data-comp` is a kebab-case slug; `data-status` is `planned` or `undecided`. No parallel name registry.
- **No reference to `TODO.md`** anywhere you write (the spec, the mockup, the gallery, or DESIGN.md). That backlog is maintained separately and is out of scope.
- **The spec retires into the permanent docs.** Migrate its rules and conventions into `DESIGN.md` per the distribution map, so the five files (`tokens.css`, `styles.css`, `mockup.html`, `gallery.html`, `DESIGN.md`) become the sole design source. After absorbing it, leave the spec in `dev/notes/` as a historical record and note at its top that it is retired.
- **Mind the one seam:** after you reorganize `DESIGN.md`, confirm that `dev/notes/coverage-map.md`'s citations of `DESIGN.md` sections still resolve, and fix any stale pointers. (This is the spec's post-Phase-3 verification.)
- **Out of scope:** `frontend/`, `sidecar/`, and any application code. This is the `design/` layer only; syncing the real app to these tokens is deliberately future work.

## Working style (ultracode)

The spec's phase dependencies define where parallelism is safe: Phase 0 blocks; Phases 1 and 2 run in parallel after it; then 3, then 4, with the flexible 5. Fan the independent work out as concurrent subagents in isolated git worktrees and merge, following the same worktree mechanism this repo's `dev/prompts/nextup-parallel-execution.md` established (region-disjoint hunks auto-merge; isolate, verify per lane, then merge). (Ignore `dev/prompts/design-docs-refactor.md` if you come across it; it is the superseded earlier effort that created the current token split.) You own the sequencing, the merges, and the final verification. Optimize for elapsed time; quality must match a careful single-agent pass.

## Verification (per CLAUDE.md, required)

Serve over `http://localhost` (the Playwright MCP browser blocks `file:`), iterate **headless** through the resize-and-click loop at the narrow and wide extremes for every surface you touch, then finish with **one headed parity pass**.

**Capture the baseline first.** Before Phase 0, snapshot the current mockup as a screenshot set across its representative panels and states at both the narrow and wide extremes. Lanes run in isolated worktrees that mutate the file, so diff every later render against that captured baseline, not against a live re-edit. The render-identical bar is a hard gate for Phases 0 and 1: if the post-extraction or post-tokenization mockup differs visibly from that baseline, it is not done.

**If the browser drops, fall back rather than stall.** The DEVLOG shows the Playwright MCP browser dropping mid-session repeatedly; if it does, fall back to headless Chrome over `http://localhost` and keep going. Preserve the intent of the headed parity pass with a real rendered comparison; do not degrade to static checks (grep or diff-reading) alone.

The gallery must be exhaustive (the full badge catalog and the five inbox types, plus every other registry component shown once).

## Finish

- Append one `DEVLOG.md` entry per the project rule: what the refactor produced, the observable outcome, and a `Files:` line.
- Report back with the final `design/` file list, a one-line statement of what each file owns (the maintenance contract), confirmation that the spec's acceptance criteria are met, and any Open Questions left marked `undecided`.
