// ============================================================================
// Team — one agent-node-card per live session (mockup DOM, live data).
// Identity row · model badge + created stamp + status badge · settings chips ·
// Ctx/Turns health bars · run strip (segmented from the checklist, barber-pole
// floor) · marquee · subagent strip + per-card node-inbox envelope.
// ============================================================================

import React, { useLayoutEffect, useRef, useState } from 'react'
import { useDash } from '../store'
import { Ic } from '../lib/icons'
import { AgGlyph } from '../lib/icons'
import { identOf, runStateOf, ctxColor, createdStamp, modelLabel, modeLabel, NB_CLASS, NB_LABEL } from '../lib/identity'
import type { Session, Subagent, Checklist, Marquee, InboxItem } from '../api'

const CTX_CUTOFF = 80              // % — the common Max-Context auto-stop default (mockup CTX_CUTOFF)
const DEFAULT_MAX_TURNS = 50       // ⚠ sessions don't expose their max-turns yet — display floor

const SUB_CLASS: Record<string, string> = { running: 'sb-active', done: 'sb-idle', error: 'sb-error', waiting: 'sb-pending' }
const INBOX_SEC_ORDER = ['error', 'warning', 'permission', 'plan', 'decision', 'response']
const SEC_LABEL: Record<string, string> = { error: 'Error', warning: 'Warning', permission: 'Permission', plan: 'Review', decision: 'Decision', response: 'Response' }

function RunStrip({ s, cl }: { s: Session; cl?: Checklist }) {
  const state = runStateOf(s)
  if (cl && cl.total > 0) {
    const segs = []
    for (let i = 0; i < cl.total; i++) {
      const done = i < cl.done
      const cur = i === cl.done && state !== 'idle'
      let cls = 'rseg'
      if (done) cls += ' done'
      else if (cur) {
        cls += ' cur'
        if (state === 'pending') cls += ' cur-paused'
        else if (state === 'error') cls += ' cur-error'
      }
      segs.push(<i key={i} className={cls} />)
    }
    const title = cl.current ? `Step ${Math.min(cl.done + 1, cl.total)} of ${cl.total} · ${cl.current}` : `${cl.done} of ${cl.total} steps done`
    return <div data-comp="run-strip" className="run-strip run-seg" title={title}>{segs}</div>
  }
  if (state === 'error') return <div data-comp="run-strip" className="run-strip run-error"><i /></div>
  if (state === 'pending') return <div data-comp="run-strip" className="run-strip run-pending"><i style={{ width: '100%' }} /></div>
  if (state === 'active') return <div data-comp="run-strip" className="run-strip run-active run-indet"><i /></div>
  return <div data-comp="run-strip" className="run-strip run-idle"><i /></div>
}

function MarqueeBand({ mq, idle }: { mq?: Marquee; idle: boolean }) {
  const line = mq?.line || (idle ? 'idle — awaiting prompt' : 'working…')
  const isIdle = mq ? mq.idle : idle
  if (isIdle) return <div data-comp="marquee" className="node-feed idle"><span className="trk a">{line}</span></div>
  const seg = `${line}  ·  `
  return (
    <div data-comp="marquee" className="node-feed">
      <span className="trk a">{seg}{seg}</span>
      <span className="trk b">{seg}{seg}</span>
    </div>
  )
}

function SubStrip({ subs, onBadge }: { subs: Subagent[]; onBadge: (sub: Subagent) => void }) {
  const [open, setOpen] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const badgesRef = useRef<HTMLDivElement>(null)
  useLayoutEffect(() => {
    const el = badgesRef.current
    if (el) setHasMore(el.scrollHeight > el.clientHeight + 2)
  }, [subs.length, open])
  if (!subs.length) return <span className="subs-empty">no subagents</span>
  return (
    <div className={`subs-acc${hasMore ? ' has-more' : ''}${open ? ' open' : ''}`}
      onClick={e => { if (hasMore) { e.stopPropagation(); setOpen(o => !o) } }}>
      <div className="subs-badges" ref={badgesRef}>
        {subs.map(sub => (
          <span key={sub.id} data-comp="subagent-badge" className={`sbadge ${SUB_CLASS[sub.status] || 'sb-active'}`}
            title={`subagent ${sub.id} — ${sub.status} · click → focus parent + open Subagents + scope feed`}
            onClick={e => { e.stopPropagation(); onBadge(sub) }}>{sub.id}</span>
        ))}
      </div>
      <button className="subs-chev" title="Show all subagents" type="button"><Ic name="chevron-right" /></button>
    </div>
  )
}

