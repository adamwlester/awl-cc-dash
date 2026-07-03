# s10-research-15-rewind-handoff.md

Sources checked on 2026-07-02. Confidence tags use: **[confirmed]** = documented by official source or directly implied by documented behavior; **[plausible]** = reasonable inference from documented mechanisms but needs a live spike; **[speculative]** = unofficial, undocumented, or version-fragile.

## 1. Restated question

The dashboard needs to know whether a Claude Code conversation can be manipulated at a selected Timeline point **N**, where the Timeline is the ordered conversation/message history sent to the model, not just file state.

For **Rewind (A)**, the target behavior is: take an existing Claude Code session, discard or hide conversation after message/prompt **N**, and continue the same agent from that earlier point.

For **Fork / Handoff (B)**, the target behavior is: create a new Claude Code agent/session whose conversation context is the source session's prefix through **N**, then allow it to diverge independently while the original session remains intact.

The dashboard's normal control surface is a detached **tmux + Claude Code TUI** session in WSL2, with `<session-id>.jsonl` treated as the master record and whole-session resume done today with `claude --resume <session-id>`. The main question is not whether whole-session resume works; it is whether resume/fork can target an earlier point and whether that can be automated safely.

## 2. Options considered

### Option 1 — Transcript-file surgery + `claude --resume`

**Serves:** rewind and fork, in theory.

Concrete idea:

- Rewind: copy the original `<session-id>.jsonl` to a backup, truncate the active transcript after the chosen Timeline boundary, then run `claude --resume <same-session-id>`.
- Fork: copy the source transcript to a new `<new-session-id>.jsonl`, truncate it after **N**, edit embedded session/message metadata if needed, then run `claude --resume <new-session-id>` or `claude --session-id <new-session-id>`.

Findings:

- Claude Code transcripts are documented as JSONL files under `~/.claude/projects/<project>/<session-id>.jsonl`, with one JSON object per line for messages, tool calls, and metadata. **[confirmed]** [S1]
- Anthropic explicitly warns that the transcript format is internal and may change between versions; direct parsers can break, and `/export` or script interfaces are preferred for stable integrations. **[confirmed]** [S1]
- The Agent SDK's storage docs state that `forkSession` is **not** a byte-for-byte copy: it reads source entries, rewrites every `sessionId`, and remaps UUIDs. Adapter-level copying would leave old session IDs embedded. **[confirmed]** [S9]
- Tool-use integrity matters. Anthropic's tool-use protocol requires a `tool_result` to correspond to a prior `tool_use`; results must appear in the required order, and missing/improperly ordered tool results can cause request errors. A raw transcript cut between `tool_use` and `tool_result` is therefore unsafe. **[confirmed]** [S10]
- A manual cut might work if it lands on a complete, valid turn boundary and preserves all required metadata, compaction records, session IDs, parent UUID chains, subagent transcript references, and checkpoint records. **[plausible — needs live spike]**
- There is no official documentation saying `claude --resume` accepts a manually modified or hand-copied transcript as a supported operation. **[confirmed absence in checked docs; needs live spike before reliance]** [S1] [S3]

Assessment: transcript surgery should **not** be the load-bearing mechanism. It is likely the riskiest option because Claude Code now exposes supported rewind/fork controls, and official docs warn against depending on raw transcript internals.

### Option 2 — Native Claude Code CLI/TUI resume, branch, fork, and rewind semantics

**Serves:** rewind and fork; strongest match to the tmux/TUI architecture, but with automation caveats.

Concrete mechanisms:

- `/rewind` or `/checkpoint` in the TUI.
- `/branch [name]` in the TUI.
- `claude --continue --fork-session` or `claude --resume <session-id> --fork-session` from the CLI.
- `claude --resume <session-id>` / `claude --continue` for whole-session resume.

Findings:

