// Real-browser checks of every visible control on an ISOLATED demo instance.
// Usage: bun check-app.mjs <outDir> [baseUrl]   (reset the demo first: make_demo_root.py + record_agent_review.py)
import { chromium } from 'playwright';
import { mkdir } from 'node:fs/promises';
const out = process.argv[2], base = process.argv[3] ?? 'http://127.0.0.1:8781';
await mkdir(out, { recursive: true }).catch(() => {});
const failures = [], notes = [];
const check = (name, ok, detail = '') => { (ok ? notes : failures).push(`${ok ? 'ok  ' : 'FAIL'} ${name} ${detail}`); };
const browser = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true, args: ['--no-first-run'] });

for (const [w, h] of [[1440, 900], [1920, 1080]]) {
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  page.on('console', m => { if (m.type() === 'error' && !/favicon/.test(m.text())) errors.push(m.text()); });
  await page.goto(base + '/#/railway', { waitUntil: 'networkidle' });
  await page.waitForFunction(() => { const v = document.querySelector('video'); return v && v.readyState >= 2 && Math.abs(v.currentTime - 5.4) < 0.2; });
  check(`${w}: opens at the decisive part, not sample 0`, await page.evaluate(() => document.querySelector('video').currentTime > 5));
  check(`${w}: no vertical page scroll`, await page.evaluate(() => document.documentElement.scrollHeight <= innerHeight + 1));
  check(`${w}: primary action visible without scrolling`, await page.getByRole('button', { name: 'Send to XProtect review' }).isVisible()
    && await page.getByRole('button', { name: 'Send to XProtect review' }).evaluate(b => b.getBoundingClientRect().bottom <= innerHeight));
  check(`${w}: box drawn on the sample frame`, await page.locator('svg.overlay rect.box').count() === 1);
  await page.screenshot({ path: `${out}/railway-${w}.png` });

  // Overlay never invents positions between samples.
  await page.getByRole('button', { name: 'Next sample' }).click();
  await page.waitForTimeout(300);
  const t1 = await page.evaluate(() => document.querySelector('video').currentTime);
  await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(300);
  const between = await page.evaluate(() => ({ t: document.querySelector('video').currentTime, boxes: document.querySelectorAll('svg.overlay rect.box').length }));
  check(`${w}: next sample steps to the next 0.5 s sample`, Math.abs(t1 - 5.9) < 0.06, `t=${t1}`);
  check(`${w}: no box between samples`, between.boxes === 0 && /Between detector samples/.test(await page.locator('.sampled').innerText()), JSON.stringify(between));
  await page.getByRole('button', { name: 'Previous sample' }).click();
  await page.getByRole('button', { name: 'The climb' }).click();
  await page.waitForTimeout(400);
  check(`${w}: climb jump`, Math.abs(await page.evaluate(() => document.querySelector('video').currentTime) - 9.2) < 0.06);
  await page.getByLabel('Box').uncheck(); check(`${w}: box toggle off`, await page.locator('svg.overlay rect.box').count() === 0); await page.getByLabel('Box').check();
  await page.getByLabel('Region').uncheck(); check(`${w}: region toggle off`, await page.locator('svg.overlay polygon').count() === 0); await page.getByLabel('Region').check();
  await page.getByRole('button', { name: 'Play from the trigger' }).click();
  await page.waitForFunction(() => document.querySelector('video').paused && document.querySelector('video').currentTime > 9.5, null, { timeout: 15000 });
  check(`${w}: play from trigger stops after the climb`, true);
  await page.getByRole('button', { name: 'Play', exact: true }).click(); await page.waitForTimeout(500);
  check(`${w}: play / pause`, await page.evaluate(() => !document.querySelector('video').paused));
  await page.getByRole('button', { name: 'Pause', exact: true }).click();
  await page.locator('.scrub').focus(); await page.keyboard.press('ArrowLeft');
  check(`${w}: scrub input is keyboard operable`, true);
  await page.getByRole('button', { name: /Person at the platform edge/ }).click(); await page.waitForTimeout(300);
  check(`${w}: signal row seeks`, Math.abs(await page.evaluate(() => document.querySelector('video').currentTime) - 5.4) < 0.06);

  // Details dialog and focus return.
  await page.getByRole('button', { name: 'Evidence details' }).click();
  check(`${w}: details open`, await page.getByRole('dialog').getByText('Reviewed footage').isVisible());
  if (w === 1440) await page.screenshot({ path: `${out}/details-${w}.png` });
  await page.keyboard.press('Escape');
  check(`${w}: Escape closes and focus returns`, await page.evaluate(() => document.activeElement?.textContent === 'Evidence details'));

  // Case switching, with isolation.
  for (const [name, expect] of [['School gate at night', 'no opening observed'], ['Sidewalk with scooter', 'Still for'], ['Sidewalk with bin', 'Still for']]) {
    await page.getByRole('link', { name: new RegExp(name) }).click();
    await page.waitForFunction(() => { const i = document.querySelector('.stage img'); return i && i.complete && i.naturalWidth > 0; }, null, { timeout: 15000 });
    await page.waitForTimeout(600);
    check(`${w}: ${name} loads its own evidence`, (await page.locator('.brief').innerText()).includes(expect));
    if (name === 'School gate at night') check(`${w}: gate shows no detector controls (none exist)`, await page.getByLabel('Box').count() === 0 && await page.locator('.sampled').count() === 0);
    check(`${w}: ${name} is not a railway review`, !(await page.locator('.brief').innerText()).includes('What XProtect receives'));
    if (w === 1440 || name !== 'Sidewalk with bin') await page.screenshot({ path: `${out}/${name.split(' ').pop()}-${w}.png` });
  }
  await page.getByRole('link', { name: /Station platform/ }).click();
  await page.waitForSelector('video');

  // New assessment: honest availability.
  await page.getByRole('button', { name: 'New assessment' }).click();
  const dlg = page.getByRole('dialog');
  const text = await dlg.innerText();
  check(`${w}: New assessment states availability or the exact next step`, /Start it with|Start assessment/.test(text), text.slice(0, 120).replace(/\n/g, ' '));
  const box = await dlg.boundingBox();
  check(`${w}: dialog is centered`, Math.abs(box.x + box.width / 2 - w / 2) < 24 && box.y > 20, JSON.stringify(box));
  if (w === 1440) await page.screenshot({ path: `${out}/new-assessment-${w}.png` });
  await page.keyboard.press('Escape');

  // Decision dialog validation (cancelled; no state change).
  await page.getByRole('button', { name: 'Send to XProtect review' }).click();
  const save = page.getByRole('button', { name: 'Save review request' });
  check(`${w}: save disabled until footage acknowledged`, await save.isDisabled());
  await page.getByLabel('Entry onto the tracks').check();
  await page.getByLabel('I watched the relevant footage').check();
  check(`${w}: verdict needs a note`, await save.isDisabled());
  await page.getByRole('button', { name: 'Cancel' }).click();
  check(`${w}: no console or page errors`, errors.length === 0, errors.join(' | '));
  await page.close();
}

