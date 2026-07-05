#!/usr/bin/env python3
"""extract-web.py — export a full claude.ai (web) conversation to Markdown.

Pulls a conversation from claude.ai's internal API — including the parts ordinary exporters
drop (tool calls, tool results, thinking, citations, artifacts) — using your logged-in
`sessionKey` cookie (see README for how to grab it). Network + auth required; this is the
cloud-side sibling of extract-desktop.py (which reads the desktop app's local sessions).

Exports land in `<repo>/transcripts/web/` by default (override with --out), named to match
the claude-history-viewer extension's convention, `claude-<conversation-date>-<title-slug>`:
    claude-<date>-<slug>.md             rendered transcript (text + thinking + tools + citations)
    claude-<date>-<slug>.source.json    raw API response (full fidelity, source of truth)
    claude-<date>-<slug>.artifacts/     extracted artifact files (only when the chat has any)
    claude-<date>-<slug>.summary.md     stats sidecar — only when --summary is passed

Usage (stdlib only — any Python 3.9+, no venv needed; run from this folder or anywhere):
    python extract-web.py --list
    python extract-web.py --name "Linting explained simply"
    python extract-web.py --name "Linting explained simply" --summary
    python extract-web.py --conversation https://claude.ai/chat/<uuid>
    python extract-web.py --name "..." --out C:\\somewhere\\else

Extras:
    --tokens {heuristic,tiktoken,api}   summary token-estimate method (api = exact, free,
                                        needs ANTHROPIC_API_KEY); only used with --summary
    --resummarize <path>                offline: (re)write the .summary.md for an existing
                                        export (.source.json file, or an old-format export
                                        dir containing conversation.json) — no fetch, no key
    --org <uuid>                        override the auto-detected organization
    --session-key <key>                 inline auth (else $CLAUDE_SESSION_KEY, else session_key.txt)
"""

from __future__ import annotations   # keep `X | None` annotations working on Python 3.9

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = "https://claude.ai/api"
HERE = Path(__file__).resolve().parent
KEY_FILE = HERE / "session_key.txt"

# This file lives at <repo>/dev/tools/claude-context-extractor/, so the repo root is 3 up.
# If the script is copied somewhere shallower, fall back to CWD instead of crashing at import.
try:
    REPO_ROOT = Path(__file__).resolve().parents[3]
except IndexError:
    REPO_ROOT = Path.cwd()
DEFAULT_OUT = REPO_ROOT / "transcripts" / "web"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


def load_key(cli_key: str | None = None) -> str:
    key = (cli_key or "").strip() or os.environ.get("CLAUDE_SESSION_KEY", "").strip()
    if not key and KEY_FILE.exists():
        key = KEY_FILE.read_text(encoding="utf-8").strip()
    if not key or "REPLACE-ME" in key:
        sys.exit("No sessionKey found. Pass --session-key, set CLAUDE_SESSION_KEY, or paste it into session_key.txt.")
    if key.startswith("sessionKey="):           # tolerate a pasted "sessionKey=sk-ant-..." form
        key = key.split("=", 1)[1]
    return key


def api_get(path: str, key: str):
    url = path if path.startswith("http") else f"{BASE}{path}"
    req = urllib.request.Request(url, headers={
        "Cookie": f"sessionKey={key}",
        "User-Agent": UA,
        "Accept": "application/json",
    })
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            body = e.read().decode("utf-8", "replace")[:600]
            sys.exit(f"HTTP {e.code} on {url}\n{body}")
        except urllib.error.URLError as e:
            sys.exit(f"Network error on {url}: {e}")
    sys.exit("Too many retries.")


def resolve_org(key: str, override: str | None) -> str:
    if override:
        return override
    orgs = api_get("/organizations", key)
    if not orgs:
        sys.exit("No organizations returned (is the sessionKey valid?).")
    for o in orgs:                               # prefer an org with chat capability
        if "chat" in (o.get("capabilities") or []):
            return o["uuid"]
    return orgs[0]["uuid"]


def conv_id(s: str) -> str:
    m = UUID_RE.search(s)
    return m.group(0) if m else s


