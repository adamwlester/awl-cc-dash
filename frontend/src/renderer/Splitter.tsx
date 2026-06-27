// ============================================================================
// Splitter — a draggable panel divider (a 3px navy line with a wider grab area)
// ----------------------------------------------------------------------------
// 'vertical'   = a vertical bar dragged horizontally (between columns).
// 'horizontal' = a horizontal bar dragged vertically (between stacked panels).
// onDelta is the incremental pixel movement along the drag axis; the parent
// applies it to the adjacent panel's size (clamped to its own min/max).
// ============================================================================

import React, { useRef } from 'react'
import { C } from './tokens'

export function Splitter({ orientation, onDelta }: {
  orientation: 'vertical' | 'horizontal'
  onDelta: (delta: number) => void
}) {
  const isV = orientation === 'vertical'
  const last = useRef(0)

  const onDown = (e: React.MouseEvent) => {
    last.current = isV ? e.clientX : e.clientY
    const move = (ev: MouseEvent) => {
      const cur = isV ? ev.clientX : ev.clientY
      onDelta(cur - last.current)
      last.current = cur
    }
    const up = () => {
      window.removeEventListener('mousemove', move)
      window.removeEventListener('mouseup', up)
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
    }
    window.addEventListener('mousemove', move)
    window.addEventListener('mouseup', up)
    document.body.style.cursor = isV ? 'col-resize' : 'row-resize'
    document.body.style.userSelect = 'none'
    e.preventDefault()
  }

  return (
    <div
      data-splitter={orientation}
      onMouseDown={onDown}
      style={{
        flexShrink: 0, display: 'flex', alignItems: 'center', justifyContent: 'center',
        cursor: isV ? 'col-resize' : 'row-resize', zIndex: 5,
        ...(isV ? { width: 7, height: '100%' } : { height: 7, width: '100%' }),
      }}
    >
      <div style={{ background: C.border, ...(isV ? { width: 3, height: '100%' } : { height: 3, width: '100%' }) }} />
    </div>
  )
}
