// Record the real application (isolated demo instance) for the presentation. Usage:
//   bun capture-walkthrough.mjs <outDir> [baseUrl]
// The demo instance has its own review store, so the operator's saved decision is never touched.
import { chromium } from 'playwright';
import { mkdir, readdir, rename } from 'node:fs/promises';
const out = process.argv[2], base = process.argv[3] ?? 'http://127.0.0.1:8781';
await mkdir(out, { recursive: true });
const browser = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true, args: ['--no-first-run'] });
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, recordVideo: { dir: out, size: { width: 1920, height: 1080 } } });
const page = await ctx.newPage();
const t0 = Date.now();
const mark = label => console.log(((Date.now() - t0) / 1000).toFixed(1), label);
await page.goto(base + '/#/railway', { waitUntil: 'networkidle' });
await page.waitForFunction(() => { const v = document.querySelector('video'); return v && v.readyState >= 2 && Math.abs(v.currentTime - 5.4) < 0.2; });
await page.evaluate(() => document.fonts.ready);
mark('opened at the trigger sample');
await page.waitForTimeout(3500);
await page.getByRole('button', { name: 'Play from the trigger' }).click();
await page.waitForFunction(() => document.querySelector('video').paused && document.querySelector('video').currentTime > 9.5, null, { timeout: 15000 });
mark('played to the climb');
await page.waitForTimeout(1500);
await page.getByRole('button', { name: 'Previous sample' }).click();
await page.waitForTimeout(900);
await page.getByRole('button', { name: 'Next sample' }).click();
await page.waitForTimeout(1500);
await page.getByRole('button', { name: /Person at the platform edge/ }).click();
await page.waitForTimeout(2200);
await page.getByRole('button', { name: 'Send to XProtect review' }).click();
await page.getByRole('dialog').waitFor();
await page.waitForTimeout(1200);
await page.getByLabel('Entry onto the tracks').check();
await page.getByLabel('Note').fill('Person lowers off the platform edge and walks away along the tracks.');
await page.getByLabel('I watched the relevant footage').check();
await page.waitForTimeout(1200);
await page.getByRole('button', { name: 'Save review request' }).click();
await page.getByRole('dialog').waitFor({ state: 'detached' });
mark('saved request');
await page.waitForTimeout(2500);
const send = page.getByRole('button', { name: 'Send to XProtect', exact: true });
if (await send.count()) {
  await send.click();
  await page.getByRole('dialog').waitFor();
  await page.waitForTimeout(3500);
  mark('send dialog shown (not confirmed)');
  await page.getByRole('button', { name: 'Cancel' }).click();
  await page.waitForTimeout(1200);
}
const video = page.video();
await ctx.close();
await browser.close();
const path = await video.path();
await rename(path, `${out}/walkthrough.webm`);
mark('done');
