const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('awl', {
  sidecarUrl: 'http://127.0.0.1:7690',

  // §7.16 Assets thumbnails (decided mechanism): the main process renders a
  // real Shell thumbnail via nativeImage.createThumbnailFromPath, falling back
  // to app.getFileIcon. Returns a data: URL, or null when neither works.
  thumb: (absPath: string): Promise<string | null> => ipcRenderer.invoke('awl:thumb', absPath),

  // §3.4 styled close dialog (#50 upgrade): main asks the renderer to show the
  // in-app two-option dialog on window close. The immediate ack tells main the
  // renderer is alive — no ack means unresponsive, and main falls back to the
  // native dialog. The answer mirrors the native buttons:
  //   0 = Close · 1 = Close & stop agents · 2 = Cancel.
  onCloseRequest: (cb: () => void): void => {
    ipcRenderer.on('awl:close-request', () => {
      ipcRenderer.send('awl:close-ack')
      cb()
    })
  },
  // Main dismisses a stale styled dialog when it falls back to the native one
  // (a late ack past the grace window would otherwise leave dead buttons).
  onCloseCancel: (cb: () => void): void => {
    ipcRenderer.on('awl:close-cancel', () => cb())
  },
  answerClose: (choice: number): void => { ipcRenderer.send('awl:close-answer', choice) },
})
