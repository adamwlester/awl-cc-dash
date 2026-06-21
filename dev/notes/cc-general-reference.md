# Claude Code Settings Reference

> Complete reference for all Claude Code configuration surfaces.
> Source: [code.claude.com/docs/en/settings](https://code.claude.com/docs/en/settings) (March 2026)

---

## VS Code Extension Settings

These live in VS Code's own `settings.json` (`Ctrl+,` → top-right icon for JSON), **not** in `.claude/settings.json`. They control the extension UI wrapper around Claude Code.

> **Overlap with core settings:** `claudeCode.initialPermissionMode` mirrors `permissions.defaultMode`. `claudeCode.respectGitIgnore` mirrors `respectGitignore`. The VS Code setting applies to the extension UI; the core setting applies to CLI sessions. Set both if you use both.

---

### `claudeCode.initialPermissionMode`

Permission mode when a new conversation starts. This is the mode selector shown in the extension UI (Shift+Tab to cycle).

```json
"claudeCode.initialPermissionMode": "acceptEdits"
```

| Value | Behavior |
|-------|----------|
| `"default"` | Prompts on first use of each tool |
| `"plan"` | Read-only — Claude explores and presents a plan before editing |
| `"acceptEdits"` | Auto-approves file edits for the session |
| `"auto"` | AI classifier decides safety (requires Team/Enterprise/API plan + Sonnet 4.6 or Opus 4.6) |
| `"bypassPermissions"` | Skips all prompts — **sandboxed environments only!** |

**Type:** string (default: `"default"`)

> `"auto"` and `"bypassPermissions"` only appear in the selector when `claudeCode.allowDangerouslySkipPermissions` is `true`.

---

### `claudeCode.selectedModel`

Model used for new conversations. `"default"` defers to Anthropic's current default. Change per-session with `/model`.

```json
"claudeCode.selectedModel": "opus"
```

| Value | Description |
|-------|-------------|
| `"default"` | Use Anthropic's current default model |
| `"opus"` | Claude Opus 4.6 |
| `"sonnet"` | Claude Sonnet 4.6 |
| `"haiku"` | Claude Haiku 4.5 |
| Full model ID (e.g. `"claude-opus-4-6"`) | Specific model version |

**Type:** string (default: `"default"`)

> Available models may be further restricted by `availableModels` in `.claude/settings.json`. This setting mirrors the core `model` key — the VS Code setting applies to the extension UI; the core setting applies to CLI sessions.

---

### `claudeCode.useTerminal`

Launch Claude in terminal mode (raw TUI) instead of the graphical webview panel.

```json
"claudeCode.useTerminal": false
```

**Type:** boolean (default: `false`)

---

### `claudeCode.preferredLocation`

Where the Claude Code panel opens in VS Code.

```json
"claudeCode.preferredLocation": "panel"
```

| Value | Behavior |
|-------|----------|
| `"panel"` | Opens as a bottom tab (default) |
| `"sidebar"` | Opens in the right sidebar |

**Type:** string (default: `"panel"`)

---

### `claudeCode.autosave`

Auto-save open files before Claude reads or writes them. Prevents stale buffer conflicts.

```json
"claudeCode.autosave": true
```

**Type:** boolean (default: `true`)

---

### `claudeCode.useCtrlEnterToSend`

Use `Ctrl+Enter` (or `Cmd+Enter`) instead of `Enter` to send prompts. Frees `Enter` for newlines.

```json
"claudeCode.useCtrlEnterToSend": false
```

**Type:** boolean (default: `false`)

---

### `claudeCode.enableNewConversationShortcut`

Enable `Cmd+N` / `Ctrl+N` to start a new conversation from the extension.

```json
"claudeCode.enableNewConversationShortcut": true
```

**Type:** boolean (default: `true`)

---

### `claudeCode.hideOnboarding`

Hide the onboarding checklist (graduation cap icon) in the extension UI.

```json
"claudeCode.hideOnboarding": false
```

**Type:** boolean (default: `false`)

---

### `claudeCode.respectGitIgnore`

Exclude `.gitignore` patterns from file searches and the `@` file picker in the extension.

```json
"claudeCode.respectGitIgnore": true
```

**Type:** boolean (default: `true`)

---

### `claudeCode.environmentVariables`

Environment variables injected into the Claude process launched by the extension. For shared config, prefer `env` in `.claude/settings.json` instead.

```json
"claudeCode.environmentVariables": [
  { "name": "MY_VAR", "value": "my_value" }
]
```

**Type:** array of `{ name: string, value: string }` (default: `[]`)

---

### `claudeCode.disableLoginPrompt`

Skip authentication prompts at startup. Useful for third-party API provider setups where Claude Code's built-in auth is not used.

```json
"claudeCode.disableLoginPrompt": false
```

**Type:** boolean (default: `false`)

---

### `claudeCode.allowDangerouslySkipPermissions`

Unlocks `auto` and `bypassPermissions` in the mode selector (Shift+Tab). `auto` additionally requires a Team, Enterprise, or API plan and Sonnet 4.6 or Opus 4.6 — the option may remain unavailable even with this toggle on.

```json
"claudeCode.allowDangerouslySkipPermissions": false
```

**Type:** boolean (default: `false`)

---

### `claudeCode.claudeProcessWrapper`

Executable path used to launch the Claude process. Allows wrapping with custom tooling (e.g. profilers, credential helpers).

```json
"claudeCode.claudeProcessWrapper": "/path/to/wrapper"
```

**Type:** string (default: none)

---

## Claude Code Core Settings (`.claude/settings.json`)

These live in `.claude/settings.json`, `.claude/settings.local.json`, or `~/.claude/settings.json`. They are shared between the VS Code extension and the CLI.

### Settings File Locations

| Scope | File | Shared? |
|-------|------|---------|
| User (global) | `~/.claude/settings.json` | No |
| Project (team) | `.claude/settings.json` | Yes (committed) |
| Local (personal) | `.claude/settings.local.json` | No (gitignored) |
| Managed (IT/admin) | System-level `managed-settings.json` | Yes (deployed) |

**Precedence:** Managed > CLI args > Local > Project > User

Enable VS Code autocomplete by adding this to any settings file:

```json
{ "$schema": "https://json.schemastore.org/claude-code-settings.json" }
```

---

### Permissions

#### `permissions.allow`

Tools Claude can use **without prompting**. Array of permission rule strings.

```json
"permissions": {
  "allow": [
    "Bash(npm run *)",
    "Bash(git *)",
    "Read(~/.zshrc)",
    "mcp__puppeteer__*",
    "WebFetch(domain:github.com)",
    "Agent(Explore)"
  ]
}
```

**Rule syntax:**

| Pattern | Matches |
|---------|---------|
| `Bash` or `Bash(*)` | All Bash commands |
| `Bash(npm run *)` | Commands starting with `npm run ` |
| `Bash(* --version)` | Commands ending with ` --version` |
| `Bash(git * main)` | Commands like `git checkout main` |
| `Read(./.env)` | Specific file relative to cwd |
| `Read(/src/**)` | Recursive from project root |
| `Read(~/.zshrc)` | Home-relative path |
| `Read(//c/Users/alice/**)` | Absolute path (Windows: `C:\` = `//c/`) |
| `Edit(/docs/**)` | Edit files in project's docs/ |
| `WebFetch(domain:example.com)` | Fetch from specific domain |
| `mcp__servername` | All tools from an MCP server |
| `mcp__server__toolname` | Specific MCP tool |
| `Agent(Explore)` | Specific subagent |

> **Wildcards:** `*` = single dir level, `**` = recursive. For Bash, `Bash(ls *)` enforces a word boundary (won't match `lsof`), while `Bash(ls*)` matches both.

---

#### `permissions.ask`

Tools that **always prompt for confirmation**. Same syntax as `allow`.

```json
"permissions": {
  "ask": ["Bash(git push *)"]
}
```

---

#### `permissions.deny`

Tools Claude **cannot use at all**. Evaluated first — always wins over allow/ask.

```json
"permissions": {
  "deny": [
    "Bash(curl *)",
    "Read(./.env)",
    "Read(./secrets/**)",
    "Agent(Explore)"
  ]
}
```

> **Limitation:** Deny rules block Claude's built-in tools, not Bash subprocesses. `Read(./.env)` blocks the Read tool but not `cat .env` in Bash. Use the sandbox for OS-level enforcement.

**Evaluation order:** deny > ask > allow (first match wins)

---

#### `permissions.additionalDirectories`

Extra directories Claude can access, same rules as the launch directory. Also settable via `--add-dir` or `/add-dir`.

```json
"permissions": {
  "additionalDirectories": ["../docs/", "/absolute/path/to/project"]
}
```

---

#### `permissions.defaultMode`

Permission mode on startup.

```json
"permissions": {
  "defaultMode": "default"
}
```

| Value | Behavior |
|-------|----------|
| `"default"` | Prompts on first use of each tool |
| `"acceptEdits"` | Auto-approves file edits for the session |
| `"plan"` | Read-only — no modifications or commands |
| `"auto"` | AI classifier decides safety (research preview) |
| `"dontAsk"` | Auto-denies unless pre-approved via allow rules |
| `"bypassPermissions"` | Skips all prompts — **containers/VMs only!** |

---

#### `permissions.disableBypassPermissionsMode`

Prevent `bypassPermissions` mode from being activated. Disables `--dangerously-skip-permissions`.

```json
"permissions": {
  "disableBypassPermissionsMode": "disable"
}
```

**Type:** `"disable"` or omit

---

### Model & API

#### `model`

Override the default model.

```json
"model": "claude-sonnet-4-6"
```

**Type:** string (model ID)

---

#### `availableModels`

Restrict which models users can select via `/model`, `--model`, or Config tool.

```json
"availableModels": ["sonnet", "haiku", "opus"]
```

**Type:** string[]

---

#### `modelOverrides`

Map Anthropic model IDs to provider-specific IDs (e.g. Bedrock inference profile ARNs).

```json
"modelOverrides": {
  "claude-opus-4-6": "arn:aws:bedrock:us-east-1:123456:inference-profile/abc"
}
```

**Type:** object — `{ [anthropicModelId]: providerModelId }`

---

#### `effortLevel`

Persist effort level across sessions. Written automatically by `/effort`.

```json
"effortLevel": "medium"
```

**Values:** `"low"` | `"medium"` | `"high"` | `"max"` — Supported on Opus 4.6 and Sonnet 4.6

---

#### `apiKeyHelper`

Custom script (runs in `/bin/sh`) to generate an auth value. Sent as `X-Api-Key` and `Authorization: Bearer` headers.

```json
"apiKeyHelper": "/path/to/generate_api_key.sh"
```

**Type:** string (shell command)

---

#### `forceLoginMethod`

Restrict login to a specific account type.

```json
"forceLoginMethod": "claudeai"
```

**Values:** `"claudeai"` (Claude.ai accounts) | `"console"` (API billing accounts)

---

#### `forceLoginOrgUUID`

Auto-select an organization during login. Requires `forceLoginMethod` to be set.

```json
"forceLoginOrgUUID": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

**Type:** string (UUID)

---

### Environment Variables

#### `env`

Key-value pairs applied to every session.

```json
"env": {
  "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
  "OTEL_METRICS_EXPORTER": "otlp",
  "MY_CUSTOM_VAR": "value"
}
```

**Type:** object — `{ [name]: value }`

---

### Hooks

Hooks run custom commands at lifecycle events. Each event key holds an array of rule objects with an optional `matcher` and a `hooks` array.

**Hook handler types:**

| Type | Key fields | Default timeout |
|------|-----------|----------------|
| `"command"` | `command`, `shell` | 600s |
| `"http"` | `url`, `headers`, `allowedEnvVars` | 30s |
| `"prompt"` | `prompt`, `model` | 30s |
| `"agent"` | `prompt`, `model` | 60s |

**Common fields on all handlers:** `type` (required), `timeout`, `statusMessage`, `once` (bool, run once per session), `async` (bool)

**Available env vars in hooks:** `$CLAUDE_PROJECT_DIR`, `$CLAUDE_ENV_FILE`, `$CLAUDE_CODE_REMOTE`, `$CLAUDE_PLUGIN_ROOT`, `$CLAUDE_PLUGIN_DATA`

---

#### `hooks.SessionStart`

Fires when a session starts.

**Matcher values:** `"startup"` | `"resume"` | `"clear"` | `"compact"`

```json
"hooks": {
  "SessionStart": [{
    "matcher": "startup",
    "hooks": [{
      "type": "command",
      "command": "./scripts/setup.sh",
      "timeout": 600,
      "statusMessage": "Setting up..."
    }]
  }]
}
```

---

#### `hooks.UserPromptSubmit`

Fires when the user submits a prompt. **No matcher support.**

```json
"hooks": {
  "UserPromptSubmit": [{
    "hooks": [{ "type": "command", "command": "./scripts/validate-prompt.sh" }]
  }]
}
```

---

#### `hooks.PreToolUse`

Fires before a tool runs. Can block, allow, or modify the call.

**Matcher:** tool name — `"Bash"`, `"Edit|Write"`, `"mcp__.*"`, etc.

```json
"hooks": {
  "PreToolUse": [{
    "matcher": "Bash",
    "hooks": [{ "type": "command", "command": "./scripts/block-dangerous.sh", "timeout": 10 }]
  }]
}
```

---

#### `hooks.PermissionRequest`

Fires when permission is requested. **Matcher:** tool name.

---

#### `hooks.PostToolUse`

Fires after a tool completes successfully. **Matcher:** tool name.

```json
"hooks": {
  "PostToolUse": [{
    "matcher": "Write|Edit",
    "hooks": [{ "type": "command", "command": "./scripts/lint.sh" }]
  }]
}
```

---

#### `hooks.PostToolUseFailure`

Fires after a tool fails. **Matcher:** tool name.

---

#### `hooks.Notification`

Fires on notifications.

**Matcher values:** `"permission_prompt"` | `"idle_prompt"` | `"auth_success"` | `"elicitation_dialog"`

---

#### `hooks.SubagentStart` / `hooks.SubagentStop`

Fires when a subagent starts or stops. **Matcher:** agent type or custom name — `"Bash"`, `"Explore"`, `"Plan"`, etc.

---

#### `hooks.TaskCreated` / `hooks.TaskCompleted`

Fires when tasks are created or completed. **No matcher support.**

---

#### `hooks.Stop`

Fires when Claude stops responding. **No matcher support.**

---

#### `hooks.StopFailure`

Fires when Claude stops due to an error.

**Matcher values:** `"rate_limit"` | `"authentication_failed"` | `"billing_error"` | `"invalid_request"` | `"server_error"` | `"max_output_tokens"` | `"unknown"`

---

#### `hooks.TeammateIdle`

Fires when a teammate agent is idle. **No matcher support.**

---

#### `hooks.InstructionsLoaded`

Fires when CLAUDE.md instructions are loaded.

**Matcher values:** `"session_start"` | `"nested_traversal"` | `"path_glob_match"` | `"include"` | `"compact"`

---

#### `hooks.ConfigChange`

Fires when settings change.

**Matcher values:** `"user_settings"` | `"project_settings"` | `"local_settings"` | `"policy_settings"` | `"skills"`

---

#### `hooks.CwdChanged`

Fires when the working directory changes. **No matcher support.**

---

#### `hooks.FileChanged`

Fires when a watched file changes. **Matcher:** filename pattern.

```json
"hooks": {
  "FileChanged": [{
    "matcher": ".envrc|.env",
    "hooks": [{ "type": "command", "command": "direnv export json >> $CLAUDE_ENV_FILE" }]
  }]
}
```

---

#### `hooks.PreCompact` / `hooks.PostCompact`

Fires before/after context compaction. **Matcher values:** `"manual"` | `"auto"`

---

#### `hooks.Elicitation` / `hooks.ElicitationResult`

MCP server elicitation events. **Matcher:** MCP server name.

---

#### `hooks.WorktreeCreate` / `hooks.WorktreeRemove`

Worktree lifecycle events. **No matcher support.**

---

#### `disableAllHooks`

Kill switch — disables all hooks and custom status lines.

```json
"disableAllHooks": true
```

**Type:** boolean (default: `false`)

---

#### `allowManagedHooksOnly`

*Managed settings only.* Block user/project/plugin hooks. Only managed + SDK hooks run.

```json
"allowManagedHooksOnly": true
```

**Type:** boolean

---

#### `allowedHttpHookUrls`

Allowlist of URL patterns for HTTP hooks. Supports `*` wildcard. Undefined = no restriction, empty array = block all.

```json
"allowedHttpHookUrls": ["https://hooks.example.com/*"]
```

**Type:** string[]

---

#### `httpHookAllowedEnvVars`

Allowlist of env var names HTTP hooks can interpolate into headers. Each hook's effective vars = intersection with this list.

```json
"httpHookAllowedEnvVars": ["MY_TOKEN", "HOOK_SECRET"]
```

**Type:** string[]

---

### Sandbox

OS-level isolation for Bash commands. Available on macOS, Linux, and WSL2.

#### `sandbox.enabled`

Enable Bash sandboxing.

```json
"sandbox": { "enabled": true }
```

**Type:** boolean (default: `false`)

---

#### `sandbox.failIfUnavailable`

Exit with error at startup if sandbox can't start. For strict managed deployments.

```json
"sandbox": { "failIfUnavailable": true }
```

**Type:** boolean (default: `false`)

---

#### `sandbox.autoAllowBashIfSandboxed`

Auto-approve all Bash commands when sandboxed.

```json
"sandbox": { "autoAllowBashIfSandboxed": true }
```

**Type:** boolean (default: `true`)

---

#### `sandbox.excludedCommands`

Commands that bypass the sandbox entirely.

```json
"sandbox": { "excludedCommands": ["git", "docker"] }
```

**Type:** string[]

---

#### `sandbox.allowUnsandboxedCommands`

Allow the `dangerouslyDisableSandbox` escape hatch. Set `false` to force all commands through sandbox.

```json
"sandbox": { "allowUnsandboxedCommands": false }
```

**Type:** boolean (default: `true`)

---

#### `sandbox.enableWeakerNestedSandbox`

Enable weaker sandbox for unprivileged Docker environments. Linux/WSL2 only. **Reduces security.**

```json
"sandbox": { "enableWeakerNestedSandbox": true }
```

**Type:** boolean (default: `false`)

---

#### `sandbox.enableWeakerNetworkIsolation`

macOS only. Allow TLS trust service in sandbox. Required for `gh`, `gcloud`, `terraform` with MITM proxy. **Reduces security.**

```json
"sandbox": { "enableWeakerNetworkIsolation": true }
```

**Type:** boolean (default: `false`)

---

#### `sandbox.filesystem.allowWrite`

Extra writable paths. Merged across all scopes and with `Edit(...)` allow rules.

```json
"sandbox": { "filesystem": { "allowWrite": ["/tmp/build", "~/.kube"] } }
```

**Path prefixes:** `/` = absolute, `~/` = home, `./` = project root

**Type:** string[]

---

#### `sandbox.filesystem.denyWrite`

Block writes to these paths. Merged across scopes and with `Edit(...)` deny rules.

```json
"sandbox": { "filesystem": { "denyWrite": ["/etc", "/usr/local/bin"] } }
```

**Type:** string[]

---

#### `sandbox.filesystem.denyRead`

Block reads from these paths. Merged with `Read(...)` deny rules.

```json
"sandbox": { "filesystem": { "denyRead": ["~/.aws/credentials"] } }
```

**Type:** string[]

---

#### `sandbox.filesystem.allowRead`

Re-allow reads within `denyRead` regions. Takes precedence over `denyRead`.

```json
"sandbox": { "filesystem": { "allowRead": ["."] } }
```

**Type:** string[]

---

#### `sandbox.filesystem.allowManagedReadPathsOnly`

*Managed settings only.* Ignore `allowRead` from non-managed settings.

**Type:** boolean (default: `false`)

---

#### `sandbox.network.allowedDomains`

Domains allowed for outbound traffic. Supports wildcards.

```json
"sandbox": { "network": { "allowedDomains": ["github.com", "*.npmjs.org"] } }
```

**Type:** string[]

---

#### `sandbox.network.allowManagedDomainsOnly`

*Managed settings only.* Ignore `allowedDomains` from non-managed settings.

**Type:** boolean (default: `false`)

---

#### `sandbox.network.allowUnixSockets`

Unix socket paths accessible in the sandbox.

```json
"sandbox": { "network": { "allowUnixSockets": ["/var/run/docker.sock"] } }
```

**Type:** string[]

---

#### `sandbox.network.allowAllUnixSockets`

Allow all Unix socket connections in sandbox.

**Type:** boolean (default: `false`)

---

#### `sandbox.network.allowLocalBinding`

Allow binding to localhost ports. macOS only.

**Type:** boolean (default: `false`)

---

#### `sandbox.network.httpProxyPort` / `sandbox.network.socksProxyPort`

Bring-your-own proxy ports. Omit to let Claude run its own.

```json
"sandbox": { "network": { "httpProxyPort": 8080, "socksProxyPort": 8081 } }
```

**Type:** number

---

### Auto Mode

Customize the auto-mode AI classifier. **Not read from shared project settings** (`.claude/settings.json`). Only from user, local, or managed.

#### `autoMode.environment`

Describe your trusted infrastructure in plain English. Tells the classifier what "external" means.

```json
"autoMode": {
  "environment": [
    "Source control: github.example.com/acme-corp",
    "Trusted cloud buckets: s3://acme-builds",
    "Trusted internal domains: *.internal.example.com",
    "Key services: Jenkins at ci.example.com"
  ]
}
```

**Type:** string[] (prose descriptions)

---

#### `autoMode.allow`

Exceptions to block rules. **Replaces the entire default allow list** — copy defaults first with `claude auto-mode defaults`.

```json
"autoMode": {
  "allow": ["Deploying to staging is allowed: isolated and resets nightly"]
}
```

**Type:** string[] (prose descriptions)

---

#### `autoMode.soft_deny`

Block rules. **Replaces the entire default block list** — copy defaults first with `claude auto-mode defaults`.

```json
"autoMode": {
  "soft_deny": ["Never run database migrations outside the migrations CLI"]
}
```

**Type:** string[] (prose descriptions)

> **CLI helpers:** `claude auto-mode defaults` (view built-in rules), `claude auto-mode config` (view effective config), `claude auto-mode critique` (AI review of custom rules)

---

#### `disableAutoMode`

Prevent auto mode from being activated. Removes `auto` from Shift+Tab cycle.

```json
"disableAutoMode": "disable"
```

**Type:** `"disable"` or omit

---

#### `useAutoModeDuringPlan`

Use auto mode semantics during plan mode. Not read from shared project settings.

```json
"useAutoModeDuringPlan": false
```

**Type:** boolean (default: `true`)

---

### MCP Servers

MCP servers are configured in `~/.claude.json` (user/local scope) or `.mcp.json` (project scope). These settings keys control approval and restrictions.

#### `enableAllProjectMcpServers`

Auto-approve all MCP servers defined in project `.mcp.json` files.

```json
"enableAllProjectMcpServers": true
```

**Type:** boolean

---

#### `enabledMcpjsonServers`

Approve specific MCP servers from `.mcp.json`.

```json
"enabledMcpjsonServers": ["memory", "github"]
```

**Type:** string[]

---

#### `disabledMcpjsonServers`

Reject specific MCP servers from `.mcp.json`.

```json
"disabledMcpjsonServers": ["filesystem"]
```

**Type:** string[]

---

#### `allowedMcpServers`

*Managed settings only.* Allowlist of permitted MCP servers. Undefined = no restrictions, empty array = block all.

```json
"allowedMcpServers": [{ "serverName": "github" }]
```

**Type:** `{ serverName: string }[]`

---

#### `deniedMcpServers`

*Managed settings only.* Blocklist of MCP servers. Takes precedence over allowlist.

```json
"deniedMcpServers": [{ "serverName": "filesystem" }]
```

**Type:** `{ serverName: string }[]`

---

#### `allowManagedMcpServersOnly`

*Managed settings only.* Only managed `allowedMcpServers` applies.

**Type:** boolean (default: `false`)

---

### Worktree

#### `worktree.symlinkDirectories`

Directories to symlink from main repo into worktrees. Saves disk in monorepos.

```json
"worktree": { "symlinkDirectories": ["node_modules", ".cache"] }
```

**Type:** string[]

---

#### `worktree.sparsePaths`

Sparse checkout paths — only these are written to disk in worktrees.

```json
"worktree": { "sparsePaths": ["packages/my-app", "shared/utils"] }
```

**Type:** string[]

---

### Git & Attribution

#### `attribution`

Customize or disable attribution on git commits and PR descriptions. Empty string = hidden.

```json
"attribution": {
  "commit": "Generated with Claude Code\n\nCo-Authored-By: Claude <noreply@anthropic.com>",
  "pr": "Generated with [Claude Code](https://claude.com/claude-code)"
}
```

| Key | Controls | Default |
|-----|----------|---------|
| `commit` | Git commit trailers/message | Co-Authored-By trailer |
| `pr` | PR description footer | Claude Code link |

---

#### `includeCoAuthoredBy`

**Deprecated** — use `attribution.commit` instead. Whether to include co-authored-by in commits.

**Type:** boolean (default: `true`)

---

#### `includeGitInstructions`

Include built-in git/PR workflow instructions in system prompt. Set `false` if using custom git skills. Env var `CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS` takes precedence.

```json
"includeGitInstructions": false
```

**Type:** boolean (default: `true`)

---

### UI & Behavior

#### `language`

Preferred response language. Also sets voice dictation language.

```json
"language": "japanese"
```

**Type:** string (e.g. `"japanese"`, `"spanish"`, `"french"`)

---

#### `outputStyle`

Output style preset — adjusts the system prompt.

```json
"outputStyle": "Explanatory"
```

**Type:** string

---

#### `defaultShell`

Default shell for `!` commands. Requires `CLAUDE_CODE_USE_POWERSHELL_TOOL=1` for PowerShell.

```json
"defaultShell": "powershell"
```

**Values:** `"bash"` (default) | `"powershell"`

---

#### `voiceEnabled`

Enable push-to-talk voice dictation. Requires Claude.ai account. Written by `/voice`.

```json
"voiceEnabled": true
```

**Type:** boolean

---

#### `alwaysThinkingEnabled`

Enable extended thinking by default. Usually set via `/config`.

```json
"alwaysThinkingEnabled": true
```

**Type:** boolean

---

#### `statusLine`

Custom status line displayed as context.

```json
"statusLine": { "type": "command", "command": "~/.claude/statusline.sh" }
```

**Type:** object — `{ type: "command", command: string }`

---

#### `fileSuggestion`

Custom script for `@` file autocomplete.

```json
"fileSuggestion": { "type": "command", "command": "~/.claude/file-suggestion.sh" }
```

**Type:** object — `{ type: "command", command: string }`

---

#### `respectGitignore`

Whether the `@` file picker respects `.gitignore` patterns.

```json
"respectGitignore": false
```

**Type:** boolean (default: `true`)

---

#### `spinnerVerbs`

Customize action verbs shown in the spinner.

```json
"spinnerVerbs": { "mode": "append", "verbs": ["Pondering", "Crafting"] }
```

| Key | Type | Description |
|-----|------|-------------|
| `mode` | `"replace"` \| `"append"` | Replace defaults or add to them |
| `verbs` | string[] | Custom verb strings |

---

#### `spinnerTipsEnabled`

Show tips in the spinner while Claude is working.

```json
"spinnerTipsEnabled": false
```

**Type:** boolean (default: `true`)

---

#### `spinnerTipsOverride`

Override spinner tips with custom strings.

```json
"spinnerTipsOverride": {
  "excludeDefault": true,
  "tips": ["Use /help for commands", "Check wiki.example.com"]
}
```

| Key | Type | Description |
|-----|------|-------------|
| `excludeDefault` | boolean | `true` = only custom tips; `false` = merge with defaults |
| `tips` | string[] | Custom tip strings |

---

#### `prefersReducedMotion`

Reduce or disable UI animations (spinners, shimmer, flash) for accessibility.

```json
"prefersReducedMotion": true
```

**Type:** boolean (default: `false`)

---

#### `showClearContextOnPlanAccept`

Show "clear context" option on the plan accept screen.

```json
"showClearContextOnPlanAccept": true
```

**Type:** boolean (default: `false`)

---

#### `fastModePerSessionOptIn`

Fast mode doesn't persist across sessions. Users must `/fast` each time.

```json
"fastModePerSessionOptIn": true
```

**Type:** boolean (default: `false`)

---

#### `teammateMode`

How agent team teammates display.

```json
"teammateMode": "tmux"
```

**Values:** `"auto"` (picks split panes in tmux/iTerm2, in-process otherwise) | `"in-process"` | `"tmux"`

---

#### `agent`

Run the main thread as a named subagent. Uses that subagent's system prompt, tool restrictions, and model.

```json
"agent": "code-reviewer"
```

**Type:** string (subagent name)

---

#### `plansDirectory`

Where plan files are stored. Path relative to project root.

```json
"plansDirectory": "./plans"
```

**Type:** string (default: `~/.claude/plans`)

---

#### `autoUpdatesChannel`

Release channel to follow for updates.

```json
"autoUpdatesChannel": "stable"
```

**Values:** `"latest"` (default, most recent) | `"stable"` (~1 week old, skips regressions)

---

#### `cleanupPeriodDays`

Delete sessions inactive longer than N days at startup. `0` = disable persistence entirely.

```json
"cleanupPeriodDays": 20
```

**Type:** number (default: `30`)

---

#### `autoMemoryDirectory`

Custom directory for auto memory storage. Accepts `~/` paths. **Not allowed in shared project settings** to prevent redirecting memory writes.

```json
"autoMemoryDirectory": "~/my-memory-dir"
```

**Type:** string

---

#### `feedbackSurveyRate`

Probability (0-1) that the session quality survey appears. `0` = suppress entirely.

```json
"feedbackSurveyRate": 0.05
```

**Type:** number (default varies by plan)

---

#### `otelHeadersHelper`

Script to generate dynamic OpenTelemetry headers. Runs at startup and periodically.

```json
"otelHeadersHelper": "/path/to/generate_otel_headers.sh"
```

**Type:** string (shell command)

---

### AWS (Bedrock)

#### `awsAuthRefresh`

Script that refreshes AWS credentials by modifying the `.aws` directory.

```json
"awsAuthRefresh": "aws sso login --profile myprofile"
```

**Type:** string (shell command)

---

#### `awsCredentialExport`

Script that outputs JSON with AWS credentials.

```json
"awsCredentialExport": "/path/to/generate_aws_grant.sh"
```

**Type:** string (shell command)

---

### Announcements

#### `companyAnnouncements`

Messages shown to users at startup. Multiple entries rotate randomly.

```json
"companyAnnouncements": [
  "Welcome! Review code guidelines at docs.example.com",
  "Reminder: code reviews required for all PRs"
]
```

**Type:** string[]

---

### Managed-Only Keys

These only take effect in managed settings (IT/admin deployed). Cannot be overridden.

#### `allowManagedPermissionRulesOnly`

Prevent user and project settings from defining permission rules. Only managed rules apply.

**Type:** boolean

---

#### `channelsEnabled`

Allow channels for Team and Enterprise users.

**Type:** boolean

---

#### `allowedChannelPlugins`

Allowlist of channel plugins. Replaces the default Anthropic allowlist when set. Requires `channelsEnabled: true`.

```json
"allowedChannelPlugins": [
  { "marketplace": "claude-plugins-official", "plugin": "telegram" }
]
```

**Type:** `{ marketplace: string, plugin: string }[]`

---

#### `strictKnownMarketplaces`

Allowlist of plugin marketplaces users can add. Undefined = no restrictions, empty = block all.

```json
"strictKnownMarketplaces": [{ "source": "github", "repo": "acme-corp/plugins" }]
```

**Type:** `{ source: string, repo: string }[]`

---

#### `blockedMarketplaces`

Blocklist of marketplace sources. Checked before download — blocked sources never touch the filesystem.

```json
"blockedMarketplaces": [{ "source": "github", "repo": "untrusted/plugins" }]
```

**Type:** `{ source: string, repo: string }[]`

---

#### `pluginTrustMessage`

Custom message appended to the plugin trust warning before installation.

```json
"pluginTrustMessage": "All plugins from our marketplace are approved by IT"
```

**Type:** string

---

### Global Config (`~/.claude.json`)

These live in `~/.claude.json`, **not** `settings.json`. Adding them to settings.json triggers a schema error.

| Key | Values | Default | Description |
|-----|--------|---------|-------------|
| `autoConnectIde` | boolean | `false` | Auto-connect to running IDE from external terminal |
| `autoInstallIdeExtension` | boolean | `true` | Auto-install Claude Code IDE extension in VS Code |
| `editorMode` | `"normal"` \| `"vim"` | `"normal"` | Key binding mode for input prompt |
| `showTurnDuration` | boolean | `true` | Show "Cooked for 1m 6s" after responses |
| `terminalProgressBarEnabled` | boolean | `true` | Terminal progress bar (ConEmu, Ghostty, iTerm2) |

---

## Quick Reference

- **Two config systems:** VS Code `settings.json` (`claudeCode.*`) controls the extension UI; `.claude/settings.json` controls Claude Code core behavior
- **Permission eval order:** deny > ask > allow (first match wins)
- **Bash wildcards:** `Bash(ls *)` requires space (won't match `lsof`); `Bash(ls*)` matches both
- **Read/Edit paths:** `*` = one dir, `**` = recursive. `//` = absolute, `~/` = home, `/` = project root
- **Windows paths:** normalized to POSIX — `C:\Users\alice` becomes `//c/Users/alice`
- **Hook env vars:** `$CLAUDE_PROJECT_DIR`, `$CLAUDE_ENV_FILE`, `$CLAUDE_CODE_REMOTE`
- **Auto mode:** run `claude auto-mode defaults` before customizing allow/soft_deny
- **Schema autocomplete:** add `"$schema": "https://json.schemastore.org/claude-code-settings.json"`
