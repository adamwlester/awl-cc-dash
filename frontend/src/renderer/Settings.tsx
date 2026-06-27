// ============================================================================
// Settings — a step-into view wiring the PROVEN registry reads (read-only)
// ----------------------------------------------------------------------------
// Replaces the 3-pane body; returns on Close. Tabs: Usage · MCP · Plugins ·
// Config — each backed by a proven endpoint (/usage, /settings/mcp, /plugins,
// /config). Reads only: enable/disable toggles and the gated global-edit are a
// later run (surfaced, not faked). Setups and the Usage plan/limits band are
// absent (Setups has no store; live rate-limit windows are API-only, not local).
// ============================================================================

import React, { useEffect, useState } from 'react'
import { C, FONT, MONO } from './tokens'
import { Tabs, Btn, Segmented } from './ui'
import { AgentTile } from './AgentTile'
import { api, type Session, type Usage } from './api'

function Pill({ on }: { on: boolean }) {
  return (
    <span style={{
      fontSize: 9, fontWeight: 800, padding: '2px 7px', borderRadius: 3, border: `2px solid ${C.border}`,
      background: on ? C.successSoft : C.surface, color: on ? C.successText : C.t5,
    }}>{on ? 'enabled' : 'disabled'}</span>
  )
}

function Tag({ children, tone }: { children: React.ReactNode; tone: 'live' | 'new' }) {
  return (
    <span style={{
      fontSize: 8, fontWeight: 800, padding: '1px 5px', borderRadius: 3, border: `1.5px solid ${C.border}`,
      background: tone === 'live' ? C.successSoft : C.warnSoft, color: tone === 'live' ? C.successText : C.warnText,
      textTransform: 'uppercase', marginLeft: 6,
    }}>{tone === 'live' ? 'Live' : 'New session'}</span>
  )
}

const SectionH = ({ children }: { children: React.ReactNode }) => (
  <div style={{ fontSize: 10, fontWeight: 800, color: C.t3, textTransform: 'uppercase', letterSpacing: '0.05em', margin: '14px 0 8px', borderBottom: `2px solid ${C.border}`, paddingBottom: 4 }}>{children}</div>
)

const card: React.CSSProperties = { background: C.card, border: `2px solid ${C.border}`, borderRadius: 5, boxShadow: C.shadowSm, padding: '8px 11px', marginBottom: 8 }
const kv: React.CSSProperties = { fontSize: 11, color: C.t2, fontFamily: MONO }

// ---- Usage -----------------------------------------------------------------
function UsageTab({ sessions }: { sessions: Session[] }) {
  const [u, setU] = useState<Usage | null>(null)
  useEffect(() => { api.usage().then(setU) }, [])
  const byId = Object.fromEntries(sessions.map(s => [s.session_id, s]))
  return (
    <div>
      <SectionH>Token consumption (this session)</SectionH>
      <div style={{ ...card, display: 'flex', gap: 24, alignItems: 'center' }}>
        <div><div style={{ fontSize: 22, fontWeight: 900, color: C.t1, fontFamily: MONO }}>{(u?.fleet.total_tokens ?? 0).toLocaleString()}</div><div style={{ fontSize: 9, color: C.t5 }}>fleet total tokens</div></div>
        <div><div style={{ fontSize: 22, fontWeight: 900, color: C.t1 }}>{u?.fleet.agent_count ?? 0}</div><div style={{ fontSize: 9, color: C.t5 }}>agents</div></div>
      </div>
      <SectionH>Per agent</SectionH>
      {(u?.agents || []).map(a => {
        const id = byId[a.session_id]?.identity
        return (
          <div key={a.session_id} style={{ ...card, display: 'flex', alignItems: 'center', gap: 10 }}>
            <AgentTile icon={id?.icon} color={id?.color} size={24} />
            <div style={{ flex: 1, fontSize: 11, fontWeight: 800, color: C.t1 }}>{id ? `${String(id.number).padStart(2, '0')} ${id.name || id.role}` : a.session_id}</div>
            <div style={{ ...kv, width: 70 }}>{a.model || '—'}</div>
            <div style={{ ...kv, width: 90, textAlign: 'right' }}>{a.tokens != null ? a.tokens.toLocaleString() : '—'} tok</div>
            <div style={{ ...kv, width: 50, textAlign: 'right' }}>{a.percent != null ? `${a.percent}%` : '—'}</div>
            <div style={{ ...kv, width: 60, textAlign: 'right' }}>{a.work_steps ?? '—'} turns</div>
          </div>
        )
      })}
      <div style={{ fontSize: 9, color: C.t5, marginTop: 10 }}>Plan / rate-limit windows are API-only (not in local files) — not built. Per-agent cost is out of scope (bridge emits none).</div>
    </div>
  )
}

