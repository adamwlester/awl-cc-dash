---
source: claude
created: 2026-04-01
tags: [claude-code, plugins, research, tui-dashboard, ecosystem]
---

# Claude Code Plugin & Skills Ecosystem Research

Research date: 2026-04-01. Conducted for the Python/Textual TUI dashboard project that controls Claude Code sessions via tmux in WSL2.

## Ecosystem Overview

The Claude Code plugin ecosystem has grown rapidly since the plugin system launched in October 2025. As of April 2026 there are reportedly 9,000+ plugins available across multiple sources.

### Discovery Channels

| Source | URL | Notes |
|--------|-----|-------|
| Official Anthropic marketplace | `anthropics/claude-plugins-official` on GitHub | 32 curated plugins, 15.7k stars |
| Bundled plugins in claude-code repo | `anthropics/claude-code/plugins/` | 13 reference implementations |
| `/plugin marketplace add` command | Built into Claude Code CLI | Git-based marketplace protocol |
| claudecodemarketplace.com | https://claudecodemarketplace.com | Community directory |
| buildwithclaude.com | https://buildwithclaude.com | Plugin browsing site |
| claudepluginhub.com | https://www.claudepluginhub.com | Community hub |
| skillsmp.com | https://www.skillsmp.com | 733k+ skills across Claude/Codex/ChatGPT |
| npm registry | Standard npm packages | Plugins can be installed from npm |

### Plugin Installation Methods

1. **Marketplace protocol**: `/plugin marketplace add owner/repo` then `/plugin install plugin-name`
2. **Direct npm**: Plugins published to npm can be installed directly
3. **Local directory**: `claude --plugin-dir ./path`
4. **settings.json**: Configure in project `.claude/settings.json`

---

## Directly Relevant: TUI Session Management Projects

These are existing projects doing similar things to our planned dashboard.

### sooneocean/claude-session-manager (CSM) -- HIGHEST RELEVANCE

- **Tech**: Python + Textual framework (same stack we plan to use)
- **What it does**: Manages 10+ Claude Code sessions from a single TUI dashboard
- **Key design insight**: Does NOT use long-running subprocesses. Instead spawns short-lived `claude -p --output-format stream-json --verbose --include-partial-messages "prompt"` processes and uses `--resume SESSION_ID` for continuity
- **Features**: Real-time streaming, cost tracking, SOP stage detection, auto-compact at 50K tokens, session persistence to JSON, broadcast commands, session tagging/notes
- **150 tests**, Python 3.10+, MIT license
- **Important note**: The isatty() finding -- claude CLI suppresses output when not a TTY. CSM works around this with `-p` (print) mode + stream-json
- **Relevance**: This is essentially a prior-art version of our project. Study its architecture, especially `core/output_parser.py` and `core/session_manager.py`
- **GitHub**: https://github.com/sooneocean/claude-session-manager

### nyanko3141592/tmuxcc -- HIGH RELEVANCE

- **Tech**: Rust + Ratatui (TUI framework)
- **What it does**: TUI dashboard for managing AI coding agents in tmux panes
- **Supports**: Claude Code, OpenCode, Codex CLI, Gemini CLI
- **Key features**: Real-time status detection (Idle/Processing/Awaiting Approval/Error), approval management (approve/reject pending permission requests), batch operations, subagent tracking, pane preview
- **55 stars**, Rust, MIT license
- **How it works**: Scans all tmux sessions/windows/panes, detects agents by process name and pane content, parses agent-specific output for status, sends keystrokes for approvals
- **Relevance**: Very close to our tmux approach. Agent detection and approval management patterns are directly applicable
- **GitHub**: https://github.com/nyanko3141592/tmuxcc

### openwong2kim/wmux -- MODERATE RELEVANCE

- **Tech**: Electron + React + node-pty (ConPTY on Windows)
- **What it does**: Native Windows AI agent terminal (no WSL required)
- **Key features**: Split terminals, browser automation via CDP, MCP integration, session persistence, agent detection, notification system
- **Inspired by**: cmux (macOS tmux-based equivalent)
- **Relevance**: Different approach (Electron vs TUI) but the agent detection patterns, notification strategies, and MCP auto-registration are worth studying
- **GitHub**: https://github.com/openwong2kim/wmux

### Other TUI tools found

