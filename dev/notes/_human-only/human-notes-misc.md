<!--
================================================================================
  ⛔ STOP — AGENTS / AI / LLMs: DO NOT USE THIS FILE ⛔
================================================================================
  This file is the HUMAN OWNER'S PRIVATE SCRATCHPAD. It is NOT a source of
  truth, NOT a reference, NOT documentation, and NOT instructions.

  - DO NOT read it for context, decisions, settings, or behavior.
  - DO NOT cite, quote, summarize, or base ANY action or answer on it.
  - DO NOT treat anything here as binding, current, or accurate. It is
    unverified, possibly stale, and possibly wrong on purpose.

  Authoritative sources are: CLAUDE.md, .claude/settings.json, DEVLOG.md,
  and design/DESIGN.md. Use those — never this file.

  If a task seems to require this file, STOP and ask the human instead.
================================================================================
-->

# ⛔ FOR THE HUMAN OWNER ONLY — NOT AN AGENT RESOURCE ⛔

> **Agents/LLMs: ignore this entire file.** It is private human notes — not a
> reference, not documentation, not instructions. Do not read, cite, or act on
> anything in it. Authoritative sources are CLAUDE.md, .claude/settings.json,
> DEVLOG.md, and design/DESIGN.md.

# Claude Code Sandbox

A minimal workspace for learning and testing Claude Code in a way that matches normal project use.

This document is a lose collection of notes. None of this is binding, it is just a means of tracking miscellaneous ideas, concepts and the like.

## Agent Agreement
- **All agents use only `.claude/settings.json`** — no settings.local.json. Keeps config centralized and predictable.

# Multi-Agent Coordination

## Identifying File Creators

When multiple agents work in the same repo, use these approaches to track who created what:

### File Headers
Add a comment header to files created by agents:
```javascript
// Created by Claude-Haiku on 2026-03-26
// Purpose: test utility for X
```

Quick visual identification when scanning files, and easily grep-able.

### Activity Log
Maintain a shared activity log (e.g., `WORK_LOG.md`) where each agent documents what they're doing:
```
2026-03-26 10:45 | Claude-Opus | Created scratch/experiment.js | Reason: testing new approach for auth
2026-03-26 10:50 | Claude-Haiku | Modified config.json | Reason: added test permission
```

This provides both a record of who created what and visibility into ongoing work, decisions, and blockers.

## Keeping Agents Aligned

Use a shared source of truth:
- **README.md or PLAN.md** — Current goals, status, and decisions
- **Structured state file** — JSON/YAML tracking in-progress tasks with reasoning
- **Git commits** — Detailed commit messages that explain the "why"

# Settings dirs
VS Code settings:
```
C:\Users\lester\AppData\Roaming\Code\User\settings.json
```
Claude Code user settings:
```
-C:\Users\lester\.claude\settings.json
```
Some Claude global config:
```
-C:\Users\lester\.claude.json
```

# MCP Server Plan

Global servers go in `~/.claude.json` — configure once, available in all projects.
Project-specific servers go in `.mcp.json` per repo.

## All Servers — Configured in `~/.claude.json`

All entries below are live in config. Search for `YOUR_TOKEN_HERE` in `~/.claude.json` to find placeholders.

