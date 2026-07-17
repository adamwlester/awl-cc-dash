// ============================================================================
// Library — Plans · Documents · Assets (middle column, bottom).
// Plans + Documents render as the shared reviewable-document card: entry-nav
// beside single-open cards, the line-numbered editor with the select-to-act
// rail, comments via the sidecar .meta.json sidecars, raw-markdown edit → PUT,
// and the decision footer. Assets lists the project's materialized attachments
// (GET /library/assets) as the rail + preview, thumbnails via the decided
// Electron nativeImage/getFileIcon IPC (§7.16). The header Import control
// (§11 #28) pulls an external Claude session in through GET/POST
// /import/external — to an agent's queue, read here, or filed as a doc.
// ============================================================================

import React, { useEffect, useMemo, useRef, useState } from 'react'
import { api, API, type LibraryDoc, type DocMeta, type AssetRecord, type ImportSessionRow } from '../api'
import { useDash } from '../store'
import { Ic } from '../lib/icons'
import { identOf, IdentBadge, AgTile, USER_IDENT, type Ident } from '../lib/identity'
import { ExportControl } from './ExportControl'
import { toast } from '../lib/toast'

interface Entry {
  id: string
  doc: LibraryDoc
  meta: DocMeta | null
  kind: 'plan' | 'doc'
}

const BADGE: Record<string, [string, string]> = {
  review: ['db-review', 'In review'], approved: ['db-approved', 'Approved'], draft: ['db-draft', 'Draft'],
  revise: ['db-review', 'Revise'], rejected: ['db-held', 'Rejected'],
}
function lifeOf(meta: DocMeta | null): [string, string] {
  const s = (meta?.verdict === 'approve' || meta?.state === 'approved') ? 'approved' : (meta?.state || 'draft')
  return BADGE[s] || BADGE.draft
}

function inlineMd(s: string): React.ReactNode {
  const parts = s.split(/(`[^`]+`|\*\*[^*]+\*\*)/g)
  return parts.map((p, i) => {
    if (p.startsWith('`') && p.endsWith('`')) return <span key={i} className="md-code-i">{p.slice(1, -1)}</span>
    if (p.startsWith('**') && p.endsWith('**')) return <b key={i}>{p.slice(2, -2)}</b>
    return p
  })
}

export function Library() {
  const d = useDash()
  const [plans, setPlans] = useState<Entry[]>([])
  const [docs, setDocs] = useState<Entry[]>([])
  const [openId, setOpenId] = useState<string | null>(null)
  const bump = useRef(0)
  const [refresh, setRefresh] = useState(0)
  const [impOpen, setImpOpen] = useState(false)
  // Import destination "Read now" (panel): the returned markdown renders here
  // as a read-only doc surface (nothing is filed).
  const [readDoc, setReadDoc] = useState<{ title: string; markdown: string } | null>(null)

  useEffect(() => {
    let cancelled = false
    const load = async () => {
      if (!d.projectCwd) { setPlans([]); setDocs([]); return }
      const [pl, dc, root, reviews] = await Promise.all([
        api.libraryDocuments(d.projectCwd, 'plans'),
        api.libraryDocuments(d.projectCwd, 'docs'),
        api.libraryDocuments(d.projectCwd),
        api.libraryReviews(d.projectCwd),
      ])
      if (cancelled) return
      if (pl == null && dc == null && root == null) return   // sidecar unreachable — freeze on last-known (#38)
      // GET /library/reviews keys by LEAF FILENAME with owner/state/verdict
      // NESTED under `review` (comments/provenance are top-level) — key by
      // filename and flatten the review block up so lifeOf/counters read flat.
      const meta = (fn: string): DocMeta | null => { const m: any = reviews?.[fn]; return m ? { ...m, ...(m.review || {}) } : null }
      if (pl != null) setPlans(pl.map(doc => ({ id: `plan-${doc.filename}`, doc, meta: meta(doc.filename), kind: 'plan' as const })))
      const seen = new Set<string>()
      const dd: Entry[] = []
      for (const doc of [...(dc || []), ...(root || [])]) {
        if (seen.has(doc.path)) continue
        seen.add(doc.path)
        dd.push({ id: `doc-${doc.filename}-${dd.length}`, doc, meta: meta(doc.filename), kind: 'doc' })
      }
      if (dc != null || root != null) setDocs(dd)
    }
    load()
    const i = setInterval(load, 8000)
    return () => { cancelled = true; clearInterval(i) }
  }, [d.projectCwd, refresh])

  const entries = d.libTab === 'plan' ? plans : docs
  const awaiting = plans.filter(p => p.meta?.state === 'review').length
  const plansBadge = plans.filter(p => p.meta?.state === 'review' || (!p.meta?.verdict && p.meta?.state !== 'approved')).length
  const docsBadge = docs.filter(x => x.meta?.state === 'review').length

  return (
    <section className="rz-panel" id="pDocs" style={{ flex: '1 1 44%', minHeight: 'var(--pane-docs-min-h)', maxHeight: 'var(--pane-docs-max-h)' }}>
      <div className="pcard-head">
        <h3>Library</h3>
        <div data-comp="tab-bar" className="tabset">
          <button className={`tab-btn${d.libTab === 'plan' ? ' active' : ''}`} onClick={() => d.setLibTab('plan')}>Plans{plansBadge > 0 && <span data-comp="count-square" className="req-badge ml-1">{plansBadge}</span>}</button>
          <button className={`tab-btn${d.libTab === 'documents' ? ' active' : ''}`} onClick={() => d.setLibTab('documents')}>Documents{docsBadge > 0 && <span data-comp="count-square" className="req-badge ml-1">{docsBadge}</span>}</button>
          <button className={`tab-btn${d.libTab === 'assets' ? ' active' : ''}`} onClick={() => d.setLibTab('assets')}>Assets</button>
          {/* IMPORT lives on the Library header (host decision — DESIGN.md → Library): reachable from all three tabs. */}
          <button data-comp="import-button" className="btn btn-sm lib-import-btn" onClick={() => setImpOpen(o => !o)}
            title="Import an external Claude session (claude.ai web / the desktop app) — deliver to an agent, read it here, or file it as a reference doc">
            <Ic name="download-cloud" className="w-3.5 h-3.5" />Import
          </button>
        </div>
      </div>
      <div className="pcard-body flex flex-col overflow-hidden" style={{ background: 'var(--background)' }}>
        {impOpen && (
          <ImportDrawer
            onClose={() => setImpOpen(false)}
            onRead={(title, markdown) => { setReadDoc({ title, markdown }); setImpOpen(false) }}
            onFiled={() => { setImpOpen(false); d.setLibTab('documents'); setRefresh(x => x + 1) }} />
        )}
        {readDoc && <ImportReadCard doc={readDoc} onClose={() => setReadDoc(null)} />}
        {!readDoc && (d.libTab === 'plan' || d.libTab === 'documents') && (
          <div className="flex-1 min-h-0 flex p-2.5 gap-2.5">
            <nav data-comp="entry-nav" className="docnav">
              {entries.map(e => {
                const bb = lifeOf(e.meta)
                const fn = e.doc.filename
                const dir = e.doc.path.slice(0, e.doc.path.length - fn.length)
                return (
                  <div key={e.id} className={`docnav-row navcard${openId === e.id ? ' on' : ''}`} role="button" tabIndex={0}
                    onClick={() => setOpenId(openId === e.id ? null : e.id)}
                    onKeyDown={ev => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); setOpenId(openId === e.id ? null : e.id) } }}>
                    <div className="docnav-top">
                      <span className="docnav-lab">
                        <span className="docnav-name">{e.kind === 'plan' ? fn.replace(/\.md$/, '') : fn}</span>
                        {e.kind === 'doc' && <span className="docnav-path">{dir}</span>}
                      </span>
                      {e.kind === 'doc' && (
                        <span className="docnav-acts">
                          <button data-comp="ghost-icon-button" className="ghost-ic" title="Rename" onClick={async ev => {
                            ev.stopPropagation()
                            const nn = prompt('Rename to', fn)
                            if (nn && d.projectCwd) { const r = await api.renameDocument({ cwd: d.projectCwd, path: e.doc.path, new_filename: nn }); toast(r ? `Renamed → ${nn}` : 'Rename failed (store docs only)'); setRefresh(x => x + 1) }
                          }}><Ic name="pencil" /></button>
                        </span>
                      )}
                    </div>
                    <div className="docnav-life"><span data-comp="lifecycle-badge" className={`dbadge ${bb[0]}`}>{bb[1]}</span></div>
                  </div>
                )
              })}
              {d.libTab === 'documents' && (
                <div data-comp="add-menu" className="docnav-addwrap">
                  <button className="docnav-add" onClick={async () => {
                    if (!d.projectCwd) { toast('No project open'); return }
                    const name = prompt('New document filename', `notes-${Date.now() % 10000}.md`)
                    if (!name) return
                    const r = await api.createDocument({ cwd: d.projectCwd, filename: name, content: `# ${name.replace(/\.md$/, '')}\n`, subdir: 'docs' })
                    toast(r ? `Added ${name}` : 'Add failed')
                    setRefresh(x => x + 1)
                  }}><Ic name="plus" />Add document</button>
                </div>
              )}
              {!entries.length && <div className="awl-empty">{d.projectCwd ? 'nothing here yet' : 'no project open'}</div>}
            </nav>
            <div className="docmain flex-1 min-h-0 flex flex-col overflow-hidden">
              {d.libTab === 'plan' && (
                <div className="text-[9px] text-muted font-mono mb-2 flex items-center flex-none">
                  <span>&lt;project&gt;/plans/</span><span className="flex-1" />
                  <span>{plans.length} plan{plans.length === 1 ? '' : 's'} · {awaiting} awaiting review</span>
                </div>
              )}
              <div className="flex flex-col gap-2 overflow-y-auto flex-1 min-h-0">
                {entries.map(e => (
                  <PlanCard key={e.id} e={e} open={openId === e.id} onToggle={() => setOpenId(openId === e.id ? null : e.id)}
                    onChanged={() => setRefresh(x => x + 1)} />
                ))}
                {!entries.length && <div className="awl-empty">{d.projectCwd ? `No ${d.libTab === 'plan' ? 'plans' : 'documents'} in this project yet.` : 'Open a project to see its library.'}</div>}
              </div>
            </div>
          </div>
        )}

        {!readDoc && d.libTab === 'assets' && <AssetsTab />}
      </div>
    </section>
  )
}

