// Screenshots of the REAL Ortru server (read only: navigation and client-side drawing, no saves, no sends).
// Usage: bun scripts/shoot-real.mjs <outDir> [baseUrl]
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';

const [out = '../runs/ortru/real', base = 'http://127.0.0.1:8790'] = process.argv.slice(2);
try { mkdirSync(out, { recursive: true }); } catch { /* bun reports EEXIST on Windows */ }
const browser = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true, args: ['--no-first-run'] });
for (const [w, h] of [[1440, 900], [1920, 1080]]) {
  const page = await (await browser.newContext({ viewport: { width: w, height: h } })).newPage();
  const problems = [];
  page.on('console', (m) => { if (m.type() === 'error') problems.push(m.text()); });
  page.on('pageerror', (e) => problems.push(e.message));
  const shot = (n) => page.screenshot({ path: `${out}/${w}-${n}.png` });
  await page.goto(base);
  await page.locator('.qrow').first().waitFor();
  await page.waitForFunction(() => document.querySelector('video')?.readyState >= 2);
  await shot('exceptions-record');
  await page.getByRole('link', { name: /^Watches/ }).click();
  await page.locator('.card').first().waitFor();
  await shot('watches');
  await page.locator('.card', { hasText: 'Station platform' }).first().click();
  await page.getByRole('heading', { name: /Station platform/ }).waitFor();
  await shot('watch-station');
  await page.locator('.watch-page').screenshot({ path: `${out}/${w}-watch-station-clip.png` });
  await page.getByRole('link', { name: /^Watches/ }).click();
  await page.locator('.card', { hasText: 'School gate' }).first().click();
  await page.getByRole('heading', { name: /School gate/ }).waitFor();
  await shot('watch-gate');
  await page.locator('.watch-page').screenshot({ path: `${out}/${w}-watch-gate-clip.png` });
  await page.getByRole('link', { name: /^Watches/ }).click();
  await page.getByRole('button', { name: 'Create Watch' }).click();
  await page.getByLabel('Authorized XProtect camera').selectOption({ label: 'Person on railway tracks' });
  await page.locator('.snap img').waitFor();
  await page.getByLabel('Name this Watch').fill('Platform edge');
  await page.getByLabel('What should Hafnia look for?').fill('A person climbs down from the platform edge onto the railway track area');
  await page.getByLabel('Name the visible condition').fill('Person on the track area');
  const bb = await page.locator('.snap').boundingBox();
  for (const [fx, fy] of [[0.3, 0.34], [0.98, 0.68], [0.98, 0.98], [0.62, 0.98]]) await page.mouse.click(bb.x + bb.width * fx, bb.y + bb.height * fy);
  await page.waitForTimeout(300);
  await shot('create-watch');
  await page.locator('.editor').screenshot({ path: `${out}/${w}-create-watch-clip.png` });
  await page.getByRole('link', { name: 'Evidence archive' }).click();
  await page.getByRole('heading', { name: 'Evidence archive' }).waitFor();
  await shot('archive');
  if (problems.length) console.log(w, 'PROBLEMS', problems);
}
await browser.close();
console.log('done');
