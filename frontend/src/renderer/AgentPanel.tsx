// ============================================================================
// Agent panel — Details + Create (the focused agent's config & live readouts)
// ----------------------------------------------------------------------------
// Console tab is intentionally ABSENT (needs a net-new screen endpoint).
//
// Details wires the PROVEN controls — set model (POST /model), set effort
// (POST /effort), Retire (DELETE) — and honestly disables what the bridge can't
// do: Mode is shown as the launched value with the segmented control DISABLED
// (mid-run mode change 400s; mode is applied at launch), and Fast/Thinking are
// disabled (400 on bridge). Live readout: the health-colored Ctx bar + the Turns
// count and by-tool breakdown (from GET /context work_steps/tools — NOT
// total_turns, which is 0 on bridge).
//
// Create wires POST /sessions: identity (role/name/color/icon), model,
// mode-at-launch, cwd, and an optional per-agent disallowed-tools gate (proven).
// ============================================================================

import React, { useEffect, useState } from 'react'
import { C, FONT, MONO, AG_COLORS, deriveBadge, fmtCreated, timeAgo, healthColor } from './tokens'
import { Btn, StatusBadge, Segmented, Tabs, Field, ReadOnly } from './ui'
import { AgentTile } from './AgentTile'
import { api, type Session, type ContextUsage, type CreatePayload, type ConsoleCommand } from './api'

const MODEL_OPTS = [
  { value: 'inherit', label: 'Inherit' }, { value: 'opus', label: 'Opus' },
  { value: 'sonnet', label: 'Sonnet' }, { value: 'haiku', label: 'Haiku' },
]
const MODE_OPTS = [
  { value: 'plan', label: 'Plan' }, { value: 'default', label: 'Ask' },
  { value: 'acceptEdits', label: 'Edit' }, { value: 'dontAsk', label: 'Auto' },
  { value: 'bypassPermissions', label: 'Bypass' },
]
const EFFORT_OPTS = [
  { value: 'low', label: 'Low' }, { value: 'medium', label: 'Med' }, { value: 'high', label: 'High' },
]
// A small curated subset of the 167 game-icons for the Create picker (the
// backend round-robins one if none is chosen).
const ICON_OPTS = [
  'android-mask', 'alien-skull', 'bear-head', 'fox-head', 'eagle-head',
  'dragon-head__lorc', 'cyborg-face', 'goblin-head', 'mecha-head', 'medusa-head',
  'minotaur', 'astronaut-helmet', 'wizard-face', 'death-skull', 'owl', 'robot-golem',
]
const AG_COLOR_LIST = Object.entries(AG_COLORS) // [name, hex]

function modelValue(model: string | null): string {
  if (!model) return 'inherit'
  const m = model.toLowerCase()
  return MODEL_OPTS.find(o => m.includes(o.value))?.value || 'inherit'
}

// ---- Details ---------------------------------------------------------------