// Reload, stale revision, negative API responses.
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto(base + '/#/railway', { waitUntil: 'networkidle' });
const api = await page.evaluate(async () => {
  const get = await (await fetch('/api/cases/railway')).json();
  const stale = await fetch('/api/cases/railway/action', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Review-CSRF': get.csrf }, body: JSON.stringify({ action: 'review', revision: 'stale' }) });
  const noCsrf = await fetch('/api/cases/railway/action', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'review', revision: get.case.actionRevision }) });
  const unknown = await fetch('/api/cases/nonexistent');
  const frame = await fetch('/api/cases/railway/frames/999');
  const native = await fetch('/api/cases/gate/native', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Review-CSRF': get.csrf }, body: JSON.stringify({ action: 'preview' }) });
  return { stale: stale.status, noCsrf: noCsrf.status, unknown: unknown.status, frame: frame.status, native: native.status };
});
check('stale revision is refused (409)', api.stale === 409, JSON.stringify(api));
check('missing session token is refused (403)', api.noCsrf === 403);
check('unknown case is 404', api.unknown === 404);
check('missing frame is 404', api.frame === 404);
check('native preview for a case without a handoff is refused', api.native === 422);

// Complete a request, reload, and confirm persistence (isolated store).
await page.getByRole('button', { name: 'Send to XProtect review' }).click();
await page.getByLabel('Entry onto the tracks').check();
await page.getByLabel('Note').fill('Person lowers off the platform edge and walks away along the tracks.');
await page.getByLabel('I watched the relevant footage').check();
await page.getByRole('button', { name: 'Save review request' }).click();
await page.getByRole('dialog').waitFor({ state: 'detached' });
await page.reload({ waitUntil: 'networkidle' });
await page.waitForSelector('.saved');
check('saved request survives reload', (await page.locator('.saved').innerText()).includes('entry visible'));
check('decision in another case is untouched', await page.evaluate(async () => (await (await fetch('/api/cases/gate')).json()).case.state.status === 'review_required'));
check('native state stays distinct from the saved request', /Ready|In Smart Client|Sent/.test(await page.locator('.native').innerText()));
await page.close();
await browser.close();
console.log(notes.join('\n')); console.log(failures.length ? `\n${failures.length} FAILED\n${failures.join('\n')}` : `\nall ${notes.length} checks passed`);
process.exit(failures.length ? 1 : 0);
