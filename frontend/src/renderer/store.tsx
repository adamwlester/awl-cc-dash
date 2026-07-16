// ============================================================================
// Dash store — global data + UI state for the rebuilt renderer (§11 #37).
// ----------------------------------------------------------------------------
// Owns the merged /events SSE bus (dedup by id, order by seq), the §4.3 polling
// cadences (/health 5s · /sessions,/usage,/inbox,/links 2s · checklist+marquee
// 3s · /subagents 4.5s · focused /context ~1.2s), and #38 degraded mode: on
// /health failure the panels freeze on last-known values (visibly stale) and
// polling backs off to a gentle retry; the title-bar connector-health badge
// reads Connecting / Connected / Reconnecting / Offline.
// ============================================================================

import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import {
  api, openEventStream,
  type Session, type SDKEvent, type ContextUsage, type InboxResponse, type LinksResponse,
  type Checklist, type Marquee, type Subagent, type UsageAgent, type ScratchPost,
  type ProjectsResponse, type Template, type Disposition,
} from './api'

const EVENT_CAP = 4000

// ---- §7.17 — client-side normalization of the subagents blend ----------------
// The sidecar now blends server-side (subagents_naming.blend_live: exact/
// prefix engine-id merge, in-order running pairing, stopped hook-only
// leftovers dropped), so rows normally arrive already merged with non-null
// ids. This normalization stays as a HARMLESS backstop — a no-op on blended
// input — covering an older sidecar and any transient {id: null} extra
// (running-pair rules mirror the server's; verified live 2026-07-16).
type WireSubagent = Omit<Subagent, 'id'> & { id: string | null }
export function normalizeSubs(raw: WireSubagent[]): Subagent[] {
  const named = raw.filter(s => s.id != null) as Subagent[]
  const hook = raw.filter(s => s.id == null)
  if (!hook.length) return named
  const out = named.map(s => ({ ...s }))
  const claimed = new Set<number>()
  const sameAgent = (x?: string | null, y?: string | null) =>
    !!x && !!y && (x === y || (x.length >= 8 && y.startsWith(x)) || (y.length >= 8 && x.startsWith(y)))
  const claim = (idx: number, h: WireSubagent) => {
    claimed.add(idx)
    const t = out[idx]
    out[idx] = {
      ...t,
      agent_id: t.agent_id || h.agent_id,
      type: t.type || h.type,
      live_status: h.live_status ?? t.live_status,
      transcript_path: h.transcript_path ?? t.transcript_path,
    }
  }
  const leftovers: WireSubagent[] = []
  for (const h of hook) {
    // 1) exact/prefix engine-id match (the merge the sidecar itself intends)
    let idx = out.findIndex((s, i) => !claimed.has(i) && sameAgent(s.agent_id, h.agent_id))
    // 2) a RUNNING hook record belongs to a transcript spawn whose result (and
    //    agentId) hasn't landed yet — pair in order with an unclaimed running
    //    spawn that has no engine id
    if (idx < 0 && h.live_status === 'running') idx = out.findIndex((s, i) => !claimed.has(i) && !s.agent_id && s.status === 'running')
    // 3) a STOPPED hook record whose result never carried an agentId — pair
    //    with an unclaimed finished spawn missing its engine id
    if (idx < 0 && h.live_status !== 'running') idx = out.findIndex((s, i) => !claimed.has(i) && !s.agent_id && s.status !== 'running')
    if (idx >= 0) claim(idx, h)
    else leftovers.push(h)
  }
  // Leftover hook records that are STILL RUNNING are real live activity the
  // transcript hasn't caught up with (the blend's stated reason to append) —
  // keep them, with an honest display id derived from the real engine id (the
  // s1/A1 ids are themselves dashboard-minted). A STOPPED leftover never gained
  // a transcript spawn — the engine's internal helper agents fire the same
  // hooks (verified live 2026-07-16: 4 such records beside 2 real spawns) —
  // and keeping those inflates the roster forever, so they are dropped.
  let n = 0
  for (const h of leftovers) {
    if (h.live_status !== 'running') continue
    n += 1
    out.push({ ...h, id: h.agent_id ? String(h.agent_id).slice(0, 5) : `h${n}` })
  }
  return out
}

export type LinkState = 'connecting' | 'connected' | 'reconnecting' | 'offline'

export type FeedTab = 'transcript' | 'scratch' | 'log' | 'inbox'
export type PromptTab = 'compose' | 'history'
export type AgentTab = 'details' | 'create' | 'past' | 'console'
export type LibTab = 'plan' | 'documents' | 'assets'

