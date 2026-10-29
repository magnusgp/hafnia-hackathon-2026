// Ortru deck: keyboard navigation with in-slide steps, full screen, notes dock, a synchronized speaker window and an overview.
(() => {
  const slides = [...document.querySelectorAll('.slide')];
  const params = new URLSearchParams(location.search);
  const channel = 'BroadcastChannel' in window ? new BroadcastChannel('ortru-deck') : null;
  const stepsOf = (s) => [...s.querySelectorAll('[data-step]')];
  const notesOf = (s) => (s.querySelector('.notes')?.textContent || '').trim();
  let i = 0, shown = 0, started = Date.now();

  // missing screenshots (they are private and not in the repository) degrade to a caption
  document.querySelectorAll('.shot img').forEach((img) => {
    const miss = () => { img.hidden = true; img.closest('.shot').classList.add('missing'); };
    img.addEventListener('error', miss);
    if (img.complete && img.naturalWidth === 0) miss();
  });

  function render() {
    slides.forEach((s, k) => { s.classList.toggle('on', k === i); s.classList.toggle('past', k < i); });
    stepsOf(slides[i]).forEach((el, k) => el.classList.toggle('shown', k < shown));
    document.getElementById('count').textContent = `${i + 1} / ${slides.length}`;
    const dock = document.getElementById('dock');
    dock.innerHTML = `<small>Speaker notes · slide ${i + 1}</small>${notesOf(slides[i])}`;
    document.title = `${slides[i].dataset.title || 'Ortru'} · Ortru`;
    history.replaceState(null, '', `#${i + 1}`);
    channel?.postMessage({ i, shown });
  }
  function go(n, reveal = false) {
    i = Math.max(0, Math.min(slides.length - 1, n));
    shown = reveal ? stepsOf(slides[i]).length : 0;
    render();
  }
  function next() {
    if (shown < stepsOf(slides[i]).length) { shown++; render(); } else if (i < slides.length - 1) go(i + 1);
  }
  function back() {
    if (shown > 0) { shown--; render(); } else if (i > 0) go(i - 1, true);
  }

  if (params.get('view') === 'notes') {
    // speaker window: notes, next slide, elapsed time; follows the main window
    document.body.className = 'notes-view';
    document.getElementById('deck').style.display = 'none';
    document.getElementById('hud').style.display = 'none';
    const d = document.getElementById('dock');
    d.hidden = false; d.style.cssText = 'position:static;max-height:none;border:0;padding:4vh 6vw;font-size:3vh';
    const timer = document.createElement('div');
    timer.style.cssText = 'position:fixed;right:3vw;top:2vh;font:400 3vh IBM Plex Mono,monospace';
    document.body.append(timer);
    setInterval(() => { const s = Math.floor((Date.now() - started) / 1000); timer.textContent = `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`; }, 500);
    channel?.addEventListener('message', (e) => {
      i = e.data.i; shown = e.data.shown;
      const nxt = slides[i + 1];
      d.innerHTML = `<small>Slide ${i + 1} of ${slides.length} · ${slides[i].dataset.title}</small><p>${notesOf(slides[i])}</p>`
        + (nxt ? `<small style="margin-top:4vh">Next</small><p><b>${nxt.dataset.title}</b></p>` : '<small style="margin-top:4vh">Last slide</small>');
    });
    return;
  }

  document.addEventListener('keydown', (e) => {
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const k = e.key;
    if (['ArrowRight', ' ', 'PageDown', 'Enter'].includes(k)) { e.preventDefault(); next(); }
    else if (['ArrowLeft', 'PageUp', 'Backspace'].includes(k)) { e.preventDefault(); back(); }
    else if (k === 'Home') go(0);
    else if (k === 'End') go(slides.length - 1, true);
    else if (k === 'f' || k === 'F') { document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen?.(); }
    else if (k === 'n' || k === 'N') { const d = document.getElementById('dock'); d.hidden = !d.hidden; }
    else if (k === 'g' || k === 'G') { document.body.classList.toggle('overview'); }
    else if (k === 's' || k === 'S') { window.open(`${location.pathname}?view=notes`, 'ortru-notes', 'width=900,height=700'); render(); }
    else if (/^[1-9]$/.test(k)) go(Number(k) - 1);
    else if (k === 'Escape') document.body.classList.remove('overview');
  });
  slides.forEach((s, k) => s.addEventListener('click', () => { if (document.body.classList.contains('overview')) { document.body.classList.remove('overview'); go(k); } }));
  document.getElementById('deck').addEventListener('click', (e) => { if (!document.body.classList.contains('overview') && !e.target.closest('a')) next(); });
  go(Math.max(0, Math.min(slides.length - 1, (parseInt(location.hash.slice(1), 10) || 1) - 1)));
})();
