// Standalone Vite config — serves ONLY the renderer over http://localhost for
// browser-based verification (Playwright MCP blocks file:). This is a dev aid,
// not part of the Electron app: `npm run dev` / `npm run build` use
// electron.vite.config.ts and do not read this file. In a plain browser
// window.awl is undefined, so api.ts falls back to the sidecar at
// http://127.0.0.1:7690 (CORS is open).
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  root: 'src/renderer',
  plugins: [react()],
  server: { port: 5199, strictPort: true },
})
