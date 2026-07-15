// Tailwind config — mirrors the inline `tailwind.config` block in design/mockup.html
// (the mockup runs the Tailwind CDN; the renderer compiles the same theme at build
// time so the mockup's utility classes render identically). Values resolve to the
// tokens in design/tokens.css via var().
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ['./src/renderer/**/*.{ts,tsx,html}'],
  theme: {
    extend: {
      fontFamily: { sans: ['Archivo', 'sans-serif'], mono: ['JetBrains Mono', 'monospace'] },
      fontWeight: { base: '500', heading: '800' },
      colors: {
        background: 'var(--background)', 'secondary-background': 'var(--secondary-background)',
        foreground: 'var(--foreground)', main: 'var(--main)', 'main-foreground': 'var(--main-foreground)',
        border: 'var(--border)', ring: 'var(--ring)', overlay: 'var(--overlay)',
        surface3: 'var(--surface-3)', muted: 'var(--muted)', 'muted-2': 'var(--muted-2)',
        secondary: 'var(--secondary)', 'secondary-foreground': 'var(--secondary-foreground)', select: 'var(--select)',
        'main-dim': 'var(--main-dim)', 'secondary-dim': 'var(--secondary-dim)',
        success: 'var(--success)', warning: 'var(--warning)', danger: 'var(--danger)',
        agent: {
          crimson: 'var(--ag-crimson)', emerald: 'var(--ag-emerald)', cobalt: 'var(--ag-cobalt)', amber: 'var(--ag-amber)', fern: 'var(--ag-fern)',
          violet: 'var(--ag-violet)', vermilion: 'var(--ag-vermilion)', cyan: 'var(--ag-cyan)', gold: 'var(--ag-gold)', citron: 'var(--ag-citron)',
          orchid: 'var(--ag-orchid)', azure: 'var(--ag-azure)', teal: 'var(--ag-teal)', lime: 'var(--ag-lime)', indigo: 'var(--ag-indigo)', magenta: 'var(--ag-magenta)',
        },
      },
      borderRadius: { base: 'var(--radius-base)' },
      boxShadow: { shadow: 'var(--shadow)', shadowsm: 'var(--shadow-sm)' },
      spacing: { boxShadowX: '4px', boxShadowY: '4px', reverseBoxShadowX: '-4px', reverseBoxShadowY: '-4px' },
    },
  },
  plugins: [],
}
