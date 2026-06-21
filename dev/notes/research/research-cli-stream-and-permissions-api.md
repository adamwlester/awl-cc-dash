# Claude Code CLI: Stream Interception & Permission API Deep Dive

> Research report from source code analysis of `cc-source/src/` (Claude Code v2.1.90)
> Date: 2026-04-02

---

## AREA 1: Stream Interception

### A. `--output-format stream-json` Mode

**How it works:** When you run `claude -p "query" --output-format stream-json --verbose`, the CLI enters non-interactive (print) mode and writes each `SDKMessage` as a newline-delimited JSON (NDJSON) line to stdout. Every message is serialized via `ndjsonSafeStringify()` and written with `structuredIO.write()`.

**Source:** `src/cli/print.ts` (lines 594, 628, 884, 928)

**Key requirement:** `--output-format stream-json` in print mode (`-p`) **requires** `--verbose`. Without `--verbose`, the CLI exits with an error (line 787-789). This is because non-verbose mode only emits the final `result` message.

**What events are emitted (the `SDKMessage` union):**

The full `SDKMessage` type is defined in `src/entrypoints/sdk/coreSchemas.ts` (line 1854). It is a union of these message types:

| Message Type | `type` field | Description |
|---|---|---|
| `SDKAssistantMessage` | `assistant` | Full assistant turn with content blocks (text, tool_use, thinking) |
| `SDKUserMessage` | `user` | User messages (emitted when `--replay-user-messages` is enabled) |
| `SDKUserMessageReplay` | `user` | Replayed user messages |
| `SDKResultSuccess` | `result` (subtype `success`) | Final result with cost, usage, duration, permission denials |
| `SDKResultError` | `result` (subtype `error_*`) | Error termination |
| `SDKSystemMessage` | `system` (subtype `init`) | Session initialization with tools, MCP servers, model, permission mode |
| `SDKPartialAssistantMessage` | `stream_event` | **Partial streaming events** (raw Anthropic API stream events). Only emitted when `--include-partial-messages` is set |
| `SDKCompactBoundaryMessage` | `system` (subtype `compact_boundary`) | Context compaction boundary markers |
| `SDKStatusMessage` | `system` (subtype `status`) | Status updates |
| `SDKAPIRetryMessage` | `system` (subtype `api_retry`) | API retry notifications with error info |
| `SDKLocalCommandOutput` | `system` (subtype `local_command_output`) | Slash command output |
| `SDKHookStartedMessage` | `system` (subtype `hook_started`) | Hook execution started (verbose only) |
| `SDKHookProgressMessage` | `system` (subtype `hook_progress`) | Hook execution progress with stdout/stderr |
| `SDKHookResponseMessage` | `system` (subtype `hook_response`) | Hook execution result with exit code and outcome |
| `SDKToolProgressMessage` | `tool_progress` | Long-running tool elapsed time updates |
| `SDKAuthStatusMessage` | `auth_status` | Authentication state changes |
| `SDKTaskNotificationMessage` | `system` (subtype `task_notification`) | Background task completion |
| `SDKTaskStartedMessage` | `system` (subtype `task_started`) | Background task started |
| `SDKTaskProgressMessage` | `system` (subtype `task_progress`) | Background task progress |
| `SDKSessionStateChangedMessage` | `system` (subtype `session_state_changed`) | State transitions: `idle`, `running`, `requires_action` |
| `SDKFilesPersistedEvent` | `system` (subtype `files_persisted`) | Files persisted to storage |
| `SDKToolUseSummaryMessage` | `tool_use_summary` | Tool use summaries |
| `SDKRateLimitEvent` | `rate_limit_event` | Rate limit information |
| `SDKElicitationCompleteMessage` | `system` (subtype `elicitation_complete`) | MCP elicitation completed |
| `SDKPromptSuggestionMessage` | `prompt_suggestion` | Predicted next user prompt |

