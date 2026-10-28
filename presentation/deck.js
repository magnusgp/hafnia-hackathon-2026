'use strict';
// Adaptive Watch deck. Manual: arrows/space, f fullscreen, c captions. Timed: ?auto=1 (driven by timing.json).
const params = new URLSearchParams(location.search);
const scenes = [...document.querySelectorAll('.scene')];
const caption = document.getElementById('caption');
const bar = document.querySelector('#progress i');
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
let samples = null, timing = null, index = -1, timers = [], captionsOn = params.has('captions') || params.has('auto');
if (params.has('record')) document.body.classList.add('record');

const wait = ms => new Promise(r => setTimeout(r, ms));
const later = (ms, fn) => timers.push(setTimeout(fn, ms));
const clear = () => { timers.forEach(clearTimeout); timers = []; };
const vid = id => document.getElementById(id);

function seek(v, t) {
  return new Promise(res => {
    const done = () => { v.removeEventListener('seeked', done); res(); };
    v.addEventListener('seeked', done); v.currentTime = t;
    setTimeout(res, 800);
  });
}

function drawSample(svg, s) {
  const ns = 'http://www.w3.org/2000/svg';
  svg.replaceChildren();
  const poly = document.createElementNS(ns, 'polygon');
  poly.setAttribute('class', 'region');
  poly.setAttribute('points', samples.region.map(p => p.join(',')).join(' '));
  svg.append(poly);
  if (s && s.box) {
    const r = document.createElementNS(ns, 'rect');
    r.setAttribute('class', 'box');
    Object.entries({x: s.box[0], y: s.box[1], width: s.box[2] - s.box[0], height: s.box[3] - s.box[1]}).forEach(([k, v]) => r.setAttribute(k, v));
    svg.append(r);
  }
}

const hooks = {
  async open(el) {
    const v = vid('v-open'); await seek(v, 8.0);
    if (!reduce) v.play();
  },
  async silent() {
    const v = vid('v-silent'); await seek(v, 7.2);
    if (!reduce) { v.play(); v.onended = () => { v.currentTime = 7.2; v.play(); }; }
  },
  async signal() {
    const v = vid('v-signal'), svg = vid('ov-signal');
    v.pause();
    const first = samples.samples.find(s => s.t === samples.trigger);
    await seek(v, first.t); drawSample(svg, first);
    // Step through the real 2 Hz detector samples; the box exists only on the frame it was measured.
    const steps = samples.samples.filter(s => s.t >= first.t && s.t <= samples.decisive + 0.6);
    steps.forEach((s, i) => { if (i) later(6200 + (i - 1) * 520, async () => { await seek(v, s.t); drawSample(svg, s); }); });
  },
  async operator() {
    const v = vid('v-operator'); await seek(v, 0); v.play();
  },
  xprotect() {
    const proof = vid('x-proof');
    if (timing && timing.proof) proof.textContent = timing.proof;
  },
};

function leave() {
  clear();
  document.querySelectorAll('video').forEach(v => { v.pause(); v.onended = null; });
}

async function go(i) {
  if (i < 0 || i >= scenes.length || i === index) return;
  leave();
  index = i;
  scenes.forEach((s, k) => s.classList.toggle('active', k === i));
  const el = scenes[i];
  el.querySelectorAll('[data-in]').forEach(n => n.style.setProperty('--d', (Number(n.dataset.in) - 1) * 0.55 + (el.id === 'open' ? 5.0 : 0)));
  if (el.id === 'signal') el.querySelectorAll('[data-in]').forEach(n => n.style.setProperty('--d', n.dataset.in === '4' ? 12 : 0.3));
  location.hash = el.id;
  if (hooks[el.id]) await hooks[el.id](el);
}

function showCaption(text) {
  caption.textContent = text || '';
  caption.classList.toggle('on', captionsOn && !!text);
}

// Timed run: scenes begin at their start offsets; captions follow narration sentences.
async function runTimed() {
  const t0 = performance.now(), total = timing.total;
  let sceneIdx = -1, cap = '';
  await new Promise(resolve => {
    const frame = () => {
      const t = (performance.now() - t0) / 1000;
      const k = timing.scenes.findLastIndex(s => t >= s.start);
      if (k !== sceneIdx && k >= 0) { sceneIdx = k; go(scenes.findIndex(s => s.id === timing.scenes[k].id)); }
      const s = timing.scenes[Math.max(k, 0)];
      const line = s.sentences.findLast(x => t >= s.start + x.t && t < s.start + x.t + x.d);
      const text = line ? line.text : '';
      if (text !== cap) { cap = text; showCaption(text); }
      bar.style.width = `${Math.min(100, (t / total) * 100)}%`;
      if (t >= total) return resolve();
      requestAnimationFrame(frame);
    };
    frame();
  });
  window.__deckDone = true;
}

async function init() {
  samples = await (await fetch('assets/samples.json')).json();
  try { timing = await (await fetch('timing.json')).json(); } catch { timing = null; }
  if (params.has('auto') && timing) {
    window.startDeck = () => runTimed();
    if (!params.has('hold')) await runTimedWhenReady();
    return;
  }
  const start = Math.max(0, scenes.findIndex(s => s.id === location.hash.slice(1)));
  go(start);
  addEventListener('keydown', e => {
    if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') { e.preventDefault(); go(index + 1); }
    else if (e.key === 'ArrowLeft' || e.key === 'PageUp') go(index - 1);
    else if (e.key === 'Home') go(0);
    else if (e.key === 'End') go(scenes.length - 1);
    else if (e.key === 'f') document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen();
    else if (e.key === 'c') { captionsOn = !captionsOn; if (!captionsOn) showCaption(''); }
  });
  addEventListener('hashchange', () => go(scenes.findIndex(s => s.id === location.hash.slice(1))));
  bar.style.width = '0';
}
async function runTimedWhenReady() { await wait(500); window.__deckReady = true; }
init();
