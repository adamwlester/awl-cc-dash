// Use require() directly for Electron CJS compatibility
const { app, BrowserWindow, dialog, ipcMain, nativeImage, Menu } = require('electron')
const { join } = require('path')
import type { BrowserWindow as BrowserWindowType, Event as ElectronEvent } from 'electron'
import { ensureSidecar, requestGracefulStop, sidecarSummary, stopOwnedSidecar } from './sidecar'

// One-click launch (§11 #20): Electron main owns the sidecar lifecycle — see
// ./sidecar.ts. Close semantics per ARCHITECTURE §3.4. The close dialog is the
// STYLED in-app one first (§50): main asks the renderer over IPC and acts on
// its answer; the native dialog stays the fallback when the renderer is
// unresponsive (no ack) or the send fails. Choices (both surfaces):
//   0 Close              → quit; terminate the OWNED sidecar child only. Detached
//                          WSL tmux agents keep running — that is the point
//                          (Read-back A of tests/test_oneclick_launch_live.py).
//                          An ADOPTED (pre-existing) sidecar is never killed.
//   1 Close & stop agents→ first invoke the sidecar's graceful-stop path
//                          (POST /projects/close {stop_agents:true}; a 409 "no
//                          project open" is tolerated), then quit as above.
//   2 Cancel             → abort the close.
let quitConfirmed = false
let closeDialogOpen = false

/** Ask the renderer to run the styled §3.4 close dialog. Resolves the choice,
 *  or null when the renderer is unresponsive (no ack within the grace window)
 *  — the caller then falls back to the native dialog. Once acked, the answer
 *  is waited on without a timeout (the user is deliberating in the styled UI)
 *  — BUT a renderer that acked and then reloaded or crashed can never answer,
 *  so those events rescue to null too; without that, closeDialogOpen would
 *  stay latched and every later close would be swallowed forever. */
function askRendererClose(win: BrowserWindowType): Promise<number | null> {
  return new Promise((resolve) => {
    let acked = false
    let settled = false
    const wc = win.webContents
    const settle = (v: number | null) => {
      if (settled) return
      settled = true
      cleanup()
      resolve(v)
    }
    const onAck = () => { acked = true }
    const onAnswer = (_e: unknown, choice: unknown) =>
      settle(typeof choice === 'number' && choice >= 0 && choice <= 2 ? choice : 2)
    const onGone = () => settle(null)   // reload / crash — the dialog's state is gone
    const cleanup = () => {
      ipcMain.removeListener('awl:close-ack', onAck)
      ipcMain.removeListener('awl:close-answer', onAnswer)
      try {
        wc.removeListener('render-process-gone', onGone)
        wc.removeListener('did-navigate', onGone)
        wc.removeListener('destroyed', onGone)
      } catch { /* webContents may already be destroyed */ }
    }
    ipcMain.on('awl:close-ack', onAck)
    ipcMain.on('awl:close-answer', onAnswer)
    wc.on('render-process-gone', onGone)
    wc.on('did-navigate', onGone)
    wc.on('destroyed', onGone)
    try {
      wc.send('awl:close-request')
    } catch {
      settle(null); return
    }
    setTimeout(() => { if (!acked) settle(null) }, 450)
  })
}

async function resolveCloseChoice(win: BrowserWindowType): Promise<number> {
  // Smoke seam: AWL_SMOKE_CLOSE='0'|'1'|'2' resolves the dialog choice without
  // native UI so the close path can be driven unattended (used by the in-lane
  // smoke; the full interactive dialog drive rides the phase-3 e2e).
  const smoke = process.env.AWL_SMOKE_CLOSE
  if (smoke === '0' || smoke === '1' || smoke === '2') return Number(smoke)
  // Styled in-app dialog first; null = renderer unresponsive → native fallback.
  const styled = await askRendererClose(win)
  if (styled !== null) return styled
  // A late ack (renderer main thread was blocked past the grace window) could
  // otherwise leave a zombie styled dialog whose answers nobody listens to —
  // tell the renderer to dismiss before the native dialog takes over.
  try { win.webContents.send('awl:close-cancel') } catch { /* window going away */ }
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
    // #38: two floors. 1440 is the no-scroll layout floor (pinned 400 + 340
    // middle-min + pinned 700); minWidth 1180 is the usable-with-inner-scroll
    // floor so small laptops can still open the window — between 1180 and 1440
    // the app.css horizontal-scroll guard covers it rather than breaking layout.
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

  // Default menu removed product-wide (Menu.setApplicationMenu(null) below) —
  // its role accelerators went with it, so the dev loop keeps its devtools +
  // reload keys via this dev-gated shim (ELECTRON_RENDERER_URL = electron-vite
  // dev, the same discriminator the loader below uses).
  if (process.env.ELECTRON_RENDERER_URL) {
    win.webContents.on('before-input-event', (_e: ElectronEvent, input: { type: string; key: string; control: boolean; shift: boolean }) => {
      if (input.type !== 'keyDown') return
      const key = (input.key || '').toLowerCase()
      if (key === 'f12' || (input.control && input.shift && key === 'i')) win.webContents.toggleDevTools()
      else if (input.control && !input.shift && key === 'r') win.webContents.reload()
    })
  }

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

// §7.16 Assets thumbnails — the decided mechanism (docs/ARCHITECTURE.md §7.16):
// Electron's nativeImage.createThumbnailFromPath (the Windows Shell thumbnail
// provider) with app.getFileIcon() as the file-type-icon fallback. Returns a
// data: URL string, or null when neither source can render the path.
ipcMain.handle('awl:thumb', async (_e: unknown, absPath: unknown): Promise<string | null> => {
  if (typeof absPath !== 'string' || !absPath.trim()) return null
  try {
    const img = await nativeImage.createThumbnailFromPath(absPath, { width: 96, height: 96 })
    if (img && !img.isEmpty()) return img.toDataURL()
  } catch { /* not thumbnailable (non-image, missing codec, …) — fall through */ }
  try {
    const icon = await app.getFileIcon(absPath, { size: 'normal' })
    if (icon && !icon.isEmpty()) return icon.toDataURL()
  } catch { /* no icon either */ }
  return null
})

app.whenReady().then(() => {
  // The default File/Edit/View/Window/Help strip is gone product-wide; the
  // dev-gated before-input-event shim in createWindow() keeps F12/Ctrl+Shift+I
  // (devtools) and Ctrl+R (reload) alive for the dev loop.
  Menu.setApplicationMenu(null)
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