**Additionally, the `StdoutMessage` union (what actually hits stdout) includes:**

| Message Type | `type` field | Description |
|---|---|---|
| `SDKControlRequest` | `control_request` | Permission requests sent to the SDK consumer |
| `SDKControlResponse` | `control_response` | Responses to control requests |
| `SDKControlCancelRequest` | `control_cancel_request` | Cancellation of pending control requests |
| `SDKKeepAliveMessage` | `keep_alive` | WebSocket keep-alive |
| `SDKStreamlinedText` | `streamlined_text` | (Internal) Streamlined text output |
| `SDKStreamlinedToolUseSummary` | `streamlined_tool_use_summary` | (Internal) Streamlined tool summaries |
| `SDKPostTurnSummary` | `system` (subtype `post_turn_summary`) | Post-turn summaries |

Source: `src/entrypoints/sdk/controlSchemas.ts` lines 642-653

**Key schemas for each message type:**

- `SDKAssistantMessage`: `{ type: "assistant", message: <Anthropic API message object>, parent_tool_use_id: string|null, uuid, session_id }`
- `SDKResultSuccess`: `{ type: "result", subtype: "success", duration_ms, duration_api_ms, is_error, num_turns, result: string, total_cost_usd, usage, modelUsage, permission_denials: [{tool_name, tool_use_id, tool_input}], session_id }`
- `stream_event`: `{ type: "stream_event", event: <raw Anthropic stream event>, parent_tool_use_id: string|null, uuid, session_id }`

**Does it include tool use?** Yes. Tool use blocks appear inside `SDKAssistantMessage.message.content` as `tool_use` content blocks, exactly as they come from the Anthropic API. Tool results appear in subsequent assistant messages.

**Does it include thinking?** Yes. Thinking blocks appear in `SDKAssistantMessage.message.content` as `thinking` content blocks.

**Does it include permission prompts?** Yes. Permission requests are emitted as `control_request` messages with `subtype: "can_use_tool"`. The `SDKSessionStateChangedMessage` with `state: "requires_action"` also fires.

**Can you get partial/streaming content?** Yes, with the `--include-partial-messages` flag. This emits `stream_event` messages containing raw Anthropic API stream events (content_block_start, content_block_delta, etc.). **Requires** `-p`, `--output-format stream-json`, and `--verbose`.

**Practical CLI command:**

```bash
# Full verbose stream with partial messages
claude -p "explain this code" \
  --output-format stream-json \
  --verbose \
  --include-partial-messages

# Basic verbose stream (complete messages only)
claude -p "fix the bug in main.ts" \
  --output-format stream-json \
  --verbose
```

**Stability:** Stable, public API. Used by the Agent SDK, VS Code extension, and claude.ai bridge.

---

### B. `--input-format stream-json` Mode

**How it works:** When `--input-format stream-json` is set, the CLI reads NDJSON from stdin instead of plain text. Each line must be a valid JSON object. The `StructuredIO` class (at `src/cli/structuredIO.ts`) parses these lines.

**Supported input message types (`StdinMessage` union):**

| Type | `type` field | Purpose |
|---|---|---|
| `SDKUserMessage` | `user` | Send a user message: `{ type: "user", session_id: "", message: { role: "user", content: "..." }, parent_tool_use_id: null }` |
| `SDKControlRequest` | `control_request` | Send control commands (initialize, set_model, interrupt, etc.) |
| `SDKControlResponse` | `control_response` | **Respond to permission requests** (`can_use_tool`) with allow/deny decisions |
| `SDKKeepAliveMessage` | `keep_alive` | Keep connection alive (silently ignored) |
| `SDKUpdateEnvironmentVariables` | `update_environment_variables` | Update process env vars at runtime |

Source: `src/entrypoints/sdk/controlSchemas.ts` lines 655-663

**Can you send structured input events?** Yes. You can send:
- User messages (multi-turn conversations)
- Permission decisions (allow/deny tool use)
- Control commands (interrupt, set model, set thinking tokens, etc.)

