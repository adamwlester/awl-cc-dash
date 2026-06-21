"""
MCP config sync — copy MCP server definitions from Windows to WSL.

Reads the Windows .claude.json, translates server configs for Linux,
and writes them into the WSL Claude Code config.
"""

import json
from .paths import WIN_CLAUDE_JSON, WSL_CLAUDE_DIR

# Servers that use Windows-specific binaries and won't work in WSL
SKIP_SERVERS = {
    "playwright",  # uses cmd /c npx @playwright — needs Windows browser
}

# Servers that use local Windows executables (not npx/uvx)
# These need individual handling or skipping
LOCAL_EXE_MARKERS = [
    ".exe",
    ".bat",
    ".cmd",
    "Scripts\\",
    "Scripts/",
]


def _is_local_exe(server_cfg):
    """Check if a server config points to a local Windows executable."""
    command = server_cfg.get("command", "")
    if any(marker in command for marker in LOCAL_EXE_MARKERS):
        return True
    return False


def _translate_server(name, cfg):
    """Translate a Windows MCP server config for WSL/Linux.

    Returns the translated config, or None if the server can't be translated.
    """
    # HTTP-based servers need no translation
    if cfg.get("type") == "http":
        return cfg

    command = cfg.get("command", "")
    args = list(cfg.get("args", []))
    env = dict(cfg.get("env", {}))

    # Skip known incompatible servers
    if name in SKIP_SERVERS:
        return None

    # Skip local Windows executables
    if _is_local_exe(cfg):
        return None

    # Translate `cmd /c npx ...` → `npx ...`
    if command == "cmd" and len(args) >= 2 and args[0] == "/c":
        actual_cmd = args[1]  # npx or uvx
        remaining_args = args[2:]
        return {
            "command": actual_cmd,
            "args": remaining_args,
            **({"env": env} if env else {}),
        }

    # Already a direct command (unlikely on Windows but handle it)
    if command in ("npx", "uvx", "node", "python3"):
        return {
            "command": command,
            "args": args,
            **({"env": env} if env else {}),
        }

    return None


def sync_mcp_config(bridge):
    """Sync MCP server configs from Windows .claude.json to WSL.

    Reads the Windows config, translates compatible servers for Linux,
    and merges them into the WSL Claude Code settings.

    Returns:
        dict with status, synced server names, and skipped server names.
    """
    # Read Windows config
    try:
        raw = bridge._run(f"cat '{WIN_CLAUDE_JSON}'", timeout=10)
        win_config = json.loads(raw)
    except Exception as e:
        raise Exception(f"Failed to read Windows .claude.json: {e}")

    win_servers = win_config.get("mcpServers", {})
    if not win_servers:
        return {"status": "ok", "synced": [], "skipped": [], "message": "No MCP servers found in Windows config."}

    synced = []
    skipped = []
    translated = {}

    for name, cfg in win_servers.items():
        result = _translate_server(name, cfg)
        if result:
            translated[name] = result
            synced.append(name)
        else:
            skipped.append(name)

    if not translated:
        return {"status": "ok", "synced": synced, "skipped": skipped, "message": "No compatible servers to sync."}

    # Read existing WSL config — lives at ~/.claude.json (user home, not inside ~/.claude/)
    wsl_config_path = "/home/lester/.claude.json"
    try:
        existing_raw = bridge._run(f"cat '{wsl_config_path}' 2>/dev/null || echo '{{}}'")
        wsl_config = json.loads(existing_raw)
    except (json.JSONDecodeError, Exception):
        wsl_config = {}

    # Merge — don't overwrite existing WSL-specific server configs
    existing_servers = wsl_config.get("mcpServers", {})
    for name, cfg in translated.items():
        existing_servers[name] = cfg
    wsl_config["mcpServers"] = existing_servers

    # Write back. Pipe the JSON via stdin rather than embedding it in the
    # command string — a large config (many MCP servers) would otherwise blow
    # past Windows' ~32 KB command-line limit and raise WinError 206.
    config_json = json.dumps(wsl_config, indent=2)
    bridge._run(
        f"cat > '{wsl_config_path}'",
        timeout=10,
        stdin_data=config_json,
    )

    return {
        "status": "ok",
        "synced": synced,
        "skipped": skipped,
        "config_path": wsl_config_path,
    }
