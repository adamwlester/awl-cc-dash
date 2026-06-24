# Plan: Size-triggered DEVLOG rotation (instruction-only, with digests)

## Context

[DEVLOG.md](../../DEVLOG.md) has grown to **2,178 lines / ~157 KB / ~34K tokens / 152 entries**
(2026‑03‑26 → 2026‑06‑23). The cost isn't disk — it's that [CLAUDE.md](../../CLAUDE.md#L46) and the
DEVLOG header both tell **every agent to read the whole file before making changes**, so all ~34K
tokens load into context on essentially every session. Most of that bulk is sandbox‑era,
pre‑fork `[Reconstructed]` history that current tasks never need.

We want a **self-managing log**: agents archive the old tail **when the file gets too long**, not on
any calendar or milestone schedule (work here is too chaotic for those boundaries). Decisions made:
- **Trigger = instruction-only.** No hook, no helper script. A documented rule in the DEVLOG header +
  CLAUDE.md tells agents to rotate when the file crosses a line-count threshold.
- **Keep digests + an index.** Each rotation leaves a dense prose digest plus an index row in the main
  file, so agents keep the narrative memory cheaply and open an archive only when they need detail.

Outcome: `DEVLOG.md` breathes between a small target and threshold instead of growing forever; full
history is preserved verbatim under `archive/devlog/` (immutability rule intact); the rotation rule is
a worked example future agents can copy.

## Approach

Size-triggered rotation (the `logrotate` pattern), measured in **lines** as a cheap deterministic
proxy for tokens:

- **Threshold:** when `DEVLOG.md` exceeds **~700 lines**, rotate.
- **Target:** move the **oldest** entries (the bottom of the file — it's newest-first) into an archive
  file until the main file is back under **~300 lines**.
- Cut only at `### YYYY-MM-DD HH:MM:SS` entry headings — never mid-entry.

These numbers are documented as tunable defaults, not hard-coded anywhere.

### 1. Establish the archive home and do the first cut

- Create `archive/devlog/DEVLOG-archive-01.md` with a short header stating it is archived, immutable
  DEVLOG history (entries retain their original `### …` headings and `Files:` lines, **verbatim**).
- **Initial cut line = the fresh-repo fork.** Move every entry dated **before 2026‑06‑21** (all the
  sandbox-era `[Reconstructed]` entries) out of `DEVLOG.md` into `DEVLOG-archive-01.md`, in original
  order. Keep fork‑forward entries in `DEVLOG.md`. If the main file is still well over the ~300 target
  after that, push the oldest remaining `[Reconstructed]` entries into the archive too, stopping at an
  entry boundary near the target.
- `archive/devlog/` is new; `archive/` already exists as the established home for retired-but-referenced
  material, so this fits the existing precedent.

### 2. Restructure `DEVLOG.md`

- **Header blockquote** (around [DEVLOG.md:3-24](../../DEVLOG.md#L3-L24)): add a short **Rotation**
  paragraph — "When this file exceeds ~700 lines, move the oldest entries into the newest
  `archive/devlog/DEVLOG-archive-NN.md` until it's back under ~300, then add/refresh a digest + index
  row in *Archived history* below. Move entries verbatim; never edit them; cut only at entry headings."
- **Trim the Log section:** remove the archived entries from the bottom. Leave the Status block and the
  recent window untouched.
- **Add an `## Archived history` section at the very bottom** containing:
  - A **digest**: a few dense lines per archive file summarizing what that span covered (key
    decisions/outcomes — e.g. "sandbox→awl-cc-dash migration, bridge package + test suite, driver seam,
    dashboard design lineage v1→v9").
  - An **index table**: `| Archive file | Date range | Entries | Summary |` with one row per archive
    file, linking to `archive/devlog/DEVLOG-archive-01.md`.

### 3. Update the instruction docs (instruction-only trigger lives here)

- [CLAUDE.md:46](../../CLAUDE.md#L46) — Key Files row for DEVLOG.md: note that DEVLOG.md is the **recent
  window**; older entries live in `archive/devlog/` and are read **on demand** (via the index), not by
  default. Adjust "read it before making changes" → read the window; consult archives only when a task
  needs older history.
- [CLAUDE.md:136-143](../../CLAUDE.md#L136-L143) — Behavioral rule: append a **rotation sub-bullet**
  giving the threshold (~700) / target (~300) / procedure (move oldest verbatim to newest
  `archive/devlog/DEVLOG-archive-NN.md`, refresh digest + index). Keep the existing "log every change"
  rule as-is.

## Files to change

- **New:** `archive/devlog/DEVLOG-archive-01.md` — archived pre-fork entries, verbatim + mini-header.
- **Edit:** [DEVLOG.md](../../DEVLOG.md) — header Rotation rule; trim Log; add `## Archived history`
  (digest + index).
- **Edit:** [CLAUDE.md](../../CLAUDE.md) — Key Files row (L46) + Behavioral rotation sub-bullet (L136).
- **Edit:** [DEVLOG.md](../../DEVLOG.md) — new entry logging this change (per the project's own DEVLOG
  rule).

## Verification

- **No entries lost (conservation check):** count `### ` entry headings in `DEVLOG.md` +
  `archive/devlog/DEVLOG-archive-01.md` after the change; the sum must equal the original **152**.
  (`Select-String -Pattern '^### \d{4}-' | Measure-Object`.)
- **Window shrank:** `DEVLOG.md` line count is back near ~300 and under the ~700 threshold; report the
  before/after line + approx token counts (before ~2,178 lines / ~34K tokens).
- **Verbatim archive:** spot-check 2–3 moved entries against git history (`git show HEAD:DEVLOG.md`) to
  confirm text is byte-identical, not summarized.
- **Links resolve:** the index table link to `archive/devlog/DEVLOG-archive-01.md` is a valid relative
  path; the digest mentions every archive file present.
- **Instructions consistent:** re-read the edited CLAUDE.md rows and DEVLOG header to confirm an agent
  following them would (a) read only the window by default, (b) know the threshold/target, (c) know to
  refresh the digest + index on rotation.
- No code/build affected (docs-only change) — no app run needed.
