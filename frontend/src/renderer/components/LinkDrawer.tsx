// ============================================================================
// Link Config drawer — create/inspect agent-to-agent links (opens against the
// right column's left edge, keeping the Team panel visible). Live /links.
// ============================================================================

import React, { useEffect, useState } from 'react'
import { api, type LinkDirection, type LinkTrigger } from '../api'
import { useDash } from '../store'
import { Ic } from '../lib/icons'
import { identOf, AgTile, type Ident } from '../lib/identity'
import { toast } from '../lib/toast'

const TRIGGERS: { v: LinkTrigger; nm: string; sub: string }[] = [
  { v: 'now', nm: 'Now', sub: 'Interrupt & deliver immediately' },
  { v: 'inject', nm: 'Inject', sub: 'Deliver to the running target without stopping it' },
  { v: 'next', nm: 'Next', sub: "Deliver at the target's next turn boundary" },
  { v: 'queue', nm: 'Queue', sub: "Add to the target's prompt queue — the Direct-messaging default" },
  { v: 'hold', nm: 'Hold', sub: 'Stage for your manual approval before it\'s sent' },
  { v: 'piggyback', nm: 'Piggyback', sub: "Never initiates — rides the target's next inbound message · the Shared-context default" },
]
const CONTENT = ['Messages', 'Thinking', 'Files', 'Shell', 'Search', 'Workflow']

