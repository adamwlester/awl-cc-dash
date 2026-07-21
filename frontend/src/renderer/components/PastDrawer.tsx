// ============================================================================
// Past drawer — the resume picker + the per-agent archive (#17/#18, §7.12),
// now a second Team-panel drawer beside Link Config (same Sheet behavior; one
// drawer open at a time — the store's single `drawer` slot enforces it).
// RESUMABLE: GET /sessions/past — every persisted agent that isn't live (dead
// roster records + archived/retired ones), source-tagged, each with an honest
// `resumable` flag (a row with no conversation id reads greyed, Resume
// disabled). Resume → POST /sessions/resume: relaunch on the SAME conversation
// (never a fork); resuming an archived row also un-retires it. ARCHIVE: the
// deep-freeze records behind the rows (GET /archive) — expandable key/value
// cards over Resume + the true-delete (DELETE /archive/{id}, behind the
// designed inline danger confirm; the referenced transcript is untouched).
// ============================================================================

import React, { useEffect, useState } from 'react'
import { api, type PastAgent, type ArchiveRecord, type Identity } from '../api'
import { useDash } from '../store'
import { Ic, AgGlyph } from '../lib/icons'
import { clearAttachCache } from './Console'
import { modelLabel } from '../lib/identity'
import { toast } from '../lib/toast'