// ---- Import drawer (§11 #28) — in-flow under the panel header ---------------------
// Source segment (Web = claude.ai · Desktop = the desktop app's local store) →
// the session list by title (filterable; the honest 4xx message renders
// verbatim where the list would be) → ONE destination (agent queue · read now ·
// file as doc). Esc / the ghost-x close.
function ImportDrawer({ onClose, onRead, onFiled }: {
  onClose: () => void
  onRead: (title: string, markdown: string) => void
  onFiled: () => void
}) {
  const d = useDash()
  const [src, setSrc] = useState<'web' | 'desktop'>('web')
  const [rows, setRows] = useState<ImportSessionRow[] | null>(null)
  const [listErr, setListErr] = useState<string | null>(null)
  const [filter, setFilter] = useState('')
  const [selIdx, setSelIdx] = useState<number | null>(null)
  const [dest, setDest] = useState<'agent' | 'read' | 'doc'>('agent')
  const [agent, setAgent] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const [runErr, setRunErr] = useState<string | null>(null)

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.stopPropagation(); onClose() } }
    document.addEventListener('keydown', onKey, true)
    return () => document.removeEventListener('keydown', onKey, true)
  }, [onClose])

  // List on open + on source switch — the 4xx (missing session key, no desktop
  // store, tool missing) renders exactly as returned.
  useEffect(() => {
    let cancelled = false
    setRows(null); setListErr(null); setSelIdx(null)
    api.importList(src).then(r => {
      if (cancelled) return
      if (r.ok && r.data) setRows(r.data.sessions)
      else setListErr(r.detail || 'listing failed')
    })
    return () => { cancelled = true }
  }, [src])

  useEffect(() => { if (!agent && d.sessions.length) setAgent(d.sessions[0].session_id) }, [d.sessions, agent])

  const q = filter.trim().toLowerCase()
  const visible = (rows || []).map((r, i) => ({ r, i })).filter(x => !q || x.r.title.toLowerCase().includes(q))
  const picked = selIdx != null ? (rows || [])[selIdx] : null
  const destLabel = dest === 'agent'
    ? (agent ? (() => { const s = d.sessions.find(x => x.session_id === agent); return s ? `${identOf(s).role} ${identOf(s).name}` : 'agent' })() : 'agent')
    : dest === 'read' ? 'read now' : 'Documents'

  const run = async () => {
    if (!picked) return
    if (dest === 'agent' && !agent) { toast('Pick a target agent'); return }
    if (dest === 'doc' && !d.projectCwd) { toast('No project open — File as doc needs a project store'); return }
    setBusy(true); setRunErr(null)
    const r = await api.importRun({
      source: src, title: picked.title,
      destination: dest === 'agent' ? 'agent' : dest === 'read' ? 'panel' : 'library',
      target_agent: dest === 'agent' ? agent : undefined,
      cwd: dest === 'doc' ? d.projectCwd : undefined,
    })
    setBusy(false)
    if (!r.ok || !r.data) { setRunErr(r.detail || 'import failed'); return }
    if (dest === 'agent') {
      const s = d.sessions.find(x => x.session_id === agent)
      toast(`Queued import → ${s ? identOf(s).name : agent} — “${r.data.title}” lands on its prompt queue`)
      onClose()
    } else if (dest === 'read') {
      onRead(r.data.title, r.data.markdown || '(the import returned no markdown)')
      toast('Imported for reading — opened here (read-only, nothing filed)')
    } else {
      toast(`Imported → Documents · ${r.data.filename}`)
      onFiled()
    }
  }

  return (
    <div data-comp="import-drawer" className={`imp-drawer${rows != null && !listErr && visible.length === 0 ? ' empty' : ''}`}>
      <div className="imp-head"><Ic name="download-cloud" /><span>Import a Claude session</span>
        <button data-comp="ghost-icon-button" className="ghost-ic" title="Close (Esc)" onClick={onClose}><Ic name="x" /></button></div>
      <div className="imp-grid">
        <div className="imp-col">
          <span className="lbl">Source</span>
          <div data-comp="segmented-control" className="seg imp-src-seg">
            <button className={src === 'web' ? 'active' : ''} onClick={() => setSrc('web')}>Web</button>
            <button className={src === 'desktop' ? 'active' : ''} onClick={() => setSrc('desktop')}>Desktop</button>
          </div>
          <div className="imp-srcnote">{src === 'web' ? 'claude.ai chats, listed by title' : 'the desktop app’s local sessions, read off disk'}</div>
          <span className="lbl imp-lbl-gap">Destination</span>
          <div className="imp-dests">
            <button data-comp="option-card" className={`opt${dest === 'agent' ? ' on' : ''}`} onClick={() => setDest('agent')}><span className="opt-nm">To agent</span><span className="opt-desc">deliver to an agent — lands on its prompt queue as context</span></button>
            <button data-comp="option-card" className={`opt${dest === 'read' ? ' on' : ''}`} onClick={() => setDest('read')}><span className="opt-nm">Read now</span><span className="opt-desc">open here in the Library as a read-only doc</span></button>
            <button data-comp="option-card" className={`opt${dest === 'doc' ? ' on' : ''}`} onClick={() => setDest('doc')}><span className="opt-nm">File as doc</span><span className="opt-desc">file into Documents as a reference doc</span></button>
          </div>
          <div className={`imp-aglist${dest === 'agent' ? ' show' : ''}`}>
            <div className="aglist aglist-scroll imp-agscroll">
              {d.sessions.map(s => {
                const a = identOf(s)
                return (
                  <button key={s.session_id} className={`agrow${agent === s.session_id ? ' on' : ''}`} onClick={() => setAgent(s.session_id)}>
                    <AgTile a={a} /><span className="ag-lab"><span className="ag-role">{a.role}</span><span className="ag-name">{a.name}</span></span><Ic name="check" className="ag-ck" />
                  </button>
                )
              })}
              {!d.sessions.length && <div className="awl-empty">no live agents to deliver to</div>}
            </div>
          </div>
        </div>
        <div className="imp-col imp-col--sessions">
          <span className="lbl">Session</span>
          <div data-comp="search-input" className="imp-filter"><Ic name="search" /><input placeholder="Filter by title…" value={filter} onChange={e => setFilter(e.target.value)} /></div>
          {listErr
            ? <div className="imp-none" style={{ display: 'block' }}>{listErr}</div>
            : rows == null
              ? <div className="awl-empty">listing {src === 'web' ? 'claude.ai chats' : 'desktop sessions'}…</div>
              : (
                <div className="imp-list">
                  {visible.map(({ r, i }) => (
                    <button key={`${r.title}-${i}`} data-comp="import-session-row" className={`imp-row${selIdx === i ? ' on' : ''}`} onClick={() => setSelIdx(i)}>
                      <span className="imp-t">{r.title}</span>
                      <span className="imp-meta">{[r.updated_at, r.model].filter(Boolean).join(' · ') || r.source}</span>
                    </button>
                  ))}
                </div>
              )}
          <div className="imp-none">No sessions match.</div>
        </div>
      </div>
      {runErr && <div className="imp-srcnote" style={{ color: 'var(--danger)', marginTop: 'var(--space-6)' }}>{runErr}</div>}
      <div className="imp-foot">
        <span className="imp-sel">{picked ? `“${picked.title}” → ${destLabel}` : 'Pick a session to import'}</span>
        <button data-comp="button" className="btn-main btn-sm" disabled={!picked || busy} onClick={run}
          title="Import the picked session to the chosen destination">
          <Ic name="download-cloud" className="w-3 h-3" />{busy ? 'Importing…' : 'Import'}
        </button>
      </div>
    </div>
  )
}

