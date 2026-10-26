import assert from 'node:assert/strict';
import {writeFile} from 'node:fs/promises';
import {chromium} from 'playwright';
const browser=await chromium.launch({channel:'msedge',headless:true});
const context=await browser.newContext({viewport:{width:1440,height:900}});const page=await context.newPage();
try {
 await page.goto('http://127.0.0.1:8771',{waitUntil:'networkidle'});
 await page.getByRole('button',{name:'New demo session',exact:true}).click();
 await page.getByRole('button',{name:'Next observation',exact:true}).click();
 await page.locator('.incident-list .button').first().click();
 await page.getByRole('button',{name:'Mark reviewed',exact:true}).waitFor();
 await page.getByRole('button',{name:'Next observation',exact:true}).click();
 await page.getByText('2 / 6 candidate observations',{exact:false}).waitFor();
 const response=page.waitForResponse(r=>r.url().endsWith('/decisions'));
 await page.getByRole('button',{name:'Mark reviewed',exact:true}).click();
 const result=await response;assert.equal(result.status(),409);
 await page.getByRole('status').filter({hasText:'Decision rejected. Reload evidence and retry.'}).waitFor();
 await page.screenshot({path:'runs/recovery-capture/original-failure.png',fullPage:true});
 const id=page.url().split('/').at(-1);const current=await(await page.request.get(`http://127.0.0.1:8771/api/incidents/${id}`)).json();
 const report={revision:'3b14be9 frontend',actualHTTPStatus:result.status(),browserObservationIds:result.request().postDataJSON().evidence,serverObservationIds:current.observations.map(o=>o.observationId),savedDecisions:current.decisions.length,message:'Decision rejected. Reload evidence and retry.'};
 await writeFile('runs/recovery-capture/original-failure.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
} finally {await context.close();await browser.close();}