- Claude Code documents session management commands for resume and branching. Sessions are saved automatically and can be resumed by `--continue`, `--resume`, and `/resume`. **[confirmed]** [S1] [S3]
- `--fork-session` is an official CLI flag: when resuming, it creates a new session ID instead of reusing the original; docs show `claude --resume abc123 --fork-session`. **[confirmed]** [S3]
- `/branch [name]` is an official TUI command that creates a branch of the current conversation at the current point, switches into that branch, and preserves the original. **[confirmed]** [S4]
- The sessions docs state that session picker groups include forked sessions created by `/branch`, `/rewind`, or `--fork-session`; the original session remains unchanged. **[confirmed]** [S1]
- `/rewind` is now officially documented as a checkpointing feature. Every user prompt creates a checkpoint. The rewind menu lists prompts and provides actions to restore code plus conversation, conversation only, code only, or summarize from/up to that point. **[confirmed]** [S2]
- `/rewind` explicitly can restore **conversation** state, not merely file/code state. After restoring conversation, the original selected prompt is restored into the input field for the user to resend or edit. **[confirmed]** [S2]
- `/rewind` can also restore code, but its file-tracking has limits: Bash changes and external changes are not tracked, and checkpointing is not a replacement for git. **[confirmed]** [S2]
- Checkpointing persists across sessions and retains recent checkpoints. **[confirmed]** [S2]
- Rewinding past `/clear` requires Claude Code v2.1.191 or later. **[confirmed; version-sensitive]** [S2]
- `/rewind` appears to be an interactive TUI menu, not a documented non-interactive CLI flag in the public CLI reference. **[confirmed as to docs checked; needs live spike for automation]** [S2] [S3]
- A native, tmux-compatible fork-from-N can likely be implemented as: first create a full fork with `claude --resume <source-id> --fork-session`, then drive `/rewind` inside the new fork to the desired checkpoint and choose “Restore conversation” or “Restore code and conversation.” Original remains intact because the rewind happens in the fork. **[plausible — needs live spike]**
- This TUI-native approach depends on reliably driving the interactive rewind picker over tmux, or adding a sidecar affordance that sends slash commands and key sequences. It is therefore useful but automation-fragile until tested. **[plausible — needs live spike]**

Assessment: native Claude Code controls are the best fit for a product that already operates through tmux/TUI. The big open risk is not capability existence; it is whether the dashboard can drive the interactive rewind menu robustly enough from outside the TUI.

### Option 3 — Claude Agent SDK session forking / resume-at-message

**Serves:** fork strongly; rewind as an SDK-mediated exception; potentially the cleanest non-interactive historical fork.

Concrete mechanisms:

- Use the TypeScript Agent SDK to inspect persisted messages with `getSessionMessages(sessionId)`.
- Choose a message UUID corresponding to Timeline point **N**.
- Invoke `query()` with `resume: <source-session-id>`, `resumeSessionAt: <message-uuid>`, and `forkSession: true`.
- Capture the new forked session ID from the SDK result, then return to the normal TUI path with `claude --resume <new-session-id>`.

Findings:

- The Agent SDK session docs say sessions persist conversation history: prompts, tool calls, tool results, and responses. They do not include filesystem state; file checkpointing is separate. **[confirmed]** [S5]
- The SDK officially documents `continue`, `resume`, and `fork` session options. Forking creates a new session with a copy of the original history and leaves the original unchanged. **[confirmed]** [S5]
- TypeScript Agent SDK reference includes `forkSession`, `resume`, `sessionId`, and crucially `resumeSessionAt`, described as “Resume session at a specific message UUID.” **[confirmed]** [S6]
- TypeScript Agent SDK reference also provides `getSessionMessages(sessionId)` and `SessionMessage.uuid`, which gives a documented way to map Timeline entries to message UUIDs without scraping raw JSONL. **[confirmed]** [S6]
- Python Agent SDK docs include `fork_session` and `get_session_messages()`, but the checked Python reference does not document an equivalent `resume_session_at` option. **[confirmed as to docs checked; version-sensitive]** [S7]
- SDK forking branches conversation history, not filesystem state. If the fork shares the same working directory, file edits made by either session are visible to the other unless code state is separately checkpointed or the fork uses a separate worktree/directory. **[confirmed]** [S5] [S8]
- A TypeScript SDK call with `resumeSessionAt + forkSession` is the most promising non-interactive mechanism for branch-from-N. It avoids transcript byte surgery and lets Claude Code/SDK preserve internal tool/result/session invariants. **[plausible — needs live spike]**
- It is not yet confirmed that an SDK-created fork can always be resumed later by the normal Claude Code TUI with `claude --resume <new-session-id>` in the exact same way as a TUI-created fork, although the shared session model and documented session storage make this likely. **[plausible — needs live spike]** [S1] [S5] [S9]
- It is not yet confirmed whether the SDK can create a “pure” branch without adding an initial prompt/turn. A practical Handoff flow may need to treat the handoff instruction itself as the first divergent turn in the new branch. **[plausible — needs live spike]**