| Server | Status | Token Needed | Where to Get It |
|--------|--------|-------------|-----------------|
| Playwright | Ready | None | Local, no auth |
| GitHub | Needs token | `GITHUB_PERSONAL_ACCESS_TOKEN` | github.com > Settings > Developer settings > Personal access tokens |
| Google Workspace | Needs token | `CLIENT_ID` + `CLIENT_SECRET` | Google Cloud Console > APIs & Services > Credentials |
| Slack | Needs token | `SLACK_BOT_TOKEN` | api.slack.com > Your Apps > OAuth & Permissions |
| Zapier | Needs URL | MCP endpoint URL (replaces `YOUR_TOKEN_HERE` in args) | zapier.com/mcp > copy your endpoint URL |
| Firecrawl | Needs token | `FIRECRAWL_API_KEY` | firecrawl.dev > Dashboard > API Keys |
| Apify | Needs token | `APIFY_TOKEN` | console.apify.com > Settings > Integrations |
| n8n | Needs token | `N8N_API_URL` + `N8N_API_KEY` | Your n8n instance > Settings > API |
| Supabase | Ready (OAuth) | None (authenticates via browser) | OAuth flow on first use |
| Neon | Needs token | API key (in args) | console.neon.tech > Settings > API Keys |
| Brave Search | Needs token | `BRAVE_API_KEY` | brave.com/search/api > Get API Key |
| Exa | Needs token | `EXA_API_KEY` | dashboard.exa.ai/api-keys |
| Notion | Needs token | `NOTION_TOKEN` | notion.so/my-integrations > Create integration |
| Linear | Ready (OAuth) | None (authenticates via browser) | OAuth flow on first use |
| Docker | Ready | None | Local, needs Docker Desktop + Python/uvx |
| Cloudflare | Ready (OAuth) | None (authenticates via browser) | OAuth flow on first use |

# Claude Code CLI — Parameter Lifecycle & Agent Scope Map

> How dynamic is each setting? Who does it affect? Where do you set it?
> Focused on CLI (`claude`) behavior. VS Code extension-only settings excluded.

---

## How to Read This Document

Each parameter is tagged with three properties:

**Mutability** — when can the value change?

| Tag | Meaning |
|-----|---------|
| `STARTUP` | Locked at session launch. Change requires a new session. |
| `SESSION` | Changeable mid-session via slash command, but not persisted unless noted. |
| `LIVE` | Evaluated per tool call or event — changes to the config file take effect immediately or on next invocation. |
| `WRITE-BACK` | Slash command writes the value back to `settings.json`, persisting across sessions. |

**Agent Scope** — who is affected?

| Tag | Meaning |
|-----|---------|
| `MAIN` | Applies only to the main session (top-level agent). |
| `INHERITED` | Subagents inherit from parent unless overridden. |
| `PER-AGENT` | Can be set independently per subagent via frontmatter. |
| `TEAM-LEAD` | Agent Teams teammates inherit from the lead; no per-teammate override. |
| `GLOBAL` | Affects the Claude Code process itself, not any individual agent. |

**Config Location** — where is it defined?

| Abbreviation | Path |
|--------------|------|
| `~settings` | `~/.claude/settings.json` (user global) |
| `.settings` | `.claude/settings.json` (project, committed) |
| `.local` | `.claude/settings.local.json` (project, gitignored) |
| `managed` | System-level `managed-settings.json` (IT-deployed) |
| `frontmatter` | Agent `.md` file in `~/.claude/agents/` or `.claude/agents/` |
| `CLI` | Command-line flag (`--model`, `--permission-mode`, etc.) |
| `ENV` | Environment variable |
| `~/.claude.json` | Global config (separate from settings.json) |

**Precedence (highest wins):** managed → CLI args → .local → .settings → ~settings

---

## 1. Identity & Model Selection

These determine *which* model runs and *how hard* it thinks. Model is the most common "why do I need a new session?" culprit.

| Parameter | Mutability | Agent Scope | Config Locations | Notes |
|-----------|-----------|-------------|-----------------|-------|
| `model` | `STARTUP` | `PER-AGENT` | ~settings, .settings, .local, CLI (`--model`), frontmatter (`model:`) | Locked at launch for the main session. Subagents can specify a different model in frontmatter or use `model: inherit` to match parent. `/model` changes it for the *next* session only (does not write back). |
| `availableModels` | `STARTUP` | `GLOBAL` | ~settings, .settings, managed | Restricts the picker — `/model` and `--model` can only select from this list. Not per-agent. |
| `modelOverrides` | `STARTUP` | `GLOBAL` | ~settings, .settings | Maps Anthropic model IDs → provider-specific ARNs (Bedrock/Vertex). Process-level; agents don't override. |
| `effortLevel` | `SESSION` | `MAIN` | ~settings (`WRITE-BACK` via `/effort`) | `/effort low|medium|high` changes mid-session AND writes to ~settings. Subagents don't inherit this — they use whatever the model defaults to. |
| `alwaysThinkingEnabled` | `SESSION` | `MAIN` | ~settings (`WRITE-BACK` via `/config`) | Extended thinking toggle. Main session only. |
| `agent` | `STARTUP` | `MAIN` | .settings, CLI (`--agent`) | Runs the main thread as a named subagent (its system prompt, tools, model). Session-level decision; can't swap agents mid-conversation. |
| `CLAUDE_CODE_SUBAGENT_MODEL` | `STARTUP` | `INHERITED` | ENV | Overrides the default model for *all* subagents that don't specify `model:` in frontmatter. |

