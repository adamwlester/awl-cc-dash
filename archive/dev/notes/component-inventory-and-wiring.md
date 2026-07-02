# Component Inventory and Behavior Wiring

**Source:** `design/mockup.html` (5,297 lines, reconstructed in full and verified faithful).
**Method:** direct grep and region reads of the CSS block (lines ~414 to 2020), the body markup (~2058 to 3464), and the behavior script (~3466 to 5293). Every claim below was checked against the actual file, not against prior session notes.
**Scope:** read-and-report only. This audit changed no other repo files. It exists to feed the forthcoming design-system spec and the component-gallery build roadmap.

## How to read this

Three findings shape everything below, so they come first:

1. **There is no `data-comp` attribute anywhere in the file (0 occurrences).** The canonical-name mechanism the gallery plan depends on (one name tag per element) does not exist yet. Every canonical name in this document is therefore *proposed*, derived from the element's class token plus its role. Adding the name tags is the first concrete task the build roadmap should carry.
2. **The mockup agrees with `DESIGN.md` on the two things that looked like disagreements** (the splitter grip and the link edges). Details are in the "Flagged" section.
3. **The mockup is heavily wired, not a static prototype.** `boot()` renders every list from JavaScript data arrays and wires resize, autosize, jump-pills, hover-cards, and the subagent-wrap observer. The static or stub surface is small and is enumerated explicitly in Part 2.

Class tokens are shown in `code` so this doubles as a grep index. Acronyms are spelled out on first use.

---

# Part 1: Component Inventory

Organized as the gallery would group it: the badge catalog and the inbox card types first (the two families whose variants never appear on screen together), then composite panel-specific components, then cross-cutting primitives.

## A. Badge catalog

This is the centerpiece. These variants are mutually exclusive at runtime, so the gallery is the only place they can be seen side by side.

| Canonical name | Class token(s) | Every variant | Where it appears |
|---|---|---|---|
| Status badge | `.node-badge` / `.nb-*` | Active (`nb-active`), Idle (`nb-idle`), Pending (`nb-pending`), Error (`nb-error`) | Team Graph card; Agent Details header (`det-badge`). Binary run-state, not a count. |
| Subagent badge | `.sbadge` / `.sb-*` | Active (`sb-active`), Idle (`sb-idle`), Pending (`sb-pending`). No `sb-error` is defined. | Subagent strip on the graph card (s1..sN). |
| Lifecycle badge | `.dbadge` / `.db-*` | Active, Complete, Error, Draft, Review, Approved, Sent, Next, Queued, Held (10 total) | Messages cards, History cards, and Plan cards (Plan status maps via `PLAN_BADGE`). |
| Verdict badge | `.vbadge` / `.v-*` | Approve (`v-approve`, green, circle-check), Revise (`v-revise`, amber, triangle-alert), Block (`v-block`, danger, circle-x) | Plans review surface. Built by `verdictBadgeHTML()` from the `VERDICT` map. |
| Count chip | `.req-badge`, `.cnt-chip`, `.fmt-badge` | Tab counts (Plans = 2, Inbox = 4); the Response-format active-option count | Tab bars; the Compose Response control. |
| Connector health badge | `.hbadge` / `.hb-*` | Connected/OK (`hb-conn`, with a success dot), OAuth (`hb-oauth`), Parked (`hb-parked`), Warn (`hb-warn`, reused for "OAuth expired" and "Denied") (4 total) | Settings, MCP (Model Context Protocol) and Config panes. |
| Config-scope badge | `.lc-badge` / `.lc-*` | Live (`lc-live`, e.g. "Live · /effort"), New session (`lc-session`) (2 total) | Settings Config rows, the "where this takes effect" tag. |
| Identity badge | `.agtile` plus label | 16 identity colors (`--ag-crimson` through `--ag-magenta`); the user variant (`.agtile--user`, dashed); full and mini sizes | Graph cards, From/To dropdowns, message/inbox/history headers, the Console bar. |
| Inbox subtype badge | `.inbox-subtype`, `.inbox-subtype--warning` | Error base (red), Warning (amber); labels such as "Connection" and "Max turns" | Inside Error and Warning inbox cards only. |
| Overflow badge | `.badge-more` | "+N" | Multi-badge summaries when the selected count exceeds the cap (default 3). |

That is roughly 11 families and 30-plus individual variants. This is precisely the set that is hard to track from the running app, since most variants are one data state away from being invisible.

## B. Inbox card types

The other never-co-occurring family, rendered data-driven from the `REQS` array filtered through `INBOX_SECTIONS`. Sections render most-to-least urgent: Error, Warning, Permission, Plan, Decision. The section header carries the type (`.inbox-sec--TYPE` with a label and a count); there is no per-card type badge, which matches `DESIGN.md`.

