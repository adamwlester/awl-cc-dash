// Standalone Vite dev server for the renderer (no Electron) — serves the UI over
// http://localhost so it can be driven in a browser for verification (the
// Playwright MCP browser blocks file:). With no Electron preload, window.awl is
// absent, so the renderer falls back to the sidecar at http://127.0.0.1:7690.
//   cd frontend && npx vite --config vite.standalone.config.mjs
import react from '@vitejs/plugin-react'

export default {
  plugins: [react()],
  root: 'src/renderer',
  server: { port: 5180, strictPort: true, host: '127.0.0.1' },
}
