---
source: claude
created: 2026-03-31
tags: [testing, wsl2, tmux, claude-code, environment-check]
---

# WSL2 + tmux Environment Check

**Date of test:** 2026-03-31

---

## Step 1: Check WSL2 is available and running

**Command:**
```powershell
wsl --list --verbose
```

**Output:**
```
  NAME                  STATE           VERSION
* docker-desktop        Running         2
```

**Result:** WSL2 is available and running, but the **only installed distro is `docker-desktop`** — a minimal Alpine-based internal distro used by Docker Desktop. There is no general-purpose Linux distribution (e.g., Ubuntu, Debian) installed.

---

## Step 2: Check Node.js in WSL2

**Command:**
```powershell
wsl node --version
```

**Output:**
```
/bin/sh: node: not found
```

**Command:**
```powershell
wsl npm --version
```

**Output:**
```
env: can't execute 'bash': No such file or directory
```

**Result:** FAILED — Node.js and npm are not installed in the WSL2 docker-desktop distro. Additionally, `bash` itself is not available (docker-desktop uses `/bin/sh` only).

---

## Step 3: Check if Claude Code CLI is accessible from WSL2

**Command:**
```powershell
wsl claude --version
```

**Output:**
```
/tmp/docker-desktop-root/run/desktop/mnt/host/c/Users/lester/AppData/Roaming/npm/claude: exec: line 15: node: not found
```

**Command:**
```powershell
wsl which claude
```

**Output:**
```
/tmp/docker-desktop-root/run/desktop/mnt/host/c/Users/lester/AppData/Roaming/npm/claude
```

**Command:**
```powershell
wsl bash -c "export PATH=$PATH:/usr/local/bin:$HOME/.npm-global/bin && claude --version"
```

**Output:**
```
/bin/sh: bash: not found
```

**Result:** FAILED — The `claude` binary is found via the Windows PATH mount at the npm global path, but it **cannot execute** because Node.js is not available in the docker-desktop distro. Bash is also not available.

---

## Step 4: Check tmux in WSL2

**Command:**
```powershell
wsl tmux -V
```

**Output:**
```
/bin/sh: tmux: not found
```

**Command:**
```powershell
wsl which tmux
```

**Output:**
```
(no output, exit code 1)
```

**Result:** FAILED — tmux is not installed in the WSL2 docker-desktop distro.

---

## Step 5: Test basic tmux operation from Windows

**Skipped** — tmux is not installed (Step 4 failed).

---

## Step 6: Test cross-boundary control (Windows PowerShell → WSL tmux)

**Skipped** — tmux is not installed (Step 4 failed).

---

## Additional context

**Command:**
```powershell
wsl sh -c 'cat /etc/os-release'
```

**Output:**
```
PRETTY_NAME="Docker Desktop"
```

The docker-desktop WSL2 distro is a purpose-built minimal environment for Docker. It lacks bash, Node.js, npm, tmux, and most standard Linux tooling.

---

## Summary

| Step | Description | Result |
|------|-------------|--------|
| 1 | WSL2 available and running | PARTIAL — WSL2 works, but only `docker-desktop` distro present |
| 2 | Node.js in WSL2 | FAILED — not installed; bash also missing |
| 3 | Claude Code CLI in WSL2 | FAILED — binary found via Windows PATH but can't execute (no Node.js) |
| 4 | tmux in WSL2 | FAILED — not installed |
| 5 | Basic tmux operation | SKIPPED — tmux not available |
| 6 | Cross-boundary control | SKIPPED — tmux not available |

### What's missing

1. **A general-purpose Linux distro** — Need to install Ubuntu or Debian via `wsl --install -d Ubuntu` to get a usable WSL2 environment
2. **Node.js** — Required for Claude Code CLI; needs a real distro first
3. **tmux** — Needs a real distro, then `apt install tmux`
4. **bash** — The docker-desktop distro only has `/bin/sh`

### Next steps (not performed)

1. Install a proper WSL2 distro: `wsl --install -d Ubuntu`
2. Inside that distro, install Node.js (via nvm or apt)
3. Install Claude Code CLI: `npm install -g @anthropic-ai/claude-code`
4. Install tmux: `sudo apt install tmux`
5. Re-run this test suite