export interface Jump {
  seq: number
  target: 'inbox' | 'history' | 'compose' | 'transcript' | 'plans' | 'documents' | 'console' | 'subagents'
  agent?: string
  type?: string
}

export interface PendingCompose {
  seq: number
  targets?: string[]        // pre-target these agents
  embeds?: { source: string; text: string }[]  // frozen reference blocks to insert
  text?: string             // raw text to load (Retry)
  // Attachment chips to add to the Compose strip (§7.14): materialized asset
  // ids from POST /library/assets, handed over from the Library/Assets Attach.
  attachments?: { id: string; filename: string; kind?: 'asset' | 'doc' }[]
}

interface Dash {
  // data
  linkState: LinkState
  healthVersion: string
  sessions: Session[]
  usageBy: Record<string, UsageAgent>
  tokenPill: number
  inbox: InboxResponse
  links: LinksResponse
  checklistBy: Record<string, Checklist>
  marqueeBy: Record<string, Marquee>
  subagentsBy: Record<string, Subagent[]>
  events: SDKEvent[]
  ctx: ContextUsage | null
  ctxLoading: boolean
  scratch: ScratchPost[]
  projects: ProjectsResponse | null
  templates: Template[]
  nowMs: number
  sessionStart: number
  // ui
  selectedId: string | null
  agentTab: AgentTab
  feedTab: FeedTab
  promptTab: PromptTab
  libTab: LibTab
  settingsOpen: boolean
  settingsTab: string
  consoleExpanded: boolean
  drawerOpen: boolean
  jump: Jump
  pendingCompose: PendingCompose
  // actions
  select: (id: string | null) => void
  setAgentTab: (t: AgentTab) => void
  setFeedTab: (t: FeedTab) => void
  setPromptTab: (t: PromptTab) => void
  setLibTab: (t: LibTab) => void
  openSettings: (tab?: string) => void
  closeSettings: () => void
  setConsoleExpanded: (b: boolean) => void
  setDrawerOpen: (b: boolean | ((b: boolean) => boolean)) => void
  statusJump: (state: 'active' | 'idle' | 'pending' | 'error', agent?: string) => void
  gotoInbox: (agent: string, type?: string) => void
  gotoSubagent: (agent: string, subId: string) => void
  replyTo: (agent: string, embed?: { source: string; text: string }, text?: string) => void
  attachToCompose: (atts: { id: string; filename: string; kind?: 'asset' | 'doc' }[]) => void
  refreshInbox: () => Promise<void>
  refreshLinks: () => Promise<void>
  refreshProjects: () => Promise<void>
  refreshCtx: () => Promise<void>
  sendPrompt: (text: string, opts: { source: string; targets: string[]; timing: Disposition; attachments?: string[] }) => Promise<string>
  projectCwd: string | null
}

const DashCtx = createContext<Dash | null>(null)
export const useDash = (): Dash => {
  const d = useContext(DashCtx)
  if (!d) throw new Error('useDash outside provider')
  return d
}

