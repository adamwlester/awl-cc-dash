// Use require() directly for Electron CJS compatibility
const { app, BrowserWindow } = require('electron')
const { join } = require('path')

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

  if (process.env.ELECTRON_RENDERER_URL) {
    win.loadURL(process.env.ELECTRON_RENDERER_URL)
  } else {
    win.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

app.whenReady().then(createWindow)
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit() })
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow() })
