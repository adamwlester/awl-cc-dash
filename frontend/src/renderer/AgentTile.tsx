// ============================================================================
// AgentTile — the recolorable game-icon identity tile
// ----------------------------------------------------------------------------
// The tile background is the agent's color; the glyph is a white knockout. The
// recolored SVG comes from the sidecar (GET /assets/agent-icons/<icon>?color=),
// so a tile is a single <img>. If the icon fails to load, the colored square
// (with the agent's color) still reads as identity.
// ============================================================================

import React from 'react'
import { C } from './tokens'
import { api } from './api'

export function AgentTile({ icon, color, size = 28, radius = 5 }: {
  icon?: string | null
  color?: string | null
  size?: number
  radius?: number
}) {
  const c = color || C.mutedFill
  const ic = icon || 'android-mask'
  return (
    <div style={{
      width: size, height: size, borderRadius: radius, border: `2px solid ${C.border}`,
      overflow: 'hidden', flexShrink: 0, background: c, lineHeight: 0,
    }}>
      <img
        src={api.iconUrl(ic, c)}
        alt=""
        width={size} height={size}
        draggable={false}
        style={{ display: 'block', width: '100%', height: '100%' }}
        onError={(e) => { (e.currentTarget as HTMLImageElement).style.visibility = 'hidden' }}
      />
    </div>
  )
}
