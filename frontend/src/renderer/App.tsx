// ============================================================================
// AWL Multi-Agent Dashboard — the rebuilt renderer shell (§11 #37).
// ----------------------------------------------------------------------------
// Reproduces the design system's frame: title bar · three resizable columns
// (Agent | Team / Library | Feed / Prompt) · status footer, with the
// Settings and Console step-into views. The mockup's fixed dev window is the
// one sanctioned divergence — the app fills its window (design/app.css).
// ============================================================================

import React, { useEffect, useState } from 'react'
import { DashProvider, useDash } from './store'
import { AgentSprite, Ic } from './lib/icons'
import { TitleBar, FootBar, RzHandle } from './components/frame'
import { TeamGraph } from './components/TeamGraph'
import { AgentPanel } from './components/AgentPanel'
import { TeamFeed } from './components/TeamFeed'
import { PromptPanel } from './components/PromptPanel'
import { Library } from './components/Library'
import { LinkDrawer } from './components/LinkDrawer'
import { PastDrawer } from './components/PastDrawer'
import { SettingsView } from './components/SettingsView'
import { ConsoleView } from './components/Console'

function Shell() {
  const d = useDash()
  return (
    <div className={`app${d.linkState === 'offline' ? ' awl-offline' : ''}`}>
      <AgentSprite />
      <TitleBar />
      <div className="awl-stale-note">OFFLINE — panels frozen on last-known values</div>

      <div className="three">
        <div className="rz-group horizontal" id="rzMain">
          <AgentPanel />
          <RzHandle orient="h" />

          <div className="rz-panel" id="pMid" style={{ flex: '1 1 40%' }}>
            <div className="rz-group vertical" id="rzMid">
              <TeamGraph />
              <RzHandle orient="v" />
              <Library />
            </div>
          </div>

          <RzHandle orient="h" />

          <div className="rz-panel" id="pRight" style={{ flex: '1 1 36%', minWidth: 'var(--col-right-min)', maxWidth: 'var(--col-right-max)' }}>
            <LinkDrawer />
            <PastDrawer />
            <div className="rz-group vertical" id="rzRight">
              <TeamFeed />
              <RzHandle orient="v" />
              <PromptPanel />
            </div>
          </div>
        </div>
      </div>

      <FootBar />
      <div id="rz-readout" aria-hidden="true" />
      <SettingsView />
      <ConsoleView />
      <AppCloseDialog />
    </div>
  )
}

// ---- §3.4 app-quit dialog — the STYLED two-option close confirm (#50) -------
// Electron main intercepts window close and asks here over IPC (preload
// `onCloseRequest`); the answer mirrors the native buttons (0 Close · 1 Close &
// stop agents · 2 Cancel). Reuses the Settings→Projects `project-close-confirm`
// component styling, centered as the app-quit variant. Esc / ghost-x cancel.
function AppCloseDialog() {
  const d = useDash()
  const [open, setOpen] = useState(false)
  useEffect(() => {
    const awl = (window as any).awl
    if (awl?.onCloseRequest) awl.onCloseRequest(() => setOpen(true))
    // Main falls back to the native dialog when the ack arrives too late —
    // dismiss the styled one so two dialogs never fight (its answers would be
    // dead: main stopped listening when it settled the fallback).
    if (awl?.onCloseCancel) awl.onCloseCancel(() => setOpen(false))
  }, [])
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.stopPropagation(); answer(2) } }
    document.addEventListener('keydown', onKey, true)
    return () => document.removeEventListener('keydown', onKey, true)
  }, [open])
  const answer = (choice: number) => { setOpen(false); (window as any).awl?.answerClose?.(choice) }
  if (!open) return null
  const projName = d.projects?.projects.find(p => p.open)?.name
  return (
    <div className="awl-quit-overlay" role="dialog" aria-label="Close the dashboard">
      <div data-comp="project-close-confirm" className="proj-close-confirm show awl-quit-box" role="group" aria-label="Close confirm">
        <div className="proj-cc-head"><Ic name="alert-triangle" /><span>Close the dashboard{projName ? ` — ${projName} is open` : ''}?</span>
          <button data-comp="ghost-icon-button" className="ghost-ic" title="Cancel (Esc)" onClick={() => answer(2)}><Ic name="x" /></button></div>
        <div className="proj-opt">
          <button data-comp="button" className="btn-main btn-sm" onClick={() => answer(0)}><Ic name="x-circle" className="w-3 h-3" />Close</button>
          <span className="proj-opt-note">Agents keep running detached in tmux — all state is already saved.</span>
        </div>
        <div className="proj-opt">
          <button data-comp="button" className="btn-danger btn-sm" onClick={() => answer(1)}><Ic name="square" className="w-3 h-3" />Close &amp; stop agents</button>
          <span className="proj-opt-note">Ends the open project&#8217;s agent sessions gracefully first.</span>
        </div>
      </div>
    </div>
  )
}

export function App() {
  return (
    <DashProvider>
      <Shell />
    </DashProvider>
  )
}