function NodeCard({ s }: { s: Session }) {
  const d = useDash()
  const a = identOf(s)
  const state = runStateOf(s)
  const [inboxOpen, setInboxOpen] = useState(false)
  const usage = d.usageBy[s.session_id]
  const ctxPct = usage?.percent ?? null
  const turns = s.total_turns
  const turnsPct = Math.min(100, Math.round((turns / DEFAULT_MAX_TURNS) * 100))
  const subs = d.subagentsBy[s.session_id] || []
  const items = (d.inbox.inbox[s.session_id] || []).filter(i => !i.resolved)
  const sortedItems = [...items].sort((x, y) => INBOX_SEC_ORDER.indexOf(x.type) - INBOX_SEC_ORDER.indexOf(y.type))
  const isOpus = (s.model || '').toLowerCase().includes('opus')
  const fastOn = !!(s as any).fast_mode
  const thinking = (s as any).thinking as boolean | undefined
  const mode = s.run_state?.permission_mode || s.permission_mode
  const effort = (s as any).effort as string | undefined
  const selected = d.selectedId === s.session_id

  const onBadge = (sub: Subagent) => {
    d.select(s.session_id)
    d.setAgentTab('details')
    d.setFeedTab('transcript')
    d.gotoSubagent(s.session_id, sub.id)
  }

  return (
    <div data-comp="agent-node-card" data-agent={s.session_id}
      className={`node${selected ? ' selected' : ''}${inboxOpen ? ' ninb-open' : ''}`}
      onClick={() => { d.select(s.session_id); d.setAgentTab('details') }}
      style={{ ['--nc' as any]: a.color }}>
      <svg className="node-bg" aria-hidden="true">{/* watermark — sprite <use> fast path, recolor-endpoint <image> for the rest */}
        {a.icon && <AgGlyphUse icon={a.icon} color={a.color} />}
      </svg>
      <div className="node-id">
        <span className="agtile" style={{ color: a.color }}><AgGlyph icon={a.icon} color={a.color} /></span>
        <div className="node-idblk"><div className="node-role">{a.role}</div><div className="node-name">{a.name}</div></div>
      </div>
      <div className="node-mrow">
        <span className="node-model-badge">{modelLabel(s.model)}
          {isOpus && <Ic name="zap" className={`node-bolt${fastOn ? '' : ' off'}`} />}
        </span>
        <span className="node-age" title="Created · elapsed">{createdStamp(s.created_at, d.nowMs)}</span>
        <button data-comp="status-badge" className={`node-badge ${NB_CLASS[state]}`}
          onClick={e => { e.stopPropagation(); d.statusJump(state, s.session_id) }}
          title={{ active: 'Active — open Prompts → History', idle: 'Idle — open Prompts → Compose', pending: 'Pending — awaiting your input · open Inbox', error: 'Error — run failed · open Inbox' }[state]}>
          {NB_LABEL[state]}
        </button>
      </div>
      <div className="node-div" />
      <div className="node-settings">
        <span data-comp="node-chip" className="node-chip" title="Permission mode"><Ic name="shield" />{mode ? modeLabel(mode).toLowerCase() : '—'}</span>
        <span className="node-chip" title="Reasoning effort"><Ic name="gauge" />{effort || '—'}</span>
        <span className="node-chip" title="Extended thinking"><Ic name="brain" />{thinking == null ? '—' : thinking ? 'on' : 'off'}</span>
      </div>
      <div className="node-bars">
        <div className="nbar-row"><span className="nbl">Ctx</span>
          <div className="pbar">{ctxPct != null && <i style={{ width: `${Math.min(100, ctxPct)}%`, background: ctxColor(ctxPct) }} />}<span className="bar-cut" style={{ left: `${CTX_CUTOFF}%` }} /></div>
          <span className="nbv">{ctxPct != null ? `${Math.round(ctxPct)}%` : '—'}</span>
        </div>
        <div className="nbar-row"><span className="nbl">Turns</span>
          <div className="pbar"><i style={{ width: `${turnsPct}%`, background: ctxColor(turnsPct) }} /></div>
          <span className="nbv">{turns}/{DEFAULT_MAX_TURNS}</span>
        </div>
      </div>
      <div className="node-band">
        <RunStrip s={s} cl={d.checklistBy[s.session_id]} />
        <div className="node-div" />
        <MarqueeBand mq={d.marqueeBy[s.session_id]} idle={state === 'idle'} />
      </div>
      <div data-comp="node-subagents" className="node-subs">
        <div className="node-subs-bar">
          <SubStrip subs={subs} onBadge={onBadge} />
          {items.length ? (
            <button data-comp="node-inbox" className="node-inbox" aria-expanded={inboxOpen}
              title={`Inbox — ${items.length} open item${items.length === 1 ? '' : 's'} · click to expand`}
              onClick={e => { e.stopPropagation(); setInboxOpen(o => !o) }}>
              <Ic name="mail" className="ninb-ic" /><span className="ninb-n">{items.length}</span>
            </button>
          ) : (
            <span data-comp="node-inbox" className="node-inbox node-inbox--empty" title="Inbox — no open items"><Ic name="mail" className="ninb-ic" /></span>
          )}
        </div>
        {items.length > 0 && (
          <div className="ninb-drawer">
            {sortedItems.map(it => (
              <button key={it.id} className="ninb-row" title={`Open in Inbox → ${SEC_LABEL[it.type] || it.type}`}
                onClick={e => { e.stopPropagation(); d.gotoInbox(s.session_id, it.type) }}>
                <span className={`ninb-type ninb-type--${it.type}`}>{SEC_LABEL[it.type] || it.type}</span>
                <span className="ninb-row-t">{inboxTitle(it)}</span>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// The node-bg watermark (kept separate so the outer <svg className="node-bg"> matches the mockup DOM):
// sprite <use> when the icon (or its base name) is in the curated 50; otherwise an SVG <image> off the
// sidecar recolor endpoint, tinted to the design's watermark formula — color-mix(nc 5%, white) — so all
// 167 icons watermark instead of vanishing (NU-4).
import { spriteSymOf, glyphHex } from '../lib/icons'
import { api } from '../api'
function watermarkHex(color: string): string {
  const hex = glyphHex(color)
  if (!/^#[0-9a-fA-F]{6}$/.test(hex)) return hex
  const n = parseInt(hex.slice(1), 16)
  const mix = (c: number) => Math.round(c * 0.05 + 255 * 0.95)
  return `#${[(n >> 16) & 255, (n >> 8) & 255, n & 255].map(c => mix(c).toString(16).padStart(2, '0')).join('')}`
}
function AgGlyphUse({ icon, color }: { icon: string; color: string }) {
  const sym = spriteSymOf(icon)
  if (sym) return <use href={`#${sym}`} />
  return <image href={api.iconUrl(icon, watermarkHex(color))} width="100%" height="100%" preserveAspectRatio="xMidYMid meet" />
}

export function inboxTitle(it: InboxItem): string {
  const dt = it.data || {}
  return dt.title || dt.question || dt.command || dt.tool_name || dt.text || dt.message || dt.error || it.type
}

export function TeamGraph() {
  const d = useDash()
  return (
    <section className="rz-panel" id="pGraph" style={{ flex: '1 1 52%', minHeight: 'var(--pane-graph-min-h)', maxHeight: 'var(--pane-graph-max-h)' }}>
      <div className="pcard-head">
        <h3>Team</h3>
        <button className="btn btn-sm" onClick={() => d.setDrawer(p => p === 'link' ? null : 'link')}><Ic name="link-2" className="w-3.5 h-3.5" />Link Config</button>
        <button className="btn btn-sm" onClick={() => d.setDrawer(p => p === 'past' ? null : 'past')}><Ic name="history" className="w-3.5 h-3.5" />Past</button>
      </div>
      <div className="pcard-body overflow-auto" style={{ background: 'var(--background)' }}>
        <div className="graph-wrap p-3.5" data-status="planned">
          <div className="graph-grid">
            {d.sessions.map(s => <NodeCard key={s.session_id} s={s} />)}
          </div>
          {!d.sessions.length && (
            <div className="awl-empty">No agents yet — create one from the Agent panel's <b>Create</b> tab.</div>
          )}
        </div>
      </div>
    </section>
  )
}
