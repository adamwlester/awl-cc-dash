// ============================================================================
// AWL Multi-Agent Dashboard — the rebuilt renderer shell (§11 #37).
// ----------------------------------------------------------------------------
// Reproduces the design system's frame: title bar · three resizable columns
// (Agent | Team Graph / Library | Team Feed / Prompt) · status footer, with the
// Settings and Console step-into views. The mockup's fixed dev window is the
// one sanctioned divergence — the app fills its window (design/app.css).
// ============================================================================

import React from 'react'
import { DashProvider, useDash } from './store'
import { AgentSprite } from './lib/icons'
import { TitleBar, FootBar, RzHandle } from './components/frame'
import { TeamGraph } from './components/TeamGraph'
import { AgentPanel } from './components/AgentPanel'
import { TeamFeed } from './components/TeamFeed'
import { PromptPanel } from './components/PromptPanel'
import { Library } from './components/Library'
import { LinkDrawer } from './components/LinkDrawer'
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
