# Add a Settings panel to the dashboard mockup

Add a new top-level Settings panel to the dashboard UI concept. Branch a new version, `agent-dashboard/design/ui-concept-v9p3.html`, from `ui-concept-v9p4.html`, and apply the "Preserve everything you weren't asked to change" rule in `CLAUDE.md`: reproduce ui-concept-v9p4 exactly and add only what is described here.

## Read first (don't restate context that lives in these)

- `agent-dashboard/README.md` for the design system, layout model, principles, and component conventions. Match them; do not restyle existing UI.
- `agent-dashboard/design/ui-concept-ui-concept-v9p4.html` as the base.
- `docs/human-notes-misc.md` for the "Global Config Surface" backlog item, the MCP server list, and the CLI parameter lifecycle map (use the map to mark which settings are live vs. need a new session).

## Placement and form

- Add a gear / Settings control to the right of the title bar, beside the WSL2 / tmux / Connected chips.
- It opens a step-into full-window view that toggles in and out, not a fourth always-on column. The 3-pane view returns on exit. Stay within the "no floating popups" principle.

## Structure: subject tabs, scope inside

Tabs are by subject, not by elevation. Inside MCP, Plugins, and Config, show scope (user / project / local) as a secondary segment; never split one subject across tabs.

- **Usage**: plan, limits, token consumption (the /stats and /status surface). Usage only, no dollar/cost spend (the README lists per-agent cost/spend as out of scope).
- **MCP**: server registry with enable/disable, connection/OAuth health, and the disabled-server "parking" state. Scope: user / project.
- **Plugins**: installed plus enabled state, and marketplaces. Scope: user / project / local.
- **Config**: default model, permission mode, sandbox, hooks, env, CLAUDE.md, plans. Scope: global / project. Mark per setting whether a change is live or needs a new session.
- **Setups**: the full Save/Load setup functionality currently in the footer.

## Behavior

- Within each tab, keep read-only status/health/usage visually separate from editable config.
- Gate edits to global (`~/.claude`) config behind an explicit confirm.
- Do not duplicate the Agent panel. This panel owns the global registry and enablement of MCP servers and plugins; per-agent scoping stays in the Agent panel. Do not make "enable server X" here read like "let agent Y use server X" there.
- Keep glanceable quick-access in the footer (a Save/Load action and a usage summary); the panel holds the full detail.

## Ground the content in the real system

Where a tab's content depends on the actual setup, confirm it against the system instead of inventing: read the configured MCP servers and global settings from the Claude config, the installed/enabled plugins, and the available models, and reflect the real environment/bridge status. Keep it representative like the rest of the mockup, but matched to this machine.

Name the panel "Settings" unless the README conventions suggest a clearly better fit.

## Resources

please use the screenshots found in prompts\add-settings-panel\resources to inform your new UI content but modify it to utilize the our palette and neobrutalism.dev theme/style. Note, for prompts\add-settings-panel\resources\vs-code-plugins.png, just emulate the "Plugins" tab elements from the image. Ignore the "Marketplaces" tab.