---

## 2. Permissions & Tool Access

The core safety layer. The most nuanced area for agent-specificity because subagents have their own permission model that partially decouples from the main session.

### 2a. Permission Mode

| Parameter | Mutability | Agent Scope | Config Locations | Notes |
|-----------|-----------|-------------|-----------------|-------|
| `permissions.defaultMode` | `STARTUP` | `MAIN` | ~settings, .settings, .local, CLI (`--permission-mode`) | Sets the mode on session launch. Can be cycled with `Shift+Tab` during the session (runtime change, not persisted). |
| Subagent `permissionMode` | `STARTUP` | `PER-AGENT` | frontmatter | Each subagent `.md` can declare its own mode. **Overrides the parent's mode** — a subagent can be `dontAsk` even if the main session is `default`. |
| Background subagent permissions | `STARTUP` | `PER-AGENT` | (interactive at spawn) | Background agents batch-prompt you *before launch* for all permissions they'll need, then auto-approve those and auto-deny everything else for the run. Cannot be changed after spawn. |
| Agent Teams teammate mode | `STARTUP` | `TEAM-LEAD` | (inherited) | Teammates inherit the lead agent's permission settings wholesale. No per-teammate override exists. |
| `permissions.disableBypassPermissionsMode` | `STARTUP` | `GLOBAL` | managed, ~settings | Prevents `bypassPermissions` from being activated anywhere. Process-level kill switch. |
| `disableAutoMode` | `STARTUP` | `GLOBAL` | ~settings, .local, managed | Removes `auto` from the mode cycle. |

### 2b. Allow / Ask / Deny Rules

| Parameter | Mutability | Agent Scope | Config Locations | Notes |
|-----------|-----------|-------------|-----------------|-------|
| `permissions.allow` | `LIVE` | `INHERITED` | ~settings, .settings, .local, managed | Evaluated per tool call. Subagents inherit these rules. Adding a new rule to the file takes effect on the next tool invocation within the current session. |
| `permissions.ask` | `LIVE` | `INHERITED` | ~settings, .settings, .local, managed | Forces confirmation even if another rule would allow. Same live evaluation. |
| `permissions.deny` | `LIVE` | `INHERITED` | ~settings, .settings, .local, managed | Evaluated first — always wins. Deny rules block even in `bypassPermissions` mode. Subagents inherit. You can deny specific agents with `Agent(AgentName)`. |
| Subagent `tools` (allowlist) | `STARTUP` | `PER-AGENT` | frontmatter | Whitelist of tools the subagent can use (e.g., `tools: Read, Grep, Glob`). Resolved at spawn; can't be changed mid-run. |
| Subagent `disallowedTools` (denylist) | `STARTUP` | `PER-AGENT` | frontmatter | Blacklist applied on top of inherited tools. If both `tools` and `disallowedTools` are set, denylist is applied first, then allowlist is resolved. |
| Interactive approval (per tool call) | `LIVE` | `MAIN` | (runtime UI) | When you approve/deny a tool call in the terminal, that's a one-time decision. **Not persisted to settings.json.** Foreground subagents pass prompts through to you; background subagents cannot. |

**Evaluation order per tool call:** deny rules → permission mode → allow rules → interactive prompt (or auto-deny in `dontAsk`)

### 2c. Directory Access

