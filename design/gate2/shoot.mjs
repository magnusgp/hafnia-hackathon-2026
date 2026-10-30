// Renders each prototype state at the two target sizes with the real browser and saves PNGs (private dir, they contain footage).
// Usage: bun design/gate2/shoot.mjs <a|b> <outDir> [states...]
import { chromium } from '../../frontend/node_modules/playwright/index.mjs';
import { mkdirSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
const [comp, out, ...only] = process.argv.slice(2);
try { mkdirSync(out, { recursive: true }); } catch {}
const base = new URL(`./${comp}.html`, import.meta.url).href;
const Q = 'A%20person%20climbs%20down%20from%20the%20platform%20edge%20onto%20the%20railway%20track%20area%2C%20or%20remains%20on%20the%20tracks.';
const STATES = {
  'exception': ['#/exceptions?seek=6.9', { video: true }],
  'exception-trigger': ['#/exceptions?seek=4.9', { video: true }],
  'history': ['#/exceptions/history?seek=6.9', { video: true }],
  'evidence': ['#/exceptions/evidence?seek=6.9', { video: true }],
  'alert': ['#/exceptions/alert?seek=6.9', { video: true }],
  'watches': ['#/watches', {}],
  'editor-edit': ['#/watch/w-c95bfc089f?step=2', {}],
  'new-start': ['#/watch/new', {}],
  'new-question': [`#/watch/new?cam=person_on_railway_tracks&step=2&region=1&q=${Q}`, {}],
  'new-noframe': ['#/watch/new?cam=busy_street&step=1', {}],
  'new-monitoring': [`#/watch/w-c95bfc089f?step=3`, {}],
};
const browser = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true, args: ['--no-first-run', '--autoplay-policy=no-user-gesture-required', '--allow-file-access-from-files'] });
const problems = [];
for (const [w, h] of [[1440, 900], [1920, 1080]]) {
  for (const [name, [hash, o]] of Object.entries(STATES)) {
    if (only.length && !only.includes(name)) continue;
    const page = await (await browser.newContext({ viewport: { width: w, height: h } })).newPage();
    page.on('console', (m) => { if (m.type() === 'error') problems.push(`${name}@${w}: ${m.text()}`); });
    page.on('pageerror', (e) => problems.push(`${name}@${w}: ${e.message}`));
    await page.goto(base + hash);
    if (o.video) await page.waitForFunction(() => { const v = document.querySelector('video'); return v && v.readyState >= 2 && !v.seeking; }, null, { timeout: 15000 });
    await page.waitForTimeout(500);
    await page.screenshot({ path: `${out}/${comp}-${name}-${w}.png` });
    const sc = await page.evaluate(() => ({ docH: document.documentElement.scrollHeight, winH: innerHeight, vid: (() => { const v = document.querySelector('.pv, .redit'); return v ? Math.round(v.getBoundingClientRect().width) + 'x' + Math.round(v.getBoundingClientRect().height) : null; })() }));
    console.log(`${comp} ${name} ${w}x${h} doc ${sc.docH} win ${sc.winH} media ${sc.vid}`);
    await page.close();
  }
}
await browser.close();
if (problems.length) console.log('PROBLEMS\n' + problems.join('\n'));
