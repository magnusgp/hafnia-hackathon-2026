// Screenshot every slide of the Ortru deck at 1920x1080 with all its steps shown: bun scripts/shoot-deck.mjs <outDir>
import { chromium } from 'playwright';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
import { mkdirSync } from 'node:fs';
const [out = '../runs/ortru/deck'] = process.argv.slice(2);
try { mkdirSync(out, { recursive: true }); } catch { /* bun reports EEXIST on Windows */ }
const browser = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true, args: ['--no-first-run', '--allow-file-access-from-files'] });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
const errors = [];
page.on('pageerror', (e) => errors.push(e.message));
await page.goto(pathToFileURL(resolve('../presentation/ortru/index.html')).href);
const n = await page.locator('.slide').count();
for (let k = 0; k < n; k++) {
  await page.evaluate((k) => { location.hash = `#${k + 1}`; location.reload(); }, k);
  await page.waitForTimeout(500);
  const steps = await page.locator('.slide.on [data-step]').count();
  for (let s = 0; s < steps; s++) await page.keyboard.press('ArrowRight');
  await page.waitForTimeout(800);
  await page.screenshot({ path: `${out}/slide-${String(k + 1).padStart(2, '0')}.png` });
}
await browser.close();
console.log(n, 'slides', errors.length ? errors : 'no page errors');
