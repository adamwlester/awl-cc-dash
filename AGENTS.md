# AGENTS.md

## Codex Entry Point

This repository's primary project guide is `CLAUDE.md`. Read it before doing
repo work, then follow the relevant docs it points to, especially
`docs/ARCHITECTURE.md`, `design/DESIGN.md`, and `DEVLOG.md` when the task
touches architecture, UI/design, or repo history.

## Codex Support Role

Codex agents are being used as support capacity for this repo so work can
continue when Claude Code / Claude Max plan tokens are limited. Treat Codex
work as complementary to the existing Claude Code workflow: preserve the same
project conventions, keep handoffs clear, and avoid changing Claude-specific
configuration unless explicitly asked.

Use Codex for focused implementation, review, cleanup, documentation, testing,
and repo-management tasks that can safely offset token usage from the Claude
Max plan. When a task depends on Claude Code behavior, bridge sessions, or
multi-agent dashboard assumptions, verify against `CLAUDE.md` and the relevant
project docs before editing.

## Working Rules

- Keep changes scoped to the user's request.
- Prefer existing project patterns over new abstractions.
- Do not create or switch branches without explicit permission.
- Run relevant tests or checks when practical.
- If you change repository files, update `DEVLOG.md` according to the rules in
  `CLAUDE.md` before finishing.
