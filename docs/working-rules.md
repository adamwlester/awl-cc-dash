# Working rules

How agents work in awl-cc-dash beyond the shared instructions in `C:\Users\lester\MeDocuments\AI\AGENTS.md`. The short form of each rule is in the repo's [AGENTS.md](../AGENTS.md); this file carries the detail.

## Replies

- **Plain overview first, especially on the backend.** The FastAPI sidecar, the bridge, drivers, server-sent events (SSE) and async code are largely outside the user's comfort zone. Open with a short, lay-language summary framed in outcomes (what is going on, what you did, what you propose) before the technical specifics. When he asks for "a high-level overview", that is the default he already wants, not a special mode.
- **Match the moment.** Read his register and mirror it: some moments want three tight lines, others the full breakdown. When you cannot tell, go lighter and let him pull for more, but never below the point where he can follow it on first read. Uncontextualized terseness and filler padding are the problems, not length.
- **Name things.** List the actual items, files, folders, sections and actions; "the items you approved" or "a few things are lined up" is a failure.
- **Cite code as a clickable path with a line anchor**, for example `[main.py:42](sidecar/main.py#L42)`, never a bare filename or an unlocated "the handler". A pointer is an address, not an explanation: never drop a bare section number, file or symbol (a naked "§7.5" or "the driver seam") as if he already knows it; say in plain words what it is and why it matters, then attach the link.
- **Status marks sparingly.** An occasional warning or check mark where it earns attention; never one per line, and never numbered-emoji headers unless he asks for that format.
- **End a run with a one-line git check-in:** what merged back to `main`, and anything you would suggest keeping as a branch, so he can approve or decline what lingers.

## Editing

- **Preserve intent: carry untouched parts forward faithfully.** When you edit a file or produce a new version of an existing artifact (for example a new user interface (UI) mockup branched from the prior one), reproduce the parts you were not asked to change exactly as they were. Do not skip, summarize, simplify, restyle or drop sections because reproducing them is tedious. When in doubt keep the prior version intact, and before finishing confirm nothing outside the requested change was lost or quietly altered.
- **This is not a license to under-edit.** When a task calls for a real refactor, change every place the change reaches; timid, partial edits are their own failure.
- **Transient files:** prefix any filename you pass to screenshot or export tools with `.scratch/`. One-off files there may be deleted when done.

## Git permissions

`.claude/settings.json` has an empty `permissions.ask` list on purpose (as of 2026-07-15): the branch and worktree permission gates are off so long or unattended runs never stall on an approval prompt. Keep it that way unless the user says otherwise.

## Bridge sessions

The bridge drives Claude Code agents as detached tmux sessions in Windows Subsystem for Linux 2 (WSL2) and reads them through `capture-pane` (screen state) and the JSON Lines (JSONL) transcript (messages), so a session needs no window to run or be read. A Windows Terminal tab is only a way for a human to watch a session; an automatically opened tab steals the user's focus and routes his keystrokes into the command-line interface (CLI) mid-task.

- **Programmatic creation never opens a tab.** Anything that creates sessions in code (the test suite, fixtures, batch spawns, the sidecar's bridge driver, scratch scripts) creates them tab-less. Do not reintroduce automatic tab-opening when adding any of these.
- **A tab opens only on a deliberate human request:** the dashboard user choosing to attach in the product, the user asking to watch a session during development, or a human running `python -m bridge create` by hand at a terminal (invoking the command is itself the request, so the CLI may default to showing a tab). The mechanism is the opt-in path, currently `create(..., show=True)` or the `show()` method.
- This rule constrains automatic behavior only; it does not limit the product's deliberate manual-attach feature, which `design/DESIGN.md` calls out as a tmux advantage. Implementation: [ARCHITECTURE](ARCHITECTURE.md) §6.4.

## Codex

Codex agents serve as support capacity when Claude Code usage is limited: focused implementation, review, cleanup, documentation, testing and repo management. They follow the same conventions, keep handoffs clear, and do not change Claude-specific configuration (`.claude/`) unless asked. When a task depends on Claude Code behavior, bridge sessions or multi-agent dashboard assumptions, check [ARCHITECTURE](ARCHITECTURE.md) and the relevant docs before editing.
