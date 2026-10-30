/* Shared logic for both Gate 2 compositions: the occurrence model, what a Watch is effectively doing, the player,
   the region editor. Read-only by construction: this prototype has no request code at all. */
(() => {
  const D = window.ORTRU;
  const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => [...r.querySelectorAll(s)];
  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const hm = (iso) => iso.slice(11, 16);
  const day = (iso) => `${+iso.slice(8, 10)} ${MON[+iso.slice(5, 7) - 1]}`;
  const clock = (s) => `${Math.floor(s / 60)}:${(s % 60).toFixed(1).padStart(4, '0')}`;
  const MARK = '../../brand-kit/ortru/mark.svg';

  /* ---- one occurrence = the assessments that show the same visual event (server `event` key) ---- */
  const members = D.members;
  const sentMember = members.find((m) => m.id === D.sentId);
  const rev2 = D.history.revisions.find((r) => r.available);
  const watchOf = (id) => D.watches.find((w) => w.id === id);
  const occurrence = (() => {
    const w = watchOf(sentMember.watch.id);
    const dur = sentMember.video.duration;
    const samples = sentMember.vision.samples;
    const near = samples.filter((s) => s.near);
    return {
      id: sentMember.event, // the key the server computes for the group
      title: w.config.hafnia.condition,
      watchName: w.config.name.split(':')[0],
      watch: w, camera: sentMember.camera.name,
      question: w.config.hafnia.instruction.replace(/\.?$/, '.'),
      members, primary: sentMember, duration: dur, samples,
      first: members[0].interval[0], last: members[members.length - 1].interval[0],
      // three different claims, each with its own source and its own moment in the clip
      hafnia: { answer: 'No entry observed', limit: sentMember.hafnia.limitations, spans: [0, dur] },
      vision: { from: near[0].mediaTime, to: near[near.length - 1].mediaTime, trigger: sentMember.vision.trigger },
      // the AI reviewer's reading of the same footage (revision 2); the descent is NOT a detector output
      review: { from: 6.4, to: 7.9, who: sentMember.decision.reviewerLabel, rev: rev2.revision, at: rev2.at },
      alert: { localId: D.alarm.localId, sent: sentMember.native.transport?.at ?? '2026-10-29T15:08:38.506290+00:00', verifiedBy: D.alarm.verifiedBy, verifiedOn: D.alarm.verifiedOn },
    };
  })();

  /* ---- what a Watch is effectively doing: its own status AND whether Hafnia can answer ---- */
  function watchState(w) {
    const signedIn = D.gateway.available;
    if (w.status === 'disabled') return { key: 'off', label: 'Off', dot: 'dot', note: 'Switched off' };
    if (w.status === 'paused') return { key: 'paused', label: 'Paused', dot: 'dot amber', note: signedIn ? '' : 'Resuming waits for Hafnia sign-in' };
    if (!signedIn) return { key: 'waiting', label: 'Waiting for sign-in', dot: 'dot red', note: 'Checks cannot finish without Hafnia' };
    return { key: 'monitoring', label: 'Monitoring', dot: 'dot green', note: '' };
  }
  function lastResult(w) {
    const j = w.jobs[0];
    if (!j) return { tone: 'none', text: 'No checks yet', at: '' };
    const at = `${day(j.created)} ${hm(j.created)}`;
    if (j.state === 'completed') return { tone: 'raised', text: 'Raised an exception', at, exception: true };
    const why = j.error?.reason || '';
    if (/restart/i.test(why)) return { tone: 'failed', text: 'Could not check: the camera loop restarts inside the window', at };
    if (/12.{1,3}17/.test(why)) return { tone: 'failed', text: 'Hafnia step could not run: needs 12–17 s of footage, this camera gives 11 s', at };
    return { tone: 'failed', text: 'Check failed', at };
  }
  const why = {
    // why the review policy raised attention, per policy kind (the server's own label is not used: it names the two sources, not the claims)
    disagreement: 'Raised because vision placed a person at the region while Hafnia reported no entry. This Watch flags that combination.',
    corroborated: 'Hafnia and vision both point to it.',
    unresolved: 'Hafnia could not decide and vision found a person at the region.',
  };

  /* ---- player: one video, a clock everyone listens to ---- */
  function player(host, { onTime } = {}) {
    const polygon = occurrence.watch.config.region.polygon;
    host.innerHTML = `<div class="pv"><video muted playsinline preload="auto" src="generated/media/occurrence.mp4"></video>
      <svg class="ov" viewBox="0 0 832 480" preserveAspectRatio="none"><polygon class="region" points="${polygon.map(([x, y]) => `${x * 832},${y * 480}`).join(' ')}"/><g class="det"></g></svg></div>`;
    const v = $('video', host), det = $('.det', host), api = { v, show: { region: true, box: true } };
    const draw = (t) => {
      const s = occurrence.samples.reduce((a, b) => (Math.abs(b.mediaTime - t) < Math.abs(a.mediaTime - t) ? b : a));
      const ok = api.show.box && s.box && Math.abs(s.mediaTime - t) < 0.3;
      det.innerHTML = ok ? `<rect class="box" x="${s.box[0] * 832}" y="${s.box[1] * 480}" width="${(s.box[2] - s.box[0]) * 832}" height="${(s.box[3] - s.box[1]) * 480}"/>` : '';
      $('.region', host).style.display = api.show.region ? '' : 'none';
    };
    let raf;
    const tick = () => { fire(); if (!v.paused) raf = requestAnimationFrame(tick); };
    const fire = () => { draw(v.currentTime); onTime && onTime(v.currentTime, !v.paused); };
    v.addEventListener('play', () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(tick); });
    ['seeked', 'timeupdate', 'pause', 'loadedmetadata'].forEach((e) => v.addEventListener(e, fire));
    api.seek = (t) => { v.currentTime = Math.max(0, Math.min(occurrence.duration - 0.05, t)); };
    api.toggle = () => (v.paused ? v.play() : v.pause());
    api.step = (d) => { v.pause(); api.seek(v.currentTime + d); };
    api.redraw = fire;
    return api;
  }

  /* ---- region editor: the camera frame is the control ---- */
  function regionEditor(host, src, initial, onChange) {
    let pts = (initial || []).map((p) => [...p]), drawing = !pts.length, drag = -1;
    host.classList.add('redit');
    host.innerHTML = `<img alt="Camera frame" src="${src}"><svg viewBox="0 0 832 480" preserveAspectRatio="none"></svg>`;
    const svg = $('svg', host);
    const xy = (e) => { const r = svg.getBoundingClientRect(); return [Math.min(1, Math.max(0, (e.clientX - r.left) / r.width)), Math.min(1, Math.max(0, (e.clientY - r.top) / r.height))]; };
    const render = () => {
      host.classList.toggle('drawing', drawing);
      const P = pts.map(([x, y]) => `${x * 832},${y * 480}`).join(' ');
      svg.innerHTML = (pts.length > 1 ? `<${drawing ? 'polyline' : 'polygon'} class="poly" ${drawing ? 'style="fill:none"' : ''} points="${P}"/>` : '') +
        pts.map(([x, y], i) => `<ellipse class="handle" data-i="${i}" cx="${Math.min(824, Math.max(8, x * 832))}" cy="${Math.min(472, Math.max(8, y * 480))}" rx="7" ry="7"/>`).join('');
      onChange && onChange(pts.map((p) => p.map((n) => +n.toFixed(3))), drawing);
    };
    svg.addEventListener('pointerdown', (e) => {
      const h = e.target.closest('.handle');
      if (drawing && h && +h.dataset.i === 0 && pts.length >= 3) { drawing = false; return render(); }
      if (h) { drag = +h.dataset.i; svg.setPointerCapture(e.pointerId); return; }
      if (drawing) { pts.push(xy(e)); render(); }
    });
    svg.addEventListener('pointermove', (e) => { if (drag >= 0) { pts[drag] = xy(e); render(); } });
    svg.addEventListener('pointerup', () => { drag = -1; });
    svg.addEventListener('dblclick', (e) => { const h = e.target.closest('.handle'); if (h && pts.length > 3 && !drawing) { pts.splice(+h.dataset.i, 1); render(); } });
    render();
    return { redraw() { pts = []; drawing = true; render(); }, points: () => pts };
  }

  /* the visible-condition label offered from the question; the operator can correct it (the server does not derive it) */
  function deriveLabel(q) {
    let s = q.trim().split(/[.;]/)[0].split(/,| or /)[0].replace(/^(an?|the)\s+/i, '').trim();
    if (s.length > 72) { s = s.slice(0, 72); s = s.slice(0, s.lastIndexOf(' ')); }
    return s ? s[0].toUpperCase() + s.slice(1) : '';
  }

  /* connection: setup and transport facts live in one small place */
  function connection() {
    const g = D.gateway;
    return `<div class="conn-row"><span class="dot ${g.available ? 'green' : 'red'}"></span><div><b>Hafnia</b> ${g.available ? 'signed in' : 'not signed in'}
        <div class="muted">Recordings are read and local vision runs. Hafnia checks wait until you sign in.</div>
        ${g.available ? '' : '<div class="muted">Sign in from the launcher: <code>scripts\\ortru.ps1 -Gateway</code></div>'}</div></div>
      <div class="conn-row"><span class="dot ${D.native.sending ? 'green' : ''}"></span><div><b>XProtect Event Server</b> ${D.native.sending ? 'sending on' : 'sending off'}
        <div class="muted">${esc(D.native.target)}</div></div></div>
      <div class="conn-row"><span class="dot"></span><div><b>Hafnia requests today</b> ${D.budget.usedToday} of ${D.budget.global_}</div></div>`;
  }
  const protoMark = () => document.body.insertAdjacentHTML('beforeend', '<div class="proto-mark">Design prototype · nothing is saved or sent</div>');

  const span = (a, b) => `${hm(a)}–${hm(b)}`;
  const O = occurrence;
  function drawers(which, closeTo = '#/exceptions') {
    if (!which) return '';
    const head = (t) => `<div class="scrim" data-go="${closeTo}"></div><aside class="drawer" role="dialog" aria-label="${t}"><header><h2>${t}</h2><button class="btn quiet" data-go="${closeTo}">Close</button></header><div class="body">`;
    if (which === 'history') {
      const first = members[0];
      return head(`${members.length} observations of one event`) + `<p class="muted">The camera replays one short clip, so each scheduled check recorded the same footage again. All four assessments are kept with their own Hafnia request and decision.</p>
        <section>${members.map((m, i) => `<div class="obs"><b>${day(m.interval[0])} ${m.interval[0].slice(11, 19)}–${m.interval[1].slice(11, 19)} UTC</b><span>Hafnia: no entry seen</span>
          <span class="muted">${m.id === D.sentId ? `Reviewed by AI (revision ${rev2.revision}) · alarm ${O.alert.localId}` : 'No decision yet'}</span><span class="muted">${i ? (m.video.sha256 === members[0].video.sha256 ? 'Same footage as the first' : 'Different footage') : 'First observation'}</span></div>`).join('')}</section>
        <section><h3>Review revisions of the first observation</h3>${D.history.revisions.map((r) => r.available
          ? `<div class="obs"><b>Revision ${r.revision}</b><span class="muted">${day(r.at)} ${hm(r.at)} UTC</span><span style="grid-column:1/-1">${esc(r.reviewer === 'claude_ai_demo' ? O.review.who : r.reviewer)} · ${esc(r.outcome === 'escalate' ? 'sent to XProtect' : r.outcome)}</span><details style="grid-column:1/-1"><summary class="muted">Read the review</summary>${esc(r.note)}</details></div>`
          : `<div class="obs"><b>Revision ${r.revision}</b><span class="gap" style="grid-column:1/-1">Overwritten before history was kept. It cannot be reconstructed, and nothing has been invented in its place.</span></div>`).join('')}</section></div></aside>`;
    }
    if (which === 'evidence') {
      const p = O.primary;
      return head('Evidence details') + `<dl class="kv"><dt>Recording</dt><dd>${p.video.duration} s. ${members.every((m) => m.video.sha256 === p.video.sha256) ? `Identical in all ${members.length} observations.` : 'The observations differ.'}</dd>
        ${members.map((m, i) => `<dt>Observation ${i + 1}</dt><dd>${m.interval[0].slice(11, 19)} UTC<br>recording <code>${m.video.sha256}</code><br>Hafnia request <code>${m.requestSha256}</code><br>summary <code>${m.hafnia.summaryId}</code></dd>`).join('')}
        <dt>Hafnia answer</dt><dd>${esc(p.hafnia.outcome)} · timing ${esc(p.hafnia.timing)}</dd>
        <dt>Local vision</dt><dd>${esc(p.vision.model)} on ${esc(p.vision.device)}, ${p.vision.samplesPerSecond} samples per second, ${p.vision.tracks} tracks</dd>
        <dt>Requests today</dt><dd>This Watch ${O.watch.schedule.usedToday} of ${O.watch.schedule.budgetPerDay}; all Watches ${D.budget.usedToday} of ${D.budget.global_}</dd></dl>
        <section><h3>What the sources can and cannot say</h3><ul class="muted" style="margin:0;padding-left:18px">${p.limitations.map((l) => `<li>${esc(l)}</li>`).join('')}</ul></section>
        <details><summary>Prompt sent to Hafnia</summary><p class="muted" style="margin-top:8px">${esc(p.hafnia.prompt)}</p></details></div></aside>`;
    }
    if (which === 'alert') {
      return head('XProtect alert') + `<dl class="kv"><dt>Event</dt><dd>${esc(O.primary.native.destination.event)}</dd><dt>Alarm</dt><dd>${esc(O.primary.native.destination.alarm)}</dd>
        <dt>Sent</dt><dd>${day(O.alert.sent)} ${hm(O.alert.sent)} UTC, Event Server accepted (HTTP 200, one attempt)</dd>
        <dt>Alarm in XProtect</dt><dd>Alarm ${O.alert.localId}, camera ${esc(O.camera)}, source time 12:42:29.513</dd>
        <dt>Smart Client</dt><dd>Verified by the ${O.alert.verifiedBy}, 30 Oct: recorded image with the detection box</dd></dl>
        <details><summary>Send another alert for this event</summary><p class="muted" style="margin:8px 0">The event already raised alarm ${O.alert.localId}. A second alarm for the same footage needs explicit confirmation.</p>
        <label class="check"><input type="checkbox" disabled> I understand this raises a second alarm</label><p style="margin-top:8px"><button class="btn" disabled>Send again</button></p></details></div></aside>`;
    }
  }


  window.OR = { span, drawers, D, $, $$, esc, hm, day, clock, MARK, occurrence, members, watchOf, watchState, lastResult, why, player, regionEditor, deriveLabel, connection, protoMark, rev2 };
})();