Assessment: this is the best candidate for a non-interactive, arbitrary-point fork. It violates the dashboard's preferred tmux-only path, but only as a targeted session-construction step; after the fork exists, the new agent can return to the normal `claude --resume <new-id>` TUI path.

### Option 4 — Reconstruct-and-replay / seed a fresh session with prefix context

**Serves:** approximate fork only; approximate rewind if used to replace the original.

Concrete mechanisms:

- Start a fresh Claude Code session with a new pinned session ID.
- Feed a summary or exported prefix of messages 1..N as initial context, for example as a system/developer preamble or first prompt.
- Optionally include relevant file diffs, current worktree state, and the selected handoff instruction.

Findings:

- This is not true resume. It does not preserve the exact internal conversation chain, message UUIDs, compaction state, hidden metadata, cache state, or tool-use/tool-result chronology. **[confirmed by contrast with SDK/session docs]** [S1] [S5]
- It may be good enough for a “handoff with context” feature if the UI labels it as an approximation, especially if the selected prefix is summarized and paired with a git worktree/diff snapshot. **[plausible]**
- It can be expensive in tokens if the prefix is replayed verbatim, and lossy if summarized. **[confirmed general consequence of prompt seeding; exact cost needs measurement]**
- It avoids reliance on version-fragile transcript internals and can run entirely through the current tmux/TUI launch path. **[confirmed]**

Assessment: this is the fallback if exact branch-from-N cannot be automated reliably. It should not be called a true fork.

### Option 5 — Other mechanisms and adjacent features

**Serves:** mostly clarifies non-solutions.

Findings:

- Claude Code file checkpointing and Agent SDK file checkpointing can rewind files, but file rewind does **not** by itself rewind conversation. SDK docs explicitly state that after file rewind, conversation history/context remains. **[confirmed]** [S8]
- `claude -p --resume <session-id> --rewind-files <checkpoint-uuid>` is documented for file-only checkpoint restore in SDK contexts. It is useful for code state, not for conversation prefix selection. **[confirmed]** [S8]
- `/fork <directive>` is not the same as Handoff branch. Current docs describe it as spawning a background subagent with full conversation; `/branch` is the command for switching into a conversation copy. Before v2.1.161, `/fork` was an alias for `/branch`, so its meaning is version-sensitive. **[confirmed; version-sensitive]** [S4]
- The Claude Code VS Code extension exposes message-level hover actions such as “Fork conversation from here,” “Rewind code to here,” and “Fork conversation and rewind code.” This confirms that Claude Code has message-level branch semantics in at least one UI, but that UI path is not directly usable by a tmux sidecar. **[confirmed; adjacent only]** [S11]
- Unofficial references mention a hidden CLI flag named `--resume-session-at <message-id>` and GitHub issues discuss `resumeSessionAt` gaps across SDK versions. These are useful hints for a spike but should not be load-bearing because they are not in the checked official CLI reference. **[speculative]** [S12] [S13]
- There are local session files beyond the single transcript in practice, especially subagent transcript paths and storage adapter/subkey behavior. Official storage docs mention subagent transcripts stored under subpaths and warn that custom stores must support listing subkeys for resume. **[confirmed]** [S9]

Assessment: the only “other” mechanism worth watching is an official future CLI flag for resume-at-message. Today, the supported choices are TUI `/rewind`/`/branch`/`--fork-session` and SDK `resumeSessionAt`/`forkSession`; file-only checkpointing is not sufficient.

## 3. Trade-offs

