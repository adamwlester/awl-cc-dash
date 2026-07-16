// ============================================================================
// Icons — Lucide UI icons + the recolorable agent-icon sprite.
// ----------------------------------------------------------------------------
// The mockup draws UI icons via `<i data-lucide="…">` at stroke-width 2.25;
// here the same names render through lucide-react. Agent icons come from the
// game-icons sprite extracted verbatim from mockup.html (tile bg=currentColor,
// glyph=var(--icon-fg)); icons outside the curated 50 fall back to the
// sidecar's recolor endpoint.
// ============================================================================

import React from 'react'
import {
  Activity, AlertTriangle, ArrowDownLeft, ArrowLeftRight, ArrowLeft, ArrowRight, ArrowUpRight,
  Brain, Check, ChevronDown, ChevronRight, ChevronsDown, ChevronsUp, ChevronsUpDown,
  Clipboard, Clock, CloudDownload, Copy, CornerDownLeft, CornerUpRight, Cpu, Dices, Download, Eye,
  FileDown, FileImage, FileText, Folder, FolderGit2, FolderOpen, FolderPlus, Gauge, GitBranch,
  History, Image, Inbox, Info, Link, Link2, List, ListChecks, Lock, Mail, Maximize2, MessageSquare,
  MessageSquarePlus, Mic, NotebookPen, Paperclip, Pencil, Plus, Power, Puzzle, Quote,
  RotateCcw, Save, ScanSearch, Search, SendHorizontal, Server, Settings, Shield, Sigma,
  SlidersHorizontal, Sparkles, Square, SquarePen, Store, Terminal, ThumbsDown, ThumbsUp,
  Trash2, Undo2, Upload, User, Users, WandSparkles, Webhook, Workflow, X, XCircle, Zap,
  CircleCheck, CircleX, TriangleAlert, type LucideIcon,
} from 'lucide-react'
import { AGENT_SPRITE } from '../design/sprite'
import { API } from '../api'

const MAP: Record<string, LucideIcon> = {
  'activity': Activity, 'alert-triangle': AlertTriangle, 'arrow-down-left': ArrowDownLeft,
  'arrow-left-right': ArrowLeftRight, 'arrow-left': ArrowLeft, 'arrow-right': ArrowRight,
  'arrow-up-right': ArrowUpRight, 'brain': Brain, 'check': Check, 'chevron-down': ChevronDown,
  'chevron-right': ChevronRight, 'chevrons-down': ChevronsDown, 'chevrons-up': ChevronsUp,
  'chevrons-up-down': ChevronsUpDown, 'clipboard': Clipboard, 'clock': Clock, 'copy': Copy,
  'corner-down-left': CornerDownLeft, 'corner-up-right': CornerUpRight, 'cpu': Cpu,
  'dices': Dices, 'download': Download, 'download-cloud': CloudDownload, 'eye': Eye, 'file-down': FileDown,
  'file-image': FileImage, 'file-text': FileText,
  'folder': Folder, 'folder-git-2': FolderGit2, 'folder-open': FolderOpen, 'folder-plus': FolderPlus,
  'gauge': Gauge, 'git-branch': GitBranch, 'history': History, 'image': Image, 'inbox': Inbox,
  'info': Info, 'link': Link, 'link-2': Link2, 'lock': Lock,
  'list': List, 'list-checks': ListChecks, 'mail': Mail, 'maximize-2': Maximize2,
  'message-square': MessageSquare, 'message-square-plus': MessageSquarePlus, 'mic': Mic,
  'notebook-pen': NotebookPen, 'paperclip': Paperclip, 'pencil': Pencil, 'plus': Plus,
  'power': Power, 'puzzle': Puzzle, 'quote': Quote, 'rotate-ccw': RotateCcw, 'save': Save,
  'scan-search': ScanSearch, 'search': Search, 'send-horizontal': SendHorizontal, 'server': Server,
  'settings': Settings, 'shield': Shield, 'sigma': Sigma, 'sliders-horizontal': SlidersHorizontal,
  'sparkles': Sparkles, 'square': Square, 'square-pen': SquarePen, 'store': Store,
  'terminal': Terminal, 'thumbs-down': ThumbsDown, 'thumbs-up': ThumbsUp, 'trash-2': Trash2,
  'undo-2': Undo2, 'upload': Upload, 'user': User, 'users': Users, 'wand-sparkles': WandSparkles,
  'webhook': Webhook, 'workflow': Workflow, 'x': X, 'x-circle': XCircle, 'zap': Zap,
  'circle-check': CircleCheck, 'circle-x': CircleX, 'triangle-alert': TriangleAlert,
}

