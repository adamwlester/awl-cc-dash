// ============================================================================
// Agent selectors — the header accordion From/To drawers (in-flow, sticky).
// One shared roster (sessions → identities + User/System/Scratch) renders the
// feed filter tree, Compose From/To, and the History From filter, mirroring
// fillRosterLists in design/behavior.js.
// ============================================================================

import React, { useEffect, useState } from 'react'
import { useDash } from '../store'
import { Ic } from '../lib/icons'
import { AgTile, AgRow, IdentBadge, identOf, USER_IDENT, SYSTEM_IDENT, SCRATCH_IDENT, type Ident } from '../lib/identity'
import type { Subagent } from '../api'

export interface RosterRow {
  ident: Ident
  subs?: Subagent[]      // tree mount only
}

export function useRoster(): { agents: RosterRow[] } {
  const d = useDash()
  return {
    agents: d.sessions.map(s => ({ ident: identOf(s), subs: d.subagentsBy[s.session_id] || [] })),
  }
}

const SUB_CLASS: Record<string, string> = { running: 'sb-active', done: 'sb-idle', error: 'sb-error', waiting: 'sb-pending' }
const SUB_LAB: Record<string, string> = { running: 'running', done: 'done', error: 'error', waiting: 'waiting' }

/** Multi-select accordion (feed From/To filter · Compose To · History From). */
export function MultiAgAccordion({ id, header, rows, lead, sel, onSel, cap = 3, tree }: {
  id: string
  header: string
  rows: RosterRow[]
  lead?: Ident[]                 // leading pseudo rows (User/System or Scratch)
  sel: Set<string>
  onSel: (next: Set<string>) => void
  cap?: number
  tree?: boolean                 // subagent tree (leaf key = `${parent}:${subId}`)
}) {
  const [open, setOpen] = useState(false)
  const [expanded, setExpanded] = useState<Set<string>>(new Set())
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])

  const allKeys: string[] = [...(lead || []).map(l => l.key), ...rows.map(r => r.ident.key)]
  const leafKeys: string[] = tree ? rows.flatMap(r => (r.subs || []).map(su => `${r.ident.key}:${su.id}`)) : []
  const everything = [...allKeys, ...leafKeys]
  const allOn = everything.length > 0 && everything.every(k => sel.has(k))

  const toggle = (key: string, subKeys: string[] = []) => {
    const next = new Set(sel)
    const on = next.has(key)
    if (on) { next.delete(key); subKeys.forEach(k => next.delete(k)) }
    else { next.add(key); subKeys.forEach(k => next.add(k)) }
    onSel(next)
  }
  const allNone = () => onSel(allOn ? new Set() : new Set(everything))

  // trigger badges — selected top-level identities, collapsed to +N
  const selectedIdents: Ident[] = [
    ...(lead || []).filter(l => sel.has(l.key)),
    ...rows.filter(r => sel.has(r.ident.key)).map(r => r.ident),
  ]
  const shown = selectedIdents.slice(0, cap)
  const more = selectedIdents.length - shown.length

  return (
    <div data-comp="source-dropdown" id={id} className={`src-dd dd multi dd--acc${open ? ' open' : ''}`} data-agscope>
      <button className="dd-trig" type="button" onClick={() => setOpen(o => !o)}>
        <span data-comp="badge-strip" className="dd-badges">
          {shown.map(a => <IdentBadge a={a} key={a.key} />)}
          {more > 0 && <span className="badge-more" title={`${more} more`}>+{more}</span>}
          {!selectedIdents.length && <span className="msel-ph">None selected</span>}
        </span>
        <span className="acc-chevcell"><Ic name="chevron-right" className="acc-cv" /></span>
      </button>
      <div className={`src-pop src-acc${open ? ' open' : ''}`}>
        <div className="src-pop-head">
          <span className="sec-h" style={{ margin: 0 }}>{header}</span>
          <button data-comp="text-button" className="mini-link" onClick={allNone}>{allOn ? 'None' : 'All'}</button>
        </div>
        <div data-comp="agent-list" className="aglist aglist-scroll" style={{ maxHeight: 300 }}>
          {(lead || []).map(l => <AgRow key={l.key} a={l} on={sel.has(l.key)} onClick={() => toggle(l.key)} />)}
          {rows.map(r => {
            const k = r.ident.key
            const subs = tree ? (r.subs || []) : []
            if (!subs.length) return <AgRow key={k} a={r.ident} on={sel.has(k)} onClick={() => toggle(k)} />
            const subKeys = subs.map(su => `${k}:${su.id}`)
            const selN = subKeys.filter(sk => sel.has(sk)).length + (sel.has(k) ? 0 : 0)
            const isExp = expanded.has(k)
            return (
              <React.Fragment key={k}>
                <button className={`agrow agrow--parent${sel.has(k) ? ' on' : ''}${isExp ? ' subs-open' : ''}`} type="button"
                  onClick={() => toggle(k, subKeys)}>
                  <AgTile a={r.ident} />
                  <span className="ag-lab"><span className="ag-role">{r.ident.role}</span><span className="ag-name">{r.ident.name}</span></span>
                  <span className="ag-subcount" title={`${subKeys.filter(sk => sel.has(sk)).length} of ${subs.length} subagents selected`}>{subKeys.filter(sk => sel.has(sk)).length}/{subs.length}</span>
                  <span className="ag-exp" title="Show subagents" onClick={e => {
                    e.stopPropagation()
                    setExpanded(p => { const n = new Set(p); n.has(k) ? n.delete(k) : n.add(k); return n })
                  }}><Ic name="chevron-right" /></span>
                  <Ic name="check" className="ag-ck" />
                </button>
                <div className={`agrow-subs${isExp ? ' open' : ''}`}>
                  {subs.map(su => (
                    <button key={su.id} className={`agrow agrow--sub${sel.has(`${k}:${su.id}`) ? ' on' : ''}`} type="button"
                      onClick={() => toggle(`${k}:${su.id}`)}>
                      <span className={`sbadge ${SUB_CLASS[su.status] || 'sb-active'} sub-fbadge`}>{su.id}</span>
                      <span className="ag-lab"><span className="ag-role">{su.type || 'subagent'}</span><span className="ag-name">{SUB_LAB[su.status] || ''}</span></span>
                      <Ic name="check" className="ag-ck" />
                    </button>
                  ))}
                </div>
              </React.Fragment>
            )
          })}
        </div>
      </div>
    </div>
  )
}

