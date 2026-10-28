// Release checks of what a judge sees on an ISOLATED demo instance: trigger start, the three lanes,
// a failed New assessment, review persistence and the guarded native send.
// Usage: bun check-release.mjs <outDir> [baseUrl]. Sends nothing: the demo server runs without --native-send.
import { chromium } from 'playwright';
import { mkdir } from 'node:fs/promises';
const out = process.argv[2], base = process.argv[3] ?? 'http://127.0.0.1:8781';
await mkdir(out, { recursive: true }).catch(() => {});
const failures = [], notes = [];
const check = (name, ok, detail = '') => { (ok ? notes : failures).push(`${ok ? 'ok  ' : 'FAIL'} ${name} ${detail}`); };
const browser = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true, args: ['--no-first-run'] });
const time = page => page.evaluate(() => document.querySelector('video').currentTime);

for (const [w, h] of [[1440, 900], [1920, 1080]]) {
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error' && !/favicon|status of 422|status of 500/.test(m.text())) errors.push(m.text()); });
  await page.goto(base + '/#/railway', { waitUntil: 'networkidle' });
  await page.waitForFunction(() => { const v = document.querySelector('video'); return v && v.readyState >= 2; });
  const trigger = await page.evaluate(async () => (await (await fetch('/api/cases/railway')).json()).case.vision.trigger.mediaTime);
  check(`${w}: footage starts at the detector trigger`, Math.abs(await time(page) - trigger) < 0.2, `trigger=${trigger} start=${await time(page)}`);

  // Three lanes: labels, content, and a click in each lane seeks.
  const labels = await page.locator('.lane-labels span').allInnerTexts();
  check(`${w}: three lane labels`, labels.join('|') === 'Hafnia|Local vision|Reviewed footage', labels.join('|'));
  const lanes = page.locator('.lane-body .lane');
  check(`${w}: lane content (answer, detector samples, reviewed phases)`,
    await lanes.nth(0).locator('.bar').count() === 1 && await lanes.nth(1).locator('.dot').count() > 5 && await lanes.nth(2).locator('.bar').count() >= 1,
    `${await lanes.nth(1).locator('.dot').count()} dots, ${await lanes.nth(2).locator('.bar').count()} bars`);
  let prev = -1;
  for (const [i, frac] of [[0, 0.2], [1, 0.5], [2, 0.8]]) {
    const b = await lanes.nth(i).boundingBox();
    await page.mouse.click(b.x + b.width * frac, b.y + b.height / 2);
    await page.waitForTimeout(400);
    const t = await time(page);
    const dur = await page.evaluate(() => document.querySelector('video').duration);
    check(`${w}: lane ${i + 1} click seeks to ${frac * 100}%`, Math.abs(t / dur - frac) < 0.08 && t > prev, `t=${t.toFixed(2)} of ${dur.toFixed(2)}`);
    prev = t;
  }
  if (w === 1440) await page.screenshot({ path: `${out}/lanes-${w}.png` });

  // A failed New assessment is explained, in the dialog, and can be retried. The server answers are simulated.
  await page.route('**/api/casebook', async route => {
    const r = await route.fetch(); const j = await r.json();
    j.assessment = { available: true, cameras: [{ id: 'cam-x', title: 'Station platform camera' }] };
    await route.fulfill({ response: r, json: j });
  });
  let n = 0;
  await page.route('**/api/jobs', async route => {
    n += 1;
    if (n === 1) return route.fulfill({ status: 422, json: { error: 'The Hafnia gateway refused the request. Start it again with scripts\\launch.ps1 -AssessmentLogin.' } });
    return route.fulfill({ json: { job: { id: 'a'.repeat(32), state: 'failed', caseId: null, video: null,
      stages: [{ key: 'record', label: 'Record the camera', status: 'done', detail: '' }, { key: 'hafnia', label: 'Ask Hafnia', status: 'failed', detail: '' }],
      error: { reason: 'Hafnia did not answer within 60 s', next: 'No request was counted. Try again.' } } } });
  });
  await page.reload({ waitUntil: 'networkidle' });
  await page.getByRole('button', { name: 'New assessment' }).click();
  await page.getByRole('button', { name: 'Start assessment' }).click();
  await page.getByRole('alert').waitFor();
  check(`${w}: refused assessment shows the reason`, /gateway refused/.test(await page.getByRole('alert').innerText()));
  check(`${w}: dialog stays usable after a refusal`, await page.getByRole('button', { name: 'Start assessment' }).isEnabled());
  await page.getByRole('button', { name: 'Start assessment' }).click();
  await page.getByText('Hafnia did not answer within 60 s').waitFor();
  const dlg = await page.getByRole('dialog').innerText();
  check(`${w}: failed stage shows reason and next step`, /Ask Hafnia/.test(dlg) && /Try again/.test(dlg) && !/Open result/.test(dlg));
  if (w === 1440) await page.screenshot({ path: `${out}/assessment-failure-${w}.png` });
  await page.unroute('**/api/jobs'); await page.unroute('**/api/casebook');
  await page.keyboard.press('Escape');
  check(`${w}: no unexpected console or page errors`, errors.length === 0, errors.join(' | '));
  await page.close();
}

// Persistence, native guard and untouched operator state, over the API of the isolated instance.
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto(base + '/#/railway', { waitUntil: 'networkidle' });
await page.waitForSelector('.saved');
check('review persists across reload (isolated store)', /entry visible/.test(await page.locator('.saved').innerText()));
check('no Send to XProtect button while sending is off', await page.getByRole('button', { name: 'Send to XProtect', exact: true }).count() === 0);
const r = await page.evaluate(async () => {
  const get = await (await fetch('/api/cases/railway')).json();
  const send = await fetch('/api/cases/railway/native', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Review-CSRF': get.csrf }, body: JSON.stringify({ action: 'send', confirmed: true, approval: 'x' }) });
  return { canSend: get.case.native?.canSend, status: send.status, body: await send.json() };
});
check('native send refused by the server when disabled', r.status === 422 && /disabled/.test(r.body.error) && r.canSend === false, JSON.stringify(r));
await browser.close();
console.log(notes.join('\n')); console.log(failures.length ? `\n${failures.length} FAILED\n${failures.join('\n')}` : `\nall ${notes.length} checks passed`);
process.exit(failures.length ? 1 : 0);
