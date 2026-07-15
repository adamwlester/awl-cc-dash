// ============================================================================
// App frame — title bar, footer, resizable splitters (mirrors mockup DOM).
// ============================================================================

import React, { useCallback, useEffect, useState } from 'react'
import { useDash } from '../store'
import { Ic } from '../lib/icons'
import { fmtTokens, runStateOf, timeAgo } from '../lib/identity'

// ---- resizable splitter (ports initResizers from behavior.js) --------------
export function RzHandle({ orient }: { orient: 'h' | 'v' }) {
  const onDown = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    e.preventDefault()
    const h = e.currentTarget
    const horiz = orient === 'h'
    const prev = h.previousElementSibling as HTMLElement | null
    const next = h.nextElementSibling as HTMLElement | null
    if (!prev || !next) return
    const s = horiz ? e.clientX : e.clientY
    const pS = horiz ? prev.offsetWidth : prev.offsetHeight
    const nS = horiz ? next.offsetWidth : next.offsetHeight
    h.classList.add('dragging')
    document.body.style.cursor = horiz ? 'col-resize' : 'row-resize'
    document.body.style.userSelect = 'none'
    const ro = document.getElementById('rz-readout')
    const showReadout = (e2: MouseEvent | React.MouseEvent) => {
      if (!ro) return
      const pPx = horiz ? prev.offsetWidth : prev.offsetHeight
      const nPx = horiz ? next.offsetWidth : next.offsetHeight
      ro.innerHTML = `${Math.round(pPx)}px<span class="rz-ro-sep">${horiz ? '│' : '─'}</span>${Math.round(nPx)}px`
      ro.classList.add('show')
      const ow = ro.offsetWidth, oh = ro.offsetHeight, pad = 6
      let x = (e2 as MouseEvent).clientX + 14, y = (e2 as MouseEvent).clientY + 16
      if (x + ow + pad > window.innerWidth) x = (e2 as MouseEvent).clientX - ow - 14
      if (y + oh + pad > window.innerHeight) y = (e2 as MouseEvent).clientY - oh - 16
      ro.style.left = `${Math.max(pad, x)}px`
      ro.style.top = `${Math.max(pad, y)}px`
    }
    const mv = (e2: MouseEvent) => {
      const d = (horiz ? e2.clientX : e2.clientY) - s
      const p = Math.max(150, pS + d), n = Math.max(150, nS - d)
      prev.style.flex = `${p} 1 0`
      next.style.flex = `${n} 1 0`
      showReadout(e2)
    }
    showReadout(e)
    const up = () => {
      document.removeEventListener('mousemove', mv)
      document.removeEventListener('mouseup', up)
      h.classList.remove('dragging')
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      if (ro) ro.classList.remove('show')
    }
    document.addEventListener('mousemove', mv)
    document.addEventListener('mouseup', up)
  }, [orient])
  return <div className={`rz-handle ${orient === 'h' ? 'vstyle' : 'hstyle'}`} data-orient={orient} onMouseDown={onDown} />
}

// ---- title bar ---------------------------------------------------------------
const HB: Record<string, { cls: string; dot: string | null; label: string; title: string }> = {
  connected: { cls: 'hb-conn', dot: 'var(--success)', label: 'Connected', title: 'Sidecar link — Connected' },
  reconnecting: { cls: 'hb-reconnecting', dot: 'var(--warning)', label: 'Reconnecting', title: 'Sidecar link — feed dropped, auto-retrying' },
  offline: { cls: 'hb-offline', dot: 'var(--danger)', label: 'Offline', title: 'Sidecar unreachable — panels frozen on last-known values' },
  connecting: { cls: 'hb-connecting', dot: 'var(--muted-2)', label: 'Connecting', title: 'Sidecar link — connecting' },
}