**Can you inject tool results?** Not directly. Tool results are managed internally by the REPL loop. However, you can provide tool input modifications via permission responses (`updatedInput` field).

**Can you inject file attachments?** The `SDKUserMessage` content field accepts the same content block array as the Anthropic API, so image and file content blocks can be embedded in user messages.

**Practical example (multi-turn with permission handling):**

```bash
# Start a stream-json session
claude -p --input-format stream-json --output-format stream-json --verbose

# Send on stdin:
{"type":"user","session_id":"","message":{"role":"user","content":"create a file called test.txt"},"parent_tool_use_id":null}

# When you see a control_request with subtype "can_use_tool", respond:
{"type":"control_response","response":{"subtype":"success","request_id":"<from the request>","response":{"behavior":"allow","updatedInput":{}}}}

# Or deny:
{"type":"control_response","response":{"subtype":"success","request_id":"<from the request>","response":{"behavior":"deny","message":"Not allowed"}}}
```

**Stability:** Stable. This is the primary SDK communication protocol.

---

### C. JSONL Transcript / Session Files

**Where are they stored?**

```
~/.claude/projects/<hashed-project-path>/<session-uuid>.jsonl
```

Source: `src/utils/sessionStorage.ts` line 198-204

The project directory path is hashed. Each session gets a UUID-named `.jsonl` file. Subagent transcripts go to:

```
~/.claude/projects/<hashed-path>/<session-uuid>/subagents/agent-<agent-uuid>.jsonl
```

**Format:** Each line is a JSON object (NDJSON). Entry types are defined in `src/types/logs.ts` as the `Entry` union and include:

- `TranscriptMessage` (serialized conversation messages -- user, assistant, system)
- `FileHistorySnapshotMessage` (file state snapshots for undo)
- `ContextCollapseSnapshotEntry` / `ContextCollapseCommitEntry` (compaction metadata)
- `ContentReplacementEntry` (snipped content references)
- `AttributionSnapshotMessage` (git attribution data)
- `PersistedWorktreeSession` (worktree session metadata)
- Custom title entries, tags, etc.

**Can you tail/watch them in real-time?** Yes. The files are append-only during a session. You can `tail -f` the JSONL file to observe messages as they're written. The tmux bridge's `read_log()` method already does this.

**Gotchas:**
- Files can grow large (50MB+ cap for reads, multi-GB in practice)
- The `TranscriptMessage` entries contain the full Anthropic API message objects including tool use blocks and results
- Agent transcripts are in subdirectories under the session UUID

**Stability:** Stable storage format, but the exact entry schemas are internal and may change between versions.

---

### D. Remote Control / Bridge Mode

**How it works:** `claude remote-control` (or `claude --remote-control` / `--rc` for interactive sessions) starts a bridge that connects to claude.ai's backend via WebSocket. This allows controlling the CLI from the claude.ai web interface.

**Architecture:**

The bridge system lives in `src/bridge/`. Key files:

| File | Purpose |
|---|---|
| `bridgeMain.ts` | Main bridge loop -- polls for work, spawns sessions |
| `bridgeMessaging.ts` | WebSocket message routing, echo dedup, control request handling |
| `bridgePermissionCallbacks.ts` | Permission request/response types for bridge |
| `sessionRunner.ts` | Spawns child `claude` processes with `--sdk-url` |
| `replBridge.ts` / `replBridgeTransport.ts` | WebSocket transport layer |
| `types.ts` | Bridge configuration and session handle types |

**Protocol:** WebSocket (SSE fallback). The child CLI process runs with `--input-format stream-json --output-format stream-json` and communicates with the bridge parent via stdin/stdout pipes. The bridge parent relays messages over WebSocket to claude.ai.

**What flows over the bridge:**

