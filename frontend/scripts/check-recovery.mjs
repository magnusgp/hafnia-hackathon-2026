import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import { chromium } from 'playwright';
const base=process.env.REVIEW_URL || 'http://127.0.0.1:8770';
const out=new URL('../../runs/recovery-capture/',import.meta.url);
const local=u=>decodeURIComponent(u.pathname.replace(/^\/(\w:)/,'$1'));
await mkdir(out,{recursive:true});
const browser=await chromium.launch({channel:'msedge',headless:true});
const reports=[];
try {
for(const [width,height] of [[1440,900],[1920,1080]]) {
 const context=await browser.newContext({viewport:{width,height},recordVideo:{dir:local(out),size:{width,height}}});
 const page=await context.newPage(); const errors=[],statuses=[],external=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(!r.url().startsWith(base+'/'))external.push(r.url());});
 page.on('response',r=>{if(r.url().includes('/api/') && r.request().method()==='POST') statuses.push({path:new URL(r.url()).pathname,status:r.status()});});
 async function post(path,body={}) {return page.evaluate(async ({path,body})=>{
  const session=await (await fetch('/api/session')).json(); const demo=await (await fetch('/api/demo')).json();
  const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-AW-CSRF':session.csrf},body:JSON.stringify({demoSession:demo.session,cursor:demo.cursor,...body})});return r.status;
 },{path,body});}
 await page.goto(base,{waitUntil:'networkidle'});
 await page.getByRole('heading',{name:'Incidents',exact:true}).waitFor();
 assert.equal(await page.getByRole('button',{name:'Start replay',exact:true}).count(),0);
 await page.getByRole('link',{name:'Demo mode',exact:true}).click();
 await page.getByRole('button',{name:'New demo session',exact:true}).click();
 await page.getByText('0 / 6 candidate observations',{exact:false}).waitFor();
 await page.route('**/api/demo/next',async route=>{
  assert.ok(await page.getByRole('button',{name:'Next observation',exact:true}).isDisabled());
  await route.continue({postData:JSON.stringify({...route.request().postDataJSON(),cursor:-1})});
 },{times:1});
 await page.getByRole('button',{name:'Next observation',exact:true}).click();
 await page.getByRole('alert').filter({hasText:'Replay action was not completed (HTTP 409)'}).waitFor();
 await page.getByRole('button',{name:'Next observation',exact:true}).click();
 await page.locator('.incident-list .button').first().click();
 await page.locator('.frame img').evaluate(i=>i.decode());
 const id=page.url().split('/').at(-1);
 const note=page.getByRole('textbox',{name:'Review note',exact:true});
 await note.fill('Reviewed source samples and recorded Hafnia interpretation.');
 // Another browser/backend advances while this investigation stays open.
 assert.equal(await post('/api/demo/next'),200);
 await page.getByRole('status').filter({hasText:'Evidence changed: another observation'}).waitFor();
 await page.getByText('2 observations',{exact:false}).waitFor();
 assert.equal(await note.inputValue(),'Reviewed source samples and recorded Hafnia interpretation.');
 await page.screenshot({path:local(new URL(`updated-${width}.png`,out)),fullPage:true});
 // Deterministic race: advance immediately before the pending decision reaches the server.
 await page.route('**/decisions',async route=>{assert.ok(await page.getByRole('button',{name:'Save review',exact:true}).isDisabled());assert.ok(await page.getByRole('button',{name:'Dismiss incident',exact:true}).isDisabled());assert.equal(await post('/api/demo/next'),200);await route.continue();},{times:1});
 const conflict=page.waitForResponse(r=>r.url().endsWith('/decisions') && r.status()===409);
 await page.getByRole('button',{name:'Save review',exact:true}).click();
 await conflict;
 await page.getByRole('status').filter({hasText:'Decision was not saved (HTTP 409)'}).waitFor();
 let e=await (await page.request.get(base+`/api/incidents/${id}`)).json();
 assert.equal(e.decisions.length,0);assert.equal(e.observationCount,3);
 await page.getByRole('button',{name:'Save review',exact:true}).click();
 await page.getByRole('status').filter({hasText:'Review saved.'}).waitFor();
 assert.equal(await page.getByRole('button',{name:'Escalate to XProtect',exact:true}).count(),0);
 await page.getByText('Unavailable in replay',{exact:true}).waitFor();
 assert.equal(await post(`/api/incidents/${id}/native-action/prepare`),409);
 const unauthorized=await page.request.post(base+`/api/incidents/${id}/native-action/confirm`,{headers:{Origin:base},data:{confirmed:true}});assert.equal(unauthorized.status(),403);
 statuses.push({path:'/native-action/confirm without CSRF',status:unauthorized.status()});
 assert.equal(await post(`/api/incidents/${id}/native-action/confirm`,{confirmed:true,token:'unauthorized'}),409);
 // Playback controls, scrubber, localization, region, timeline and assessment picker.
 await page.getByRole('button',{name:'Play samples',exact:true}).click();
 await page.getByRole('button',{name:'Pause',exact:true}).click();
 await page.getByRole('slider',{name:'Recording sample'}).fill('0');
 await page.getByRole('checkbox',{name:'Selected CV box',exact:true}).uncheck();
 await page.getByRole('checkbox',{name:'Selected CV box',exact:true}).check();
 await page.getByRole('checkbox',{name:'Draft region',exact:false}).check();
 await page.getByRole('button',{name:'Final sample',exact:false}).click();
 await page.getByRole('button',{name:'First sample',exact:false}).click();
 await page.getByRole('button',{name:'Selected stationary candidate',exact:false}).click();
 await page.getByRole('combobox',{name:'Hafnia assessment'}).selectOption('0');
 await page.getByRole('button',{name:'Dismiss incident',exact:true}).click();
 await page.getByRole('status').filter({hasText:'Incident dismissed.'}).waitFor();
 assert.ok(await page.getByRole('button',{name:'Dismiss incident',exact:true}).isDisabled());
 assert.ok(await page.getByRole('button',{name:'Save review',exact:true}).isDisabled());
 await page.reload({waitUntil:'networkidle'});
 e=await (await page.request.get(base+`/api/incidents/${id}`)).json();assert.equal(e.state,'dismissed');assert.equal(e.decisions.length,2);
 await page.getByRole('link',{name:'Incidents',exact:false}).first().click();
 assert.equal(await page.locator('.incident-list article').count(),0);
 await page.getByRole('link',{name:'Incident history',exact:true}).click();
 await page.locator(`a[href="#/investigation/${id}"]`).click();
 await page.getByRole('button',{name:'Save review',exact:true}).waitFor();
 await page.getByRole('link',{name:'Demo mode',exact:true}).click();
 await page.getByRole('button',{name:'Continue replay',exact:true}).click();
 assert.ok(await page.getByRole('button',{name:'Next observation',exact:true}).isDisabled());
 await page.getByRole('button',{name:'Pause replay',exact:true}).click();
 await page.getByRole('button',{name:'Continue replay',exact:true}).click();
 await page.getByText('6 / 6 candidate observations',{exact:false}).waitFor({timeout:15000});
 assert.ok(await page.getByRole('button',{name:'Continue replay',exact:true}).isDisabled());
 assert.ok(await page.getByRole('button',{name:'Next observation',exact:true}).isDisabled());
 assert.ok(await page.getByRole('button',{name:'Pause replay',exact:true}).isDisabled());
 const index=await (await page.request.get(base+'/api/incidents')).json();
 assert.equal(index.records.length,2);assert.deepEqual(index.records.map(r=>r.observationCount),[3,3]);
 await page.locator('.incident-list .button').first().click();
 await page.locator('.frame img').evaluate(i=>i.decode());
 await page.getByRole('button',{name:'Save review',exact:true}).click();
 await page.getByRole('status').filter({hasText:'Review saved.'}).waitFor();
 await page.screenshot({path:local(new URL(`decision-${width}.png`,out)),fullPage:true});
 assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(errors,[]);assert.deepEqual(external,[]);
 reports.push({width,height,errors,external,statuses,staleConflictDidNotSave:true,dismissalPersisted:true,duplicateIncidents:false});
 await context.close();await page.video().saveAs(local(new URL(`interaction-${width}.webm`,out)));
}
await writeFile(new URL('browser-report.json',out),JSON.stringify(reports,null,2));console.log(JSON.stringify(reports,null,2));
}finally{await browser.close();}