| Type | Card class | Body rendering | Action set |
|---|---|---|---|
| Error | `inbox-card--error` | inline error text (`.rc-body.inbox-err`), danger left-edge | Retry, Dismiss, Reply |
| Warning | `inbox-card--warning` | notice text (`.rc-body`) | Acknowledge, Reply |
| Permission | `inbox-card--permission` | mono command body (`.rc-body`) | Approve, Deny, Always allow, Reply |
| Plan | `inbox-card--plan` | plan summary (`.rc-body`) | Review (routes to Library, Plans), Reply |
| Decision | `inbox-card--decision` | option buttons (`.opt`) | Approve (disabled until an option is picked), Reply |

Error and Warning cards can additionally carry an inbox subtype badge in the header (from the `subtype` field on the request); the other three never do.

## C. Composite, panel-specific components

These are the larger assemblies the gallery should show once, in a representative state, with their sub-parts labeled.

- **Agent node card** (`.node`, Team Graph). Sub-parts in order: `node-meta-strip` (age plus status badge), `node-id` (identity tile, role and name block, model, fast-mode bolt), `node-meta` line, `node-settings` (three `node-chip`: permission, effort, thinking), `node-bars` (Ctx and Turns `pbar` with a `bar-cut` threshold marker and a green/amber/red ramp), `node-band` (`run-strip` barber-pole plus a `node-feed` marquee), `node-subs` (subagent strip, the "no subagents" empty state, or an accordion when the strip wraps). States: `.selected`, `run-active` / `run-idle` / `run-pending` / `run-error`, and `node-feed.idle`.
- **Message card** (`.fcard` in `#msg-list`). Header is identity badge plus lifecycle badge plus title plus time; the body is `msg-blocks` with 7 block kinds (`text`, `think`, `read`, `write`, `bash`, `diff`, `meta`), each shown by a 3-character rail tag rather than an inline label. Diff blocks color added and removed lines (`blk-add` / `blk-del`). Messages carry a block-level rail for multi-select.
- **History card** (`.fcard[data-histcard]`). Same select-to-act model as the feed cards; the header adds an Edit ghost button before the timestamp and a separate expand chevron.
- **Plan card** (`.plan-card`, from the `PLANS` array). A review surface: a feedback nav rail grouped by section, verdict badges, a status badge, and comment popouts.
- **Asset card** (from the `ASSETS` array). A gradient thumbnail, file name, path, and a meta line (type, dimensions, size).
- **Shared doc editor** (`.md` line-numbered view plus an interactive `md-rail`). Reused by both Documents and Plans; the rail supports title/section/line selection.
- **Registry row** (`.reg-row`) and **Settings row** (`.set-row`). The registry row is name and meta plus a health badge plus a switch; the settings row is a key, a value, and a scope tag.
- **Scratch post and Log line** (from the `SCRATCH` and `LOG` arrays). Their own simpler card and line forms.

## D. Cross-cutting primitives

The reusable vocabulary the gallery should anchor on, since these recur in every panel.

- **Buttons:** `btn`, `btn-sm`, `btn-main` (primary, pink), `btn-secondary` (teal), `btn-danger` (danger outline), `btn-danger-solid`, `icon-btn`, `icon-btn--danger`, `ghost-ic`, `ghost-ic--danger`, `mic-btn`, `fill-btn`, `fill-btn--go`, `mini-link`.
- **Split button** (`.split`): the outline variant (`.split--outline`, the Revise control, teal) and the primary variant (`.split--primary`, the Send control, pink). Parts: `split-drop` (chevron plus current-scope label), `split-act` (the action), and `split-menu` (the `split-mi` options with a `sel` state).
- **Merged Export control** (`.ea-dd` / `.exp-btn`): Copy, Export to file, Embed, Attach, with empty-state gating. Mounted at boot via `expMenuHTML` into the Feed and History footers.
- **Response format control** (`.fmt`): `fmt-btn` plus the `fmt-badge` count plus a `fmt-menu`.
- **Segmented controls** (`.seg`): Mode (Plan, Ask, Edit, Auto, Bypass; Bypass uses `seg-danger`) and Effort (Low through Ultra).
- **Tab bar** (`.tabset` / `.tab-btn`): used in every panel and in Settings.
- **Dropdowns and pickers:** `.src-dd` in single (From) and multi (To, Filter) forms with an identity-badge summary in the trigger and an `agrow` list with checks; the color and icon pickers (`.picker`); the role combobox (`.combo`); and the multi-select (`.msel`).
- **Toggles:** `think-tog` and `fast-tog` (Mode toggles), `minitog` (the feed Type/Content filter), `swh` (the settings switch), and `thumb` (the agree toggle).
- **Steppers** (`.stepper`): Max turns and Context percent.
- **Progress bars:** `.pbar`, `.ctxbar`, and `.nbar` (the Ctx and Turns health bars with a threshold cut and a green/amber/red ramp), plus the `run-strip` barber-pole.
- **Accordions:** `.acc` and `.ctx-trigger` (Context and Turns), `subs-acc` (the subagent drawer), and the history timeline.
- **Chips:** `chip` (the version chip, v1.2), `node-chip`, `tok-pill`, and the attachment chip.
- **Jump-to-end pill** (`.jump-pill`): a universal control on scroll regions, shown or hidden by scroll position.
- **Timeline** (`.tl`): the Rewind and Handoff view in Agent Details.
- **Marquee** (`.node-feed` with `trk a` and `trk b`): the scrolling activity text on a node card.
- **Toast** (`.toast`): the transient notification used throughout.
- **Slide-overs:** the Summarize panel (`.feed-overlay`), the Settings step-into view, and the Console step-into view.