| Option | Costs | Where it breaks | Assumptions |
|---|---|---|---|
| Transcript surgery + `--resume` | Engineering effort to parse and mutate internal JSONL; backup/restore; risk of corrupting user session. | Internal format changes; embedded session IDs and UUIDs; tool-use/tool-result pairing; compaction/summarization records; subagent paths; checkpoint metadata; unknown validation/repair behavior. | Assumes `claude --resume` accepts modified transcripts and that safe cut boundaries can be detected. **[speculative / needs live spike]** |
| Native `/rewind` | Fits current tmux/TUI architecture; no SDK exception; uses official Claude Code behavior. | Rewind menu is interactive; external automation may be brittle; prompt/checkpoint mapping must be recovered from UI or transcript; version gates such as v2.1.191 for rewind past `/clear`. | Assumes the sidecar can reliably drive slash command + menu selection in a detached tmux session. **[plausible / needs live spike]** |
| Native `/branch` / `--fork-session` | Official way to preserve original and create a new session ID; clean for branch at current/end point. | `--fork-session` alone forks the current/full resume point, not an arbitrary historical point; `/branch` branches “current conversation at this point,” so historical branch needs either prior `/rewind` in a copy or SDK resume-at-message. | Assumes full-session fork plus rewind-in-fork yields correct branch-from-N. **[plausible / needs live spike]** |
| TypeScript SDK `resumeSessionAt + forkSession` | Deliberate exception to tmux path; requires SDK invocation, version pinning, and mapping dashboard Timeline entries to SDK message UUIDs. | May add a new initial prompt; exact allowed UUID boundary semantics need test; working directory/file state is not forked; Python SDK docs do not expose same option. | Assumes SDK-created session can be resumed normally by Claude Code TUI and that `resumeSessionAt` behaves as a prefix cut. **[plausible / needs live spike]** |
| Reconstruct-and-replay | Lowest implementation risk; works with fresh tmux/TUI session; no internal transcript writes. | Not exact; loses tool state, message UUID lineage, hidden/transient state, original compaction chain, and maybe fidelity of earlier reasoning; token-expensive. | Assumes product can honestly label it as “context handoff,” not true fork. **[confirmed limitation / plausible product fallback]** |
| File checkpointing / `--rewind-files` | Useful for code state coordination; may combine with conversation branching if separate worktrees/checkpoints are used. | Does not rewind conversation; Bash/external changes not tracked; same working directory can create cross-session file interference. | Assumes file state is independently managed with git/worktrees or Claude Code checkpoint constraints. **[confirmed]** |

Important boundary rule: any manual or SDK-assisted historical selection should select **complete message/turn boundaries**, not raw JSONL lines. For raw surgery, never cut between an assistant `tool_use` and the required `tool_result`. For SDK/TUI routes, prefer official message UUIDs or checkpoint menu entries because the runtime is more likely to maintain those invariants. **[confirmed for tool pairing; plausible for implementation details]** [S6] [S10]

## 4. Per-finding confidence

| # | Finding | Confidence | Needs live spike / repo check? |
|---|---|---:|---|
| 1 | Claude Code persists sessions in JSONL files under `~/.claude/projects/.../<session-id>.jsonl`. | **confirmed** | Repo check only to confirm dashboard's exact transcript path resolver. |
| 2 | Whole-session resume via `--resume`, `--continue`, and `/resume` is documented. | **confirmed** | No. |
| 3 | `--fork-session` is an official CLI flag that creates a new session ID when resuming. | **confirmed** | Spike recommended to verify captured new ID and exact terminal behavior under tmux. |
| 4 | `/branch` creates a branch of the current conversation and preserves the original. | **confirmed** | Spike recommended for tmux automation and session-ID capture. |
| 5 | `/rewind` can restore conversation state, code state, or both to a previous prompt checkpoint. | **confirmed** | Spike required for menu automation and for exact transcript/session artifacts after restore. |
| 6 | `/rewind` is not merely file rewind; it explicitly includes conversation restore. | **confirmed** | No, except version pin verification in the product environment. |
| 7 | File checkpointing alone does not rewind conversation; conversation context remains after file rewind in SDK docs. | **confirmed** | No. |
| 8 | `forkSession` in SDK branches conversation history but not filesystem state. | **confirmed** | Need product check for worktree isolation strategy. |
| 9 | TypeScript SDK exposes `resumeSessionAt`, “resume session at a specific message UUID.” | **confirmed** | Spike required to verify behavior with Claude Code sessions created by TUI and subsequent TUI resume. |
| 10 | TypeScript SDK exposes `getSessionMessages` and message UUIDs for mapping timeline points to resume targets. | **confirmed** | Need product check to map dashboard Timeline entries to SDK message UUIDs robustly. |
| 11 | Python SDK docs checked do not expose `resume_session_at`; they do expose `fork_session`. | **confirmed as of checked docs** | Version-sensitive; re-check before implementation if using Python SDK. |
| 12 | Manual JSONL truncation/copy is unsupported and fragile. | **confirmed for fragility warning; speculative for exact failure modes** | Yes, only if team still wants to evaluate it. |
| 13 | Manual transcript truncation may work if cut on safe boundaries and metadata is preserved. | **speculative** | Yes; do not rely without an isolated spike. |
| 14 | Best TUI-native branch-from-N is full fork first, then `/rewind` inside the fork. | **plausible** | Yes; this is the main native spike. |
| 15 | Best non-interactive branch-from-N is TypeScript SDK `resumeSessionAt + forkSession`, then `claude --resume <new-id>` in tmux. | **plausible** | Yes; this is the main SDK-exception spike. |
| 16 | A hidden CLI `--resume-session-at` may exist. | **speculative** | Yes; do not use as load-bearing until official docs or local `claude --help`/behavior confirm. |
| 17 | Reconstruct-and-replay is only an approximation, not a true fork or rewind. | **confirmed** | No, though quality needs product testing. |
| 18 | VS Code extension has message-level fork/rewind affordances, confirming product-level semantics but not giving the tmux sidecar a direct control path. | **confirmed** | No, unless considering an extension-based architecture, which is out of scope. |

