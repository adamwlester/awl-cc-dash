# claude-context-extractor

Pull a full **claude.ai** conversation (web or desktop) — including the parts ordinary
exporters drop (tool calls, tool results, citations, artifacts, branch tree) — and save it as
raw JSON + a clean Markdown transcript + extracted artifact files. Purpose: capture external
Claude context so it can be handed to another Claude session.

## Your steps (this is all you do)
1. **Paste your claude.ai `sessionKey`** into [`session_key.txt`](session_key.txt) (replace the
   placeholder line).
   - Get it: open **claude.ai** (logged in) → press **F12** → **Application** tab →
     **Storage → Cookies → `https://claude.ai`** → click **`sessionKey`** → copy the **Value**
     (starts with `sk-ant-sid01-`). `document.cookie` won't show it — use the Cookies panel.
2. **Give Claude the conversation link** (`https://claude.ai/chat/…`), or just say "list them."
3. **Tell Claude to run it.** Done.

> The `sessionKey` is account-level access. `session_key.txt` is gitignored; delete it / log out
> of claude.ai when you're finished.

## For Claude (the rest)
Stdlib only — no install. Run from this folder (`tools/claude-context-extractor/`):

```
python extract.py --list                           # list recent conversations
python extract.py --conversation <url-or-uuid>     # export by URL / UUID
python extract.py --name "<title>"                 # export by conversation title (substring, case-insensitive)
python extract.py --summary <dir-or-json>          # (offline) re-summarize an existing export — no fetch
python extract.py --conversation <uuid> --org <org-uuid>     # if org auto-detect is wrong

# options:
#   --tokens {heuristic,tiktoken,api}   token estimate (api = exact, free, needs ANTHROPIC_API_KEY)
#   --session-key <key>                 inline auth (else $CLAUDE_SESSION_KEY, else session_key.txt)
#   --out <dir>                         output directory (default: ./out)
```

Output lands in `out/<date>-<name>/` (or `--out`):
- `conversation.json` — raw `chat_conversations` API response (source of truth, full fidelity).
- `transcript.md` — rendered: text + thinking + tool_use + tool_result + citations.
- `summary.md` — turns, tools, thinking, models, timing, and a token estimate (auto-written).
- `artifacts/` — extracted documents / code / canvases.

Notes for implementers:
- Auth: `Cookie: sessionKey=…`. Org UUID auto-resolves via `/api/organizations`; override with `--org`.
- Single-conversation fetch uses `?tree=True&rendering_mode=messages&render_all_tools=true`.
- The exact API field names (`chat_messages`/`content`/`sender`) and artifact block shape should
  be **validated on the first live run** and the renderer adjusted if claude.ai differs.