1. **Outbound (CLI -> claude.ai):** All `SDKMessage` events (assistant messages, tool use, results, system events)
2. **Inbound (claude.ai -> CLI):** User messages, permission decisions, control requests (interrupt, set_model, set_permission_mode, set_max_thinking_tokens)
3. **Permission forwarding:** When the child CLI emits a `control_request` with `subtype: "can_use_tool"`, the bridge forwards it to claude.ai. When the user approves/denies on claude.ai, the response flows back as a `control_response`.

**Can external programs connect?** The bridge is designed for claude.ai integration, not general-purpose external connections. However, `--rc` (interactive remote control) creates a session on claude.ai that can be controlled from the web.

For programmatic external control, use the `--input-format stream-json --output-format stream-json` stdio protocol instead -- it provides the same capabilities without the WebSocket infrastructure.

**Permission handling over the bridge:**

```typescript
// From src/bridge/bridgePermissionCallbacks.ts
type BridgePermissionResponse = {
  behavior: 'allow' | 'deny'
  updatedInput?: Record<string, unknown>
  updatedPermissions?: PermissionUpdate[]
  message?: string
}
```

The bridge can:
- Forward permission requests to claude.ai (via `sendRequest`)
- Receive permission decisions from claude.ai (via `onResponse`)
- Cancel pending permission requests (via `cancelRequest`)

Source: `src/bridge/bridgePermissionCallbacks.ts`

**Stability:** Stable for claude.ai integration. The bridge is actively used in production.

---

### E. MCP-Based Observation

**Can an MCP server observe tool calls as they happen?** Not directly through standard MCP. MCP servers receive tool calls addressed to them, but they cannot observe tool calls to other tools (Bash, Read, Edit, etc.).

**However, there are two workarounds:**

1. **PostToolUse hooks:** Configure hooks for specific tools that call your MCP server or HTTP endpoint with the tool execution details.

2. **MCP Channels (research preview):** The `--channels` flag enables MCP notification channels. A channel-capable MCP server can receive notifications about events. This is gated behind `claude/channel` capability and an allowlist. Not generally available.

3. **Stream-json output parsing:** Run Claude Code with `--output-format stream-json --verbose` and parse the stdout stream externally. This gives you everything -- tool calls, results, thinking, permission events.

**Stability:** Channels are experimental/research preview. Hooks and stream-json are stable.

---

### F. Agent SDK Streaming

**How the SDK works for multi-turn agentic runs:**

The Agent SDK (`claude_agent_sdk` Python package) spawns a child `claude` process with:
```
claude -p --input-format stream-json --output-format stream-json --verbose --include-partial-messages
```

It communicates via the NDJSON stdio protocol. The SDK:

1. Sends an `initialize` control_request on startup
2. Receives the `system` (init) message with tools, model info, etc.
3. Sends user messages as `SDKUserMessage` NDJSON lines
4. Receives streaming events on stdout
5. Handles `control_request` with `subtype: "can_use_tool"` for permission decisions
6. Sends back `control_response` to approve/deny

The `--sdk-url` flag is for remote WebSocket connection (used by the bridge), not needed for local SDK use.

**The full stream for an agentic run looks like:**

```
-> {"type":"control_request","request_id":"...","request":{"subtype":"initialize",...}}
<- {"type":"control_response","response":{"subtype":"success","request_id":"...","response":{commands, models, ...}}}
<- {"type":"system","subtype":"init",...}
-> {"type":"user","session_id":"","message":{"role":"user","content":"fix the bug"},...}
<- {"type":"stream_event","event":{"type":"content_block_start",...},...}  (if --include-partial-messages)
<- {"type":"stream_event","event":{"type":"content_block_delta",...},...}
<- {"type":"assistant","message":{content: [{type:"text",...},{type:"tool_use",...}]},...}
<- {"type":"control_request","request_id":"abc","request":{"subtype":"can_use_tool","tool_name":"Bash","input":{...},...}}
-> {"type":"control_response","response":{"subtype":"success","request_id":"abc","response":{"behavior":"allow","updatedInput":{}}}}
<- {"type":"assistant","message":{...},...}  (tool result turn)
<- {"type":"result","subtype":"success","result":"...","total_cost_usd":0.05,...}
```