| Parameter | Mutability | Agent Scope | Config Locations | Notes |
|-----------|-----------|-------------|-----------------|-------|
| `permissions.additionalDirectories` | `SESSION` | `INHERITED` | ~settings, .settings, CLI (`--add-dir`), `/add-dir` | Extra directories Claude can access. Can be added mid-session via `/add-dir`. Subagents inherit. |

---

## 3. Sandbox (OS-Level Isolation)

Sandbox settings are process-level — they wrap the Bash tool at the OS layer. Individual agents don't get their own sandbox config; they all run inside the same sandbox (or lack thereof).

| Parameter | Mutability | Agent Scope | Config Locations | Notes |
|-----------|-----------|-------------|-----------------|-------|
| `sandbox.enabled` | `STARTUP` | `GLOBAL` | ~settings, .settings, managed | Enables OS-level Bash sandboxing. Must be set before session start. |
| `sandbox.failIfUnavailable` | `STARTUP` | `GLOBAL` | managed | Hard-fail if sandbox can't start. IT policy enforcement. |
| `sandbox.autoAllowBashIfSandboxed` | `STARTUP` | `GLOBAL` | ~settings, .settings | Auto-approve all Bash when sandboxed. Default `true`. |
| `sandbox.excludedCommands` | `STARTUP` | `GLOBAL` | ~settings, .settings | Commands that bypass the sandbox (e.g., `git`, `docker`). |
| `sandbox.allowUnsandboxedCommands` | `STARTUP` | `GLOBAL` | managed, ~settings | Whether the `dangerouslyDisableSandbox` escape hatch exists. |
| `sandbox.filesystem.*` | `STARTUP` | `GLOBAL` | ~settings, .settings, managed | `allowWrite`, `denyWrite`, `allowRead`, `denyRead` — merged across all config scopes. |
| `sandbox.network.*` | `STARTUP` | `GLOBAL` | ~settings, .settings, managed | `allowedDomains`, `allowUnixSockets`, `allowLocalBinding`, proxy ports. |

---

## 4. Auto Mode (AI Classifier)

Auto mode replaces manual permission prompts with a model-based classifier. Config is intentionally restricted — **not read from shared project settings** to prevent untrusted repos from weakening safety rules.

| Parameter | Mutability | Agent Scope | Config Locations | Notes |
|-----------|-----------|-------------|-----------------|-------|
| `autoMode.environment` | `STARTUP` | `GLOBAL` | ~settings, .local, managed | Prose descriptions of trusted infrastructure. Informs the classifier's safety decisions. |
| `autoMode.allow` | `STARTUP` | `GLOBAL` | ~settings, .local, managed | Exceptions to block rules. **Replaces entire default list** — run `claude auto-mode defaults` first. |
| `autoMode.soft_deny` | `STARTUP` | `GLOBAL` | ~settings, .local, managed | Block rules. **Replaces entire default list.** |
| `useAutoModeDuringPlan` | `STARTUP` | `GLOBAL` | ~settings, .local, managed | Use auto-mode semantics during plan mode. Not from `.settings`. |

---

## 5. Hooks (Lifecycle Automation)

Hooks fire custom commands at specific lifecycle events. They're defined in settings files, not agent frontmatter — so they apply to the session as a whole. Subagent-specific hooks exist (`SubagentStart`, `SubagentStop`) but are defined at the session level, not inside the agent.

| Parameter | Mutability | Agent Scope | Config Locations | Notes |
|-----------|-----------|-------------|-----------------|-------|
| All `hooks.*` events | `LIVE` | `GLOBAL` | ~settings, .settings, .local, managed | Hooks are evaluated when their event fires. Adding a new hook to settings takes effect on the next event occurrence. |
| `hooks.SubagentStart` | `LIVE` | `GLOBAL` | (same) | Fires when *any* subagent starts. Matcher filters by agent type/name. Defined at session level, not per-agent. |
| `hooks.SubagentStop` | `LIVE` | `GLOBAL` | (same) | Fires when *any* subagent completes. |
| `hooks.PreToolUse` | `LIVE` | `GLOBAL` | (same) | Can block, allow, or modify tool calls. Fires for main session and subagents alike. |
| `hooks.PostToolUse` | `LIVE` | `GLOBAL` | (same) | Common pattern: lint after `Write|Edit`, re-inject rules after `compact`. |
| `hooks.PermissionRequest` | `LIVE` | `GLOBAL` | (same) | Can programmatically allow/deny permission prompts. |
| `disableAllHooks` | `STARTUP` | `GLOBAL` | ~settings, .settings, managed | Kill switch for all hooks. |
| `allowManagedHooksOnly` | `STARTUP` | `GLOBAL` | managed | Block user/project/plugin hooks. |
| `allowedHttpHookUrls` | `STARTUP` | `GLOBAL` | managed, ~settings | Allowlist for HTTP hook endpoints. |

