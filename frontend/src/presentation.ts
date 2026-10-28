import '@fontsource-variable/manrope'
let current = Math.max(1, Math.min(3, Number(location.hash.replace('#slide-', '')) || 1))
function show(index: number) {
  current = Math.max(1, Math.min(3, index))
  document.querySelectorAll('.slide').forEach((slide, i) => slide.classList.toggle('active', i === current - 1))
  document.querySelector('#count')!.textContent = `0${current} / 03`
  ;(document.querySelector('#previous') as HTMLButtonElement).disabled = current === 1
  ;(document.querySelector('#next') as HTMLButtonElement).disabled = current === 3
  history.replaceState(null, '', `#slide-${current}`)
}
document.querySelector('#previous')!.addEventListener('click', () => show(current - 1))
document.querySelector('#next')!.addEventListener('click', () => show(current + 1))
document.addEventListener('keydown', event => { if (['ArrowRight', ' ', 'PageDown'].includes(event.key)) { event.preventDefault(); show(current + 1) } if (['ArrowLeft', 'PageUp'].includes(event.key)) { event.preventDefault(); show(current - 1) } })
window.addEventListener('hashchange', () => show(Number(location.hash.replace('#slide-', '')) || 1))
show(current)
