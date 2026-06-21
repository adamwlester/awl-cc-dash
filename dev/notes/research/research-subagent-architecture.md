# Claude Code Subagent Architecture — Deep Investigation

> Research report based on direct source code analysis of Claude Code v2.1.90+
> Source: `C:\Users\lester\MeDocuments\AppData\Anthropic\resources\cc-source\src\`
> Date: 2026-04-02

---

## 1. Architecture Overview

Claude Code uses a hierarchical agent architecture with three distinct layers:

```
Main Agent (REPL)
  |
  +-- Subagents (Agent tool)          ← own context window, report back
  |     |-- Built-in types (Explore, Plan, general-purpose, etc.)
  |     |-- Custom agents (.claude/agents/*.md, ~/.claude/agents/*.md)
  |     |-- Plugin agents (from installed plugins)
  |     +-- Fork agents (experimental, inherits parent context)
  |
  +-- Agent Teams (TeamCreate + Agent tool with name param)
        |-- Team Lead (the main agent, or a session-wide agent)
        |-- Teammates (tmux panes, iTerm2 panes, or in-process)
        +-- Shared task list + mailbox messaging
```

**Key relationships:**

- The **main agent** runs in the REPL loop and has access to the full system prompt, CLAUDE.md, tools, and MCP servers.
- **Subagents** are spawned via the `Agent` tool. Each runs in its own context window with a custom system prompt and a potentially restricted tool set. They return a text result to the parent.
- **Teammates** are independent Claude Code processes (or in-process contexts) that communicate via a mailbox system and shared task lists.
- Subagents **cannot spawn other subagents** (the Agent tool is in `ALL_AGENT_DISALLOWED_TOOLS` for external users). Fork agents technically keep the Agent tool in their pool for cache reasons but reject recursive fork attempts at call time.

---

## 2. Spawning Mechanics

### The Agent Tool

**File:** `src/tools/AgentTool/AgentTool.tsx`
**Tool name:** `Agent` (alias: `Task` for backward compatibility)
**Permission required:** No (always allowed)

### Input Schema

Defined in `AgentTool.tsx` lines 82-125:

```typescript
// Base schema
z.object({
  description: z.string(),     // 3-5 word summary
  prompt: z.string(),          // Full task instructions
  subagent_type: z.string().optional(),  // Which agent to use
  model: z.enum(['sonnet', 'opus', 'haiku']).optional(),
  run_in_background: z.boolean().optional(),
})

// Extended with multi-agent params (when agent teams enabled)
z.object({
  name: z.string().optional(),       // Makes agent addressable via SendMessage
  team_name: z.string().optional(),  // Team to spawn into
  mode: permissionModeSchema().optional(),  // e.g., 'plan'
  isolation: z.enum(['worktree']).optional(),  // or ['worktree', 'remote'] for ant
  cwd: z.string().optional(),        // Working directory override (KAIROS feature)
})
```

**Schema gating:** `run_in_background` is omitted from the schema when `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` or the fork experiment is active. `cwd` is only present when the KAIROS feature is enabled.

### Output Schema

Two discriminated variants:

```typescript
// Synchronous completion
{ status: 'completed', agentId, content, totalToolUseCount, totalDurationMs, totalTokens, usage, prompt }

// Asynchronous launch
{ status: 'async_launched', agentId, description, prompt, outputFile, canReadOutputFile? }
```

Internal-only variants (not exported):
- `{ status: 'teammate_spawned', ... }` — when spawning a teammate
- `{ status: 'remote_launched', ... }` — when using `isolation: 'remote'` (ant-only)

### Spawning Flow (call function)

1. **Team check:** If `team_name` and `name` are both provided, routes to `spawnTeammate()` instead of subagent creation.
2. **Agent resolution:** Looks up `subagent_type` in `agentDefinitions.activeAgents`. If not found, checks if it was denied by permission rules. Fork path: omitting `subagent_type` with the fork experiment active triggers an implicit fork.
3. **MCP requirement check:** If the agent has `requiredMcpServers`, waits up to 30s for pending servers to connect.
4. **Model resolution:** Calls `getAgentModel()` (see section 6).
5. **System prompt construction:**
   - Fork path: inherits parent's rendered system prompt byte-for-byte (for cache sharing).
   - Normal path: calls `agentDefinition.getSystemPrompt()`, then enhances with environment details.
6. **Worktree setup:** If `isolation: 'worktree'`, creates a temporary git worktree via `createAgentWorktree()`.
7. **Async vs sync decision:** Background if `run_in_background=true`, `selectedAgent.background=true`, coordinator mode, fork experiment, or KAIROS assistant mode.
8. **Tool pool assembly:** Builds an independent tool pool for the worker using `assembleToolPool()` with the worker's own permission mode (default: `acceptEdits`).
9. **Launch:** Calls `runAgent()` either directly (sync) or via `runAsyncAgentLifecycle()` (async).

---

## 3. Built-in Agent Types

All defined in `src/tools/AgentTool/built-in/`:

### Explore (`exploreAgent.ts`)

| Property | Value |
|----------|-------|
| **Type name** | `Explore` |
| **Model** | `haiku` (external), `inherit` (ant) |
| **Tools** | All tools EXCEPT: Agent, ExitPlanMode, Edit, Write, NotebookEdit |
| **System prompt** | Read-only file search specialist |
| **omitClaudeMd** | `true` — does not receive CLAUDE.md hierarchy |
| **Purpose** | Fast codebase exploration with thoroughness levels: quick, medium, very thorough |
| **One-shot** | Yes — listed in `ONE_SHOT_BUILTIN_AGENT_TYPES`, skips SendMessage/usage trailer |

### Plan (`planAgent.ts`)

| Property | Value |
|----------|-------|
| **Type name** | `Plan` |
| **Model** | `inherit` |
| **Tools** | Same as Explore (inherits `EXPLORE_AGENT.tools`) |
| **Disallowed tools** | Agent, ExitPlanMode, Edit, Write, NotebookEdit |
| **omitClaudeMd** | `true` |
| **Purpose** | Software architect for designing implementation plans |
| **One-shot** | Yes |
| **Gate** | Controlled by `tengu_amber_stoat` GrowthBook flag + `BUILTIN_EXPLORE_PLAN_AGENTS` build feature |

### general-purpose (`generalPurposeAgent.ts`)

| Property | Value |
|----------|-------|
| **Type name** | `general-purpose` |
| **Model** | Inherit (via `getDefaultSubagentModel()`) |
| **Tools** | `['*']` — all tools |
| **Purpose** | Complex research, multi-step tasks, code modifications |
| **Default agent** | Used when `subagent_type` is omitted and fork experiment is off |

### statusline-setup (`statuslineSetup.ts`)

| Property | Value |
|----------|-------|
| **Type name** | `statusline-setup` |
| **Model** | `sonnet` |
| **Tools** | `['Read', 'Edit']` |
| **Color** | `orange` |
| **Purpose** | Configure Claude Code status line from shell PS1 or user instructions |

### claude-code-guide (`claudeCodeGuideAgent.ts`)

| Property | Value |
|----------|-------|
| **Type name** | `claude-code-guide` |
| **Model** | `haiku` |
| **Permission mode** | `dontAsk` |
| **Tools** | Glob, Grep, Read, WebFetch, WebSearch (or Bash + Read + WebFetch + WebSearch for ant builds) |
| **Purpose** | Answers questions about Claude Code, Agent SDK, and Claude API by fetching official docs |
| **Context-aware** | Receives user's custom skills, agents, MCP servers, plugin commands, and settings in prompt |

### verification (`verificationAgent.ts`)

| Property | Value |
|----------|-------|
| **Type name** | `verification` |
| **Model** | `inherit` |
| **Color** | `red` |
| **Background** | `true` (always runs async) |
| **Disallowed tools** | Agent, ExitPlanMode, Edit, Write, NotebookEdit |
| **Gate** | `VERIFICATION_AGENT` build feature + `tengu_hive_evidence` GrowthBook flag |
| **Purpose** | Adversarial verification — tries to break implementations, produces PASS/FAIL/PARTIAL verdicts |
| **Critical reminder** | Has `criticalSystemReminder_EXPERIMENTAL` injected at every user turn |

### Fork Agent (implicit, `forkSubagent.ts`)

| Property | Value |
|----------|-------|
| **Type name** | `fork` |
| **Model** | `inherit` |
| **Tools** | `['*']` |
| **maxTurns** | 200 |
| **Permission mode** | `bubble` (surfaces prompts to parent terminal) |
| **Not registered** | Not in `getBuiltInAgents()` — only used when `subagent_type` is omitted with fork experiment active |
| **Purpose** | Inherits parent's full conversation context for cache-identical API prefixes |
| **Gate** | `FORK_SUBAGENT` build feature, disabled in coordinator mode and non-interactive sessions |

---

## 4. Custom Agent Definitions

### File Format

Custom agents are Markdown files with YAML frontmatter. The body becomes the system prompt.

**File:** `src/tools/AgentTool/loadAgentsDir.ts`

### Frontmatter Schema (complete, from source)

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | **Yes** | — | Unique identifier (becomes `agentType`) |
| `description` | string | **Yes** | — | When to use; Claude sees this to decide delegation |
| `tools` | string (CSV) or array | No | All tools (`*`) | Allowlist; `Agent(x,y)` restricts spawnable subagent types |
| `disallowedTools` | string (CSV) or array | No | — | Denylist; removed from inherited/specified tools |
| `model` | string | No | `inherit` | `sonnet`, `opus`, `haiku`, full model ID, or `inherit` |
| `effort` | string or integer | No | inherit | `low`, `medium`, `high`, `max`, or integer |
| `permissionMode` | string | No | `default` | `default`, `acceptEdits`, `dontAsk`, `bypassPermissions`, `plan` |
| `maxTurns` | integer | No | — | Maximum agentic turns |
| `skills` | array of strings | No | — | Skills preloaded into context at startup |
| `mcpServers` | array | No | — | Server references (string) or inline definitions (`{name: config}`) |
| `hooks` | object | No | — | `PreToolUse`, `PostToolUse`, `Stop` events |
| `memory` | string | No | — | `user`, `project`, or `local` |
| `background` | boolean | No | `false` | Always run as background task |
| `isolation` | string | No | — | `worktree` (or `remote` for ant) |
| `initialPrompt` | string | No | — | Auto-submitted as first user turn when running via `--agent` |
| `color` | string | No | — | UI color for the agent |

### Tool Restriction Mechanics

**File:** `src/tools/AgentTool/agentToolUtils.ts` — `resolveAgentTools()`

1. **Filtering pipeline:** All tools first pass through `filterToolsForAgent()`:
   - `ALL_AGENT_DISALLOWED_TOOLS`: TaskOutput, ExitPlanModeV2, EnterPlanMode, Agent (for non-ant), AskUserQuestion, TaskStop, Workflow
   - `CUSTOM_AGENT_DISALLOWED_TOOLS`: Same as above (extends ALL)
   - Async agents additionally filtered to `ASYNC_AGENT_ALLOWED_TOOLS`: Read, WebSearch, TodoWrite, Grep, WebFetch, Glob, shell tools, Edit, Write, NotebookEdit, SendMessage, LSP, and MCP tools
   - MCP tools (`mcp__*`) always pass through

2. **Disallowed tools applied:** Tools in `disallowedTools` are removed from the available pool.

3. **Allowlist resolution:** If `tools` is defined and not `['*']`, only listed tools are included. The `Agent(type1, type2)` syntax extracts `allowedAgentTypes` metadata.

4. **Main thread vs subagent:** When an agent runs as main thread (`--agent`), `filterToolsForAgent` is skipped and the tool pool comes directly from `assembleToolPool()`.

### Source Priority (highest wins)

From `getActiveAgentsFromList()`:

1. `policySettings` (managed/admin)
2. `flagSettings` (CLI `--agents` JSON)
3. `projectSettings` (`.claude/agents/`)
4. `userSettings` (`~/.claude/agents/`)
5. `plugin` (plugin `agents/` directories)
6. `built-in` (code-defined)

When multiple agents share the same `name`, the higher-priority source wins. The `/agents` command shows override information.

### Plugin Agent Restrictions

For agents sourced from plugins (`source: 'plugin'`):
- `hooks`, `mcpServers`, and `permissionMode` fields are **silently ignored** for security
- This is enforced by `isSourceAdminTrusted()` checks in `runAgent.ts`

### Memory Auto-Injection

When `memory` is set and auto-memory is enabled:
- `Read`, `Write`, and `Edit` tools are automatically added to the tool list
- `loadAgentMemoryPrompt()` appends memory instructions + first 200 lines/25KB of `MEMORY.md` to the system prompt
- Memory directory is created on first use via `ensureMemoryDirExists()`

---

## 5. Execution Modes

### Foreground (Synchronous)

- Main conversation blocks until subagent completes
- Permission prompts passed through to user
- `AskUserQuestion` works normally
- Shares parent's `AbortController` (Escape cancels both)
- After 2 seconds, shows a "Ctrl+B to background" hint
- Can be dynamically backgrounded via Ctrl+B (transitions to async lifecycle)

### Background (Asynchronous)

Triggered by:
- `run_in_background: true` in tool call
- `background: true` in agent definition
- Fork experiment active (forces ALL spawns async)
- Coordinator mode
- KAIROS assistant mode

Characteristics:
- Gets its own unlinked `AbortController`
- Cannot show permission prompts (`shouldAvoidPermissionPrompts: true`)
- Exception: `permissionMode: 'bubble'` surfaces prompts to parent terminal
- Parent receives `async_launched` result immediately with `agentId` and `outputFile` path
- On completion, `enqueueAgentNotification()` delivers result as a user-role message
- Can be killed via `TaskStop` (by the user or parent)

### Auto-Background

Controlled by `CLAUDE_AUTO_BACKGROUND_TASKS=1` env var or `tengu_auto_background_agents` GrowthBook flag. When active, foreground agents auto-background after 120 seconds (2 minutes).

### Worktree Isolation

When `isolation: 'worktree'`:
1. `createAgentWorktree()` creates a temporary git worktree with slug `agent-{agentId[:8]}`
2. All agent operations run inside `runWithCwdOverride(worktreePath, ...)`
3. On completion, `hasWorktreeChanges()` checks if the worktree has changes vs the HEAD commit
4. If no changes: worktree is automatically cleaned up via `removeAgentWorktree()`
5. If changes exist: worktree path and branch are returned in the notification

### Remote Isolation (ant-only)

When `isolation: 'remote'`:
- Delegates to CCR (Claude Code Remote) via `teleportToRemote()`
- Always runs in background
- Returns `remote_launched` status with a session URL

### In-Process Teammates

**File:** `src/utils/swarm/spawnInProcess.ts`

When agent teams use the in-process backend:
- Teammates run in the same Node.js process using `AsyncLocalStorage` for context isolation
- Cannot spawn background agents
- Cannot spawn nested teammates
- Get restricted tool set: standard tools + task management tools (`TaskCreate`, `TaskGet`, `TaskList`, `TaskUpdate`, `SendMessage`)
- Agent tool available but only for synchronous subagent spawning

---

## 6. Model & Resource Control

### Model Resolution Order

**File:** `src/utils/model/agent.ts` — `getAgentModel()`

Priority (highest first):

1. **`CLAUDE_CODE_SUBAGENT_MODEL` env var** — Overrides everything. Applies `parseUserSpecifiedModel()`.
2. **Per-invocation `model` parameter** — The `model` field in the Agent tool call (only `sonnet`, `opus`, `haiku`).
3. **Agent definition `model` field** — From frontmatter or built-in definition.
4. **Default:** `getDefaultSubagentModel()` returns `'inherit'`.
5. **`'inherit'` resolution:** Calls `getRuntimeMainLoopModel()` with the parent's model. Handles plan mode Opus upgrade logic.

**Bedrock region inheritance:** If the parent model uses a cross-region prefix (e.g., `eu.`), subagents using alias models automatically inherit that prefix. Explicit full model IDs that already carry a region prefix are preserved.

**Alias tier matching:** When a bare alias (`opus`, `sonnet`, `haiku`) matches the parent's tier, the parent's exact model string is used instead of resolving through `getDefaultOpusModel()` etc. This prevents surprising downgrades (e.g., Opus 4.6 user spawning `model: opus` getting an older Opus version).

### Effort Propagation

**File:** `src/tools/AgentTool/runAgent.ts` lines 483-497

If the agent definition has an `effort` field, it overrides the parent's `effortValue` in the agent's `getAppState()`. Otherwise, the parent's effort level is inherited.

### Token/Output Limits

**File:** `src/utils/task/outputFormatting.ts`

- `TASK_MAX_OUTPUT_LENGTH` env var controls the maximum characters in task output
- Default: 32,000 characters
- Upper limit: 160,000 characters
- The Agent tool itself has `maxResultSizeChars: 100_000`

### Thinking Configuration

- **Fork agents:** Inherit parent's `thinkingConfig` (for cache-identical prefixes)
- **Regular subagents:** Thinking is **disabled** (`{ type: 'disabled' }`) to control output token costs

### CLAUDE.md Optimization

- Agents with `omitClaudeMd: true` (Explore, Plan) do NOT receive the CLAUDE.md hierarchy
- This saves ~5-15 Gtok/week across 34M+ Explore spawns
- Kill-switch: `tengu_slim_subagent_claudemd` GrowthBook flag (defaults true)
- Explore and Plan also drop `gitStatus` from system context (stale snapshot, can run `git status` themselves)

---

## 7. Agent Communication

### Result Delivery

**Synchronous agents:** The parent blocks until the agent completes. `finalizeAgentTool()` extracts the last assistant message's text content and returns it as the tool result. The parent sees `agentId`, `agentType`, content, token usage, tool use count, and duration.

**Asynchronous agents:** On completion, `enqueueAgentNotification()` creates a synthetic user-role message delivered to the parent:
- Includes: task description, status (completed/failed/killed), final message text, usage stats
- If worktree isolation was used: includes `worktreePath` and `worktreeBranch`
- If transcript classifier flags the output: prepends a security warning

### SendMessage Tool

**File:** `src/tools/SendMessageTool/SendMessageTool.ts`

Available when `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` or `--agent-teams` flag is set.

**Input schema:**
```typescript
{
  to: string,      // Teammate name, "*" for broadcast, "uds:<socket>" for cross-session
  summary?: string, // 5-10 word preview
  message: string | StructuredMessage  // Plain text or shutdown/plan_approval protocol
}
```

**Routing:**

1. **Teammate messaging:** Writes to the recipient's mailbox file at `~/.claude/teams/{team-name}/mailbox/`
2. **Broadcast:** `to: "*"` sends to all teammates except self
3. **Subagent resume:** When `to` matches an agent ID, calls `resumeAgentBackground()` — this loads the agent's transcript from disk, creates a new `runAgent()` with the resumed messages + new prompt, and runs it as a background agent
4. **In-process teammate:** If the target is an in-process teammate, uses `queuePendingMessage()` to deliver directly
5. **Structured messages:** `shutdown_request`, `shutdown_response`, `plan_approval_response` — protocol messages for coordinating agent lifecycle

### Agent Name Registry

When a background agent is spawned with a `name` parameter, the mapping `name -> agentId` is stored in `appState.agentNameRegistry`. This allows `SendMessage({to: "my-agent-name"})` to route correctly.

### Idle Notifications

When a teammate completes its turn, the system automatically sends an idle notification to the team lead. This includes:
- The teammate's name
- Brief summaries of any peer DMs they sent during their turn
- Status is purely informational — teammate can be woken up by sending another message

---

## 8. Team/Swarm System

### Architecture

**Files:**
- `src/tools/TeamCreateTool/` — Creates teams
- `src/tools/TeamDeleteTool/` — Deletes teams
- `src/utils/swarm/` — All swarm infrastructure

### Team Creation Flow

1. `TeamCreateTool.call()` generates a team name, creates a team file at `~/.claude/teams/{name}/config.json`, and a task list at `~/.claude/tasks/{name}/`
2. The creating agent becomes the **team lead** with agent ID `team-lead@{teamName}`
3. Team file stores: name, description, creation time, lead agent ID, lead session ID, members array

### Spawning Teammates

When the Agent tool receives both `team_name` and `name` parameters, it routes to `spawnTeammate()` instead of creating a subagent:

**File:** `src/tools/shared/spawnMultiAgent.ts` (referenced) and `src/utils/swarm/`

The teammate is created using one of three backends:

### Backend Types

**File:** `src/utils/swarm/backends/types.ts`

| Backend | Type | Isolation | Use Case |
|---------|------|-----------|----------|
| **tmux** | Process-based | Separate process in tmux pane | Default for tmux environments |
| **iTerm2** | Process-based | Separate process in iTerm2 split pane | Mac iTerm2 users |
| **in-process** | In-process | AsyncLocalStorage context | Same Node.js process |

**Backend detection:** `src/utils/swarm/backends/detection.ts` auto-detects the environment.

**tmux backend** (`TmuxBackend.ts`):
- Creates panes in a dedicated swarm view window
- Spawns full Claude Code processes with inherited CLI flags
- Inherits env vars: API provider config, proxy settings, config dir, etc.
- Teammate command configurable via `CLAUDE_CODE_TEAMMATE_COMMAND` env var

**in-process backend** (`InProcessBackend.ts`, `spawnInProcess.ts`):
- Creates `TeammateContext` with isolated identity (name, team, agentId)
- Uses `AsyncLocalStorage` so each teammate has its own context
- Creates linked `AbortController`
- Registers `InProcessTeammateTaskState` in AppState

### Permission Sharing

From `spawnUtils.ts` — `buildInheritedCliFlags()`:
- `bypassPermissions` propagated unless plan mode is required
- `acceptEdits` propagated
- Model override (`--model`) propagated
- Settings path propagated
- Plugin directories propagated
- Teammate mode propagated
- Chrome flag propagated

### Team Communication

**Mailbox system:** `src/utils/teammateMailbox.ts`
- Messages written to files in `~/.claude/teams/{team-name}/mailbox/`
- Each teammate has its own mailbox
- Messages are automatically delivered as user-role messages
- Include: `from`, `text`, `summary`, `timestamp`, `color`

**Teammate prompt addendum:** `src/utils/swarm/teammatePromptAddendum.ts`
- Appended to teammate's system prompt
- Explains that text responses are not visible to team — must use `SendMessage`

### Teammate Model

**File:** `src/utils/swarm/teammateModel.ts`
- Default teammate model: Opus 4.6 (provider-aware — correct model ID for Bedrock/Vertex/Foundry)
- Hardcoded fallback: `CLAUDE_OPUS_4_6_CONFIG[getAPIProvider()]`

### Task Coordination

Teams share a task list at `~/.claude/tasks/{team-name}/`:
- Tasks created via `TaskCreate` tool
- Tasks assigned via `TaskUpdate` with `owner` field
- All teammates can read/write the shared task list
- Task IDs auto-increment from 1 per team

---

## 9. User-Facing Controls

### Slash Commands

| Command | Purpose |
|---------|---------|
| `/agents` | List and manage agent configurations. Shows all agents by source group with override information. Reloads agent definitions on invocation. |
| `/model` | Change model (affects subagent model when set to `inherit`) |
| `/statusline` | Triggers the `statusline-setup` built-in agent |
| `/fork <directive>` | Available when fork experiment is active |

### CLI Flags

| Flag | Purpose |
|------|---------|
| `--agent <name>` | Run entire session as a specific agent |
| `--agents '<json>'` | Define agents inline as JSON |
| `--disallowedTools "Agent(X)"` | Deny specific agent types |
| `--agent-teams` | Enable agent teams feature |
| `--teammate-mode <mode>` | Backend mode for teammates (tmux/iterm2/in-process) |

### Environment Variables

| Variable | Purpose |
|----------|---------|
| `CLAUDE_CODE_SUBAGENT_MODEL` | Override model for ALL subagents (highest priority) |
| `CLAUDE_CODE_DISABLE_BACKGROUND_TASKS=1` | Disable all background agent execution |
| `CLAUDE_AUTO_BACKGROUND_TASKS=1` | Auto-background foreground agents after 120s |
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` | Enable agent teams and SendMessage tool |
| `CLAUDE_CODE_AGENT_LIST_IN_MESSAGES` | Control whether agent list is in tool description or attachment message (true/false) |
| `CLAUDE_CODE_COORDINATOR_MODE` | Enable coordinator mode (different built-in agents) |
| `CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS` | Disable all built-in agents (SDK/noninteractive only) |
| `CLAUDE_CODE_TEAMMATE_COMMAND` | Override command for spawning teammate processes |
| `CLAUDE_CODE_SIMPLE` | Skip custom agents, only use built-ins |
| `TASK_MAX_OUTPUT_LENGTH` | Max characters in agent output (default 32K, max 160K) |

### Settings.json Controls

```json
{
  "agent": "code-reviewer",           // Default session agent
  "permissions": {
    "deny": ["Agent(Explore)"]         // Deny specific agent types
  }
}
```

### Interactive Controls

| Action | Effect |
|--------|--------|
| **Ctrl+B** | Background a running foreground agent |
| **@"agent-name (agent)"** | Explicitly invoke a specific agent |
| **"Use the X subagent to..."** | Natural language delegation |
| **Escape** | Cancel foreground agent (shared AbortController) |

---

## 10. Key Code Paths

### Core Agent System

| File | Purpose |
|------|---------|
| `src/tools/AgentTool/AgentTool.tsx` | Main tool definition, input/output schemas, spawn routing, sync/async lifecycle |
| `src/tools/AgentTool/runAgent.ts` | Agent execution — system prompt construction, tool resolution, query() loop, MCP init, hook registration, skill preloading |
| `src/tools/AgentTool/prompt.ts` | `getPrompt()` — generates the tool description including available agents list and usage examples |
| `src/tools/AgentTool/agentToolUtils.ts` | `resolveAgentTools()`, `filterToolsForAgent()`, `finalizeAgentTool()`, `runAsyncAgentLifecycle()`, handoff classification |
| `src/tools/AgentTool/loadAgentsDir.ts` | Agent definition types, frontmatter parsing (`parseAgentFromMarkdown()`), JSON parsing (`parseAgentFromJson()`), priority merging |
| `src/tools/AgentTool/builtInAgents.ts` | `getBuiltInAgents()` — assembles the list of built-in agents with feature gates |
| `src/tools/AgentTool/resumeAgent.ts` | `resumeAgentBackground()` — loads transcript from disk, reconstructs replacement state, resumes as background agent |
| `src/tools/AgentTool/forkSubagent.ts` | Fork experiment — `FORK_AGENT` definition, `buildForkedMessages()`, recursive fork guard, worktree notice |
| `src/tools/AgentTool/constants.ts` | Tool name constants, `ONE_SHOT_BUILTIN_AGENT_TYPES` |

### Built-in Agent Definitions

| File | Agent |
|------|-------|
| `src/tools/AgentTool/built-in/exploreAgent.ts` | Explore (read-only search) |
| `src/tools/AgentTool/built-in/generalPurposeAgent.ts` | general-purpose (all tools) |
| `src/tools/AgentTool/built-in/planAgent.ts` | Plan (read-only architect) |
| `src/tools/AgentTool/built-in/claudeCodeGuideAgent.ts` | claude-code-guide (docs helper) |
| `src/tools/AgentTool/built-in/statuslineSetup.ts` | statusline-setup (status bar config) |
| `src/tools/AgentTool/built-in/verificationAgent.ts` | verification (adversarial testing) |

### Model Resolution

| File | Purpose |
|------|---------|
| `src/utils/model/agent.ts` | `getAgentModel()` — full resolution chain with Bedrock region inheritance |

### Tool Restrictions

| File | Purpose |
|------|---------|
| `src/constants/tools.ts` | `ALL_AGENT_DISALLOWED_TOOLS`, `CUSTOM_AGENT_DISALLOWED_TOOLS`, `ASYNC_AGENT_ALLOWED_TOOLS`, `IN_PROCESS_TEAMMATE_ALLOWED_TOOLS` |

### Team/Swarm System

| File | Purpose |
|------|---------|
| `src/tools/TeamCreateTool/TeamCreateTool.ts` | Team creation, team file writing, AppState registration |
| `src/tools/TeamCreateTool/prompt.ts` | Team workflow documentation prompt |
| `src/tools/TeamDeleteTool/TeamDeleteTool.ts` | Team deletion and cleanup |
| `src/tools/SendMessageTool/SendMessageTool.ts` | Message routing, broadcast, subagent resume, protocol messages |
| `src/tools/SendMessageTool/prompt.ts` | SendMessage usage documentation |
| `src/utils/swarm/constants.ts` | Team names, socket names, env vars |
| `src/utils/swarm/teamHelpers.ts` | Team file I/O, member management, cleanup |
| `src/utils/swarm/spawnUtils.ts` | CLI flag and env var inheritance for teammates |
| `src/utils/swarm/spawnInProcess.ts` | In-process teammate spawning |
| `src/utils/swarm/backends/TmuxBackend.ts` | tmux pane management |
| `src/utils/swarm/backends/ITermBackend.ts` | iTerm2 pane management |
| `src/utils/swarm/backends/InProcessBackend.ts` | In-process backend |
| `src/utils/swarm/backends/registry.ts` | Backend auto-detection and mode resolution |
| `src/utils/swarm/backends/types.ts` | `BackendType`, `PaneBackend` interface |
| `src/utils/swarm/teammateModel.ts` | Default teammate model (Opus 4.6) |
| `src/utils/swarm/teammatePromptAddendum.ts` | System prompt addition for teammates |

### Agent Memory

| File | Purpose |
|------|---------|
| `src/tools/AgentTool/agentMemory.ts` | Memory scope resolution, path computation, memory prompt generation |
| `src/tools/AgentTool/agentMemorySnapshot.ts` | Project snapshot initialization for agent memory |

### Agent UI

| File | Purpose |
|------|---------|
| `src/tools/AgentTool/UI.tsx` | Agent tool rendering — progress, grouped display, result messages |
| `src/tools/AgentTool/agentDisplay.ts` | Source group ordering, override resolution, model display |
| `src/tools/AgentTool/agentColorManager.ts` | Agent color assignment and management |

---

## Appendix: Key Type Definitions

### AgentDefinition (union type)

```typescript
type AgentDefinition = BuiltInAgentDefinition | CustomAgentDefinition | PluginAgentDefinition

type BaseAgentDefinition = {
  agentType: string
  whenToUse: string
  tools?: string[]
  disallowedTools?: string[]
  skills?: string[]
  mcpServers?: AgentMcpServerSpec[]
  hooks?: HooksSettings
  color?: AgentColorName
  model?: string
  effort?: EffortValue
  permissionMode?: PermissionMode
  maxTurns?: number
  filename?: string
  baseDir?: string
  criticalSystemReminder_EXPERIMENTAL?: string
  requiredMcpServers?: string[]
  background?: boolean
  initialPrompt?: string
  memory?: AgentMemoryScope  // 'user' | 'project' | 'local'
  isolation?: 'worktree' | 'remote'
  omitClaudeMd?: boolean
}

type BuiltInAgentDefinition = BaseAgentDefinition & {
  source: 'built-in'
  getSystemPrompt: (params: { toolUseContext }) => string
}

type CustomAgentDefinition = BaseAgentDefinition & {
  source: SettingSource  // 'userSettings' | 'projectSettings' | 'policySettings' | 'flagSettings' | ...
  getSystemPrompt: () => string
}

type PluginAgentDefinition = BaseAgentDefinition & {
  source: 'plugin'
  plugin: string
  getSystemPrompt: () => string
}
```

### AgentToolResult

```typescript
type AgentToolResult = {
  agentId: string
  agentType?: string
  content: Array<{ type: 'text', text: string }>
  totalToolUseCount: number
  totalDurationMs: number
  totalTokens: number
  usage: {
    input_tokens: number
    output_tokens: number
    cache_creation_input_tokens: number | null
    cache_read_input_tokens: number | null
    server_tool_use: { web_search_requests: number, web_fetch_requests: number } | null
    service_tier: 'standard' | 'priority' | 'batch' | null
    cache_creation: { ephemeral_1h_input_tokens: number, ephemeral_5m_input_tokens: number } | null
  }
}
```