// ---- Import "Read now" surface — the returned markdown, read-only ------------------
function ImportReadCard({ doc, onClose }: { doc: { title: string; markdown: string }; onClose: () => void }) {
  const lines = doc.markdown.split('\n')
  return (
    <div className="flex-1 min-h-0 flex flex-col p-2.5" data-comp="import-read-card">
      <div data-comp="editor-header" className="lib-edit-head" style={{ flex: '0 0 auto' }}>
        <span className="lib-edit-lab">Read-only</span>
        <span className="lib-edit-fname" title={doc.title}>{doc.title}</span>
        <span className="flex-1" />
        <button data-comp="ghost-icon-button" className="ghost-ic" title="Close the imported read" onClick={onClose}><Ic name="x" /></button>
      </div>
      <div data-comp="doc-editor" className="doc-ed" style={{ flex: '1 1 auto', minHeight: 0, overflowY: 'auto' }}>
        <div className="md">
          {lines.map((ln, i) => (
            <div className="md-row" key={i} data-line={i + 1}>
              <span className="md-rail"><span className="rn">{i + 1}</span></span>
              {/^#\s+/.test(ln)
                ? <span className="md-line md-h1">{inlineMd(ln.replace(/^#\s+/, ''))}</span>
                : /^#{2,4}\s+/.test(ln)
                  ? <span className={`md-line md-h${(ln.match(/^(#+)/) as any)[1].length}`}>{inlineMd(ln.replace(/^#{2,4}\s+/, ''))}</span>
                  : ln.trim() === ''
                    ? <span className="md-line md-blank"> </span>
                    : <span className="md-line">{inlineMd(ln)}</span>}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// ---- Assets tab (§7.16) — rail + preview over GET /library/assets ------------------
const IMG_EXT = new Set(['png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp', 'tiff'])
const isImageFile = (name: string) => IMG_EXT.has((name.split('.').pop() || '').toLowerCase())
const fileTypeIcon = (name: string) => (isImageFile(name) ? 'file-image' : 'file-text')

// Thumbnail via the decided mechanism (§7.16): main-process IPC →
// nativeImage.createThumbnailFromPath (Shell provider) → app.getFileIcon
// fallback; when the IPC is absent (browser verification) or both fail, an
// image asset falls back to its byte-endpoint URL, others to the type icon.
function useThumb(rec: AssetRecord, cwd: string | null): string | null {
  const [url, setUrl] = useState<string | null>(null)
  useEffect(() => {
    let cancelled = false
    setUrl(null)
    const thumb = (window as any).awl?.thumb as ((p: string) => Promise<string | null>) | undefined
    // The Shell provider needs a WINDOWS path: derive it from the store cwd +
    // the record's rel_path (both are store-truths from the listing).
    const winPath = cwd && rec.rel_path ? `${cwd.replace(/[\\/]+$/, '')}\\.awl-cc-dash\\${String(rec.rel_path).replace(/\//g, '\\')}` : null
    const fallback = () => { if (!cancelled) setUrl(rec.http_url && isImageFile(rec.filename) ? `${API}${rec.http_url}` : null) }
    if (thumb && winPath) thumb(winPath).then(u => { if (!cancelled) { u ? setUrl(u) : fallback() } }).catch(fallback)
    else fallback()
    return () => { cancelled = true }
  }, [rec.id, rec.rel_path, cwd])
  return url
}

function AssetThumb({ rec, cwd }: { rec: AssetRecord; cwd: string | null }) {
  const url = useThumb(rec, cwd)
  if (url) return <span data-comp="asset-thumb" className="asset-thumb" title={rec.filename}><img className="awl-asset-thumb" src={url} alt="" /></span>
  return <span data-comp="asset-thumb" className="asset-thumb asset-thumb--icon" title={rec.filename}><Ic name={fileTypeIcon(rec.filename)} /></span>
}

function AssetsTab() {
  const d = useDash()
  const [assets, setAssets] = useState<AssetRecord[] | null>(null)
  const [selId, setSelId] = useState<string | null>(null)
  const [confirmDel, setConfirmDel] = useState<string | null>(null)   // asset id awaiting the inline confirm

  useEffect(() => {
    let cancelled = false
    let inflight = false
    const pull = async () => {
      if (!d.projectCwd) { setAssets([]); return }
      if (inflight) return
      inflight = true
      try {
        const r = await api.libraryAssets(d.projectCwd)
        if (!cancelled && r != null) setAssets(r)
      } finally { inflight = false }
    }
    pull()
    const i = setInterval(pull, 8000)
    return () => { cancelled = true; clearInterval(i) }
  }, [d.projectCwd])

  const list = assets || []
  const sel = list.find(a => (a.id || a.filename) === selId) || list[0] || null

  const attach = async (rec: AssetRecord) => {
    if (!rec.id) { toast('Loose file — not byte-addressable; re-add it via Attach to materialize it'); return }
    d.attachToCompose([{ id: rec.id, filename: rec.filename, kind: 'asset' }])
    toast(`Attached ${rec.filename} — chip added to Compose`)
  }

  // Remove (§7.16, DELETE /library/assets/{id}): bytes dir + .meta.json
  // sidecar; honest 404/400/500 details verbatim. Behind the inline danger
  // confirm (the Past-tab archive-delete pattern).
  const doDelete = async (rec: AssetRecord) => {
    setConfirmDel(null)
    if (!rec.id || !d.projectCwd) return
    const r = await api.deleteAsset(rec.id, d.projectCwd)
    if (r.ok) {
      toast(`Removed ${rec.filename} — bytes and metadata deleted from the project store`)
      setSelId(null)
      setAssets(prev => (prev || []).filter(a => a.id !== rec.id))
    } else {
      toast(`Remove failed: ${r.detail || 'sidecar error'}`)
    }
  }

  return (
    <div className="flex-1 min-h-0 flex p-2.5 gap-2.5">
      <nav data-comp="entry-nav" className="docnav assetnav">
        {list.map(a => {
          const key = a.id || a.filename
          return (
            <div key={key} className={`docnav-row assetnav-row${sel && (sel.id || sel.filename) === key ? ' on' : ''}`} role="button" tabIndex={0}
              onClick={() => setSelId(key)}
              onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setSelId(key) } }}
              title={a.id ? a.filename : `${a.filename} — loose file (no asset id; visible media, not byte-endpoint-addressable)`}>
              <AssetThumb rec={a} cwd={d.projectCwd} />
              <span className="docnav-lab">
                <span className="docnav-name">{a.filename}</span>
                <span className="docnav-path">{[a.mime, a.size != null ? fmtSize(a.size) : null, a.id ? null : 'loose'].filter(Boolean).join(' · ')}</span>
              </span>
            </div>
          )
        })}
        {assets != null && !list.length && <div className="awl-empty">{d.projectCwd ? 'no assets yet — Attach in Compose materializes files here' : 'no project open'}</div>}
        {assets == null && <div className="awl-empty">reading assets…</div>}
      </nav>
      <div className="docmain assetmain flex-1 min-h-0 flex flex-col">
        {sel ? (
          <div data-comp="asset-card" className="assetdoc on" style={{ display: 'flex', flexDirection: 'column', flex: '1 1 auto', minHeight: 0 }}>
            <div className="doc-header">
              <span className="dh-path">{sel.rel_path || sel.filename}</span>
              <span className="dh-dates"><b>Created</b> {(sel.created || sel.provenance?.created_at || '—').slice(0, 16).replace('T', ' ')}{sel.provenance?.created_by ? <>&nbsp;&nbsp;<b>By</b> {sel.provenance.created_by}</> : null}</span>
            </div>
            <div className="asset-preview">
              {sel.http_url && isImageFile(sel.filename)
                ? <span className="ap-img" style={{ background: 'var(--surface-3)' }}><img className="awl-asset-thumb" style={{ objectFit: 'contain' }} src={`${API}${sel.http_url}`} alt={sel.filename} /></span>
                : <span className="ap-img" style={{ background: 'var(--surface-3)' }}><Ic name={isImageFile(sel.filename) ? 'image' : fileTypeIcon(sel.filename)} style={{ color: 'var(--muted)' }} /></span>}
            </div>
            {confirmDel === sel.id && sel.id && (
              // flexWrap: the assets preview column gets very narrow at the
              // 1180 floor — the buttons wrap under the message instead of
              // squeezing the text into a one-word-per-line column.
              <div data-comp="inline-confirm" className="tl-confirm foot-confirm--danger" style={{ display: 'flex', flexWrap: 'wrap' }}>
                <span style={{ flex: '1 1 14ch' }}>Remove {sel.filename} forever? Bytes + metadata are deleted from the store.</span>
                <button className="btn btn-sm ml-auto" onClick={() => setConfirmDel(null)}>Cancel</button>
                <button className="btn-danger-solid btn-sm" onClick={() => doDelete(sel)}><Ic name="trash-2" className="w-3.5 h-3.5" />Remove</button>
              </div>
            )}
            <div className="doc-foot">
              <ExportControl a={{
                enabled: !!sel.id,          // Assets are Attach-only (whole-file)
                wholeOnly: true,
                onCopy: () => toast('Assets are Attach-only — an image isn’t copyable as text'),
                onFile: () => toast('Assets are Attach-only'),
                onEmbed: () => toast('Assets are Attach-only — Embed needs quotable text'),
                onAttach: () => attach(sel),
              }} />
              <span className="flex-1" />
              <button data-comp="button" className="btn-danger btn-sm" disabled={!sel.id}
                title={sel.id ? 'Remove this asset — deletes its bytes and metadata from the project store' : 'Loose file (no asset id) — not managed by the store; remove it on disk'}
                onClick={() => sel.id && setConfirmDel(sel.id)}>
                <Ic name="trash-2" className="w-3 h-3" />Remove
              </button>
            </div>
          </div>
        ) : <div className="awl-empty">{d.projectCwd ? 'No asset selected.' : 'Open a project to see its assets.'}</div>}
      </div>
    </div>
  )
}

function fmtSize(n: number): string {
  if (n >= 1024 * 1024) return `${(n / (1024 * 1024)).toFixed(1)} MB`
  if (n >= 1024) return `${Math.round(n / 1024)} KB`
  return `${n} B`
}

// ---- the reviewable-document card ------------------------------------------------
function PlanCard({ e, open, onToggle, onChanged }: { e: Entry; open: boolean; onToggle: () => void; onChanged: () => void }) {
  const d = useDash()
  const [content, setContent] = useState<string | null>(null)
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const [sel, setSel] = useState<{ kind: 'line' | 'section' | 'doc'; line: number } | null>(null)
  const [lens, setLens] = useState<'toc' | 'feedback' | 'authors'>('toc')
  const [composer, setComposer] = useState(false)
  const [note, setNote] = useState('')
  const [verdict, setVerdict] = useState<'approve' | 'revise' | 'block'>('approve')
  const [reviewer, setReviewer] = useState<string | null>(null)
  const [revOpen, setRevOpen] = useState(false)

  useEffect(() => {
    if (open && content == null) api.libraryDocument(e.doc.path).then(r => setContent(r?.content ?? '(unreadable)'))
  }, [open])

  const meta = e.meta
  // Provenance (§8.5, §11 #41) rides on BOTH the reviews .meta.json (e.meta) and
  // the Library listing (e.doc) — prefer the sidecar meta, fall back to the doc.
  const prov = meta?.provenance || e.doc.provenance || null
  const hasProv = !!(prov && (prov.created_by || prov.created_at || prov.session))
  const authorSession = prov?.created_by
    ? d.sessions.find(x => x.session_id === prov.created_by || identOf(x).short === prov.created_by)
    : null
  const owner: Ident = (() => {
    const key = meta?.owner || prov?.created_by
    const s = key ? d.sessions.find(x => x.session_id === key || identOf(x).short === key) : null
    return s ? identOf(s) : USER_IDENT
  })()
  const bb = lifeOf(meta)
  const lines = (content ?? '').split('\n')
  const comments = (meta?.comments || []).filter(c => !c.resolved)

  const stepDone = lines.filter(l => /^\s*-\s*\[(x|X)\]/.test(l)).length
  const stepAll = lines.filter(l => /^\s*-\s*\[( |x|X)\]/.test(l)).length

  const headings = lines.map((ln, i) => ({ ln, i })).filter(x => /^#{2,4}\s+/.test(x.ln))
    .map(x => ({ line: x.i + 1, level: (x.ln.match(/^(#+)/) as any)[1].length, text: x.ln.replace(/^#{2,4}\s+/, '') }))

  const commentsFor = (heading: string | null) => comments.filter(c => (c.anchor_heading || null) === heading)

  const saveEdit = async () => {
    if (!d.projectCwd) return
    const r = await api.writeDocument({ cwd: d.projectCwd, path: e.doc.path, content: draft })
    toast(r ? 'Saved' : 'Write failed')
    if (r) { setContent(draft); setEditing(false); onChanged() }
  }
  const addComment = async () => {
    if (!d.projectCwd) return
    if (verdict !== 'approve' && !note.trim()) { toast('Revise/Block needs a comment'); return }
    const anchor = sel && sel.kind === 'section' ? lines[sel.line - 1]?.replace(/^#{2,4}\s+/, '') : undefined
    const r = await api.addComment({
      cwd: d.projectCwd, path: e.doc.path, author: 'user',
      text: `[${verdict}] ${note.trim() || '(approve)'}`,
      anchor_heading: anchor, anchor_quote: sel && sel.kind === 'line' ? lines[sel.line - 1] : undefined,
    })
    toast(r ? 'Comment saved' : 'Comment failed')
    setComposer(false); setNote(''); onChanged()
  }
  const decide = async (v: 'approve' | 'revise' | 'reject') => {
    const ownerSession = d.sessions.find(x => x.session_id === (meta?.owner || '') || identOf(x).short === (meta?.owner || ''))
    if (ownerSession && v !== 'reject') {
      const r = await api.planVerdict(ownerSession.session_id, { verdict: v === 'approve' ? 'approve' : 'revise', filename: e.doc.filename, by: 'user' })
      toast(r ? `${v} recorded → ${identOf(ownerSession).name}` : 'Verdict rejected by the sidecar')
    } else {
      toast(`${v} noted — no owning session to notify${v === 'reject' ? ' (reject is dashboard-side only today)' : ''}`)
    }
    onChanged()
  }
  const sendReview = async () => {
    if (!reviewer) { toast('Pick a reviewer first'); return }
    const r = await api.send(reviewer, `Review the ${e.kind} at ${e.doc.path} and post verdicts as comments.`, { source: 'user', disposition: 'queue' })
    toast(r.ok ? `Sent for review` : `Review send failed${r.detail ? ` — ${r.detail}` : ''}`)
  }

  const railKind = (i: number): 'title' | 'sec' | 'line' => {
    const ln = lines[i]
    if (/^#\s+/.test(ln)) return 'title'
    if (/^#{2,4}\s+/.test(ln)) return 'sec'
    return 'line'
  }
  const selected = (i: number): boolean => {
    if (!sel) return false
    if (sel.kind === 'doc') return true
    if (sel.kind === 'line') return sel.line === i + 1
    // section: from its heading to the next heading of level <= its level
    const startIdx = sel.line - 1
    const m = lines[startIdx]?.match(/^(#{2,4})\s+/)
    const lvl = m ? m[1].length : 2
    if (i < startIdx) return false
    for (let j = startIdx + 1; j <= i; j++) {
      const mm = lines[j]?.match(/^(#{1,4})\s+/)
      if (mm && mm[1].length <= lvl) return false
    }
    return true
  }

  return (
    <div data-comp="plan-card" className={`plan-card${open ? ' open' : ''}`} id={e.id}>
      <button className="plan-head" onClick={onToggle}>
        <div className="plan-head-main">
          <div className="plan-row r1">
            <IdentBadge a={owner} />
            <span className="plan-title">{e.doc.filename.replace(/\.md$/, '')}</span>
            <span className="flex-1" />
            <span className="cnt-strip">
              {comments.length > 0 && <span data-comp="count-chip" className="cnt-chip c-revise" title={`${comments.length} open comment(s)`}><Ic name="triangle-alert" /><span className="cn">{comments.length}</span></span>}
            </span>
            <span data-comp="lifecycle-badge" className={`dbadge ${bb[0]}`}>{bb[1]}</span>
          </div>
          <div className="plan-row r2">
            {stepAll > 0 && <span data-comp="count-chip" className={`cnt-chip c-steps${stepDone === stepAll ? ' all' : ''}`} title={`${stepDone} of ${stepAll} steps done`}><Ic name="list-checks" /><span className="cn">{stepDone}/{stepAll} steps</span></span>}
            <span className="flex-1" />
            <span className="plan-dates"><b>Edited</b> {e.doc.modified?.slice(0, 16).replace('T', ' ')}</span>
          </div>
        </div>
        <Ic name="chevron-right" className="plan-chev" />
      </button>
      {open && (
        <div className="plan-body">
          <div className="plan-rev">
            <div className="plan-nav">
              <div className="nav-tabs">
                <button data-comp="nav-tab" className={`nav-tab nav-tab--ol${lens === 'toc' ? ' on' : ''}`} onClick={() => setLens('toc')} title="TOC — table of contents"><span className="nt-ic"><Ic name="list" /></span><span className="nt-lab">TOC</span></button>
                <button data-comp="nav-tab" className={`nav-tab nav-tab--fb${lens === 'feedback' ? ' on' : ''}`} onClick={() => setLens('feedback')} title="Feedback"><span className="nt-ic"><Ic name="message-square" /></span><span className="nt-lab">Feedback</span>{comments.length > 0 && <span className="nav-cnt">{comments.length}</span>}</button>
                <button data-comp="nav-tab" className={`nav-tab nav-tab--au${lens === 'authors' ? ' on' : ''}`} onClick={() => setLens('authors')} title="Authors"><span className="nt-ic"><Ic name="users" /></span><span className="nt-lab">Authors</span>{hasProv && <span className="nav-cnt">1</span>}</button>
              </div>
              {lens === 'toc' && (
                <div className="ol-scroll">
                  <div className="ol-cap">Table of contents</div>
                  <div className="ol-list">
                    {headings.map(h => (
                      <button data-comp="outline-item" key={h.line} className="ol-item" data-hlevel={h.level}
                        onClick={() => setSel({ kind: 'section', line: h.line })}>
                        <span className={`ol-dot${commentsFor(h.text).some(c => /\[(revise)\]/.test(c.text)) ? ' d-revise' : ''}${commentsFor(h.text).some(c => /\[(block)\]/.test(c.text)) ? ' d-block' : ''}`} />
                        <span className="ol-nm">{h.text}</span>
                        <span className="ol-c" title={`line ${h.line}`}>{h.line}</span>
                      </button>
                    ))}
                    {!headings.length && <div className="fb-empty">no sections</div>}
                  </div>
                </div>
              )}
              {lens === 'feedback' && (
                <div className="ol-scroll">
                  <div className="ol-cap">Feedback</div>
                  {comments.map(c => {
                    const jump = () => {
                      const h = headings.find(h2 => h2.text === c.anchor_heading)
                      if (h) setSel({ kind: 'section', line: h.line })
                    }
                    return (
                    <div key={c.id} className="fb-card" role="button" tabIndex={0} onClick={jump}
                      onKeyDown={ev => { if (ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); jump() } }}>
                      <div className="flex items-center gap-1 w-full"><span className="docnav-name">{c.author}</span><span className="fcard-time" style={{ marginLeft: 'auto' }}>{(c.ts || '').slice(5, 16).replace('T', ' ')}</span></div>
                      <div className="text-[10px] text-muted" style={{ width: '100%' }}>{c.text.slice(0, 90)}</div>
                      {d.projectCwd && <button className="mini-link" onClick={async ev => { ev.stopPropagation(); await api.resolveComment({ cwd: d.projectCwd!, path: e.doc.path, comment_id: c.id }); toast('Comment resolved'); onChanged() }}>resolve</button>}
                    </div>
                    )
                  })}
                  {!comments.length && <div className="fb-empty">No feedback yet.</div>}
                </div>
              )}
              {lens === 'authors' && (
                <div className="ol-scroll">
                  <div className="ol-cap">Authors</div>
                  {hasProv ? (
                    <div className="fb-card">
                      <div className="flex items-center gap-2 w-full">
                        {authorSession ? <IdentBadge a={identOf(authorSession)} /> : <span className="docnav-name">{prov!.created_by || 'unknown'}</span>}
                        <span data-comp="contribution-badge" className="dbadge au-act" style={{ marginLeft: 'auto' }}>Drafted</span>
                      </div>
                      {prov!.created_at && <div className="text-[10px] text-muted" style={{ width: '100%' }}>{prov!.created_at.slice(0, 16).replace('T', ' ')}</div>}
                      {prov!.session && <div className="text-[9px] text-muted-2 font-mono" style={{ width: '100%' }} title={prov!.session}>session {prov!.session.length > 24 ? prov!.session.slice(0, 24) + '…' : prov!.session}</div>}
                    </div>
                  ) : <div className="fb-empty">No authorship recorded yet.</div>}
                </div>
              )}
            </div>
            <div className="plan-main">
              <div data-comp="editor-header" className="lib-edit-head">
                <span className="lib-edit-lab">Editor</span>
                <span className="lib-edit-file">{e.doc.filename}</span>
                <span className="flex-1" />
                <button data-comp="ghost-icon-button" className={`ghost-ic${composer ? ' rec' : ''}`} title={sel ? 'Comment on the selection' : 'Select a line or section first'}
                  onClick={() => { if (!sel) { toast('Select a line or section first'); return } setComposer(o => !o) }}><Ic name="message-square-plus" /></button>
                <button data-comp="ghost-icon-button" className="ghost-ic" title="Edit raw markdown" onClick={() => { if (!editing) setDraft(content ?? ''); setEditing(o => !o) }}><Ic name="square-pen" /></button>
                <button data-comp="ghost-icon-button" className="ghost-ic" title="Dictation pending backend" disabled><Ic name="mic" /></button>
              </div>
              {editing ? (
                <>
                  <textarea className="entry-edit" style={{ display: 'block' }} value={draft} onChange={ev => setDraft(ev.target.value)} rows={16} />
                  <div className="flex gap-2 mt-2">
                    <button className="btn-main btn-sm" onClick={saveEdit}>Save</button>
                    <button className="btn btn-sm" onClick={() => setEditing(false)}>Cancel</button>
                  </div>
                </>
              ) : (
                <div data-comp="doc-editor" className="doc-ed">
                  <div className="md">
                    {content == null && <div className="awl-empty">loading…</div>}
                    {lines.map((ln, i) => {
                      const kind = railKind(i)
                      const isSel = selected(i)
                      const heading = kind === 'sec' ? ln.replace(/^#{2,4}\s+/, '') : null
                      const cms = heading != null ? commentsFor(heading) : []
                      return (
                        <div data-comp="markdown-row" key={i} className={`md-row${kind === 'sec' ? ' md-h-row' : ''}${isSel ? ' rsel' : ''}`} data-line={i + 1}>
                          <button className={`md-rail${kind === 'sec' ? ' is-sec' : ''}${kind === 'title' ? ' is-title' : ''}`}
                            title={kind === 'title' ? 'Select the whole document' : kind === 'sec' ? 'Select this section' : `Select line ${i + 1}`}
                            onClick={() => {
                              if (kind === 'title') setSel(sel?.kind === 'doc' ? null : { kind: 'doc', line: 1 })
                              else if (kind === 'sec') setSel(sel?.kind === 'section' && sel.line === i + 1 ? null : { kind: 'section', line: i + 1 })
                              else setSel(sel?.kind === 'line' && sel.line === i + 1 ? null : { kind: 'line', line: i + 1 })
                            }}>
                            {cms.length > 0 && <span className="rd" title={`${cms.length} comment(s)`}>{cms.length}</span>}
                            <span className="rn">{i + 1}</span>
                          </button>
                          {/^#\s+/.test(ln)
                            ? <span className="md-line md-h1">{inlineMd(ln.replace(/^#\s+/, ''))}</span>
                            : /^#{2,4}\s+/.test(ln)
                              ? <span className={`md-line md-h${(ln.match(/^(#+)/) as any)[1].length}`}>{inlineMd(ln.replace(/^#{2,4}\s+/, ''))}</span>
                              : /^\s*-\s*\[( |x|X)\]\s+/.test(ln)
                                ? <span className={`md-line md-task${/\[(x|X)\]/.test(ln) ? ' done' : ''}`}><span className="md-box">{/\[(x|X)\]/.test(ln) ? '☑' : '☐'}</span> {inlineMd(ln.replace(/^\s*-\s*\[( |x|X)\]\s+/, ''))}</span>
                                : ln.trim() === ''
                                  ? <span className="md-line md-blank"> </span>
                                  : <span className="md-line">{inlineMd(ln)}</span>}
                        </div>
                      )
                    })}
                    <div className="md-row md-fill" aria-hidden="true"><span className="md-rail md-rail--fill" /><span className="md-line" /></div>
                  </div>
                  <div data-comp="comment-popover" className={`plan-cmt-pop${composer ? ' open' : ''}`}>
                    {composer && (
                      <div className="p-2 flex flex-col gap-2">
                        <div className="flex items-center gap-2">
                          <IdentBadge a={USER_IDENT} />
                          <select className="in" style={{ width: 110, height: 26, fontSize: 10 }} value={verdict} onChange={ev => setVerdict(ev.target.value as any)}>
                            <option value="approve">Approve</option><option value="revise">Revise</option><option value="block">Block</option>
                          </select>
                          <span className="text-[9px] text-muted-2">{sel?.kind === 'doc' ? 'whole doc' : sel ? `${sel.kind} @ line ${sel.line}` : ''}</span>
                        </div>
                        <textarea className="in" rows={2} placeholder={verdict === 'approve' ? 'Optional note…' : 'Revise/Block needs a comment'} value={note} onChange={ev => setNote(ev.target.value)} />
                        <div className="flex gap-2">
                          <button className="btn-main btn-sm cmt-save" disabled={verdict !== 'approve' && !note.trim()} onClick={addComment}>Save</button>
                          <button className="btn btn-sm" onClick={() => setComposer(false)}>Cancel</button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
          <div className="plan-foot">
            <ExportControl a={{
              enabled: !!sel || !!content,
              fileDisabled: !d.projectCwd,
              onCopy: () => {
                const text = sel?.kind === 'line' ? lines[sel.line - 1] : sel?.kind === 'section' ? lines.filter((_, i) => selected(i)).join('\n') : (content || '')
                navigator.clipboard?.writeText(text); toast('Copied')
              },
              onFile: async () => {
                if (!d.projectCwd) return
                const text = sel ? lines.filter((_, i) => selected(i)).join('\n') : (content || '')
                const r = await api.createDocument({ cwd: d.projectCwd, filename: `excerpt-${Date.now()}.md`, content: text, subdir: 'docs' })
                toast(r ? 'Exported → Documents' : 'Export failed')
                onChanged()
              },
              onEmbed: () => {
                const text = sel ? lines.filter((_, i) => selected(i)).join('\n') : (content || '')
                d.replyTo(d.selectedId || '', { source: e.doc.filename, text })
              },
              // Real Attach (§7.14): the doc is COPIED into the project store
              // via POST /library/assets (source_path ingest) and chipped by
              // asset id; a selected section/line rides as the citation anchor.
              onAttach: async () => {
                if (!d.projectCwd) { toast('No project open'); return }
                const citation = sel?.kind === 'section'
                  ? { doc: e.doc.filename, location: lines[sel.line - 1]?.replace(/^#{2,4}\s+/, '') || `line ${sel.line}` }
                  : sel?.kind === 'line'
                    ? { doc: e.doc.filename, location: `line ${sel.line}` }
                    : undefined
                const r = await api.ingestAsset({ cwd: d.projectCwd, source_path: e.doc.path, created_by: 'user', citation })
                if (r.ok && r.data?.asset?.id) {
                  d.attachToCompose([{ id: r.data.asset.id, filename: r.data.asset.filename, kind: 'doc' }])
                  toast(`Attached ${r.data.asset.filename} — chip added to Compose${citation ? ` (cites ${citation.location})` : ''}`)
                } else toast(`Attach failed: ${r.detail || 'sidecar error'}`)
              },
            }} />
            <div data-comp="review-chip" className="rev-chip" data-revchip>
              <button className="rev-trig" type="button" onClick={() => setRevOpen(o => !o)} title="Choose the reviewer">
                {reviewer && d.sessions.some(s => s.session_id === reviewer)
                  ? <IdentBadge a={identOf(d.sessions.find(s => s.session_id === reviewer)!)} />
                  : <span className="msel-ph" style={{ padding: '0 var(--space-8)' }}>Reviewer…</span>}
                <Ic name="chevrons-up-down" className="picker-cv" />
              </button>
              <div className={`src-pop rev-pop${revOpen ? ' open' : ''}`}>
                <div className="src-pop-head"><span className="sec-h" style={{ margin: 0 }}>Reviewer</span></div>
                <div className="aglist aglist-scroll" style={{ maxHeight: 220 }}>
                  {d.sessions.map(s => {
                    const a = identOf(s)
                    return (
                      <button key={s.session_id} className={`agrow${reviewer === s.session_id ? ' on' : ''}`} type="button"
                        onClick={() => { setReviewer(s.session_id); setRevOpen(false) }}>
                        <AgTile a={a} /><span className="ag-lab"><span className="ag-role">{a.role}</span><span className="ag-name">{a.name}</span></span><Ic name="check" className="ag-ck" />
                      </button>
                    )
                  })}
                  {!d.sessions.length && <div className="awl-empty">no agents</div>}
                </div>
              </div>
              <button className="rev-act" type="button" onClick={sendReview} title="Send this document for review"><Ic name="scan-search" /></button>
            </div>
            <div className="plan-foot-right">
              {meta?.verdict === 'approve' || meta?.state === 'approved'
                ? <span className="text-[9px] font-bold font-mono" style={{ color: 'var(--success)' }}>Approved</span>
                : (<>
                  <button data-comp="button" className="btn-secondary" title="Send the flagged sections back to the authoring agent" onClick={() => decide('revise')}><Ic name="wand-sparkles" className="w-3.5 h-3.5" />Revise</button>
                  <button data-comp="button" className="btn-danger" onClick={() => decide('reject')}><Ic name="x" className="w-3.5 h-3.5" />Reject</button>
                  <button data-comp="button" className="btn-main" onClick={() => decide('approve')}><Ic name="check" className="w-3.5 h-3.5" />Approve</button>
                </>)}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
