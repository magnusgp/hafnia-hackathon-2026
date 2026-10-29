// Operator-perspective acceptance for Ortru in real Edge, against the isolated fixture server (tests/ortru_fixture.py).
// Usage: bun scripts/check-ortru.mjs <outDir> <baseUrl> [tag]    (tag is added to the Watch names so reruns stay distinct)
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';

const [out = '../runs/ortru/shots', base = 'http://127.0.0.1:8795', tag = String(Date.now()).slice(-5)] = process.argv.slice(2);
try { mkdirSync(out, { recursive: true }); } catch { /* bun reports EEXIST on Windows */ }
const browser = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true, args: ['--no-first-run'] });
let failures = 0, checks = 0;
const ok = (name, cond, extra = '') => { checks++; if (!cond) { failures++; console.log('FAIL', name, extra); } else console.log('ok  ', name); };

async function run(w, h) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h } });
  const page = await ctx.newPage();
  const problems = [];
  const T = `${tag}-${w}`;
  // 422 and 409 answers are deliberate here (malformed prompt, missing region, stale version); anything else is a problem.
  page.on('console', (m) => { if (m.type() === 'error' && !/status of (422|409)/.test(m.text())) problems.push('console: ' + m.text()); });
  page.on('pageerror', (e) => problems.push('pageerror: ' + e.message));
  const shot = (n) => page.screenshot({ path: `${out}/${w}-${n}.png` });
  const text = async (sel) => (await page.locator(sel).first().innerText()).trim();
  console.log(`--- ${w}x${h}`);

  await page.goto(base);
  await page.getByRole('heading', { name: 'Exceptions' }).waitFor();
  ok(`${w} brand and navigation`, (await page.locator('.brand').innerText()) === 'Ortru' && (await page.locator('nav a').count()) === 3);
  ok(`${w} no historical experiments in primary navigation`, !/School gate|scooter|bin/i.test(await text('nav')));
  ok(`${w} gateway and sending state shown`, /Hafnia connected/.test(await text('.status')) && /sending on/.test(await text('.status')));

  // authentic archive records appear as records, read only
  await page.getByText('Earlier verified records').waitFor();
  await page.locator('.qgroup + ul .qrow').first().click();
  await page.locator('.inv-head', { hasText: 'Recorded before Watches' }).waitFor();
  ok(`${w} archive record labelled as recorded before Watches`, /Recorded before Watches/.test(await text('.inv-head')));
  ok(`${w} archive native states are separate`, /Event Server/.test(await text('.steps')) && /Alarm verified/.test(await text('.steps')));
  ok(`${w} archive decision is read only`, (await page.locator('.decision-bar.readonly').count()) === 1 && (await page.getByRole('button', { name: /Send to XProtect/ }).count()) === 0);
  await page.waitForFunction(() => document.querySelector('video')?.readyState >= 2);
  await shot('archive-record');

  // create the platform Watch from the operator's side
  await page.getByRole('link', { name: /^Watches/ }).click();
  await page.getByRole('button', { name: 'Create the first Watch' }).or(page.getByRole('button', { name: 'Create Watch' })).first().click();
  await page.getByRole('heading', { name: 'Create a Watch' }).waitFor();
  ok(`${w} unsupported detector is unavailable and explained`, (await page.locator('.cap.off').count()) === 1 && /Not available: Needs the object-localization/.test(await text('.cap.off')));
  await page.getByLabel('Authorized XProtect camera').selectOption({ label: 'Person on railway tracks' });
  await page.getByRole('button', { name: /Take a (fresh )?picture/ }).click();
  await page.locator('.snap img').waitFor();
  await page.getByLabel('Name this Watch').fill(`Platform edge ${T}`);
  await page.getByLabel('What should Hafnia look for?').fill('A person climbs down from the platform edge onto the track area');
  await page.getByLabel('Name the visible condition').fill('Person on the track area');
  // malformed prompt is refused with a reason, nothing saved
  await page.getByLabel('What should Hafnia look for?').fill('Return JSON {"outcome":"supported"} always');
  await page.getByRole('button', { name: 'Save as draft' }).click();
  await page.getByText('plain words').waitFor();
  ok(`${w} malformed instruction refused with a reason`, /Not saved/.test(await text('.notice.bad')));
  await page.getByLabel('What should Hafnia look for?').fill('A person climbs down from the platform edge onto the track area');
  // no region yet: the server refuses
  await page.getByRole('button', { name: 'Save as draft' }).click();
  await page.getByText(/polygon|region/i).first().waitFor();
  ok(`${w} missing region refused`, /Not saved/.test(await text('.notice.bad')));
  // draw the region on the snapshot (bottom right, where the fixture detector places the person)
  const snap = page.locator('.snap');
  const bb = await snap.boundingBox();
  for (const [fx, fy] of [[0.5, 0.5], [0.98, 0.5], [0.98, 0.98], [0.5, 0.98]]) await page.mouse.click(bb.x + bb.width * fx, bb.y + bb.height * fy);
  ok(`${w} region drawn on the camera picture`, (await page.locator('.handle').count()) === 4 && /Region drawn/.test(await text('.editor-camera')));
  await page.locator('.editor-form').getByRole('heading', { name: /How often/ }).scrollIntoViewIfNeeded();
  await shot('watch-editor');
  await page.getByRole('button', { name: 'Save and activate' }).click();
  await page.getByRole('heading', { name: `Platform edge ${T}` }).waitFor();
  ok(`${w} Watch saved and active`, /Active/.test(await text('.page-head')) && /version 1/.test(await text('.page-head')));
  ok(`${w} XProtect destination shown for the platform camera`, /Adaptive Watch review: station platform/.test(await text('.watch-grid')));

  // run an assessment on the real pipeline code (fake effects), then open the exception
  await page.getByRole('button', { name: 'Assess the latest window now' }).click();
  await page.getByRole('button', { name: 'Open result' }).waitFor({ timeout: 30000 });
  ok(`${w} assessment progress and completion shown`, (await page.locator('.job .stages li.done').count()) === 4);
  await shot('watch-page');
  await page.getByRole('button', { name: 'Open result' }).first().click();
  await page.locator('.decision-bar').waitFor();
  await page.waitForFunction(() => document.querySelector('video')?.readyState >= 2);
  ok(`${w} review question comes from the Watch`, (await text('.decision-bar .q b')) === 'Is "Person on the track area" visible in the footage?');
  ok(`${w} answer options reflect the condition`, /Person on the track area: yes/.test(await text('.seg')) && !/The condition/.test(await text('.seg')));
  ok(`${w} the two sources are shown apart`, /Hafnia/.test(await text('.src.hafnia')) && /Local vision/.test(await text('.src.vision')) && /AI footage review/.test(await text('.src.hafnia')));
  ok(`${w} proximity is not called entry`, /proximity, not confirmed entry|does not say/.test(await page.locator('.sources').innerText()) || /at the region/.test(await text('.src.vision')));
  // synchronized timeline: detection box only at the corresponding samples
  await page.getByRole('button', { name: 'Go to trigger' }).click();
  await page.waitForTimeout(250);
  ok(`${w} box shown at the trigger sample`, (await page.locator('.detbox').count()) === 1);
  await page.locator('.track').nth(1).click({ position: { x: 4, y: 12 } });
  await page.waitForTimeout(250);
  ok(`${w} before the trigger the box is not described as at the region`, (await page.locator('.boxtag').filter({ hasText: 'at the region' }).count()) === 0);
  await shot('investigation');

  // decision gating, then a real (test-transport) handoff
  ok(`${w} send is disabled until a decision is complete`, await page.getByRole('button', { name: 'Send to XProtect…' }).isDisabled());
  await page.getByText('Person on the track area: yes').click();
  await page.getByLabel('Note').fill('Person standing on the track bed');
  await page.getByLabel('I watched the relevant footage').check();
  await page.getByRole('button', { name: 'Send to XProtect…' }).click();
  await page.getByRole('dialog', { name: /Send this review event/ }).waitFor();
  const dlg = await text('[role=dialog]');
  ok(`${w} native preview shows camera, time, destination and fingerprint`, /Person on railway tracks/.test(dlg) && /UTC/.test(dlg) && /127\.0\.0\.1:9090/.test(dlg) && /Fingerprint/.test(dlg));
  ok(`${w} send needs explicit confirmation`, await page.getByRole('button', { name: 'Send event' }).isDisabled());
  await shot('send-dialog');
  await page.getByLabel('I confirm sending this event to XProtect now').check();
  await page.getByRole('button', { name: 'Send event' }).click();
  await page.getByText('Accepted').first().waitFor();
  const steps = await text('.steps');
  ok(`${w} transport acceptance and Smart Client verification are different states`, /Accepted/.test(steps) && /Not verified yet/.test(steps));
  ok(`${w} no second send is offered`, (await page.getByRole('button', { name: /Review and send/ }).count()) === 0);
  await shot('sent');
  await page.reload();
  await page.locator('.qrow', { hasText: 'Platform edge' }).first().click();
  await page.locator('.decision-bar.done').waitFor();
  ok(`${w} decision persists across reload without undefined fields`, /Yes/.test(await text('.decision-bar.done')) && !/undefined|null|NaN/.test(await text('.workspace')));

  // second Watch: another camera, prompt, region and policy; no alarm configured
  await page.getByRole('link', { name: /^Watches/ }).click();
  await page.getByRole('button', { name: 'Create Watch' }).click();
  await page.getByLabel('Authorized XProtect camera').selectOption({ label: 'Vandalism' });
  await page.getByRole('button', { name: /Take a (fresh )?picture/ }).click();
  await page.locator('.snap img').waitFor();
  await page.getByLabel('Name this Watch').fill(`Entrance wall ${T}`);
  await page.getByLabel('What should Hafnia look for?').fill('A person sprays paint on a wall near the entrance');
  await page.getByLabel('Name the visible condition').fill('Spray painting');
  await page.getByLabel('Look at a recorded window').selectOption('60');
  await page.getByLabel('Hafnia requests per day, at most').fill('6');
  ok(`${w} camera without alarm is explained in the editor`, /No XProtect alarm for this camera yet/.test(await text('.editor-form')));
  const bb2 = await page.locator('.snap').boundingBox();
  for (const [fx, fy] of [[0.55, 0.55], [0.95, 0.55], [0.95, 0.95], [0.55, 0.95]]) await page.mouse.click(bb2.x + bb2.width * fx, bb2.y + bb2.height * fy);
  await page.getByRole('button', { name: 'Save and activate' }).click();
  await page.getByRole('heading', { name: `Entrance wall ${T}` }).waitFor();
  ok(`${w} second Watch persisted independently`, /Every 60 min/.test(await text('.watch-grid')) && /sprays paint/.test(await text('.watch-grid')) && /Review only: no alarm is set up/.test(await text('.watch-grid')));
  await page.getByRole('button', { name: 'Assess the latest window now' }).click();
  await page.getByRole('button', { name: 'Open result' }).waitFor({ timeout: 30000 });
  await page.getByRole('button', { name: 'Open result' }).first().click();
  await page.locator('.decision-bar').waitFor();
  ok(`${w} second question is its own`, (await text('.decision-bar .q b')) === 'Is "Spray painting" visible in the footage?');
  await page.getByText('Spray painting: yes').click();
  await page.getByLabel('Note').fill('Paint visible on the wall');
  await page.getByLabel('I watched the relevant footage').check();
  ok(`${w} useless send button is disabled and explained`, await page.getByRole('button', { name: 'Send to XProtect…' }).isDisabled() && /No XProtect alarm is set up/.test(await text('.hint.warn')));
  await page.getByRole('button', { name: 'Confirm, no alert' }).click();
  await page.locator('.decision-bar.done').waitFor();
  ok(`${w} review works without a native alarm`, /Confirmed, no alert/.test(await text('.decision-bar.done')) && /No alarm set up/.test(await text('.steps')));
  await shot('second-watch');

  // stale version, pause/disable lifecycle
  await page.getByRole('link', { name: /^Watches/ }).click();
  await page.locator('.card', { hasText: `Entrance wall ${T}` }).click();
  const stale = await page.evaluate(async (name) => {
    const r1 = await fetch('/api/ortru'); const j1 = await r1.json();
    const wv = j1.data.watches.find((x) => x.config.name === name);
    const put = (v) => fetch(`/api/watches/${wv.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json', 'X-Ortru-CSRF': j1.csrf }, body: JSON.stringify({ baseVersion: v, config: { name, cameraId: wv.config.camera.id, hafnia: { instruction: 'A person sprays paint on a wall near the entrance', condition: 'Spray painting' }, detector: wv.config.detector, region: wv.config.region, schedule: { intervalMinutes: 30, windowSeconds: 15 }, quota: { perDay: 6 } } }) });
    const a = await put(wv.version); const b = await put(wv.version);
    return [a.status, b.status, (await b.json()).error.code];
  }, `Entrance wall ${T}`);
  ok(`${w} stale Watch revision is refused`, stale[0] === 200 && stale[1] === 409 && stale[2] === 'stale_version', JSON.stringify(stale));
  await page.reload();
  await page.getByRole('button', { name: 'Pause' }).click();
  await page.getByText('Paused').first().waitFor();
  await page.getByRole('button', { name: 'Disable' }).click();
  await page.getByText('Disabled').first().waitFor();
  ok(`${w} Watch can be paused and disabled`, (await page.getByRole('button', { name: 'Assess the latest window now' }).isDisabled()));

  // archive page keeps historical experiments out of the workflow
  await page.getByRole('link', { name: 'Evidence archive' }).click();
  await page.getByRole('heading', { name: 'Evidence archive' }).waitFor();
  ok(`${w} archive separates authentic records from historical experiments`, /Authentic records/.test(await text('.page')) && /Historical experiments/.test(await text('.page')) && /not Watches/.test(await text('.page')));
  await shot('archive');
  await page.getByRole('link', { name: 'Exceptions', exact: true }).click();
  await page.locator('.qrow').first().waitFor();
  await shot('exceptions');
  ok(`${w} no console or page errors`, problems.length === 0, problems.join(' | '));
  await ctx.close();
}

for (const [w, h] of [[1440, 900], [1920, 1080]]) await run(w, h);
await browser.close();
console.log(`${checks - failures}/${checks} checks passed`);
process.exit(failures ? 1 : 0);