---

# Part 2: Behavior, Wired vs Static

Everything here is verified against the script. `boot()` is the master initializer: it builds the icon grids, role comboboxes, and multi-selects; mounts the Export controls; renders every list (`renderAssets`, `renderDocs`, `renderPlans`, `renderFeed`, `renderConsole`, plus `fillAgLists`, `buildTemplateOptions`, `renderAttachStrip`); restores the last tab state from `localStorage`; syncs the Agent panel to the selected node; and wires autosize, jump-pills, the subagent-wrap observer, hover-cards, resizers, and editor mics.

## Wired behavior categories

These are the behaviors that earn real implementation in the mockup, grouped for the spec.

1. **Tab switching.** `switchTab` (the `feed`, `doc`, `prompt`, and `mid` groups), `settingsTab`, the model tabs, and the Rewind/Handoff tri-tabs. Persists the active tab per group to `localStorage`, swaps the matching footer, and re-gates the prompt action row.
2. **Card selection and focus (the column-tie).** `selectNode` calls `repaintAgentPanel`, so clicking a Team Graph card repaints the entire Agent column from the `AG` data. This is the core selection model `DESIGN.md` describes.
3. **Select-to-act selection.** `fcardSel` (feed and history cards toggle `.sel`), `msgWholeSel` and `msgBlkSelMulti` (the Messages block-rail multi-select), `feedSelectAll` and `histSelectAll`, and `pickDecision` (an inbox option). Selection feeds the Export control.
4. **Dropdown and popover open/close.** `toggleSrcPop`, `toggleSourceDD`, `togglePicker`, `toggleCombo`, `toggleMsel`, `toggleFmt`, `toggleSplitMenu`, `toggleAddMenu`, `toggleAttPop`, `toggleExport`, `toggleRevPop`, `toggleVdd`, and `closeAllPopups`, with distinct single-select and multi-select semantics.
5. **Accordion and expand/collapse.** `toggleFcard` (card expand), `subsTrig` (the subagent drawer), the Context and Turns triggers, `toggleBlockClamp` and `toggleLimit` (clamping long content), and `initSubsAcc` (wrap detection that decides whether the subagent strip needs the chevron and drawer).
6. **Empty-state gating.** `eaUpdate` and `eaUpdateAll` enable or disable each Export mode by selection kind and disable the whole Export button when nothing is actionable; the inbox Decision Approve stays disabled until an option is picked; the placeholder fill button stays disabled until a placeholder is active; the jump pill shows or hides by scroll position (`initJumpPills`, `refreshJumpPills`); and the attachment section is hidden when empty.
7. **Cross-panel navigation and hand-off.** `statusJump` routes a status badge to the Inbox, History, or Compose (with expand, select, and a flash on the target card); `inboxReply` opens the Editor pre-filled with a frozen embed block of the request and pre-targets the agent; `inboxRetry` loads the last command into the Editor; `reviewPlan` routes to Library Plans; and `replyTo` pre-targets an agent.
8. **Live form state.** `pickColor` recolors the identity tile live via `--cur-color`; `pickIconChoice` swaps the icon; `segPick`, `setMode`, and `setScope` drive the segmented controls; `toggleThink`, `toggleFast`, and `gateFast` drive the Mode toggles; `step` increments a stepper; `applyTemplate` and `fillPlaceholder` insert and fill template blocks; and `autosize` grows the textareas.
9. **Data-driven rendering.** `renderFeed`, `renderInbox`, `renderPlans`, `renderDocs`, `renderAssets`, `renderHist`, and `renderConsole` build every list from the JavaScript data arrays (`REQS`, `MSGS`, `PLANS`, `ASSETS`, `HIST`, `SCRATCH`, `LOG`, `CON_FEED`). Count badges update dynamically (`refreshInbox` recomputes the inbox count and the awaiting-input line).
10. **Resize and layout.** `initResizers` drags the splitters (mirroring react-resizable-panels), `rz-readout` shows the cursor-following pixel readout of the two adjacent panels, and ResizeObserver instances drive autosize, the subagent-wrap recompute, and the Console step-into pin.
11. **Transient feedback.** `toast` is used pervasively as the stand-in for any action whose real effect is deferred. It is the line between "wired" and "acknowledged but mock," so it is worth treating as its own category.

