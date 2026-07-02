# Unverified Behavior Candidate Review

Date: 2026-07-02

Goal: find places where the repo already describes wanted behavior, but the behavior is not yet proven,
not wired, or still has an unclear implementation path. This is a triage note only; it does not change
`docs/ARCHITECTURE.md` or `dev/notes/TODO.md`.

Reviewed the numbered source set from the session. Note: `dev/notes/coverage-map.md` had already been
moved to `archive/dev/notes/coverage-map.md`, so I reviewed the moved archive copy. I also checked
`archive/notes/data-model-map-2026-07-01.md` because it is open in the session and backs the current
NEXT UP -- BUILD list.

## Candidate Items

1. **Inject behavior needs a doc-sync decision.**
   The architecture queue still treats "true mid-run Inject" as open, but `sidecar/main.py`,
   `sidecar/drivers/bridge.py`, `tests/test_sidecar_unit.py`, and `tests/test_hookbus_unit.py` all describe
   hook-boundary Inject as spike-proven and wired. In plain terms: the dashboard can hand a message to a
   running agent at the next tool/stop hook boundary, but it still cannot shove text into the model while it
   is actively thinking.
   **Rec:** review this first. Either remove/demote the architecture open item if hook-boundary Inject is the
   intended final behavior, or rename it to "earlier-than-hook-boundary Inject" and keep only that narrower
   problem open.

2. **Plan/Decision cards are split between "notice it" and "answer it."**
   The architecture wants `ExitPlanMode` and `AskUserQuestion` to become actionable dashboard cards.
   `sidecar/main.py` says the hook path can detect-and-surface them, but the richer hold-for-answer /
   `updatedInput` / approve-resume loop still needs live proof.
   **Rec:** keep this as a high-priority architecture queue item, but split the wording: detection may already
   be supported; the unproven part is dashboard answer/resume.

3. **Mid-run permission mode has a plausible POC path now.**
   The current bridge leaves `set_mode()` as a no-op because Claude Code only cycles modes with Shift+Tab.
   The mode-control research found a plausible read-compute-send-verify loop using tmux `BTab`, plus a
   possible `/plan` shortcut whose persistence is untested.
   **Rec:** keep high priority. Run a small live POC before declaring mode permanently launch-only.

4. **Fast Mode and Thinking Mode are UI-visible but backend-blocked.**
   `sidecar/drivers/bridge.py` leaves `set_fast()` and `set_thinking()` as no-ops; the archived coverage map
   called these impossible on the bridge. The design still mentions Opus Fast Mode / Thinking controls.
   **Rec:** add either an architecture open/omitted entry or a design clarification. Do not leave them as
   implied live controls without an explicit bridge story or an explicit fallback.

5. **Permission handling has newer native hook surfaces worth re-checking.**
   The current product supports binary approve/deny by keypress and intentionally omits Always Allow because
   option 2 was never live-verified. The CLI/API research also documents PermissionRequest hooks,
   `--permission-prompt-tool`, and remote permission responses that may be cleaner than screen-menu driving.
   **Rec:** do not restore Always Allow by default. Do a research spike only if smoother permission automation
   becomes a product goal.

6. **Console raw feed has two separate gaps.**
   The architecture queue covers terminal fidelity (ANSI colors, spinners, box drawing). Separately,
   ARCHITECTURE says the live mirror feed and keystroke passthrough are not wired yet, while the design says
   the console surface is design-final.
   **Rec:** keep the fidelity item, but track wiring separately from rendering fidelity: first prove live
   mirror + command passthrough, then decide whether ANSI/xterm-level rendering is worth it.

7. **Context breakdown and Compact controls need reality checks.**
   DESIGN describes an on-demand context pull with per-category rows, and TODO scratch asks for compact
   multi-select/history. Current bridge code derives total usage/turns from JSONL, while the older coverage
   map says category breakdown comes only from `/context` table scraping. The compaction reference says
   `compact_boundary` transcript metadata can identify compact events.
   **Rec:** add a medium-priority research item unless already intentionally omitted. Decide whether the
   product will parse `/context`, settle for total/turn usage, or move richer compaction controls to an SDK
   path.

8. **Projects tab concept is verified only as a scratch UI.**
   TODO points at `.scratch/ui-snippets/projects-tab.html`, and that snippet says it is concept-only:
   only the Projects tab is live, other tabs/close are inert, and it must be rebuilt across the six design
   files. It also implies backend semantics: one open project, close-but-agents-keep-running, close-and-stop,
   and reopen/reattach.
   **Rec:** keep the design item active, and open a follow-up backend question for project registry and
   close/reopen semantics once the design lands.

9. **One-click app launch overlaps with project close semantics.**
   ARCHITECTURE already has one-click Electron-spawns-sidecar as an open question. The Projects concept adds
   a related but distinct question: what happens to running tmux agents when the app or project closes?
   **Rec:** keep one-click launch in the architecture queue, but mention that it should be tested together
   with project close/reopen behavior, not as a standalone packaging chore.

10. **Storage, cold restore, and delete are implementation gaps, not mostly research gaps.**
    TODO NEXT UP -- BUILD and the archived data-model map already spell out the storage rename, project
    state store, transcript pinning, cold restore, and delete-to-project-state work. The riskiest bit is
    cold restore: today's dead tmux records are pruned, while the desired behavior is `claude --resume`.
    **Rec:** leave these in TODO/build, not the open-question queue, unless the `--resume` path fails in a
    live spike.