// ---- MCP -------------------------------------------------------------------
function McpTab() {
  const [scope, setScope] = useState<'user' | 'project'>('user')
  const [data, setData] = useState<{ user: any[]; project: any[] } | null>(null)
  useEffect(() => { api.settingsMcp().then(setData) }, [])
  const servers = (scope === 'user' ? data?.user : data?.project) || []
  return (
    <div>
      <div style={{ width: 220, marginBottom: 8 }}>
        <Segmented options={[{ value: 'user', label: 'User' }, { value: 'project', label: 'Project' }]} value={scope} onChange={(v) => setScope(v as any)} />
      </div>
      {servers.length === 0 ? <div style={{ fontSize: 11, color: C.t5 }}>No {scope}-scope MCP servers.</div> : servers.map((s, i) => (
        <div key={i} style={card}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ fontSize: 12, fontWeight: 900, color: C.t1 }}>{s.name}</span>
            <Pill on={s.enabled !== false} />
            <div style={{ flex: 1 }} />
            <span style={{ fontSize: 9, color: C.t5 }}>{s.transport}</span>
          </div>
          <div style={{ ...kv, fontSize: 10, color: C.t3, marginTop: 4 }}>{s.command ? `${s.command} ${(s.args || []).join(' ')}` : s.url || ''}</div>
          {s.env_keys?.length ? <div style={{ fontSize: 9, color: C.t5, marginTop: 3 }}>env: {s.env_keys.join(', ')} (values masked)</div> : null}
        </div>
      ))}
    </div>
  )
}

// ---- Plugins ---------------------------------------------------------------
function PluginsTab() {
  const [data, setData] = useState<{ installed: any[]; marketplaces: any[] } | null>(null)
  useEffect(() => { api.settingsPlugins().then(setData) }, [])
  return (
    <div>
      <SectionH>Installed</SectionH>
      {(data?.installed || []).map((p, i) => (
        <div key={i} style={{ ...card, display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 11, fontWeight: 900, color: C.t1 }}>{p.name}</span>
          <span style={{ fontSize: 9, color: C.t5, fontFamily: MONO }}>@{p.marketplace} · v{p.version}</span>
          <div style={{ flex: 1 }} />
          <span style={{ fontSize: 9, color: C.t5 }}>{p.scope}</span>
          <Pill on={p.enabled === true} />
        </div>
      ))}
      <SectionH>Marketplaces</SectionH>
      {(data?.marketplaces || []).length === 0 ? <div style={{ fontSize: 11, color: C.t5 }}>None.</div> : (data?.marketplaces || []).map((m, i) => (
        <div key={i} style={{ ...kv, fontSize: 10, color: C.t3, marginBottom: 4 }}>{typeof m === 'string' ? m : (m.name || JSON.stringify(m))}</div>
      ))}
    </div>
  )
}

// ---- Config ----------------------------------------------------------------
function Row({ label, value, tag }: { label: string; value: React.ReactNode; tag?: 'live' | 'new' }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '6px 0', borderBottom: `1.5px solid ${C.rule}` }}>
      <div style={{ width: 150, fontSize: 10, fontWeight: 800, color: C.t3 }}>{label}{tag && <Tag tone={tag}>{tag}</Tag>}</div>
      <div style={{ flex: 1, ...kv }}>{value ?? '—'}</div>
    </div>
  )
}