## Static, cosmetic, or stub (not truly wired)

The full not-wired surface, so the spec can mark each with the planned-status convention.

- **Link edges.** `drawEdges()` and the `LINKS` array still ship, but the `#edge-layer` SVG host is not present in the current graph markup, so the function early-returns and nothing draws. This matches the `DESIGN.md` "planned" status and the in-file comment that the link lines were removed pending proper edges.
- **Link Agents drawer Save and Delete.** `linkSave` and `linkDelete` read the form values, then only toast and bump a counter (`bumpLinks`). No real link is created or removed.
- **Subagent badge click.** The handler is `onclick="event.stopPropagation()"`, a deliberate no-op. This matches `DESIGN.md` ("not yet wired").
- **MCP and plugin enable/disable.** `setSwitch` toggles the switch visual and handles a locked state, but the underlying enable is a scripted demo (toast only, no real server change).
- **Console run.** `runConsoleCmd` pushes a mock line into `CON_FEED`, re-renders the console, and toasts "(mock)". No real agent execution.
- **Review and citation routing.** `sendReview` and `gotoCitation` are toast-only; `gotoCitation` carries an explicit "wires routing later" note.
- **Attachment routing.** `composeAttach` and `openAttachment` navigate to the relevant Library tab and toast, but do not actually attach.
- **Static chrome.** The header chips (WSL2, that is Windows Subsystem for Linux 2, plus tmux and Connected), the footer counts, the clocks, and the Summarize body text are display-only.

---

# Flagged: mockup vs DESIGN.md

1. **Splitter grip: agrees.** `DESIGN.md` says "navy divider rather than a grip nub." The mockup hides the nub (`.rz-grip{ display:none }`, commented "nub removed") and draws the divider with the 3px `.rz-handle::before` that turns teal on hover. Minor cleanup: the `.rz-grip` div is still present as dead markup and should be removed.
2. **Link edges: agrees** (both treat links as planned and not drawn). Note for the status convention: the `drawEdges` function, the `LINKS` data, `drawEdgesSoon`, and a ResizeObserver that calls `drawEdges` all still ship dormant. Good candidate to mark "planned" explicitly so it is not mistaken for live code.
3. **`req-*` drift: partial.** `DESIGN.md` says the per-card inbox request-type badge was retired and the `--req-*` tokens were quarantined. The per-card type badge is indeed gone (the sections carry the type, confirmed), but the class `.req-badge` lives on, repurposed as the teal tab count chip (Plans and Inbox). The legacy name is misleading; the spec should rename it to a count-chip name.
4. **Badge taxonomy gap.** `DESIGN.md` documents count chips, status badges (`nb-*` and `db-*`), and identity badges, but the mockup also ships connector-health badges (`hbadge` / `hb-*`), config-scope badges (`lc-badge` / `lc-*`), verdict badges (`vbadge` / `v-*`), and inbox subtype badges (`inbox-subtype`). These four are real and in use and should be added to the documented badge set and shown in the gallery.
5. **`data-comp` absent.** The canonical-name mechanism the gallery plan relies on (one name tag per element) does not exist in the mockup yet (0 occurrences). This is the first task the build roadmap should add; until then, the names in this audit are proposed rather than read from the file.
6. **Subagent error state.** Status badges define 4 states (active, idle, pending, error) but subagent badges define only 3 (`sb-active`, `sb-idle`, `sb-pending`; no `sb-error`). If a subagent can error, the `sb-error` variant is missing. Worth confirming intent.

---

# Implications for the gallery and spec

These follow directly from the findings and are offered as input, not as new design decisions.

- The gallery must enumerate, at minimum, the 11 badge families and roughly 30-plus variants in section A and the 5 inbox card types in section B, since none of these can be seen together in the running app.
- The canonical-name tags (`data-comp` or whatever the spec settles on) are a prerequisite for the gallery to be authored against real names rather than the proposed ones here.
- The not-wired list in Part 2 maps one-to-one to the items that should carry the planned-status marker, so the gallery does not present dormant code as live behavior.
- The four undocumented badge families (connector-health, config-scope, verdict, inbox subtype) and the `req-badge` rename are the concrete `DESIGN.md` edits this audit surfaces.
