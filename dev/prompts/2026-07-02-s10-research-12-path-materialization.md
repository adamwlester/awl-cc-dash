# RESEARCH PROMPT — Attachment / citation path materialization across the WSL2 ↔ Windows filesystem boundary

> Paste this entire message into a fresh ChatGPT or Claude web session. It is fully self-contained — you do not need any repository or local file.

## Standing note (read first)
You have NO access to the awl-cc-dash repository or any of its files. Answer from general knowledge, official Claude Code / WSL2 / tmux documentation, and the web. Cite your sources inline. Tag every finding with a confidence level — **confirmed** (documented, or you verified it), **plausible** (reasonable inference, untested), or **speculative** (educated guess). Explicitly flag any claim that would need to be verified against the actual repo or a live spike before we rely on it. Everything you need is embedded below; do not ask for files.

## System context
awl-cc-dash is a single-window Electron desktop app (Windows, one operator) that talks to a FastAPI "sidecar" service on `127.0.0.1:7690` over HTTP + Server-Sent Events. The sidecar is the brain: it owns all cross-agent coordination state. The sidecar drives Claude Code coding-agent sessions as DETACHED tmux sessions running inside WSL2 (Windows Subsystem for Linux 2, Ubuntu) — one real `claude` CLI process per agent — and reads each agent through two channels: `tmux capture-pane` (a ~1s poll of the terminal screen) and the agent's JSONL (JSON-Lines) transcript file on disk. The primary control path is this tmux / terminal-UI (TUI) bridge — **NOT** the Claude Agent SDK. (A second, limited-use in-process Agent-SDK driver exists only for non-interactive utility passes like a "Revise/Summarize" text rewrite; it never drives the interactive coding agents and is not the main path.) WSL2↔Windows is a real boundary in both directions: `localhost` inside WSL2 does not reach the Windows host, and — the subject of this prompt — the two sides see the filesystem differently.

