import assert from 'node:assert/strict';
import {mkdir,readFile,writeFile} from 'node:fs/promises';
import {chromium} from 'playwright';
const base=process.env.REVIEW_URL || 'http://127.0.0.1:8770';
const out=new URL('../../runs/recovery-capture/',import.meta.url);
const local=u=>decodeURIComponent(u.pathname.replace(/^\/(\w:)/,'$1'));
await mkdir(out,{recursive:true});const browser=await chromium.launch({channel:'msedge',headless:true});const report=[];
try {
for(const [width,height] of [[1440,900],[1920,1080]]) {
 const context=await browser.newContext({viewport:{width,height},recordVideo:{dir:local(out),size:{width,height}}});
 const page=await context.newPage();const errors=[],failed=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400)failed.push({url:r.url(),status:r.status()});});
 await page.goto(base,{waitUntil:'networkidle'});
 await page.getByRole('link',{name:'Demo mode',exact:true}).click();
 await page.getByRole('button',{name:'New demo session',exact:true}).click();
 await page.getByRole('button',{name:'Start replay',exact:true}).click();
 await page.locator('.incident-list .button').first().waitFor();
 await page.getByRole('button',{name:'Pause replay',exact:true}).click();
 await page.getByRole('button',{name:'Next observation',exact:true}).click();
 await page.getByRole('button',{name:'Continue replay',exact:true}).click();
 await page.locator('.incident-list .button').first().click();
 await page.locator('.frame img').evaluate(i=>i.decode());
 await page.getByRole('status').filter({hasText:'Evidence changed: another observation'}).waitFor();
 await page.waitForTimeout(2500);
 await page.getByRole('checkbox',{name:'Draft region',exact:false}).check();
 await page.getByRole('button',{name:'Play samples',exact:true}).click();
 await page.waitForTimeout(3000);
 const pause=page.getByRole('button',{name:'Pause',exact:true});if(await pause.count())await pause.click();
 await page.getByText('HAFNIA INTERPRETATION',{exact:true}).scrollIntoViewIfNeeded();
 await page.waitForTimeout(3000);
 await page.getByRole('textbox',{name:'Review note',exact:true}).scrollIntoViewIfNeeded();
 await page.getByRole('textbox',{name:'Review note',exact:true}).fill('Saved source imagery and Hafnia assessment reviewed. Pedestrian clearance still requires verification.');
 await page.getByRole('button',{name:'Save review',exact:true}).click();
 await page.getByRole('status').filter({hasText:'Review saved.'}).waitFor();
 await page.waitForTimeout(2500);
 await page.getByRole('button',{name:'Dismiss incident',exact:true}).click();
 await page.getByRole('status').filter({hasText:'Incident dismissed.'}).waitFor();
 await page.waitForTimeout(2000);
 await page.reload({waitUntil:'networkidle'});
 assert.ok(await page.getByRole('button',{name:'Save review',exact:true}).isDisabled());
 await page.getByRole('link',{name:'Incidents',exact:false}).first().click();
 await page.waitForTimeout(1500);
 await page.getByRole('link',{name:'Incident history',exact:true}).click();
 await page.waitForTimeout(1500);
 await page.screenshot({path:local(new URL(`clean-${width}.png`,out)),fullPage:true});
 assert.deepEqual(errors,[]);assert.deepEqual(failed,[]);
 const video=page.video();await context.close();const path=local(new URL(`operator-clean-${width}.webm`,out));await video.saveAs(path);
 const meta=await browser.newPage();const encoded=(await readFile(path)).toString('base64');
 const duration=await meta.evaluate(async encoded=>{
  const bytes=Uint8Array.from(atob(encoded),c=>c.charCodeAt(0));const v=document.createElement('video');v.src=URL.createObjectURL(new Blob([bytes],{type:'video/webm'}));
  await new Promise((resolve,reject)=>{v.onloadedmetadata=resolve;v.onerror=reject;});
  if(!Number.isFinite(v.duration)){v.currentTime=1e9;await new Promise(resolve=>{v.ontimeupdate=resolve;});}return v.duration;
 },encoded);await meta.close();assert.ok(duration<180);report.push({width,height,durationSeconds:duration,errors,failed,recording:path});
}
await writeFile(new URL('clean-recording-report.json',out),JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));
}finally{await browser.close();}
