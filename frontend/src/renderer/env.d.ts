// Vite ambient declarations for the renderer tree.
declare module '*.css'
declare module '*.svg' {
  const src: string
  export default src
}
