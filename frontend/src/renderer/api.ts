// ============================================================================
// Sidecar API — base URL, types, and thin fetch helpers
// ----------------------------------------------------------------------------
// The renderer reaches the sidecar via window.awl.sidecarUrl (injected by the
// Electron preload), falling back to http://127.0.0.1:7690 when served standalone
// in a browser for verification.
// ============================================================================

export const API: string = (window as any).awl?.sidecarUrl || 'http://127.0.0.1:7690'

// ---- Types (mirror sidecar to_dict / endpoint shapes) ----------------------

export interface Identity {
  role: string
  number: number
  name: string
  color: string   // hex from the 16 --ag-* tokens
  icon: string    // name from assets/icons/agents/
}

export interface LaunchConfig {
  allowed_tools: string[] | null
  disallowed_tools: string[] | null
  permission_rules: Record<string, string[]> | null
  enabled_plugins: Record<string, boolean> | null
  mcp_servers: string[] | null
}

export interface Session {
  session_id: string
  agent_type: string | null
  model: string | null
  permission_mode: string
  cwd: string | null
  driver: string
  status: string // connecting | idle | running | error | closed
  created_at: string
  total_cost_usd: number
  total_turns: number
  event_count: number
  has_pending_permission: boolean
  permission_request: PermissionDetail | null
  identity: Identity | null
  launch_config: LaunchConfig
}

export interface SDKEvent {
  type: string
  subtype?: string
  sdk_type?: string
  timestamp?: string
  data?: any
  content?: any
  [key: string]: any
}

export interface ContextUsage {
  tokens: number
  window: number
  model: string | null
  percent: number
  turns: number
  work_steps: number
  tools: Record<string, number>
  tool_total: number
}

export interface UsageAgent {
  session_id: string
  model: string | null
  status: string
  tokens: number | null
  window: number | null
  percent: number | null
  work_steps: number | null
  tool_total: number | null
}

export interface Usage {
  agents: UsageAgent[]
  fleet: { agent_count: number; total_tokens: number }
  token_pill: number
}

export interface Subagent {
  id: string
  tool_use_id: string | null
  agent_id: string | null
  type: string | null
  description: string | null
  status: 'running' | 'done' | 'error'
  usage: any
}

export interface Subagents {
  count: number
  subagents: Subagent[]
}

export interface PermissionDetail {
  question?: string
  options?: { index: number; label: string }[]
  raw?: string
}

// ---- Create payload --------------------------------------------------------

export interface CreatePayload {
  model?: string | null
  permission_mode?: string
  cwd?: string | null
  allowed_tools?: string[] | null
  disallowed_tools?: string[] | null
  identity?: Partial<Identity> | null
}

// ---- Fetch helpers ---------------------------------------------------------

async function getJSON<T>(path: string): Promise<T | null> {
  try {
    const r = await fetch(`${API}${path}`)
    if (!r.ok) return null
    return (await r.json()) as T
  } catch {
    return null
  }
}

async function postJSON<T>(path: string, body?: any): Promise<T | null> {
  try {
    const r = await fetch(`${API}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
    if (!r.ok) return null
    return (await r.json()) as T
  } catch {
    return null
  }
}

export const api = {
  health: () => getJSON<{ status: string; version: string; active_sessions: number }>('/health'),
  sessions: () => getJSON<Session[]>('/sessions'),
  session: (id: string) => getJSON<Session>(`/sessions/${id}`),
  history: (id: string) => getJSON<SDKEvent[]>(`/sessions/${id}/history`),
  context: (id: string) => getJSON<ContextUsage>(`/sessions/${id}/context`),
  subagents: (id: string) => getJSON<Subagents>(`/sessions/${id}/subagents`),
  usage: () => getJSON<Usage>('/usage'),
  create: (payload: CreatePayload) => postJSON<Session>('/sessions', payload),
  send: (id: string, prompt: string) =>
    fetch(`${API}/sessions/${id}/send`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt }),
    }),
  interrupt: (id: string) => postJSON(`/sessions/${id}/interrupt`),
  retire: (id: string) =>
    fetch(`${API}/sessions/${id}`, { method: 'DELETE' }),
  setModel: (id: string, model: string) => postJSON(`/sessions/${id}/model`, { model }),
  setEffort: (id: string, effort: string) => postJSON(`/sessions/${id}/effort`, { effort }),
  answerPermission: (id: string, approve: boolean) =>
    postJSON(`/sessions/${id}/permission`, { approve }),
  iconUrl: (icon: string, color: string) =>
    `${API}/assets/agent-icons/${encodeURIComponent(icon)}.svg?color=${encodeURIComponent(color)}`,
}