function Details({ session, ctx, onSetModel, onSetEffort, onRetire }: {
  session: Session
  ctx: ContextUsage | null
  onSetModel: (m: string) => void
  onSetEffort: (e: string) => void
  onRetire: () => void
  nowMs: number
}) {
  const [confirmRetire, setConfirmRetire] = useState(false)
  const [effort, setEffort] = useState<string | null>(null)
  const id = session.identity
  const badge = deriveBadge(session.status, session.has_pending_permission)
  const lc = session.launch_config
  const tools = ctx?.tools || {}
  const toolChips = Object.entries(tools).filter(([, n]) => n > 0)

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 12 }}>
      {/* header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10, marginBottom: 14 }}>
        <AgentTile icon={id?.icon} color={id?.color} size={44} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 9, fontWeight: 800, color: C.t3, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{id?.role || 'agent'}</div>
          <div style={{ fontSize: 16, fontWeight: 900, color: C.t1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {String(id?.number ?? '').padStart(2, '0')} {id?.name || ''}
          </div>
        </div>
        <div style={{ textAlign: 'right' }}>
          <StatusBadge badge={badge} />
          <div style={{ fontSize: 8.5, color: C.t5, fontFamily: MONO, marginTop: 4 }}>
            {fmtCreated(session.created_at)}<br />{timeAgo(session.created_at)} ago
          </div>
        </div>
      </div>

      {/* Band 1 — config (read-only display v1; Model is editable) */}
      <div style={{ display: 'flex', gap: 10 }}>
        <div style={{ flex: 1 }}><Field label="Role"><ReadOnly>{id?.role || '—'}</ReadOnly></Field></div>
        <div style={{ width: 64 }}><Field label="No."><ReadOnly mono>{String(id?.number ?? '—').padStart(2, '0')}</ReadOnly></Field></div>
      </div>
      <Field label="Name"><ReadOnly>{id?.name || '—'}</ReadOnly></Field>
      <div style={{ display: 'flex', gap: 10 }}>
        <div style={{ flex: 1 }}><Field label="Color"><ReadOnly mono>{id?.color || '—'}</ReadOnly></Field></div>
        <div style={{ flex: 1 }}><Field label="Icon"><ReadOnly>{id?.icon || '—'}</ReadOnly></Field></div>
      </div>
      <Field label="Working dir"><ReadOnly mono>{session.cwd || '(default)'}</ReadOnly></Field>

      <Field label="Model (editable mid-run)">
        <Segmented options={MODEL_OPTS} value={modelValue(session.model)}
          onChange={(v) => onSetModel(v === 'inherit' ? '' : v)} />
        <div style={{ fontSize: 9, color: C.t5, marginTop: 3 }}>current: {session.model || 'default'}</div>
      </Field>

      {/* Band 2 — runtime knobs */}
      <Field label="Mode (set at launch — mid-run change unavailable on bridge)">
        <Segmented options={MODE_OPTS} value={session.permission_mode} disabled danger="bypassPermissions" />
      </Field>
      <Field label="Effort (set-only — no readback on bridge)">
        <Segmented options={EFFORT_OPTS} value={effort} onChange={(v) => { setEffort(v); onSetEffort(v) }} />
      </Field>
      <Field label="Fast / Thinking (unavailable on bridge)">
        <div style={{ display: 'flex', gap: 8 }}>
          <Btn variant="cream" disabled style={{ flex: 1 }}>Opus Fast-Mode</Btn>
          <Btn variant="cream" disabled style={{ flex: 1 }}>Thinking Mode</Btn>
        </div>
      </Field>

      {/* Band 3 — live readout */}
      <div style={{ borderTop: `2px solid ${C.border}`, margin: '14px 0 10px' }} />
      <Field label="Context usage">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <div style={{ flex: 1, height: 10, background: C.surface, border: `2px solid ${C.border}`, borderRadius: 4, overflow: 'hidden' }}>
            <div style={{ width: `${ctx?.percent == null ? 0 : Math.max(0, Math.min(100, ctx.percent))}%`, height: '100%', background: healthColor(ctx?.percent) }} />
          </div>
          <span style={{ fontSize: 11, fontWeight: 800, fontFamily: MONO, color: C.t1, minWidth: 88, textAlign: 'right' }}>
            {ctx?.percent == null ? '—' : `${ctx.percent}%`} {ctx?.window ? `· ${Math.round((ctx.window) / 1000)}K` : ''}
          </span>
        </div>
        <div style={{ fontSize: 9, color: C.t5, marginTop: 3, fontFamily: MONO }}>
          {ctx?.tokens != null ? `${ctx.tokens.toLocaleString()} tokens` : 'no transcript yet'}
        </div>
      </Field>
      <Field label={`Turns — ${ctx?.work_steps ?? 0} work-steps`}>
        {toolChips.length === 0 ? (
          <div style={{ fontSize: 10, color: C.t5 }}>No tool use yet.</div>
        ) : (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
            {toolChips.map(([k, n]) => (
              <span key={k} style={{ fontSize: 9, fontWeight: 700, color: C.t2, background: C.surface, border: `1.5px solid ${C.rule}`, borderRadius: 3, padding: '2px 6px' }}>
                {k} {n}
              </span>
            ))}
            <span style={{ fontSize: 9, fontWeight: 800, color: C.t3, padding: '2px 4px' }}>· {ctx?.tool_total ?? 0} total</span>
          </div>
        )}
      </Field>

      {lc && (lc.disallowed_tools || lc.allowed_tools || lc.mcp_servers || lc.enabled_plugins) && (
        <Field label="Launch scope (read-only)">
          <ReadOnly mono>
            {lc.disallowed_tools?.length ? <div>deny tools: {lc.disallowed_tools.join(', ')}</div> : null}
            {lc.allowed_tools?.length ? <div>allow tools: {lc.allowed_tools.join(', ')}</div> : null}
            {lc.mcp_servers ? <div>mcp: {lc.mcp_servers.length ? lc.mcp_servers.join(', ') : '(none)'}</div> : null}
            {lc.enabled_plugins ? <div>plugins: {Object.keys(lc.enabled_plugins).join(', ')}</div> : null}
          </ReadOnly>
        </Field>
      )}

      {/* footer — Retire (with confirm). Delete deferred (no wipe backend). */}
      <div style={{ borderTop: `2px solid ${C.border}`, margin: '14px 0 10px' }} />
      {!confirmRetire ? (
        <Btn variant="danger" onClick={() => setConfirmRetire(true)} style={{ width: '100%' }}>⏻ Retire agent</Btn>
      ) : (
        <div style={{ display: 'flex', gap: 8 }}>
          <Btn variant="dangerSolid" onClick={() => { setConfirmRetire(false); onRetire() }} style={{ flex: 1 }}>Confirm retire</Btn>
          <Btn variant="cream" onClick={() => setConfirmRetire(false)} style={{ flex: 1 }}>Cancel</Btn>
        </div>
      )}
      <div style={{ fontSize: 9, color: C.t5, marginTop: 6, textAlign: 'center' }}>
        Delete (permanent wipe) deferred — Retire ends the session.
      </div>
    </div>
  )
}

