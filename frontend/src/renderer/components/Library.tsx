// ============================================================================
// Library — Plans · Documents · Assets (middle column, bottom).
// Plans + Documents render as the shared reviewable-document card: entry-nav
// beside single-open cards, the line-numbered editor with the select-to-act
// rail, comments via the sidecar .meta.json sidecars, raw-markdown edit → PUT,
// and the decision footer. Assets is the honest tab shell (no backend asset
// surface yet).
// ============================================================================

import React, { useEffect, useMemo, useRef, useState } from 'react'
import { api, type LibraryDoc, type DocMeta } from '../api'
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
      const meta = (p: string): DocMeta | null => (reviews && (reviews[p] || reviews[p.replace(/\\/g, '/')])) || null
      if (pl != null) setPlans(pl.map(doc => ({ id: `plan-${doc.filename}`, doc, meta: meta(doc.path), kind: 'plan' as const })))
      const seen = new Set<string>()
      const dd: Entry[] = []
      for (const doc of [...(dc || []), ...(root || [])]) {
        if (seen.has(doc.path)) continue
        seen.add(doc.path)
        dd.push({ id: `doc-${doc.filename}-${dd.length}`, doc, meta: meta(doc.path), kind: 'doc' })
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
        </div>
      </div>
      <div className="pcard-body flex flex-col overflow-hidden" style={{ background: 'var(--background)' }}>
        {(d.libTab === 'plan' || d.libTab === 'documents') && (
          <div className="flex-1 min-h-0 flex p-2.5 gap-2.5">
            <nav data-comp="entry-nav" className="docnav">
              {entries.map(e => {
                const bb = lifeOf(e.meta)
                const fn = e.doc.filename
                const dir = e.doc.path.slice(0, e.doc.path.length - fn.length)
                return (
                  <div key={e.id} className={`docnav-row navcard${openId === e.id ? ' on' : ''}`} role="button" tabIndex={0}
                    onClick={() => setOpenId(openId === e.id ? null : e.id)}>
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

        {d.libTab === 'assets' && (
          <div className="flex-1 min-h-0 flex p-2.5 gap-2.5">
            <nav data-comp="entry-nav" className="docnav assetnav">
              <div className="awl-empty">no assets listed</div>
            </nav>
            <div className="docmain assetmain flex-1 min-h-0 flex flex-col">
              <div className="awl-empty">Assets needs a backend listing surface (assets/ dir) — the tab ships as a shell until it lands.</div>
            </div>
          </div>
        )}
      </div>
    </section>
  )
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
  const owner: Ident = (() => {
    const key = meta?.owner || meta?.provenance?.created_by
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
    toast(r ? `Sent for review` : 'Review send failed')
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
                <button data-comp="nav-tab" className={`nav-tab nav-tab--au${lens === 'authors' ? ' on' : ''}`} onClick={() => setLens('authors')} title="Authors"><span className="nt-ic"><Ic name="users" /></span><span className="nt-lab">Authors</span>{meta?.provenance && <span className="nav-cnt">1</span>}</button>
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
                  {comments.map(c => (
                    <div key={c.id} className="fb-card" role="button" onClick={() => {
                      const h = headings.find(h2 => h2.text === c.anchor_heading)
                      if (h) setSel({ kind: 'section', line: h.line })
                    }}>
                      <div className="flex items-center gap-1 w-full"><span className="docnav-name">{c.author}</span><span className="fcard-time" style={{ marginLeft: 'auto' }}>{(c.ts || '').slice(5, 16).replace('T', ' ')}</span></div>
                      <div className="text-[10px] text-muted" style={{ width: '100%' }}>{c.text.slice(0, 90)}</div>
                      {d.projectCwd && <button className="mini-link" onClick={async ev => { ev.stopPropagation(); await api.resolveComment({ cwd: d.projectCwd!, path: e.doc.path, comment_id: c.id }); toast('Comment resolved'); onChanged() }}>resolve</button>}
                    </div>
                  ))}
                  {!comments.length && <div className="fb-empty">No feedback yet.</div>}
                </div>
              )}
              {lens === 'authors' && (
                <div className="ol-scroll">
                  <div className="ol-cap">Authors</div>
                  {meta?.provenance
                    ? <div className="fb-card"><span className="docnav-name">{meta.provenance.created_by || 'unknown'}</span><span data-comp="contribution-badge" className="dbadge au-act">Drafted</span></div>
                    : <div className="fb-empty">No authorship recorded yet.</div>}
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
              onAttach: () => d.replyTo(d.selectedId || '', { source: e.doc.path, text: `Read this file: ${e.doc.path}` }),
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
