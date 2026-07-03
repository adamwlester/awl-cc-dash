# Adopting a push-based Claude Code HTTP-hook event stream as the primary run-state signal

## 1. Restated question

Should awl-cc-dash move from a screen-scraping-first run-state model to a Claude Code hook-event-first model for interactive coding agents, where each WSL2/tmux Claude Code process POSTs lifecycle events to the existing Windows FastAPI sidecar, while preserving the current `tmux capture-pane` classifier and transcript tailing as fallbacks for sessions where hooks are absent, disabled, stale, or lossy? [confirmed: prompt constraint]

The answer is: adopt hooks as the primary signal **when present and fresh**, but do **not** hard-replace screen polling. The right architecture is an authoritative-when-present event layer over the current polling floor, with transcript reconciliation for deterministic tool-in-flight checks. [plausible: design recommendation]

Key framing constraints I used:

- The primary control path remains TUI-over-tmux, not the Agent SDK. [confirmed: prompt constraint]
- The WSL2 -> Windows HTTP hop via the WSL2 default gateway is already a working, best-effort transport for existing hooks. [confirmed: prompt constraint]
- A hookless launch must still work: failed gateway resolution, disabled hooks, settings policy, safe mode, or a down sidecar must degrade to polling. [confirmed: prompt constraint; supported by Claude Code's non-blocking HTTP hook error behavior, S1]
- The goal is run-state fidelity: `idle`, `generating`, `permission-prompt`, and related supporting states such as `error`, `ended`, `hook-stale`, and `background-running`. [plausible: state-model extension]

## 2. Options considered

### Option A - Keep screen polling as the only primary signal

Keep the current ~1 second `tmux capture-pane` sampling and classify the visible TUI text into `idle`, `generating`, `permission-prompt`, and `unknown`. tmux documents `capture-pane` as capturing pane contents, with `-p` outputting to stdout; by default it captures the visible pane contents. [confirmed, S6]

This is the safest operational floor because it observes the same terminal surface the operator sees. [plausible] It also already handles hookless sessions. [confirmed: prompt constraint]

### Option B - Replace screen polling with a pure push-based HTTP-hook stream

Register HTTP hooks for all useful Claude Code lifecycle events and derive run-state only from POSTed hook payloads. Claude Code documents HTTP hooks as `type: "http"` handlers that send the event JSON input as an HTTP POST request to a configured URL; the response uses the same JSON output format as command hooks. [confirmed, S1]

This is attractive because the event stream is structured, low-frequency compared with display scraping, and has typed fields such as `session_id`, `transcript_path`, `permission_mode` on many events, `tool_name`, `tool_input`, and `tool_use_id` on tool events. [confirmed, S1]

However, a pure replacement is not safe. HTTP hook failures, non-2xx statuses, connection failures, and timeouts are documented as non-blocking errors where execution continues, which means a missed event can silently desynchronize the dashboard. [confirmed, S1] Also, the documented `async: true` background mode is only available for `type: "command"` hooks, not HTTP hooks. [confirmed, S1] Therefore an HTTP hook is not documented as fire-and-forget; it must return quickly or wait until timeout. [confirmed/plausible]

### Option C - Hybrid: hooks authoritative when fresh, screen polling and transcript overlay as floor

Use hooks as the primary run-state source once a session has produced a valid hook event recently. Keep screen polling active as a watchdog and fallback, and use the transcript to reconcile tool-in-flight state. This is the recommended path. [plausible]

The sidecar receives hook events, assigns a per-agent `arrival_seq`, enqueues them into a per-agent arbiter, and emits merged state over the existing SSE path. Polling remains enabled, but can run at a lower cadence while hooks are fresh, returning to the current ~1 second cadence when hooks are absent or stale. [plausible]

### Option D - Transcript-first tailing, hooks as accelerators

Tail the JSONL transcript and derive state from assistant `tool_use` blocks and corresponding user `tool_result` blocks, treating an unmatched `tool_use` id as evidence the agent is still working. Anthropic's platform docs define a `tool_use` id as the identifier later matched by a `tool_result` block. [confirmed, S7] Claude Code hook inputs include `transcript_path`, which gives the sidecar a documented pointer to the conversation JSONL. [confirmed, S1]

This is a strong cross-check but a weaker primary signal: transcript writes may lag the UI; not every permission prompt or terminal status is represented as a clean state transition; and schema details should be verified against the installed Claude Code build before relying on transcript parsing for product-critical state. [plausible/speculative]

### Option E - Switch the interactive agents to Agent SDK or print-mode stream-json

Reject for this dashboard's primary path. The prompt states the interactive coding agents are real `claude` CLI processes in detached tmux sessions, and the main path is not the Agent SDK. [confirmed: prompt constraint] Claude Code does document `--include-hook-events` for `--output-format stream-json` in print mode, but that is not the same as the interactive TUI/tmux bridge. [confirmed, S3]

## 3. Trade-offs

### Option A trade-offs - screen only

Benefits:

- [confirmed/plausible] Works with hookless sessions and requires no new Claude Code settings.
- [confirmed] Uses `tmux capture-pane`, a documented tmux capability for capturing visible pane output. [S6]
- [plausible] Preserves current behavior and operator mental model.

Costs and breakpoints:

- [plausible] It infers state from a human-optimized terminal screen rather than a machine-typed lifecycle stream, so it can flicker on spinner text, partial redraws, terminal wrapping, themes, and permission prompt wording changes.
- [plausible] It is polling-based, so best-case detection latency is tied to the polling interval.
- [plausible] It is weaker for many concurrent agents because each agent consumes periodic tmux subprocess work even when idle.

Assumptions to verify:

- [repo-verification needed] The current classifier's failure modes are acceptable as a floor, especially after Claude Code TUI updates.

### Option B trade-offs - pure hooks replace polling

Benefits:

- [confirmed] Claude Code has documented lifecycle hooks, including `UserPromptSubmit`, `PreToolUse`, `PermissionRequest`, `PostToolUse`, `PostToolUseFailure`, `PostToolBatch`, `Notification`, `Stop`, `StopFailure`, `SessionStart`, `SessionEnd`, `SubagentStart`, and `SubagentStop`. [S1]
- [confirmed] HTTP hooks provide structured JSON POST bodies, including common fields such as `session_id`, `transcript_path`, `cwd`, and `permission_mode` on events that include it. [S1]
- [confirmed] Tool events include specific fields such as `tool_name`, `tool_input`, and often `tool_use_id`; `PostToolUse` includes `tool_response` and optional `duration_ms`. [S1]

Costs and breakpoints:

- [confirmed] HTTP hook connection failures and timeouts allow Claude Code execution to continue, so events can be missed without stopping the agent. [S1]
- [confirmed] HTTP hooks are not documented as supporting `async: true`; that option is documented only for command hooks. [S1]
- [confirmed] `UserPromptSubmit` blocks model processing until the hook completes or times out, and most command/http/mcp hooks default to long timeouts unless explicitly lowered. [S1]
- [confirmed] `Stop` does not run when the stoppage occurred due to user interrupt; API errors fire `StopFailure` instead. [S1]
- [plausible] A pure hook design can get stuck in `generating` if the `Stop`/`StopFailure` event is lost.

Assumptions to verify:

- [spike required] Whether the installed Claude Code build sends `permission_mode` on every event the dashboard cares about. The docs explicitly warn that not all events receive `permission_mode`; each event's example must be checked. [S1]
- [spike required] Whether every bridge-driven prompt path triggers `UserPromptSubmit` under the interactive tmux TUI, including injected or pasted prompts.

### Option C trade-offs - hybrid, recommended

Benefits:

- [plausible] Uses hooks for typed, low-latency state changes when they are available.
- [confirmed/plausible] Preserves the existing hookless session floor required by the prompt.
- [confirmed/plausible] Can reconcile hook loss using the transcript, because hook payloads include `transcript_path`, and Anthropic tool-use semantics give each `tool_use` an id matched by a later `tool_result`. [S1, S7]
- [plausible] Reduces UI flicker because a `PermissionRequest` hook is more semantically precise than a screen text classifier.

Costs and breakpoints:

- [plausible] Requires a per-agent state arbiter and conflict-resolution policy.
- [plausible] Requires operational metrics: hook seen, hook stale, queue drops, last event age, fallback reason.
- [plausible] More complex to test because correctness depends on merge behavior under lost, late, and duplicate events.

Assumptions to verify:

- [repo-verification needed] How the sidecar currently maps Claude Code `session_id`, tmux session id, app agent id, and transcript path.
- [spike required] Payload fields and event order on the installed CLI version, especially for parallel tool calls, `PermissionRequest`, `StopFailure`, and subagents.

### Option D trade-offs - transcript-first

Benefits:

- [confirmed] `tool_use` / `tool_result` id matching is a documented Claude tool-use concept. [S7]
- [confirmed] Hooks expose `transcript_path`, so a hook can bootstrap transcript discovery without scraping the filesystem. [S1]
- [plausible] Transcript reconciliation is deterministic for open tool calls and can harden against screen flicker or a late `PostToolUse` hook.

Costs and breakpoints:

- [plausible/speculative] Claude Code's on-disk transcript schema is less stable as a product contract than documented hook payloads; verify the installed build before relying on it.
- [plausible] Transcript tailing may not directly represent the permission dialog state or TUI idle prompt timing.
- [plausible] It can lag behind real-time UI state.

### Option E trade-offs - SDK/stream-json

Benefits:

- [confirmed] Claude Code print mode can include hook lifecycle events in `stream-json` output when `--include-hook-events` is used with `--output-format stream-json`. [S3]

Costs and breakpoints:

- [confirmed: prompt constraint] It violates the dashboard's current primary path: interactive `claude` CLI processes in detached tmux sessions.
- [plausible] Migrating the main driver from TUI/tmux to SDK or print-mode stream-json would be a larger architectural rewrite than extending existing hooks.

### Exact event set worth registering

Core events to register for run-state:

| Event | Matcher | Run-state use | Include? | Confidence |
|---|---:|---|---:|---|
| `SessionStart` | `startup|resume|clear|compact` | Mark hook path live; initialize `hook_seen`, `session_id`, `transcript_path`, optional model/title. | Yes | confirmed, S1 |
| `UserPromptSubmit` | omit/empty | Set `state=generating` or `state=processing_prompt`; record `prompt_id` if present; avoid storing raw `prompt` unless needed. | Yes | confirmed, S1 |
| `PreToolUse` | `*` | Set `state=generating`, `current_tool`, `open_tool_ids[tool_use_id]=running`; records `tool_name`, `tool_input`. | Yes | confirmed, S1 |
| `PermissionRequest` | `*` | Set `state=permission-prompt`, `current_tool`; this is the cleanest permission dialog signal. | Yes | confirmed, S1 |
| `PostToolUse` | `*` | Close successful `tool_use_id`; record duration; do **not** set idle, because Claude may continue generating. | Yes | confirmed/plausible, S1 |
| `PostToolUseFailure` | `*` | Close failed `tool_use_id`; record error; keep state generating unless terminal condition follows. | Yes | confirmed/plausible, S1 |
| `PostToolBatch` | matcher omitted | Batch boundary after all tool calls in a batch resolve; useful because `PostToolUse` can fire concurrently for parallel calls. | Yes | confirmed, S1 |
| `PermissionDenied` | `*` | Record denied tool call and reason; clear permission prompt when applicable. | Useful | confirmed/plausible, S1 |
| `Stop` | matcher omitted | Set `idle` if no background tasks or scheduled wakeups; otherwise set `background-running` or `scheduled`. | Yes | confirmed/plausible, S1 |
| `StopFailure` | omit or match error types | Set `error` / `idle-with-error`; record API failure type. | Yes | confirmed, S1 |
| `SessionEnd` | omit or all reasons | Set `ended`; cleanup per-agent maps. | Yes | confirmed, S1 |
| `Notification` | `permission_prompt|idle_prompt` | Supporting signal for permission and idle notifications; do not rely on it over `PermissionRequest`/`Stop`. | Supporting | confirmed/plausible, S1 |
| `SubagentStart` | `*` | Track subagent map; do not mutate parent coarse state except current parent tool may be `Agent`. | Optional | confirmed/plausible, S1 |
| `SubagentStop` | `*` | Close subagent map; do not mark parent session idle. | Optional | confirmed/plausible, S1 |

Events to avoid for primary run-state:

- `MessageDisplay`: useful for display transformation but too high-volume for coarse run-state; it can flood the sidecar and is not needed to know idle/generating/permission. [confirmed/plausible, S1]
- `FileChanged`, `ConfigChange`, `InstructionsLoaded`, `PostCompact`, `WorktreeCreate`, `WorktreeRemove`, `CwdChanged`: useful for audit/config workflows but not primary run-state. [confirmed/plausible, S1]
- `Elicitation` / `ElicitationResult`: consider later only if MCP elicitation dialogs become a dashboard state. [confirmed/plausible, S1]

### HTTP-hook config shape

Use generated per-agent settings or launch-time settings so the hook URL contains the current WSL2 default-gateway IP and an app-level `agent_id` / `launch_id`. Claude Code's documented HTTP hook schema is an inner hook handler with `type: "http"`, `url`, optional `timeout`, optional `headers`, and optional `allowedEnvVars`. [confirmed, S1]

One representative event block:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "http",
            "url": "http://<gateway-ip>:7690/internal/hooks/claude-code?agent_id=<agent-id>&launch_id=<launch-id>",
            "timeout": 1,
            "headers": {
              "Authorization": "Bearer $AWL_CC_DASH_HOOK_TOKEN"
            },
            "allowedEnvVars": ["AWL_CC_DASH_HOOK_TOKEN"]
          }
        ]
      }
    ]
  }
}
```

Generate analogous blocks for: `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PermissionRequest`, `PostToolUse`, `PostToolUseFailure`, `PostToolBatch`, `PermissionDenied`, `Stop`, `StopFailure`, `Notification`, and `SessionEnd`, plus optional `SubagentStart` and `SubagentStop`. [plausible]

Suggested matcher choices:

```json
{
  "hooks": {
    "SessionStart": [{ "matcher": "startup|resume|clear|compact", "hooks": ["<same http handler object>"] }],
    "UserPromptSubmit": [{ "hooks": ["<same http handler object>"] }],
    "PreToolUse": [{ "matcher": "*", "hooks": ["<same http handler object>"] }],
    "PermissionRequest": [{ "matcher": "*", "hooks": ["<same http handler object>"] }],
    "PostToolUse": [{ "matcher": "*", "hooks": ["<same http handler object>"] }],
    "PostToolUseFailure": [{ "matcher": "*", "hooks": ["<same http handler object>"] }],
    "PostToolBatch": [{ "hooks": ["<same http handler object>"] }],
    "PermissionDenied": [{ "matcher": "*", "hooks": ["<same http handler object>"] }],
    "Notification": [{ "matcher": "permission_prompt|idle_prompt", "hooks": ["<same http handler object>"] }],
    "Stop": [{ "hooks": ["<same http handler object>"] }],
    "StopFailure": [{ "hooks": ["<same http handler object>"] }],
    "SessionEnd": [{ "hooks": ["<same http handler object>"] }]
  }
}
```

The second snippet is intentionally schematic because JSON has no object reference syntax; the actual generator should expand `"<same http handler object>"` into the full handler object. [confirmed/plausible]

Also set, if your environment uses hook URL allowlists:

```json
{
  "allowedHttpHookUrls": [
    "http://<gateway-ip>:7690/internal/hooks/*",
    "http://localhost:7690/internal/hooks/*"
  ],
  "httpHookAllowedEnvVars": ["AWL_CC_DASH_HOOK_TOKEN"]
}
```

Claude Code documents `allowedHttpHookUrls` as a settings allowlist for HTTP hook targets, and `httpHookAllowedEnvVars` as the allowlist for environment variables interpolated into HTTP hook headers. [confirmed, S2]

### Latency, ordering, and dedup engineering

Latency policy:

- [confirmed] HTTP hooks are synchronous from Claude Code's point of view; HTTP errors/timeouts are non-blocking only after the failed response/timeout path resolves. [S1]
- [confirmed] The default timeout is long for most command/http/mcp hooks, and `UserPromptSubmit` specifically blocks prompt processing until completion or timeout. [S1]
- [plausible] Set every run-state HTTP hook timeout to a small integer, such as 1 second, and ensure the FastAPI handler normally returns `204 No Content` or `200 {}` in a few milliseconds.
- [plausible] The HTTP handler should do only: authenticate, parse minimal fields, assign `received_at` and `arrival_seq`, enqueue to a per-agent queue, and return. Do not tail transcripts, write slow durable logs, call the Electron UI, run tmux commands, or perform network I/O inside the hook request path.
- [plausible] Avoid `MessageDisplay` and other high-volume events so event rate scales with prompts and tools, not tokens.

Ordering policy:

- [confirmed] Hook payloads have `session_id`; newer docs also document `prompt_id` for correlation with a prompt, requiring Claude Code v2.1.196 or later. [S1]
- [confirmed] Tool events provide `tool_use_id` on `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, and `PermissionDenied`; `PermissionRequest` intentionally lacks `tool_use_id`. [S1]
- [confirmed] `PostToolUse` fires once per tool and can fire concurrently for parallel tool calls; `PostToolBatch` fires once after the full batch resolves. [S1]
- [plausible] Assign a sidecar `arrival_seq` per app agent. This gives deterministic processing order inside the sidecar, but it is arrival order, not original creation order.
- [speculative unless wrapped] A true source-side `report_seq` is not available in the documented pure HTTP-hook payload. To create one, you would need a command-hook wrapper that increments a local counter and POSTs to the sidecar, or an undocumented Claude Code field. Do not rely on `report_seq` in direct HTTP hooks until a spike proves it exists.