// ---- Create ----------------------------------------------------------------

const BLANK = { role: '', name: '', cwd: '', model: 'inherit', mode: 'acceptEdits', color: '', icon: '', deny: '' }

function Create({ onCreate, onCancel, busy }: {
  onCreate: (p: CreatePayload) => void
  onCancel: () => void
  busy: boolean
}) {
  const [f, setF] = useState({ ...BLANK })
  const set = (k: string, v: string) => setF(prev => ({ ...prev, [k]: v }))

  const submit = () => {
    const identity: any = {}
    if (f.role.trim()) identity.role = f.role.trim()
    if (f.name.trim()) identity.name = f.name.trim()
    if (f.color) identity.color = f.color
    if (f.icon) identity.icon = f.icon
    const payload: CreatePayload = {
      model: f.model === 'inherit' ? null : f.model,
      permission_mode: f.mode,
      cwd: f.cwd.trim() || null,
      identity: Object.keys(identity).length ? identity : null,
      disallowed_tools: f.deny.trim() ? f.deny.split(',').map(s => s.trim()).filter(Boolean) : null,
    }
    onCreate(payload)
  }

  const inputStyle: React.CSSProperties = {
    width: '100%', background: C.input, border: `2px solid ${C.border}`, borderRadius: 5,
    padding: '6px 9px', fontSize: 11, color: C.t1, fontFamily: FONT, outline: 'none',
  }

  return (
    <div style={{ flex: 1, overflow: 'auto', padding: 12 }}>
      <div style={{ display: 'flex', gap: 10 }}>
        <div style={{ flex: 1 }}><Field label="Role"><input className="nb-in" style={inputStyle} value={f.role} placeholder="e.g. researcher" onChange={e => set('role', e.target.value)} /></Field></div>
        <div style={{ flex: 1 }}><Field label="Name"><input className="nb-in" style={inputStyle} value={f.name} placeholder="(optional)" onChange={e => set('name', e.target.value)} /></Field></div>
      </div>
      <div style={{ fontSize: 9, color: C.t5, marginTop: -4, marginBottom: 8 }}>Number, color & icon are auto-assigned if left unset.</div>

      <Field label="Color"><div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
        {AG_COLOR_LIST.map(([name, hex]) => (
          <button key={name} title={name} onClick={() => set('color', f.color === hex ? '' : hex)}
            style={{ width: 22, height: 22, borderRadius: 4, background: hex, cursor: 'pointer',
              border: `2px solid ${f.color === hex ? C.main : C.border}`, boxShadow: f.color === hex ? C.shadowSm : 'none' }} />
        ))}
      </div></Field>

      <Field label="Icon">
        <select className="nb-in" style={{ ...inputStyle, fontFamily: MONO }} value={f.icon} onChange={e => set('icon', e.target.value)}>
          <option value="">(auto)</option>
          {ICON_OPTS.map(n => <option key={n} value={n}>{n}</option>)}
        </select>
      </Field>

      <Field label="Model"><Segmented options={MODEL_OPTS} value={f.model} onChange={v => set('model', v)} /></Field>
      <Field label="Mode (applied at launch)"><Segmented options={MODE_OPTS} value={f.mode} onChange={v => set('mode', v)} danger="bypassPermissions" /></Field>
      <Field label="Working dir (WSL or Windows path; optional)"><input className="nb-in" style={{ ...inputStyle, fontFamily: MONO }} value={f.cwd} placeholder="/tmp/my-agent or C:/path" onChange={e => set('cwd', e.target.value)} /></Field>
      <Field label="Disallowed tools (comma-sep; proven hard-block)"><input className="nb-in" style={{ ...inputStyle, fontFamily: MONO }} value={f.deny} placeholder="e.g. Bash, WebSearch" onChange={e => set('deny', e.target.value)} /></Field>

      <div style={{ borderTop: `2px solid ${C.border}`, margin: '12px 0 10px' }} />
      <div style={{ display: 'flex', gap: 8 }}>
        <Btn variant="primary" onClick={submit} disabled={busy} style={{ flex: 1 }}>{busy ? 'Creating…' : 'Create'}</Btn>
        <Btn variant="cream" onClick={() => setF({ ...BLANK })} disabled={busy}>Reset</Btn>
        <Btn variant="cream" onClick={onCancel} disabled={busy}>Cancel</Btn>
      </div>
    </div>
  )
}

