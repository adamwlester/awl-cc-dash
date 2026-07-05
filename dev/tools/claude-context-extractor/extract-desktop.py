#!/usr/bin/env python3
"""extract-desktop.py — export a Claude *desktop app* "local agent mode" session to Markdown.

The Claude desktop app runs its local agent mode as a Claude Code session under the hood and
stores each one on disk: a config JSON (which carries the human-readable session title) plus a
standard Claude Code CLI transcript (one JSON record per line). On the Microsoft Store (MSIX)
build the app's `AppData\\Roaming\\Claude` path is virtualized into the package container —
this script knows the real location and reads sessions by title, no network or auth needed.

Exports land in `<repo>/transcripts/desktop/` by default (override with --out), named to match
the claude-history-viewer extension's convention: `claude-<session-start-date>-<title-slug>.md`.
A stats sidecar `claude-<date>-<slug>.summary.md` is written only when --summary is passed.

Usage (stdlib only — any Python 3.9+, no venv needed). Copy-paste these from the repo root:
    python dev/tools/claude-context-extractor/extract-desktop.py --list
    python dev/tools/claude-context-extractor/extract-desktop.py --name "glossary-maintenance-strategy-1"
    python dev/tools/claude-context-extractor/extract-desktop.py --name "glossary-maintenance-strategy-1" --summary
    python dev/tools/claude-context-extractor/extract-desktop.py --session local_62de1ffd-c4d1-4ad1-b3d9-93aacc347982
    python dev/tools/claude-context-extractor/extract-desktop.py --name glossary   # substring; errors if ambiguous
    python dev/tools/claude-context-extractor/extract-desktop.py --name "..." --out C:\\somewhere\\else
(Or `cd dev/tools/claude-context-extractor` first and drop the path prefix: `python extract-desktop.py --list`.)

Escape hatches:
    --root <dir>          sessions root, if the app stores sessions somewhere non-standard
    --transcript <jsonl>  render one transcript file directly (skip discovery);
                          pair with --config <json> to supply title/model metadata
"""

from __future__ import annotations   # keep `X | None` annotations working on Python 3.9

import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

# Candidate session-store locations, first match wins (override with --root).
# The MSIX (Microsoft Store) build virtualizes AppData\Roaming\Claude into the package
# container; a non-Store install would use the plain Roaming path.
SESSIONS_ROOT_CANDIDATES = [
    Path.home() / "AppData/Local/Packages/Claude_pzs8sxrjxfjjc/LocalCache/Roaming/Claude/local-agent-mode-sessions",
    Path.home() / "AppData/Roaming/Claude/local-agent-mode-sessions",
]

# This file lives at <repo>/dev/tools/claude-context-extractor/, so the repo root is 3 up.
# If the script is copied somewhere shallower, fall back to CWD instead of crashing at import.
try:
    REPO_ROOT = Path(__file__).resolve().parents[3]
except IndexError:
    REPO_ROOT = Path.cwd()
DEFAULT_OUT = REPO_ROOT / "transcripts" / "desktop"

TOOL_INPUT_CAP = 3000     # chars of tool-call input shown per call
TOOL_RESULT_CAP = 4000    # chars of tool output shown per result


def default_root() -> Path | None:
    for c in SESSIONS_ROOT_CANDIDATES:
        if c.exists():
            return c
    return None


# ----------------------------- discovery (by name) -----------------------------