---

## 6. MCP Servers

MCP server definitions live in `.mcp.json` (not `settings.json`). The settings below control *approval and restrictions* of those servers.

| Parameter | Mutability | Agent Scope | Config Locations | Notes |
|-----------|-----------|-------------|-----------------|-------|
| `.mcp.json` server definitions | `STARTUP` | `INHERITED` | `~/.claude/.mcp.json`, `.mcp.json` | Servers start at session launch. Subagents inherit available MCP tools unless restricted via `tools`/`disallowedTools` in frontmatter. Failed servers can be reconnected via UI without restart. |
| `enableAllProjectMcpServers` | `STARTUP` | `GLOBAL` | ~settings | Auto-approve all project-level MCP servers. |
| `enabledMcpjsonServers` | `STARTUP` | `GLOBAL` | ~settings | Approve specific MCP servers by name. |
| `disabledMcpjsonServers` | `STARTUP` | `GLOBAL` | ~settings | Reject specific MCP servers by name. |
| `allowedMcpServers` | `STARTUP` | `GLOBAL` | managed | IT allowlist. Undefined = no restrictions. |
| `deniedMcpServers` | `STARTUP` | `GLOBAL` | managed | IT blocklist. Wins over allowlist. |
| Subagent MCP tool access | `STARTUP` | `PER-AGENT` | frontmatter | Use `tools:` to allowlist specific MCP tools (e.g., `mcp__github__create_issue`) or `disallowedTools:` to exclude them. Must be configured explicitly — agents that don't list MCP tools in `tools:` won't have access if using an allowlist. |

---

## 7. Context & Memory

These control what survives across sessions, compaction events, and agent boundaries.

| Parameter | Mutability | Agent Scope | Config Locations | Notes |
|-----------|-----------|-------------|-----------------|-------|
| `CLAUDE.md` files | `LIVE` | `INHERITED` | `~/.claude/CLAUDE.md`, `.claude/CLAUDE.md`, `CLAUDE.md` | Loaded at session start and re-read on file change. Subagents get a fresh context but CLAUDE.md is loaded through normal message flow. Survives compaction (re-loaded, not summarized). |
| `/compact` | `SESSION` | `MAIN` | (slash command) | Summarizes conversation history. Lossy — early instructions may be dropped. Can pass focus instructions: `/compact focus on auth`. Session Memory makes this instant if enabled. |
| `/clear` | `SESSION` | `MAIN` | (slash command) | Wipes conversation history. Session file remains on disk. |
| Session Memory | `LIVE` | `MAIN` | (automatic, requires Anthropic API) | Background process writes summaries to `~/.claude/projects/<hash>/<session>/session-memory/summary.md`. Recalled at *new* session start (not resume). Not available on Bedrock/Vertex. |
| Agent memory | `LIVE` | `PER-AGENT` | `.claude/agent-memory-local/<agent-type>/MEMORY.md` | Per-agent-type persistent memory. Agents read/write this file to remember things across sessions. |
| `autoMemoryDirectory` | `STARTUP` | `GLOBAL` | ~settings, .local | Custom directory for auto memory. Not allowed in `.settings` to prevent redirect attacks. |
| `cleanupPeriodDays` | `STARTUP` | `GLOBAL` | ~settings | Delete sessions inactive > N days. `0` = disable persistence. |

---

## 8. Environment & Shell