def cmd_list(key: str, org: str) -> None:
    convs = api_get(f"/organizations/{org}/chat_conversations", key)
    for c in sorted(convs, key=lambda c: c.get("updated_at", ""), reverse=True)[:40]:
        print(f"{c.get('updated_at','')[:19]}  {c['uuid']}  {c.get('name','(untitled)')}")


def _fmt_citation(c) -> str:
    if isinstance(c, dict):
        title = c.get("title") or ""
        url = c.get("url") or c.get("uri") or ""
        detail = (f"{title} — {url}" if title and url and title != url
                  else (url or title or json.dumps(c, ensure_ascii=False)[:200]))
    else:
        detail = str(c)[:200]
    return f"\n> **[citation]** {detail}"


def render_block(b: dict) -> str:
    t = b.get("type")
    if t == "text":
        txt = b.get("text", "")
        for c in (b.get("citations") or []):
            txt += _fmt_citation(c)
        return txt
    if t == "thinking":
        body = (b.get("thinking") or b.get("text") or "").replace("\n", "\n> ")
        return f"\n> **[thinking]**\n> {body}"
    if t == "tool_use":
        return f"\n**[tool_use: {b.get('name','tool')}]** `{json.dumps(b.get('input', {}), ensure_ascii=False)}`"
    if t == "tool_result":
        dump = json.dumps(b.get("content"), ensure_ascii=False, indent=2)[:4000]
        return f"\n**[tool_result]**\n```\n{dump}\n```"
    return f"\n**[{t}]** " + json.dumps({k: v for k, v in b.items() if k != "type"}, ensure_ascii=False)[:2000]


def slugify(title: str) -> str:
    """Mirror the claude-history-viewer extension's filename slug:
    lowercase, non-alphanumeric runs -> '-', trim '-', max 50 chars."""
    return re.sub(r"[^a-z0-9]+", "-", (title or "session").lower()).strip("-")[:50] or "session"


def disambiguate(out_dir: Path, base: str, owner_marker: str) -> str:
    """Keep the extension's naming, but never clobber a DIFFERENT conversation's export.
    Re-exporting the same conversation reuses its filename (refresh); a different conversation
    that happens to share the title+date gets `-2`, `-3`, ... appended."""
    candidate, n = base, 2
    while True:
        existing = out_dir / f"{candidate}.md"
        if not existing.exists():
            return candidate
        try:
            head = existing.read_text(encoding="utf-8", errors="replace")[:2000]
        except Exception:
            head = ""
        if owner_marker in head:         # same conversation — safe to overwrite
            return candidate
        candidate = f"{base}-{n}"
        n += 1


def cmd_fetch(key: str, org: str, arg: str, method: str = "heuristic", model: str | None = None,
              out_dir: Path = DEFAULT_OUT, want_summary: bool = False) -> None:
    cid = conv_id(arg)
    data = api_get(
        f"/organizations/{org}/chat_conversations/{cid}"
        "?tree=True&rendering_mode=messages&render_all_tools=true", key)

    name = data.get("name") or cid
    started = parse_ts(data.get("created_at")) or datetime.now()
    out_dir.mkdir(parents=True, exist_ok=True)
    base = disambiguate(out_dir, f"claude-{started:%Y-%m-%d}-{slugify(name)}",
                        f"- conversation: {cid}")
    (out_dir / f"{base}.source.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8", errors="replace")

    msgs = data.get("chat_messages") or data.get("messages") or []
    lines = [f"# {name}", "",
             f"- conversation: {cid}",
             f"- messages: {len(msgs)}",
             f"- exported: {datetime.now():%Y-%m-%d %H:%M}", "", "---", ""]
    artifacts = 0
    art_dir = out_dir / f"{base}.artifacts"
    art_used: set[str] = set()           # uniquify within the export — same-titled artifacts
    ext_map = {"text/html": "html", "text/markdown": "md", "application/vnd.ant.code": "txt"}
    for m in msgs:
        lines.append(f"## {m.get('sender') or m.get('role') or '?'}")
        for b in (m.get("content") or []):
            lines.append(render_block(b))
            if b.get("type") == "tool_use" and b.get("name") == "artifacts":
                inp = b.get("input", {}) or {}
                content = inp.get("content")
                if content:
                    artifacts += 1
                    art_dir.mkdir(parents=True, exist_ok=True)
                    fn = slugify(inp.get("title") or inp.get("id") or f"artifact-{artifacts}")
                    ext = ext_map.get(inp.get("type", ""), "txt")
                    stem, n = fn, 2
                    while f"{stem}.{ext}" in art_used:
                        stem = f"{fn}-{n}"
                        n += 1
                    art_used.add(f"{stem}.{ext}")
                    (art_dir / f"{stem}.{ext}").write_text(content, encoding="utf-8",
                                                           errors="replace")
        lines.append("")
    (out_dir / f"{base}.md").write_text("\n".join(lines), encoding="utf-8", errors="replace")

    print(f"Wrote to {out_dir}:")
    print(f"  {base}.md · {base}.source.json" + (f" · {base}.artifacts/ ({artifacts})" if artifacts else ""))
    if want_summary:
        s = write_summary(out_dir / f"{base}.summary.md", data, method, model)
        extra = f" · exact {s['exact_total']:,}" if s.get("exact_total") else ""
        print(f"  {base}.summary.md — {s['messages']} msgs · {sum(s['tools'].values())} tool calls · "
              f"~{s['total']:,} tokens ({s['method']}){extra}")