/** UI icon by mockup name (`data-lucide` equivalent), stroke 2.25 like LU(). */
export function Ic({ name, className, style, size }: {
  name: string; className?: string; style?: React.CSSProperties; size?: number
}) {
  const C = MAP[name]
  if (!C) return null
  return <C className={className ? `lucide ${className}` : 'lucide'} style={style} strokeWidth={2.25} size={size} absoluteStrokeWidth={false} aria-hidden />
}

/** The recolorable agent-icon sprite — mount ONCE near the root. */
export function AgentSprite() {
  return <div style={{ display: 'none' }} aria-hidden dangerouslySetInnerHTML={{ __html: AGENT_SPRITE }} />
}

// icon file name (assets/icons/agents/<name>.svg — what the sidecar assigns)
// → sprite symbol id. Mirrors AGENT_ICONS in design/behavior.js.
export const SPRITE_BY_FILE: Record<string, string> = {
  'wizard-face': 'ag-wizard', 'metal-golem-head': 'ag-golem', 'gas-mask': 'ag-gasmask', 'robot-helmet': 'ag-robot',
  'fox-head': 'ag-fox', 'spider-mask': 'ag-spider', 'eagle-head': 'ag-eagle', 'centurion-helmet': 'ag-centurion',
  'parrot-head': 'ag-parrot', 'tribal-mask': 'ag-tribal', 'astronaut-helmet': 'ag-astronaut', 'third-eye': 'ag-thirdeye',
  'cowled': 'ag-cowled', 'wolf-head': 'ag-wolf', 'bear-head': 'ag-bear', 'tiger-head': 'ag-tiger', 'dragon-head': 'ag-dragon',
  'skull-mask': 'ag-skull', 'ninja-head': 'ag-ninja', 'viking-head': 'ag-viking', 'samurai-helmet': 'ag-samurai',
  'oni': 'ag-oni', 'goblin-head': 'ag-goblin', 'ogre': 'ag-ogre', 'vampire-dracula': 'ag-vampire', 'witch-face': 'ag-witch',
  'pumpkin-mask': 'ag-pumpkin', 'cyborg-face': 'ag-cyborg', 'mecha-head': 'ag-mecha',
  'stag-head': 'ag-stag', 'elephant-head': 'ag-elephant', 'raccoon-head': 'ag-raccoon', 'rabbit-head': 'ag-rabbit',
  'buffalo-head': 'ag-buffalo', 'minotaur': 'ag-minotaur', 'medusa-head': 'ag-medusa', 'orc-head': 'ag-orc',
  'troll': 'ag-troll', 'imp-laugh': 'ag-imp', 'spectre': 'ag-spectre', 'spartan-helmet': 'ag-spartan',
  'black-knight-helm': 'ag-knight', 'pirate-captain': 'ag-pirate', 'plague-doctor-profile': 'ag-plague',
  'clown': 'ag-clown', 'monk-face': 'ag-monk', 'android-mask': 'ag-android', 'samus-helmet': 'ag-samus',
  'death-skull': 'ag-deathskull', 'squid-head': 'ag-squid',
}

/** The agent glyph inside a tile — sprite <use> for the curated 50, sidecar
    recolor endpoint (white glyph) as the fallback for the rest. */
export function AgGlyph({ icon }: { icon: string }) {
  const sym = SPRITE_BY_FILE[icon]
  if (sym) return <svg className="ag-svg"><use href={`#${sym}`} /></svg>
  if (icon) return <img className="ag-svg" src={`${API}/assets/agent-icons/${encodeURIComponent(icon)}.svg?color=%23ffffff`} alt="" />
  return <svg className="ag-svg"><use href="#ag-wizard" /></svg>
}