**Stability:** Stable. This is the primary SDK protocol.

---

## AREA 2: Permission Request Interception

### A. `--permission-prompt-tool` Flag

**How it works:** This flag specifies an MCP tool name that will handle all permission prompts instead of the default interactive TUI prompt. When a tool needs permission, Claude Code calls the specified MCP tool with the permission request details and uses its response to decide allow/deny.

**Source:** `src/utils/permissions/PermissionPromptToolResultSchema.ts`

**Input schema sent to the MCP tool:**

```typescript
{
  tool_name: string,    // Name of the tool requesting permission (e.g., "Bash", "Write")
  input: Record<string, unknown>,  // The tool's input parameters
  tool_use_id?: string  // Unique tool use request ID
}
```

**Expected response schema:**

```typescript
// Allow response
{
  behavior: "allow",
  updatedInput: Record<string, unknown>,  // Modified input (empty {} = use original)
  updatedPermissions?: PermissionUpdate[],  // Optional: persist permission rule changes
  toolUseID?: string,
  decisionClassification?: "user_temporary" | "user_permanent" | "user_reject"
}

// Deny response
{
  behavior: "deny",
  message: string,     // Explanation shown to Claude
  interrupt?: boolean, // If true, aborts the entire conversation turn
  toolUseID?: string,
  decisionClassification?: "user_temporary" | "user_permanent" | "user_reject"
}
```

Source: `src/utils/permissions/PermissionPromptToolResultSchema.ts` lines 44-77

**`updatedPermissions` can modify rules persistently:**

```typescript
type PermissionUpdate =
  | { type: "addRules", destination: "userSettings"|"projectSettings"|"localSettings"|"session"|"cliArg", rules: [{toolName, ruleContent?}], behavior: "allow"|"deny"|"ask" }
  | { type: "replaceRules", ... }
  | { type: "removeRules", ... }
  | { type: "setMode", destination, mode: "default"|"acceptEdits"|"plan"|"dontAsk"|"bypassPermissions" }
  | { type: "addDirectories", destination, directories: string[] }
  | { type: "removeDirectories", destination, directories: string[] }
```

Source: `src/entrypoints/sdk/coreSchemas.ts` lines 263-298

**Practical usage:**

```bash
# Use an MCP tool called "my-permission-handler" (must be configured as an MCP server)
claude -p "deploy the app" --permission-prompt-tool mcp__myserver__my-permission-handler
```

**Stability:** Stable. Used by the VS Code extension and other SDK consumers.

---

### B. `--permission-mode` Options

All modes defined in `src/types/permissions.ts`:

| Mode | Internal Name | What It Does | Source |
|---|---|---|---|
| **Default** | `default` | Read-only tools auto-approved. Bash, Write, Edit require approval | Standard |
| **Accept Edits** | `acceptEdits` | File edits (Edit, Write) in CWD auto-approved. Bash still requires approval | Standard |
| **Plan** | `plan` | Read-only only. No edits, no commands. Claude suggests but doesn't execute | Standard |
| **Auto** | `auto` | Background classifier (Sonnet 4.6) evaluates each action. Safe actions auto-approved, risky ones prompted. **Requires Team/Enterprise/API plan + Sonnet 4.6 or Opus 4.6** | Feature-gated (`TRANSCRIPT_CLASSIFIER`) |
| **Don't Ask** | `dontAsk` | Only pre-approved tools execute (via `allowedTools` rules). Everything else auto-denied with message | Standard |
| **Bypass Permissions** | `bypassPermissions` | Everything auto-approved. Still prompts for writes to `.git`, `.claude`, `.vscode`, `.idea` | Standard |
| **Bubble** | `bubble` | Internal only. Used by subagents to surface permission requests to parent | Internal |

