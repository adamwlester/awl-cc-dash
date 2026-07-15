import React from 'react'
import { createRoot } from 'react-dom/client'
// Fonts — Archivo (heading 800 / body 500) + JetBrains Mono, bundled offline.
import '@fontsource/archivo/400.css'
import '@fontsource/archivo/500.css'
import '@fontsource/archivo/600.css'
import '@fontsource/archivo/700.css'
import '@fontsource/archivo/800.css'
import '@fontsource/archivo/900.css'
import '@fontsource/jetbrains-mono/400.css'
import '@fontsource/jetbrains-mono/500.css'
import '@fontsource/jetbrains-mono/600.css'
// Design system (verbatim copies) + Tailwind layer + renderer shims — this
// order mirrors the mockup's cascade (tokens → utilities → styles.css).
import './design/tokens.css'
import './index.css'
import './design/styles.css'
import './design/app.css'
import { App } from './App'

const root = createRoot(document.getElementById('root')!)
root.render(<App />)