Per-agent arbiter:

- [plausible] Route each event to one arbiter keyed by dashboard `agent_id`, with fallback matching by `(session_id, transcript_path, launch_id)`.
- [plausible] Maintain per-prompt phase and per-tool maps rather than a single last-event-wins scalar.
- [plausible] Use event phases for stale-event suppression: `SessionStart=0`, `UserPromptSubmit=10`, `PreToolUse=30`, `PermissionRequest=40`, `PostToolUse/PostToolUseFailure/PermissionDenied=50`, `PostToolBatch=55`, `Stop/StopFailure=90`, `SessionEnd=100`.
- [plausible] A late `PostToolUse` for a prompt that already reached `Stop` should update audit/tool history but must not revert the coarse state from `idle` to `generating`.
- [plausible] A new `prompt_id`, or a new prompt observed by tmux injection if `prompt_id` is absent, starts a new phase and can move state back to `generating`.

Dedup policy:

- [confirmed] Claude Code itself deduplicates identical matching HTTP handlers by URL during a hook fire. [S1]
- [plausible] Still dedup in the sidecar using natural keys:
  - Tool events: `(agent_id, session_id, prompt_id, hook_event_name, tool_use_id)`.
  - `PermissionRequest`: `(agent_id, session_id, prompt_id, hook_event_name, tool_name, stable_hash(tool_input), short_time_bucket)`.
  - `Stop`: `(agent_id, session_id, prompt_id, hook_event_name, stop_hook_active, stable_hash(last_assistant_message))`.
  - `Notification`: `(agent_id, session_id, prompt_id, notification_type, stable_hash(message), short_time_bucket)`.
  - `SessionStart`/`SessionEnd`: `(agent_id, session_id, hook_event_name, source_or_reason, launch_id)`.