Source: `src/types/permissions.ts` lines 16-38, `src/utils/permissions/PermissionMode.ts` lines 42-91

**`bypassPermissions` vs `dontAsk`:**
- `bypassPermissions`: auto-allows everything (with safety exceptions for sensitive dirs)
- `dontAsk`: auto-denies everything not explicitly pre-approved. Opposite approach -- designed for locked-down CI/CD environments

**Practical CLI:**

```bash
claude -p "task" --permission-mode acceptEdits
claude -p "task" --permission-mode bypassPermissions  # or --dangerously-skip-permissions
claude -p "task" --permission-mode dontAsk --allowedTools "Bash(npm test)" "Read"
```

---

### C. Auto Mode Classifier

**How it works:** When permission mode is `auto`, a background classifier model (Sonnet 4.6) evaluates each tool call. The classifier receives the recent conversation transcript and the proposed action, then decides whether it's safe to auto-approve.

**Source:** `src/utils/permissions/yoloClassifier.ts`, `src/utils/permissions/classifierDecision.ts`

**Architecture:**
1. Tool call arrives needing permission
2. `isAutoModeAllowlistedTool()` checks if it's in the safe allowlist (read-only tools, search tools, etc.) -- if yes, auto-approve without classifier
3. For `acceptEdits` fast path: file edits within CWD are auto-approved, outside CWD go to classifier
4. Otherwise, `classifyYoloAction()` calls the classifier API with the conversation context and proposed action
5. Classifier returns `{ shouldBlock: boolean, reason: string }`
6. If `shouldBlock`, the permission prompt is shown to the user
7. If not blocked, the action is auto-approved

**Safe-allowlisted tools (skip classifier entirely):**

Source: `src/utils/permissions/classifierDecision.ts` lines 56-94

- File reads, Grep, Glob, LSP, ToolSearch, ListMcpResources, ReadMcpResource
- Task management (TodoWrite, TaskCreate, TaskGet, etc.)
- Plan mode tools (AskUserQuestion, EnterPlanMode, ExitPlanMode)
- Agent coordination (TeamCreate, TeamDelete, SendMessage)
- Sleep

**Customizing auto mode rules:**

```bash
# View built-in rules
claude auto-mode defaults

# View effective config with settings applied
claude auto-mode config
```

Auto mode config is managed via GrowthBook feature flags (`tengu_auto_mode_config`). The system prompt for the classifier includes permission descriptions that define what's allowed/denied.

**Two-stage classifier:** The classifier uses a 2-stage approach:
1. Fast stage: Quick classification
2. Thinking stage: Extended thinking for uncertain cases

Both stages have separate token usage and timing tracked (for telemetry).

**Denial tracking:** The system tracks consecutive classifier denials. After hitting `DENIAL_LIMITS`, it falls back to regular prompting to prevent infinite denial loops.

Source: `src/utils/permissions/denialTracking.ts`

**Stability:** Feature-gated behind `TRANSCRIPT_CLASSIFIER`. Requires opt-in and specific plans. Considered production but evolving.

---

### D. Permission Hooks

**PreToolUse hooks CAN influence permission decisions:**

Source: `src/utils/hooks.ts` lines 3394-3436, `src/types/hooks.ts` lines 72-78

A `PreToolUse` hook can return JSON output with:

```json
{
  "decision": "approve",
  "reason": "This command is safe"
}
```

Or:
```json
{
  "decision": "block",
  "reason": "This is a dangerous command"
}
```

Valid `permissionDecision` values: `"allow"`, `"deny"`, `"ask"`, `"defer"`

Decision precedence when multiple hooks fire: **deny > defer > ask > allow**

The hook also receives `updatedInput` to modify tool parameters.

**PermissionRequest hooks CAN programmatically approve/deny:**

