// Drive a real New assessment in the browser and record it. Usage: bun live-run.mjs <outDir> [baseUrl]
// Pauses at the continuity step until <outDir>/confirm.flag exists (the reviewer watches the recording first).
import { chromium } from 'playwright';
import { mkdir, rename } from 'node:fs/promises';
import { existsSync } from 'node:fs';
const out = process.argv[2], base = process.argv[3] ?? 'http://127.0.0.1:8780';
await mkdir(out).catch(() => {});
const browser = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true, args: ['--no-first-run'] });
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, recordVideo: { dir: out, size: { width: 1920, height: 1080 } } });
const page = await ctx.newPage();
const t0 = Date.now();
const log = m => console.log(((Date.now() - t0) / 1000).toFixed(1), m);
await page.goto(base + '/#/railway', { waitUntil: 'networkidle' });
await page.getByRole('button', { name: 'New assessment' }).click();
const dlg = page.getByRole('dialog');
log('dialog: ' + (await dlg.innerText()).replace(/\n/g, ' ').slice(0, 200));
await page.waitForTimeout(1500);
await dlg.getByRole('button', { name: 'Start assessment' }).click();
log('started');
let last = '';
for (let i = 0; i < 400; i++) {
  await page.waitForTimeout(1500);
  const text = (await dlg.innerText().catch(() => '')).replace(/\n+/g, ' | ');
  if (text !== last) { last = text; log(text.slice(0, 400)); }
  if (await dlg.getByRole('button', { name: /Continuous/ }).count()) {
    log('AWAITING_CONTINUITY');
    while (!existsSync(`${out}/confirm.flag`)) await page.waitForTimeout(1000);
    await dlg.getByRole('button', { name: /Continuous/ }).click();
    log('continuity confirmed');
  }
  if (await dlg.getByRole('button', { name: 'Open result' }).count()) { log('COMPLETED'); break; }
  if (await dlg.locator('[role=alert]').count()) { log('FAILED: ' + (await dlg.locator('[role=alert]').first().innerText())); break; }
}
if (await dlg.getByRole('button', { name: 'Open result' }).count()) {
  await page.waitForTimeout(1500);
  await dlg.getByRole('button', { name: 'Open result' }).click();
  await page.waitForSelector('video');
  await page.waitForTimeout(3500);
  await page.screenshot({ path: `${out}/result.png` });
  log('result opened: ' + page.url());
}
const video = page.video();
await ctx.close(); await browser.close();
await rename(await video.path(), `${out}/live.webm`);
log('done');
