// ============================================================================
// Console — the focused agent's raw terminal feed + slash-command catalog.
// ----------------------------------------------------------------------------
// In-column (Agent panel tab) and the expanded step-into view share the same
// internals. The feed attaches on open via POST /sessions/{id}/console/attach
// → { ws_url } → WebSocket → xterm (ttyd-style raw protocol, handled binary).
// When the attach endpoint isn't merged yet the Console degrades honestly to
// the catalog + run bar (both LIVE through /console/catalog and console/run).
// ============================================================================

import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Terminal } from '@xterm/xterm'
import { FitAddon } from '@xterm/addon-fit'
import '@xterm/xterm/css/xterm.css'
import { api, type ConsoleCatalog, type ConsoleCommand } from '../api'
import { useDash } from '../store'
import { Ic } from '../lib/icons'
import { AgTile, identOf } from '../lib/identity'
import { toast } from '../lib/toast'

interface ConLine { c: string; t: string }

// Module-level echo cache so the in-column console and the expanded step-into
// show the same feed for a session (the mockup shares one CON_FEED the same way).
const LINE_CACHE = new Map<string, ConLine[]>()

// Module-level attach cache (NU-6 — console expand reuses the live attach):
// keyed by SESSION ID ONLY (ConsoleView is always-mounted, keyed by the
// sessionId flip), storing the IN-FLIGHT attach promise. Two views asking
// concurrently (the mount+expand race) share one POST; an expand onto an
// already-attached session resolves synchronously to 'ws' with zero POST.
// Entries are populated on issue, kept on success, and cleared on terminal
// failure, socket death (onDead), and retire/hard-delete (clearAttachCache) so
// a resumed agent re-attaches fresh.
const ATTACH_CACHE = new Map<string, Promise<{ ws_url: string } | null>>()
export function clearAttachCache(sessionId: string) { ATTACH_CACHE.delete(sessionId) }

// ---- shared console session state (one per focused agent) -------------------
export function useConsole(sessionId: string | null) {
  const [lines, setLinesRaw] = useState<ConLine[]>(() => (sessionId && LINE_CACHE.get(sessionId)) || [])
  const setLines = useCallback((fn: (p: ConLine[]) => ConLine[]) => setLinesRaw(p => {
    const next = fn(p)
    if (sessionId) LINE_CACHE.set(sessionId, next)
    return next
  }), [sessionId])
  const [wsUrl, setWsUrl] = useState<string | null>(null)
  const [attachState, setAttachState] = useState<'trying' | 'ws' | 'degraded'>('trying')
  const [catalog, setCatalog] = useState<ConsoleCatalog | null>(null)

  useEffect(() => { api.consoleCatalog().then(c => { if (c) setCatalog(c) }) }, [])

  // NU-6 onDead bookkeeping (declared before the attach effect that resets it):
  // the live session id, and the session already given its one recovery.
  const sidRef = useRef<string | null>(sessionId)
  sidRef.current = sessionId
  const recoveredRef = useRef<string | null>(null)

  useEffect(() => {
    setLinesRaw((sessionId && LINE_CACHE.get(sessionId)) || [])
    setWsUrl(null)
    setAttachState('trying')
    recoveredRef.current = null
    if (!sessionId) { setAttachState('degraded'); return }
    let cancelled = false
    let retryTimer: ReturnType<typeof setTimeout> | undefined
    // Attach can fail transiently (live drive 2026-07-17: first attach failed,
    // the tab sat degraded until a remount re-attached). Bounded recovery: one
    // retry ~1.5s after a failed first attempt, then settle degraded — further
    // recovery stays manual (next mount). A cancelled unmount never retries.
    // NU-6: the module ATTACH_CACHE fronts the ladder — a cache hit resolves
    // to 'ws' with zero POST (the expand lag dies); a miss runs the real
    // ladder, caching its in-flight promise so concurrent mounts share one
    // POST. Terminal failure clears the entry (only if it's still ours).
    const attach = (attempt: number) => {
      const p = api.consoleAttach(sessionId)
      ATTACH_CACHE.set(sessionId, p)
      p.then(r => {
        if (cancelled) return
        if (r && r.ws_url) { setWsUrl(r.ws_url); setAttachState('ws'); return }
        if (ATTACH_CACHE.get(sessionId) === p) ATTACH_CACHE.delete(sessionId)
        if (attempt === 0) {
          retryTimer = setTimeout(() => { if (!cancelled) attach(1) }, 1500)
        } else {
          setAttachState('degraded')
          setLines(p2 => p2.length ? p2 : [{ c: 'l-status', t: 'live terminal attach not available yet — slash commands below run for real; output lands here' }])
        }
      })
    }
    const cached = ATTACH_CACHE.get(sessionId)
    if (cached) {
      cached.then(r => {
        if (cancelled) return
        if (r && r.ws_url) { setWsUrl(r.ws_url); setAttachState('ws') }
        else attach(0)   // stale failed entry (its owner already cleared it) — run the real ladder
      })
    } else attach(0)
    return () => { cancelled = true; if (retryTimer) clearTimeout(retryTimer) }
  }, [sessionId])

  // NU-6 invalidation: a WS that dies WITHOUT a clean unmount-close (XtermFeed
  // onDead) means the cached attach is stale — drop the entry and re-run the
  // attach ladder ONCE for this session; if that recovery also fails, settle
  // 'degraded' (strictly better than the old dead '[terminal detached]').
  const onDead = useCallback(() => {
    const sid = sessionId
    if (!sid) return
    ATTACH_CACHE.delete(sid)
    if (sidRef.current !== sid) return
    if (recoveredRef.current === sid) {
      setWsUrl(null)
      setAttachState('degraded')
      setLines(p => p.length ? p : [{ c: 'l-status', t: 'live terminal attach not available yet — slash commands below run for real; output lands here' }])
      return
    }
    recoveredRef.current = sid
    setWsUrl(null)
    setAttachState('trying')
    const p = api.consoleAttach(sid)
    ATTACH_CACHE.set(sid, p)
    p.then(r => {
      if (sidRef.current !== sid) return
      if (r && r.ws_url) { setWsUrl(r.ws_url); setAttachState('ws') }
      else {
        if (ATTACH_CACHE.get(sid) === p) ATTACH_CACHE.delete(sid)
        setWsUrl(null)
        setAttachState('degraded')
        setLines(p2 => p2.length ? p2 : [{ c: 'l-status', t: 'live terminal attach not available yet — slash commands below run for real; output lands here' }])
      }
    })
  }, [sessionId, setLines])

  const run = useCallback(async (cmd: string) => {
    if (!sessionId) { toast('No agent focused'); return }
    setLines(p => [...p, { c: 'l-cmd', t: `> ${cmd}` }])
    const r = await api.consoleRun(sessionId, cmd)
    if (!r) { setLines(p => [...p, { c: 'l-sys', t: '⎿ command failed (sidecar rejected it)' }]); return }
    const screen = (r.screen || '').split('\n').filter(l => l.trim().length)
    setLines(p => [...p, ...screen.slice(-30).map(t => ({ c: 'l-out', t }))])
  }, [sessionId, setLines])

  return { sessionId, lines, wsUrl, attachState, catalog, run, onDead }
}

