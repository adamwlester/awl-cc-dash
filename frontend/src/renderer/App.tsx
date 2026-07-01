// ============================================================================
// AWL Multi-Agent Dashboard — the three-pane shell (throwaway MVP renderer)
// ----------------------------------------------------------------------------
// Title bar · three resizable columns (Agent | Team Graph/Work | Team
// Feed/Prompt) · status footer. Owns the global state + the merged /events SSE
// bus and wires the current sidecar contract into the panels. Selection drives
// the app: clicking a Team Graph card focuses that agent in the Agent panel,
// Feed, and Prompt.
//
// Scope: this is the FUNCTIONAL MVP renderer exercising the current backend —
// the merged event stream, the 5-type Inbox, agent-to-agent linking, Scratch,
// the Console, send-timing + send-as-agent, Settings reads/writes, Library
// reads, subagents, the checklist/marquee run-strip, templates, and
// revise/summarize. Minimal styling, reusing tokens.ts + ui.tsx primitives.
// ============================================================================

import React, { useCallback, useEffect, useRef, useState } from 'react'
import { C, FONT, timeAgo } from './tokens'
import {
  api, openEventStream,
  type Session, type SDKEvent, type ContextUsage, type CreatePayload,
  type SendOpts, type InboxResponse, type LinksResponse, type Checklist, type Marquee,
} from './api'
import { Splitter } from './Splitter'
import { TeamGraph } from './TeamGraph'
import { AgentPanel } from './AgentPanel'
import { TeamFeed } from './TeamFeed'
import { PromptPanel } from './PromptPanel'
import { WorkPanel } from './WorkPanel'
import { Settings } from './Settings'

