// Screenshot any local HTML file: bun scripts/shot-html.mjs <file.html> <out.png> [width] [height]
import { chromium } from 'playwright';
import { pathToFileURL } from 'node:url';
import { resolve } from 'node:path';
const [file, out, w = '1440', h = '900'] = process.argv.slice(2);
const browser = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true, args: ['--no-first-run', '--allow-file-access-from-files'] });
const page = await browser.newPage({ viewport: { width: +w, height: +h } });
await page.goto(pathToFileURL(resolve(file)).href);
await page.waitForTimeout(400);
await page.screenshot({ path: out });
await browser.close();
