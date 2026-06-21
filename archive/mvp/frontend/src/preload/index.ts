const { contextBridge } = require('electron')

contextBridge.exposeInMainWorld('awl', {
  sidecarUrl: 'http://127.0.0.1:7691',
})