// ---- Console (slash-command runner) ----------------------------------------

function Console({ session }: { session: Session }) {
  const [catalog, setCatalog] = useState<{ clusters: string[]; by_cluster: Record<string, ConsoleCommand[]> } | null>(null)
  const [q, setQ] = useState('')
  const [filtered, setFiltered] = useState<ConsoleCommand[] | null>(null)
  const [manual, setManual] = useState('')
  const [screen, setScreen] = useState<{ command: string; interactive: boolean; screen: string } | null>(null)
  const [running, setRunning] = useState(false)

  useEffect(() => { api.consoleCatalog().then(c => c && setCatalog({ clusters: c.clusters, by_cluster: c.by_cluster })) }, [])
  useEffect(() => {
    if (!q.trim()) { setFiltered(null); return }
    let cancelled = false
    api.consoleCatalog(q).then(c => { if (!cancelled) setFiltered(c?.commands || []) })
    return () => { cancelled = true }
  }, [q])

  const run = async (command: string) => {
    if (!command.trim()) return
    setRunning(true)
    const r = await api.consoleRun(session.session_id, command.trim())
    setRunning(false)
    setScreen(r || { command, interactive: false, screen: '(no response — Console needs a bridge agent)' })
  }

  const inputStyle: React.CSSProperties = {
    width: '100%', background: C.input, border: `2px solid ${C.border}`, borderRadius: 5,
    padding: '6px 9px', fontSize: 11, color: C.t1, fontFamily: MONO, outline: 'none',
  }

  const CmdRow = ({ c }: { c: ConsoleCommand }) => (
    <div onClick={() => run(c.command)} className="nb-btn" style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 8px', border: `2px solid ${C.border}`, borderRadius: 5, background: C.card, boxShadow: C.shadowSm, marginBottom: 5, cursor: 'pointer' }}>
      <span style={{ fontSize: 11, fontWeight: 800, color: C.t1, fontFamily: MONO, minWidth: 96 }}>{c.command}</span>
      <span style={{ flex: 1, minWidth: 0, fontSize: 9.5, color: C.t3, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.description}</span>
      {c.interactive && <span title="opens a sub-prompt" style={{ fontSize: 8, fontWeight: 800, color: C.warnText, background: C.warnSoft, border: `1.5px solid ${C.border}`, borderRadius: 3, padding: '0 4px' }}>INT</span>}
      {c.also_in && <span style={{ fontSize: 8, fontWeight: 800, color: C.t5 }}>· {c.also_in}</span>}
    </div>
  )

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <div style={{ padding: 10, display: 'flex', gap: 6, borderBottom: `2px solid ${C.border}`, background: C.surface }}>
        <input className="nb-in" style={{ ...inputStyle, fontFamily: MONO }} value={manual} placeholder="/command …" onChange={e => setManual(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') run(manual) }} />
        <Btn variant="primary" onClick={() => run(manual)} disabled={!manual.trim() || running}>{running ? '…' : 'Run'}</Btn>
      </div>
      {screen && (
        <div style={{ borderBottom: `2px solid ${C.border}` }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 10px', background: C.codeBg }}>
            <span style={{ fontSize: 10, fontWeight: 800, color: C.t1, fontFamily: MONO }}>{screen.command}</span>
            {screen.interactive && <span style={{ fontSize: 8, fontWeight: 800, color: C.warnText }}>interactive — drives a sub-prompt</span>}
            <div style={{ flex: 1 }} />
            <Btn variant="ghost" onClick={() => setScreen(null)}>✕</Btn>
          </div>
          <pre style={{ margin: 0, padding: 10, maxHeight: 160, overflow: 'auto', fontSize: 10, fontFamily: MONO, color: C.t3, whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{screen.screen}</pre>
        </div>
      )}
      <div style={{ padding: 10, flexShrink: 0 }}>
        <input className="nb-in" style={inputStyle} value={q} placeholder="Filter commands…" onChange={e => setQ(e.target.value)} />
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: '0 10px 10px' }}>
        {filtered ? (
          filtered.length === 0 ? <div style={{ fontSize: 11, color: C.t5, textAlign: 'center', marginTop: 20 }}>No matches.</div>
            : filtered.map(c => <CmdRow key={c.command} c={c} />)
        ) : catalog ? (
          catalog.clusters.map(cl => (
            <div key={cl}>
              <div style={{ fontSize: 9, fontWeight: 800, color: C.t3, textTransform: 'uppercase', letterSpacing: '0.05em', margin: '10px 0 6px' }}>{cl}</div>
              {(catalog.by_cluster[cl] || []).map(c => <CmdRow key={c.command} c={c} />)}
            </div>
          ))
        ) : <div style={{ fontSize: 11, color: C.t5, textAlign: 'center', marginTop: 20 }}>Loading catalog…</div>}
      </div>
    </div>
  )
}

// ---- Panel shell -----------------------------------------------------------

type AgentTab = 'details' | 'create' | 'console'

export function AgentPanel({ session, ctx, tab, onTab, onSetModel, onSetEffort, onRetire, onCreate, creating, nowMs }: {
  session: Session | null
  ctx: ContextUsage | null
  tab: AgentTab
  onTab: (t: AgentTab) => void
  onSetModel: (m: string) => void
  onSetEffort: (e: string) => void
  onRetire: () => void
  onCreate: (p: CreatePayload) => void
  creating: boolean
  nowMs: number
}) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{ height: 34, minHeight: 34, background: C.surface, borderBottom: `2px solid ${C.border}`, display: 'flex', alignItems: 'center', padding: '0 10px', gap: 8, flexShrink: 0 }}>
        <span style={{ fontSize: 11, fontWeight: 800, color: C.t1, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Agent</span>
        <div style={{ flex: 1 }} />
        <Tabs tabs={[{ value: 'details', label: 'Details' }, { value: 'console', label: 'Console' }, { value: 'create', label: 'Create' }]} active={tab} onChange={(t) => onTab(t as AgentTab)} />
      </div>
      {tab === 'create' ? (
        <Create onCreate={onCreate} onCancel={() => onTab('details')} busy={creating} />
      ) : tab === 'console' ? (
        session ? <Console session={session} /> : (
          <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20, textAlign: 'center', color: C.t5, fontSize: 11, lineHeight: 1.6 }}>
            Select an agent to open its Console.
          </div>
        )
      ) : session ? (
        <Details session={session} ctx={ctx} onSetModel={onSetModel} onSetEffort={onSetEffort} onRetire={onRetire} nowMs={nowMs} />
      ) : (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 20, textAlign: 'center', color: C.t5, fontSize: 11, lineHeight: 1.6 }}>
          No agent selected.<br />Pick a card in the Team Graph,<br />or switch to Create.
        </div>
      )}
    </div>
  )
}