- [plausible] Keep a bounded dedup LRU per agent and a bounded raw-event ring buffer for debugging.

Fallback policy:

- [confirmed] The prompt requires screen polling to remain the fallback. [prompt constraint]
- [confirmed] Claude Code settings can disable all hooks, and safe mode disables hooks/customizations except policy-managed pieces; HTTP hook URL allowlists can also block nonmatching URLs. [S1, S2, S3]
- [confirmed] In WSL2 NAT mode, Microsoft documents using `ip route show | grep -i default | awk '{ print $3 }'` inside WSL to get the Windows host IP as seen from WSL2; with mirrored networking, localhost works. [S4, S5]
- [plausible] Per launch, compute hook status: `expected`, `first_seen`, `fresh`, `stale`, `absent`, `disabled_or_blocked_unknown`.
- [plausible] If no hook event arrives within a short window after launch or first prompt, keep current screen polling as primary.
- [plausible] If hooks were fresh but no expected terminal event arrives before the state becomes suspicious, mark `hook_stale`, restore ~1 second polling, and reconcile with transcript.
- [plausible] Transcript overlay should override false idle when it sees an open `tool_use` id with no matching `tool_result`.

## 4. Per-finding confidence

| Finding | Confidence | Notes |
|---|---:|---|
| Claude Code supports HTTP hooks with `type: "http"`, `url`, `timeout`, `headers`, and `allowedEnvVars`. | confirmed | Official hooks reference. [S1] |
| HTTP hook input is sent as a JSON POST body and HTTP response body uses hook JSON output semantics. | confirmed | Official hooks reference. [S1] |
| HTTP hook connection failures, non-2xx responses, and timeouts are non-blocking errors; execution continues. | confirmed | Official hooks reference. [S1] |
| `async: true` is documented only for command hooks, not HTTP hooks. | confirmed | Official hooks reference. [S1] |
| Candidate events `PermissionRequest`, `SubagentStart`, `SubagentStop`, and `StopFailure` are real documented events as of the current docs checked on 2026-07-02. | confirmed | Official hooks reference. [S1] |
| `permission_mode` is present as a common field on events that receive it, but not all events receive it. | confirmed | Official hooks reference. [S1] |
| Relying on `permission_mode` being present on every hook payload is unsafe until spiked on the installed CLI build. | plausible | Docs explicitly warn not all events receive it. [S1] |
| A direct pure HTTP hook does not provide a documented source-side sequence number. | plausible | No sequence field appears in common/event schemas; absence should be spike-verified. [S1] |
| A sidecar `arrival_seq` is useful but cannot prove original event creation order under parallel tool calls or network delay. | plausible | Derived from distributed-systems reasoning and documented concurrent `PostToolUse`. [S1] |
| `PostToolBatch` should be registered because it resolves parallel `PostToolUse` ambiguity at batch granularity. | plausible/confirmed | Event and concurrency behavior documented; recommendation is design judgment. [S1] |
| Hooks should be primary only while fresh, with screen and transcript fallback. | plausible | Design judgment based on documented lossy/non-blocking HTTP behavior and prompt constraints. [S1] |
| The WSL2 default-gateway IP approach is appropriate in NAT mode; localhost may work in mirrored networking mode. | confirmed | Microsoft WSL networking docs. [S4, S5] |
| Binding/security details of the existing FastAPI sidecar need repo/live verification before changing exposure. | speculative/repo-verification needed | Prompt says existing hook path works; implementation binding is not visible here. |
| Transcript open-tool detection is a valid cross-check using `tool_use` ids and matching `tool_result` blocks. | confirmed/plausible | Tool-use id matching is documented by Anthropic; exact Claude Code JSONL schema should be spiked. [S7] |
| `SubagentStart`/`SubagentStop` should not mark the parent session idle. | plausible | Derived from event semantics; verify with live subagent transcripts. [S1] |

