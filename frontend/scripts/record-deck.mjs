// Record the timed deck in a real browser. Usage: bun record-deck.mjs <outDir>
import { chromium } from 'playwright';
import { mkdir, rename } from 'node:fs/promises';
const out = process.argv[2];

await mkdir(out);
const url = 'file:///C:/Users/Administrator/dev/hafnia-hackathon-2026/presentation/index.html?auto=1&record=1';
const browser = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true, args: ['--allow-file-access-from-files', '--autoplay-policy=no-user-gesture-required'] });
const t0 = Date.now();
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 }, recordVideo: { dir: out, size: { width: 1920, height: 1080 } } });
const page = await ctx.newPage();
page.on('pageerror', e => console.log('pageerror', e.message));
await page.goto(url);
await page.waitForFunction(() => window.__deckReady === true);
await page.evaluate(() => document.fonts.ready);
await page.waitForTimeout(800);
const start = Date.now();
await page.evaluate(() => window.startDeck());
await page.waitForFunction(() => window.__deckDone === true, null, { timeout: 400000 });
await page.waitForTimeout(500);
const video = page.video();
await ctx.close(); await browser.close();
await rename(await video.path(), `${out}/deck.webm`);
console.log(JSON.stringify({ offset: (start - t0) / 1000 }));
