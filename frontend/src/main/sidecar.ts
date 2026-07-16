// Sidecar lifecycle — one-click launch (ARCHITECTURE §2 / §4.1 / §11 #20).
//
// Electron main owns the FastAPI sidecar's spawn / shutdown. On startup we
// probe :7690 — if a sidecar is already up we ADOPT it (never spawn a second,
// and NEVER kill an adopted sidecar on close); if it is down, we SPAWN one as
// a supervised child using the same invocation start-dashboard.bat uses:
// python running sidecar/main.py (which binds uvicorn on :7690 itself),
// preferring the repo-root .venv interpreter and falling back to PATH python
// exactly like the .bat. start-dashboard.bat stays the documented fallback.
//
// Lifecycle contract (proven live by tests/test_oneclick_launch_live.py):
//   Read-back A — detached WSL tmux agents SURVIVE the sidecar child's death;
//   Read-back B — a respawned sidecar's reconnect_sessions() rebinds them.
// Killing the owned child on app close is therefore safe by construction:
// agents live under WSL's process tree, never under the sidecar's Windows one.
//
// Crash-restart supervision is deliberately NOT built (§2's manual-relaunch
// posture): if the owned child dies we log it and let the renderer's /health
// failure handling surface it; relaunching the app respawns the sidecar and
// its reconnect_sessions() rebinds the surviving agents (Read-back B).

import { spawn, spawnSync, type ChildProcess } from 'child_process'
import * as fs from 'fs'
import * as http from 'http'
import * as path from 'path'

export const SIDECAR_URL = 'http://127.0.0.1:7690'

const HEALTH_PROBE_TIMEOUT_MS = 1500
// A cold sidecar import + uvicorn bind can take a while on a busy machine —
// the Python lifecycle spike allows 150 s; stay in that ballpark.
const BIND_WAIT_MS = 120_000
// Graceful stop walks every running agent (driver.stop() each) — be generous.
const GRACEFUL_STOP_TIMEOUT_MS = 45_000

export type SidecarMode = 'none' | 'adopted' | 'owned' | 'failed'

let mode: SidecarMode = 'none'
let owned: ChildProcess | null = null
let ownedLogPath: string | null = null
let stopRequested = false

/** One-line state description for logs and the smoke drive. */
export function sidecarSummary(): string {
  switch (mode) {
    case 'adopted':
      return `adopted (already running at ${SIDECAR_URL}; not owned, never killed)`
    case 'owned':
      return `owned child pid=${owned?.pid} (log: ${ownedLogPath})`
    case 'failed':
      return `failed to start${ownedLogPath ? ` (log: ${ownedLogPath})` : ''} — fallback: start-dashboard.bat`
    default:
      return 'none'
  }
}

/** GET /health with a short timeout; false on any error/timeout. */
export function probeHealth(timeoutMs: number = HEALTH_PROBE_TIMEOUT_MS): Promise<boolean> {
  return new Promise((resolve) => {
    const req = http.get(`${SIDECAR_URL}/health`, { timeout: timeoutMs }, (res) => {
      res.resume()
      resolve(res.statusCode === 200)
    })
    req.on('timeout', () => {
      req.destroy()
      resolve(false)
    })
    req.on('error', () => resolve(false))
  })
}

function looksLikeRepoRoot(dir: string): boolean {
  return fs.existsSync(path.join(dir, 'sidecar', 'main.py'))
}

/**
 * Resolve the repo root: AWL_REPO_ROOT env override first, then walk up from
 * each candidate dir (dev layout: frontend/ sits directly under the repo root,
 * which contains sidecar/ and usually .venv).
 */
export function resolveRepoRoot(candidateDirs: string[]): string | null {
  const override = process.env.AWL_REPO_ROOT
  if (override) {
    if (looksLikeRepoRoot(override)) return path.resolve(override)
    console.warn(`[awl] AWL_REPO_ROOT=${override} has no sidecar/main.py — ignoring override`)
  }
  for (const start of candidateDirs) {
    let dir = path.resolve(start)
    for (let i = 0; i < 10; i++) {
      if (looksLikeRepoRoot(dir)) return dir
      const parent = path.dirname(dir)
      if (parent === dir) break
      dir = parent
    }
  }
  return null
}

/** Prefer the repo .venv interpreter; fall back to PATH python (like the .bat). */
function resolvePython(repoRoot: string): string {
  const venvPython =
    process.platform === 'win32'
      ? path.join(repoRoot, '.venv', 'Scripts', 'python.exe')
      : path.join(repoRoot, '.venv', 'bin', 'python')
  return fs.existsSync(venvPython) ? venvPython : 'python'
}

/**
 * Adopt-or-spawn. Returns the resulting mode. Never throws — a sidecar that
 * cannot start must not take the window down with it (the renderer's /health
 * handling shows the gap, and start-dashboard.bat remains the fallback).
 */