## 5. Sources & citations

[S1] **Anthropic Claude Code docs — Manage sessions.** Documents resume, branch/fork behavior, session grouping, transcript location, JSONL format, and warning that transcript internals can change. Accessed 2026-07-02.  
https://code.claude.com/docs/en/sessions

[S2] **Anthropic Claude Code docs — Checkpointing.** Documents `/rewind`, checkpoint creation at each user prompt, restore code/conversation options, version note for rewind past `/clear`, and checkpoint limitations. Accessed 2026-07-02.  
https://code.claude.com/docs/en/checkpointing

[S3] **Anthropic Claude Code docs — CLI reference.** Documents `--continue`, `--resume`, `--session-id`, and `--fork-session`; also notes `claude --help` may not list every flag. Accessed 2026-07-02.  
https://code.claude.com/docs/en/cli-reference

[S4] **Anthropic Claude Code docs — Slash commands.** Documents `/branch`, `/fork`, `/resume`, and `/rewind`, including version-sensitive `/fork` behavior. Accessed 2026-07-02.  
https://code.claude.com/docs/en/commands

[S5] **Anthropic Claude Agent SDK docs — Manage sessions.** Documents SDK session contents, resume/fork behavior, conversation-vs-filesystem distinction, and `fork_session` semantics. Accessed 2026-07-02.  
https://code.claude.com/docs/en/agent-sdk/sessions

[S6] **Anthropic Claude Agent SDK docs — TypeScript SDK reference.** Documents `getSessionMessages`, `SessionMessage.uuid`, `forkSession`, `resume`, `sessionId`, and `resumeSessionAt`. Accessed 2026-07-02.  
https://code.claude.com/docs/en/agent-sdk/typescript

[S7] **Anthropic Claude Agent SDK docs — Python SDK reference.** Documents Python `get_session_messages()` and `fork_session`; checked reference did not show a Python `resume_session_at` equivalent. Accessed 2026-07-02.  
https://code.claude.com/docs/en/agent-sdk/python

[S8] **Anthropic Claude Agent SDK docs — File checkpointing.** Documents file-only rewind behavior, `--rewind-files`, and explicitly says file rewind does not rewind conversation. Accessed 2026-07-02.  
https://code.claude.com/docs/en/agent-sdk/file-checkpointing

[S9] **Anthropic Claude Agent SDK docs — Session storage.** Documents JSONL/session-store persistence, opaque entry handling, dual-write behavior, and that SDK `forkSession` rewrites session IDs and remaps UUIDs rather than byte-copying sessions. Accessed 2026-07-02.  
https://code.claude.com/docs/en/agent-sdk/session-storage

[S10] **Anthropic API docs — Handle tool calls.** Documents `tool_use` / `tool_result` matching and ordering constraints; relevant to transcript surgery safety. Accessed 2026-07-02.  
https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls

[S11] **Anthropic Claude Code docs — VS Code extension.** Documents message-level UI actions such as forking conversation from a message and rewinding code. Adjacent evidence only; not a tmux control path. Accessed 2026-07-02.  
https://code.claude.com/docs/en/vs-code

[S12] **GitHub issue — anthropics/claude-agent-sdk-python #690, “Session `resume_at` support.”** Unofficial/user-submitted discussion indicating CLI may have hidden `--resume-session-at` and Python SDK lacks parity. Use only as a spike hint. Accessed 2026-07-02.  
https://github.com/anthropics/claude-agent-sdk-python/issues/690

[S13] **Unofficial gist of Claude Code hidden CLI flags.** Mentions `--resume-session-at` and other hidden flags. Use only as a spike hint; not official documentation. Accessed 2026-07-02.  
https://gist.github.com/johnlindquist/b2207ac2cc1a8fdcf5e08d30676c3e52

## 6. Verdict + recommendation + fallback

### Rewind (A): **PARTIAL YES**

A true conversation rewind mechanism exists in current Claude Code: `/rewind` can restore conversation state to a previous prompt checkpoint, and can optionally restore code state too. **[confirmed]** [S2] [S4]

However, for awl-cc-dash, this is only a **partial yes** because the documented mechanism is an interactive TUI menu. The dashboard can probably drive it over tmux, but that must be verified. There is no checked official CLI flag equivalent to “resume this same session at message UUID N” in the public CLI reference. **[confirmed as to docs checked; automation needs live spike]** [S2] [S3]

Recommended rewind spike:

1. In WSL2, create a disposable test project and launch a pinned Claude Code TUI session:
   ```bash
   claude --session-id s10-rewind-test
   ```
2. Send three prompts that create distinguishable conversation checkpoints and at least one file edit, for example:
   - Prompt 1: create `a.txt` with `A1`.
   - Prompt 2: create `b.txt` with `B1`.
   - Prompt 3: explain both files and add `c.txt`.
3. Confirm the transcript path exists under `~/.claude/projects/.../s10-rewind-test.jsonl`.
4. From the same tmux-driving code path the dashboard uses, send:
   ```text
   /rewind
   ```
5. Select the Prompt 2 checkpoint and choose **Restore conversation** first. Observe:
   - whether the selected prompt is restored into the TUI input field;
   - whether Prompt 3 is absent from the active model context after continuing;
   - whether the transcript receives new branch/rewind records or preserves old lines as history;
   - whether `claude --resume s10-rewind-test` resumes the rewound conversation state or the full original tail.
6. Repeat with **Restore code and conversation**. Observe:
   - whether `c.txt` is removed/restored as expected;
   - whether Bash/external changes remain untracked as documented;
   - whether the dashboard can distinguish conversation-only versus code+conversation choices.
7. Pin the tested Claude Code minimum version. Require at least v2.1.191 if rewinding across `/clear` matters.

Implementation recommendation for Rewind:

- Prefer native `/rewind` if tmux automation is reliable enough.
- Do **not** implement same-session rewind by raw JSONL truncation except as an isolated experimental fallback.
- Add a product-level constraint: rewind targets should be prompt/checkpoint boundaries, not arbitrary raw transcript lines.

### Fork / Handoff (B): **PARTIAL YES, with two viable spike paths**

A native branch/fork mechanism exists: `/branch` and `--fork-session` create new sessions and leave the original unchanged. **[confirmed]** [S1] [S3] [S4]

For branch-from-an-arbitrary-past-Timeline-point **N**, the answer is **partial yes** because the best documented non-interactive primitive is in the **TypeScript Agent SDK**, not the main TUI path. The best native TUI approximation is to fork first and then rewind the fork. Both require a live spike before product reliance.

#### Most promising path 1: native tmux/TUI full-fork then rewind-in-fork

Spike steps:

1. Start with the source session ID, for example `SOURCE=s10-source`.
2. Create a new full fork:
   ```bash
   claude --resume "$SOURCE" --fork-session
   ```