export function DashProvider({ children }: { children: React.ReactNode }) {
  // ---- data ----------------------------------------------------------------
  const [linkState, setLinkState] = useState<LinkState>('connecting')
  const [healthVersion, setHealthVersion] = useState('')
  const [sessions, setSessions] = useState<Session[]>([])
  const [usageBy, setUsageBy] = useState<Record<string, UsageAgent>>({})
  const [tokenPill, setTokenPill] = useState(0)
  const [inbox, setInbox] = useState<InboxResponse>({ inbox: {}, fleet_badge: 0 })
  const [links, setLinks] = useState<LinksResponse>({ links: [], grouped: {} })
  const [checklistBy, setChecklistBy] = useState<Record<string, Checklist>>({})
  const [marqueeBy, setMarqueeBy] = useState<Record<string, Marquee>>({})
  const [subagentsBy, setSubagentsBy] = useState<Record<string, Subagent[]>>({})
  const [events, setEvents] = useState<SDKEvent[]>([])
  const [ctx, setCtx] = useState<ContextUsage | null>(null)
  const [ctxLoading, setCtxLoading] = useState(false)
  const [scratch, setScratch] = useState<ScratchPost[]>([])
  const [projects, setProjects] = useState<ProjectsResponse | null>(null)
  const [templates, setTemplates] = useState<Template[]>([])
  const [nowMs, setNowMs] = useState(Date.now())
  const sessionStart = useRef(Date.now()).current

  // ---- ui ------------------------------------------------------------------
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [agentTab, setAgentTab] = useState<AgentTab>('details')
  const [feedTab, setFeedTab] = useState<FeedTab>('transcript')
  const [promptTab, setPromptTab] = useState<PromptTab>('compose')
  const [libTab, setLibTab] = useState<LibTab>('plan')
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [settingsTab, setSettingsTab] = useState('projects')
  const [consoleExpanded, setConsoleExpanded] = useState(false)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [jump, setJump] = useState<Jump>({ seq: 0, target: 'inbox' })
  const [pendingCompose, setPendingCompose] = useState<PendingCompose>({ seq: 0 })

  const healthyRef = useRef(false)        // gate for data polls (freeze when offline)
  const healthFails = useRef(0)
  const esOpenRef = useRef(false)
  const sessionsRef = useRef<Session[]>([])
  sessionsRef.current = sessions
  const selectedRef = useRef<string | null>(null)
  selectedRef.current = selectedId

  // ---- clock ----------------------------------------------------------------
  useEffect(() => {
    const i = setInterval(() => setNowMs(Date.now()), 1000)
    return () => clearInterval(i)
  }, [])

  // ---- merged event bus: history backfill + live SSE (dedup by id, seq order)
  const seenRef = useRef<Set<string>>(new Set())
  const ingest = useCallback((incoming: SDKEvent[]) => {
    const fresh: SDKEvent[] = []
    for (const e of incoming) {
      const key = e.id || `${e.agent_id ?? '?'}:${e.seq ?? Math.random()}`
      if (seenRef.current.has(key)) continue
      seenRef.current.add(key)
      fresh.push(e)
    }
    if (!fresh.length) return
    setEvents(prev => {
      const merged = prev.concat(fresh)
      merged.sort((a, b) => (a.seq ?? 0) - (b.seq ?? 0))
      if (merged.length <= EVENT_CAP) return merged
      const capped = merged.slice(merged.length - EVENT_CAP)
      const next = new Set<string>()
      for (const e of capped) next.add(e.id || `${e.agent_id ?? '?'}:${e.seq ?? ''}`)
      seenRef.current = next
      return capped
    })
  }, [])

  useEffect(() => {
    let cancelled = false
    api.eventsHistory().then(h => { if (!cancelled && h) ingest(h) })
    const es = openEventStream({
      onEvent: ev => ingest([ev]),
      onOpen: () => { esOpenRef.current = true; if (healthyRef.current) setLinkState('connected') },
      onError: () => { esOpenRef.current = false; if (healthyRef.current) setLinkState('reconnecting') },
    })
    return () => { cancelled = true; es.close() }
  }, [ingest])

  // ---- health (5s; backs off to 10s after repeated failures — #38) ---------
  useEffect(() => {
    let cancelled = false
    let timer: any
    const tick = async () => {
      const h = await api.health()
      if (cancelled) return
      if (h) {
        const wasDown = !healthyRef.current
        healthyRef.current = true
        healthFails.current = 0
        setHealthVersion(h.version || '')
        setLinkState(esOpenRef.current || wasDown === false ? 'connected' : 'connected')
      } else {
        healthyRef.current = false
        healthFails.current += 1
        setLinkState('offline')
      }
      timer = setTimeout(tick, healthFails.current >= 3 ? 10000 : 5000)
    }
    tick()
    return () => { cancelled = true; clearTimeout(timer) }
  }, [])

  // ---- roster + inbox + links (2s; frozen while offline) -------------------
  useEffect(() => {
    let cancelled = false
    const poll = async () => {
      if (!healthyRef.current && healthFails.current > 0) return   // attempt at startup; freeze only when known-down (#38)
      const [ss, ib, lk] = await Promise.all([api.sessions(), api.inbox(), api.links()])
      if (cancelled) return
      if (ss) setSessions(ss)
      if (ib) setInbox(ib)
      if (lk) setLinks(lk)
    }
    poll()
    const i = setInterval(poll, 2000)
    return () => { cancelled = true; clearInterval(i) }
  }, [])

  // ---- usage — polled on its OWN cadence, off the roster critical path ------
  // /usage aggregates a screen-scrape and can lag several seconds; bundling it
  // into the 2s roster Promise.all made the agents not appear until it resolved
  // (cold-load showed "0 agents" for ~7s). Poll it separately, with an in-flight
  // guard so a slow scrape can't pile up requests. (#38 — decouple slow reads.)
  useEffect(() => {
    let cancelled = false
    let inflight = false
    const poll = async () => {
      if (!healthyRef.current && healthFails.current > 0) return
      if (inflight) return
      inflight = true
      try {
        const us = await api.usage()
        if (cancelled || !us) return
        const by: Record<string, UsageAgent> = {}
        for (const a of us.agents) by[a.session_id] = a
        setUsageBy(by)
        setTokenPill(us.token_pill || 0)
      } finally { inflight = false }
    }
    poll()
    const i = setInterval(poll, 4000)
    return () => { cancelled = true; clearInterval(i) }
  }, [])

  // ---- checklist + marquee (3s) ---------------------------------------------
  useEffect(() => {
    let cancelled = false
    const poll = async () => {
      if (!healthyRef.current && healthFails.current > 0) return   // attempt at startup; freeze only when known-down (#38)
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

  // ---- subagents (4.5s) ------------------------------------------------------
  useEffect(() => {
    let cancelled = false
    const poll = async () => {
      if (!healthyRef.current && healthFails.current > 0) return   // attempt at startup; freeze only when known-down (#38)
      const ss = sessionsRef.current
      if (!ss.length) { setSubagentsBy({}); return }
      const entries = await Promise.all(
        ss.map(async s => [s.session_id, normalizeSubs(((await api.subagents(s.session_id))?.subagents || []) as WireSubagent[])] as const)
      )
      if (!cancelled) setSubagentsBy(Object.fromEntries(entries))
    }
    poll()
    const i = setInterval(poll, 4500)
    return () => { cancelled = true; clearInterval(i) }
  }, [])

  // ---- projects + templates (30s, lazy surfaces refresh on demand) ----------
  const refreshProjects = useCallback(async () => { const p = await api.projects(); if (p) setProjects(p) }, [])
  useEffect(() => {
    let cancelled = false
    const poll = async () => {
      if (!healthyRef.current && healthFails.current > 0) return   // attempt at startup; freeze only when known-down (#38)
      const [p, t] = await Promise.all([api.projects(), api.templates()])
      if (cancelled) return
      if (p) setProjects(p)
      if (t) setTemplates(t)
    }
    poll()
    const i = setInterval(poll, 30000)
    return () => { cancelled = true; clearInterval(i) }
  }, [])

  // ---- picker-first startup (§3.1/§9.1) --------------------------------------
  // Startup never silently auto-loads a project: when the first successful
  // /projects read shows NO open project, step into Settings → Projects (the
  // picker, last-used preselected by the tab's ordering). Runs exactly once.
  const pickerShownRef = useRef(false)
  useEffect(() => {
    if (pickerShownRef.current || projects == null) return
    pickerShownRef.current = true
    if (!projects.open) { setSettingsTab('projects'); setSettingsOpen(true) }
  }, [projects])

  const projectCwd = projects?.open || sessions.find(s => s.cwd)?.cwd || null

  // ---- scratch (3s, needs a cwd) --------------------------------------------
  useEffect(() => {
    let cancelled = false
    const poll = async () => {
      if ((!healthyRef.current && healthFails.current > 0) || !projectCwd) return
      const r = await api.scratch(projectCwd)
      if (!cancelled && r) setScratch(r.posts || [])
    }
    poll()
    const i = setInterval(poll, 3000)
    return () => { cancelled = true; clearInterval(i) }
  }, [projectCwd])

  // ---- focused context (~1.2s) ----------------------------------------------
  useEffect(() => {
    if (!selectedId) { setCtx(null); return }
    let cancelled = false
    const loop = async () => {
      while (!cancelled) {
        if (healthyRef.current) {
          const c = await api.context(selectedId)
          if (cancelled) break
          if (c) setCtx(c)
        }
        await new Promise(r => setTimeout(r, 1200))
      }
    }
    loop()
    return () => { cancelled = true }
  }, [selectedId])

  const refreshCtx = useCallback(async () => {
    const id = selectedRef.current
    if (!id) return
    setCtxLoading(true)
    const c = await api.context(id)
    if (c) setCtx(c)
    setCtxLoading(false)
  }, [])

  // Clear a stale selection if the agent vanished.
  useEffect(() => {
    if (selectedId && sessions.length && !sessions.some(s => s.session_id === selectedId)) setSelectedId(null)
  }, [sessions, selectedId])
  // Auto-select the first agent when nothing is focused.
  useEffect(() => {
    if (!selectedId && sessions.length) setSelectedId(sessions[0].session_id)
  }, [sessions, selectedId])

  // ---- cross-panel actions ---------------------------------------------------
  const select = useCallback((id: string | null) => { setSelectedId(id) }, [])
  const bumpJump = useCallback((j: Omit<Jump, 'seq'>) => setJump(p => ({ ...j, seq: p.seq + 1 })), [])

  const statusJump = useCallback((state: 'active' | 'idle' | 'pending' | 'error', agent?: string) => {
    if (state === 'pending' || state === 'error') { setFeedTab('inbox'); bumpJump({ target: 'inbox', agent, type: state === 'error' ? 'error' : undefined }) }
    else if (state === 'active') { setPromptTab('history'); bumpJump({ target: 'history', agent }) }
    else { setPromptTab('compose'); bumpJump({ target: 'compose', agent }) }
  }, [bumpJump])

  const gotoInbox = useCallback((agent: string, type?: string) => {
    setFeedTab('inbox'); bumpJump({ target: 'inbox', agent, type })
  }, [bumpJump])

  // Subagent-badge action (§7.17): focus parent (caller) + open the Details
  // Subagents accordion to the row + scope the Team Feed to that subagent.
  const gotoSubagent = useCallback((agent: string, subId: string) => {
    bumpJump({ target: 'subagents', agent, type: subId })
  }, [bumpJump])

  const replyTo = useCallback((agent: string, embed?: { source: string; text: string }, text?: string) => {
    setPromptTab('compose')
    setPendingCompose(p => ({ seq: p.seq + 1, targets: [agent], embeds: embed ? [embed] : [], text }))
    bumpJump({ target: 'compose', agent })
  }, [bumpJump])

  // Attach hand-off (§7.14): drop materialized asset chips onto the Compose
  // attachment strip and reveal Compose (the design's "switch + flash" path).
  const attachToCompose = useCallback((atts: { id: string; filename: string; kind?: 'asset' | 'doc' }[]) => {
    setPromptTab('compose')
    setPendingCompose(p => ({ seq: p.seq + 1, attachments: atts }))
    bumpJump({ target: 'compose' })
  }, [bumpJump])

  const refreshInbox = useCallback(async () => { const ib = await api.inbox(); if (ib) setInbox(ib) }, [])
  const refreshLinks = useCallback(async () => { const lk = await api.links(); if (lk) setLinks(lk) }, [])

  const sendPrompt = useCallback(async (text: string, opts: { source: string; targets: string[]; timing: Disposition; attachments?: string[] }): Promise<string> => {
    const agents = opts.targets.filter(t => t !== 'scratch')
    const toScratch = opts.targets.includes('scratch')
    let out = ''
    if (toScratch && projectCwd) {
      const r = await api.postScratch({ cwd: projectCwd, author: opts.source, text })
      out += r ? 'posted to Scratch' : 'Scratch post failed'
    }
    for (const id of agents) {
      const r = await api.send(id, text, {
        source: opts.source, recipients: [...agents, ...(toScratch ? ['scratch'] : [])],
        disposition: opts.timing, attachments: opts.attachments?.length ? opts.attachments : null,
      })
      // Honest failure: carry the endpoint's own detail (unknown attachment id,
      // "agent has no cwd; attachments need a project store", …) — never a bare
      // "send failed" that hides why nothing was delivered.
      out += `${out ? ' · ' : ''}${r.ok && r.data ? `${r.data.status}` : `send failed${r.detail ? ` — ${r.detail}` : ''}`}`
    }
    return out || 'no target'
  }, [projectCwd])

  const openSettings = useCallback((tab?: string) => { if (tab) setSettingsTab(tab); setSettingsOpen(true) }, [])
  const closeSettings = useCallback(() => setSettingsOpen(false), [])

  const value: Dash = {
    linkState, healthVersion, sessions, usageBy, tokenPill, inbox, links, checklistBy, marqueeBy,
    subagentsBy, events, ctx, ctxLoading, scratch, projects, templates, nowMs, sessionStart,
    selectedId, agentTab, feedTab, promptTab, libTab, settingsOpen, settingsTab, consoleExpanded, drawerOpen,
    jump, pendingCompose,
    select, setAgentTab, setFeedTab, setPromptTab, setLibTab, openSettings, closeSettings,
    setConsoleExpanded, setDrawerOpen, statusJump, gotoInbox, gotoSubagent, replyTo, attachToCompose,
    refreshInbox, refreshLinks, refreshProjects, refreshCtx, sendPrompt, projectCwd,
  }
  return <DashCtx.Provider value={value}>{children}</DashCtx.Provider>
}
