"""
Spike 2: Bidirectional SDK Stream with Permission Handling
============================================================
Can we handle permission requests programmatically via stdin/stdout NDJSON?

Spawns claude in full bidirectional stream-json mode, sends a task that requires
tool approval (writing a file), intercepts the permission control_request,
auto-approves it, and verifies the task completes.

Expected: We should see control_request with subtype "can_use_tool", respond
with control_response to allow it, and get a successful result.
"""

import subprocess
import json
import time
import threading
import os
from datetime import datetime

OUTFILE = __file__.replace(".py", "_results.md")
# Write to a temp location that's safe to create/delete
TEST_FILE = os.path.join(os.path.dirname(__file__), "_spike2_test_output.txt")

def run_spike():
    print("=" * 60)
    print("SPIKE 2: Bidirectional Permission Handling")
    print("=" * 60)

    cmd = [
        "claude", "-p",
        "--input-format", "stream-json",
        "--output-format", "stream-json",
        "--verbose",
    ]

    print(f"\nCommand: {' '.join(cmd)}")
    print(f"Started: {datetime.now().isoformat()}")
    print("-" * 60)

    events = []
    event_types = {}
    permission_requests = []
    permission_responses = []
    start = time.time()

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        stdin=subprocess.PIPE,
        text=True,
        bufsize=1,
        encoding="utf-8",
        errors="replace",
        env=env,
    )

    # Send the initial user message that will trigger a tool use requiring permission
    user_msg = {
        "type": "user",
        "session_id": "",
        "message": {
            "role": "user",
            "content": f"Write the text 'spike2 test successful' to the file {TEST_FILE}. Do not explain, just write the file."
        },
        "parent_tool_use_id": None,
    }
    print(f"\n  -> Sending user message...")
    proc.stdin.write(json.dumps(user_msg) + "\n")
    proc.stdin.flush()

    # Read events from stdout, handle permission requests
    try:
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

                elapsed = f"{time.time() - start:.2f}s"
                events.append({
                    "type": key,
                    "timestamp": time.time() - start,
                    "keys": list(event.keys()),
                    "raw_size": len(line),
                })

                print(f"  [{elapsed}] {key} ({len(line)} bytes)")

                # Handle permission requests
                if event_type == "control_request":
                    req = event.get("request", {})
                    req_subtype = req.get("subtype", "")
                    request_id = event.get("request_id", "")

                    if req_subtype == "can_use_tool":
                        tool_name = req.get("tool_name", "?")
                        tool_input = req.get("input", {})
                        print(f"         -> PERMISSION REQUEST: tool={tool_name} request_id={request_id}")

                        # Preview the tool input
                        input_preview = json.dumps(tool_input)[:120]
                        print(f"         -> Input: {input_preview}")

                        permission_requests.append({
                            "tool_name": tool_name,
                            "request_id": request_id,
                            "input_preview": input_preview,
                        })

                        # Auto-approve!
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
                        print(f"         <- APPROVING (allow)")
                        proc.stdin.write(json.dumps(response) + "\n")
                        proc.stdin.flush()
                        permission_responses.append({
                            "request_id": request_id,
                            "decision": "allow",
                        })
                    else:
                        print(f"         -> control subtype: {req_subtype}")

                # Show assistant content
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
                    print(f"         -> denials: {event.get('permission_denials', [])}")

            except json.JSONDecodeError:
                print(f"  [?] Non-JSON: {line[:80]}")

        proc.wait(timeout=120)
        stderr_out = proc.stderr.read()

    except subprocess.TimeoutExpired:
        proc.kill()
        stderr_out = "TIMEOUT"
    except Exception as e:
        proc.kill()
        stderr_out = str(e)

    elapsed_total = time.time() - start

    # Check if the file was actually created
    file_created = os.path.exists(TEST_FILE)
    file_content = ""
    if file_created:
        with open(TEST_FILE) as f:
            file_content = f.read()
        os.remove(TEST_FILE)  # cleanup

    # Summary
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    print(f"Total events: {len(events)}")
    print(f"Total time: {elapsed_total:.2f}s")
    print(f"Exit code: {proc.returncode}")
    print(f"Permission requests seen: {len(permission_requests)}")
    print(f"Permission responses sent: {len(permission_responses)}")
    print(f"Test file created: {file_created}")
    if file_content:
        print(f"Test file content: '{file_content.strip()}'")
    print(f"\nEvent type breakdown:")
    for k, v in sorted(event_types.items()):
        print(f"  {k}: {v}")

    if stderr_out and stderr_out.strip():
        print(f"\nStderr (first 500): {stderr_out[:500]}")

    # Write results
    with open(OUTFILE, "w") as f:
        f.write("---\n")
        f.write("title: 'Spike 2: Bidirectional Permission Handling Results'\n")
        f.write(f"date: {datetime.now().strftime('%Y-%m-%d')}\n")
        f.write("tags: [testing, sdk, stream-json, permissions, spike]\n")
        f.write("---\n\n")
        f.write("# Spike 2: Bidirectional Permission Handling Results\n\n")
        f.write(f"**Date:** {datetime.now().isoformat()}\n")
        f.write(f"**Command:** `{' '.join(cmd)}`\n")
        f.write(f"**Duration:** {elapsed_total:.2f}s\n")
        f.write(f"**Exit code:** {proc.returncode}\n")
        f.write(f"**Total events:** {len(events)}\n\n")

        f.write("## Permission Handling\n\n")
        f.write(f"- **Requests received:** {len(permission_requests)}\n")
        f.write(f"- **Responses sent:** {len(permission_responses)}\n")
        f.write(f"- **Test file created:** {file_created}\n")
        f.write(f"- **Test file content:** `{file_content.strip()}`\n\n")

        if permission_requests:
            f.write("### Permission Request Details\n\n")
            f.write("| # | Tool | Request ID | Input Preview |\n")
            f.write("|---|------|-----------|---------------|\n")
            for i, pr in enumerate(permission_requests):
                f.write(f"| {i+1} | `{pr['tool_name']}` | `{pr['request_id'][:16]}...` | `{pr['input_preview'][:80]}` |\n")
            f.write("\n")

        f.write("## Event Type Breakdown\n\n")
        f.write("| Type | Count |\n|------|-------|\n")
        for k, v in sorted(event_types.items()):
            f.write(f"| `{k}` | {v} |\n")

        f.write("\n## Event Timeline\n\n")
        f.write("| # | Time | Type | Size |\n")
        f.write("|---|------|------|------|\n")
        for i, ev in enumerate(events):
            f.write(f"| {i+1} | {ev.get('timestamp', 0):.2f}s | `{ev['type']}` | {ev.get('raw_size', '?')}b |\n")

        if stderr_out and stderr_out.strip():
            f.write(f"\n## Stderr\n\n```\n{stderr_out[:1000]}\n```\n")

        f.write("\n## Verdict\n\n")
        if file_created and len(permission_requests) > 0 and len(permission_responses) > 0:
            f.write("**PASS** — Full bidirectional SDK protocol works. Permission requests captured, auto-approved via stdin, task completed successfully. The file was written without any human touching a TUI.\n\n")
            f.write("**Implication:** Terminal embedding (ttyd/xterm.js) is NOT required. A GUI can spawn Claude in SDK mode, render the structured event stream natively, and handle all permissions programmatically. This eliminates the WSL2 port-forwarding risk entirely.\n")
        elif len(permission_requests) > 0 and not file_created:
            f.write("**PARTIAL** — Permission requests were received but the file was not created. The approval response may not have been formatted correctly.\n")
        elif len(permission_requests) == 0:
            f.write("**INCONCLUSIVE** — No permission requests were received. The task may have been auto-approved by existing permission rules, or the permission mode may need adjustment.\n")
        else:
            f.write("**FAIL** — Could not establish bidirectional SDK protocol.\n")

    print(f"\nResults written to: {OUTFILE}")

if __name__ == "__main__":
    run_spike()