Question-specific detail you need:
- The dashboard works on ONE project at a time — a single repo root — and persists that project's data in a folder inside the project. The TARGET layout is `<project>/.awl-cc-dash/` with subdirs `plans/`, `docs/`, `assets/`, and `state/`; attachment and citation media are intended to live in `assets/`. **None of that is built yet:** today the folder is a flat `.awl/` holding only two files (a scratchpad and a plan-reviews JSON), the `assets/` home does not exist, and the media/document storage path is unbuilt (it currently defers assets/media and document write-back). So the file/path story for attachments is greenfield.
- Three processes hold three filesystem views of the SAME byte-file. The SIDECAR runs on Windows. The RENDERER runs on Windows (Chromium) and would open the file as `C:\...\.awl-cc-dash\assets\foo.png`. The AGENT runs inside WSL2 and would open the same file as `/mnt/c/.../.awl-cc-dash/assets/foo.png`.
- The system already has working, MOUNT-ONLY path translation between the two views: Windows→WSL (`C:\Users\x\f` → `/mnt/c/Users/x/f`) and WSL→Windows (`/mnt/c/Users/x/f` → `C:\Users\x\f`). It ONLY translates `/mnt/<drive>/` mounts. Built on top of it, the sidecar already computes WSL-reachable `/mnt/...` forms of a couple of project files and hands those absolute paths to agents — a working primitive, but mount-only and with no path canonicalization.
- The sharp edge: if a project lives on the WSL-NATIVE filesystem (e.g. `~/proj` or `/home/user/proj`, which Windows sees only as a `\\wsl$\` / `\\wsl.localhost\` UNC path — a Windows `\\host\share`-style network path), there is NO `/mnt/c` form and the mount translation is asymmetric or a no-op. That case is the unsolved part.
- Note on a related but SEPARATE precedent: the intended design is for Claude Code's plan-mode output directory to be set to an ABSOLUTE, canonicalized WSL path (`<canonical project root>/.awl-cc-dash/plans`), precisely because a relative `./` would resolve against the agent's raw current working directory (cwd) and break the same-folder invariant. **This is documented intent, NOT built** — today no such directory setting is written into agents' launch config and project-root resolution does no canonicalization. Treat "make an agent-facing path absolute and WSL-shaped" as a desired move the system is only partway toward, not a finished foundation.
- One more available primitive: the bridge can materialize large per-agent files directly onto the WSL filesystem by piping bytes through a `cat > file` stdin write (it does this to dodge Windows' ~32 KB command-line-argument limit — a Windows `argv` cap that raises `WinError 206`, not a tmux limit). The useful takeaway: writing an attachment's BYTES onto WSL-side disk from the Windows host is already a solved move; prompt TEXT into a running agent, by contrast, goes in via tmux keystrokes, not stdin.

## The question
When an operator attaches a file to a message, or an agent cites a file, (a) where does that file get a real on-disk home, and (b) how is the file's PATH rewritten so that BOTH the Windows Electron renderer AND a WSL2 coding-agent can resolve and open the SAME referenced byte-file? The crux is the WSL2 ↔ Windows filesystem boundary — not the attachment-chip UI.

## Constraints on a valid answer
- The Windows↔WSL2 filesystem boundary is the entire problem. Do NOT solve the chip UI, the upload widget, or the event plumbing.
- The answer must work whether the project sits on `/mnt/<drive>` (a Windows drive, symmetric mount translation) OR on the WSL-native filesystem (a `\\wsl$\` UNC path from Windows, asymmetric / no `/mnt` form) — OR it must explicitly bound its scope to one case and say so plainly.
- No dependence on unshipped, preview, or experimental CLI/OS features. Assume a current stable WSL2 + Ubuntu + Windows 11 stack.
- The answer must degrade to an honest fallback: if no reliable cross-boundary path story exists, attachments remain display-only chips (no agent-openable file) until a storage/path story lands. State that fallback explicitly.
- You MUST weigh these design decisions explicitly:
  - **Canonical stored form** — store a WSL-absolute path? a Windows-absolute path? or a project-RELATIVE path that is rewritten per-receiver at delivery time (WSL form to the agent, Windows form to the renderer)?
  - **Copy vs reference** — copy the attached file INTO `<project>/.awl-cc-dash/assets/` vs. reference it in place at its original location.
  - **Access performance/reliability** — `/mnt/c` access (a Windows drive seen from inside WSL) vs. `\\wsl$\` UNC access (the WSL-native filesystem seen from Windows), including the known throughput and reliability differences between them.
  - **Boundary pitfalls** — symlinks, case-sensitivity differences, file permissions/ownership, line-ending / binary integrity, and file locking across the boundary.
  - **Writer/reader direction** — how the Windows-side sidecar reliably WRITES into an assets directory that WSL agents then READ (and the reverse, when an agent cites a file the renderer must display).

## What is already known / assumed (do not re-derive)
- Mount translation for `/mnt/<drive>/` paths is a SOLVED, working primitive here (both directions). The `\\wsl$\` / WSL-native direction is the UNSOLVED part — focus effort there.
- `assets/` inside `<project>/.awl-cc-dash/` is the intended destination for attachment/citation media (not yet built).
- The sidecar already hands agents WSL-reachable `/mnt/...` absolute forms of certain project files — so "give an agent a `/mnt/...` path it can open" is proven for projects on a Windows drive.
- The sidecar and renderer both run on Windows; the coding agents run in WSL2. Bytes can also be written onto WSL-side disk from Windows via a `cat > file` stdin pipe when a path alone won't do.

## Deliver a structured report
Produce a single structured report the operator can paste straight into their research notes. Use exactly these sections:
1. **Restated question** — the question in your own words, to confirm framing.
2. **Options considered** — each distinct approach, described concretely.
3. **Trade-offs** — for each option: what it costs, where it breaks, what it assumes.
4. **Per-finding confidence** — tag each material claim confirmed / plausible / speculative (inline tags are fine).
5. **Sources & citations** — links/titles for every non-obvious claim.
6. **Recommendation + fallback** — one concrete recommended path, AND the honest fallback if the recommendation proves infeasible.