3. Capture the new session ID from terminal output, transcript discovery, or session picker grouping.
4. Attach/control the new forked TUI in its own tmux session.
5. Run `/rewind` inside the **fork**, select Timeline point **N**, and choose **Restore conversation** or **Restore code and conversation**.
6. Resume both source and fork and verify:
   - the source transcript/context remains unchanged;
   - the fork has context only through **N** after the rewind;
   - later source prompts do not influence the fork;
   - the sidecar can resolve the fork's new `<session-id>.jsonl` path;
   - session grouping in `/resume` shows the source/fork relationship.

Why this is attractive:

- It stays on the official Claude Code TUI/CLI path.
- It avoids transcript surgery.
- It uses documented `/rewind` and `--fork-session` behavior.

Main risk:

- It requires robust automation of an interactive rewind picker from outside the TUI.

#### Most promising path 2: TypeScript SDK `resumeSessionAt + forkSession`, then return to TUI

Spike steps:

1. Use TypeScript SDK `getSessionMessages(sourceSessionId)` to fetch official message UUIDs.
2. Map dashboard Timeline point **N** to a `SessionMessage.uuid`. Prefer user-prompt or complete assistant-message boundaries; do not map to raw JSONL lines.
3. Run an SDK query with `resume`, `resumeSessionAt`, and `forkSession`. Treat the first handoff instruction as the branch's first divergent turn unless a pure zero-turn creation mode is proven.

   Example shape to test, not production code:

   ```ts
   import { query, getSessionMessages } from "@anthropic-ai/claude-agent-sdk";

   const sourceSessionId = process.argv[2];
   const targetIndex = Number(process.argv[3]);
   const messages = await getSessionMessages(sourceSessionId, { dir: process.cwd(), limit: 1000 });
   const targetUuid = messages[targetIndex].uuid;

   let forkedSessionId: string | undefined;

   for await (const msg of query({
     prompt: "You are a handoff branch created from the selected earlier point. Continue from here.",
     options: {
       cwd: process.cwd(),
       resume: sourceSessionId,
       resumeSessionAt: targetUuid,
       forkSession: true,
       systemPrompt: { type: "preset", preset: "claude_code" },
       settingSources: ["user", "project", "local"],
       maxTurns: 1
     }
   })) {
     if (msg.type === "result") forkedSessionId = msg.session_id;
   }

   console.log(forkedSessionId);
   ```

4. Launch the normal TUI path on the captured fork:
   ```bash
   claude --resume "$FORKED_SESSION_ID"
   ```
5. Verify:
   - source remains unchanged;
   - fork transcript/session ID is independently resumable by CLI/TUI;
   - context after target UUID excludes later messages;
   - file state behavior is acceptable or explicitly managed via a separate git worktree/checkpoint;
   - permissions and settings match product expectations, since some docs note permissions do not carry over for forked sessions.

Why this is attractive:

- It is the cleanest non-interactive historical branch candidate.
- It uses documented SDK fields instead of editing JSONL internals.
- It can be isolated to one “construct branch session” operation, after which the dashboard can return to tmux/TUI.

Main risk:

- It is an SDK exception and must be version-pinned/tested. Exact semantics of `resumeSessionAt` with TUI-created Claude Code sessions, and whether a no-new-turn branch can be created, need a live spike.

### Honest fallback if exact Rewind/Fork cannot be automated reliably

If tmux automation of `/rewind` is brittle and the SDK route fails to produce TUI-resumable sessions, cut “true rewind/fork” from the first version and ship an explicitly labeled approximation:

- **Resume original:** keep existing whole-session `claude --resume <session-id>` only.
- **Context handoff:** create a fresh agent/session and seed it with a generated summary or exported prefix through **N**, plus current file diffs and operator instructions.
- **File state:** use git worktrees or explicit checkpoint/file-restore workflows rather than relying on conversation history to imply file state.
- **UI copy:** call it “Create new agent with context up to this point,” not “fork,” unless true session prefix carry is verified.

Final recommendation:

1. **Do not build transcript surgery as the primary path.** It is unsupported and fragile.
2. **Spike native full-fork then `/rewind` first** because it best matches the current tmux architecture and uses official CLI/TUI features.
3. **Spike TypeScript SDK `resumeSessionAt + forkSession` second** as the likely best non-interactive solution for Handoff branch-from-N.
4. **Require separate file-state policy** for Handoff. Conversation fork does not automatically isolate filesystem state; use git worktrees, dashboard-managed copies, or explicit code checkpoint restore depending on desired UX.
