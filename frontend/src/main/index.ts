// Use require() directly for Electron CJS compatibility
const { app, BrowserWindow, dialog } = require('electron')
const { join } = require('path')
import type { BrowserWindow as BrowserWindowType, Event as ElectronEvent } from 'electron'
import { ensureSidecar, requestGracefulStop, sidecarSummary, stopOwnedSidecar } from './sidecar'

// One-click launch (§11 #20): Electron main owns the sidecar lifecycle — see
// ./sidecar.ts. Close semantics per ARCHITECTURE §3.4, served here as a native
// dialog (the accepted v1 surface; the styled in-app dialog rides the #50
// design work):
//   Close              → quit; terminate the OWNED sidecar child only. Detached
//                        WSL tmux agents keep running — that is the point
//                        (Read-back A of tests/test_oneclick_launch_live.py).
//                        An ADOPTED (pre-existing) sidecar is never killed.
//   Close & stop agents→ first invoke the sidecar's graceful-stop path
//                        (POST /projects/close {stop_agents:true}; a 409 "no
//                        project open" is tolerated), then quit as above.
//   Cancel             → abort the close.
let quitConfirmed = false
let closeDialogOpen = false

async function resolveCloseChoice(win: BrowserWindowType): Promise<number> {
  // Smoke seam: AWL_SMOKE_CLOSE='0'|'1'|'2' resolves the dialog choice without
  // native UI so the close path can be driven unattended (used by the in-lane
  // smoke; the full interactive dialog drive rides the phase-3 e2e).
  const smoke = process.env.AWL_SMOKE_CLOSE
  if (smoke === '0' || smoke === '1' || smoke === '2') return Number(smoke)
  const { response } = await dialog.showMessageBox(win, {
    type: 'question',
    title: 'Close AWL Dashboard',
    message: 'Close the dashboard?',
    detail:
      'Close: the dashboard lets go — agents keep running detached in tmux, and all state is already saved.\n\n' +
      'Close & stop agents: also end the open project’s tmux sessions gracefully first.',
    buttons: ['Close', 'Close & stop agents', 'Cancel'],
    defaultId: 0,
    cancelId: 2,
    noLink: true,
  })
  return response
}

async function handleCloseRequest(win: BrowserWindowType): Promise<void> {
  closeDialogOpen = true
  try {
    const choice = await resolveCloseChoice(win)
    if (choice === 2) return // Cancel — abort the close
    if (choice === 1) await requestGracefulStop() // Close & stop agents (§3.4 second option)
    stopOwnedSidecar() // kills the owned child's process tree; no-op when adopted/none
    quitConfirmed = true
    win.destroy()
    app.quit()
  } finally {
    closeDialogOpen = false
  }
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1440,
    height: 900,
    // #38: the pinned side columns (400 + 700) plus the middle floor need ~1180px;
    // below that the layout horizontal-scrolls (app.css guard) rather than breaking.
    minWidth: 1180,
    minHeight: 600,
    title: 'AWL Multi-Agent Dashboard',
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
    backgroundColor: '#fef6e4', // --background (cream canvas) — matches the rebuilt renderer
  })

  // Intercept close: the §3.4 dialog decides detach vs graceful-stop vs cancel.
  win.on('close', (event: ElectronEvent) => {
    if (quitConfirmed) return
    event.preventDefault()
    if (closeDialogOpen) return
    void handleCloseRequest(win)
  })

  if (process.env.ELECTRON_RENDERER_URL) {
    win.loadURL(process.env.ELECTRON_RENDERER_URL)
  } else {
    win.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

app.whenReady().then(() => {
  createWindow()
  // Own the sidecar (adopt-or-spawn) without blocking the window — the
  // renderer's /health handling covers the gap while a cold sidecar binds.
  void ensureSidecar([app.getAppPath(), __dirname]).then(() => {
    console.log(`[awl] sidecar: ${sidecarSummary()}`)
    if (process.env.AWL_SMOKE_CLOSE !== undefined) {
      // Smoke seam: once the sidecar settles, auto-drive the close path.
      setTimeout(() => BrowserWindow.getAllWindows()[0]?.close(), 1500)
    }
  })
})

app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit() })
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow() })

// Last-resort cleanup on any quit path — idempotent, never touches an adopted sidecar.
app.on('quit', () => stopOwnedSidecar())