// ---- xterm host --------------------------------------------------------------
// `sendResize` is the SINGLE-WRITER rule for pane geometry: the in-column tab
// and the expanded overlay both mount an XtermFeed while expanded (two WS
// clients, one tmux window) — only the topmost view may drive the sidecar's
// POST /sessions/{id}/console/resize (debounced ~350ms trailing; the pin —
// `window-size manual` — stays, `resize-window` keeps it set). The ttyd
// '1{columns,rows}' message still goes up either way — harmless, tmux ignores
// a client resize under the pin.
function XtermFeed({ wsUrl, sessionId, sendResize, onDead }: { wsUrl: string; sessionId: string | null; sendResize: boolean; onDead?: () => void }) {
  const hostRef = useRef<HTMLDivElement>(null)
  // Ref, not an effect dep: flipping topmost-ness (expand/collapse) must not
  // tear down and rebuild the live terminal.
  const sendResizeRef = useRef(sendResize)
  sendResizeRef.current = sendResize
  // Ref for the same reason: a changing onDead identity must not rebuild the WS.
  const onDeadRef = useRef(onDead)
  onDeadRef.current = onDead
  // Regaining the writer role (sendResize false→true — e.g. the expanded
  // overlay closed and this in-column feed drives geometry again) must
  // RE-ASSERT geometry: the host's size didn't change, so the ResizeObserver
  // won't fire, yet tmux is still pinned at the departed view's size. Guarded
  // so it never fires on initial mount (ws.onopen already pushes then).
  const pushGeomRef = useRef<() => void>(() => {})
  const wasWriterRef = useRef(sendResize)
  useEffect(() => {
    if (sendResize && !wasWriterRef.current) pushGeomRef.current()
    wasWriterRef.current = sendResize
  }, [sendResize])
  useEffect(() => {
    const host = hostRef.current
    if (!host) return
    const term = new Terminal({
      fontFamily: 'JetBrains Mono, monospace', fontSize: 12, theme: { background: '#00000000' },
      allowTransparency: true, convertEol: false, scrollback: 4000,
    })
    const fit = new FitAddon()
    term.loadAddon(fit)
    term.open(host)
    try { fit.fit() } catch { /* not yet laid out */ }
    let resizeTimer: ReturnType<typeof setTimeout> | null = null
    const pushGeometry = () => {
      if (!sendResizeRef.current || !sessionId) return
      if (resizeTimer) clearTimeout(resizeTimer)
      // Gate re-checked at FIRE time too: a pending in-column timer must not
      // land after the expanded view has become the writer.
      // Below-floor clamp (viewer smaller than the sidecar's 60×15 scraper
      // floor renders tmux-clipped): accepted degrade — the applied values in
      // the response are deliberately not reconciled here.
      resizeTimer = setTimeout(() => { if (sendResizeRef.current && sessionId) void api.consoleResize(sessionId, term.cols, term.rows) }, 350)
    }
    pushGeomRef.current = pushGeometry
    let ws: WebSocket | null = null
    // NU-6: a socket death WITHOUT a clean unmount-close invalidates the shared
    // attach cache (onDead). Guarded so onerror+onclose report once, and the
    // unmount cleanup (or a wsUrl swap) never reports at all.
    let closedByUnmount = false
    let deadFired = false
    const reportDead = () => {
      if (closedByUnmount || deadFired) return
      deadFired = true
      onDeadRef.current?.()
    }
    try {
      ws = new WebSocket(wsUrl, ['tty'])
      ws.binaryType = 'arraybuffer'
      ws.onopen = () => {
        try { ws!.send(JSON.stringify({ AuthToken: '' })) } catch { /* ttyd handshake — optional */ }
        try { ws!.send('1' + JSON.stringify({ columns: term.cols, rows: term.rows })) } catch { }
        pushGeometry()
      }
      ws.onmessage = (m) => {
        if (typeof m.data === 'string') {
          // ttyd: '0'+data = output, '1' title, '2' prefs; plain strings pass through
          if (m.data.length && (m.data[0] === '0')) term.write(m.data.slice(1))
          else if (m.data[0] !== '1' && m.data[0] !== '2') term.write(m.data)
        } else {
          const buf = new Uint8Array(m.data as ArrayBuffer)
          if (buf.length && buf[0] === 0x30) term.write(buf.slice(1))
          else term.write(buf)
        }
      }
      ws.onerror = () => reportDead()
      ws.onclose = () => { term.write('\r\n\x1b[2m[terminal detached]\x1b[0m\r\n'); reportDead() }
      term.onData(d => { try { ws && ws.readyState === 1 && ws.send('0' + d) } catch { } })
    } catch { term.write('[attach failed]'); reportDead() }
    const ro = new ResizeObserver(() => {
      try { fit.fit(); ws && ws.readyState === 1 && ws.send('1' + JSON.stringify({ columns: term.cols, rows: term.rows })); pushGeometry() } catch { }
    })
    ro.observe(host)
    return () => { closedByUnmount = true; ro.disconnect(); if (resizeTimer) clearTimeout(resizeTimer); try { ws?.close() } catch { }; term.dispose() }
  }, [wsUrl, sessionId])
  return <div className="awl-xterm-host" ref={hostRef} />
}

