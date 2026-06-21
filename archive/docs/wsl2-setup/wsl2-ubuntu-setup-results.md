---
source: claude
created: 2026-03-31
tags: [wsl2, ubuntu, setup, testing]
---

# WSL2 Ubuntu Setup Results — Phase 1

**Date:** 2026-03-31
**Run by:** claude-code-main (automated from Windows sandbox)

---

## Step 1: Install Ubuntu on WSL2

**Command:** `wsl --install -d Ubuntu`

**Result:** SUCCESS (with manual intervention)

- Ubuntu provisioned successfully on WSL2
- Initial install hung waiting for interactive user creation
- Workaround: terminated WSL, created user non-interactively via `useradd`, set default user via `/etc/wsl.conf`

**Verification:** `wsl -l -v`

```
  NAME                  STATE           VERSION
* Ubuntu                Running         2
  docker-desktop        Running         2
```

### Ubuntu Version

```
PRETTY_NAME="Ubuntu 24.04.4 LTS"
VERSION_ID="24.04"
VERSION="24.04.4 LTS (Noble Numbat)"
```

---

## Step 2: Set Ubuntu as Default WSL Distro

**Command:** `wsl --set-default Ubuntu`

**Result:** SUCCESS — Ubuntu marked as default (asterisk confirmed in `wsl -l -v`)

---

## Step 3: Install Node.js via nvm

**Commands:**
```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh | bash
nvm install --lts
```

**Result:** SUCCESS

| Component | Version |
|-----------|---------|
| nvm       | 0.40.3  |
| Node.js   | v24.14.1 (LTS) |
| npm       | 11.11.0 |

---

## Step 4: Install Claude Code CLI

**Command:** `npm install -g @anthropic-ai/claude-code`

**Result:** SUCCESS

| Component       | Version |
|-----------------|---------|
| Claude Code CLI | 2.1.87  |

**Note:** Authentication not attempted — requires interactive `claude` login by user.

---

## Step 5: Install tmux

**Command:** `sudo apt install -y tmux`

**Result:** SUCCESS (tmux was already bundled with Ubuntu 24.04)

| Component | Version |
|-----------|---------|
| tmux      | 3.4     |

tmux 3.4 >= 3.2 requirement for smux compatibility: **PASS**

---

## WSL User Configuration

| Setting        | Value   |
|----------------|---------|
| Unix username  | lester  |
| Default user   | lester (via /etc/wsl.conf) |
| Home directory | /home/lester |
| Shell          | /bin/bash |
| sudo access    | Yes (member of sudo group) |
| Password       | `lester` (set during automated creation — **change this**) |

---

## Errors / Notes

1. **`wsl --install -d Ubuntu` hung** — The install process blocks indefinitely waiting for interactive username/password input. All subsequent `wsl` commands also blocked until the install process was terminated. Workaround was to `wsl --shutdown`, then create the user via `useradd` as root.

2. **nvm not available via `bash -lc`** — nvm appends to `.bashrc` but WSL's non-interactive bash doesn't source it reliably. Must explicitly source `/home/lester/.nvm/nvm.sh` when running commands via `wsl -d Ubuntu -- bash -c '...'`.

3. **Password is trivial** — The user `lester` was created with password `lester` for automation purposes. Should be changed before any real use: `wsl -d Ubuntu -- bash -c 'passwd lester'`

---

## Phase 1 Status: COMPLETE

All components installed. **Next step:** User must manually authenticate Claude Code by running:

```bash
wsl
claude
```

Then follow the interactive auth flow. Do not proceed to Phase 2 until auth is confirmed.
