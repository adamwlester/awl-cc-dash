// ============================================================================
// Settings — the step-into full-window view (Projects · Setups · Usage · MCP ·
// Plugins · Config). Projects leads and is fully live (§3.3/§3.4: open/close
// flows, the two-option close confirm, register via path input); the other
// tabs read from the existing /settings endpoints.
// ============================================================================

import React, { useEffect, useState } from 'react'
import { api } from '../api'
import { useDash } from '../store'
import { Ic } from '../lib/icons'
import { fmtTokens, timeAgo } from '../lib/identity'
import { toast } from '../lib/toast'

const TABS = ['projects', 'setups', 'usage', 'mcp', 'plugins', 'config'] as const

export function SettingsView() {
  const d = useDash()
  const tab = d.settingsTab

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape' && d.settingsOpen) d.closeSettings() }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [d.settingsOpen])

  if (!d.settingsOpen) return null
  return (
    <div className="settings-view open" aria-hidden={false}>
      <div className="set-head">
        <span className="set-title"><Ic name="settings" />Settings</span>
        <div className="set-tabs">
          {TABS.map(t => (
            <button key={t} className={`tab-btn${tab === t ? ' active' : ''}`} onClick={() => d.openSettings(t)}>
              {t === 'mcp' ? 'MCP' : t[0].toUpperCase() + t.slice(1)}
            </button>
          ))}
        </div>
        <button data-comp="button" className="btn set-close" onClick={d.closeSettings}><Ic name="x" className="w-3 h-3" />Close</button>
      </div>
      <div className="set-body">
        <div className="set-wrap">
          {tab === 'projects' && <ProjectsTab />}
          {tab === 'usage' && <UsageTab />}
          {tab === 'mcp' && <McpTab />}
          {tab === 'plugins' && <PluginsTab />}
          {tab === 'config' && <ConfigTab />}
          {tab === 'setups' && <SetupsTab />}
        </div>
      </div>
    </div>
  )
}

function Note({ children }: { children: React.ReactNode }) {
  return <div data-comp="settings-note" className="set-note"><Ic name="info" /><span>{children}</span></div>
}
function Sec({ icon, title, kind, kindCls, children }: { icon: string; title: string; kind?: string; kindCls?: string; children: React.ReactNode }) {
  return (
    <div className="set-sec">
      <div data-comp="settings-section-header" className="set-sec-h">
        <span className="nm"><Ic name={icon} />{title}</span>
        {kind && <span data-comp="settings-kind-badge" className={`set-kind ${kindCls || 'ro'}`}>{kind}</span>}
      </div>
      <div className="set-sec-b">{children}</div>
    </div>
  )
}
function Row({ k, v, right }: { k: string; v: React.ReactNode; right?: React.ReactNode }) {
  return <div data-comp="settings-row" className="set-row"><span className="rk">{k}</span><span className="rv plain">{v}</span>{right && <span className="rt">{right}</span>}</div>
}

