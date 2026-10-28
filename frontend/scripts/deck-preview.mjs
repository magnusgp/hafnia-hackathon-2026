// Screenshot each deck scene in manual mode. Usage: bun deck-preview.mjs <outDir>
import { chromium } from 'playwright';
import { mkdir } from 'node:fs/promises';
const out = process.argv[2];
await mkdir(out, { recursive: true });
const root = 'file:///C:/Users/Administrator/dev/hafnia-hackathon-2026/presentation/index.html';
const browser = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true, args: ['--allow-file-access-from-files', '--autoplay-policy=no-user-gesture-required'] });
const page = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
page.on('pageerror', e => console.log('pageerror', e.message));
for (const id of ['open', 'silent', 'signal', 'how', 'built', 'close']) {
  await page.goto(`${root}#${id}`); await page.reload();
  await page.waitForTimeout(id === 'signal' ? 14000 : id === 'open' ? 6500 : 3500);
  await page.screenshot({ path: `${out}/${id}.png` });
}
await browser.close();
