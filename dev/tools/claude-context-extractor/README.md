# claude-context-extractor

Two stdlib-only Python exporters that capture full Claude conversations — including the parts ordinary exporters drop (tool calls, tool results, thinking, citations, artifacts) — as clean Markdown, so external Claude context can be handed to another session.

| Script | Source | Access | Default output |
|--------|--------|--------|----------------|
| [`extract-web.py`](extract-web.py) | **claude.ai** (web) conversations | network + `sessionKey` cookie | `<repo>/transcripts/web/` |
| [`extract-desktop.py`](extract-desktop.py) | **Claude desktop app** local-agent-mode sessions | local disk only — no network, no auth | `<repo>/transcripts/desktop/` |

The third transcript surface, `<repo>/transcripts/cli/` (Claude Code CLI sessions), is not covered here — the **claude-history-viewer** VS Code extension exports those directly (its export dir is set in `.vscode/awl-cc-dash.code-workspace`).

Both scripts share one convention, matching that extension's filenames: exports are named `claude-<session-date>-<title-slug>` (lowercase slug, max 50 chars). A stats sidecar `<name>.summary.md` (message/tool/thinking counts, timing, token estimate) is written **only** when `--summary` is passed. Override the output folder with `--out <dir>`. The whole `transcripts/` tree is gitignored — personal data never gets committed.

When an export finishes, the readable transcript `.md` (and the `.summary.md`, when written) opens as a tab in your running VS Code window — via the `code` CLI, the same convenience the claude-history-viewer extension gives — so you can grab the path and read it immediately. The bulky raw `.source.json` and any artifacts folder are left closed. Pass `--no-open` to skip it (batch/headless runs); if `code` isn't on PATH the export still completes and just prints a "skipped auto-open" note.

## extract-desktop.py — desktop app sessions (no setup)

The desktop app runs "local agent mode" as a Claude Code session under the hood and stores each one on disk: a config JSON carrying the human-readable title, plus a standard Claude Code JSONL transcript. On the Microsoft Store (MSIX) build these live under the package container (`AppData\Local\Packages\Claude_...\LocalCache\Roaming\Claude\local-agent-mode-sessions`) — the script auto-detects that, so it just works. Run these from the repo root:

```
python dev/tools/claude-context-extractor/extract-desktop.py --list                                    # all sessions by title/date
python dev/tools/claude-context-extractor/extract-desktop.py --name "glossary-maintenance-strategy-1"  # export by title
python dev/tools/claude-context-extractor/extract-desktop.py --name "<title>" --summary                # + stats sidecar
python dev/tools/claude-context-extractor/extract-desktop.py --session local_62de1ffd-...              # export by session id
```

Escape hatches: `--no-open` skips opening the export in VS Code; `--root <dir>` if sessions live somewhere non-standard; `--transcript <file.jsonl>` (optionally + `--config <file.json>`) renders one transcript directly.

## extract-web.py — claude.ai conversations (needs your sessionKey)

### Your steps (this is all you do)
1. **Paste your claude.ai `sessionKey`** into [`session_key.txt`](session_key.txt) (replace the placeholder line).
   - Get it: open **claude.ai** (logged in) → press **F12** → **Application** tab → **Storage → Cookies → `https://claude.ai`** → click **`sessionKey`** → copy the **Value** (starts with `sk-ant-sid01-`). `document.cookie` won't show it — use the Cookies panel.
2. **Give Claude the conversation link** (`https://claude.ai/chat/…`) or its title, or just say "list them."
3. **Tell Claude to run it.** Done.

> The `sessionKey` is account-level access. `session_key.txt` is gitignored; delete it / log out of claude.ai when you're finished.

### Commands

Run these from the repo root (or `cd dev/tools/claude-context-extractor` first and drop the path prefix):

```
python dev/tools/claude-context-extractor/extract-web.py --list                             # list recent conversations
python dev/tools/claude-context-extractor/extract-web.py --name "Linting explained simply"  # export by title (substring, case-insensitive)
python dev/tools/claude-context-extractor/extract-web.py --name "<title>" --summary         # + stats sidecar
python dev/tools/claude-context-extractor/extract-web.py --conversation <url-or-uuid>       # export by URL / UUID
python dev/tools/claude-context-extractor/extract-web.py --resummarize <path>               # offline: (re)write a summary for an
                                                                                            #   existing export (.source.json or old dir) — no fetch

# options:
#   --tokens {heuristic,tiktoken,api}   summary token estimate (api = exact, free, needs ANTHROPIC_API_KEY)
#   --session-key <key>                 inline auth (else $CLAUDE_SESSION_KEY, else session_key.txt)
#   --org <org-uuid>                    override org auto-detect
#   --out <dir>                         output directory (default: <repo>/transcripts/web)
#   --no-open                           don't open the export in VS Code afterward (default: open it)
```

Each web export writes up to three siblings into the output folder:
- `claude-<date>-<slug>.md` — rendered transcript: text + thinking + tool_use + tool_result + citations.
- `claude-<date>-<slug>.source.json` — raw `chat_conversations` API response (source of truth, full fidelity).
- `claude-<date>-<slug>.artifacts/` — extracted documents / code / canvases (only when the chat has any).
- `claude-<date>-<slug>.summary.md` — only with `--summary`.

Notes for implementers:
- Auth: `Cookie: sessionKey=…`. Org UUID auto-resolves via `/api/organizations`; override with `--org`.
- Single-conversation fetch uses `?tree=True&rendering_mode=messages&render_all_tools=true`.
- Live-verified 2026-07-05 (`--list` + a full export ran clean against claude.ai); the desktop script is live-verified against the MSIX session store the same day.