const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v))
const EVENT_CAP = 4000

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
  const [allEvents, setAllEvents] = useState<SDKEvent[]>([])
  const [ctx, setCtx] = useState<ContextUsage | null>(null)
  const [usageBy, setUsageBy] = useState<Record<string, { percent: number | null; work_steps: number | null }>>({})
  const [subagentsBy, setSubagentsBy] = useState<Record<string, any[]>>({})
  const [checklistBy, setChecklistBy] = useState<Record<string, Checklist>>({})
  const [marqueeBy, setMarqueeBy] = useState<Record<string, Marquee>>({})
  const [inbox, setInbox] = useState<InboxResponse>({ inbox: {}, fleet_badge: 0 })
  const [links, setLinks] = useState<LinksResponse>({ links: [], grouped: {} })
  const [tokenPill, setTokenPill] = useState(0)
  const [health, setHealth] = useState<{ ok: boolean; version: string }>({ ok: false, version: '' })
  const [agentTab, setAgentTab] = useState<'details' | 'create' | 'console'>('details')
  const [creating, setCreating] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [nowMs, setNowMs] = useState(Date.now())
  const mountedAt = useRef(Date.now())
  const sessionsRef = useRef<Session[]>([])
  sessionsRef.current = sessions
  const seenRef = useRef<Set<string>>(new Set())

  // Resizable layout sizes (px); middle column + bottom panels flex.
  const [leftW, setLeftW] = useState(340)
  const [rightW, setRightW] = useState(460)
  const [graphH, setGraphH] = useState(360)
  const [feedH, setFeedH] = useState(320)

  const selected = sessions.find(s => s.session_id === selectedId) || null
  const focusedEvents = selectedId ? allEvents.filter(e => e.agent_id === selectedId) : []

  // ---- "ago" tick ----------------------------------------------------------
  useEffect(() => {
    const i = setInterval(() => setNowMs(Date.now()), 1000)
    return () => clearInterval(i)
  }, [])

  // ---- merged event bus: history backfill + live SSE (dedup by id, seq order)
  const ingest = useCallback((incoming: SDKEvent[]) => {
    const fresh: SDKEvent[] = []
    for (const e of incoming) {
      const key = e.id || `${e.agent_id ?? '?'}:${e.seq ?? Math.random()}`
      if (seenRef.current.has(key)) continue
      seenRef.current.add(key)
      fresh.push(e)
    }
    if (!fresh.length) return
    setAllEvents(prev => {
      const merged = prev.concat(fresh)
      merged.sort((a, b) => (a.seq ?? 0) - (b.seq ?? 0))
      if (merged.length <= EVENT_CAP) return merged
      const capped = merged.slice(merged.length - EVENT_CAP)
      // Keep the dedup set bounded in lockstep with the event window so a
      // long-lived session doesn't leak ids for evicted events. A re-replayed
      // old event just re-appends and slices back out by seq — no duplicate.
      const next = new Set<string>()
      for (const e of capped) next.add(e.id || `${e.agent_id ?? '?'}:${e.seq ?? ''}`)
      seenRef.current = next
      return capped
    })
  }, [])

  useEffect(() => {
    let cancelled = false
    // Immediate paint from the bounded-ring backfill…
    api.eventsHistory().then(hist => { if (!cancelled && hist) ingest(hist) })
    // …then the live merged stream (also re-replays the ring on reconnect —
    // deduped by event id).
    const es = openEventStream({ onEvent: (ev) => ingest([ev]) })
    return () => { cancelled = true; es.close() }
  }, [ingest])

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

  // ---- roster + usage + inbox + links (all agents) -------------------------
  useEffect(() => {
    let cancelled = false
    const poll = async () => {
      const [ss, us, ib, lk] = await Promise.all([api.sessions(), api.usage(), api.inbox(), api.links()])
      if (cancelled) return
      if (ss) setSessions(ss)
      if (us) {
        const by: Record<string, { percent: number | null; work_steps: number | null }> = {}
        for (const a of us.agents) by[a.session_id] = { percent: a.percent, work_steps: a.work_steps }
        setUsageBy(by)
        setTokenPill(us.token_pill || 0)
      }
      if (ib) setInbox(ib)
      if (lk) setLinks(lk)
    }
    poll()
    const i = setInterval(poll, 2000)
    return () => { cancelled = true; clearInterval(i) }
  }, [])

  const refreshLinks = useCallback(async () => { const lk = await api.links(); if (lk) setLinks(lk) }, [])

  // ---- checklist + marquee (all agents; cheap, in-memory on the sidecar) ----
  useEffect(() => {
    let cancelled = false
    const poll = async () => {
      const ss = sessionsRef.current
      if (!ss.length) { setChecklistBy({}); setMarqueeBy({}); return }
      const [cls, mqs] = await Promise.all([
        Promise.all(ss.map(async s => [s.session_id, await api.checklist(s.session_id)] as const)),
        Promise.all(ss.map(async s => [s.session_id, await api.marquee(s.session_id)] as const)),
      ])
      if (cancelled) return
      setChecklistBy(Object.fromEntries(cls.filter(([, v]) => v)) as Record<string, Checklist>)
      setMarqueeBy(Object.fromEntries(mqs.filter(([, v]) => v)) as Record<string, Marquee>)
    }
    poll()
    const i = setInterval(poll, 3000)
    return () => { cancelled = true; clearInterval(i) }
  }, [])

  // ---- subagents (all agents) — slower cadence: each read_log spawns wsl.exe.
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

  // ---- focused agent: context (the message stream comes from the merged bus)
  useEffect(() => {
    if (!selectedId) { setCtx(null); return }
    let cancelled = false
    const loop = async () => {
      while (!cancelled) {
        const c = await api.context(selectedId)
        if (cancelled) break
        setCtx(c)
        await new Promise(r => setTimeout(r, 1200))
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
      setSessions(prev => prev.some(x => x.session_id === s.session_id) ? prev : [...prev, s])
      setSelectedId(s.session_id); setAgentTab('details')
    }
  }, [])

  const onRetire = useCallback(async () => {
    if (!selectedId) return
    await api.retire(selectedId)
    setSelectedId(null)
  }, [selectedId])

  const onSend = useCallback(async (prompt: string, opts?: SendOpts) => {
    if (!selectedId) return null
    return await api.send(selectedId, prompt, opts)
  }, [selectedId])

  const onStop = useCallback(async () => { if (selectedId) await api.interrupt(selectedId) }, [selectedId])
  const onSetModel = useCallback(async (m: string) => { if (selectedId && m) await api.setModel(selectedId, m) }, [selectedId])
  const onSetEffort = useCallback(async (e: string) => { if (selectedId) await api.setEffort(selectedId, e) }, [selectedId])
  const onAnswer = useCallback(async (id: string, approve: boolean) => { await api.answerPermission(id, approve) }, [])
  const onResolveInbox = useCallback(async (agent: string, itemId: string, answer?: any) => {
    await api.resolveInbox(agent, itemId, answer)
    const ib = await api.inbox(); if (ib) setInbox(ib)
  }, [])

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
        {inbox.fleet_badge > 0 && <Chip bg={C.warnSoft} fg={C.warnText}>⚑ {inbox.fleet_badge} need you</Chip>}
        <div style={{ flex: 1 }} />
        <Chip bg={C.card} fg={C.t3}>{new Date(nowMs).toLocaleTimeString()}</Chip>
        <Chip bg={C.card} fg={C.t3}>WSL2</Chip>
        <Chip bg={C.card} fg={C.t3}>tmux</Chip>
        {health.ok
          ? <Chip bg={C.successSoft} fg={C.successText}>● Connected</Chip>
          : <Chip bg={C.dangerSoft} fg={C.danger}>● Sidecar offline</Chip>}
        <button className="nb-btn" title="Settings" onClick={() => setSettingsOpen(o => !o)}
          style={{ fontSize: 13, lineHeight: 1, padding: '2px 7px', borderRadius: 5, border: `2px solid ${C.border}`, background: settingsOpen ? C.card : C.main, color: C.mainFg, cursor: 'pointer', boxShadow: C.shadowSm }}>⚙</button>
      </div>

      {/* ===== Body: Settings step-into replaces the 3-pane when open ===== */}
      {settingsOpen ? (
        <Settings sessions={sessions} project={selected?.cwd || null} onClose={() => setSettingsOpen(false)} />
      ) : (
      <div style={{ flex: 1, display: 'flex', overflow: 'hidden', minHeight: 0 }}>
        {/* Left — Agent panel */}
        <div style={{ width: leftW, flexShrink: 0, borderRight: 'none', overflow: 'hidden' }}>
          <AgentPanel session={selected} ctx={ctx} tab={agentTab} onTab={setAgentTab}
            onSetModel={onSetModel} onSetEffort={onSetEffort} onRetire={onRetire}
            onCreate={onCreate} creating={creating} nowMs={nowMs} />
        </div>
        <Splitter orientation="vertical" onDelta={(d) => setLeftW(w => clamp(w + d, 260, 620))} />

        {/* Middle — Team Graph over the Work panel (Library / Links / Scratch) */}
        <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ height: graphH, flexShrink: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <div style={{ height: 34, minHeight: 34, background: C.surface, borderBottom: `2px solid ${C.border}`, display: 'flex', alignItems: 'center', padding: '0 10px', flexShrink: 0 }}>
              <span style={{ fontSize: 11, fontWeight: 800, color: C.t1, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Team Graph</span>
            </div>
            <TeamGraph sessions={sessions} usageBy={usageBy} subagentsBy={subagentsBy as any}
              checklistBy={checklistBy} marqueeBy={marqueeBy}
              selectedId={selectedId} onSelect={(id) => { setSelectedId(id); setAgentTab('details') }} nowMs={nowMs} />
          </div>
          <Splitter orientation="horizontal" onDelta={(d) => setGraphH(h => clamp(h + d, 150, 900))} />
          <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
            <WorkPanel sessions={sessions} focused={selected} links={links} onLinksChanged={refreshLinks} />
          </div>
        </div>
        <Splitter orientation="vertical" onDelta={(d) => setRightW(w => clamp(w - d, 340, 760))} />

        {/* Right — Team Feed over Prompt */}
        <div style={{ width: rightW, flexShrink: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          <div style={{ height: feedH, flexShrink: 0, overflow: 'hidden' }}>
            <TeamFeed focusedId={selectedId} events={allEvents} sessions={sessions}
              inbox={inbox} onAnswer={onAnswer} onResolveInbox={onResolveInbox} />
          </div>
          <Splitter orientation="horizontal" onDelta={(d) => setFeedH(h => clamp(h + d, 150, 900))} />
          <div style={{ flex: 1, minHeight: 0, overflow: 'hidden' }}>
            <PromptPanel session={selected} sessions={sessions} events={focusedEvents} onSend={onSend} onStop={onStop} />
          </div>
        </div>
      </div>
      )}

      {/* ===== Footer ===== */}
      <div style={{ height: 28, minHeight: 28, background: C.surface, borderTop: `2px solid ${C.border}`, display: 'flex', alignItems: 'center', padding: '0 12px', gap: 14, flexShrink: 0, fontSize: 10, fontWeight: 700, color: C.t3 }}>
        <span>{sessions.length} agents</span>
        <span>{subCount} subagents</span>
        <span style={{ color: C.success }}>{active} active</span>
        <span>{idle} idle</span>
        <span style={{ color: C.warning }}>{pending} pending</span>
        {errored > 0 && <span style={{ color: C.danger }}>{errored} error</span>}
        <span>{links.links.filter(l => l.active).length} links</span>
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
