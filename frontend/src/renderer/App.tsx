// ============================================================================
// AWL Multi-Agent Dashboard — the three-pane shell
// ----------------------------------------------------------------------------
// Title bar · three resizable columns (Agent | Team Graph/Library | Team
// Feed/Prompt) · status footer. Owns the global state + polling and wires the
// proven bridge endpoints into the panels. Selection drives the app: clicking a
// Team Graph card focuses that agent in the Agent panel, Feed, and Prompt.
//
// Honest scope: Library (middle-bottom) is a placeholder (needs file endpoints);
// the Console tab, Scratch/Log feeds, the non-Permission Inbox sections, linking,
// send-timing, and Settings are absent (each needs net-new backend) — see the
// per-panel notes. Everything rendered is backed by a proven endpoint.
// ============================================================================

import React, { useCallback, useEffect, useRef, useState } from 'react'
import { C, FONT, timeAgo } from './tokens'
import { api, type Session, type SDKEvent, type ContextUsage, type CreatePayload } from './api'
import { Splitter } from './Splitter'
import { TeamGraph } from './TeamGraph'
import { AgentPanel } from './AgentPanel'
import { TeamFeed } from './TeamFeed'
import { PromptPanel } from './PromptPanel'

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v))

function fmtTokens(n: number): string {
  if (n >= 1e6) return `${(n / 1e6).toFixed(2)}M`
  if (n >= 1e3) return `${(n / 1e3).toFixed(1)}K`
  return String(n)
}

function Chip({ children, bg, fg }: { children: React.ReactNode; bg: string; fg: string }) {
  return (
    <span style={{ fontSize: 9.5, fontWeight: 800, padding: '2px 8px', borderRadius: 5, background: bg, color: fg, border: `2px solid ${C.border}`, whiteSpace: 'nowrap' }}>
      {children}
    </span>
  )
}