## 5. Sources & citations

[S1] **Claude Code Docs - Hooks reference**. Official reference for hook events, configuration, HTTP hooks, common input fields, event-specific schemas, HTTP response handling, async hooks, and matcher behavior. Accessed 2026-07-02.  
https://code.claude.com/docs/en/hooks

[S2] **Claude Code Docs - Settings**. Official reference for hook configuration controls, including `allowedHttpHookUrls`, `httpHookAllowedEnvVars`, and managed hook behavior. Accessed 2026-07-02.  
https://code.claude.com/docs/en/settings

[S3] **Claude Code Docs - CLI reference**. Official reference for CLI flags including `--include-hook-events`, `--permission-mode`, and `--safe-mode`. Accessed 2026-07-02.  
https://code.claude.com/docs/en/cli-reference

[S4] **Microsoft Learn - Accessing network applications with WSL**. Official WSL networking guidance; documents default NAT behavior, retrieving the Windows host IP from inside WSL2 using the default route, and mirrored-mode localhost behavior. Accessed 2026-07-02.  
https://learn.microsoft.com/en-us/windows/wsl/networking

[S5] **Microsoft Learn - Basic commands for WSL**. Official WSL command reference; documents `ip route show | grep -i default | awk '{ print $3 }'` as returning the Windows machine IP as seen from WSL2. Accessed 2026-07-02.  
https://learn.microsoft.com/en-us/windows/wsl/basic-commands

