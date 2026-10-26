import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { chromium } from 'playwright';

const base = process.env.REVIEW_URL || 'http://127.0.0.1:8769';
const out = new URL('../../runs/operator-demo-capture/', import.meta.url);
await mkdir(out, {recursive:true});
const local = url => url.pathname.replace(/^\/(\w:)/, '$1');
const browser = await chromium.launch({channel:'msedge', headless:true});
const report = [];
try {
  for (const [width,height] of [[1440,900],[1920,1080]]) {
    const context = await browser.newContext({viewport:{width,height}, recordVideo:{dir:local(out),size:{width,height}}});
    const page = await context.newPage();
    const errors = [], external = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('request', request => {if (!request.url().startsWith(base)) external.push(request.url());});
    await page.goto(base+'/#/monitoring', {waitUntil:'networkidle'});
    await page.getByRole('button',{name:'New demo session'}).click();
    await page.getByText('0 / 6 candidate observations', {exact:false}).waitFor();
    await page.getByRole('button',{name:'Start replay',exact:true}).click();
    await page.getByText('6 / 6 candidate observations', {exact:false}).waitFor({timeout:20000});
    await page.getByRole('button',{name:'New demo session'}).waitFor({state:'visible'});
    const index = await (await page.request.get(base+'/api/incidents')).json();
    assert.equal(index.records.length,2);
    assert.deepEqual(index.records.map(r=>r.observationCount),[3,3]);
    assert.equal(await page.locator('.incident-list article').count(),2);
    await page.screenshot({path:local(new URL(`grouped-${width}.png`,out)),fullPage:true});
    for (let n=0;n<index.records.length;n++) {
      const record=index.records[n];
      await page.locator(`a[href="#/investigation/${record.id}"]`).click();
      await page.locator('.frame img').evaluate(img=>img.decode());
      const e=await (await page.request.get(base+`/api/incidents/${record.id}`)).json();
      assert.equal(e.evidenceKind,'replay');
      assert.equal(e.independentObservationCount,0);
      assert.equal(e.dispatchReviewReady,false);
      assert.ok(e.hafnia.length>0 && e.hafnia.every(h=>h.original_response));
      await page.getByRole('textbox',{name:'Review note',exact:true}).fill('Reviewed saved imagery and recorded interpretation.');
      await page.getByRole('button',{name:'Mark reviewed',exact:true}).click();
      await page.getByRole('status').filter({hasText:'Decision saved.'}).waitFor();
      const decided = page.waitForResponse(r=>r.url().endsWith('/decisions') && r.request().method()==='POST' && r.request().postDataJSON().action===(n===0?'dismiss':'request_escalation'));
      await page.getByRole('button',{name:n===0?'Dismiss':'Request escalation',exact:true}).click();
      assert.equal((await decided).status(),200);
      await page.getByRole('status').filter({hasText:n===0?'Decision saved.':'Escalation requested.'}).waitFor();
      await page.reload({waitUntil:'networkidle'});
      await page.locator('.frame img').evaluate(img=>img.decode());
      const saved=await (await page.request.get(base+`/api/incidents/${record.id}`)).json();
      assert.equal(saved.state,n===0?'dismissed':'review_required');
      assert.equal(saved.decisions.length,2);
      assert.equal(saved.alarmStatus,'unverified');
      await page.screenshot({path:local(new URL(`decision-${n}-${width}.png`,out)),fullPage:true});
      await page.getByRole('link',{name:'Monitoring',exact:false}).click();
    }
    assert.equal((await page.request.get(base+'/api/dispatch')).status(),404);
    assert.deepEqual(errors,[]);
    assert.deepEqual(external,[]);
    assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    report.push({width,height,incidents:2,observationsPerIncident:3,decisionsSurvivedReload:true,externalBrowserRequests:external,errors});
    await context.close();
    await page.video().saveAs(local(new URL(`lifecycle-${width}.webm`,out)));
  }
  await writeFile(new URL('browser-report.json',out),JSON.stringify(report,null,2));
  console.log(JSON.stringify(report,null,2));
} finally {await browser.close();}