// ---- feed (mockup line classes for the degraded/local echo path) -------------
function conMarkup(t: string): React.ReactNode {
  const m = t.match(/^(\s*)(●|⎿|✻|>)(\s?)([\s\S]*)$/)
  if (m) {
    const cls = ({ '●': 'cmk-bullet', '⎿': 'cmk-pipe', '✻': 'cmk-think', '>': 'cmk-prompt' } as any)[m[2]]
    return <>{m[1]}<span className={cls}>{m[2]}</span>{m[3] || ''}{m[4]}</>
  }
  return t
}

export function ConsoleFeed({ id, con, sendResize = true }: { id: string; con: ReturnType<typeof useConsole>; sendResize?: boolean }) {
  const feedRef = useRef<HTMLDivElement>(null)
  useEffect(() => { const el = feedRef.current; if (el) el.scrollTop = el.scrollHeight }, [con.lines])
  if (con.attachState === 'ws' && con.wsUrl) {
    return <div data-comp="console-feed" className="con-feed awl-xterm" id={id}><XtermFeed wsUrl={con.wsUrl} sessionId={con.sessionId} sendResize={sendResize} onDead={con.onDead} /></div>
  }
  return (
    <div data-comp="console-feed" className="con-feed" id={id} ref={feedRef}>
      {con.attachState === 'trying' && <div className="con-line l-status">attaching…</div>}
      {con.lines.map((l, i) => <div key={i} className={`con-line ${l.c || 'l-asst'}`}>{conMarkup(l.t)}</div>)}
    </div>
  )
}