[S6] **OpenBSD manual page - tmux(1)**. Manual reference for tmux sessions and `capture-pane`, including `-p` output to stdout and visible-pane capture behavior. Accessed 2026-07-02.  
https://man.openbsd.org/tmux

[S7] **Anthropic Platform Docs - Handle tool calls**. Official Claude tool-use reference; documents `tool_use` content blocks, unique tool-use ids, and corresponding `tool_result` blocks. Accessed 2026-07-02.  
https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls

## 6. Recommendation + fallback

### Recommendation

Adopt a push-based Claude Code HTTP-hook event stream as the **primary run-state signal when present and fresh**, not as a hard replacement for screen polling. [plausible]

Engineering plan:

1. **Generate hook config per launch.** [plausible] Re-resolve the WSL2 default-gateway IP per launch in NAT mode, keep a localhost option for mirrored mode, and write/register HTTP hooks using the documented shape: `type`, `url`, `timeout`, optional `headers`, and `allowedEnvVars`. [confirmed/plausible, S1, S4, S5]

2. **Register the core event set.** [plausible] Include `SessionStart`, `UserPromptSubmit`, `PreToolUse`, `PermissionRequest`, `PostToolUse`, `PostToolUseFailure`, `PostToolBatch`, `PermissionDenied`, `Stop`, `StopFailure`, `SessionEnd`, and supporting `Notification(permission_prompt|idle_prompt)`. Add `SubagentStart` and `SubagentStop` only if the UI wants subagent-level observability. [confirmed/plausible, S1]