| Parameter | Mutability | Agent Scope | Config Locations | Notes |
|-----------|-----------|-------------|-----------------|-------|
| `env` | `STARTUP` | `GLOBAL` | ~settings, .settings, .local | Key-value pairs injected into every session's environment. |
| `defaultShell` | `STARTUP` | `GLOBAL` | ~settings | `bash` (default) or `powershell`. Requires `CLAUDE_CODE_USE_POWERSHELL_TOOL=1` for PowerShell. |
| `apiKeyHelper` | `STARTUP` | `GLOBAL` | ~settings, managed | Script that generates auth tokens. Runs at startup. |
| `awsAuthRefresh` | `STARTUP` | `GLOBAL` | ~settings | AWS credential refresh script (Bedrock). |
| `awsCredentialExport` | `STARTUP` | `GLOBAL` | ~settings | AWS credential export script (Bedrock). |
| `forceLoginMethod` | `STARTUP` | `GLOBAL` | ~settings, managed | Restrict login to `claudeai` or `console`. |
| `forceLoginOrgUUID` | `STARTUP` | `GLOBAL` | ~settings, managed | Auto-select org during login. |

---

## 9. Git & Attribution

| Parameter | Mutability | Agent Scope | Config Locations | Notes |
|-----------|-----------|-------------|-----------------|-------|
| `attribution.commit` | `LIVE` | `GLOBAL` | ~settings, .settings | Commit message trailer. Empty string = hidden. Applied at commit time, so changes take effect on next commit. |
| `attribution.pr` | `LIVE` | `GLOBAL` | ~settings, .settings | PR description footer. |
| `includeGitInstructions` | `STARTUP` | `GLOBAL` | ~settings, .settings | Include built-in git/PR instructions in system prompt. Set `false` if using custom git skills. |

---

## 10. UI, Output & Cosmetics

These affect the terminal interface. None are per-agent.

| Parameter | Mutability | Agent Scope | Config Locations | Notes |
|-----------|-----------|-------------|-----------------|-------|
| `language` | `STARTUP` | `GLOBAL` | ~settings | Response language + voice dictation language. |
| `outputStyle` | `STARTUP` | `GLOBAL` | ~settings | Output style preset — modifies system prompt. |
| `voiceEnabled` | `SESSION` | `MAIN` | ~settings (`WRITE-BACK` via `/voice`) | Push-to-talk. Requires Claude.ai account. |
| `statusLine` | `LIVE` | `GLOBAL` | ~settings, .settings | Custom status line command. Re-evaluated periodically. |
| `spinnerVerbs` | `STARTUP` | `GLOBAL` | ~settings, .settings | Custom spinner action words. |
| `spinnerTipsEnabled` | `STARTUP` | `GLOBAL` | ~settings | Show tips in spinner. |
| `spinnerTipsOverride` | `STARTUP` | `GLOBAL` | ~settings | Custom tip strings. |
| `prefersReducedMotion` | `STARTUP` | `GLOBAL` | ~settings | Accessibility: reduce animations. |
| `fastModePerSessionOptIn` | `STARTUP` | `GLOBAL` | ~settings | Fast mode doesn't persist — must `/fast` each session. |
| `showClearContextOnPlanAccept` | `STARTUP` | `GLOBAL` | ~settings | Show "clear context" option on plan accept screen. |
| `feedbackSurveyRate` | `STARTUP` | `GLOBAL` | ~settings | Probability of session quality survey. `0` = suppress. |
| `fileSuggestion` | `STARTUP` | `GLOBAL` | ~settings | Custom `@` file picker script. |
| `respectGitignore` | `STARTUP` | `GLOBAL` | ~settings, .settings | Whether `@` file picker respects `.gitignore`. |

---

## 11. Worktree & Agent Teams

| Parameter | Mutability | Agent Scope | Config Locations | Notes |
|-----------|-----------|-------------|-----------------|-------|
| `worktree.symlinkDirectories` | `STARTUP` | `GLOBAL` | .settings | Directories to symlink into worktrees (saves disk). |
| `worktree.sparsePaths` | `STARTUP` | `GLOBAL` | .settings | Sparse checkout paths for worktrees. |
| `teammateMode` | `STARTUP` | `GLOBAL` | ~settings | How teammates display: `auto`, `in-process`, `tmux`. |
| `plansDirectory` | `STARTUP` | `GLOBAL` | ~settings, .settings | Where plan files are stored. |

