// Transient toast — ports behavior.js toast() onto the copied .toast styles.
let _tt: any = null
export function toast(msg: string) {
  let t = document.getElementById('toast')
  if (!t) {
    t = document.createElement('div')
    t.id = 'toast'
    t.className = 'toast'
    t.setAttribute('data-comp', 'toast')
    document.body.appendChild(t)
  }
  t.textContent = msg
  t.classList.add('show')
  clearTimeout(_tt)
  _tt = setTimeout(() => t!.classList.remove('show'), 2400)
}
