// Real local sources, isolated decision stores, actual browser video. No inference.
import assert from 'node:assert/strict';
import {mkdir,writeFile} from 'node:fs/promises';
import {spawn,spawnSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';

const repo=fileURLToPath(new URL('../../',import.meta.url));
const out=new URL(`../../runs/application-checks/${Date.now()}/`,import.meta.url);
await mkdir(out,{recursive:true});
const python=repo+'/.venv/Scripts/python.exe';
const evaluations=process.env.AW_EVALUATIONS??'C:/Users/Administrator/adaptive-watch-private/hafnia-16';
const browser=await chromium.launch({channel:'msedge',headless:true});
const reports=[];
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function ready(base){for(let i=0;i<100;i++){try{if((await fetch(base+'/api/workspace')).ok)return;}catch{}await sleep(100);}throw new Error('Workspace server unavailable');}
const prepare=`from adaptive_watch.negative_review import ReviewStore; import sys; source=ReviewStore('runs/negative-result-review'); record,_=source.verified(); source.close(); target=ReviewStore(sys.argv[1]); target.install(record); target.close()`;
try{
  for(const [width,height,port] of [[1440,900,8881],[1920,1080,8882]]){
    const root=new URL(`${width}/`,out);await mkdir(root,{recursive:true});
    const railway=fileURLToPath(new URL('railway/',root));
    const preparation=spawnSync(python,['-c',prepare,railway],{cwd:repo,windowsHide:true,encoding:'utf8'});
    assert.equal(preparation.status,0,preparation.stderr);
    const server=spawn(python,['-m','adaptive_watch.workspace_api','--root',fileURLToPath(root),'--railway',railway,'--evaluations',evaluations,'--port',String(port)],{cwd:repo,windowsHide:true,stdio:'ignore'});
    let context;
    try{
      const base=`http://127.0.0.1:${port}`;await ready(base);
      context=await browser.newContext({viewport:{width,height},recordVideo:{dir:fileURLToPath(root),size:{width,height}}});
      const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
      // On-screen captions are walkthrough annotations only, outside product UI.
      async function caption(text){await page.evaluate(text=>{document.querySelector('#walkthrough-caption')?.remove();const el=document.createElement('div');el.id='walkthrough-caption';el.textContent=text;Object.assign(el.style,{position:'fixed',bottom:'16px',left:'20%',right:'20%',zIndex:100,background:'#13263a',color:'white',padding:'12px 20px',borderRadius:'8px',font:'15px sans-serif',textAlign:'center',boxShadow:'0 3px 15px #0003',pointerEvents:'none'});document.body.append(el);},text);await page.waitForTimeout(1400);}
      await page.goto(base,{waitUntil:'networkidle'});
      await page.locator('.case-card').nth(3).waitFor();
      assert.equal(await page.locator('.case-card').count(),4);
      assert.equal(await page.getByText('Semantic uncertainty',{exact:true}).count(),1);
      await caption('Four source-verified assessments. Original cameras and dates; independent evidence is stated per case.');
      await page.screenshot({path:fileURLToPath(new URL('workspace.png',root)),fullPage:true});
      await page.getByRole('button',{name:'Open railway investigation',exact:true}).click();
      await page.waitForFunction(()=>document.querySelector('video')?.readyState>=2);
      const railwayData=(await (await page.request.get(base+'/api/review')).json()).review;
      assert.equal(railwayData.hafnia.summaryId,'5a1ab040-fc44-4156-ad7a-1eeecd8c7b60');
      assert.equal(railwayData.frames.length,26);
      assert.equal(await page.locator('video').evaluate(v=>v.duration),13);
      const aligned=[];
      for(const index of [7,8,11,18,19,25]){
        await page.locator('video').evaluate((v,t)=>{v.pause();v.currentTime=t;},index*.5);
        await page.waitForFunction(stamp=>document.querySelector('.media-caption time')?.textContent===stamp,railwayData.frames[index].timestamp.slice(11,23)+' UTC');
        const box=page.locator('[data-track="7"]');assert.equal(await box.count(),Number(Boolean(railwayData.frames[index].box)));
        if(await box.count())assert.equal(await box.getAttribute('data-frame'),String(index));
        aligned.push(index);
      }
      await page.getByRole('button',{name:'Proximity observation',exact:false}).click();
      await caption('Railway: original negative Hafnia result plus person/region proximity. Proximity does not confirm entry.');
      await page.screenshot({path:fileURLToPath(new URL('railway.png',root)),fullPage:true});
      await page.getByRole('button',{name:'Review footage',exact:true}).click();
      await page.waitForTimeout(1600);await page.locator('video').evaluate(v=>v.pause());
      assert.ok(await page.getByRole('button',{name:'Save review request',exact:true}).isDisabled());
      await page.getByLabel('Review note',{exact:true}).fill('Browser acceptance only: railway proximity needs verification.');
      await page.getByRole('checkbox',{name:'I have reviewed the relevant footage'}).check();
      await page.getByRole('button',{name:'Save review request',exact:true}).click();
      await page.getByRole('heading',{name:'Review request saved',exact:true}).waitFor();
      await page.reload({waitUntil:'networkidle'});
      await page.getByRole('heading',{name:'Review request saved',exact:true}).waitFor();
      await page.getByRole('button',{name:'All assessments',exact:true}).click();
      await page.getByRole('button',{name:'Open scooter investigation',exact:true}).click();
      await page.getByRole('heading',{name:'5.0 s sampled stationarity',exact:true}).waitFor();
      assert.equal(await page.locator('[data-track="7"]').count(),0);
      const scooter=(await (await page.request.get(base+'/api/cases/scooter')).json()).review;
      assert.equal(scooter.runs[0].samples,6);assert.equal(scooter.runs[0].sampled_span_s,5);
      assert.ok(!(await page.locator('main').innerText()).includes('person_on_railway_tracks'));
      await page.getByRole('slider',{name:'Recorded sample'}).fill('12');
      await page.waitForFunction(stamp=>document.querySelector('.media-caption time')?.textContent===stamp,scooter.frames[12].timestamp.slice(11,23)+' UTC');
      await page.locator('[data-object="Scooter"][data-frame="12"]').waitFor();
      const boxX=Number(await page.locator('[data-object="Scooter"]').getAttribute('x'));assert.equal(boxX,scooter.frames[12].box[0]);
      await caption('Scooter: its own camera, snapshots and CV. Six stationary samples span 5 seconds; minimum draft walkway overlap is 43.0%.');
      await page.screenshot({path:fileURLToPath(new URL('scooter.png',root)),fullPage:true});
      await page.getByRole('button',{name:'Review footage',exact:true}).click();
      assert.ok(await page.getByRole('button',{name:'Dismiss',exact:true}).isDisabled());
      await page.getByLabel('Review note',{exact:true}).fill('Browser acceptance only: scooter source reviewed separately.');
      await page.getByRole('checkbox',{name:'I have reviewed the relevant footage'}).check();
      await page.getByRole('button',{name:'Dismiss',exact:true}).click();
      await page.getByRole('heading',{name:'Review dismissed',exact:true}).waitFor();
      await page.reload({waitUntil:'networkidle'});await page.getByRole('heading',{name:'Review dismissed',exact:true}).waitFor();
      assert.ok((await page.locator('.saved-note').innerText()).includes('scooter source'));
      await page.getByRole('button',{name:'All assessments',exact:true}).click();
      await page.locator('.case-card').nth(3).waitFor();
      assert.ok((await page.locator('[data-case="railway"]').innerText()).includes('Review request saved locally'));
      assert.ok((await page.locator('[data-case="scooter"]').innerText()).includes('Dismissed'));
      assert.ok((await page.locator('[data-case="bin"]').innerText()).includes('Awaiting review'));
      await caption('Decisions survive reload independently: railway follow-up saved, scooter dismissed, gate and bin still awaiting review.');
      await page.screenshot({path:fileURLToPath(new URL('decisions.png',root)),fullPage:true});
      await page.getByRole('button',{name:'Open bin investigation',exact:true}).click();
      await page.getByRole('heading',{name:'3.0 s sampled stationarity',exact:true}).waitFor();
      assert.ok(!(await page.locator('main').innerText()).includes(scooter.camera));
      await page.getByRole('button',{name:'All assessments',exact:true}).click();
      await page.getByRole('button',{name:'Open school gate investigation',exact:true}).click();
      await page.getByRole('heading',{name:'Semantic uncertainty',exact:true}).waitFor();
      assert.equal(await page.locator('svg').count(),0);
      await page.getByRole('button',{name:'Evidence details',exact:true}).click();
      await page.getByRole('heading',{name:'Separate prompt diagnostic · 27 October',exact:true}).scrollIntoViewIfNeeded();
      await caption('School gate: negative originals and prompt-sensitive semantic evidence. Later diagnostics keep their separate dates; no CV is invented.');
      await page.screenshot({path:fileURLToPath(new URL('gate-diagnostics.png',root)),fullPage:true});
      await page.keyboard.press('Escape');
      await page.getByRole('button',{name:'All assessments',exact:true}).click();
      await page.getByRole('button',{name:'New assessment',exact:false}).click();
      await page.getByLabel('Authorized camera',{exact:true}).waitFor();
      assert.equal(await page.getByLabel('Authorized camera').locator('option').count(),2);
      const end=new Date(Date.now()-120000),start=new Date(end-15000);
      await page.getByLabel('Recording start (UTC)',{exact:true}).fill(start.toISOString().slice(0,19));
      await page.getByLabel('Recording end (UTC)',{exact:true}).fill(end.toISOString().slice(0,19));
      await page.getByRole('button',{name:'Start assessment',exact:true}).click();
      await page.getByRole('heading',{name:'Cannot start this assessment',exact:true}).waitFor();
      assert.ok((await page.locator('main').innerText()).includes('No recording was acquired and no Hafnia request was submitted.'));
      assert.ok(!(await page.locator('main').innerText()).match(/sha256|administrator password|<xml|powershell/i));
      await caption('New assessment performs real server readiness checks. It reports the missing authenticated runtime and CUDA handoff; no inference is submitted.');
      await page.screenshot({path:fileURLToPath(new URL('assessment-blocked.png',root)),fullPage:true});
      await page.goto(base+'/#case/unknown');
      await page.getByRole('alert').filter({hasText:'Unknown assessment'}).waitFor();
      assert.equal(await page.locator('img,video').count(),0);
      await caption('Unknown cases fail explicitly and show no footage or another case’s camera.');
      await page.screenshot({path:fileURLToPath(new URL('unknown.png',root)),fullPage:true});
      // CSRF, stale decisions and case/frame separation at the live HTTP boundary.
      const current=await (await page.request.get(base+'/api/cases/scooter')).json();
      assert.equal((await page.request.post(base+'/api/cases/bin/action',{data:{action:'review',revision:current.review.revision},headers:{'X-Review-CSRF':current.csrf}})).status(),409);
      assert.equal((await page.request.get(base+'/api/cases/scooter/frames/99')).status(),404);
      assert.equal((await page.request.post(base+'/api/native/send',{data:{}})).status(),403);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
      assert.deepEqual(errors,[]);
      const video=page.video();await context.close();context=null;
      await video.saveAs(fileURLToPath(new URL(`walkthrough-${width}.webm`,out)));
      reports.push({width,height,status:'passed',verifiedCases:4,railwayAlignedFrames:aligned,scooterSpanSeconds:5,binSpanSeconds:3,independentDecisionsPersisted:true,unknownCase:404,crossCaseRevision:409,runtime:'blocked; zero acquisition or inference submissions',browserErrors:errors});
    }finally{if(context)await context.close();server.kill();}
  }
  // A separate server omits the original response directory. Sources themselves
  // are untouched; this demonstrates unavailable-source handling in the browser.
  const missingRoot=new URL('missing-originals/',out);await mkdir(missingRoot,{recursive:true});
  const server=spawn(python,['-m','adaptive_watch.workspace_api','--root',fileURLToPath(missingRoot),'--evaluations',fileURLToPath(new URL('unavailable/',missingRoot)),'--port','8883'],{cwd:repo,windowsHide:true,stdio:'ignore'});
  try{
    const base='http://127.0.0.1:8883';await ready(base);
    const page=await browser.newPage({viewport:{width:1440,height:900}});
    await page.goto(base,{waitUntil:'networkidle'});
    await page.getByRole('heading',{name:'Source data unavailable'}).waitFor();
    assert.equal(await page.locator('.case-card').count(),1);
    assert.equal((await page.request.get(base+'/api/cases/scooter')).status(),422);
    await page.screenshot({path:fileURLToPath(new URL('unavailable-sources.png',out)),fullPage:true});
    await page.goto(base+'/#case/scooter');
    await page.getByRole('alert').filter({hasText:'Insufficient evidence'}).waitFor();
    assert.equal(await page.locator('img,video').count(),0);
    await page.screenshot({path:fileURLToPath(new URL('unavailable-investigation.png',out)),fullPage:true});
    await page.close();
    reports.push({unavailableOriginalResponses:'passed',hiddenCases:['gate','scooter','bin'],directCaseStatus:422});
  }finally{server.kill();}
  await writeFile(new URL('report.json',out),JSON.stringify(reports,null,2));
  console.log(JSON.stringify({output:fileURLToPath(out),reports},null,2));
}finally{await browser.close();}
