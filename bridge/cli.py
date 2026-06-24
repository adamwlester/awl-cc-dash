"""
CC tmux Bridge — CLI interface.

Usage:
    python -m bridge <command> [args...]

Or directly:
    python cli.py <command> [args...]
"""

import sys
import json
import argparse
from .bridge import TmuxBridge, TmuxBridgeError


def make_parser():
    parser = argparse.ArgumentParser(
        prog="cc-tmux-bridge",
        description="Programmatic control of Claude Code TUI sessions in WSL2/tmux.",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # create
    p = sub.add_parser("create", help="Spawn a new Claude Code session")
    p.add_argument("name", help="Session name")
    p.add_argument("--cwd", help="Working directory (Windows or WSL path)")
    p.add_argument("--model", help="Model to use (e.g. sonnet, opus)")
    p.add_argument("--claude-args", default="", help="Additional claude CLI args")
    # CLI create is interactive human use, so it opens a WT tab by default
    # (preserving long-standing behavior). The library default is tab-less.
    p.add_argument("--no-show", action="store_true",
                   help="Do not open a Windows Terminal tab for the new session")

    # send
    p = sub.add_parser("send", help="Send text to a session")
    p.add_argument("name", help="Session name")
    p.add_argument("text", help="Text to send")
    p.add_argument("--no-enter", action="store_true", help="Don't press Enter after typing")

    # keys
    p = sub.add_parser("keys", help="Send special keys to a session")
    p.add_argument("name", help="Session name")
    p.add_argument("key_names", nargs="+", metavar="KEY", help="Key names: Enter, Escape, C-c, etc.")

    # read
    p = sub.add_parser("read", help="Capture screen content from a session")
    p.add_argument("name", help="Session name")
    p.add_argument("--lines", type=int, default=50, help="Number of lines to capture (default 50)")

    # read-log
    p = sub.add_parser("read-log", help="Read structured JSONL transcript")
    p.add_argument("name", help="Session name")
    p.add_argument("--last", type=int, help="Only return last N entries")
    p.add_argument("--types", nargs="+", help="Filter by message types (e.g. user assistant)")

    # list
    sub.add_parser("list", help="List active sessions")

    # show
    p = sub.add_parser("show", help="Open a WT tab for an existing session")
    p.add_argument("name", help="Session name")

    # close
    p = sub.add_parser("close", help="Kill a session")
    p.add_argument("name", help="Session name")

    # shutdown
    sub.add_parser("shutdown", help="Kill all sessions and clean up")

    # rename
    p = sub.add_parser("rename", help="Rename a session")
    p.add_argument("old_name", help="Current session name")
    p.add_argument("new_name", help="New session name")

    # resume
    p = sub.add_parser("resume", help="Resume or create a session")
    p.add_argument("name", help="Session name")
    p.add_argument("--cwd", help="Working directory (if creating)")
    p.add_argument("--model", help="Model (if creating)")

    # status
    p = sub.add_parser("status", help="Get session state (idle, generating, etc.)")
    p.add_argument("name", help="Session name")

    # batch-create
    p = sub.add_parser("batch-create", help="Create multiple sessions from JSON config")
    p.add_argument("config", help="JSON array of agent configs, or path to JSON file")

    # broadcast
    p = sub.add_parser("broadcast", help="Send text to multiple sessions")
    p.add_argument("names", help="Comma-separated session names")
    p.add_argument("text", help="Text to send")

    # interrupt
    p = sub.add_parser("interrupt", help="Send Ctrl+C to a session")
    p.add_argument("name", help="Session name")

    # scrollback
    p = sub.add_parser("scrollback", help="Capture full scrollback history")
    p.add_argument("name", help="Session name")
    p.add_argument("--max-lines", type=int, default=10000, help="Max lines (default 10000)")

    # watch
    p = sub.add_parser("watch", help="Poll until output matches a pattern")
    p.add_argument("name", help="Session name")
    p.add_argument("pattern", help="Regex pattern to match")
    p.add_argument("--timeout", type=int, default=60, help="Timeout in seconds (default 60)")
    p.add_argument("--interval", type=float, default=0.5, help="Poll interval (default 0.5)")

    # wait-idle
    p = sub.add_parser("wait-idle", help="Block until session is idle")
    p.add_argument("name", help="Session name")
    p.add_argument("--timeout", type=int, default=120, help="Timeout in seconds (default 120)")

    # export
    p = sub.add_parser("export", help="Export session content to file")
    p.add_argument("name", help="Session name")
    p.add_argument("filepath", help="Output file path")
    p.add_argument("--mode", choices=["scrollback", "log"], default="scrollback", help="Export mode")

    # mcp-sync
    sub.add_parser("mcp-sync", help="Sync MCP config from Windows to WSL")

    return parser


def output(data):
    """Print JSON output."""
    print(json.dumps(data, indent=2, default=str))


def main(argv=None):
    parser = make_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    bridge = TmuxBridge()

    try:
        if args.command == "create":
            result = bridge.create(args.name, cwd=args.cwd, model=args.model,
                                   claude_args=args.claude_args, show=not args.no_show)
            output(result)

        elif args.command == "send":
            result = bridge.send(args.name, args.text, press_enter=not args.no_enter)
            output(result)

        elif args.command == "keys":
            result = bridge.keys(args.name, *args.key_names)
            output(result)

        elif args.command == "read":
            result = bridge.read(args.name, lines=args.lines)
            # Print content directly for readability, not JSON
            print(result["content"])

        elif args.command == "read-log":
            entries = bridge.read_log(args.name, last_n=args.last, types=args.types)
            output(entries)

        elif args.command == "list":
            sessions = bridge.list()
            if not sessions:
                print("No active sessions.")
            else:
                # Table format
                print(f"{'NAME':<20} {'PID':<8} {'WINDOWS':<8} {'ATTACHED'}")
                for s in sessions:
                    att = "yes" if s["attached"] else "no"
                    print(f"{s['name']:<20} {s['pid']:<8} {s['windows']:<8} {att}")

        elif args.command == "show":
            result = bridge.show(args.name)
            output(result)

        elif args.command == "close":
            result = bridge.close(args.name)
            output(result)

        elif args.command == "shutdown":
            result = bridge.shutdown()
            output(result)

        elif args.command == "rename":
            result = bridge.rename(args.old_name, args.new_name)
            output(result)

        elif args.command == "resume":
            result = bridge.resume(args.name, cwd=args.cwd, model=args.model)
            output(result)

        elif args.command == "status":
            result = bridge.status(args.name)
            output(result)

        elif args.command == "batch-create":
            # Try parsing as JSON string first, then as file path
            try:
                agents = json.loads(args.config)
            except json.JSONDecodeError:
                with open(args.config, "r") as f:
                    agents = json.load(f)
            results = bridge.batch_create(agents)
            output(results)

        elif args.command == "broadcast":
            names = [n.strip() for n in args.names.split(",")]
            results = bridge.broadcast(names, args.text)
            output(results)

        elif args.command == "interrupt":
            result = bridge.interrupt(args.name)
            output(result)

        elif args.command == "scrollback":
            result = bridge.scrollback(args.name, max_lines=args.max_lines)
            print(result["content"])

        elif args.command == "watch":
            result = bridge.watch(args.name, args.pattern, timeout=args.timeout, interval=args.interval)
            output(result)

        elif args.command == "wait-idle":
            result = bridge.wait_idle(args.name, timeout=args.timeout)
            output(result)

        elif args.command == "export":
            result = bridge.export(args.name, args.filepath, mode=args.mode)
            output(result)

        elif args.command == "mcp-sync":
            result = bridge.mcp_sync()
            output(result)

        return 0

    except TmuxBridgeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