- **claude-code-terminal** (PyPI): Python TUI for managing Claude Code via tmux. Alpha.
- **cmux-ctl** (PyPI): TUI dashboard for cmux workspaces and Claude Code agents, built with Textual
- **claude-tmux** (crates.io): Rust TUI for Claude Code tmux sessions (674 downloads)
- **hagope/session-manager-tui** (GitHub Gist): Single-file session manager TUI, run with `uv run`
- **seunggabi/claude-dashboard**: Go + bubbletea, k9s-style TUI for Claude Code via tmux (24 stars)

---

## Official Plugins (anthropics/claude-plugins-official)

32 plugins in the official marketplace. Most relevant for our project:

### agent-sdk-dev -- INSTALL THIS

- Development kit for the Claude Agent SDK
- Command `/new-sdk-app` for interactive project setup
- Agents for validating SDK applications against best practices
- **Why useful**: If we use the Agent SDK to orchestrate sessions programmatically

### pyright-lsp -- INSTALL THIS

- Python LSP integration via Pyright
- Provides go-to-definition, hover, find-references, etc. within Claude Code
- **Why useful**: We are writing Python; LSP gives Claude Code deeper understanding of our codebase

### plugin-dev -- INSTALL THIS

- Comprehensive toolkit for developing Claude Code plugins
- 7 expert skills, AI-assisted creation, 8-phase guided workflow
- Agents: agent-creator, plugin-validator, skill-reviewer
- **Why useful**: If we want to package our TUI dashboard as a plugin itself

### hookify -- USEFUL

- Create custom hooks to prevent unwanted behaviors
- Analyzes conversation patterns, generates hook rules
- **Why useful**: Our dashboard could leverage hooks for event capture

### Other official plugins of note

- **pr-review-toolkit**: 6 specialized review agents (comments, tests, errors, types, code, simplify)
- **code-review**: 5 parallel Sonnet agents for automated PR review
- **security-guidance**: PreToolUse hook monitoring 9 security patterns
- **commit-commands**: Git workflow automation (/commit, /commit-push-pr)
- **feature-dev**: 7-phase structured development workflow
- **ralph-loop**: Self-referential AI loops for iterative development until completion
- **skill-creator**: Tool for creating new skills

### Full list of official plugins (32 total)

agent-sdk-dev, clangd-lsp, claude-code-setup, claude-md-management, claude-opus-4-5-migration, code-review, code-simplifier, commit-commands, csharp-lsp, example-plugin, explanatory-output-style, feature-dev, frontend-design, gopls-lsp, hookify, jdtls-lsp, kotlin-lsp, learning-output-style, lua-lsp, math-olympiad, mcp-server-dev, php-lsp, playground, plugin-dev, pr-review-toolkit, pyright-lsp, ralph-loop, ruby-lsp, rust-analyzer-lsp, security-guidance, skill-creator, swift-lsp, typescript-lsp

---

## Monitoring & Observability Plugins

### jarrodwatts/claude-hud -- INSTALL THIS

- Statusline plugin showing context usage, active tools, running agents, todo progress
- Uses Claude Code native statusline API (no tmux required)
- Parses JSONL transcript for tool/agent activity
- Configurable presets (Full/Essential/Minimal)
- Shows: model, git branch, context health bar, usage rate limits, tool activity, agent status, todo progress
- Updates every ~300ms, uses native token data from Claude Code (not estimated)
- **Why useful**: The statusline API and JSONL transcript parsing patterns are directly applicable to our dashboard
- Install: `/plugin marketplace add jarrodwatts/claude-hud` then `/plugin install claude-hud`
- **GitHub**: https://github.com/jarrodwatts/claude-hud

### victorfg21/claude-productivity -- STUDY THIS

- Real-time productivity dashboard using Textual (same framework as our project)
- 5 tabs: Dashboard, Insights, History, Projects, Sessions
- Tracks tool calls, edits, bash commands via hooks (PreToolUse/PostToolUse/Stop)
- Reads .jsonl files directly from ~/.claude/projects/
- SQLite for persistence, AI insights via `claude --print`
- Excel export, 5 themes
- **Why useful**: Same tech stack (Python + Textual + SQLite). Hook architecture and .jsonl reading code are directly reusable
- **GitHub**: https://github.com/victorfg21/claude-productivity

---

## Python Development Plugins

### Piebald-AI/claude-code-lsps -- INSTALL THIS

- LSP server marketplace with 23 languages including Python (pyright)
- Provides: go-to-definition, hover, find-references, document symbols, call hierarchy, workspace symbol search
- Requires Claude Code 2.1.50+ and `npx tweakcc --apply` for patching
- Also includes: TypeScript, Rust, Go, Java, C/C++, Ruby, and many more
- Install: `/plugin marketplace add Piebald-AI/claude-code-lsps`
- **GitHub**: https://github.com/Piebald-AI/claude-code-lsps

