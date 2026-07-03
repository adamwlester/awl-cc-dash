# META-PROMPT — Generate the §10 research prompts

**Role:** You are a *prompt-writer.* Your deliverable is a set of self-contained **research prompts** — one
per research question — each to be pasted into a **separate offline chat session** (ChatGPT or Claude web)
that has **NO access to this repo.** You write the prompts and stop; you do not do the research yourself.

**The critical difference from the build prompts:** the downstream sessions cannot read any file. So each
child prompt must **embed all context inline** — you may read the repo to gather that context, but the prompt
you produce must stand entirely on its own.

---

## 1. Read these first (to gather the context you'll embed)

- `docs/ARCHITECTURE.md` **§10 items #12 and #13** (the two 🔬 needs-research entries) — the source questions,
  with their Evidence / blocker / desired-behavior bullets.
- `docs/ARCHITECTURE.md` **§1–§2** (system-at-a-glance + runtime topology) and `CLAUDE.md` (project identity)
  — so the system-context block you embed is accurate.
- `dev/notes/research/` — existing research notes for style and to avoid re-asking what's already known
  (especially `claude-code-mode-control-research.md`).
- For #12: `sidecar/library.py` (assets/media + doc write-back are deferred there).
- For #13: the coordination-spine modules `sidecar/inbox.py`, `sidecar/links.py`, `sidecar/scratchpad.py`
  (what the dashboard currently does with its *own* wrappers).

---

## 2. The research prompts to produce

**Required core (2):**

1. **#12 — Attachment / citation path materialization.** How do attachments and citations get a real on-disk
   home, and how is a file path rewritten so that **both** a Windows Electron renderer **and** a WSL2 agent
   can resolve and open the *same* referenced file? The crux is the WSL↔Windows filesystem boundary, not the
   chip UI.
2. **#13 — Native coordination primitives.** Which native Claude Code concepts (`Task`, `TodoWrite`,
   `Workflow`, `SendMessage`, agent-teams / teammate spawning) should the dashboard **adopt** versus keep as
   its **custom spine** (inbox / links / scratchpad)? And critically — which of these are actually
   reachable/observable when driving Claude Code as a **TUI over tmux** (the dashboard's primary path), as
   opposed to via the Agent SDK (which the dashboard does not use for the main path)?

**Optional (≤2 more):** in a clearly separated *"Additional research candidates"* section, you MAY add a
prompt for a genuinely research-shaped open question (mechanism unknown) you find while reading — e.g. the
**hook-event-stream adoption** the mode-control research recommends (HTTP hooks posting to the sidecar).
Keep #12 and #13 as the required core; do not pad.

---

## 3. What every child RESEARCH prompt MUST contain (self-contained for an offline chat)

1. **System-context block** — a tight paragraph the chat can reason from without the repo: *awl-cc-dash is a
   single-window Electron desktop app (Windows) that talks to a FastAPI sidecar (:7690), which drives Claude
   Code sessions as **detached tmux sessions inside WSL2** and reads them via `capture-pane` + the JSONL
   transcript. The primary control path is this **tmux/TUI bridge — NOT the Claude Agent SDK.*** Add only the
   detail the specific question needs.
2. **The precise question / decision** to answer — sharp and singular.
3. **Constraints that bound a valid answer** — e.g. the Windows↔WSL2 filesystem boundary; TUI-over-tmux not
   SDK; no dependence on unshipped/experimental CLI features; must degrade to an honest fallback.
4. **What's already known / assumed** — so the session doesn't waste effort re-deriving it (lift the relevant
   facts from §10 + the research notes).
5. **Desired output — a single, self-contained report, delivered for one-action retrieval.** Instruct the
   session to return the whole report as **one Markdown document the human can download or copy in a single
   action** — a downloadable `.md` file if the tool supports it, otherwise the entire report in **one fenced
   code block / canvas / artifact**, never scattered across the chat — and to give a **suggested filename**
   (`s10-research-NN-<slug>.md`) so it drops straight into `dev/notes/research/`. Contents: restated question ·
   options considered · trade-offs · **per-finding confidence** (confirmed / plausible / speculative) ·
   sources & citations · a concrete **recommendation** + a **fallback**.
6. **A standing note to the session:** *You have no repo access — answer from general knowledge and the web,
   cite your sources, and explicitly flag any claim that needs in-repo verification before we rely on it.*

---

## 4. Naming + output

Write each child prompt as its **own file** in `dev/prompts/`, `NN` = the §10 item number:

```
2026-07-02-s10-research-12-path-materialization.md
2026-07-02-s10-research-13-native-coordination.md
# optional:
2026-07-02-s10-research-NN-<slug>.md
```

When done: **DEVLOG** your additions (one entry listing the files created) and **stop.** The prompts are the
deliverable — do not perform the research.