---

## 12. Global Config (`~/.claude.json`)

These live in a separate file and are purely process-level preferences.

| Parameter | Mutability | Agent Scope | Notes |
|-----------|-----------|-------------|-------|
| `autoConnectIde` | `STARTUP` | `GLOBAL` | Auto-connect to running IDE from external terminal. |
| `autoInstallIdeExtension` | `STARTUP` | `GLOBAL` | Auto-install VS Code extension. |
| `editorMode` | `STARTUP` | `GLOBAL` | `normal` or `vim` key bindings for input. |
| `showTurnDuration` | `STARTUP` | `GLOBAL` | Show "Cooked for 1m 6s" after responses. |
| `terminalProgressBarEnabled` | `STARTUP` | `GLOBAL` | Terminal progress bar (ConEmu, Ghostty, iTerm2). |

---

## 13. Managed-Only Keys (IT/Admin)

These only take effect in `managed-settings.json`. Cannot be overridden by users or projects.

| Parameter | Purpose |
|-----------|---------|
| `allowManagedPermissionRulesOnly` | Only managed permission rules apply. Users/projects can't define their own. |
| `allowManagedHooksOnly` | Only managed hooks run. |
| `allowManagedMcpServersOnly` | Only managed MCP server allowlist applies. |
| `allowManagedReadPathsOnly` | Only managed `allowRead` paths apply in sandbox. |
| `sandbox.network.allowManagedDomainsOnly` | Only managed network domains apply in sandbox. |
| `channelsEnabled` | Enable channels for Team/Enterprise. |
| `allowedChannelPlugins` | Allowlist of channel plugins. |
| `strictKnownMarketplaces` | Allowlist of plugin marketplaces. |
| `blockedMarketplaces` | Blocklist of marketplace sources. |
| `pluginTrustMessage` | Custom message appended to plugin trust warning. |
| `companyAnnouncements` | Startup messages for users. |

---

## Quick Decision Matrix

**"I want to change X for a specific subagent"** — what's possible?

| What you want to change | Can you do it per-agent? | How? |
|--------------------------|------------------------|------|
| Model | Yes | `model:` in agent frontmatter |
| Tool access | Yes | `tools:` or `disallowedTools:` in frontmatter |
| Permission mode | Yes | `permissionMode:` in frontmatter |
| System prompt | Yes | Body of the agent `.md` file |
| MCP tool access | Yes | List specific `mcp__server__tool` in `tools:` |
| Hooks | No | Hooks are session-level; use matchers to filter by agent name |
| Sandbox config | No | Process-level; all agents share the same sandbox |
| Effort level | No | Main session only |
| Allow/deny rules | No (but inheritable) | Rules in settings.json are inherited; use `Agent(Name)` deny syntax to block specific agents |
| Environment variables | No | Process-level |
| Context/memory | Partially | Subagents get isolated context windows; agent memory files are per-agent-type |

**"I changed a config file — do I need to restart?"**

| Changed... | Need new session? |
|------------|-------------------|
| `model` | Yes |
| `permissions.allow/deny` rules | No — evaluated per tool call |
| `hooks.*` | No — evaluated per event |
| `CLAUDE.md` | No — re-read on file change |
| `sandbox.*` | Yes |
| MCP server definitions | Yes (but failed servers can reconnect via UI) |
| `autoMode.*` | Yes |
| `effortLevel` | No — use `/effort` |
| `env` | Yes |
| `outputStyle` / `language` | Yes |

---

# UI Color Theme Resources

Resources for dark UI color themes — specifically "lighter side of dark" / slate / blue-tinted palettes for desktop dashboard apps. Compiled 2026-04-02.

## Browse & Pick (Visual Exploration)

