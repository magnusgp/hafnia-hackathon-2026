(() => {
  const { D, $, $$, esc, hm, day, clock, MARK, occurrence: O, members, watchOf, watchState, lastResult, why, player, regionEditor, deriveLabel, connection, protoMark, span, drawers } = OR;
  const app = $('#app');
  let pl = null, dec = { verdict: null, note: '', watched: false, recorded: false }, ed = null;
  const frame = (name) => `generated/media/camera-${name}.jpg`;
  const RAISE = { disagreement: 'Hafnia finds nothing, vision finds a person', corroborated: 'Both find it', unresolved: 'Hafnia cannot decide, vision finds a person',
    hafnia_only: 'Hafnia finds it, vision does not', clear: 'Neither finds anything', inconclusive: 'Hafnia gives no usable answer' };
  const PLAY = '<svg viewBox="0 0 14 14"><path d="M2 1v12l10-6z"/></svg>', PAUSE = '<svg viewBox="0 0 14 14"><path d="M2 1h3.5v12H2zM8.5 1H12v12H8.5z"/></svg>';

  function shell(view, body) {
    app.innerHTML = `<header class="top"><div class="wordmark"><img src="${MARK}" alt="">Ortru</div>
      <nav><a href="#/exceptions" ${view === 'ex' ? 'aria-current="page"' : ''}>Exceptions</a><a href="#/watches" ${view === 'wa' ? 'aria-current="page"' : ''}>Watches</a></nav>
      <div class="conn"><button data-act="conn" aria-haspopup="true"><span class="dot ${D.gateway.available ? 'green' : 'red'}"></span>Setup</button><div class="pop" id="pop">${connection()}</div></div></header><main>${body}</main>`;
    protoMark();
  }

  /* ---------- exceptions ---------- */
  function exceptions(drawer) {
    const ev = (cls, start, end, t, when, p) => `<li class="ev ${cls}" data-seek="${start}" data-start="${start}" data-end="${end}"><span class="mk"></span><div><b>${t}</b><span class="when">${when}</span><p>${p}</p></div></li>`;
    const body = `<div class="strip"><button class="occ" aria-current="true"><img src="generated/media/frame-09.jpg" alt=""><span><b>${esc(O.title)}</b><small><span class="dot green"></span>Alerted · seen ${members.length} times</small><small><span class="dot amber"></span>No operator review yet</small></span></button>
        <details class="earlier"><summary>Earlier (${D.records.length})</summary><div class="menu">${D.records.map((r) => `<div><b style="font-weight:500">${esc(r.title || 'Station platform')}</b><small>${day(r.at)} ${hm(r.at)} UTC · alarm verified</small></div>`).join('')}</div></details></div>
      <div class="work"><section class="media"><h1>${esc(O.title)}</h1>
        <p class="lede">${esc(why.disagreement)} ${esc(O.watchName)}.</p>
        <div class="stagebox stage"><div id="pl"></div>
          <div class="xport"><button class="play" data-act="play" aria-label="Play">${PLAY}</button><span class="time" id="tc">0:00.0 <i>/ ${clock(O.duration)}</i></span>
            <div class="scrub" id="scrub" aria-label="Clip timeline"><div class="st h"><i></i></div><div class="st v"><i style="left:${(O.vision.from / O.duration) * 100}%;width:${((O.vision.to - O.vision.from + 0.5) / O.duration) * 100}%"></i></div><div class="st r"><i style="left:${(O.review.from / O.duration) * 100}%;width:${((O.review.to - O.review.from) / O.duration) * 100}%"></i></div><div class="head" id="head"></div></div>
            <span class="tog"><label><input type="checkbox" data-tog="region" checked>Region</label><label><input type="checkbox" data-tog="box" checked>Detection</label></span></div></div>
        <div class="seen"><span>Seen ${members.length} times on ${day(O.first)}:</span>${members.map((m) => `<button class="c" data-go="#/exceptions/history">${hm(m.interval[0])}</button>`).join('')}<span class="sp"><button class="link" data-go="#/exceptions/history">All observations</button><button class="link" data-go="#/exceptions/evidence">Evidence details</button></span></div></section>
      <aside class="side">
        <div class="alarmline"><span class="dot green"></span>Alarm ${O.alert.localId} in XProtect · verified in Smart Client<button class="btn" data-go="#/exceptions/alert">Details</button></div>
        <ol class="story">
          ${ev('hafnia', 0, O.duration, 'Hafnia: no entry seen', 'whole clip', 'AI footage review. Asked about someone entering the track area, it reported that it could not see that area.')}
          ${ev('vision', O.vision.from, O.vision.to + 0.5, 'Vision: person at the region', '0:04.4–0:10.4', 'Measures closeness to the outlined area, not entry.')}
          ${ev('review', O.review.from, O.review.to, 'Review: steps down onto the track bed', '0:06.4–0:07.9', `${esc(O.review.who)}. Not a detector output.`)}</ol>
        <form class="decide" id="decide" onsubmit="return false"><h2>Is a person on the track area?</h2>
          <div class="seg" role="group" aria-label="Review"><button data-v="visible" aria-pressed="false">Yes</button><button data-v="not_visible" aria-pressed="false">No</button><button data-v="unclear" aria-pressed="false">Can’t tell</button></div>
          <label class="field"><span class="sr">Note</span><textarea id="note" placeholder="What did you see? (required)"></textarea></label>
          <div class="act"><label class="check"><input type="checkbox" id="watched">I watched the relevant footage</label><button class="btn primary" id="rec" disabled>Record review</button></div>
          <div class="done" id="done" hidden></div></form></aside></div>${drawers(drawer)}`;
    shell('ex', body);
    pl = player($('#pl'), { onTime: tick });
    pl.v.addEventListener('loadedmetadata', () => { if (/seek=/.test(location.hash)) pl.seek(+location.hash.split('seek=')[1]); });
    syncDecide();
  }
  function tick(t, playing) {
    const tc = $('#tc'); if (!tc) return;
    tc.firstChild.nodeValue = clock(t) + ' ';
    $('#head').style.left = `${(t / O.duration) * 100}%`;
    $('.play', app).innerHTML = playing ? PAUSE : PLAY;
    $$('.ev').forEach((e) => e.classList.toggle('on', t >= +e.dataset.start && t <= +e.dataset.end));
  }
  function syncDecide() {
    const f = $('#decide'); if (!f) return;
    if ($('#note').value !== dec.note) $('#note').value = dec.note;
    $('#watched').checked = dec.watched;
    $$('.seg button', f).forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.v === dec.verdict)));
    $('#rec').disabled = !(dec.verdict && dec.note.trim() && dec.watched);
    const d = $('#done'); d.hidden = !dec.recorded;
    d.textContent = dec.recorded ? 'Prototype: this would be saved as revision 3 of the review history. Nothing was saved.' : '';
  }

  /* ---------- watches ---------- */
  function watches() {
    shell('wa', `<div class="wrap"><div class="head"><h1>Watches</h1><button class="btn primary" data-go="#/watch/new">New Watch</button></div><ul class="wl">${D.watches.map((w) => {
      const s = watchState(w), r = lastResult(w);
      return `<li data-href="#/watch/${w.id}"><img src="${frame(w.config.camera.name)}" alt=""><div><b>${esc(w.config.name.split(':')[0])}</b><small>${esc(w.config.hafnia.condition)}</small><small>${esc(w.config.camera.name)}</small></div>
        <div class="stt"><span class="${s.dot}"></span><div>${s.label}${s.note ? `<small>${s.note}</small>` : ''}</div></div>
        <div class="res">${esc(r.text)}<small>${r.at} UTC${r.exception ? ' · <a href="#/exceptions">Open</a>' : ''}</small></div></li>`; }).join('')}</ul></div>`);
  }

  /* ---------- watch editor (one decision at a time) ---------- */
  function editor(id, q) {
    const w = id === 'new' ? null : watchOf(id), c = w?.config;
    ed = { cam: q.cam || c?.camera.name || null, question: c?.hafnia.instruction ?? q.q ?? '', label: c?.hafnia.condition || '', edited: !!c, local: true, region: c?.region.polygon || null, every: c?.schedule.intervalMinutes || 15,
      step: +(q.step || 1), raise: new Set(c?.policy.raiseOn || ['disagreement', 'corroborated', 'unresolved']), perDay: c?.quota.perDay || 12, window: c?.schedule.windowSeconds || 15,
      margin: c?.schedule.marginSeconds || 90, id, failed: false, drawing: false, seen: new Set(w ? [1, 2, 3] : [1]), name: w ? c.name.split(':')[0] : 'New Watch' };
    if (q.region) ed.region = watchOf('w-c95bfc089f').config.region.polygon; // a state of the concept: the operator has outlined the area
    if (!ed.edited && ed.question) ed.label = deriveLabel(ed.question);
    shell('wa', `<div class="wiz"><div class="tabs" id="tabs"></div><div class="wgrid"><section class="cv" id="cv"></section><aside class="pane" id="pane"></aside></div></div>`);
    canvas(); pane();
  }
  const camObj = () => D.cameras.find((c) => c.name === ed.cam);
  function canvas() {
    const cam = camObj(), host = $('#cv');
    let top;
    if (!cam) top = `<div class="noframe"><div>Choose a camera below. Its current frame appears here and you outline the area Ortru should watch.</div></div>`;
    else if (!cam.hasSnapshot) top = `<div class="noframe"><div><b>No frame yet for ${esc(cam.name)}</b><div style="color:var(--stage-ink-2)">Ortru needs one frame to show what it will observe.</div></div><button class="btn" data-act="getframe">Get a frame</button>${ed.failed ? '<div class="fail">Could not get a frame from XProtect. Check that the camera is recording, then try again. (Design of the failure state: acquisition is not connected here.)</div>' : ''}</div>`;
    else top = `<div class="frame stage"><div id="re"></div></div><div class="legend" id="legend"></div>`;
    const film = ed.step === 1 ? `<div class="film" role="group" aria-label="Cameras">${D.cameras.map((c) => `<button data-cam="${esc(c.name)}" aria-pressed="${c.name === ed.cam}"><div class="t">${c.hasSnapshot ? `<img src="${frame(c.name)}" alt="">` : 'No frame yet'}</div><span title="${esc(c.name)}">${esc(c.name)}</span></button>`).join('')}</div>` : '';
    host.className = ed.step === 1 ? 'cv pick' : 'cv';
    host.innerHTML = top + film;
    if (cam?.hasSnapshot) ed.re = regionEditor($('#re'), frame(cam.name), ed.region, (pts, drawing) => { ed.region = pts.length ? pts : null; ed.drawing = drawing; legend(); });
  }
  function legend() {
    const l = $('#legend'); if (!l) return;
    if (ed.step === 1) { l.innerHTML = '<span>This is the frame Ortru will observe. Choose another camera, or continue.</span>'; return; }
    l.innerHTML = !ed.local ? `<span>Ortru watches the whole frame, every ${ed.every} min for ${ed.window}&nbsp;s.</span>`
      : ed.drawing ? '<span>Click the image to outline the area Ortru should watch. Click the first point to close it.</span>'
      : `<span>Ortru watches the outlined area, every ${ed.every} min for ${ed.window}&nbsp;s.</span><button class="btn quiet" data-act="redraw">Redraw</button><span class="muted" title="Double-click a point to remove it">Drag points to adjust</span>`;
  }
  function pane() {
    const cam = camObj(), al = cam?.alarm, cap = D.capabilities.find((x) => x.available);
    ed.seen.add(ed.step);
    const names = ['Camera', 'Question', 'Monitoring'];
    $('#tabs').innerHTML = `<h1>${esc(ed.name)}</h1>` + names.map((n, i) => `${i ? '<span class="sep"></span>' : ''}<button data-step="${i + 1}" ${ed.step === i + 1 ? 'aria-current="step"' : ''} class="${ed.step !== i + 1 && ed.seen.has(i + 1) ? 'done' : ''}"><span class="n">${ed.step !== i + 1 && ed.seen.has(i + 1) ? '✓' : i + 1}</span>${n}</button>`).join('');
    let h;
    if (ed.step === 1) h = `<h2>Which camera?</h2><p class="hint">Pick the camera Ortru should watch. The big picture shows what it will observe.</p>
      ${cam ? `<div class="sum"><div><b>Camera</b>${esc(cam.name)}</div><div><b>Frame</b>${cam.hasSnapshot ? 'Available' : 'None yet'}</div></div>` : ''}
      <div class="nav"><span></span><div class="r"><button class="btn primary" data-step="2" ${cam?.hasSnapshot ? '' : 'disabled'}>Next: question</button></div></div>`;
    else if (ed.step === 2) h = `<h2>What should Ortru look for?</h2>
      <label class="field"><span class="sr">Question</span><textarea id="q" rows="4" placeholder="Describe the event in a sentence">${esc(ed.question)}</textarea></label>
      <label class="field"><span>Shown as</span><input type="text" id="lab" value="${esc(ed.label)}"><small class="muted">Taken from your question. Edit it if it reads wrong.</small></label>
      <label class="check"><input type="checkbox" id="loc" ${ed.local ? 'checked' : ''}><span><b>Also check with ${esc(cap.label.toLowerCase())}</b><br><span class="muted">Vision measures closeness to the area you outline. It does not confirm entry.</span></span></label>
      <div class="nav"><button class="btn" data-step="1">Back</button><div class="r"><button class="btn primary" data-step="3">Next: monitoring</button></div></div>`;
    else h = `<h2>When should it raise an exception?</h2>
      <div>Raise an exception when:<ul class="plain">${[...ed.raise].map((k) => `<li>${RAISE[k]}</li>`).join('')}</ul></div>
      <label class="field"><span>Check every</span><select id="every">${[5, 15, 30, 60].map((m) => `<option ${+ed.every === m ? 'selected' : ''} value="${m}">${m} minutes</option>`).join('')}</select></label>
      <div class="hint">${al ? `An exception can alert XProtect: <b>${esc(al)}</b>.` : 'No XProtect alarm is set up for this camera. Exceptions stay in Ortru.'}</div>
      <details class="adv"><summary>Advanced</summary><div class="g"><div class="two"><label class="field"><span>Requests per day</span><input type="text" value="${ed.perDay}"></label><label class="field"><span>Clip length (s)</span><input type="text" value="${ed.window}"></label></div>
        <label class="field"><span>Margin after the clip (s)</span><input type="text" value="${ed.margin}"></label>
        <div class="field"><span>Raise an exception when</span>${Object.entries(RAISE).map(([k, t]) => `<label class="check"><input type="checkbox" data-raise="${k}" ${ed.raise.has(k) ? 'checked' : ''}>${t}</label>`).join('')}</div>
        <div class="hint">Hafnia answers with outcome, evidence, timing and limitations.</div></div></details>
      <div class="nav"><button class="btn" data-step="2">Back</button><div class="r"><button class="btn" data-act="savep">Save paused</button><button class="btn primary" disabled>Activate</button></div></div>
      <div class="hint" id="msg">${D.gateway.available ? '' : 'Activating needs Hafnia sign-in. Open Setup at the top right.'}</div>`;
    $('#pane').innerHTML = h;
    legend();
  }

  /* ---------- events ---------- */
  document.addEventListener('click', (e) => {
    const t = (s) => e.target.closest(s);
    if (t('[data-act="conn"]')) return $('#pop').classList.toggle('open');
    if ($('#pop')?.classList.contains('open') && !t('.pop')) $('#pop').classList.remove('open');
    let el;
    if ((el = t('[data-go]'))) location.hash = el.dataset.go;
    else if ((el = t('[data-href]')) && !t('a')) location.hash = el.dataset.href;
    else if ((el = t('[data-seek]'))) { pl.seek(+el.dataset.seek); pl.v.pause(); }
    else if (t('[data-act="play"]')) pl.toggle();
    else if ((el = t('.seg button'))) { dec.verdict = el.dataset.v; dec.recorded = false; syncDecide(); }
    else if (t('#rec')) { dec.recorded = true; syncDecide(); }
    else if ((el = t('[data-step]'))) { if (el.disabled) return; ed.step = +el.dataset.step; canvas(); pane(); }
    else if ((el = t('[data-cam]'))) { ed.cam = el.dataset.cam; ed.failed = false; ed.region = null; canvas(); pane(); }
    else if (t('[data-act="redraw"]')) ed.re.redraw();
    else if (t('[data-act="getframe"]')) { ed.failed = true; canvas(); }
    else if (t('[data-act="savep"]')) $('#msg').textContent = 'Prototype: a paused Watch would be saved here. Nothing was saved.';
  });
  document.addEventListener('input', (e) => {
    const id = e.target.id;
    if (id === 'note') { dec.note = e.target.value; dec.recorded = false; syncDecide(); }
    else if (id === 'q') { ed.question = e.target.value; if (!ed.edited) { ed.label = deriveLabel(ed.question); $('#lab').value = ed.label; } }
    else if (id === 'lab') { ed.edited = true; ed.label = e.target.value; }
  });
  document.addEventListener('change', (e) => {
    const id = e.target.id;
    if (id === 'watched') { dec.watched = e.target.checked; dec.recorded = false; syncDecide(); }
    else if (e.target.dataset.tog) { pl.show[e.target.dataset.tog] = e.target.checked; pl.redraw(); }
    else if (id === 'every') { ed.every = +e.target.value; legend(); }
    else if (id === 'loc') { ed.local = e.target.checked; legend(); }
    else if (e.target.dataset.raise) { e.target.checked ? ed.raise.add(e.target.dataset.raise) : ed.raise.delete(e.target.dataset.raise); }
  });
  document.addEventListener('keydown', (e) => {
    if (!pl || !$('.work') || /INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return;
    if (e.key === ' ') { e.preventDefault(); pl.toggle(); } else if (e.key === 'ArrowRight') pl.step(0.5); else if (e.key === 'ArrowLeft') pl.step(-0.5);
  });
  let down = false;
  const scrubTo = (e) => { const r = $('#scrub').getBoundingClientRect(); pl.seek(((e.clientX - r.left) / r.width) * O.duration); };
  document.addEventListener('pointerdown', (e) => { if (e.target.closest('#scrub')) { down = true; pl.v.pause(); scrubTo(e); } });
  document.addEventListener('pointermove', (e) => { if (down) scrubTo(e); });
  document.addEventListener('pointerup', () => { down = false; });

  function route() {
    const [path, qs] = location.hash.slice(1).split('?'); const q = Object.fromEntries(new URLSearchParams(qs || ''));
    const p = path.split('/').filter(Boolean);
    if (!p.length || p[0] === 'exceptions') exceptions(p[1]);
    else if (p[0] === 'watches') watches();
    else if (p[0] === 'watch') editor(p[1] || 'new', q);
  }
  addEventListener('hashchange', () => {
    if (location.hash.startsWith('#/exceptions') && pl && $('.work')) { const keep = pl.v.currentTime, was = !pl.v.paused; route(); pl.v.addEventListener('loadedmetadata', () => { pl.seek(keep); if (was) pl.v.play(); }, { once: true }); } else route();
  });
  route();
})();