def resolve_name(key: str, org: str, name: str) -> str:
    """Case-insensitive substring match on conversation title → uuid (exact title wins ties)."""
    convs = api_get(f"/organizations/{org}/chat_conversations", key)
    needle = name.lower().strip()
    matches = [c for c in convs if needle in (c.get("name") or "").lower()]
    if not matches:
        sys.exit(f'No conversation title matching "{name}".')
    if len(matches) > 1:
        exact = [c for c in matches if (c.get("name") or "").lower() == needle]
        if len(exact) == 1:
            return exact[0]["uuid"]
        print(f'"{name}" is ambiguous — {len(matches)} matches:', file=sys.stderr)
        for c in sorted(matches, key=lambda c: c.get("updated_at", ""), reverse=True)[:20]:
            print(f"  {c.get('updated_at','')[:19]}  {c['uuid']}  {c.get('name','')}", file=sys.stderr)
        sys.exit("Refine --name, or use --conversation <uuid>.")
    return matches[0]["uuid"]


# ----------------------------- summary + token estimation -----------------------------

def block_text(b: dict) -> str:
    """The tokenizable text of one content block."""
    t = b.get("type")
    if t == "text":
        return b.get("text", "") or ""
    if t == "thinking":
        return b.get("thinking") or b.get("text") or ""
    if t == "tool_use":
        return json.dumps(b.get("input", {}), ensure_ascii=False)
    if t == "tool_result":
        return json.dumps(b.get("content"), ensure_ascii=False)
    return json.dumps({k: v for k, v in b.items() if k != "type"}, ensure_ascii=False)


def make_local_counter(method: str):
    """Return (count_fn, label). tiktoken is an approximation for Claude; falls back to chars/4."""
    if method == "tiktoken":
        try:
            import tiktoken  # type: ignore
            enc = tiktoken.get_encoding("o200k_base")
            return (lambda s: len(enc.encode(s or ""))), "tiktoken/o200k_base (approx)"
        except Exception as e:
            print(f"  (tiktoken unavailable: {e}; using heuristic)", file=sys.stderr)
    return (lambda s: max(0, round(len(s or "") / 4))), "heuristic chars/4"


DEFAULT_API_MODEL = "claude-sonnet-4-5"


