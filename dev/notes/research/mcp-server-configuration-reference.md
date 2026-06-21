---
source: claude
created: 2026-04-01
tags: [claude-code, mcp, configuration, reference]
---

# Claude Code MCP Server Configuration -- Complete Reference

**Research date:** 2026-04-01
**Sources:** Official docs at code.claude.com/docs/en/mcp and code.claude.com/docs/en/settings, GitHub issues (anthropics/claude-code), builder.io blog, claudelog.com, live config inspection of this machine.
**Confidence:** High -- primary source is official Anthropic documentation, cross-referenced with real config files and GitHub issue discussions.

---

## 1. All File Locations Where MCP Servers Can Be Defined

There are **six** distinct places MCP server definitions can live. Three are the standard scopes, plus managed config, plugins, and Claude.ai connectors.

### 1a. `~/.claude.json` -- User-Scope and Local-Scope MCP Servers

**Path:** `~/.claude.json` (Windows: `C:\Users\<username>\.claude.json`)

This single file holds **both** user-scope and local-scope MCP servers in different sections:

```jsonc
{
  // USER-SCOPE servers -- available across ALL projects
  "mcpServers": {
    "github": {
      "command": "cmd",
      "args": ["/c", "npx", "-y", "@modelcontextprotocol/server-github"],
      "env": { "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_..." }
    },
    "notion": {
      "type": "http",
      "url": "https://mcp.notion.com/mcp"
    }
  },

  // LOCAL-SCOPE servers -- per-project, private to you
  "projects": {
    "C:/Users/lester/my-project": {
      "mcpServers": {
        "project-specific-db": {
          "command": "npx",
          "args": ["-y", "@modelcontextprotocol/server-postgres", "postgresql://..."]
        }
      },
      "enabledMcpjsonServers": [],   // which .mcp.json servers are approved
      "disabledMcpjsonServers": [],  // which .mcp.json servers are rejected
      "hasTrustDialogAccepted": true
    }
  }
}
```

**Key points:**
- User-scope = top-level `mcpServers` key
- Local-scope = `projects.<project-path>.mcpServers`
- The `enabledMcpjsonServers` and `disabledMcpjsonServers` arrays here track your approval choices for project-scope (.mcp.json) servers
- This file also stores OAuth tokens, UI preferences, and other runtime state

**CLI commands that write here:**
```bash
# User-scope (available everywhere)
claude mcp add --scope user --transport http notion https://mcp.notion.com/mcp

# Local-scope (default -- current project only, private to you)
claude mcp add --transport http stripe https://mcp.stripe.com
claude mcp add --scope local --transport http stripe https://mcp.stripe.com  # explicit
```

### 1b. `.mcp.json` -- Project-Scope MCP Servers (shared via VCS)

**Path:** `<project-root>/.mcp.json`

This file is intended to be committed to version control so all team members share the same MCP tools.

```jsonc
{
  "mcpServers": {
    "shared-server": {
      "command": "/path/to/server",
      "args": [],
      "env": {}
    },
    "api-server": {
      "type": "http",
      "url": "${API_BASE_URL:-https://api.example.com}/mcp",
      "headers": {
        "Authorization": "Bearer ${API_KEY}"
      }
    }
  }
}
```

**Key points:**
- Supports environment variable expansion: `${VAR}` and `${VAR:-default}`
- Variable expansion works in: `command`, `args`, `env`, `url`, `headers`
- **Security gate:** Claude Code prompts for approval before using these servers. Each user must individually approve (or the project settings must auto-approve -- see section 3).
- Reset approval choices: `claude mcp reset-project-choices`

**CLI command that writes here:**
```bash
claude mcp add --scope project --transport http paypal https://mcp.paypal.com/mcp
```

### 1c. `~/.claude/settings.json` -- User Settings (Controls MCP Approval, NOT Definitions)

**Path:** `~/.claude/settings.json`

This file does NOT define MCP servers directly. It controls **which project-scope servers are approved** and sets MCP-related policies.