---

## Testing & Debugging Plugins

### From ComposioHQ/awesome-claude-plugins

- **debugger**: Advanced debugging assistant for complex bugs
- **bug-fix**: Analyzes stack traces and code to identify/fix bugs
- **test-writer-fixer**: Automatically write and fix unit tests (supports Pytest)

### From official marketplace

- **security-guidance**: PreToolUse hook monitoring dangerous patterns

### jasonjmcghee/claude-debugs-for-you

- MCP Server + VS Code extension enabling interactive debugging
- Claude can evaluate expressions, set breakpoints
- **GitHub**: https://github.com/jasonjmcghee/claude-debugs-for-you

### wshobson/unit-testing (from claudepluginhub.com)

- Unit testing plugin with debugging specialist

---

## Community Curated Lists (meta-resources)

| Repo | Description |
|------|-------------|
| hesreallyhim/awesome-claude-code | Skills, hooks, commands, orchestrators, plugins |
| ComposioHQ/awesome-claude-plugins | Production-ready plugins by category |
| rohitg00/awesome-claude-code-toolkit | 135 agents, 35 skills, 42 commands, 150+ plugins |
| jeremylongshore/claude-code-plugins-plus-skills | 340 plugins + 1367 agent skills with CCPI package manager |
| ccplugins/awesome-claude-code-plugins | Curated slash commands, subagents, MCP servers, hooks |
| alirezarezvani/claude-skills | 220+ skills across engineering, marketing, product |

---

## Marketplace / Registry Beyond npm

There is no single centralized marketplace. The ecosystem is distributed:

1. **Official marketplace**: `anthropics/claude-plugins-official` (GitHub repo, curated by Anthropic)
2. **Git-based marketplaces**: Any GitHub repo with `.claude-plugin/marketplace.json` can be a marketplace
3. **Community aggregator sites**: claudecodemarketplace.com, buildwithclaude.com, claudepluginhub.com, aitmpl.com/plugins
4. **npm**: Plugins can be published as npm packages
5. **skillsmp.com**: Cross-agent skill marketplace (Claude, Codex, ChatGPT)
6. **Individual GitHub repos**: Most plugins are just repos with the standard plugin structure

The `/plugin marketplace add owner/repo` command is the primary distribution mechanism. There is no npm-style central registry -- it is more like Homebrew taps.

---

## Recommended Installation Priority

### Tier 1: Install Now

1. **pyright-lsp** (official) -- Python intelligence for our codebase
2. **claude-hud** -- Context/usage monitoring during development
3. **agent-sdk-dev** (official) -- If using Agent SDK
4. **plugin-dev** (official) -- For packaging our work as a plugin

### Tier 2: Study Their Code

1. **sooneocean/claude-session-manager** -- Closest prior art (Python + Textual + session management)
2. **victorfg21/claude-productivity** -- Same stack, hook patterns, JSONL reading
3. **nyanko3141592/tmuxcc** -- tmux-based agent monitoring patterns

### Tier 3: Consider Later

1. **hookify** -- Custom hook creation
2. **feature-dev** -- Structured development workflow
3. **ralph-loop** -- Iterative development loops
4. **ComposioHQ plugins** -- debugger, test-writer-fixer

---

## Key Technical Insights for Our Project

1. **isatty() trap**: Claude CLI detects if stdout is a TTY. When piped, it suppresses output. CSM works around this with `-p` (print) mode. Our tmux approach avoids this since sessions ARE TTYs.

2. **JSONL transcripts**: Claude Code writes structured JSONL to `~/.claude/projects/`. Both claude-hud and claude-productivity parse these for real-time data. Our dashboard should do the same.

3. **Hooks system**: PreToolUse, PostToolUse, and Stop hooks can capture events. claude-productivity demonstrates this well with SQLite persistence.

4. **statusline API**: Claude Code has a native statusline that accepts JSON on stdin. claude-hud uses this for real-time display without needing a separate window.

5. **Plugin packaging**: Our dashboard could be distributed as a Claude Code plugin via the marketplace protocol (Git repo with `.claude-plugin/marketplace.json`).

6. **stream-json output**: `claude -p --output-format stream-json` gives structured JSON events. CSM demonstrates complete parsing of these events.

7. **Our tmux advantage**: Our awl_claude_tmux_bridge already solves the TTY problem by running Claude Code in actual tmux sessions. This means we get real interactive sessions (with permission prompts, compaction, etc.) rather than the limited `-p` print mode that CSM uses. This is a genuine differentiator.
