# CC tmux Bridge

Programmatic control of Claude Code TUI sessions running in tmux inside WSL2, with automatic Windows Terminal display.

Each session is a named tmux session running a live Claude Code TUI. Every session gets a visible Windows Terminal tab automatically. Programmatic control and manual typing coexist without mode switching.

## Setup

### Prerequisites

- Windows 11 with WSL2
- Ubuntu installed in WSL (`wsl --install -d Ubuntu`)
- Claude Code CLI installed inside WSL (`npm install -g @anthropic-ai/claude-code`)
- Claude Code authenticated inside WSL (`wsl` → `claude` → follow auth flow)
- tmux 3.2+ in WSL (bundled with Ubuntu 24.04+)
- Windows Terminal (pre-installed on Windows 11)

### Installation

The package lives at the repo root as `bridge/`. From the repo root it's a
top-level package, so:

```python
from bridge import TmuxBridge
```

If you import from code that isn't run with the repo root on `sys.path`, add it
first (this is what the test suite's `conftest.py` does):

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))  # repo root
from bridge import TmuxBridge
```

Or set `PYTHONPATH` to the repo root:

```
set PYTHONPATH=%CD%;%PYTHONPATH%
```

### MCP Server Sync

Copy your Windows MCP server configs into WSL:

```python
bridge = TmuxBridge()
bridge.mcp_sync()
```

Translates `cmd /c npx` → `npx`, passes through HTTP servers, skips Windows-only servers.

## Python API

```python
from bridge import TmuxBridge

bridge = TmuxBridge()
```

### Core Operations

```python
# Create a session (auto-opens a Windows Terminal tab)
bridge.create("agent-1", cwd="C:/Users/lester/project")

# Send a prompt (types text + presses Enter)
bridge.send("agent-1", "Analyze the auth module")

# Send without pressing Enter
bridge.send("agent-1", "partial text", press_enter=False)

# Send special keys
bridge.keys("agent-1", "Enter")
bridge.keys("agent-1", "C-c")       # Ctrl+C
bridge.keys("agent-1", "Escape")

# Read screen content
result = bridge.read("agent-1", lines=50)
print(result["content"])

# Read JSONL transcript (structured output)
entries = bridge.read_log("agent-1", last_n=10, types=["user", "assistant"])

# List sessions
sessions = bridge.list()

# Open a WT tab for an existing session
bridge.show("agent-1")

# Close a single session (WT tab auto-closes)
bridge.close("agent-1")

# Kill all sessions (all WT tabs auto-close)
bridge.shutdown()
```

### Session Management

```python
# Rename
bridge.rename("agent-1", "researcher")

# Resume (returns existing or creates new)
bridge.resume("agent-1", cwd="C:/project")

# Check state: "idle", "generating", "permission_prompt", "unknown"
status = bridge.status("agent-1")
print(status["state"])
```

### Multi-Agent

```python
# Batch create (each gets its own WT tab)
agents = [
    {"name": "alpha", "cwd": "C:/project"},
    {"name": "beta",  "cwd": "C:/project", "model": "sonnet"},
]
bridge.batch_create(agents)

# Send same prompt to multiple sessions
bridge.broadcast(["alpha", "beta"], "Review the test suite")

# Interrupt a running response
bridge.interrupt("alpha")
```

### Output & Monitoring

```python
# Full scrollback history
result = bridge.scrollback("agent-1", max_lines=10000)

# Poll until output matches a regex
result = bridge.watch("agent-1", r"DONE|ERROR", timeout=60)

# Block until agent finishes responding
result = bridge.wait_idle("agent-1", timeout=120)

# Export to file
bridge.export("agent-1", "output.txt", mode="scrollback")
bridge.export("agent-1", "transcript.json", mode="log")
```

### Configuration

```python
# Set default working directory (accepts Windows or WSL paths)
bridge.set_cwd("C:/Users/lester/project")

# Set default model
bridge.set_model("sonnet")

# Sync MCP configs from Windows → WSL
result = bridge.mcp_sync()
print(f"Synced: {result['synced']}")
print(f"Skipped: {result['skipped']}")
```

### Constructor Options

```python
bridge = TmuxBridge(
    distro="Ubuntu",           # WSL distro name
    default_cwd="C:/project",  # Default working directory
    default_model="opus",      # Default model for new sessions
)
```

## CLI

```bash
cd <repo-root>    # where the bridge/ package lives
python -m bridge <command> [args...]
```

### Commands

```
create <name> [--cwd PATH] [--model MODEL]
send <name> <text> [--no-enter]
keys <name> <KEY> [KEY...]
read <name> [--lines N]
read-log <name> [--last N] [--types TYPE...]
list
show <name>
close <name>
shutdown
rename <old> <new>
resume <name> [--cwd PATH]
status <name>
batch-create <json-config>
broadcast <names> <text>
interrupt <name>
scrollback <name>
watch <name> <pattern> [--timeout N]
wait-idle <name> [--timeout N]
export <name> <filepath> [--mode scrollback|log]
mcp-sync
```

### Examples

```bash
# Create and interact (opens a WT tab automatically)
python -m bridge create my-agent --cwd "C:/project"
python -m bridge send my-agent "Hello, what files are in this project?"
python -m bridge read my-agent --lines 30

# Monitor
python -m bridge wait-idle my-agent --timeout 60
python -m bridge status my-agent

# Multi-agent (each gets a WT tab)
python -m bridge batch-create '[{"name":"a","cwd":"C:/p"},{"name":"b","cwd":"C:/p"}]'
python -m bridge broadcast a,b "Run the tests"

# Tear down everything
python -m bridge shutdown
```

## Error Handling

All errors raise `TmuxBridgeError` (Python API) or print to stderr (CLI).

```python
try:
    bridge.send("nonexistent", "hello")
except Exception as e:
    print(e)  # "Session 'nonexistent' not found. Active sessions: (none)"
```

## Architecture

```
[tmux sessions in WSL2]     ← always running, survive WT/VS Code restarts
        ↑
[bridge]    ← Python API to control them
        ↑
[Windows Terminal tabs]      ← visible display, auto-managed
```

- `create()` spawns a tmux session + opens a WT tab
- `close()` kills a tmux session → WT tab auto-closes
- `shutdown()` kills all sessions → all WT tabs auto-close
- `show()` opens a new WT tab for an existing session
- Sessions persist even if WT is closed — `show()` reconnects

## File Structure

```
bridge/
├── __init__.py       # Package exports
├── __main__.py       # python -m entry point
├── bridge.py         # TmuxBridge class (all operations)
├── cli.py            # CLI interface (argparse)
├── mcp.py            # MCP config sync (Windows → WSL)
├── paths.py          # Windows ↔ WSL path translation
├── transcript.py     # JSONL transcript parser
└── README.md
```