Source: `src/utils/hooks.ts` lines 4157-4192, `src/types/hooks.ts` lines 121-134

`PermissionRequest` hooks fire when the permission dialog is *about to be shown*. They race against the user prompt (in interactive mode) or the SDK permission handler (in SDK mode). **Whichever responds first wins.**

Response schema:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "allow",
      "updatedInput": {},
      "updatedPermissions": [
        { "type": "addRules", "rules": [{"toolName": "Bash", "ruleContent": "npm test"}], "behavior": "allow", "destination": "session" }
      ]
    }
  }
}
```

Or deny:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "deny",
      "message": "Not allowed by policy",
      "interrupt": true
    }
  }
}
```

Source: `src/types/hooks.ts` lines 121-134

**Key difference between PreToolUse and PermissionRequest:**
- `PreToolUse` fires BEFORE permission checking. It can preemptively approve/deny/defer.
- `PermissionRequest` fires WHEN the permission dialog would appear. It can answer the dialog programmatically.

**Practical hook configuration (settings.json):**

```json
{
  "hooks": {
    "PermissionRequest": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "node /path/to/my-permission-handler.js"
          }
        ]
      }
    ]
  }
}
```

The hook script receives JSON on stdin with `tool_name`, `tool_input`, and `permission_suggestions`, and outputs the decision JSON to stdout.

**Stability:** Stable. Hooks are a core public feature.

---

### E. `--allowedTools` and `--disallowedTools` Patterns

**Pattern syntax:** Uses the same permission rule syntax as `settings.json`:

| Pattern | Matches |
|---|---|
| `Bash` | All Bash commands |
| `Bash(npm test)` | Exact command |
| `Bash(npm *)` | Glob wildcard |
| `Read` | All file reads |
| `Read(.env)` | Specific file |
| `Edit(src/**)` | Gitignore-style patterns |
| `mcp__server__tool` | Specific MCP tool |
| `WebFetch(domain:example.com)` | Domain-scoped |

Source: `src/utils/permissions/shellRuleMatching.ts`, `src/utils/permissions/permissionRuleParser.ts`

**Important:** `--disallowedTools` completely removes tools from the model's context. The model won't even know the tool exists. This is different from deny rules which tell the model "you tried to use X but it was denied."

**Can you match on tool input content?** Yes. The specifier in parentheses matches against the tool's input:
- For Bash: matches against the `command` field
- For Read/Edit/Write: matches against the `file_path` field (gitignore patterns)
- For WebFetch: matches against the URL with `domain:` prefix support

**Glob patterns vs regex:** Permission rules use glob-style wildcards (`*` matches anything), NOT regex. Backslash-escaped `\*` is a literal asterisk.

**Practical usage:**

```bash
# Allow only specific bash commands
claude -p "run tests" --allowedTools "Bash(npm test)" "Bash(npm run lint)" "Read" "Grep"

# Deny dangerous tools
claude -p "refactor code" --disallowedTools "Bash" "WebFetch"
```

**Stability:** Stable, public API.

---

### F. Permission Bubbling for Subagents

**How `bubble` mode works:**

When a subagent runs with `permissionMode: 'bubble'`, permission requests are surfaced to the parent agent/process. The parent's permission handler (whether interactive prompt, SDK `can_use_tool`, or `--permission-prompt-tool`) receives the request.

Source: `src/types/permissions.ts` line 28 (`InternalPermissionMode = ... | 'bubble'`)

In the `StructuredIO` implementation (`src/cli/structuredIO.ts`), when a child process emits a `control_request` with `subtype: "can_use_tool"`, the parent process handles it through its own permission pipeline. The `agent_id` field in the permission request identifies which subagent made the request.

**Can parent agents programmatically handle child permission requests?** Yes. The SDK protocol handles this transparently -- the parent's `canUseTool` callback receives ALL permission requests including those from subagents. The `agent_id` field distinguishes them.

