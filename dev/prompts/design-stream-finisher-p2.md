# Design-Stream Finisher — Part 2 (design/)

Integrate into the `design/` files the **remaining design-layer work** the decision tracker implies — the set the first pass did **not** cover — in one coordinated pass, and leave the design system finished and final. Deliver working, verified work, not a proposal. You have full repo and system access; use it.

**Why this exists.** The first pass ([design-stream-finisher.md](dev/prompts/design-stream-finisher.md)) landed the eight **🎨-tagged** decisions — agent identity, subagent integration, permissions, the Library, prompt composition, settings, Retire & Delete, and the Console — **already done, do not redo them.** But a full cross-reference of the tracker against the live design files found more design-layer work the doc decided yet **never 🎨-tagged** — chiefly the **Tier-2 linking drawer** plus a few per-card / feed elements. That under-tagged set is your scope. The gaps below were found by audit (so you can't rediscover them by reading the tracker alone) — but **the tracker's `Decision:` paragraph is still the authority for each item's semantics**: this prompt tells you *what's missing and where*; read the item's tracker `Decision:` for *what it must mean*, and build from `Decision:`, never `Recommended:`.

## The current state of `design/` — work from the live files

Same as the first pass: **work directly on the live `design/` files as they stand** (they now include the first pass's work). `CLAUDE.md` and `design/DESIGN.md` are the authority for the design system.

- **Do NOT use `git worktree`, and do NOT touch `archive/`.** The design files carry uncommitted/untracked work in the working tree; a fresh worktree would build against a stale baseline and miss `behavior.js`. Work in the live working tree, and **locate every anchor by content, not by the line numbers below** (they're approximate starting points — the files are large and shifting).
- **Parallel stream:** if a backend integration agent is running on `sidecar/` + `bridge/`, stay entirely within the `design/` files. The one shared file is **`DEVLOG.md`** — re-read it from disk immediately before appending.

## The six-file system (the propagation contract)

`design/` is **one system in six files** (per `CLAUDE.md` → "Design changes"). Read `design/DESIGN.md` first. Each change propagates to **all** the files it touches: a **value** → `tokens.css` (reference via `var()`, never hardcode); **component CSS** → `styles.css`; **interaction logic** → `behavior.js` (shared by mockup + gallery — never duplicate into one); a **new/changed component** → tag it in `mockup.html` (`data-comp`, `data-status` if dormant) **and** add a live `gx-card` to `gallery.html` (real markup, behavior comes free from `behavior.js`; show every variant; standing specimens only for data-states unreachable by interacting) **and** register it in `DESIGN.md`; a **rule/intent** → `DESIGN.md`. **Reuse before adding** — the items below lean heavily on existing primitives (`multi-select` / `.minitog`, `switch` / `toggle-button`, `stepper`, `dir-tag`, `identity-badge`, the registry-row pattern, `accordion`). New tokens are additive; never rename one.

## The work — the gap set (pointers + the precise gap; read each item's tracker `Decision:` for semantics; each heading below names the item's `docs/ARCHITECTURE.md` section)

### 1. Link relationship model — Link Config drawer reframe (Links — agent-to-agent context, §7.6) **(largest)**
The drawer (`mockup.html` ~1383, `data-comp="link-drawer" data-status="planned"`; gallery specimen ~915) is still built to the **pre-reframe** model. **Remove** the **Payload** segment (Message/Transcript/Manual, ~`mockup.html:1392`, gallery ~927). **Add** a **Relationship** field — a *multi-select* (a link can be both) of **Direct messaging** / **Shared context** — immediately after the agent-pair+direction row. Under **Shared context**, reveal a **content-type multi-select** (reuse the Messages Content taxonomy — Thoughts/Read/Write/Bash/Diffs/Meta — already at ~`mockup.html:1458`) **and** a **"share all prior context" backfill toggle** (default off, reuse the switch primitive). **Reorder** the drawer to the decided fixed order: **pair+direction → Relationship → Trigger → End After → Save/Delete**. `behavior.js` needs multi-select + Shared-context disclosure logic (the existing `segPick` is single-select and won't serve it). Propagate to gallery (rebuild the specimen; fix the stale "Payload" blurb/hover text ~917/919) and `DESIGN.md` (replace the Payload table ~206-211, update the Linking intro ~193-214 and the hover prose ~313, register the new component(s) ~345).

### 2. Link End-After labels/defaults (Links, §7.6) **(small)**
The End-After row's structure is right (two toggleable caps), but the left cap reads **"Turns"** with placeholder **"50"** (`mockup.html` ~1396; gallery ~931; `DESIGN.md` ~212). Per the End-After decision: rename **"Turns" → "Exchanges"** (a round-trip = one message each direction — explicitly *not* internal turns/steps) and set the default **50 → 25**. Update `DESIGN.md` "Turns/Tokens" → "Exchanges/Tokens" and note default 25.

### 3. Link tracking list — the dense link-graph-readability decision (Links, §7.6) **(net-new)**
There is no all-links list anywhere. Add a **grouped-by-agent** list section at the **bottom** of the Link Config drawer (after the Save/Delete strip, ~`mockup.html:1400`): agent = group header; **each link double-listed under both its agents**; each entry shows the other agent + a **direction arrow (→ / ← / ↔) relative to that group's agent**, **reusing the same `dir-tag` glyph** as the pair row. Reuse the registry-group-header/row patterns; give it a new `data-comp` (e.g. `link-list`). Propagate to styles/behavior (seed + render; optional click-to-load master/detail) + a gallery specimen (populated **and** empty state) + `DESIGN.md` (prose + register; document the panel order ending in the list). **Leave the deferred on-graph `link-edges` (registry ~345) as `planned` — that is NOT this item** (on-graph edges and per-card link badges are explicitly deferred).

### 4. Warning card cap actions (Lifecycle caps, §7.9)
The cap *inputs* already exist (Lifecycle band: Max turns + Context % on both Create ~`mockup.html:825` and Details ~646) — **don't rebuild those.** The gap is the **Warning inbox card**, which today offers only **Acknowledge/Reply** (`behavior.js` ~1676; gallery ~603; `DESIGN.md` ~108). A **cap-crossing** Warning must offer **Continue / Raise cap / Stop** (+Reply) — Stop reuses `--danger`/`btn-danger`; "Raise cap" naturally ties to the Lifecycle stepper. **Keep a generic Acknowledge variant** for non-cap warnings (approaching rate/usage cap) — i.e. two Warning variants, not a blanket replace. Notify-only throughout (no auto-kill; Stop is user-initiated). Propagate to gallery (both variants) + `DESIGN.md`.

### 5. Segmented run-strip — the completion-% decision (Run-strip, checklist & marquee, §7.10)
The run-strip (`styles.css` ~199-212; gallery ~380) is a single continuous fill with the barber-pole as its only "indeterminate" form. Add the decided **segmented** variant: **done ÷ total**, a **vertical separator per step** (reuse `--border`/`--border-width`), with the **current in-progress step labelling the bar** (mono; reuse `--font-mono` + a small type size — register a new token only if needed). **Keep the barber-pole as the floor** (runs with no checklist). Convert at least one active card to the segmented form and keep a barber-pole card as the floor example. Keep it **decoupled from the marquee activity line** (the step label lives on the bar, not the ticker). Propagate to mockup + gallery (segmented specimen alongside the barber-pole) + `DESIGN.md` (rewrite the run-strip paragraph ~81) + tokens (only if a label token is added).

### 6. Recipient mini-badge — the message addressing schema (Addressing, §7.2)
Messages cards lead with sender badge → status → direction only (`behavior.js` ~1405-1412); the `MSGS` sample data has no recipient field. Add a typed **`recipients[]`** field to `MSGS` (`user | <agent-id> | scratch`, default `[user]`) and render a compact **recipient mini-badge** after the sender (e.g. sender → "→" → recipient → status → dir). Reuse `identity-badge` at a smaller size. `recipients[]` is **addressed-to / routing** (it drives the From/To filter + Sent/Received direction) — **not visibility** (every message still shows regardless). Propagate to styles + mockup (verify it fits the narrow right-column width) + gallery (specimens: agent→user, user→agent(s), →scratch) + `DESIGN.md` ("How messages read" ~214, Messages row ~96, register a `recipient-badge` slug in the Badges registry ~343).

### Confirmed correct — do NOT change (and a tracker error to ignore)
- **The Plan inbox card** (inbox event detection — Inbox, §7.8). It correctly ships **Review (→ Library Plans) + Reply** with **no Approve/Reject** (`behavior.js` ~1672; `DESIGN.md` ~113) — that is the intended design: plan verdicts (Approve/Revise/Reject) live **only in the Library Plans tab**, never on the Inbox card. The inbox-detection entry's `Decision:` line that reads "Approve/Reject for Plan" (~tracker line 148) is a **known error in the doc** — **ignore it.** Leave the Plan card exactly as-is; do **not** add Approve/Reject to it.

### Optional cosmetic (do if cheap, skip if it risks the above)
- **Scratch path string:** the Scratch panel header reads `~/.claude/shared/scratchpad.md` (~`mockup.html:1480`); the resolved storage model (The shared scratchpad §7.7 / Storage & the data model §8) is `<project>/.awl/scratchpad.md`. Update the illustrative string if you want the mockup to reflect it (copy, not a token).
- **The link fire contract (Links, §7.6):** optionally add one sentence to the `DESIGN.md` Linking prose noting fire = reply-completion / one-inbound-in-flight. Not blocking.

## Guardrails (the ones easy to get wrong)

- **Don't redo the first pass.** The eight 🎨-tagged decisions (identity, subagents, permissions, Library, prompt composition, settings, Retire & Delete, Console) are already landed — confirm-don't-touch unless an item above explicitly extends them.
- **These items aren't 🎨-tagged in the tracker — that's expected and not a reason to skip them.** This pass exists precisely because the doc under-tagged its linking/feed design work. Build them from their tracker `Decision:` paragraphs.
- **Build from `Decision:`, never `Recommended:`** (several `Recommended` lines state superseded/reversed policy).
- **The link tracking list is the bottom list only** — on-graph link edges and per-card link badges are deferred; don't add them.
- **The cap Warning is notify-only** — the Warning actions never auto-kill; Stop is a user action.
- **The segmented run-strip's denominator can grow mid-run** (the bar can step backward) — that's the honest behavior; never fabricate a %.
- **Don't disturb the OQ-2 marker** — the `inbox-section` `data-status="undecided"` (fold-vs-catalog) is a separate open question; leave it.
- **No reference to `TODO.md`** anywhere you write.

## Exclusions

- **PARKED — the React port:** no React port / no library migration. Static design system only.
- **Backend wiring belongs to the other stream.** The linking engine, inbox/Plan/Decision detection, the run-strip checklist data, recipient routing, and the cap poll-loop are all backend. You draw the surface; you don't wire it.
- **The Plan inbox card:** correct as-is (Review + Reply, no Approve/Reject) — do not touch it; the tracker's "Approve/Reject for Plan" line is a doc error, not a gap.

## Working style (ultracode)

Work in the live working tree — **no git worktrees** (uncommitted/untracked baseline). The gaps fall into three largely-disjoint lanes you can parallelize across subagents that share the tree (partition by region; serialize edits to shared hotspots like `mockup.html` / `behavior.js` / `DESIGN.md`): **(A)** the Link Config drawer — the relationship-model reframe + End-After + the link tracking list (one coherent surface, do together); **(B)** the inbox/lifecycle — the Warning card cap actions; **(C)** the glance-card + feed — the segmented run-strip + the recipient mini-badge. You own sequencing, integration, and verification.

## Verification (per CLAUDE.md, required — this renders)

Serve over `http://localhost` (Playwright MCP blocks `file:`; if MCP is locked/drops, fall back to headless Chromium over localhost). Iterate **headless** at the **narrow and wide extremes** and **drive every new control**: the reframed drawer (Relationship multi-select, Shared-context disclosure, content-type multi-select, backfill toggle, reordered rows), the Save/Delete strip, the new link list, the Warning card's three cap actions (and the generic-Acknowledge variant), the segmented run-strip (vs the barber-pole floor), and the recipient mini-badge on Messages cards. Screenshot each state, compare to the item's `Decision:`, fix what's off — then finish with **one headed parity pass** re-screenshotting the touched states at both extremes. The gallery must be exhaustive: every touched/new component present as a live `gx-card`, every variant shown.

## Finish

- Append one `DEVLOG.md` entry per the project rule (re-read from disk first): what this pass produced, the observable outcome, and a `Files:` line.
- Report back with: the per-item outcome for the six gap items (drawer reframe, End-After, link list, Warning cap actions, segmented run-strip, recipient mini-badge — what landed, which files), confirmation the **Plan inbox card was left as-is** (it's correct; the tracker line is a doc error), any optional cosmetic done, and confirmation of the headed parity pass (or the fallback used).