function ConfigTab({ project }: { project: string | null }) {
  const [scope, setScope] = useState<'global' | 'project'>('global')
  const [data, setData] = useState<any>(null)
  useEffect(() => { api.settingsConfig(project || undefined).then(setData) }, [project])
  const c = (scope === 'global' ? data?.global : data?.project) || {}
  const perms = c.permissions || {}
  return (
    <div>
      <div style={{ width: 220, marginBottom: 8 }}>
        <Segmented options={[{ value: 'global', label: 'Global' }, { value: 'project', label: 'Project' }]} value={scope} onChange={(v) => setScope(v as any)} />
      </div>
      {scope === 'global' && <div style={{ fontSize: 9, color: C.warnText, background: C.warnSoft, border: `2px solid ${C.border}`, borderRadius: 5, padding: '6px 9px', marginBottom: 8 }}>⚠ Global config affects every project. Edits would be confirm-gated — writes are a later run (reads only here).</div>}
      <div style={card}>
        <Row label="Default model" value={c.model || '(inherit)'} tag="live" />
        <Row label="Effort" value={c.effort || '—'} tag="live" />
        <Row label="Permission mode" value={c.permissionMode || '(default)'} tag="new" />
        <Row label="Sandbox" value={c.sandbox == null ? '—' : String(c.sandbox)} tag="new" />
        <Row label="Plans directory" value={c.plansDirectory || '—'} tag="new" />
        <Row label="permissions.allow" value={(perms.allow || []).join(', ') || '—'} />
        <Row label="permissions.deny" value={(perms.deny || []).join(', ') || '—'} />
        <Row label="permissions.ask" value={(perms.ask || []).join(', ') || '—'} />
        <Row label="env" value={Object.keys(c.env || {}).join(', ') || '—'} />
        <Row label="hooks" value={(c.hooks || []).length ? `${(c.hooks || []).length} configured` : '—'} />
      </div>
      <SectionH>CLAUDE.md</SectionH>
      {(data?.claudeMd || []).map((m: any, i: number) => (
        <div key={i} style={{ ...kv, fontSize: 10, color: m.exists ? C.t2 : C.t5, marginBottom: 3 }}>
          [{m.scope}] {m.path} {m.exists ? '' : '(absent)'}
        </div>
      ))}
    </div>
  )
}

export function Settings({ sessions, project, onClose }: {
  sessions: Session[]
  project: string | null
  onClose: () => void
}) {
  const [tab, setTab] = useState<'usage' | 'mcp' | 'plugins' | 'config'>('usage')
  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column', minHeight: 0, background: C.bg }}>
      <div style={{ height: 40, minHeight: 40, background: C.surface, borderBottom: `2px solid ${C.border}`, display: 'flex', alignItems: 'center', padding: '0 14px', gap: 10, flexShrink: 0 }}>
        <span style={{ fontSize: 12, fontWeight: 900, color: C.t1, textTransform: 'uppercase', letterSpacing: '0.08em' }}>Settings</span>
        <Tabs tabs={[
          { value: 'usage', label: 'Usage' }, { value: 'mcp', label: 'MCP' },
          { value: 'plugins', label: 'Plugins' }, { value: 'config', label: 'Config' },
        ]} active={tab} onChange={(t) => setTab(t as any)} />
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 9, color: C.t5 }}>read-only · writes are a later run</span>
        <Btn variant="cream" onClick={onClose}>✕ Close</Btn>
      </div>
      <div style={{ flex: 1, overflow: 'auto', padding: '14px 18px', fontFamily: FONT }}>
        {tab === 'usage' && <UsageTab sessions={sessions} />}
        {tab === 'mcp' && <McpTab />}
        {tab === 'plugins' && <PluginsTab />}
        {tab === 'config' && <ConfigTab project={project} />}
      </div>
    </div>
  )
}