```jsonc
{
  "enableAllProjectMcpServers": true,       // auto-approve ALL .mcp.json servers
  "enabledMcpjsonServers": ["memory", "github"],  // whitelist specific servers
  "disabledMcpjsonServers": ["filesystem"]  // blacklist specific servers
}
```

### 1d. `.claude/settings.json` -- Project Settings (Shared)

**Path:** `<project-root>/.claude/settings.json`

Same keys as user settings but scoped to the project. Committed to VCS.

```jsonc
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",
  "enableAllProjectMcpServers": true,
  "enabledMcpjsonServers": ["context7", "playwright"],
  "disabledMcpjsonServers": ["filesystem"]
}
```

### 1e. `.claude/settings.local.json` -- Local Settings (Personal, Gitignored)

**Path:** `<project-root>/.claude/settings.local.json`

Same format as project settings.json but NOT committed to version control. Claude Code auto-configures git to ignore this file.

**CAVEAT:** As of early 2026, there have been multiple bug reports (GitHub issues #24657, #16402, #24477) that `enabledMcpjsonServers` set in `settings.local.json` is **silently ignored** in some versions. The workaround is to set it in `.claude/settings.json` or use `enableAllProjectMcpServers: true`. Check your Claude Code version -- this may be fixed in later releases.

### 1f. Managed MCP Config -- Enterprise/IT-Deployed

**Path (system-wide, requires admin privileges):**
- macOS: `/Library/Application Support/ClaudeCode/managed-mcp.json`
- Linux/WSL: `/etc/claude-code/managed-mcp.json`
- Windows: `C:\Program Files\ClaudeCode\managed-mcp.json`

```jsonc
{
  "mcpServers": {
    "company-internal": {
      "type": "stdio",
      "command": "/usr/local/bin/company-mcp-server",
      "args": ["--config", "/etc/company/mcp-config.json"],
      "env": {
        "COMPANY_API_URL": "https://internal.company.com"
      }
    }
  }
}
```

**Key points:**
- When this file exists, it takes **exclusive control** -- users cannot add/modify MCP servers
- Same JSON format as `.mcp.json`
- Can be combined with allowlists/denylists in `managed-settings.json`
- Legacy Windows path `C:\ProgramData\ClaudeCode\managed-settings.json` is no longer supported as of v2.1.75

**Managed settings (separate file, same directories):**
- `managed-settings.json` -- contains `allowedMcpServers`, `deniedMcpServers`, `allowManagedMcpServersOnly`
- `managed-settings.d/*.json` -- drop-in directory for separate policy fragments (merged alphabetically)

### 1g. Plugin-Provided MCP Servers

Plugins can bundle MCP servers in two ways:

1. `.mcp.json` at the plugin root directory
2. Inline in `plugin.json` under `mcpServers`

```jsonc
// plugin.json
{
  "name": "my-plugin",
  "mcpServers": {
    "plugin-api": {
      "command": "${CLAUDE_PLUGIN_ROOT}/servers/api-server",
      "args": ["--port", "8080"]
    }
  }
}
```

Plugin MCP servers start automatically when the plugin is enabled. Manage via `/reload-plugins`.

### 1h. Claude.ai Connectors

MCP servers configured in your Claude.ai account (at claude.ai/settings/connectors) are automatically available in Claude Code when logged in with a Claude.ai account. They appear in `/mcp` with indicators showing their source.

---

## 2. Disabling Individual Servers Without Removing Them

There is **no** `enabled: false` flag on individual server definitions. Instead, there are several mechanisms:

### 2a. `disabledMcpjsonServers` (for project-scope .mcp.json servers)

Set in any settings.json file:

```jsonc
// In ~/.claude/settings.json, .claude/settings.json, or .claude/settings.local.json
{
  "disabledMcpjsonServers": ["filesystem", "postgres"]
}
```

This rejects specific servers from `.mcp.json` files. The server definition stays in `.mcp.json` but Claude Code won't load it.

### 2b. `deniedMcpServers` (managed/enterprise -- blocks any server)

Set in managed-settings.json (admin-only):

```jsonc
{
  "deniedMcpServers": [
    { "serverName": "dangerous-server" },
    { "serverCommand": ["npx", "-y", "unapproved-package"] },
    { "serverUrl": "https://*.untrusted.com/*" }
  ]
}
```

Denylist takes **absolute precedence** over everything, including allowlists.

### 2c. Permission deny rules (blocks MCP tools, not the server itself)

```jsonc
{
  "permissions": {
    "deny": ["mcp__servername__*"]
  }
}
```

This keeps the server connected but prevents Claude from using any of its tools. Useful for temporarily silencing a server.

### 2d. `ENABLE_CLAUDEAI_MCP_SERVERS=false`

Disables all Claude.ai connector MCP servers for a session:
```bash
ENABLE_CLAUDEAI_MCP_SERVERS=false claude
```

### 2e. Declining approval at the prompt

When Claude Code encounters a project-scope (.mcp.json) server, it prompts for approval. Declining stores a rejection in `~/.claude.json` under the project's `disabledMcpjsonServers`. Reset with: `claude mcp reset-project-choices`.

---

## 3. `enableAllProjectMcpServers` -- What It Does

```jsonc
{
  "enableAllProjectMcpServers": true
}
```

**Effect:** Automatically approves ALL MCP servers defined in any project `.mcp.json` file, without prompting.

**Where it can be set:**
- `~/.claude/settings.json` (user scope -- applies to all projects)
- `.claude/settings.json` (project scope -- applies to this project, shared with team)
- `.claude/settings.local.json` (local scope -- applies to this project, private)
- `managed-settings.json` (managed scope -- cannot be overridden)

**When to use:** When you trust all `.mcp.json` definitions in repos you work with and don't want to approve each one individually.

**Relationship to the other keys:**
- `enableAllProjectMcpServers: true` -- blanket approve all
- `enabledMcpjsonServers: ["name1", "name2"]` -- whitelist specific servers
- `disabledMcpjsonServers: ["name3"]` -- blacklist specific servers (takes precedence over the above)

---

## 4. Can Project Settings Override/Block User-Level Servers?

### Scope precedence (general settings):

1. **Managed** (highest) -- cannot be overridden
2. **Command line arguments**
3. **Local** (`.claude/settings.local.json`) -- overrides project and user
4. **Project** (`.claude/settings.json`) -- overrides user
5. **User** (`~/.claude/settings.json`) -- lowest

### MCP server precedence specifically:

When servers with the **same name** exist at multiple scopes:
1. **Local-scope** (in `~/.claude.json` per-project) -- wins
2. **Project-scope** (`.mcp.json`) -- second
3. **User-scope** (in `~/.claude.json` top-level) -- last

If a server is configured both locally and through a Claude.ai connector, the local config wins and the connector entry is skipped.

### Can project settings block user-level servers?

**No, project settings cannot directly remove or block a user-scope MCP server.** Project `settings.json` controls approval of `.mcp.json` servers, not user-scope servers in `~/.claude.json`. Only managed settings can restrict which servers load via `allowedMcpServers` / `deniedMcpServers`.

However, a project-scope server with the **same name** as a user-scope server will be overridden by local scope (local > project > user).

---

## 5. JSON Schema / Structure for Each Config File

### `~/.claude.json` (runtime state + server definitions)

```jsonc
{
  // User-scope MCP servers
  "mcpServers": {
    "<server-name>": {
      // For stdio servers:
      "command": "string",         // executable
      "args": ["string"],          // arguments
      "env": { "KEY": "value" },   // environment variables

      // For HTTP servers:
      "type": "http",
      "url": "https://...",
      "headers": { "Authorization": "Bearer ..." },
      "headersHelper": "command-string",  // dynamic headers script
      "oauth": {
        "clientId": "string",
        "callbackPort": 8080,
        "authServerMetadataUrl": "https://..."  // optional override
      }
    }
  },

  // Per-project state
  "projects": {
    "<absolute-project-path>": {
      "mcpServers": { /* same schema as above -- LOCAL-scope servers */ },
      "enabledMcpjsonServers": ["server1"],
      "disabledMcpjsonServers": ["server2"],
      "hasTrustDialogAccepted": true,
      "allowedTools": ["mcp__servername__toolname"]
    }
  },

  // Claude.ai connector tracking
  "claudeAiMcpEverConnected": ["claude.ai Gmail"],

  // Other runtime fields (theme, tips, etc.)
  "numStartups": 59,
  "theme": "light-ansi"
}
```

### `.mcp.json` (project-scope, committed to VCS)

```jsonc
{
  "mcpServers": {
    "<server-name>": {
      // stdio
      "command": "string",
      "args": ["${ENV_VAR:-default}"],
      "env": { "KEY": "${SECRET_KEY}" },

      // OR http
      "type": "http",
      "url": "${API_BASE_URL}/mcp",
      "headers": { "Authorization": "Bearer ${TOKEN}" },
      "headersHelper": "script-command",
      "oauth": { ... }
    }
  }
}
```

### `settings.json` / `settings.local.json` (MCP-related keys only)

```jsonc
{
  "$schema": "https://json.schemastore.org/claude-code-settings.json",

  // MCP approval controls
  "enableAllProjectMcpServers": true,
  "enabledMcpjsonServers": ["server1", "server2"],
  "disabledMcpjsonServers": ["server3"],

  // MCP permission rules
  "permissions": {
    "allow": ["mcp__servername__*"],
    "deny": ["mcp__dangerousserver__*"]
  }
}
```

### `managed-settings.json` (enterprise policy)

```jsonc
{
  "allowedMcpServers": [
    { "serverName": "github" },
    { "serverCommand": ["npx", "-y", "@modelcontextprotocol/server-filesystem"] },
    { "serverUrl": "https://mcp.company.com/*" }
  ],
  "deniedMcpServers": [
    { "serverName": "dangerous-server" },
    { "serverUrl": "https://*.untrusted.com/*" }
  ],
  "allowManagedMcpServersOnly": true  // only admin allowlist applies
}
```

### `managed-mcp.json` (enterprise-deployed servers)

```jsonc
{
  "mcpServers": {
    "<server-name>": {
      // Same schema as .mcp.json servers
    }
  }
}
```

---

## 6. Environment Variables and CLI Flags That Control MCP Loading

### Environment Variables

| Variable | Effect | Default |
|----------|--------|---------|
| `MCP_TIMEOUT` | MCP server startup timeout in ms | (platform default) |
| `MCP_TOOL_TIMEOUT` | Individual MCP tool execution timeout in ms | 30000 |
| `MAX_MCP_OUTPUT_TOKENS` | Max tokens for MCP tool output before warning | 25000 |
| `ENABLE_CLAUDEAI_MCP_SERVERS` | Set to `false` to disable Claude.ai connector servers | `true` |
| `ENABLE_TOOL_SEARCH` | Controls tool search/deferral behavior (`true`, `false`, `auto`, `auto:N`) | unset (all deferred) |
| `MCP_CLIENT_SECRET` | Pass OAuth client secret non-interactively | (none) |

**Usage:**
```bash
MCP_TIMEOUT=10000 MAX_MCP_OUTPUT_TOKENS=50000 ENABLE_CLAUDEAI_MCP_SERVERS=false claude
```

You can also set these persistently via the `env` key in any `settings.json`:
```jsonc
{
  "env": {
    "MCP_TIMEOUT": "10000",
    "MAX_MCP_OUTPUT_TOKENS": "50000"
  }
}
```

### CLI Commands

| Command | Effect |
|---------|--------|
| `claude mcp add [options] <name> ...` | Add a server (options: `--scope`, `--transport`, `--env`, `--header`) |
| `claude mcp add-json <name> '<json>'` | Add server from raw JSON config |
| `claude mcp add-from-claude-desktop` | Import servers from Claude Desktop config |
| `claude mcp list` | List all configured servers |
| `claude mcp get <name>` | Get details for a specific server |
| `claude mcp remove <name>` | Remove a server |
| `claude mcp reset-project-choices` | Reset approval/denial choices for .mcp.json servers |
| `claude mcp serve` | Run Claude Code itself as an MCP server |
| `/mcp` (inside session) | View/manage/authenticate MCP servers interactively |

### CLI Flags on `claude mcp add`

| Flag | Effect |
|------|--------|
| `--scope local` | Store in ~/.claude.json per-project (default) |
| `--scope project` | Store in .mcp.json |
| `--scope user` | Store in ~/.claude.json top-level |
| `--transport stdio\|http\|sse` | Transport type |
| `--env KEY=value` | Set environment variable for the server |
| `--header "Name: value"` | Set HTTP header |
| `--client-id <id>` | OAuth client ID |
| `--client-secret` | Prompt for OAuth client secret |
| `--callback-port <port>` | Fixed OAuth callback port |
| `--channels` | Enable channel (push message) capability |

---

## 7. VS Code Extension MCP Configuration

The Claude Code VS Code extension does **NOT** have its own separate MCP config layer. It reads the exact same configuration files as the CLI:

- `~/.claude.json` (user + local scope servers)
- `.mcp.json` (project scope servers)
- `~/.claude/settings.json` and `.claude/settings.json` (approval settings)

**How to add MCP servers when using the VS Code extension:**
- Run `claude mcp add` in your terminal (works whether inside or outside VS Code)
- Or directly edit the JSON files listed above
- The VS Code extension's `/mcp` command in the chat panel shows the same servers as the CLI

The extension provides a "Customize" section in its command menu that gives access to MCP servers, hooks, memory, permissions, and plugins -- but these all read/write the same underlying files.

**Note:** The separate `awl-claude-http-bridge` VS Code extension in this workspace is a custom tool (not Anthropic's), and its configuration is completely independent of Claude Code's MCP system.

---

## Summary: Decision Tree

```
Where should I define my MCP server?

Is it just for me, on one project?
  -> Default (local scope): `claude mcp add ...`
     Stored in: ~/.claude.json under projects.<path>.mcpServers

Is it just for me, across all projects?
  -> User scope: `claude mcp add --scope user ...`
     Stored in: ~/.claude.json top-level mcpServers

Should the whole team have it?
  -> Project scope: `claude mcp add --scope project ...`
     Stored in: .mcp.json (commit to VCS)
     Teammates must approve it (or set enableAllProjectMcpServers)

Is it an enterprise-mandated server?
  -> Managed: Deploy managed-mcp.json to system directory
     Users cannot modify or remove it

Do I want to disable a server without removing it?
  -> For .mcp.json servers: Add to disabledMcpjsonServers in settings.json
  -> For any server: Add permission deny rule: "mcp__name__*"
  -> For Claude.ai servers: ENABLE_CLAUDEAI_MCP_SERVERS=false
  -> Enterprise: Add to deniedMcpServers in managed-settings.json
```

---

## Known Issues / Gotchas

1. **`enabledMcpjsonServers` in `settings.local.json` may be silently ignored** (GitHub #24657, #16402). Claude Code reads this value from `~/.claude.json` per-project state, not from `settings.local.json`. The interactive approval prompt writes to `~/.claude.json`. Workaround: use `enableAllProjectMcpServers: true` in `.claude/settings.json`.

2. **"local scope" for MCP is different from "local settings."** MCP local-scope servers live in `~/.claude.json` (home directory). Local *settings* live in `.claude/settings.local.json` (project directory). This naming collision is a common source of confusion.

3. **Windows requires `cmd /c` wrapper** for stdio servers using npx: `claude mcp add --transport stdio my-server -- cmd /c npx -y @some/package`

4. **Per-project entries in `~/.claude.json` may not persist** between sessions for some fields (reported in #24657 as of Feb 2026). The `enabledMcpjsonServers` value can be cleared when sessions end.

5. **`mcpServers` cannot be defined in `settings.json`** -- only in `~/.claude.json` and `.mcp.json`. Adding `mcpServers` to `settings.json` or `settings.local.json` will trigger a schema validation error or be silently ignored.
