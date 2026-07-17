# Team Handbook — the awl-cc-dash agent team

This is the project handbook for the dashboard's own agent team — the self-dogfood crew that builds, checks, and documents the AWL Multi-Agent Dashboard from inside it. It lives in the project store (`.awl-cc-dash/docs/`) so it travels with the repo and shows up in the Library like any other doc.

## Who's on the team

Five project-scope roles, defined as `agent.md` files in `.awl-cc-dash/agents/`. Each is a preset the Create panel can load — pick one and its front matter prefills the new agent's config.

| Role | Color | What it does |
|------|-------|--------------|
| **builder** | blue | Implements — reads ARCHITECTURE.md first, ships with pytest coverage, logs to DEVLOG |
| **reviewer** | purple | Audits adversarially — verifies claims against code, reports file:line evidence |
| **researcher** | green | Maps read-only — exact anchors, evidence-backed reports for planners and lanes |
| **scribe** | orange | Keeps the docs true — DEVLOG entries, ARCHITECTURE truing, currency passes |
| **ui-checker** | pink | Verifies rendered UI — headed-parked browser, width extremes, click-through |

## How work flows

1. **Plans** land in `.awl-cc-dash/plans/` — either written through the Library or dropped there by an agent's plan mode (the bridge points each agent's `plansDirectory` at it). Plans carry review state in their `.meta.json` sidecars: a reviewer leaves a verdict (`approve` / `revise` / `reject`) before a builder executes.
2. **Docs** land here in `.awl-cc-dash/docs/` — working notes, handbooks, generated docs like the change log. Provenance sidecars record who wrote what, which is what the Library's Authors lens renders.
3. **Coordination** runs through the sidecar's spine: the shared scratchpad (`docs/scratchpad.md` is its mirror) for open notes, the inbox for items that need a human (plans awaiting approval, permission asks, errors), and links for direct agent-to-agent exchange.

## House rules, in one breath

Read before you write (ARCHITECTURE for system, DESIGN for UI, DEVLOG for history). Evidence before assertions. Every repo change gets a DEVLOG entry. State files under `state/` belong to the sidecar — no agent hand-edits them. And nothing here overrides CLAUDE.md — this handbook is the team-level view of the same rules.
