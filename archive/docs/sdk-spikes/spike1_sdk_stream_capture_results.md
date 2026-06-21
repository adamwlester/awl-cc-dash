---
title: 'Spike 1: SDK Stream Capture Results'
date: 2026-04-03
tags: [testing, sdk, stream-json, spike]
---

# Spike 1: SDK Stream Capture Results

**Date:** 2026-04-03T01:50:56.661434
**Command:** `claude -p List the files in the current directory. Just show the output, nothing else. --output-format stream-json --verbose`
**Duration:** 16.82s
**Exit code:** 0
**Total events:** 16

## Event Type Breakdown

| Type | Count |
|------|-------|
| `assistant` | 2 |
| `rate_limit_event` | 1 |
| `result:success` | 1 |
| `system:hook_response` | 5 |
| `system:hook_started` | 5 |
| `system:init` | 1 |
| `user` | 1 |

## Event Timeline

| # | Time | Type | Size | Keys |
|---|------|------|------|------|
| 1 | 6.91s | `system:hook_started` | 252b | type, subtype, hook_id, hook_name, hook_event, uuid, session_id |
| 2 | 6.91s | `system:hook_started` | 252b | type, subtype, hook_id, hook_name, hook_event, uuid, session_id |
| 3 | 6.91s | `system:hook_started` | 252b | type, subtype, hook_id, hook_name, hook_event, uuid, session_id |
| 4 | 6.91s | `system:hook_started` | 252b | type, subtype, hook_id, hook_name, hook_event, uuid, session_id |
| 5 | 6.91s | `system:hook_started` | 252b | type, subtype, hook_id, hook_name, hook_event, uuid, session_id |
| 6 | 6.91s | `system:hook_response` | 323b | type, subtype, hook_id, hook_name, hook_event, output, stdout, stderr, exit_code, outcome, uuid, session_id |
| 7 | 6.91s | `system:hook_response` | 987b | type, subtype, hook_id, hook_name, hook_event, output, stdout, stderr, exit_code, outcome, uuid, session_id |
| 8 | 6.91s | `system:hook_response` | 2039b | type, subtype, hook_id, hook_name, hook_event, output, stdout, stderr, exit_code, outcome, uuid, session_id |
| 9 | 6.91s | `system:hook_response` | 13053b | type, subtype, hook_id, hook_name, hook_event, output, stdout, stderr, exit_code, outcome, uuid, session_id |
| 10 | 6.91s | `system:hook_response` | 945b | type, subtype, hook_id, hook_name, hook_event, output, stdout, stderr, exit_code, outcome, uuid, session_id |
| 11 | 8.02s | `system:init` | 13511b | type, subtype, cwd, session_id, tools, mcp_servers, model, permissionMode, slash_commands, apiKeySource, claude_code_version, output_style, agents, skills, plugins, uuid, fast_mode_state |
| 12 | 10.59s | `assistant` | 775b | type, message, parent_tool_use_id, session_id, uuid |
| 13 | 10.61s | `rate_limit_event` | 309b | type, rate_limit_info, uuid, session_id |
| 14 | 12.81s | `user` | 655b | type, message, parent_tool_use_id, session_id, uuid, timestamp, tool_use_result |
| 15 | 14.99s | `assistant` | 755b | type, message, parent_tool_use_id, session_id, uuid |
| 16 | 15.69s | `result:success` | 1054b | type, subtype, is_error, duration_ms, duration_api_ms, num_turns, result, stop_reason, session_id, total_cost_usd, usage, modelUsage, permission_denials, terminal_reason, fast_mode_state, uuid |

## Verdict

**PASS** — Full event stream captured. Assistant messages, tool use, and result with cost/usage all present.