In practice:
1. Subagent tries to use a tool
2. Subagent's permission check results in `ask` (because of `bubble` mode)
3. Permission request is forwarded to parent via `control_request`
4. Parent's SDK host (VS Code, custom wrapper, etc.) shows the prompt or handles programmatically
5. Response flows back to the subagent

**Stability:** Internal. `bubble` is not exposed as a user-facing permission mode.

---

### G. Programmatic Permission via the Bridge

**Can Remote Control peers approve/deny permissions?** Yes. This is a core feature of the bridge.

Source: `src/bridge/bridgePermissionCallbacks.ts`, `src/bridge/bridgeMessaging.ts`

**How it works:**

1. Child CLI emits `control_request` with `subtype: "can_use_tool"` on stdout
2. Bridge's `sessionRunner.ts` detects this via `onPermissionRequest` callback (line 62-66)
3. Bridge forwards the request to claude.ai via the WebSocket
4. User approves/denies on claude.ai
5. Bridge sends `control_response` back to the child CLI's stdin
6. Child CLI resolves the pending promise in `StructuredIO`

**The bridge also supports server-initiated control requests:**

Source: `src/bridge/bridgeMessaging.ts` lines 243-391

The server (claude.ai) can send these control requests to the CLI:

| Subtype | Effect |
|---|---|
| `initialize` | Initialize session capabilities |
| `set_model` | Change model mid-session |
| `set_max_thinking_tokens` | Change thinking budget |
| `set_permission_mode` | Change permission mode remotely |
| `interrupt` | Abort current generation |

**Permission response protocol:**

```typescript
// From the bridge to the child CLI:
{
  type: "control_response",
  response: {
    subtype: "success",
    request_id: "<matching request_id>",
    response: {
      behavior: "allow" | "deny",
      updatedInput?: Record<string, unknown>,
      updatedPermissions?: PermissionUpdate[],
      message?: string  // only for deny
    }
  }
}
```

**The bridge also races permissions:** When `StructuredIO` is used with bridge support, the bridge's permission response races against the local SDK consumer's response. The `injectControlResponse()` method (line 283-309 of `structuredIO.ts`) handles bridge permission responses, cancelling the local prompt if the bridge responds first.

**Stability:** Stable. This is the production bridge used by claude.ai.

---

## Summary: Best Approaches for Building Middleware

### For stream interception:

**Recommended:** Use `claude -p --output-format stream-json --verbose --include-partial-messages` and parse stdout NDJSON. This gives you the complete event stream including:
- All assistant messages with tool use blocks
- All tool results
- Streaming partial content
- Permission requests (`control_request`)
- Session state changes
- Hook events
- Task progress
- Rate limit events
- Final result with cost/usage

### For permission control:

**Three tiers of control (from simplest to most powerful):**

1. **Static rules:** `--allowedTools` / `--disallowedTools` + `--permission-mode` -- simple, no code needed
2. **Hooks:** `PermissionRequest` hooks in `settings.json` -- runs your script, receives JSON, returns decisions. Works in both interactive and non-interactive mode.
3. **Full SDK protocol:** `--input-format stream-json --output-format stream-json` -- read `control_request` messages from stdout, write `control_response` messages to stdin. Maximum control, used by the Agent SDK and VS Code extension.

### For building a wrapper/middleware:

The ideal architecture is:

```
Your Middleware Process
    |
    +-- Spawns: claude -p --input-format stream-json --output-format stream-json --verbose --include-partial-messages
    |
    +-- Reads stdout: NDJSON stream of all events
    +-- Writes stdin: User messages + permission decisions
    +-- Handles: control_request (subtype: can_use_tool) -> control_response
```

This is exactly how the Python Agent SDK works. You have full programmatic control over:
- What prompts to send
- Which tools to approve/deny (with optional input modification)
- When to interrupt
- What model to use
- Permission mode changes

All without needing WebSocket, bridge infrastructure, or special privileges.
