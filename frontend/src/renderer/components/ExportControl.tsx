// ============================================================================
// The merged Export control — ONE selection-gated dropdown (Copy · Export→file
// · Embed · Attach) reused by the Feed, History, and Library footers.
// DOM mirrors expMenuHTML in design/behavior.js.
// ============================================================================

import React, { useEffect, useRef, useState } from 'react'
import { Ic } from '../lib/icons'

export interface ExportActions {
  enabled: boolean
  wholeOnly?: boolean         // Attach gate (whole selections only)
  onCopy: () => void
  onFile: () => void | Promise<void>
  onEmbed: () => void
  onAttach: () => void | Promise<void>
  fileDisabled?: boolean
}

export function ExportControl({ a }: { a: ExportActions }) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const close = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false) }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])
  const mi = (icon: string, label: string, sub: string, disabled: boolean, fn: () => void) => (
    <button className="exp-mi ea-mi" disabled={disabled} onClick={() => { fn(); setOpen(false) }}>
      <Ic name={icon} /><span className="lead"><b>{label}</b><span className="sub">{sub}</span></span>
    </button>
  )
  return (
    <div data-comp="export-control" className={`exp ea-dd${open ? ' open' : ''}`} ref={ref}>
      <button className="exp-btn" title="Export · add to prompt…" disabled={!a.enabled} onClick={e => { e.stopPropagation(); setOpen(o => !o) }}>
        <Ic name="download" className="ic" /><Ic name="chevron-down" className="cv" />
      </button>
      <div className="exp-menu">
        <div className="exp-h">Copy &amp; Export</div>
        {mi('copy', 'Copy selected', 'the selection to the clipboard', !a.enabled, a.onCopy)}
        {mi('file-down', 'Export selected → file', 'new doc in Library → Documents', !a.enabled || !!a.fileDisabled, () => void a.onFile())}
        <div className="exp-h">Add to prompt</div>
        {mi('quote', 'Embed in prompt', 'drop a frozen quoted block into the Editor', !a.enabled, a.onEmbed)}
        {mi('paperclip', 'Attach as file', 'save it as a doc + add a path chip to the Editor', !a.enabled || !!a.fileDisabled, () => void a.onAttach())}
      </div>
    </div>
  )
}