export async function ensureSidecar(candidateDirs: string[]): Promise<SidecarMode> {
  if (await probeHealth()) {
    mode = 'adopted'
    console.log(`[awl] adopted running sidecar at ${SIDECAR_URL} — it will not be killed on close`)
    return mode
  }

  const repoRoot = resolveRepoRoot(candidateDirs)
  if (!repoRoot) {
    mode = 'failed'
    console.error(
      `[awl] cannot resolve the repo root (no sidecar/main.py above: ${candidateDirs.join(' | ')}). ` +
        'Set AWL_REPO_ROOT or launch via start-dashboard.bat.'
    )
    return mode
  }

  const python = resolvePython(repoRoot)
  const scratch = path.join(repoRoot, '.scratch')
  let child: ChildProcess
  try {
    fs.mkdirSync(scratch, { recursive: true })
    const stamp = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19)
    ownedLogPath = path.join(scratch, `sidecar-electron-${stamp}.log`)
    const logFd = fs.openSync(ownedLogPath, 'w')
    child = spawn(python, ['main.py'], {
      cwd: path.join(repoRoot, 'sidecar'),
      env: { ...process.env, PYTHONIOENCODING: 'utf-8' },
      stdio: ['ignore', logFd, logFd], // pipe to a file so the pipe never fills and blocks the child
      windowsHide: true,
    })
    child.on('exit', (code, signal) => {
      try {
        fs.closeSync(logFd)
      } catch {
        /* already closed */
      }
      // §2 manual-relaunch posture: log, never auto-restart.
      console.log(`[awl] owned sidecar child exited (code=${code} signal=${signal})`)
    })
    child.on('error', (err) => {
      console.error(`[awl] sidecar spawn error: ${err.message}`)
    })
  } catch (err) {
    mode = 'failed'
    console.error(`[awl] failed to spawn sidecar (${python} main.py): ${(err as Error).message}`)
    return mode
  }

  owned = child
  mode = 'owned'
  console.log(`[awl] spawned sidecar child pid=${child.pid} (${python} main.py) — log: ${ownedLogPath}`)

  const bound = await waitForBind(child)
  if (!bound) {
    if (child.exitCode !== null || child.signalCode !== null) {
      mode = 'failed'
      owned = null
      console.error(`[awl] sidecar child died before binding :7690 — see ${ownedLogPath}`)
    } else {
      // Still running but not answering yet: keep ownership (close will still
      // terminate it); the renderer shows the /health gap meanwhile.
      console.warn(`[awl] sidecar child not answering /health after ${BIND_WAIT_MS} ms — see ${ownedLogPath}`)
    }
  }
  return mode
}

/** Poll /health until the child binds; abort early if the child dies. */
async function waitForBind(child: ChildProcess, timeoutMs: number = BIND_WAIT_MS): Promise<boolean> {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (child.exitCode !== null || child.signalCode !== null) return false
    if (await probeHealth()) return true
    await new Promise((r) => setTimeout(r, 1000))
  }
  return false
}

/**
 * The §3.4 "Close & stop agents" first half: ask the sidecar to gracefully
 * stop the open project's agents via POST /projects/close {stop_agents:true}.
 * A 409 (no project open — nothing to stop) and an unreachable sidecar are
 * both tolerated: this is best-effort, and the caller terminates afterwards
 * regardless. Resolves when the sidecar answers or the timeout passes.
 */
export function requestGracefulStop(timeoutMs: number = GRACEFUL_STOP_TIMEOUT_MS): Promise<void> {
  return new Promise((resolve) => {
    const body = JSON.stringify({ stop_agents: true })
    const req = http.request(
      `${SIDECAR_URL}/projects/close`,
      {
        method: 'POST',
        headers: {
          'content-type': 'application/json',
          'content-length': Buffer.byteLength(body),
        },
        timeout: timeoutMs,
      },
      (res) => {
        res.resume()
        res.on('end', () => {
          console.log(`[awl] graceful stop: POST /projects/close → ${res.statusCode}`)
          resolve()
        })
      }
    )
    req.on('timeout', () => {
      req.destroy()
      resolve()
    })
    req.on('error', () => resolve()) // sidecar down/unreachable — nothing to stop
    req.end(body)
  })
}

/**
 * Terminate the OWNED sidecar child — kill its whole Windows process tree
 * (taskkill /t /f), because a plain child.kill() would leave grandchildren.
 * Detached WSL tmux agents survive by construction (Read-back A): they are
 * not part of this tree. No-op when the sidecar was adopted or never spawned;
 * idempotent (safe to call again from the app 'quit' last-resort hook).
 */
export function stopOwnedSidecar(): void {
  const child = owned
  if (stopRequested) return // one-shot: the quit hook may re-enter before the kill registers
  if (!child || child.pid === undefined || child.exitCode !== null || child.signalCode !== null) return
  stopRequested = true
  console.log(`[awl] terminating owned sidecar child pid=${child.pid}`)
  if (process.platform === 'win32') {
    spawnSync('taskkill', ['/pid', String(child.pid), '/t', '/f'], { windowsHide: true })
  } else {
    child.kill('SIGTERM')
  }
}