export function App() {
  const [sessions, setSessions] = useState<Session[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [events, setEvents] = useState<SDKEvent[]>([])
  const [ctx, setCtx] = useState<ContextUsage | null>(null)
  const [usageBy, setUsageBy] = useState<Record<string, { percent: number | null; work_steps: number | null }>>({})
  const [subagentsBy, setSubagentsBy] = useState<Record<string, any[]>>({})
  const [tokenPill, setTokenPill] = useState(0)
  const [health, setHealth] = useState<{ ok: boolean; version: string }>({ ok: false, version: '' })
  const [agentTab, setAgentTab] = useState<'details' | 'create'>('details')
  const [creating, setCreating] = useState(false)
  const [nowMs, setNowMs] = useState(Date.now())
  const mountedAt = useRef(Date.now())
  const sessionsRef = useRef<Session[]>([])
  sessionsRef.current = sessions

  // Resizable layout sizes (px); middle column + bottom panels flex.
  const [leftW, setLeftW] = useState(330)
  const [rightW, setRightW] = useState(440)
  const [graphH, setGraphH] = useState(360)
  const [feedH, setFeedH] = useState(320)

  const selected = sessions.find(s => s.session_id === selectedId) || null

  // ---- "ago" tick ----------------------------------------------------------
  useEffect(() => {
    const i = setInterval(() => setNowMs(Date.now()), 1000)
    return () => clearInterval(i)
  }, [])

  // ---- health --------------------------------------------------------------
  useEffect(() => {
    const check = async () => {
      const h = await api.health()
      setHealth({ ok: !!h, version: h?.version || '' })
    }
    check()
    const i = setInterval(check, 5000)
    return () => clearInterval(i)
  }, [])

  // ---- roster + usage (all agents) -----------------------------------------
  useEffect(() => {
    let cancelled = false
    const poll = async () => {
      const [ss, us] = await Promise.all([api.sessions(), api.usage()])
      if (cancelled) return
      if (ss) setSessions(ss)
      if (us) {
        const by: Record<string, { percent: number | null; work_steps: number | null }> = {}
        for (const a of us.agents) by[a.session_id] = { percent: a.percent, work_steps: a.work_steps }
        setUsageBy(by)
        setTokenPill(us.token_pill || 0)
      }
    }
    poll()
    const i = setInterval(poll, 2000)
    return () => { cancelled = true; clearInterval(i) }
  }, [])

  // ---- subagents (all agents) — slower cadence so the per-agent read_log
  // fan-out doesn't pile onto the 2s roster/usage poll and saturate the
  // sidecar's WSL-subprocess thread pool (each read_log spawns wsl.exe).
  useEffect(() => {
    let cancelled = false
    const poll = async () => {
      const ss = sessionsRef.current
      if (!ss.length) { setSubagentsBy({}); return }
      const entries = await Promise.all(
        ss.map(async s => [s.session_id, (await api.subagents(s.session_id))?.subagents || []] as const)
      )
      if (!cancelled) setSubagentsBy(Object.fromEntries(entries))
    }
    poll()
    const i = setInterval(poll, 4500)
    return () => { cancelled = true; clearInterval(i) }
  }, [])

  // Clear a stale selection if the agent vanished (retired elsewhere).
  useEffect(() => {
    if (selectedId && sessions.length && !sessions.some(s => s.session_id === selectedId)) {
      setSelectedId(null)
    }
  }, [sessions, selectedId])

  // ---- focused agent: message stream + context -----------------------------
  useEffect(() => {
    if (!selectedId) { setEvents([]); setCtx(null); return }
    let cancelled = false
    const loop = async () => {
      while (!cancelled) {
        const [hist, c] = await Promise.all([api.history(selectedId), api.context(selectedId)])
        if (cancelled) break
        if (hist) setEvents(hist)
        setCtx(c)
        await new Promise(r => setTimeout(r, 900))
      }
    }
    loop()
    return () => { cancelled = true }
  }, [selectedId])

  // ---- handlers ------------------------------------------------------------
  const onCreate = useCallback(async (payload: CreatePayload) => {
    setCreating(true)
    const s = await api.create(payload)
    setCreating(false)
    if (s) {
      // Optimistically add to the roster so the "clear stale selection" effect
      // doesn't immediately drop this freshly-selected agent before the next
      // roster poll catches up (a race that left the new agent unselected).
      setSessions(prev => prev.some(x => x.session_id === s.session_id) ? prev : [...prev, s])
      setSelectedId(s.session_id); setAgentTab('details'); setEvents([])
    }
  }, [])

  const onRetire = useCallback(async () => {
    if (!selectedId) return
    await api.retire(selectedId)
    setSelectedId(null)
  }, [selectedId])

  const onSend = useCallback(async (prompt: string) => {
    if (!selectedId) return
    await api.send(selectedId, prompt)
  }, [selectedId])

  const onStop = useCallback(async () => { if (selectedId) await api.interrupt(selectedId) }, [selectedId])
  const onSetModel = useCallback(async (m: string) => { if (selectedId && m) await api.setModel(selectedId, m) }, [selectedId])
  const onSetEffort = useCallback(async (e: string) => { if (selectedId) await api.setEffort(selectedId, e) }, [selectedId])
  const onAnswer = useCallback(async (id: string, approve: boolean) => { await api.answerPermission(id, approve) }, [])

  // ---- footer counts -------------------------------------------------------
  const subCount = Object.values(subagentsBy).reduce((a, l) => a + l.length, 0)
  const active = sessions.filter(s => s.status === 'running' && !s.has_pending_permission).length
  const pending = sessions.filter(s => s.has_pending_permission).length
  const errored = sessions.filter(s => s.status === 'error').length
  const idle = sessions.length - active - pending - errored

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', background: C.bg, color: C.t1, fontFamily: FONT, overflow: 'hidden' }}>
      {/* ===== Title bar ===== */}
      <div style={{ height: 36, minHeight: 36, background: C.main, borderBottom: `2px solid ${C.border}`, display: 'flex', alignItems: 'center', padding: '0 14px', gap: 10, flexShrink: 0 }}>
        <span style={{ fontSize: 13, fontWeight: 900, color: C.mainFg }}>AWL Multi-Agent Dashboard</span>
        <Chip bg={C.card} fg={C.t1}>v{health.version || '0.3'}</Chip>
        <Chip bg={C.card} fg={C.t1}>{sessions.length} agents</Chip>
        <div style={{ flex: 1 }} />
        <Chip bg={C.card} fg={C.t3}>{new Date(nowMs).toLocaleTimeString()}</Chip>
        <Chip bg={C.card} fg={C.t3}>WSL2</Chip>
        <Chip bg={C.card} fg={C.t3}>tmux</Chip>
        {health.ok
          ? <Chip bg={C.successSoft} fg={C.successText}>● Connected</Chip>
          : <Chip bg={C.dangerSoft} fg={C.danger}>● Sidecar offline</Chip>}
      </div>

      {/* ===== Body: three columns ===== */}
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0 }}>
        {/* Left — Agent panel */}
        <div style={{ width: leftW, flexShrink: 0, borderRight: 'none', overflow: 'hidden' }}>
          <AgentPanel session={selected} ctx={ctx} tab={agentTab} onTab={setAgentTab}
            onSetModel={onSetModel} onSetEffort={onSetEffort} onRetire={onRetire}
            onCreate={onCreate} creating={creating} nowMs={nowMs} />
        </div>
        <Splitter orientation="vertical" onDelta={(d) => setLeftW(w => clamp(w + d, 240, 560))} />

        {/* Middle — Team Graph over Library placeholder */}
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ height: graphH, flexShrink: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <div style={{ height: 34, minHeight: 34, background: C.surface, borderBottom: `2px solid ${C.border}`, display: 'flex', alignItems: 'center', padding: '0 10px', flexShrink: 0 }}>
              <span style={{ fontSize: 11, fontWeight: 800, color: C.t1, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Team Graph</span>
            </div>
            <TeamGraph sessions={sessions} usageBy={usageBy} subagentsBy={subagentsBy as any}
              selectedId={selectedId} onSelect={(id) => { setSelectedId(id); setAgentTab('details') }} nowMs={nowMs} />
          </div>
          <Splitter orientation="horizontal" onDelta={(d) => setGraphH(h => clamp(h + d, 150, 900))} />
          <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <div style={{ height: 34, minHeight: 34, background: C.surface, borderBottom: `2px solid ${C.border}`, display: 'flex', alignItems: 'center', padding: '0 10px', flexShrink: 0 }}>
              <span style={{ fontSize: 11, fontWeight: 800, color: C.t1, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Library</span>
            </div>
            <div style={{ flex: 1, overflow: 'auto', padding: 16, background: C.bg, color: C.t5, fontSize: 11, lineHeight: 1.6 }}>
              <b style={{ color: C.t3 }}>Plans · Documents · Assets</b> — not built this run.<br />
              The Library needs net-new file endpoints (read/edit plan &amp; doc files, the review side-store, asset media). Surfaced here, deliberately deferred.
            </div>
          </div>
        </div>
        <Splitter orientation="vertical" onDelta={(d) => setRightW(w => clamp(w - d, 320, 720))} />

        {/* Right — Team Feed over Prompt */}
        <div style={{ width: rightW, flexShrink: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ height: feedH, flexShrink: 0, overflow: 'hidden' }}>
            <TeamFeed session={selected} events={events} sessions={sessions} onAnswer={onAnswer} />
          </div>
          <Splitter orientation="horizontal" onDelta={(d) => setFeedH(h => clamp(h + d, 150, 900))} />
          <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
            <PromptPanel session={selected} events={events} onSend={onSend} onStop={onStop} />
          </div>
        </div>
      </div>

      {/* ===== Footer ===== */}
      <div style={{ height: 28, minHeight: 28, background: C.surface, borderTop: `2px solid ${C.border}`, display: 'flex', alignItems: 'center', padding: '0 12px', gap: 14, flexShrink: 0, fontSize: 10, fontWeight: 700, color: C.t3 }}>
        <span>{sessions.length} agents</span>
        <span>{subCount} subagents</span>
        <span style={{ color: C.success }}>{active} active</span>
        <span>{idle} idle</span>
        <span style={{ color: C.warning }}>{pending} pending</span>
        {errored > 0 && <span style={{ color: C.danger }}>{errored} error</span>}
        <span>session {timeAgo(new Date(mountedAt.current).toISOString(), nowMs)}</span>
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 10, fontWeight: 800, padding: '2px 9px', borderRadius: 5, background: C.main, color: C.mainFg, border: `2px solid ${C.border}` }}>
          Σ {fmtTokens(tokenPill)} tokens
        </span>
      </div>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700;800;900&family=JetBrains+Mono:wght@400;500;600&display=swap');
        * { margin: 0; padding: 0; box-sizing: border-box; }
        @keyframes awlblink { 0%,100% { opacity: 1 } 50% { opacity: .3 } }
        @keyframes awlbarber { from { background-position: 0 0 } to { background-position: 22px 0 } }
        .awl-barber { background-image: repeating-linear-gradient(45deg, ${C.success} 0 8px, #8fe0bd 8px 16px); background-size: 22px 22px; animation: awlbarber .6s linear infinite; }
        .nb-btn { transition: transform .07s ease, box-shadow .07s ease; }
        .nb-btn:hover:not(:disabled), .nb-btn:active:not(:disabled) { transform: translate(2px,2px); box-shadow: none !important; }
        .nb-in:focus { box-shadow: ${C.shadowSm}; }
        textarea::placeholder, input::placeholder { color: ${C.t5}; }
        ::-webkit-scrollbar { width: 9px; height: 9px; }
        ::-webkit-scrollbar-track { background: ${C.surface}; border-left: 2px solid ${C.border}; }
        ::-webkit-scrollbar-thumb { background: ${C.t3}; border: 2px solid ${C.border}; }
        ::-webkit-scrollbar-thumb:hover { background: ${C.teal}; }
        select.nb-in { -webkit-appearance: none; appearance: none; }
      `}</style>
    </div>
  )
}