3. **Keep the HTTP handler tiny.** [plausible] Authenticate with a per-launch bearer token, parse the JSON, attach `received_at` and per-agent `arrival_seq`, enqueue to the per-agent arbiter, and return immediately. Use a short timeout such as 1 second because HTTP hooks are not documented as async and defaults are too long for run-state plumbing. [confirmed/plausible, S1]

4. **Use a per-agent state arbiter.** [plausible] Merge events by `agent_id`, `launch_id`, `session_id`, `prompt_id`, `tool_use_id`, event phase, and received time. Track coarse state plus per-tool and per-subagent maps. Do not let late lower-phase events revert a terminal state for the same prompt. [plausible]

5. **Define state transitions conservatively.** [plausible]
   - `UserPromptSubmit` -> `generating`.
   - `PreToolUse` -> `generating/tool-running`, record `current_tool`.
   - `PermissionRequest` or `Notification(permission_prompt)` -> `permission-prompt`.
   - `PostToolUse` / `PostToolUseFailure` -> clear that tool id; remain `generating` until `Stop`, `StopFailure`, or fallback evidence says otherwise.
   - `PostToolBatch` -> all tools in the current batch resolved; move to `generating/model-request` rather than idle.
   - `Stop` -> `idle` if no background tasks/session crons; otherwise `background-running` or `scheduled`.
   - `StopFailure` -> `error` / `idle-with-error` depending UI vocabulary.
   - `SessionEnd` -> `ended`.

