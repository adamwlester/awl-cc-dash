Diagnostic only. Do NOT build anything, do not edit any tracked repo file, do not install or upgrade anything, do not change global config. Your job is to drive the `bridge` package directly against the real WSL2/tmux environment, find out what actually works, and write one skim-able findings log to `.scratch`.

Setup: read the bridge section of `CLAUDE.md` and `bridge/README.md` first. Use the repo `.venv` and `from bridge import TmuxBridge`. Run ONE session at a time in a clean, empty, dedicated cwd (not WSL home, not a busy project dir) so transcript binding is unambiguous. For the streaming checks, launch with permissions bypassed (via `claude_args`) so turns complete unattended; for check 5 only, launch in default prompting mode to deliberately trigger an approval. Keep every prompt benign and confined to the throwaway dir. Close every tmux session you create when done.

Work the checks in order. Check 1 is a HARD GATE: if it fails, stop, write what you found, and report back rather than improvising fixes.

1. Binary + live turn (GATE). First verify, directly in WSL, that the binary the bridge launches actually exists and runs: compare `CLAUDE_BIN` in `bridge/paths.py` (currently `/home/lester/.local/bin/claude`) against `command -v claude` and `claude --version`, and report the real resolved absolute path if it differs. Then create a session, wait for idle, send "reply with the single word PONG", and confirm a JSONL transcript appears and `read_log` returns an assistant entry. No binary or no transcript = gate failed.

2. Content shape. After a richer turn (ask it to read one file and run one shell command), confirm `read_log` carries typed content blocks: `text`, `thinking`, `tool_use`, `tool_result`. Note any block type missing or shaped unexpectedly.

3. Run-state detection. Around that turn, poll `status()` and report whether `state` reliably moves idle to generating to idle, how laggy or flickery it is, and any premature-idle or stuck-generating behavior.

4. Slash command landing (KEYSTONE). Send `/context` as a prompt and report exactly what happens: does it run, or does the TUI slash autocomplete intercept the keystrokes? Capture the rendered output and report whether a per-category breakdown (system prompt, tools, MCP, messages, free) is present and scrapeable.

5. Permission / blocked state (HIGHEST VALUE). In default prompting mode, send a prompt that needs an approval-gated tool (a benign shell command in the throwaway dir). Report three things: does `status()` return `permission_prompt`; what detail is visible on the captured screen (which tool, which command, the menu options); and can you ANSWER it programmatically via `keys()` (the prompt is a menu, work out the right keypress) for both approve and, on a fresh prompt, deny.

6. Context % + turns from transcript. Confirm whether assistant entries carry `message.usage` token counts (so overall context % is derivable without `/context`) and that a turn count is derivable from the entries. Report the `usage` shape and a sample derived context %.

7. Crash-recovery capability. Create a session, send a turn, then construct a SECOND `TmuxBridge()` instance (simulating a sidecar restart) and call `resume(name)` + `read_log` + `status` on it. Confirm a fresh process reconnects and still sees the transcript and state.

8. OPTIONAL (only if 1 to 7 pass and it is quick): trigger a subagent and report whether `read_log` surfaces sidechain entries (e.g. an `isSidechain` flag) that distinguish child activity.

Write findings to `.scratch/bridge-diagnostic-<timestamp>.md` in a skim-first format: a one-line bottom-line verdict at the very top, then a compact table of the checks with PASS / PARTIAL / FAIL and a one-to-two line finding each, then a short "implications for the probe" paragraph. Put any raw screen captures or transcript excerpts in a clearly separated appendix at the bottom, never inline, so the top of the file stays readable. This writes only to `.scratch` and changes no tracked files, so no DEVLOG entry is needed.