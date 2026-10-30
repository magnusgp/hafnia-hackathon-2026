(() => {
  const { D, $, $$, esc, hm, day, clock, MARK, occurrence: O, members, watchOf, watchState, lastResult, why, player, regionEditor, deriveLabel, connection, protoMark, rev2, drawers } = OR;
  const app = $('#app');
  let pl = null, dec = { verdict: null, note: '', watched: false, recorded: false }, ed = null;
  const frame = (name) => `generated/media/camera-${name}.jpg`;
  const thumb = 'generated/media/frame-09.jpg';
  const span = OR.span;
  const ICON = {
    ex: '<svg viewBox="0 0 24 24"><path d="M12 3 2.5 20h19z"/><path d="M12 10v4.5M12 17.2v.1"/></svg>',
    wa: '<svg viewBox="0 0 24 24"><path d="M2 12s3.7-6.5 10-6.5S22 12 22 12s-3.7 6.5-10 6.5S2 12 2 12z"/><circle cx="12" cy="12" r="3"/></svg>',
  };
  const RAISE = { disagreement: 'Hafnia finds nothing, vision finds a person', corroborated: 'Both find it', unresolved: 'Hafnia cannot decide, vision finds a person',
    hafnia_only: 'Hafnia finds it, vision does not', clear: 'Neither finds anything', inconclusive: 'Hafnia gives no usable answer' };

  /* ---------- shell ---------- */
  function shell(view, body) {
    app.innerHTML = `<nav class="rail"><div class="wordmark"><img src="${MARK}" alt="">Ortru</div>
      <a class="nav" href="#/exceptions" ${view === 'ex' ? 'aria-current="page"' : ''}>${ICON.ex}Exceptions</a>
      <a class="nav" href="#/watches" ${view === 'wa' ? 'aria-current="page"' : ''}>${ICON.wa}Watches</a>
      <div class="conn"><button data-act="conn" aria-haspopup="true"><span class="dot ${D.gateway.available ? 'green' : 'red'}"></span>${D.gateway.available ? 'Connected' : 'Setup'}</button>
      <div class="pop" id="pop">${connection()}</div></div></nav><main>${body}</main>`;
    protoMark();
  }

  /* ---------- exceptions ---------- */
  function exceptions(drawer) {
    const list = `<aside class="list"><h2>Exceptions</h2>
      <div class="item" aria-current="true" data-href="#/exceptions"><img src="${thumb}" alt="">
        <div><b>${esc(O.title)}</b><span class="when">${esc(O.watchName)} · ${members.length} observations</span></div>
        <div class="st"><span><span class="dot green"></span>Alerted · alarm ${O.alert.localId} verified</span>
        <span><span class="dot amber"></span>No operator review yet</span>
        <span class="muted">${day(O.first)}, ${span(O.first, O.last)} UTC</span></div></div>
      <div class="sub">Earlier</div>
      ${D.records.map((r) => `<div class="item old"><div><b>${esc(r.title || 'Station platform')}</b><span class="when">${day(r.at)} ${hm(r.at)} UTC · ${r.smartClient === 'verified' ? 'alarm verified' : 'sent'}</span></div></div>`).join('')}
    </aside>`;
    const claims = `<div class="claims">
      <button class="claim" data-seek="0"><span class="dot blue"></span><span><b>Hafnia: no entry seen</b><span class="by">AI footage review of the whole clip. The track area is not in view.</span></span></button>
      <button class="claim" data-seek="${O.vision.from}"><span class="dot violet"></span><span><b>Vision: at the region, 0:04–0:10</b><span class="by">Measures closeness to the drawn area, not entry.</span></span></button>
      <button class="claim" data-seek="${O.review.from}"><span class="dot amber"></span><span><b>Review: steps down at 0:06</b><span class="by">${esc(O.review.who)}, revision ${O.review.rev}. Not a detector output.</span></span></button></div>`;
    const body = `<div class="ex">${list}<section class="inv">
      <header class="inv-head"><div><h1>${esc(O.title)}</h1><div class="meta">${esc(O.watchName)} · seen ${members.length} times · ${day(O.first)}, ${span(O.first, O.last)} UTC</div></div>
        <div class="sp"><button class="btn" data-go="#/exceptions/history">History (${members.length})</button><button class="btn" data-go="#/exceptions/evidence">Evidence</button></div></header>
      <div class="inv-body"><div class="left">
        <div class="stagebox stage"><div id="pl"></div>
          <div class="xport"><button class="play" data-act="play" aria-label="Play"><svg viewBox="0 0 14 14"><path d="M2 1v12l10-6z"/></svg></button>
            <span class="time" id="tc">0:00.0 <i>/ ${clock(O.duration)}</i></span>
            <button class="jump" data-seek="${O.vision.from}"><span class="dot violet"></span>Person at region</button>
            <button class="jump" data-seek="${O.review.from}"><span class="dot amber"></span>Steps down</button>
            <span class="tog"><label><input type="checkbox" data-tog="region" checked>Region</label><label><input type="checkbox" data-tog="box" checked>Detection</label></span></div>
          <div class="tl" id="tl">${timeline()}</div></div>
        <form class="decide" id="decide" onsubmit="return false"><h2>Is a person on the track area?<span class="muted" style="font:400 12.5px var(--body)">Your review, added to the earlier AI review</span></h2>
          <div class="seg" role="group" aria-label="Review"><button data-v="visible" aria-pressed="false">Yes</button><button data-v="not_visible" aria-pressed="false">No</button><button data-v="unclear" aria-pressed="false">Can’t tell</button></div>
          <label class="field note"><span class="sr">Note</span><textarea id="note" placeholder="What did you see? (required)"></textarea></label>
          <div class="act"><label class="check"><input type="checkbox" id="watched">I watched the relevant footage</label><button class="btn primary" id="rec" disabled>Record review</button></div>
          <div class="done" id="done" hidden></div></form>
      </div>
      <aside class="right"><div class="raised">${esc(why.disagreement)}</div>
        <div class="q"><b>Watch asks</b>${esc(O.question)}</div>${claims}
        <div class="alert"><div class="l1"><span class="dot green"></span>Alarm ${O.alert.localId} in XProtect</div>
          <div class="l2">Sent ${day(O.alert.sent)} ${hm(O.alert.sent)} UTC · verified in Smart Client ${day(O.alert.verifiedOn)}</div>
          <div><button class="btn quiet" style="padding-left:0" data-go="#/exceptions/alert">Alert details</button></div></div></aside></div></section></div>${drawers(drawer)}`;
    shell('ex', body);
    pl = player($('#pl'), { onTime: tick });
    pl.v.addEventListener('loadedmetadata', () => { if (/seek=/.test(location.hash)) pl.seek(+location.hash.split('seek=')[1]); });
    syncDecide();
  }
  function timeline() {
    const pct = (s) => (s / O.duration) * 100;
    const ticks = O.samples.map((s) => `<i class="tick" style="left:${pct(s.mediaTime)}%"></i>`).join('');
    const rule = [0, 3, 6, 9, 12].map((s) => `<span style="left:${pct(s)}%">${s}s</span>`).join('');
    return `<div class="rule">${rule}</div>
      <div class="row"><div class="bar hafnia" style="left:0;right:0">Hafnia · no entry seen</div></div>
      <div class="row">${ticks}<div class="bar vision" style="left:${pct(O.vision.from)}%;width:${pct(O.vision.to - O.vision.from + 0.5)}%">Person at the region</div></div>
      <div class="row"><div class="bar review" style="left:${pct(O.review.from)}%;width:${pct(O.review.to - O.review.from)}%"></div><div class="after" style="left:${pct(O.review.to)}%">Steps down, AI reviewer</div></div>
      <div class="head" id="head"></div>`;
  }
  function tick(t, playing) {
    const tc = $('#tc'); if (!tc) return;
    tc.firstChild.nodeValue = clock(t) + ' ';
    const tl = $('#tl'), head = $('#head'); const w = tl.clientWidth - 24;
    head.style.left = `${12 + (t / O.duration) * w}px`;
    $('.play', app).innerHTML = playing ? '<svg viewBox="0 0 14 14"><path d="M2 1h3.5v12H2zM8.5 1H12v12H8.5z"/></svg>' : '<svg viewBox="0 0 14 14"><path d="M2 1v12l10-6z"/></svg>';
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
    const rows = D.watches.map((w) => { const s = watchState(w), r = lastResult(w); return `<div class="r" data-href="#/watch/${w.id}">
      <div class="nm"><img src="${frame(w.config.camera.name)}" alt=""><div><b>${esc(w.config.name.split(':')[0])}</b><span>${esc(w.config.hafnia.condition)}</span></div></div>
      <div>${esc(w.config.camera.name)}</div>
      <div class="stt"><span class="${s.dot}"></span><div>${s.label}${s.note ? `<small>${s.note}</small>` : ''}</div></div>
      <div class="res">${esc(r.text)}<small>${r.at} UTC${r.exception ? ' · <a href="#/exceptions">Open</a>' : ''}</small></div></div>`; }).join('');
    shell('wa', `<div class="page"><div class="top"><h1>Watches</h1><a class="btn primary" style="display:inline-grid;place-items:center" href="#/watch/new">New Watch</a></div>
      <div class="wt"><div class="r hd"><span>Watch</span><span>Camera</span><span>State</span><span>Latest result</span></div>${rows}</div></div>`);
  }

  /* ---------- watch editor ---------- */
  function editor(id, q) {
    const w = id === 'new' ? null : watchOf(id), c = w?.config;
    ed = { cam: q.cam || c?.camera.name || null, question: c?.hafnia.instruction ?? q.q ?? '', label: c?.hafnia.condition || '', edited: !!c, local: true, region: c?.region.polygon || null,
      every: c?.schedule.intervalMinutes || 15, step: +(q.step || (w ? 1 : 1)), raise: new Set(c?.policy.raiseOn || ['disagreement', 'corroborated', 'unresolved']),
      perDay: c?.quota.perDay || 12, window: c?.schedule.windowSeconds || 15, margin: c?.schedule.marginSeconds || 90, id: id, failed: false, drawing: false, seen: new Set(w ? [1, 2, 3] : [1]) };
    if (q.region) ed.region = watchOf('w-c95bfc089f').config.region.polygon; // a state of the concept: the operator has outlined the area
    if (!ed.edited && ed.question) ed.label = deriveLabel(ed.question);
    shell('wa', `<div class="ed"><section class="canvas"><div class="top"><h1>${w ? esc(c.name.split(':')[0]) : 'New Watch'}</h1><span class="muted" id="sub"></span></div>
      <div id="canvas"></div></section><aside class="steps"><div class="scroll" id="steps"></div><div class="foot" id="foot"></div></aside></div>`);
    canvas(); steps();
  }
  const camObj = () => D.cameras.find((c) => c.name === ed.cam);
  function canvas() {
    const host = $('#canvas'), cam = camObj();
    if (!cam) { host.innerHTML = `<div class="noframe"><div>Choose a camera. Its current frame appears here and you outline the area Ortru should watch.</div></div>`; return; }
    if (!cam.hasSnapshot) {
      host.innerHTML = `<div class="noframe"><div><b>No frame yet for ${esc(cam.name)}</b><div class="muted" style="color:var(--stage-ink-2)">Ortru needs one frame to show what it will observe.</div></div>
        <button class="btn" data-act="getframe">Get a frame</button>${ed.failed ? '<div class="fail">Could not get a frame from XProtect. Check that the camera is recording, then try again. (Design of the failure state: acquisition is not connected here.)</div>' : ''}</div>`;
      return;
    }
    host.innerHTML = `<div class="frame stage"><div id="re"></div></div><div class="legend" id="legend"></div>`;
    ed.re = regionEditor($('#re'), frame(cam.name), ed.region, (pts, drawing) => { ed.region = pts.length ? pts : null; ed.drawing = drawing; legend(); });
  }
  function legend() {
    const l = $('#legend'); if (!l) return;
    l.innerHTML = !ed.local ? `<span>Ortru watches the whole frame, every ${ed.every} min for ${ed.window}&nbsp;s.</span>`
      : ed.drawing ? '<span>Click the image to outline the area Ortru should watch. Click the first point to close it.</span>'
      : `<span>Ortru watches the outlined area, every ${ed.every} min for ${ed.window}&nbsp;s.</span><button class="btn quiet" data-act="redraw">Redraw</button><span class="muted" title="Double-click a point to remove it">Drag points to adjust</span>`;
  }
  function steps() {
    const cam = camObj(), cap = D.capabilities.find((x) => x.available);
    const al = cam?.alarm;
    const sec = (n, title, val, body) => { const ok = ed.step !== n && ed.seen.has(n) && val; return `<div class="step ${ed.step === n ? 'open' : ''} ${ok ? 'done' : ''}"><button class="sh" data-step="${n}"><span class="n">${ok ? '✓' : n}</span><span class="t">${title}${ok ? `<span class="v">${esc(val)}</span>` : ''}</span><span></span></button>${ed.step === n ? `<div class="content">${body}</div>` : ''}</div>`; };
    ed.seen.add(ed.step);
    const s1 = `<div class="cams">${D.cameras.map((c) => `<button data-cam="${esc(c.name)}" aria-pressed="${c.name === ed.cam}"><span>${esc(c.name)}</span><small>${c.hasSnapshot ? '' : 'no frame yet'}</small></button>`).join('')}</div>`;
    const s2 = `<label class="field"><span>What should Ortru look for?</span><textarea id="q" rows="3" placeholder="Describe the event in a sentence">${esc(ed.question)}</textarea></label>
      <label class="field"><span>Shown as</span><input type="text" id="lab" value="${esc(ed.label)}"><small class="muted">Taken from your question. Edit it if it reads wrong.</small></label>
      <label class="check"><input type="checkbox" id="loc" ${ed.local ? 'checked' : ''}><span><b>Also check with ${esc(cap.label.toLowerCase())}</b><br><span class="muted">Vision measures closeness to the area you outline. It does not confirm entry.</span></span></label>`;
    const s3 = `<div>Raise an exception when <b>${[...ed.raise].map((k) => RAISE[k].toLowerCase()).join('</b>, or <b>')}</b>.</div>
      <label class="field"><span>Check every</span><select id="every">${[5, 15, 30, 60].map((m) => `<option ${+ed.every === m ? 'selected' : ''} value="${m}">${m} minutes</option>`).join('')}</select></label>
      <div class="muted">${al ? `Raising an exception can alert XProtect: <b>${esc(al)}</b>.` : 'No XProtect alarm is set up for this camera. Exceptions stay in Ortru.'}</div>
      <details class="adv"><summary>Advanced</summary><div class="g"><div class="two"><label class="field"><span>Requests per day</span><input type="text" value="${ed.perDay}"></label><label class="field"><span>Clip length (s)</span><input type="text" value="${ed.window}"></label></div>
        <label class="field"><span>Margin after the clip (s)</span><input type="text" value="${ed.margin}"></label>
        <div class="field"><span>Raise an exception when</span>${Object.entries(RAISE).map(([k, t]) => `<label class="check"><input type="checkbox" data-raise="${k}" ${ed.raise.has(k) ? 'checked' : ''}>${t}</label>`).join('')}</div>
        <div class="muted">Hafnia answers with outcome, evidence, timing and limitations.</div></div></details>`;
    $('#steps').innerHTML = sec(1, 'Camera', ed.cam, s1) + sec(2, 'Question and check', ed.label, s2) + sec(3, 'Trigger and monitoring', `Every ${ed.every} min`, s3);
    $('#foot').innerHTML = `<div class="row"><button class="btn" data-act="savep">Save paused</button><button class="btn primary" disabled>Activate</button></div><small>${D.gateway.available ? '' : 'Activating needs Hafnia sign-in. Open Setup in the left bar.'}</small>`;
    $('#sub').textContent = ed.id === 'new' ? 'Draft' : watchState(watchOf(ed.id)).label;
    legend();
  }

  /* ---------- events ---------- */
  document.addEventListener('click', (e) => {
    const t = (s) => e.target.closest(s);
    if (t('[data-act="conn"]')) return $('#pop').classList.toggle('open');
    if ($('#pop')?.classList.contains('open') && !t('.pop')) $('#pop').classList.remove('open');
    let el;
    if ((el = t('[data-go]'))) location.hash = el.dataset.go;
    else if ((el = t('[data-href]'))) location.hash = el.dataset.href;
    else if ((el = t('[data-seek]'))) { pl.seek(+el.dataset.seek); pl.v.pause(); }
    else if (t('[data-act="play"]')) pl.toggle();
    else if ((el = t('.seg button'))) { dec.verdict = el.dataset.v; dec.recorded = false; syncDecide(); }
    else if (t('#rec')) { dec.recorded = true; syncDecide(); }
    else if ((el = t('[data-step]'))) { ed.step = +el.dataset.step; steps(); }
    else if ((el = t('[data-cam]'))) { ed.cam = el.dataset.cam; ed.failed = false; ed.region = null; canvas(); steps(); ed.step = 1; }
    else if (t('[data-act="redraw"]')) ed.re.redraw();
    else if (t('[data-act="getframe"]')) { ed.failed = true; canvas(); }
    else if (t('[data-act="savep"]')) { $('#foot small').textContent = 'Prototype: a paused Watch would be saved here. Nothing was saved.'; }
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
    if (!pl || /INPUT|TEXTAREA|SELECT/.test(e.target.tagName)) return;
    if (e.key === ' ') { e.preventDefault(); pl.toggle(); } else if (e.key === 'ArrowRight') pl.step(0.5); else if (e.key === 'ArrowLeft') pl.step(-0.5);
  });
  const scrub = (e) => { const tl = $('#tl'); if (!tl || !e.target.closest('#tl')) return; const r = tl.getBoundingClientRect(); pl.seek(((e.clientX - r.left - 12) / (r.width - 24)) * O.duration); };
  let down = false;
  document.addEventListener('pointerdown', (e) => { if (e.target.closest('#tl')) { down = true; pl.v.pause(); scrub(e); } });
  document.addEventListener('pointermove', (e) => { if (down) { const tl = $('#tl'), r = tl.getBoundingClientRect(); pl.seek(((e.clientX - r.left - 12) / (r.width - 24)) * O.duration); } });
  document.addEventListener('pointerup', () => { down = false; });

  /* ---------- router ---------- */
  function route() {
    const [path, qs] = location.hash.slice(1).split('?'); const q = Object.fromEntries(new URLSearchParams(qs || ''));
    const p = path.split('/').filter(Boolean);
    if (!p.length || p[0] === 'exceptions') exceptions(p[1]);
    else if (p[0] === 'watches') watches();
    else if (p[0] === 'watch') editor(p[1] || 'new', q);
  }
  addEventListener('hashchange', () => { if (location.hash.startsWith('#/exceptions') && pl && $('.inv')) { const p = location.hash.slice(2).split('?')[0].split('/')[1]; const keep = pl.v.currentTime, was = !pl.v.paused; route(); pl.v.addEventListener('loadedmetadata', () => { pl.seek(keep); if (was) pl.v.play(); }, { once: true }); } else route(); });
  route();
})();