11. **Permanent Delete is currently inconsistent across layers.**
    ARCHITECTURE describes full delete/wipe/tombstone behavior, while the React Agent panel still says
    Delete is deferred and Retire is the available action. `sidecar/deletion.py` models deletion, but the
    project-state cleanup is still a TODO item.
    **Rec:** treat this as a doc/code alignment candidate. Verify the actual endpoint/UI before calling
    Delete supported.

12. **Link edges are planned, but dense-link readability is still undecided.**
    DESIGN, mockup, gallery, behavior.js, and TODO all agree that graph edges are designed/planned but not
    drawn. TODO also has an open item for dense link graphs once edges exist.
    **Rec:** keep D2 as build work and D3 as the follow-up design decision. Do not move dense-link behavior
    into ARCHITECTURE until basic edges exist.

13. **Link drawer actions are still mock actions.**
    The link drawer exists visually, but Save/Delete are toast/counter only and link-list row click is a
    planned master/detail extension. This is different from link-edge drawing.
    **Rec:** verify whether the React/backend link endpoints are enough to wire the drawer. If not, make a
    focused TODO item for link persistence/edit/delete UI wiring.

14. **Review chip and reviewer-agent workflow are only groundwork.**
    DESIGN says the Review chip is groundwork for a deeper single-reviewer-agent workflow, and the gallery
    marks it planned/toast-only. TODO B2 also needs plan edit-in-place plus Approve/Revise -> live resume.
    **Rec:** fold this into the Plan/Decision action-loop investigation. Do not treat Review-chip UI as proof
    that the review workflow exists.

15. **Attachments, citations, and Assets need a real file/path story.**
    DESIGN marks citation/attachment routing as planned; `sidecar/library.py` says assets/media and doc
    write-back are deferred; the old coverage map calls path materialization and WSL/Windows path rewriting
    investigation items.
    **Rec:** make this a storage/filesystem follow-up after the `.awl-cc-dash/assets/` home exists. The key
    question is not the chip UI; it is how a receiver reliably reads the referenced file.

16. **Voice features are visible but not confirmed product behavior.**
    DESIGN has per-editor mic buttons, gallery marks mic as planned, and TODO scratch separately asks for
    voice reading with speed control. There is no backend/runtime support reviewed here.
    **Rec:** decide whether voice dictation/reading is in scope. If yes, research browser/Electron speech
    APIs and privacy/offline behavior before treating the mic as more than a visual affordance.

17. **Subagent support has two different open areas.**
    ARCHITECTURE already tracks pending-vs-active status. TODO B4 separately asks for subagent creation and
    management UI. The subagent research shows richer native concepts (`Agent`, async launches, names,
    background tasks, `SendMessage`) than the dashboard currently exposes.
    **Rec:** split the work: keep pending-vs-active in the architecture queue, and create a separate research
    item for subagent creation/management semantics.

18. **Native tasks, workflows, and agent-team messaging are research candidates.**
    TODO has open items for Tasks and native agent-team messaging; scratch notes mention workflows. The
    research files show native-looking concepts (`TodoWrite`, task-management tools, `Workflow`,
    `SendMessage`, team/teammate spawning) but the dashboard has not decided how much to adopt.
    **Rec:** group these into one research pass: "which native Claude Code coordination primitives should AWL
    adopt instead of custom wrappers?"

19. **Settings writes are partly built as reads, but many toggles are still demos.**
    DESIGN marks MCP/plugin switches as planned; the coverage map says registry reads are built/proven but
    global enable/disable, OAuth health, plugin removal/search, config writes, env var writes, and confirm
    gates were not started or only partial.
    **Rec:** keep most of this as TODO/build work. The open question is OAuth/connection health source; the
    rest is write-path implementation with a global-edit confirmation guard.

20. **Usage/limits source boundaries need a small confirmation pass.**
    DESIGN says account info comes from local creds and limits come from live API data. The old coverage map
    and the prior scratch note both warn not to overstate what local files can provide.
    **Rec:** add a small doc-sync/source-boundary note before building the Usage limits UI. Per-agent cost
    should stay low-priority/open or explicitly out of scope.

21. **Handoff and Rewind are designed, but richer artifacts are deferred.**
    DESIGN describes Rewind/Handoff basics and explicitly defers richer handoff summaries/artifacts; TODO B9
    asks for a handoff report later.
    **Rec:** keep the basic Rewind/Handoff mechanics separate from the richer report/artifact feature. The
    latter is a backlog item, not an architecture blocker unless the basic branch/resume path fails.

22. **Evidence labels would make future audits less mushy.**
    The archived coverage map's labels -- proven, derivable-not-built, needs-investigation, impossible --
    are still useful even though its build tables are stale.
    **Rec:** consider adding those labels to either ARCHITECTURE maintenance notes or TODO maintenance rules
    so future agents distinguish "we tested this" from "we guessed this."

## Quick Recommendation

Start with items 1-4 and 7. They are the places most likely to change the architecture open-question list:
Inject may need narrowing/removal, Plan/Decision needs split wording, permission mode has a concrete POC,
Fast/Thinking need an explicit disposition, and context/compact may need a new open item.
