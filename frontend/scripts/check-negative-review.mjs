import assert from 'node:assert/strict';
import {mkdir,copyFile,writeFile,readFile} from 'node:fs/promises';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';

const repo=fileURLToPath(new URL('../../',import.meta.url));
const out=new URL('../../runs/negative-review-checks/',import.meta.url);
await mkdir(out,{recursive:true});
const browser=await chromium.launch({channel:'msedge',headless:true});
const reports=[];
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function ready(base){for(let i=0;i<100;i++){try{if((await fetch(base+'/api/review')).ok)return;}catch{}await sleep(100);}throw new Error('Evidence server did not start');}

try{
for(const [width,height,port] of [[1440,900,8874],[1920,1080,8875]]){
 const root=new URL(`case-${width}/`,out);await mkdir(root,{recursive:true});
 await copyFile(new URL('../../runs/negative-result-review/review.sqlite3',import.meta.url),new URL('review.sqlite3',root));
 const server=spawn(repo+'/.venv/Scripts/python.exe',['-m','adaptive_watch.negative_review_api','--root',fileURLToPath(root),'--frontend','frontend/dist','--port',String(port)],{cwd:repo,windowsHide:true,stdio:'ignore'});
 const base=`http://127.0.0.1:${port}`;
 let context;
 try{
  await ready(base);
  context=await browser.newContext({viewport:{width,height},recordVideo:{dir:fileURLToPath(out),size:{width,height}}});
  const page=await context.newPage();const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base,{waitUntil:'networkidle'});
  const data=(await (await page.request.get(base+'/api/review')).json()).review;
  assert.equal(data.frames.length,26);assert.equal(data.hafnia.outcome,'not_observed');
  assert.equal(data.hafnia.summaryId,'5a1ab040-fc44-4156-ad7a-1eeecd8c7b60');
  await page.waitForFunction(()=>document.querySelector('video')?.readyState>=2);
  assert.equal(await page.locator('video').evaluate(v=>v.duration),13);
  assert.ok(await page.getByRole('button',{name:'Review footage',exact:true}).isVisible());
  assert.equal(await page.getByRole('button',{name:'Dismiss',exact:true}).count(),0);
  assert.ok(!(await page.locator('main').innerText()).includes('sha256'));
  await page.screenshot({path:fileURLToPath(new URL(`review-${width}.png`,out)),fullPage:true});
  // Exact encoded frame index, UTC label and box coordinates must agree after seeking.
  const aligned=[];
  for(const index of [7,8,11,18,19,25]){
   await page.locator('video').evaluate((v,time)=>{v.pause();v.currentTime=time;},index*.5);
   await page.waitForFunction(i=>{const v=document.querySelector('video');return v&&!v.seeking&&Math.abs(v.currentTime-i*.5)<.001;},index);
   await page.waitForFunction(stamp=>document.querySelector('.media-caption time')?.textContent===stamp,data.frames[index].timestamp.slice(11,23)+' UTC');
   const box=await page.locator('[data-track="7"]').count();
   assert.equal(box,Number(Boolean(data.frames[index].box)));
   if(box){const x=Number(await page.locator('[data-track="7"]>rect').first().getAttribute('x'));assert.ok(Math.abs(x-data.frames[index].box[0]*832)<.001);assert.equal(await page.locator('[data-track="7"]').getAttribute('data-frame'),String(index));}
   aligned.push(index);
  }
  await page.getByRole('button',{name:'Proximity observation',exact:false}).click();
  await page.getByRole('checkbox',{name:'Show CV overlay'}).uncheck();
  await page.locator('video').evaluate(v=>{v.currentTime=0;return v.play();});
  await page.waitForTimeout(width===1920?13200:800);
  await page.locator('video').evaluate(v=>v.pause());
  await page.screenshot({path:fileURLToPath(new URL(`original-${width}.png`,out)),fullPage:true});
  await page.getByRole('checkbox',{name:'Show CV overlay'}).check();
  await page.locator('video').evaluate(v=>{v.currentTime=0;return v.play();});
  await page.waitForTimeout(width===1920?13200:800);
  await page.locator('video').evaluate(v=>v.pause());
  await page.getByRole('button',{name:'Proximity observation',exact:false}).click();
  await page.waitForTimeout(300);
  await page.screenshot({path:fileURLToPath(new URL(`overlay-${width}.png`,out)),fullPage:true});
  await page.getByRole('button',{name:'Evidence details',exact:true}).click();
  await page.getByRole('dialog').waitFor();
  assert.ok((await page.getByRole('dialog').innerText()).includes(data.hafnia.summaryId));
  assert.ok((await page.getByRole('dialog').innerText()).includes('not human-verified'));
  if(width===1440){
   await page.getByRole('button',{name:'Draw region on footage',exact:true}).click();
   let corner=0;
   for(const [x,y] of data.state.region.polygon){
    const point=await page.locator('svg[aria-label="Draw attention region"]').evaluate((svg,p)=>{const matrix=svg.getScreenCTM();const point=new DOMPoint(Math.min(p[0],.999)*832,Math.min(p[1],.999)*480).matrixTransform(matrix);return {x:point.x,y:point.y};},[x,y]);
    await page.mouse.click(point.x,point.y);
    await page.waitForFunction(n=>document.querySelectorAll('[data-corner]').length===n,++corner);
   }
   await page.getByRole('button',{name:'Save region',exact:true}).click();
   await page.waitForFunction(()=>!document.querySelector('.drawing'));
  }else await page.getByRole('button',{name:'Close',exact:true}).click();
  await page.getByRole('button',{name:'Review footage',exact:true}).click();
  await page.waitForTimeout(width===1920?13200:800);
  await page.locator('video').evaluate(v=>v.pause());
  assert.ok(await page.getByRole('button',{name:'Request XProtect review',exact:true}).isDisabled());
  await page.getByLabel('Review note',{exact:true}).fill('Workflow check only; entry remains unverified.');
  await page.getByRole('checkbox',{name:'I have reviewed the relevant footage'}).check();
  await page.getByRole('button',{name:'Request XProtect review',exact:true}).click();
  await page.getByRole('heading',{name:'Review request saved',exact:true}).waitFor();
  await page.reload({waitUntil:'networkidle'});
  assert.ok(await page.getByText('No native event has been sent.',{exact:false}).isVisible());
  let saved=(await (await page.request.get(base+'/api/review')).json()).review;
  assert.equal(saved.state.status,'xprotect_review_requested');assert.equal(saved.state.humanAnnotation.value,'not_verified');
  assert.equal(saved.native.dispatchAvailable,false);
  await page.screenshot({path:fileURLToPath(new URL(`requested-${width}.png`,out)),fullPage:true});
  await page.getByRole('button',{name:'Review footage again',exact:true}).click();
  await page.getByRole('checkbox',{name:'I have reviewed the relevant footage'}).check();
  await page.getByRole('button',{name:'Dismiss',exact:true}).click();
  await page.getByRole('heading',{name:'Review dismissed',exact:true}).waitFor();
  await page.reload({waitUntil:'networkidle'});
  assert.ok(await page.getByRole('heading',{name:'Review dismissed',exact:true}).isVisible());
  // A real stale revision from a second operator window must be rejected.
  const stale=await page.request.get(base+'/api/review');const session=await stale.json();
  const action={method:'POST',headers:{'Content-Type':'application/json','X-Review-CSRF':session.csrf},data:{action:'review',revision:session.review.revision}};
  assert.equal((await page.request.fetch(base+'/api/review/action',action)).status(),200);
  assert.equal((await page.request.fetch(base+'/api/review/action',action)).status(),409);
  await page.getByRole('button',{name:'Review footage again',exact:true}).click();
  await page.getByRole('alert').filter({hasText:'Evidence or review changed'}).waitFor();
  assert.ok(await page.getByRole('button',{name:'Request XProtect review',exact:true}).isDisabled());
  assert.equal((await page.request.post(base+'/api/review/native/confirm',{data:{confirmed:true}})).status(),403);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>window.innerWidth),false);
  assert.deepEqual(errors,[]);
  const video=page.video();await context.close();context=null;
  const recording=new URL(`operator-${width}.webm`,out);await video.saveAs(fileURLToPath(recording));
  // Verify duration from the actual recording, including WebM's optional unknown-duration form.
  const meta=await browser.newPage();const encoded=(await readFile(recording)).toString('base64');
  const duration=await meta.evaluate(async encoded=>{const v=document.createElement('video');const bytes=Uint8Array.from(atob(encoded),c=>c.charCodeAt(0));v.src=URL.createObjectURL(new Blob([bytes],{type:'video/webm'}));await new Promise((ok,no)=>{v.onloadedmetadata=ok;v.onerror=no;});if(!Number.isFinite(v.duration)){v.currentTime=1e9;await new Promise(ok=>v.ontimeupdate=ok);}return v.duration;},encoded);
  await meta.close();assert.ok(duration<180);
  reports.push({width,height,alignedFrameIndices:aligned,durationSeconds:duration,errors,recording:fileURLToPath(recording),nativeEventsSent:0});
 }catch(error){if(context){const pages=context.pages();if(pages[0]){await pages[0].screenshot({path:fileURLToPath(new URL(`failure-${width}.png`,out)),fullPage:true});await writeFile(new URL(`failure-${width}.txt`,out),await pages[0].locator('body').innerText());}}throw error;
 }finally{if(context)await context.close();server.kill();}
}
await writeFile(new URL('browser-report.json',out),JSON.stringify(reports,null,2));console.log(JSON.stringify(reports,null,2));
}finally{await browser.close();}
