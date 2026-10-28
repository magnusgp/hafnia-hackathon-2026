// Capture real rendered screenshots of the running app. Usage: bun shoot.mjs <outDir> [url]
import { chromium } from 'playwright';
import { mkdir } from 'node:fs/promises';
const out = process.argv[2], base = process.argv[3] ?? 'http://127.0.0.1:8780';
await mkdir(out, { recursive: true });
const browser = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true, args: ['--no-first-run'] });
for (const [w, h] of [[1440, 900], [1920, 1080]]) {
  const page = await browser.newPage({ viewport: { width: w, height: h } });
  const errors = [];
  page.on('pageerror', e => errors.push(e.message));
  await page.goto(base + '/#/railway', { waitUntil: 'networkidle' });
  await page.waitForSelector('video');
  await page.waitForFunction(() => { const v = document.querySelector('video'); return v && v.readyState >= 2 && Math.abs(v.currentTime - 5.4) < 0.2; });
  await page.evaluate(() => document.fonts.ready);
  await page.screenshot({ path: `${out}/railway-${w}.png` });
  console.log(w, 'errors', errors, await page.evaluate(() => ({ sh: document.documentElement.scrollHeight, ih: innerHeight })));
  await page.close();
}
await browser.close();