function EndpointDD({ sel, onSel, right }: { sel: string | null; onSel: (id: string) => void; right?: boolean }) {
  const d = useDash()
  const [open, setOpen] = useState(false)
  const cur = d.sessions.find(s => s.session_id === sel)
  const a: Ident | null = cur ? identOf(cur) : null
  return (
    <div data-comp="source-dropdown" className={`src-dd dd single flex-1 min-w-0${open ? ' open' : ''}`}>
      <button className="dd-trig" type="button" onClick={() => setOpen(o => !o)}>
        {a ? (<><AgTile a={a} /><span className="ag-lab"><span className="ag-role">{a.role}</span><span className="ag-name">{a.name}</span></span></>) : <span className="msel-ph">Pick agent…</span>}
        <Ic name="chevrons-up-down" className="picker-cv" />
      </button>
      <div className={`src-pop${right ? ' src-pop--right' : ''}${open ? ' open' : ''}`}>
        <div data-comp="agent-list" className="aglist">
          {d.sessions.map(s => {
            const ai = identOf(s)
            return (
              <button key={s.session_id} className={`agrow${sel === s.session_id ? ' on' : ''}`} type="button"
                onClick={() => { onSel(s.session_id); setOpen(false) }}>
                <AgTile a={ai} /><span className="ag-lab"><span className="ag-role">{ai.role}</span><span className="ag-name">{ai.name}</span></span><Ic name="check" className="ag-ck" />
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}

export function LinkDrawer() {
  const d = useDash()
  const [a, setA] = useState<string | null>(null)
  const [b, setB] = useState<string | null>(null)
  const [dir, setDir] = useState<LinkDirection>('both')
  const [rel, setRel] = useState<'direct' | 'shared'>('direct')
  const [content, setContent] = useState<Set<string>>(new Set(['Messages', 'Thinking']))
  const [backfill, setBackfill] = useState(false)
  const [trigger, setTrigger] = useState<LinkTrigger>('queue')
  const [trigOpen, setTrigOpen] = useState(false)
  const [limEx, setLimEx] = useState(false)
  const [limTok, setLimTok] = useState(false)
  const [exVal, setExVal] = useState('25')
  const [tokVal, setTokVal] = useState('100000')
  const [selLink, setSelLink] = useState<string | null>(null)

  useEffect(() => { if (!a && d.selectedId) setA(d.selectedId) }, [d.selectedId, d.drawer])

  const nextDir = () => setDir(p => p === 'a2b' ? 'b2a' : p === 'b2a' ? 'both' : 'a2b')
  const dirIcon = dir === 'a2b' ? 'arrow-right' : dir === 'b2a' ? 'arrow-left' : 'arrow-left-right'
  const dirTitle = dir === 'a2b' ? 'A → B' : dir === 'b2a' ? 'B → A' : 'A ↔ B (both)'

  const pickRel = (r: 'direct' | 'shared') => { setRel(r); setTrigger(r === 'direct' ? 'queue' : 'piggyback') }

  const save = async () => {
    if (!a || !b || a === b) { toast('Pick two different agents'); return }
    const r = await api.createLink({
      a, b, direction: dir, relationship: rel,
      shared_content: rel === 'shared' ? [...content].map(c => c.toLowerCase()) : [],
      shared_backfill: rel === 'shared' ? backfill : false,
      trigger,
      end_after_exchanges: limEx ? parseInt(exVal, 10) || 25 : null,
      end_after_tokens: limTok ? parseInt(tokVal, 10) || null : null,
    })
    toast(r ? 'Link saved' : 'Link rejected by the sidecar')
    d.refreshLinks()
  }
  const del = async () => {
    if (!selLink) { toast('Select a link in the list first'); return }
    const r = await api.deleteLink(selLink)
    toast(r ? 'Link removed' : 'Delete failed')
    setSelLink(null)
    d.refreshLinks()
  }

  const identFor = (id: string | null): Ident | null => {
    const s = d.sessions.find(x => x.session_id === id)
    return s ? identOf(s) : null
  }
  const active = d.links.links.filter(l => l.active)
  const expired = d.links.links.filter(l => !l.active)

  if (d.drawer !== 'link') return null
  return (
    <div data-comp="link-drawer" className="drawer">
      <div className="pcard-head"><h3>Link Config</h3><button className="ghost-ic" title="Close" onClick={() => d.setDrawer(null)}><Ic name="x" /></button></div>
      <div className="p-3 space-y-3">
        <div className="link-pair flex items-center gap-2">
          <EndpointDD sel={a} onSel={setA} />
          <button data-comp="direction-cycler" className="dir-cyc" title={dirTitle} onClick={nextDir}><Ic name={dirIcon} /></button>
          <EndpointDD sel={b} onSel={setB} right />
        </div>

        <div>
          <label className="lbl mb-1.5">Relationship <span className="text-muted-2 font-semibold normal-case">— one per link; both = two links</span></label>
          <div data-comp="segmented-control" className="seg">
            <button className={rel === 'direct' ? 'active' : ''} title="Reply-to conversation between the two agents" onClick={() => pickRel('direct')}>Direct messaging</button>
            <button className={rel === 'shared' ? 'active' : ''} title="Passive awareness — the target sees the source's selected context" onClick={() => pickRel('shared')}>Shared context</button>
          </div>
          {rel === 'shared' && (
            <div className="link-shared">
              <label className="lbl mb-1.5">Shared content <span className="text-muted-2 font-semibold normal-case">— what rides along</span></label>
              <div className="flex flex-wrap gap-1.5">
                {CONTENT.map(c => (
                  <button key={c} data-comp="mini-toggle" className={`minitog${content.has(c) ? ' on' : ''}`}
                    onClick={() => setContent(p => { const n = new Set(p); n.has(c) ? n.delete(c) : n.add(c); return n })}>{c}</button>
                ))}
              </div>
              <div className="flex items-center gap-2 mt-2">
                <button data-comp="switch" className={`swh${backfill ? ' on' : ''}`} onClick={() => setBackfill(v => !v)} title={backfill ? 'On — backfill all prior context once' : 'Off — incremental updates only'} />
                <span className="text-[10px] font-semibold text-foreground leading-tight">Share all prior context <span className="text-muted-2 font-normal">— one-time backfill, default off</span></span>
              </div>
            </div>
          )}
        </div>

        <div>
          <label className="lbl mb-1.5">Trigger</label>
          <div data-comp="trigger-dropdown" className="trig-dd">
            <button className="trig-trig" type="button" onClick={e => { e.stopPropagation(); setTrigOpen(o => !o) }}>
              <span className="trig-lbl">{TRIGGERS.find(t => t.v === trigger)?.nm}</span><Ic name="chevron-down" className="trig-cv" />
            </button>
            <div className={`split-menu${trigOpen ? ' open' : ''}`}>
              <div className="split-menu-h">When the link delivers</div>
              {TRIGGERS.map(t => (
                <button key={t.v} className={`split-mi${trigger === t.v ? ' sel' : ''}`} onClick={() => { setTrigger(t.v); setTrigOpen(false) }}>
                  <span className="lead"><b>{t.nm}</b><span className="sub">{t.sub}</span></span><span className="ck">✓</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        <div>
          <label className="lbl mb-1.5">End After <span className="text-muted-2 font-semibold normal-case">— no limit unless set</span></label>
          <div className="grid grid-cols-2 gap-2">
            <div data-comp="limit-toggle">
              <button className={`lim-tog${limEx ? ' on' : ''}`} onClick={() => setLimEx(v => !v)}>Exchanges</button>
              <input type="text" className="lim-in" placeholder="25" disabled={!limEx} value={exVal} onChange={e => setExVal(e.target.value)} />
            </div>
            <div>
              <button className={`lim-tog${limTok ? ' on' : ''}`} onClick={() => setLimTok(v => !v)}>Tokens</button>
              <input type="text" className="lim-in" placeholder="100k" disabled={!limTok} value={tokVal} onChange={e => setTokVal(e.target.value)} />
            </div>
          </div>
        </div>

        <div className="flex gap-2 pt-1">
          <button data-comp="button" className="btn-main flex-1" onClick={save}>Save</button>
          <button data-comp="button" className="btn-danger flex-1" onClick={del}>Delete</button>
        </div>

        <div>
          <div data-comp="link-list" className="link-list">
            {[['Active Links', active] as const, ['Expired Links', expired] as const].map(([lab, list]) => (
              <div className="link-sec open" key={lab}>
                <button className="link-sec-head" type="button" onClick={e => (e.currentTarget.closest('.link-sec') as HTMLElement)?.classList.toggle('open')}>
                  <Ic name="chevron-right" /><span>{lab}</span><span className="nav-cnt">{list.length}</span>
                </button>
                <div className="link-sec-body">
                  {list.map(l => {
                    const ai = identFor(l.a), bi = identFor(l.b)
                    return (
                      <button key={l.id} className={`link-row${selLink === l.id ? ' sel' : ''}`} onClick={() => setSelLink(selLink === l.id ? null : l.id)}>
                        <span className="text-[10px] font-bold">{ai?.name || l.a.slice(0, 8)}</span>
                        <Ic name={l.direction === 'both' ? 'arrow-left-right' : l.direction === 'a2b' ? 'arrow-right' : 'arrow-left'} />
                        <span className="text-[10px] font-bold">{bi?.name || l.b.slice(0, 8)}</span>
                        <span className="text-[9px] text-muted" style={{ marginLeft: 'auto' }}>{l.relationship === 'direct' ? 'Direct messaging' : 'Shared context'} · {l.exchanges} ex</span>
                      </button>
                    )
                  })}
                  {!list.length && <div className="awl-empty">none</div>}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