// ---- PROJECTS ------------------------------------------------------------------
function ProjectsTab() {
  const d = useDash()
  const [confirm, setConfirm] = useState(false)
  const [regPath, setRegPath] = useState('')
  const [flashPath, setFlashPath] = useState<string | null>(null)
  useEffect(() => { d.refreshProjects() }, [])
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape' && confirm) { e.stopPropagation(); setConfirm(false) } }
    document.addEventListener('keydown', onKey, true)
    return () => document.removeEventListener('keydown', onKey, true)
  }, [confirm])

  const proj = d.projects
  const open = proj?.projects.find(p => p.open) || null

  const doClose = async (stop: boolean) => {
    setConfirm(false)
    const r = await api.closeProject(stop)
    toast(r ? (stop ? 'Project closed — agents stopped' : 'Project closed — agents keep running in tmux') : 'Close failed')
    d.refreshProjects()
  }
  const doOpen = async (path: string) => {
    const r = await api.openProject(path)
    toast(r ? `Opened ${r.name || path}` : 'Open failed — close the current project first?')
    d.refreshProjects()
  }
  const doRegister = async () => {
    const p = regPath.trim()
    if (!p) { toast('Enter a folder path to register'); return }
    const r = await api.registerProject(p)
    toast(r ? `Registered ${r.name || p}` : 'Register failed (does the folder exist?)')
    if (r) { setFlashPath(r.path); setTimeout(() => setFlashPath(null), 1200); setRegPath('') }
    d.refreshProjects()
  }

  return (
    <div className="set-pane active">
      <Note>Open, switch, and register <b>projects</b> — the repo/folder a fleet of agents works in. <b>One project is open at a time</b>; close the current project before opening another. Closing can leave its agents running in tmux (reopening reattaches them) or stop them.</Note>

      {open ? (
        <div data-comp="active-project-card" className="set-sec">
          <div data-comp="settings-section-header" className="set-sec-h">
            <span className="nm"><Ic name="folder-open" />Active project</span>
            <span data-comp="connector-health-badge" className="hbadge hb-conn"><span className="hd" style={{ background: 'var(--success)' }} />Open</span>
          </div>
          <div className="set-sec-b">
            <Row k="Project" v={open.name} />
            <Row k="Repo path" v={open.path} />
            <Row k="Agents" v={<><b>{open.agent_count}</b> agents attached</>} />
            <Row k="Last opened" v={open.last_used ? `${open.last_used.slice(0, 16).replace('T', ' ')} · ${timeAgo(open.last_used, d.nowMs)} ago` : '—'} />
            <div data-comp="settings-row" className="set-row">
              <span className="rk">Close</span>
              <span className="rv plain" style={{ color: 'var(--muted)' }}>Returns the dashboard to no-project. Its agents can keep running in tmux, or be stopped.</span>
              <span className="rt"><button data-comp="button" className="btn btn-sm" onClick={() => setConfirm(true)}><Ic name="x-circle" className="w-3 h-3" />Close project</button></span>
            </div>
            <div data-comp="project-close-confirm" className={`proj-close-confirm${confirm ? ' show' : ''}`} role="group" aria-label="Close project confirm">
              <div className="proj-cc-head"><Ic name="alert-triangle" /><span>Close this project?</span><button data-comp="ghost-icon-button" className="ghost-ic" title="Cancel (Esc)" onClick={() => setConfirm(false)}><Ic name="x" /></button></div>
              <div className="proj-opt">
                <button data-comp="button" className="btn-main btn-sm" onClick={() => doClose(false)}><Ic name="x-circle" className="w-3 h-3" />Close</button>
                <span className="proj-opt-note">Agents keep running in tmux — reopening the project reattaches them.</span>
              </div>
              <div className="proj-opt">
                <button data-comp="button" className="btn-danger btn-sm" onClick={() => doClose(true)}><Ic name="square" className="w-3 h-3" />Close &amp; stop agents</button>
                <span className="proj-opt-note">Ends every agent session in this project first.</span>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div data-comp="project-empty" className="proj-empty"><Ic name="folder" /><span>No project open — open one from the list below, or register another folder.</span></div>
      )}

      <Sec icon="folder-git-2" title="Known projects" kind={`${proj?.projects.length ?? 0} · open / register`} kindCls="edit">
        {(() => {
          // Last-used leads (§3.1/§9.1 picker-first startup): with no project
          // open, the most-recent row is the preselected pick — it sorts first
          // and its Open takes the primary treatment.
          const rows = [...(proj?.projects || [])].sort((a2, b2) => (b2.last_used || '').localeCompare(a2.last_used || ''))
          const preselect = !open && rows.length ? rows[0].path : null
          return rows.map(p => (
            <div key={p.path} data-comp="registry-row" className={`reg-row${p.open ? ' proj-open' : ''}${flashPath === p.path ? ' proj-flash' : ''}`}>
              <div className="reg-main">
                <div className="reg-name">{p.name}</div>
                <div className="reg-meta">{p.path} · {p.agent_count} agent{p.agent_count === 1 ? '' : 's'}{p.last_used ? ` · ${timeAgo(p.last_used, d.nowMs)} ago` : ''}</div>
              </div>
              <div className="reg-rt">
                {p.open
                  ? <span data-comp="connector-health-badge" className="hbadge hb-conn"><span className="hd" style={{ background: 'var(--success)' }} />Open</span>
                  : <button data-comp="button" className={`${preselect === p.path ? 'btn-main' : 'btn'} btn-sm`} disabled={!!open}
                    title={open ? 'Close the current project first (one at a time)' : preselect === p.path ? 'Last used — the preselected pick' : 'Open this project'}
                    onClick={() => doOpen(p.path)}><Ic name="folder-open" className="w-3 h-3" />Open</button>}
              </div>
            </div>
          ))
        })()}
        {!proj?.projects.length && <Row k="Registry" v="No projects registered yet — add one below." />}
      </Sec>

      <Sec icon="folder-plus" title="Register" kind="Editable" kindCls="edit">
        <div data-comp="settings-row" className="set-row">
          <span className="rk">Other folder</span>
          <span className="rv"><div className="in-wrap"><input className="in" type="text" placeholder="e.g. ~/MeDocuments/my-project" value={regPath} onChange={e => setRegPath(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') doRegister() }} /></div></span>
          <span className="rt"><button data-comp="button" className="btn btn-sm" onClick={doRegister}><Ic name="folder-plus" className="w-3 h-3" />Register</button></span>
        </div>
      </Sec>
    </div>
  )
}

// ---- USAGE -----------------------------------------------------------------------
function UsageTab() {
  const d = useDash()
  const [account, setAccount] = useState<any>(null)
  useEffect(() => { api.settingsAccount('').then(setAccount) }, [])
  const agents = Object.values(d.usageBy)
  const total = d.tokenPill
  return (
    <div className="set-pane active">
      <Note>Plan, limits, and token consumption — the <b>/stats</b> · <b>/status</b> surface. Usage only; per-agent cost/dollar spend is deliberately out of scope.</Note>
      <Sec icon="user" title="Account" kind="Read-only">
        {account && !account.signed_out
          ? (<><Row k="Email" v={account.email || '—'} /><Row k="Organization" v={account.org || '—'} /><Row k="Plan" v={<b>{account.plan || '—'}</b>} /></>)
          : <Row k="Account" v="local credentials not readable from here — the live limits band lands with the account endpoint" />}
      </Sec>
      <Sec icon="sigma" title="Token consumption" kind="Read-only">
        <Row k="This session" v={<><b>Σ {fmtTokens(total)}</b> tokens across {agents.length} agent{agents.length === 1 ? '' : 's'}</>} />
        {agents.map(a => (
          <div data-comp="settings-row" className="set-row" key={a.session_id}>
            <span className="rk">{a.session_id.slice(0, 22)}</span>
            <span className="rv"><div className="use-bar" style={{ maxWidth: 340 }}><i style={{ width: `${Math.min(100, a.percent ?? 0)}%`, background: (a.percent ?? 0) > 75 ? 'var(--danger)' : (a.percent ?? 0) > 50 ? 'var(--warning)' : 'var(--success)' }} /></div></span>
            <span className="rt" style={{ fontFamily: 'var(--font-mono)', fontWeight: 800, fontSize: 10 }}>{a.tokens != null ? fmtTokens(a.tokens) : '—'}{a.percent != null ? ` · ${Math.round(a.percent)}%` : ''}</span>
          </div>
        ))}
        {!agents.length && <Row k="Agents" v="none live" />}
      </Sec>
    </div>
  )
}

// ---- MCP -------------------------------------------------------------------------
function McpTab() {
  const d = useDash()
  const [scope, setScope] = useState<'user' | 'project'>('user')
  const [data, setData] = useState<{ user: any[]; project: any[] } | null>(null)
  useEffect(() => { api.settingsMcp(d.projectCwd || undefined).then(setData) }, [d.projectCwd])
  const list = (data?.[scope] || []) as any[]
  return (
    <div className="set-pane active">
      <Note>The <b>global registry</b> and enablement of MCP servers. Per-agent access (which agent may use which server) stays in the <b>Agent</b> panel.</Note>
      <div className="set-scopebar">
        <div data-comp="scope-switcher" className="set-scope">
          <button className={scope === 'user' ? 'active' : ''} onClick={() => setScope('user')}>User</button>
          <button className={scope === 'project' ? 'active' : ''} onClick={() => setScope('project')}>Project</button>
        </div>
        <span className="set-scope-note">user → ~/.claude.json · project → .mcp.json</span>
      </div>
      <Sec icon="server" title="Server registry" kind={`${list.length} servers`} kindCls="edit">
        {list.map((srv: any, i: number) => (
          <div data-comp="registry-row" className={`reg-row${srv.enabled === false ? ' off' : ''}`} key={srv.name || i}>
            <div className="reg-main">
              <div className="reg-name">{srv.name || String(srv)}</div>
              <div className="reg-meta">{srv.transport || srv.type || 'stdio'}{srv.command ? ` · ${String(srv.command).slice(0, 40)}` : ''}</div>
            </div>
            <div className="reg-rt">
              <span data-comp="connector-health-badge" className={`hbadge ${srv.enabled === false ? 'hb-parked' : 'hb-conn'}`}>{srv.enabled === false ? 'Parked' : <><span className="hd" style={{ background: 'var(--success)' }} />Configured</>}</span>
              <button data-comp="switch" className={`swh${srv.enabled === false ? '' : ' on'}`} title="Enable/disable writes land with the settings-write wiring" onClick={() => toast('MCP enable/disable writes land with the settings-write wiring')} />
            </div>
          </div>
        ))}
        {!list.length && <Row k="Defined" v={`None at ${scope} scope`} />}
      </Sec>
    </div>
  )
}

// ---- PLUGINS -----------------------------------------------------------------------
function PluginsTab() {
  const [data, setData] = useState<{ installed: any[]; marketplaces: any[] } | null>(null)
  useEffect(() => { api.settingsPlugins().then(setData) }, [])
  return (
    <div className="set-pane active">
      <Note>Installed plugins, their enabled state, and marketplaces. Per-agent capability stays in the <b>Agent</b> panel.</Note>
      <Sec icon="store" title="Marketplaces" kind={String(data?.marketplaces?.length ?? 0)}>
        <div className="pl-chips" style={{ marginTop: 'var(--space-2)' }}>
          {(data?.marketplaces || []).map((m: any, i: number) => <span data-comp="plugin-skill-chip" className="pl-chip" key={i}>{m.name || String(m)}</span>)}
          {!data?.marketplaces?.length && <span className="awl-empty">none</span>}
        </div>
      </Sec>
      <Sec icon="puzzle" title="Installed" kind={`${data?.installed?.length ?? 0} · enable / disable`} kindCls="edit">
        {(data?.installed || []).map((p: any, i: number) => (
          <div data-comp="registry-row" className={`reg-row${p.enabled === false ? ' off' : ''}`} key={p.name || i}>
            <div className="reg-main">
              <div className="reg-name"><span className="set-dot" style={{ background: p.enabled === false ? 'var(--muted-2)' : 'var(--success)', display: 'inline-block', marginRight: 'var(--space-7)', verticalAlign: 'middle' }} />{p.name || String(p)}</div>
              {p.version && <div className="reg-meta">v{p.version}</div>}
            </div>
            <div className="reg-rt">
              <button data-comp="switch" className={`swh${p.enabled === false ? '' : ' on'}`} title="Enable/disable writes land with the settings-write wiring" onClick={() => toast('Plugin toggles land with the settings-write wiring')} />
            </div>
          </div>
        ))}
        {!data?.installed?.length && <Row k="Installed" v="none readable" />}
      </Sec>
    </div>
  )
}

// ---- CONFIG ------------------------------------------------------------------------
function ConfigTab() {
  const d = useDash()
  const [scope, setScope] = useState<'global' | 'project'>('global')
  const [cfg, setCfg] = useState<any>(null)
  useEffect(() => { api.settingsConfig(d.projectCwd || undefined).then(setCfg) }, [d.projectCwd])
  const pane = cfg?.[scope] ?? cfg
  const rows: [string, any][] = pane && typeof pane === 'object' ? Object.entries(pane).slice(0, 40) : []
  return (
    <div className="set-pane active">
      <Note>Default model, permission mode, sandbox, hooks, env, CLAUDE.md, and plans. Each setting is tagged <b>LIVE</b> or <b>NEW SESSION</b> per the CLI lifecycle map.</Note>
      <div className="set-scopebar">
        <div data-comp="scope-switcher" className="set-scope">
          <button className={scope === 'global' ? 'active' : ''} onClick={() => setScope('global')}>Global</button>
          <button className={scope === 'project' ? 'active' : ''} onClick={() => setScope('project')}>Project</button>
        </div>
        <span className="set-scope-note">global → ~/.claude · project → .claude</span>
      </div>
      {scope === 'global' && <div data-comp="settings-note" className="set-warn"><Ic name="alert-triangle" />Editing <b>~/.claude</b> (global) affects every project — changes require an explicit confirm.</div>}
      <Sec icon="cpu" title="Configuration" kind="Read-only (writes land with the confirm gate)">
        {rows.map(([k, v]) => (
          <Row key={k} k={k} v={<span style={{ fontFamily: 'var(--font-mono)', fontSize: 10 }}>{typeof v === 'object' ? JSON.stringify(v).slice(0, 90) : String(v).slice(0, 90)}</span>} />
        ))}
        {!rows.length && <Row k="Config" v="not readable from the sidecar yet" />}
      </Sec>
    </div>
  )
}

// ---- SETUPS -------------------------------------------------------------------------
function SetupsTab() {
  const d = useDash()
  const links = d.links.links.filter(l => l.active).length
  return (
    <div className="set-pane active">
      <Note>Save &amp; load a full dashboard setup — its agents and the links between them.</Note>
      <Sec icon="download" title="Save current setup" kind="Editable" kindCls="edit">
        <Row k="Captures" v={<><b>{d.sessions.length}</b> agents · <b>{links}</b> links</>} />
        <div data-comp="settings-row" className="set-row">
          <span className="rk">Name</span>
          <span className="rv"><div className="in-wrap"><input className="in" type="text" placeholder="e.g. security-audit-fleet" /></div></span>
          <span className="rt"><button data-comp="button" className="btn-main btn-sm" onClick={() => toast('Setup save/load lands with the setups backend')}><Ic name="download" className="w-3 h-3" />Save setup</button></span>
        </div>
      </Sec>
      <Sec icon="inbox" title="Saved setups" kind="0">
        <Row k="Saved" v="none yet — the setups store is backend work" />
      </Sec>
    </div>
  )
}