export function TitleBar() {
  const d = useDash()
  const [clock, setClock] = useState('')
  useEffect(() => {
    const t = () => setClock(new Date().toLocaleTimeString('en-GB', { hour12: false }))
    t()
    const i = setInterval(t, 1000)
    return () => clearInterval(i)
  }, [])
  const hb = HB[d.linkState]
  const projName = d.projects?.open ? (d.projects.projects.find(p => p.open)?.name || d.projects.open.split(/[\\/]/).pop()) : 'No project'
  return (
    <header className="topbar">
      <div className="flex items-center gap-3 min-w-0">
        <span className="text-[13px] font-heading text-main-foreground tracking-tight" style={{ fontWeight: 900 }}>AWL Multi-Agent Dashboard</span>
        <span data-comp="chip" className="chip" style={{ fontFamily: 'var(--font-mono)' }}>v{d.healthVersion || '—'}</span>
        <span data-comp="active-project-chip" className="chip proj-chip" title="Active project — open Settings → Projects" onClick={() => d.openSettings('projects')}>
          <Ic name="folder-open" /><span className="proj-chip-nm">{projName}</span>
        </span>
        <span className="text-[11px] font-bold text-main-foreground" style={{ opacity: 0.8 }}>{d.sessions.length} agents</span>
      </div>
      <div className="flex items-center gap-2">
        <span data-comp="chip" className="chip" style={{ fontFamily: 'var(--font-mono)' }}>{clock}</span>
        <span data-comp="chip" className="chip">WSL2</span>
        <span data-comp="chip" className="chip">tmux</span>
        <span data-comp="connector-health-badge" className={`hbadge ${hb.cls}`} title={hb.title}>
          {hb.dot && <span className="hd" style={{ background: hb.dot }} />}{hb.label}
        </span>
        <button data-comp="settings-gear" className={`topbar-gear${d.settingsOpen ? ' on' : ''}`} title="Settings" onClick={() => (d.settingsOpen ? d.closeSettings() : d.openSettings())}>
          <Ic name="settings" />
        </button>
      </div>
    </header>
  )
}

// ---- footer --------------------------------------------------------------------
export function FootBar() {
  const d = useDash()
  const counts = { active: 0, idle: 0, pending: 0, error: 0 }
  for (const s of d.sessions) counts[runStateOf(s)]++
  const subCount = Object.values(d.subagentsBy).reduce((a, l) => a + l.length, 0)
  const linkCount = d.links.links.filter(l => l.active).length
  return (
    <footer className="footbar">
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 text-[10px] font-semibold text-muted">
          <span><b className="text-foreground">{d.sessions.length}</b> agents</span><span className="opacity-40">·</span>
          <span><b className="text-foreground">{subCount}</b> subagents</span><span className="opacity-40">·</span>
          <span><b className="text-foreground">{linkCount}</b> links</span><span className="opacity-40">·</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full" style={{ background: 'var(--success)', border: 'var(--border-width) solid var(--border)' }} />{counts.active} active</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full" style={{ background: 'var(--muted-2)', border: 'var(--border-width) solid var(--border)' }} />{counts.idle} idle</span>
          <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full" style={{ background: 'var(--warning)', border: 'var(--border-width) solid var(--border)' }} />{counts.pending} pending</span>
          {counts.error > 0 && <span className="flex items-center gap-1"><span className="w-3 h-3 rounded-full" style={{ background: 'var(--danger)', border: 'var(--border-width) solid var(--border)' }} />{counts.error} error</span>}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <span data-comp="token-pill" className="tok-pill" title="Token usage — full detail in Settings → Usage" style={{ cursor: 'pointer' }} onClick={() => d.openSettings('usage')}>Σ {fmtTokens(d.tokenPill)} tokens</span>
        <span className="text-[10px] font-mono font-semibold text-muted">{sessionAge(d.sessionStart, d.nowMs)}</span>
      </div>
    </footer>
  )
}

function sessionAge(start: number, now: number): string {
  const s = Math.max(0, Math.floor((now - start) / 1000))
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(Math.floor(s / 3600))}:${p(Math.floor((s % 3600) / 60))}:${p(s % 60)}`
}