/** Single-select accordion (Compose From — User + agents). */
export function SingleAgAccordion({ id, rows, lead, sel, onSel }: {
  id: string; rows: RosterRow[]; lead?: Ident[]; sel: string; onSel: (k: string) => void
}) {
  const [open, setOpen] = useState(false)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [])
  const all: Ident[] = [...(lead || []), ...rows.map(r => r.ident)]
  const cur = all.find(a => a.key === sel) || all[0] || USER_IDENT
  return (
    <div data-comp="source-dropdown" id={id} className={`src-dd dd single dd--acc${open ? ' open' : ''}`}>
      <button className="dd-trig" type="button" onClick={() => setOpen(o => !o)}>
        <AgTile a={cur} />
        <span className="ag-lab"><span className="ag-role">{cur.role}</span><span className="ag-name">{cur.name}</span></span>
        <Ic name="chevron-right" className="acc-cv" />
      </button>
      <div className={`src-pop src-acc${open ? ' open' : ''}`}>
        <div data-comp="agent-list" className="aglist">
          {all.map(a => <AgRow key={a.key} a={a} on={a.key === cur.key} onClick={() => { onSel(a.key); setOpen(false) }} />)}
        </div>
      </div>
    </div>
  )
}

export { USER_IDENT, SYSTEM_IDENT, SCRATCH_IDENT }