def discover_sessions(root: Path):
    """Each session = a `<group>/<conversation>/local_<id>.json` config file (exactly 3 levels
    deep — same-named files nested inside a session's own runtime folder are skipped)."""
    sessions = []
    for cfg in root.rglob("local_*.json"):
        if len(cfg.relative_to(root).parts) != 3:
            continue
        try:
            o = json.loads(cfg.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(o, dict):      # valid JSON but not a session config — skip, don't crash
            continue
        sessions.append({
            "title": o.get("title") or "(untitled)",
            "model": o.get("model") or "?",
            "created": _ms_to_dt(o.get("createdAt")),
            "last": _ms_to_dt(o.get("lastActivityAt")),
            "session_id": o.get("sessionId") or cfg.stem,
            "cli": o.get("cliSessionId") or "",
            "config": cfg,
        })
    sessions.sort(key=lambda s: s["last"] or datetime.min, reverse=True)
    return sessions


def _ms_to_dt(ms):
    if not ms:                           # None / 0 / "" — no timestamp, not the 1970 epoch
        return None
    try:
        return datetime.fromtimestamp(int(ms) / 1000)
    except Exception:
        return None


def resolve_transcript(cfg_path: Path, cli: str):
    """The transcript lives inside the session's runtime folder (same name as the config,
    minus .json): `<session-dir>/.claude/projects/*/<cliSessionId>.jsonl`."""
    session_dir = cfg_path.with_suffix("")
    if cli:
        hits = list(session_dir.glob(f".claude/projects/*/{cli}.jsonl"))
        if hits:
            return hits[0]
    hits = sorted(session_dir.glob(".claude/projects/*/*.jsonl"),
                  key=lambda p: p.stat().st_mtime, reverse=True)
    return hits[0] if hits else None


def pick_by_name(sessions, needle: str):
    n = needle.lower().strip()
    matches = [s for s in sessions if n in s["title"].lower()]
    if not matches:
        sys.exit(f'No session title matching "{needle}". Run --list to see titles.')
    if len(matches) > 1:
        exact = [s for s in matches if s["title"].lower() == n]
        if len(exact) == 1:
            return exact[0]
        print(f'"{needle}" is ambiguous — {len(matches)} matches:', file=sys.stderr)
        for s in matches:
            when = s["last"].strftime("%Y-%m-%d %H:%M") if s["last"] else "?"
            print(f"   {when}  {s['title']}", file=sys.stderr)
        sys.exit("Refine --name (exact title wins ties) or use --session <id>.")
    return matches[0]


# ----------------------------- rendering -----------------------------

def slugify(title: str) -> str:
    """Mirror the claude-history-viewer extension's filename slug:
    lowercase, non-alphanumeric runs -> '-', trim '-', max 50 chars."""
    return re.sub(r"[^a-z0-9]+", "-", (title or "session").lower()).strip("-")[:50] or "session"


def export_basename(title: str, started) -> str:
    """`claude-<session-start-date>-<title-slug>` — the extension's convention."""
    d = started or datetime.now()
    return f"claude-{d:%Y-%m-%d}-{slugify(title)}"


def disambiguate(out_dir: Path, base: str, owner_marker: str) -> str:
    """Keep the extension's naming, but never clobber a DIFFERENT session's export.
    Re-exporting the same session reuses its filename (refresh); a different session that
    happens to share the title+date gets `-2`, `-3`, ... appended."""
    candidate, n = base, 2
    while True:
        existing = out_dir / f"{candidate}.md"
        if not existing.exists():
            return candidate
        try:
            head = existing.read_text(encoding="utf-8", errors="replace")[:2000]
        except Exception:
            head = ""
        if owner_marker in head:         # same session — safe to overwrite
            return candidate
        candidate = f"{base}-{n}"
        n += 1


def load_records(path: Path):
    recs = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if ln:
            try:
                recs.append(json.loads(ln))
            except json.JSONDecodeError:
                pass
    return recs


def as_text(content) -> str:
    """tool_result content may be a plain string or a list of typed blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for b in content:
            if isinstance(b, dict):
                if b.get("type") == "text":
                    out.append(b.get("text", ""))
                elif b.get("type") == "image":
                    out.append("[image]")
                else:
                    out.append(json.dumps(b, ensure_ascii=False)[:400])
            else:
                out.append(str(b))
        return "\n".join(out)
    return json.dumps(content, ensure_ascii=False) if content is not None else ""


def cap(s: str, n: int) -> str:
    s = s or ""
    return s if len(s) <= n else s[:n] + f"\n… [truncated, {len(s) - n} more chars]"


def render_block(b: dict) -> str:
    t = b.get("type")
    if t == "text":
        return b.get("text", "")
    if t == "thinking":
        body = (b.get("thinking") or b.get("text") or "").replace("\n", "\n> ")
        return f"\n> **[thinking]**\n> {body}\n"
    if t == "tool_use":
        inp = json.dumps(b.get("input", {}), ensure_ascii=False, indent=2)
        return f"\n**[tool → {b.get('name', 'tool')}]**\n```json\n{cap(inp, TOOL_INPUT_CAP)}\n```\n"
    if t == "tool_result":
        body = cap(as_text(b.get("content")), TOOL_RESULT_CAP)
        err = " (error)" if b.get("is_error") else ""
        return f"\n**[tool result{err}]**\n```\n{body}\n```\n"
    return f"\n**[{t}]** " + cap(json.dumps({k: v for k, v in b.items() if k != 'type'},
                                            ensure_ascii=False), 800)


def render(transcript: Path, cfg: dict, out_dir: Path, want_summary: bool):
    recs = load_records(transcript)
    title = cfg.get("title") or transcript.stem
    started = _ms_to_dt(cfg.get("createdAt"))
    convo = [r for r in recs if r.get("type") in ("user", "assistant")]
    attachments = [r for r in recs if r.get("type") == "attachment"]

    tools = Counter()
    n_think = n_text = n_tool_result = n_user = n_asst = 0
    models = {cfg["model"]} if cfg.get("model") else set()
    stamps = [r.get("timestamp", "") for r in recs if r.get("timestamp")]
    for r in convo:
        msg = r.get("message") or {}
        if msg.get("role") == "user":
            n_user += 1
        elif msg.get("role") == "assistant":
            n_asst += 1
        if msg.get("model"):
            models.add(msg["model"])
        c = msg.get("content")
        if isinstance(c, list):
            for b in c:
                bt = b.get("type") if isinstance(b, dict) else None
                if bt == "thinking":
                    n_think += 1
                elif bt == "text":
                    n_text += 1
                elif bt == "tool_use":
                    tools[b.get("name", "tool")] += 1
                elif bt == "tool_result":
                    n_tool_result += 1

    out_dir.mkdir(parents=True, exist_ok=True)
    sid = cfg.get("sessionId", transcript.stem)
    base = disambiguate(out_dir, export_basename(title, started), f"- session: {sid}")
    tpath = out_dir / f"{base}.md"

    lines = [f"# {title}", "",
             f"- session: {sid}",
             f"- model: {cfg.get('model', 'n/a')}",
             f"- working folder: {(cfg.get('userSelectedFolders') or ['n/a'])[0]}",
             f"- records: {len(recs)} ({len(convo)} conversation, {len(attachments)} attachments)",
             f"- source: {transcript}",
             f"- exported: {datetime.now():%Y-%m-%d %H:%M}", "", "---", ""]
    for r in convo:
        msg = r.get("message") or {}
        lines.append(f"## {msg.get('role') or r.get('type') or '?'}")
        c = msg.get("content")
        if isinstance(c, str):
            lines.append(c)
        elif isinstance(c, list):
            for b in c:
                if isinstance(b, dict):
                    lines.append(render_block(b))
        lines.append("")
    # errors="replace": transcripts can carry JSON-escaped lone surrogates (emoji split by
    # mid-string truncation); json.loads accepts them but strict utf-8 encoding would crash.
    tpath.write_text("\n".join(lines), encoding="utf-8", errors="replace")
    written = [tpath]

    if want_summary:
        span = f"{stamps[0][:19]} to {stamps[-1][:19]}" if stamps else "n/a"
        S = [f"# Summary — {title}", "",
             f"- session id: {sid}",
             f"- model: {cfg.get('model', 'n/a')}",
             f"- working folder: {(cfg.get('userSelectedFolders') or ['n/a'])[0]}",
             f"- permission mode: {cfg.get('permissionMode', 'n/a')}", "",
             "## Activity",
             f"- conversation messages: {len(convo)} ({n_user} user, {n_asst} assistant)",
             f"- text blocks: {n_text}", f"- thinking blocks: {n_think}",
             f"- tool calls: {sum(tools.values())}"]
        S += [f"    - {nm}: {c}" for nm, c in tools.most_common()]
        S += [f"- tool results: {n_tool_result}", f"- attachments: {len(attachments)}",
              f"- models seen: {', '.join(sorted(models)) or 'n/a'}", "",
              "## Timing", f"- record span (UTC): {span}",
              f"- total records in file: {len(recs)}"]
        spath = out_dir / f"{base}.summary.md"
        spath.write_text("\n".join(S), encoding="utf-8", errors="replace")
        written.append(spath)

    print("Wrote:")
    for p in written:
        print(f"  {p}")
    print(f"\n{title}")
    print(f"{len(convo)} messages ({n_user} user / {n_asst} assistant) · "
          f"{sum(tools.values())} tool calls · {n_think} thinking blocks")


# ----------------------------- CLI -----------------------------

def main():
    try:  # Windows consoles default to cp1252; errors="replace" also survives lone surrogates
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass
    ap = argparse.ArgumentParser(
        description="Export a Claude desktop-app local-agent-mode session to Markdown.")
    ap.add_argument("--list", action="store_true", help="list all local sessions by title")
    ap.add_argument("--name", help="export by title (substring, case-insensitive; exact wins ties)")
    ap.add_argument("--session", help="export by session id (e.g. local_62de1ffd-...)")
    ap.add_argument("--summary", action="store_true",
                    help="also write a <name>.summary.md stats sidecar (default: transcript only)")
    ap.add_argument("--out", help=f"output directory (default: {DEFAULT_OUT})")
    ap.add_argument("--root", help="sessions root (default: auto-detect the desktop app's store)")
    ap.add_argument("--transcript", help="render one transcript .jsonl directly (skip discovery)")
    ap.add_argument("--config", help="session config .json to pair with --transcript (optional)")
    args = ap.parse_args()

    out_dir = Path(args.out) if args.out else DEFAULT_OUT

    if args.transcript:  # explicit-path mode, no discovery
        cfg = {}
        if args.config:
            cfg_path = Path(args.config)
            if not cfg_path.exists():
                sys.exit(f"--config not found: {cfg_path}")
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            if not isinstance(cfg, dict):
                sys.exit(f"--config is not a JSON object: {cfg_path}")
        render(Path(args.transcript), cfg, out_dir, args.summary)
        return

    root = Path(args.root) if args.root else default_root()
    if not root or not root.exists():
        sys.exit("No local-agent-mode session store found (is the Claude desktop app installed?). "
                 "Pass --root <dir> if sessions live somewhere non-standard.")
    sessions = discover_sessions(root)

    if args.list or (not args.name and not args.session):
        print(f"{len(sessions)} local-agent-mode sessions:\n")
        for s in sessions:
            when = s["last"].strftime("%Y-%m-%d %H:%M") if s["last"] else "?"
            print(f"  {when:16}  {s['model']:16}  {s['title']}")
        if not args.list:
            print('\nExport one with:  python extract-desktop.py --name "<title>"')
        return

    if args.session:
        hits = [s for s in sessions if s["session_id"] == args.session
                or s["session_id"].endswith(args.session)]
        if not hits:
            sys.exit(f"No session with id {args.session}. Run --list to see sessions.")
        if len(hits) > 1:                # suffix matched several — never guess silently
            print(f"--session {args.session} is ambiguous — {len(hits)} matches:", file=sys.stderr)
            for s in hits:
                print(f"   {s['session_id']}  ({s['title']})", file=sys.stderr)
            sys.exit("Use a longer suffix or the full session id.")
        match = hits[0]
    else:
        match = pick_by_name(sessions, args.name)

    transcript = resolve_transcript(match["config"], match["cli"])
    if not transcript:
        sys.exit(f"Found session '{match['title']}' but no transcript .jsonl under it.")
    cfg = json.loads(match["config"].read_text(encoding="utf-8"))
    render(transcript, cfg, out_dir, args.summary)


if __name__ == "__main__":
    main()