def api_count_total(text: str, model: str | None) -> tuple[int | None, str | None]:
    """Exact input-token count via Anthropic's free count_tokens endpoint. Needs ANTHROPIC_API_KEY."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        return None, "no ANTHROPIC_API_KEY set"
    body = json.dumps({
        "model": model or DEFAULT_API_MODEL,
        "messages": [{"role": "user", "content": text or " "}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages/count_tokens", data=body, method="POST",
        headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                 "content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read().decode("utf-8")).get("input_tokens"), None
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:200]
        return None, f"HTTP {e.code} ({detail}) — try --model <valid id>"
    except Exception as e:
        return None, str(e)


def parse_ts(s):
    try:
        return datetime.fromisoformat((s or "").replace("Z", "+00:00"))
    except Exception:
        return None


def fmt_dur(seconds: float) -> str:
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return (f"{h}h " if h else "") + (f"{m}m " if (m or h) else "") + f"{s}s"


def summarize(data: dict, method: str = "heuristic", model: str | None = None) -> dict:
    msgs = data.get("chat_messages") or data.get("messages") or []
    count_fn, label = make_local_counter(method)

    by_sender, by_type, tools = {}, {}, {}
    thinking = artifacts = citations = truncated = n_human = n_assistant = 0
    models, stamps, durations, parts = set(), [], [], []
    cum_input = cum_output = running = 0
    if data.get("model"):
        models.add(data["model"])

    for m in msgs:
        sender = m.get("sender") or m.get("role") or "?"
        is_asst = sender.lower() not in ("human", "user")
        n_assistant += int(is_asst)
        n_human += int(not is_asst)
        mtok = 0
        for b in (m.get("content") or []):
            bt = b.get("type", "?")
            txt = block_text(b)
            parts.append(txt)
            tk = count_fn(txt)
            by_type[bt] = by_type.get(bt, 0) + tk
            mtok += tk
            if bt == "thinking":
                thinking += 1
            if bt == "tool_use":
                nm = b.get("name", "tool")
                tools[nm] = tools.get(nm, 0) + 1
                if nm == "artifacts":
                    artifacts += 1
            if b.get("citations"):
                citations += len(b["citations"])
            if b.get("model"):
                models.add(b["model"])
            st, sp = parse_ts(b.get("start_timestamp")), parse_ts(b.get("stop_timestamp"))
            if st:
                stamps.append(st)
            if sp:
                stamps.append(sp)
            if st and sp and sp > st:
                durations.append((f"{sender}/{bt}", (sp - st).total_seconds()))
        if m.get("truncated"):
            truncated += 1
        by_sender[sender] = by_sender.get(sender, 0) + mtok
        if is_asst:                       # this turn re-read all prior context, then emitted mtok
            cum_input += running
            cum_output += mtok
        running += mtok

    exact_total = exact_err = None
    if method == "api":
        exact_total, exact_err = api_count_total("\n\n".join(parts), model)

    durations.sort(key=lambda x: x[1], reverse=True)
    lo = min(stamps) if stamps else None
    hi = max(stamps) if stamps else None
    wall = (hi - lo).total_seconds() if lo and hi else 0
    return {
        "name": data.get("name"), "messages": len(msgs), "human": n_human, "assistant": n_assistant,
        "thinking": thinking, "tools": tools, "artifacts": artifacts, "citations": citations,
        "truncated": truncated, "models": sorted(models), "span": (lo, hi),
        "wall": wall, "slowest": durations[:5],
        "method": label, "total": sum(by_type.values()), "by_sender": by_sender, "by_type": by_type,
        "exact_total": exact_total, "exact_err": exact_err,
        "cum_input": cum_input, "cum_output": cum_output,
    }


def render_summary(s: dict) -> str:
    L = [f"# Summary — {s['name'] or 'conversation'}", "",
         f"_token method: {s['method']}_", "", "## Activity",
         f"- messages: {s['messages']} ({s['human']} human · {s['assistant']} assistant)",
         f"- thinking blocks: {s['thinking']}",
         f"- tool calls: {sum(s['tools'].values())}"]
    L += [f"    - {nm}: {c}" for nm, c in sorted(s["tools"].items(), key=lambda x: -x[1])]
    L += [f"- artifacts: {s['artifacts']}", f"- citations: {s['citations']}",
          f"- truncated messages: {s['truncated']}",
          f"- models: {', '.join(s['models']) or 'n/a'}", "", "## Timing"]
    a, b = s["span"]
    L.append(f"- span: {a:%Y-%m-%d %H:%M:%S} → {b:%H:%M:%S}" if a else "- span: n/a")
    L.append(f"- wall clock: {fmt_dur(s['wall'])}")
    L.append("- slowest turns:")
    L += [f"    - {lab}: {sec:.0f}s" for lab, sec in s["slowest"]]
    L += ["", "## Tokens",
          "_claude.ai's conversation JSON carries no token counts, so content figures are estimates._",
          f"- total content: ~{s['total']:,}",
          "    - by sender: " + " · ".join(f"{k} ~{v:,}" for k, v in s["by_sender"].items()),
          "    - by type: " + " · ".join(f"{k} ~{v:,}" for k, v in s["by_type"].items())]
    if s["exact_total"] is not None:
        L.append(f"- exact total (Anthropic count_tokens API): {s['exact_total']:,}")
    elif s["exact_err"]:
        L.append(f"- exact total (API): unavailable — {s['exact_err']}")
    L.append(f"- cumulative processed (rough cost proxy, ignores prompt caching): "
             f"~{s['cum_input'] + s['cum_output']:,} (input ~{s['cum_input']:,} + output ~{s['cum_output']:,})")
    return "\n".join(L)


def write_summary(dest_file: Path, data: dict, method: str, model: str | None = None) -> dict:
    s = summarize(data, method, model)
    dest_file.write_text(render_summary(s), encoding="utf-8")
    return s


def cmd_resummarize(path_str: str, method: str, model: str | None) -> None:
    """Offline (re)summary of an existing export — no key, no fetch. Accepts a
    `<base>.source.json` file (new flat layout) or a directory containing
    `conversation.json` (the tool's old per-export-folder layout)."""
    p = Path(path_str)
    if p.is_dir():
        src = p / "conversation.json"
        dest = p / "summary.md"
    else:
        src = p
        base = p.name
        for suffix in (".source.json", ".json"):
            if base.endswith(suffix):
                base = base[: -len(suffix)]
                break
        dest = p.parent / f"{base}.summary.md"
    if not src.exists():
        sys.exit(f"No source JSON at {src}")
    data = json.loads(src.read_text(encoding="utf-8"))
    s = write_summary(dest, data, method, model)
    print(render_summary(s))
    print(f"\n(summary written to {dest})")


def main() -> None:
    try:                                   # Windows consoles default to cp1252; our output is UTF-8
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass
    ap = argparse.ArgumentParser(description="Export a claude.ai conversation for context handoff.")
    ap.add_argument("--list", action="store_true", help="list recent conversations")
    ap.add_argument("--conversation", help="conversation URL or UUID to export")
    ap.add_argument("--name", help="resolve & export by conversation title (substring, case-insensitive)")
    ap.add_argument("--summary", action="store_true",
                    help="also write a <name>.summary.md stats sidecar (default: no summary)")
    ap.add_argument("--resummarize", metavar="PATH",
                    help="offline: (re)write the summary for an existing export "
                         "(.source.json file or old-format export dir) — no fetch, no key")
    ap.add_argument("--tokens", choices=["heuristic", "tiktoken", "api"], default="heuristic",
                    help="summary token-estimate method (default: heuristic; 'api' = exact via "
                         "Anthropic count_tokens, needs ANTHROPIC_API_KEY)")
    ap.add_argument("--model", default=None, help=f"model id for --tokens api (default: {DEFAULT_API_MODEL})")
    ap.add_argument("--org", help="organization UUID (auto-detected if omitted)")
    ap.add_argument("--session-key", help="claude.ai sessionKey (overrides $CLAUDE_SESSION_KEY / session_key.txt)")
    ap.add_argument("--out", help=f"output directory for exports (default: {DEFAULT_OUT})")
    args = ap.parse_args()

    if args.resummarize:                   # offline path — no sessionKey needed
        cmd_resummarize(args.resummarize, args.tokens, args.model)
        return

    if (args.tokens != "heuristic" or args.model) and not args.summary:
        print("note: --tokens/--model only affect the summary — pass --summary to use them.",
              file=sys.stderr)

    key = load_key(args.session_key)
    org = resolve_org(key, args.org)
    out_dir = Path(args.out) if args.out else DEFAULT_OUT
    if args.list:
        cmd_list(key, org)
    elif args.name:
        cmd_fetch(key, org, resolve_name(key, org, args.name), args.tokens, args.model,
                  out_dir, args.summary)
    elif args.conversation:
        cmd_fetch(key, org, args.conversation, args.tokens, args.model, out_dir, args.summary)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
