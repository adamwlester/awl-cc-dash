"""
Spike 2b: Permission Handling via CLI arg + stream-json
=========================================================
Alternative approach: pass the task as -p arg (like spike 1 which worked),
but add --input-format stream-json so we can respond to permission requests
via stdin. This avoids the hanging issue with pure stdin-driven startup.

We also use --permission-mode default to ensure permissions ARE prompted.
"""

import subprocess
import json
import time
import os
import threading
from datetime import datetime

OUTFILE = __file__.replace(".py", "_results.md")
TEST_FILE = os.path.join(os.path.dirname(__file__), "_spike2b_test.txt").replace("\\", "/")

def run_spike():
    print("=" * 60)
    print("SPIKE 2b: Permission Handling (CLI arg approach)")
    print("=" * 60)

    cmd = [
        "claude", "-p",
        f"Write exactly the text 'spike2b success' to {TEST_FILE}. Just write the file, no explanation.",
        "--output-format", "stream-json",
        "--input-format", "stream-json",
        "--verbose",
    ]

    print(f"\nCommand: {' '.join(cmd[:6])}...")
    print(f"Started: {datetime.now().isoformat()}")
    print("-" * 60)

    events = []
    event_types = {}
    permission_requests = []
    permission_responses = []
    start = time.time()

    env = os.environ.copy()

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env=env,
    )

    # Read stderr in background to prevent blocking
    stderr_lines = []
    def drain_stderr():
        try:
            for line in proc.stderr:
                stderr_lines.append(line)
        except:
            pass
    t = threading.Thread(target=drain_stderr, daemon=True)
    t.start()

    try:
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue

            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                print(f"  [?] Non-JSON: {line[:80]}")
                continue

            event_type = event.get("type", "unknown")
            event_subtype = event.get("subtype", "")
            key = f"{event_type}" + (f":{event_subtype}" if event_subtype else "")
            event_types[key] = event_types.get(key, 0) + 1

            elapsed = f"{time.time() - start:.2f}s"
            events.append({
                "type": key,
                "timestamp": time.time() - start,
                "raw_size": len(line),
            })

            print(f"  [{elapsed}] {key} ({len(line)} bytes)")

            # Handle permission requests
            if event_type == "control_request":
                req = event.get("request", {})
                request_id = event.get("request_id", "")

                if req.get("subtype") == "can_use_tool":
                    tool_name = req.get("tool_name", "?")
                    tool_input = req.get("input", {})
                    print(f"         *** PERMISSION REQUEST: tool={tool_name}")
                    print(f"         *** Input: {json.dumps(tool_input)[:150]}")

                    permission_requests.append({
                        "tool_name": tool_name,
                        "request_id": request_id,
                    })

                    # Send approval
                    response = {
                        "type": "control_response",
                        "response": {
                            "subtype": "success",
                            "request_id": request_id,
                            "response": {
                                "behavior": "allow",
                                "updatedInput": {},
                            }
                        }
                    }
                    resp_json = json.dumps(response)
                    print(f"         <<< SENDING APPROVAL")
                    proc.stdin.write(resp_json + "\n")
                    proc.stdin.flush()
                    permission_responses.append({"request_id": request_id, "decision": "allow"})

            # Show assistant content blocks
            if event_type == "assistant":
                msg = event.get("message", {})
                for block in msg.get("content", []):
                    btype = block.get("type", "?")
                    if btype == "text":
                        print(f"         -> text: {block.get('text', '')[:100]}")
                    elif btype == "tool_use":
                        print(f"         -> tool_use: {block.get('name', '?')}")

            # Show result
            if event_type == "result":
                print(f"         -> cost: ${event.get('total_cost_usd', '?')}")
                print(f"         -> turns: {event.get('num_turns', '?')}")
                denials = event.get("permission_denials", [])
                if denials:
                    print(f"         -> DENIALS: {denials}")

        proc.wait(timeout=120)
    except subprocess.TimeoutExpired:
        proc.kill()
    except Exception as e:
        print(f"  ERROR: {e}")
        proc.kill()

    elapsed_total = time.time() - start
    stderr_out = "".join(stderr_lines)

    # Check file
    file_created = os.path.exists(TEST_FILE)
    file_content = ""
    if file_created:
        with open(TEST_FILE) as f:
            file_content = f.read()
        os.remove(TEST_FILE)

    # Summary
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Total events: {len(events)}")
    print(f"Total time: {elapsed_total:.2f}s")
    print(f"Exit code: {proc.returncode}")
    print(f"Permission requests: {len(permission_requests)}")
    print(f"Permission responses: {len(permission_responses)}")
    print(f"File created: {file_created}")
    if file_content:
        print(f"File content: '{file_content.strip()}'")
    print(f"\nEvent types:")
    for k, v in sorted(event_types.items()):
        print(f"  {k}: {v}")
    if stderr_out.strip():
        print(f"\nStderr: {stderr_out[:300]}")

    # Write results
    with open(OUTFILE, "w") as f:
        f.write("---\n")
        f.write("title: 'Spike 2b: Permission Handling Results'\n")
        f.write(f"date: {datetime.now().strftime('%Y-%m-%d')}\n")
        f.write("tags: [testing, sdk, stream-json, permissions, spike]\n")
        f.write("---\n\n")
        f.write("# Spike 2b: Permission Handling via CLI + stream-json\n\n")
        f.write(f"**Date:** {datetime.now().isoformat()}\n")
        f.write(f"**Duration:** {elapsed_total:.2f}s\n")
        f.write(f"**Exit code:** {proc.returncode}\n\n")

        f.write("## Permission Handling\n\n")
        f.write(f"- Requests received: **{len(permission_requests)}**\n")
        f.write(f"- Responses sent: **{len(permission_responses)}**\n")
        f.write(f"- File created: **{file_created}**\n")
        f.write(f"- File content: `{file_content.strip()}`\n\n")

        if permission_requests:
            f.write("### Requests\n\n")
            for i, pr in enumerate(permission_requests):
                f.write(f"{i+1}. Tool: `{pr['tool_name']}`, ID: `{pr['request_id'][:20]}...`\n")
            f.write("\n")

        f.write("## Event Types\n\n")
        f.write("| Type | Count |\n|------|-------|\n")
        for k, v in sorted(event_types.items()):
            f.write(f"| `{k}` | {v} |\n")

        f.write("\n## Verdict\n\n")
        if file_created and permission_requests:
            f.write("**PASS** — Bidirectional SDK protocol confirmed. Permission requests intercepted and approved programmatically. File written successfully without any TUI interaction.\n\n")
            f.write("### Architecture Implication\n\n")
            f.write("Terminal embedding (ttyd/xterm.js/WSL2 port forwarding) is **not required**. ")
            f.write("A GUI can:\n")
            f.write("1. Spawn `claude -p <task> --input-format stream-json --output-format stream-json --verbose`\n")
            f.write("2. Read structured NDJSON events from stdout\n")
            f.write("3. Render tool calls, responses, and thinking in native UI components\n")
            f.write("4. Handle permission prompts via `control_request`/`control_response` on stdin\n\n")
            f.write("This is strictly superior to terminal embedding: richer data, typed events, programmatic control, no WSL2 networking issues.\n")
        elif file_created and not permission_requests:
            f.write("**PASS (auto-approved)** — Task completed but no permission prompts were shown. Existing allow rules or permission mode auto-approved the action. The stream capture works; permission interception needs a tighter permission mode to test.\n")
        elif not file_created and permission_requests:
            f.write("**PARTIAL** — Permission requests received but file not created. Approval response format may need adjustment.\n")
        else:
            f.write("**FAIL** — Neither permission requests nor file creation observed.\n")

    print(f"\nResults: {OUTFILE}")

if __name__ == "__main__":
    run_spike()