6. **Keep screen polling as a watchdog.** [plausible] While hooks are fresh, reduce but do not remove polling. When hooks are absent/stale/conflicting, return to the current ~1 second polling path. [confirmed/plausible: prompt constraint]

7. **Add transcript reconciliation.** [plausible] Tail JSONL using `transcript_path` when known. If transcript shows a `tool_use` id without a corresponding `tool_result`, keep the agent `generating` even if the screen classifier says idle or a late hook is missing. Use this as a cross-check, not the only source, until the exact installed transcript schema has been spiked. [confirmed/plausible, S1, S7]

8. **Instrument fallback reasons.** [plausible] Expose `hook_status`, `last_hook_event_at`, `last_hook_event_name`, `hook_events_seen`, `hook_drops`, `hook_parse_errors`, `fallback_reason`, and `state_source` (`hook`, `poll`, `transcript`, `merged`) in sidecar diagnostics. This makes the hybrid system debuggable.

9. **Run a required spike before declaring hooks authoritative.** [plausible]
   - Verify `/hooks` shows the generated HTTP hooks.
   - Capture real payloads for each registered event on the installed Claude Code version.
   - Verify `permission_mode`, `prompt_id`, `tool_use_id`, `background_tasks`, `session_crons`, and subagent fields where expected.
   - Force sidecar failure/timeouts and confirm Claude Code continues while dashboard falls back.
   - Trigger parallel tool calls and confirm `PostToolUse` concurrency plus `PostToolBatch` behavior.
   - Launch with hooks disabled/safe mode/gateway failure and confirm polling remains primary.

### Honest fallback if recommendation proves infeasible

If the spike shows HTTP hooks are too slow, blocked by policy/settings, missing critical payload fields, or unreliable under the tmux bridge, keep the current screen-polling classifier as the primary run-state signal and implement only two incremental hardening steps: [plausible]

1. Add transcript reconciliation for open `tool_use` ids without matching `tool_result` blocks, so generating-vs-idle is less dependent on screen text. [confirmed/plausible, S7]
2. Keep the already-proven hook subset (`PostToolUse`, `Stop`, and targeted `PreToolUse` for plan/decision cards) for safe-boundary context injection and UI cards, but do not promote hooks to authoritative run-state until the event stream is proven on the installed CLI build. [confirmed: prompt constraint; plausible recommendation]

Do not migrate the interactive coding agents to the Agent SDK or print-mode stream-json just to solve run-state. That would fight the stated architecture; the safe evolution is hook-first when fresh, polling/transcript as the always-on floor. [confirmed/plausible]