| Resource | Link | Notes |
|----------|------|-------|
| Realtime Colors | https://www.realtimecolors.com/ | Pick colors, see them on a live mock site. Toggle dark mode. Exports CSS. Best starting point. |
| Happy Hues | https://www.happyhues.co/ | Curated palettes shown in context on a real page layout. Click a palette and the whole page recolors. Several dark options with muted tones. |
| Radix Colors | https://www.radix-ui.com/colors | 12-step color scales for UI. Slate, Mauve, and Sage gray scales with blue/purple/green tints. Built-in dark mode variants. Most systematic approach. |
| Colorffy Dark Theme Generator | https://colorffy.com/dark-theme-generator | Give it one brand color → full dark theme with proper contrast. Exports CSS custom properties and SCSS. |
| tweakcn (shadcn theme editor) | https://tweakcn.com/ | Interactive editor for shadcn/ui themes. Modify properties and preview on real dashboard-like components in real time. |
| shadcndesign Theme Generator | https://www.shadcndesign.com/theme-generator | Another shadcn theme generator option. |
| Shadcn Studio | https://shadcnstudio.com/theme-generator | Third shadcn theme generator option. |
| DaisyUI Theme Gallery | https://daisyui.com/docs/themes/ | 35+ built-in themes with live preview on real components. Check out **dim**, **nord**, **business**, and **abyss**. |
| DaisyUI Theme Generator | https://daisyui.com/theme-generator/ | Create custom DaisyUI themes. All export as CSS variables compatible with Tailwind. |
| Coolors | https://coolors.co/generate | Classic palette generator. Tap spacebar to randomize, lock colors you like. Huge community library. |
| Dribbble — dark dashboards | https://dribbble.com/tags/dark-dashboard | 400+ visual references for dark dashboard designs. Inspiration, not code. |

## Drop-in Ready (Test in Minutes)

| Resource | Link | How to use |
|----------|------|------------|
| Catppuccin Tailwind plugin | https://github.com/catppuccin/tailwindcss | **Frappe** and **Macchiato** flavors are lighter-dark. Tailwind plugin, one import. Preview: https://tailwindcss.catppuccin.com/ |
| Catppuccin palette (raw) | https://github.com/catppuccin/catppuccin | Raw color values as CSS variables. 15k+ stars on the org. |
| Rose Pine CSS variables | https://github.com/barelyhuman/rose-pine-css | Drop-in CSS file. **Moon** variant is a soft dark. Just `<link>` it. Preview: https://rosepinetheme.com/ |
| Open Props | https://open-props.style/ | Sub-atomic CSS custom properties. Has dark and **dim** themes (the lighter-dark aesthetic). Single CSS import → surface/text/brand variables. Theme file: https://github.com/argyleink/open-props/blob/main/src/extra/theme.dark.css |
| DaisyUI npm | https://daisyui.com/docs/themes/ | `data-theme="dim"` or `data-theme="nord"` on your `<html>` tag. Instant themed components. Zero config beyond the import. 35k+ GitHub stars. |
| Radix Colors CSS imports | https://www.radix-ui.com/colors/docs/overview/usage | `@import "@radix-ui/colors/slate-dark"` → 12 steps of blue-tinted dark gray as CSS vars. No build step. Tailwind integration via https://github.com/brattonross/windy-radix-palette |
| Dracula Tailwind | https://github.com/dracula/tailwind | Classic purple-dark theme. Tailwind plugin. Higher contrast than Catppuccin. Docs: https://draculatheme.com/tailwind |
| Tokyo Night (palette source) | https://github.com/tokyo-night/tokyo-night-vscode-theme | Blue-tinted dark with vibrant accents. Hex values in repo JSON — extract into CSS variables. **Storm** variant is the lighter-dark option. |

## Recommendations for AWL Dashboard

- **Catppuccin Macchiato** — most popular "lighter dark" theme, already close to what the current concept gravitates toward. Tailwind plugin ready to go.
- **Radix Colors Slate dark** — best for granular control over each shade level. 12-step scale designed specifically for UI.
- **Open Props dim theme** — single CSS import, lighter-dark aesthetic, minimal setup.
- **Realtime Colors** — best for quick prototyping before committing to code.