// ---- command catalog -----------------------------------------------------------
export function CommandList({ catalog, filter, onPick }: { catalog: ConsoleCatalog | null; filter: string; onPick: (cmd: string) => void }) {
  if (!catalog) return <div className="awl-empty">command catalog unavailable</div>
  const q = filter.trim().toLowerCase()
  const match = (c: ConsoleCommand) => !q || c.command.toLowerCase().includes(q) || (c.description || '').toLowerCase().includes(q)
  return (
    <>
      {catalog.clusters.map(cl => {
        const items = (catalog.by_cluster[cl] || []).filter(match)
        if (!items.length) return null
        return (
          <div className="cmd-group" key={cl}>
            <div className="cmd-group-h">{cl}</div>
            {items.map(it => (
              <button className="cmd-row" key={it.command} data-cmd={it.command} onClick={() => onPick(it.command)}>
                <span className="cmd-row-top"><span className="cmd-name">{it.command}</span>
                  {it.also_in && <span className="cmd-also" title={`Also available in ${it.also_in}`}><Ic name="corner-up-right" />{it.also_in}</span>}
                </span>
                <span className="cmd-desc">{it.description}</span>
              </button>
            ))}
          </div>
        )
      })}
    </>
  )
}

// ---- expanded step-into view (covers left+middle columns; right stays visible) --
export function ConsoleView() {
  const d = useDash()
  const s = d.sessions.find(x => x.session_id === d.selectedId) || null
  const con = useConsole(d.consoleExpanded ? d.selectedId : null)
  const [filter, setFilter] = useState('')
  const [cmd, setCmd] = useState('')
  const viewRef = useRef<HTMLDivElement>(null)

  // pin the right edge to #pRight's left edge (recomputed on resize/drags)
  useEffect(() => {
    if (!d.consoleExpanded) return
    const v = viewRef.current
    const position = () => {
      if (!v) return
      const app = document.querySelector('.app'), pr = document.getElementById('pRight')
      if (!app || !pr) return
      const a = app.getBoundingClientRect(), r = pr.getBoundingClientRect()
      v.style.right = `${Math.max(0, Math.round(a.right - r.left))}px`
    }
    position()
    const pr = document.getElementById('pRight')
    const ro = pr ? new ResizeObserver(position) : null
    if (pr && ro) ro.observe(pr)
    window.addEventListener('resize', position)
    return () => { ro?.disconnect(); window.removeEventListener('resize', position) }
  }, [d.consoleExpanded])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape' && d.consoleExpanded) d.setConsoleExpanded(false) }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [d.consoleExpanded, d])

  const a = s ? identOf(s) : null
  const doRun = () => { const v = cmd.trim(); if (!v) return; con.run(v); setCmd('') }
  return (
    <div className={`console-view${d.consoleExpanded ? ' open' : ''}`} aria-hidden={!d.consoleExpanded} ref={viewRef}>
      <div className="con-head">
        <span className="con-title"><Ic name="terminal" />Console</span>
        {a && <span className="badge badge-c con-head-agent"><AgTile a={a} /><span className="b-lab"><span className="b-role">{a.role}</span><span className="b-name">{a.name}</span></span></span>}
        <span className="con-live"><i className="con-dot" />{con.attachState === 'ws' ? 'raw feed' : con.attachState === 'trying' ? 'attaching…' : 'catalog only'}</span>
        <button className="btn con-close" onClick={() => d.setConsoleExpanded(false)}><Ic name="x" className="w-3 h-3" />Close</button>
      </div>
      <div className="con-body">
        <aside data-comp="command-palette" className="con-rail">
          <div className="con-cat-head"><span className="con-cat-title">Commands</span>
            <div className="con-search"><Ic name="search" /><input placeholder="Filter commands…" value={filter} onChange={e => setFilter(e.target.value)} /></div>
          </div>
          <div className="con-cat-list">{d.consoleExpanded && <CommandList catalog={con.catalog} filter={filter} onPick={c => setCmd(c + ' ')} />}</div>
        </aside>
        <main className="con-main">
          {/* the expanded overlay is always the topmost view → it drives geometry */}
          {d.consoleExpanded && <ConsoleFeed id="con-feed-full" con={con} sendResize />}
          <div data-comp="console-runbar" className="con-run con-run--full">
            <button className="con-cmds-btn" title="Jump to the command filter" onClick={() => { const el = viewRef.current?.querySelector('.con-search input') as HTMLInputElement | null; el?.focus() }}><Ic name="terminal" className="w-3.5 h-3.5" /><span>/</span></button>
            <input className="con-input" placeholder="Type a command, or pick one from the list…" value={cmd}
              onChange={e => setCmd(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') doRun() }} />
            <button className="btn-main con-run-btn" onClick={doRun}>Run</button>
          </div>
        </main>
      </div>
    </div>
  )
}
