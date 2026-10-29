// Real-browser walkthrough of the exception and review workflow against the RUNNING Ortru server (not a fixture).
// It never saves a decision and never sends anything: the form is filled but not submitted, and the three write
// attempts it makes are ones the server must refuse (stale revision, missing confirmation, repeat of a sent event).
// Usage: bun scripts/walkthrough-gate1.mjs <outDir> [baseUrl]
import { chromium } from 'playwright';
import { mkdirSync } from 'node:fs';

const [out = '../runs/ortru/shots-gate1', base = 'http://127.0.0.1:8790'] = process.argv.slice(2);
try { mkdirSync(out, { recursive: true }); } catch { /* bun reports EEXIST on Windows */ }
const SENT = 'b586966c61d7460c997bcc47b0a3ce38';
const browser = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true, args: ['--no-first-run'] });
let failures = 0;
const ok = (name, cond, extra = '') => { if (!cond) { failures++; console.log('FAIL', name, extra); } else console.log('ok  ', name); };

async function run(w, h) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h } });
  const page = await ctx.newPage();
  const problems = [];
  page.on('console', (m) => { if (m.type() === 'error' && !/status of (422|409)/.test(m.text())) problems.push('console: ' + m.text()); });
  page.on('pageerror', (e) => problems.push('pageerror: ' + e.message));
  const shot = (n) => page.screenshot({ path: `${out}/${w}-${n}.png`, fullPage: false });
  const text = async (sel) => (await page.locator(sel).first().innerText()).trim();
  console.log(`--- ${w}x${h}`);

  await page.goto(base);
  await page.getByRole('heading', { name: 'Exceptions' }).waitFor();
  ok(`${w} brand and three navigation links`, (await text('.brand')) === 'Ortru' && (await page.locator('nav a').count()) === 3);
  const status = await text('.status');
  ok(`${w} sending on and Hafnia sign-in absent are both stated`, /sending on/.test(status) && !/Hafnia connected/.test(status), status);

  // queue: four live exceptions, only the reviewed one is sent, three open
  await page.locator('.qrow').first().waitFor();
  const rows = page.locator('.queue ul').first().locator('.qrow');
  ok(`${w} four live exceptions, none hidden by grouping`, (await rows.count()) === 4, String(await rows.count()));
  ok(`${w} three open, one sent`, /3 open/.test(await text('.qhead')) && (await page.locator('.queue ul').first().getByText('Sent to XProtect').count()) === 1);
  ok(`${w} earlier verified records listed apart`, (await page.locator('.qgroup + ul .qrow').count()) === 2);
  await shot('queue');

  // the sent, AI-reviewed exception
  await rows.filter({ hasText: '12:42:29' }).or(rows.nth(3)).first().click();
  await page.locator('.inv-head').waitFor();
  await page.locator('.decision-bar.done').waitFor();
  const steps = await text('.steps');
  ok(`${w} Event Server accepted and Smart Client not verified are separate steps`, /Accepted/.test(steps) && /Not verified yet/.test(steps), steps);
  ok(`${w} the review is shown as the AI reviewer's, not a person's`, /Claude, AI demo reviewer \(not a human\)|not a human/.test(await page.locator('.sources, .decision-bar, .prov').allInnerTexts().then((a) => a.join(' '))));
  ok(`${w} no send button for an event already sent`, (await page.getByRole('button', { name: /send to XProtect/i }).count()) === 0);
  const repeat = await text('.decision-bar .notice, .decision-bar [class*=notice]');
  ok(`${w} repeat notice names the other three assessments`, /Same visual event as 3 other assessments/.test(repeat) && /sent to XProtect/.test(repeat), repeat);
  await page.locator('details.history summary').click();
  const hist = await text('details.history');
  ok(`${w} history lists revision 2 and says revision 1 is not available`, /Revision 2/.test(hist) && /Revision 1/.test(hist) && /cannot be reconstructed/.test(hist) && /append-only/.test(hist), hist);
  await page.waitForFunction(() => document.querySelector('video')?.readyState >= 2);
  ok(`${w} the recording plays`, (await page.evaluate(() => document.querySelector('video').duration)) > 11);
  ok(`${w} detector box drawn at the trigger sample`, (await page.locator('.detbox').count()) === 1);
  await shot('sent-reviewed');
  await page.locator('.decision-bar').scrollIntoViewIfNeeded();
  await shot('sent-reviewed-decision');

  // an open sibling: form rules, nothing saved
  await rows.first().click();
  await page.locator('form.decision-bar').waitFor();
  const send = page.getByRole('button', { name: /Send to XProtect/ });
  const dismiss = page.getByRole('button', { name: 'Dismiss' });
  ok(`${w} open exception shows the same-event notice and no history`, /Assessment 4 of 4|Assessment \d of 4/.test(await text('form.decision-bar')) && (await page.locator('details.history').count()) === 0);
  ok(`${w} actions disabled until a verdict, a note and watching are given`, await send.isDisabled() && await dismiss.isDisabled());
  await page.locator('.seg label', { hasText: /: yes$/ }).click();
  ok(`${w} still disabled with a verdict only`, await send.isDisabled());
  await page.getByLabel('Note').fill('Person at the platform edge (walkthrough, not saved)');
  ok(`${w} still disabled without confirming the footage was watched`, await send.isDisabled());
  await page.locator('label.check', { hasText: 'I watched the relevant footage' }).click();
  ok(`${w} enabled once complete (not clicked)`, await send.isEnabled() && await dismiss.isEnabled());
  await shot('open-filled-not-saved');

  // server-side refusals, from the page's own session
  const res = await page.evaluate(async ({ SENT }) => {
    const boot = await (await fetch('/api/ortru')).json();
    const post = async (path, body) => { const r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Ortru-CSRF': boot.csrf }, body: JSON.stringify(body) }); return [r.status, (await r.json()).error]; };
    const q = (await (await fetch('/api/queue')).json()).data.live;
    const open = q.find((x) => x.decision === 'undecided').id;
    return {
      stale: await post(`/api/exceptions/${SENT}/decision`, { expectedRevision: 0, verdict: 'visible', note: 'x', watchedFootage: true, outcome: 'dismiss' }),
      unwatched: await post(`/api/exceptions/${open}/decision`, { expectedRevision: 0, verdict: 'visible', note: 'x', watchedFootage: false, outcome: 'dismiss' }),
      repeatSend: await post(`/api/exceptions/${open}/native`, { action: 'send', confirmed: true, approval: 'deadbeefdeadbeef' }),
      history: (await (await fetch(`/api/exceptions/${SENT}/history`)).json()).data.revisions.map((r) => [r.revision, r.available]),
      frame: (await fetch(`/api/exceptions/${open}/frames/0`)).status, video: (await fetch(`/api/exceptions/${open}/video`)).status,
    };
  }, { SENT });
  ok(`${w} stale revision refused (409)`, res.stale[0] === 409, JSON.stringify(res.stale));
  ok(`${w} missing footage confirmation refused (422)`, res.unwatched[0] === 422, JSON.stringify(res.unwatched));
  ok(`${w} repeat of an already-sent event refused without acknowledgement`, res.repeatSend[0] === 422 && /already sent/.test(res.repeatSend[1].message), JSON.stringify(res.repeatSend));
  ok(`${w} history unchanged by the refused writes`, JSON.stringify(res.history) === '[[1,false],[2,true]]', JSON.stringify(res.history));
  ok(`${w} evidence frame and recording of an open exception are served`, res.frame === 200 && res.video === 200);

  // archive record stays read only
  await page.locator('.qgroup + ul .qrow').first().click();
  await page.locator('.decision-bar.readonly').waitFor();
  ok(`${w} archive record read only`, (await page.getByRole('button', { name: /Send to XProtect/ }).count()) === 0);

  // Watches: all schedules paused
  await page.locator('nav a', { hasText: 'Watches' }).click();
  await page.locator('.page .cards.watches').waitFor();
  const watches = await page.locator('.page').first().innerText();
  ok(`${w} Watches page shows paused schedules and nothing running`, /paused/i.test(watches) && !/\bactive\b/i.test(watches.replace(/inactive/gi, '')), watches.slice(0, 300));
  await shot('watches');
  ok(`${w} no unexpected console or page errors`, problems.length === 0, problems.join(' | '));
  await ctx.close();
}

await run(1440, 900);
await run(390, 844);
await browser.close();
console.log(failures ? `${failures} failed` : 'all checks passed');
process.exit(failures ? 1 : 0);
