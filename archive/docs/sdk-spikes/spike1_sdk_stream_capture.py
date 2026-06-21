"""
Spike 1: SDK Stream Capture Test
=================================
Can we capture the full Claude Code SDK event stream from a Python script on Windows?

Spawns claude in non-interactive stream-json mode with a trivial read-only task
(no permissions needed), captures all NDJSON events, and logs their types + structure.

Expected: We should see system init, assistant messages with content blocks,
tool use blocks, and a final result with cost/usage.
"""

import subprocess
import json
import sys
import time
from datetime import datetime

OUTFILE = __file__.replace(".py", "_results.md")

def run_spike():
    print("=" * 60)
    print("SPIKE 1: SDK Stream Capture")
    print("=" * 60)

    cmd = [
        "claude", "-p",
        "List the files in the current directory. Just show the output, nothing else.",
        "--output-format", "stream-json",
        "--verbose",
    ]

    print(f"\nCommand: {' '.join(cmd)}")
    print(f"Started: {datetime.now().isoformat()}")
    print("-" * 60)

    events = []
    event_types = {}

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # line-buffered
        )

        start = time.time()

        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue

            try:
                event = json.loads(line)
                event_type = event.get("type", "unknown")
                event_subtype = event.get("subtype", "")

                key = f"{event_type}" + (f":{event_subtype}" if event_subtype else "")
                event_types[key] = event_types.get(key, 0) + 1

                # Capture full event but truncate large content for logging
                events.append({
                    "type": key,
                    "timestamp": time.time() - start,
                    "keys": list(event.keys()),
                    "raw_size": len(line),
                })

                # Print live
                elapsed = f"{time.time() - start:.2f}s"
                print(f"  [{elapsed}] {key} ({len(line)} bytes) keys={list(event.keys())}")

                # For assistant messages, show content block types
                if event_type == "assistant":
                    msg = event.get("message", {})
                    content = msg.get("content", [])
                    for block in content:
                        btype = block.get("type", "?")
                        if btype == "text":
                            text_preview = block.get("text", "")[:80]
                            print(f"         -> text: {text_preview}...")
                        elif btype == "tool_use":
                            print(f"         -> tool_use: {block.get('name', '?')} id={block.get('id', '?')[:12]}")
                        elif btype == "thinking":
                            print(f"         -> thinking ({len(block.get('thinking', ''))} chars)")
                        else:
                            print(f"         -> {btype}")

                # For result, show cost
                if event_type == "result":
                    print(f"         -> cost: ${event.get('total_cost_usd', '?')}")
                    print(f"         -> turns: {event.get('num_turns', '?')}")
                    print(f"         -> duration: {event.get('duration_ms', '?')}ms")

                # For control_request, flag it
                if event_type == "control_request":
                    req = event.get("request", {})
                    print(f"         -> PERMISSION REQUEST: {req.get('subtype', '?')} tool={req.get('tool_name', '?')}")

            except json.JSONDecodeError:
                print(f"  [?] Non-JSON line: {line[:80]}")
                events.append({"type": "parse_error", "line": line[:200]})

        proc.wait(timeout=120)
        stderr_out = proc.stderr.read()
        elapsed_total = time.time() - start

    except subprocess.TimeoutExpired:
        proc.kill()
        stderr_out = "TIMEOUT"
        elapsed_total = 120
    except FileNotFoundError:
        print("\nERROR: 'claude' not found on PATH. Is Claude Code installed?")
        return

    # Summary
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Total events: {len(events)}")
    print(f"Total time: {elapsed_total:.2f}s")
    print(f"Exit code: {proc.returncode}")
    print(f"\nEvent type breakdown:")
    for k, v in sorted(event_types.items()):
        print(f"  {k}: {v}")

    if stderr_out.strip():
        print(f"\nStderr: {stderr_out[:500]}")

    # Write results file
    with open(OUTFILE, "w") as f:
        f.write("---\n")
        f.write("title: 'Spike 1: SDK Stream Capture Results'\n")
        f.write(f"date: {datetime.now().strftime('%Y-%m-%d')}\n")
        f.write("tags: [testing, sdk, stream-json, spike]\n")
        f.write("---\n\n")
        f.write("# Spike 1: SDK Stream Capture Results\n\n")
        f.write(f"**Date:** {datetime.now().isoformat()}\n")
        f.write(f"**Command:** `{' '.join(cmd)}`\n")
        f.write(f"**Duration:** {elapsed_total:.2f}s\n")
        f.write(f"**Exit code:** {proc.returncode}\n")
        f.write(f"**Total events:** {len(events)}\n\n")

        f.write("## Event Type Breakdown\n\n")
        f.write("| Type | Count |\n|------|-------|\n")
        for k, v in sorted(event_types.items()):
            f.write(f"| `{k}` | {v} |\n")

        f.write("\n## Event Timeline\n\n")
        f.write("| # | Time | Type | Size | Keys |\n")
        f.write("|---|------|------|------|------|\n")
        for i, ev in enumerate(events):
            f.write(f"| {i+1} | {ev.get('timestamp', 0):.2f}s | `{ev['type']}` | {ev.get('raw_size', '?')}b | {', '.join(ev.get('keys', []))} |\n")

        if stderr_out.strip():
            f.write(f"\n## Stderr\n\n```\n{stderr_out[:1000]}\n```\n")

        f.write("\n## Verdict\n\n")
        has_assistant = any("assistant" in e["type"] for e in events)
        has_result = any("result" in e["type"] for e in events)
        has_system = any("system" in e["type"] for e in events)

        if has_assistant and has_result:
            f.write("**PASS** — Full event stream captured. Assistant messages, tool use, and result with cost/usage all present.\n")
        elif has_result:
            f.write("**PARTIAL** — Got result but missing assistant messages. May need --verbose flag check.\n")
        else:
            f.write("**FAIL** — Could not capture expected event types.\n")

    print(f"\nResults written to: {OUTFILE}")

if __name__ == "__main__":
    run_spike()