function pastStampFmt(iso: string | null | undefined): string {
  if (!iso) return '—'
  const d2 = new Date(iso)
  if (isNaN(d2.getTime())) return String(iso).slice(0, 16)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${p(d2.getMonth() + 1)}-${p(d2.getDate())} ${p(d2.getHours())}:${p(d2.getMinutes())}`
}
function pastIdentBits(identity: Identity | null, fallbackName?: string | null, sessionId?: string | null) {
  const num = identity?.number != null ? String(identity.number).padStart(2, '0') : ''
  // A fork's backend-assigned identity can carry an empty name (backend gap):
  // fall back to the session id it always has rather than a blank / bare "—".
  const idShort = sessionId ? sessionId.replace(/^awl-/, '').slice(0, 8) : ''
  return {
    role: identity?.role || 'agent',
    display: `${num ? num + ' ' : ''}${identity?.name || fallbackName || idShort || '—'}`,
    color: identity?.color || 'var(--muted)',
    icon: identity?.icon || '',
  }
}

/** The drawer shell — conditional render keeps the body (and its 5s poll)
    mount-scoped to the drawer actually being open. */
export function PastDrawer() {
  const d = useDash()
  if (d.drawer !== 'past') return null
  return <PastDrawerBody />
}

function PastDrawerBody() {
  const d = useDash()
  const [past, setPast] = useState<PastAgent[] | null>(null)
  const [arch, setArch] = useState<ArchiveRecord[] | null>(null)
  const [openArc, setOpenArc] = useState<Set<string>>(new Set())
  const [confirmArc, setConfirmArc] = useState<string | null>(null)
  const [busyKey, setBusyKey] = useState<string | null>(null)

  // Own 5s cadence while the drawer is open (in-flight guarded) — never bundled
  // into the roster poll (#33's lesson).
  useEffect(() => {
    let cancelled = false
    let inflight = false
    const pull = async () => {
      if (inflight) return
      inflight = true
      try {
        const [p, ar] = await Promise.all([api.sessionsPast(), api.archive()])
        if (cancelled) return
        if (p) setPast(p.past)
        if (ar) setArch(ar.archived)
      } finally { inflight = false }
    }
    pull()
    const i = setInterval(pull, 5000)
    return () => { cancelled = true; clearInterval(i) }
  }, [])

  const refresh = async () => {
    const [p, ar] = await Promise.all([api.sessionsPast(), api.archive()])
    if (p) setPast(p.past)
    if (ar) setArch(ar.archived)
  }

  const doResume = async (sel: { session_id?: string; archive_id?: string }, label: string) => {
    const key = sel.archive_id || sel.session_id || ''
    setBusyKey(key)
    const r = await api.resumeSession(sel.archive_id ? { archive_id: sel.archive_id } : { session_id: sel.session_id })
    setBusyKey(null)
    if (r.ok && r.data) {
      clearAttachCache(r.data.session_id)   // NU-6: the pre-death attach is stale after resume — the recycled port could even be another agent's terminal; force a fresh attach
      toast(`Resumed ${label} — same conversation, same identity${r.data.resumed_from === 'archive' ? ' (un-retired from the archive)' : ''}`)
      d.select(r.data.session_id)
      d.setAgentTab('details')
      refresh()
    } else {
      toast(`Resume failed: ${r.detail || 'sidecar error'}`)   // honest 400/404/409 verbatim
    }
  }

  const doArcDelete = async (arcId: string, label: string) => {
    setConfirmArc(null)
    const r = await api.deleteArchive(arcId)
    toast(r.ok ? `Archive record ${arcId} deleted forever (${label}'s transcript is untouched)` : `Delete failed: ${r.detail || 'sidecar error'}`)
    refresh()
  }

  const rows = past || []
  const arcs = arch || []
  const rez = rows.filter(p => p.resumable).length
  const kv = (k: string, v: React.ReactNode, plain?: boolean) => (
    <div className="arch-kv"><span className="k">{k}</span><span className={`v${plain ? ' plain' : ''}`}>{v}</span></div>
  )

  return (
    <div data-comp="past-drawer" className="drawer drawer--past">
      <div className="pcard-head"><h3>Past</h3><button className="ghost-ic" title="Close" onClick={() => d.setDrawer(null)}><Ic name="x" /></button></div>
      <div data-group="mid" className="p-3 space-y-3">
      <div className="agent-head">
        <span className="agtile agtile--user" style={{ width: 'var(--size-40)', height: 'var(--size-40)' }}><Ic name="history" className="agtile-luc" /></span>
        <div className="min-w-0 flex-1">
          <div className="text-[15px] font-heading text-foreground leading-tight" style={{ fontWeight: 900 }}>Past agents</div>
          <div className="text-[10px] text-muted font-semibold">resume a dead or archived agent — same conversation, same identity</div>
        </div>
      </div>

      <div>
        <div className="ro-head">
          <span className="ro-label" title="Every persisted agent that isn't live right now — dead roster records plus the archive, merged and source-tagged. Resume relaunches the agent on its own conversation (never a fork); a row with no conversation id can't resume and reads greyed.">Resumable</span>
          <span className="ml-auto text-[9.5px] text-muted font-mono font-semibold">{past == null ? '…' : `${rows.length} past · ${rez} resumable`}</span>
        </div>
        <div data-comp="past-agent-picker" className="aglist past-list">
          {rows.map(p => {
            const b = pastIdentBits(p.identity, p.name, p.session_id)
            // Roster rows carry the mockup's "died …" stamp when the sidecar
            // witnessed the stop/death (#17 died_at); legacy records and
            // unwitnessed deaths (reboot) fall back to the created stamp.
            const stamp = p.source === 'archive' ? `retired ${pastStampFmt(p.retired_at)}`
              : p.died_at ? `died ${pastStampFmt(p.died_at)}` : `created ${pastStampFmt(p.created_at)}`
            const key = p.archive_id || p.session_id || b.display
            return (
              <div key={key} data-comp="past-agent-row" className={`agrow past-row${p.resumable ? '' : ' past-row--norez'}`}
                title={p.resumable ? `${p.model || 'model —'} · ${stamp}` : 'No conversation id persisted — can’t resume onto its conversation'}>
                <span className="agtile" style={{ width: 'var(--size-28)', height: 'var(--size-28)', color: b.color }}><AgGlyph icon={b.icon} color={b.color} /></span>
                <span className="ag-lab">
                  <span className="ag-role">{b.role}{p.model ? ` · ${modelLabel(p.model)}` : ''}</span>
                  <span className="ag-name">{b.display}</span>
                </span>
                <span data-comp="past-source-badge" className={`past-src${p.source === 'archive' ? ' past-src--archive' : ''}`}
                  title={p.source === 'archive' ? 'From the archive — Resume un-retires it' : 'A dead roster record — the agent process is gone, the record persists'}>{p.source}</span>
                <span className="past-stamp">{stamp}</span>
                <button data-comp="button" className="btn btn-sm past-resume" disabled={!p.resumable || busyKey === key}
                  title={p.resumable ? 'Resume — relaunch on the same conversation, same identity' : 'Can’t resume — no conversation id to resume onto'}
                  onClick={() => doResume(p.source === 'archive' && p.archive_id ? { archive_id: p.archive_id } : { session_id: p.session_id || undefined }, b.display)}>
                  <Ic name="rotate-ccw" className="w-3 h-3" />{busyKey === key ? 'Resuming…' : 'Resume'}
                </button>
              </div>
            )
          })}
          {past != null && !rows.length && <div className="awl-empty">No past agents — everything persisted is live.</div>}
          {past == null && <div className="awl-empty">reading the past-agents feed…</div>}
        </div>
      </div>

      <div>
        <div className="ro-head">
          <span className="ro-label" title="Retire = deep-freeze: a light archive record — identity snapshot, created/retired stamps, lineage, per-agent git author — with the transcript referenced in place, never copied. Resume un-retires the agent; Delete forever true-deletes the record (the referenced transcript is untouched).">Archive</span>
          <span className="ml-auto text-[9.5px] text-muted font-mono font-semibold">{arch == null ? '…' : `${arcs.length} archived`}</span>
        </div>
        <div data-comp="archive-roster" className="arch-list">
          {arcs.map(rec => {
            const b = pastIdentBits((rec.identity as Identity) || null, rec.name, rec.session_id)
            const lin = rec.lineage || {}
            const linBits = [
              lin.parent ? `parent ${lin.parent}` : null,
              lin.fork ? `fork${typeof lin.fork === 'object' && lin.fork?.rewound_to != null ? ` @ turn ${lin.fork.rewound_to}` : ''}` : null,
              lin.handoff ? `handoff ${typeof lin.handoff === 'string' ? lin.handoff : ''}`.trim() : null,
            ].filter(Boolean).join(' · ')
            const isOpen = openArc.has(rec.archive_id)
            return (
              <div key={rec.archive_id} data-comp="archive-row" className={`fcard arch-card${isOpen ? ' open' : ''}`}>
                <div className="fcard-head">
                  <button className="fcard-exp" onClick={() => setOpenArc(prev => { const n = new Set(prev); n.has(rec.archive_id) ? n.delete(rec.archive_id) : n.add(rec.archive_id); return n })} title="Expand the archive record">
                    <span className="agtile" style={{ width: 'var(--size-28)', height: 'var(--size-28)', color: b.color }}><AgGlyph icon={b.icon} color={b.color} /></span>
                    <span className="ag-lab"><span className="ag-role">{b.role}</span><span className="ag-name">{b.display}</span></span>
                    <span className="fcard-time">retired {pastStampFmt(rec.retired_at)}</span>
                  </button>
                  <button className="fcard-chevbtn" onClick={() => setOpenArc(prev => { const n = new Set(prev); n.has(rec.archive_id) ? n.delete(rec.archive_id) : n.add(rec.archive_id); return n })} title="Expand / collapse"><Ic name="chevron-right" className="fcard-chev" /></button>
                </div>
                {confirmArc === rec.archive_id && (
                  <div data-comp="inline-confirm" className="tl-confirm foot-confirm--danger arch-del-confirm" style={{ display: 'flex' }}>
                    <span>Delete {b.display}&#8217;s archive record forever? This can&#8217;t be undone (the transcript it references is untouched).</span>
                    <button className="btn btn-sm ml-auto" onClick={() => setConfirmArc(null)}>Cancel</button>
                    <button className="btn-danger-solid btn-sm" onClick={() => doArcDelete(rec.archive_id, b.display)}><Ic name="trash-2" className="w-3.5 h-3.5" />Delete forever</button>
                  </div>
                )}
                <div className="fcard-body arch-body">
                  {kv('Archive id', rec.archive_id)}
                  {kv('Created', pastStampFmt(rec.created_at))}
                  {kv('Retired', pastStampFmt(rec.retired_at))}
                  {kv('Model · mode', `${modelLabel(rec.model)} · ${rec.permission_mode || '—'}`, true)}
                  {kv('CWD', rec.cwd || '—')}
                  {kv('Lineage', linBits || '—', !linBits)}
                  {kv('Git author', (rec as any).git_author_email || '—')}
                  {kv('Transcript', rec.transcript?.transcript_path || '—')}
                  <div className="arch-acts">
                    <button data-comp="button" className="btn btn-sm" disabled={!rec.transcript?.claude_session_id}
                      title={rec.transcript?.claude_session_id ? 'Resume — un-retires the agent back onto the roster, same conversation' : 'Can’t resume — no conversation id referenced'}
                      onClick={() => doResume({ archive_id: rec.archive_id }, b.display)}><Ic name="rotate-ccw" className="w-3 h-3" />Resume</button>
                    <span className="flex-1" />
                    <button data-comp="button" className="btn-danger btn-sm" title="Delete forever — true-deletes this archive record (the referenced transcript is untouched)"
                      onClick={() => setConfirmArc(rec.archive_id)}><Ic name="trash-2" className="w-3 h-3" />Delete forever</button>
                  </div>
                </div>
              </div>
            )
          })}
          {arch != null && !arcs.length && <div className="awl-empty">No archived agents — Retire deep-freezes an agent here.</div>}
          {arch == null && <div className="awl-empty">reading the archive…</div>}
        </div>
      </div>

      {/* the old Past-tab footer note, folded into the drawer body */}
      <div className="text-[9.5px] text-muted font-mono font-semibold">Resume relaunches on the same conversation, never a fork — actions are per-row.</div>
      </div>
    </div>
  )
}
