import {readFile,mkdir,writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {chromium} from 'playwright';
import assert from 'node:assert/strict';

const out=new URL('../../runs/negative-review-checks/',import.meta.url);
await mkdir(out,{recursive:true});
const report=JSON.parse(await readFile(new URL('../../results/reliability/completed-diagnostic-24.json',import.meta.url),'utf8'));
const direct=report.results.find(r=>r.scene==='railway'&&r.family==='direct'&&r.repeat===1);
const separate=report.results.find(r=>r.scene==='railway'&&r.family==='separate'&&r.repeat===1);
const cv=JSON.parse(await readFile(new URL('../../results/reliability/railway-frame-audit.json',import.meta.url),'utf8'));
assert.equal(report.completed_requests,24);
const counts=report.semantic_counts.railway;
assert.equal(counts.asserts_entry_or_occupancy,3);assert.equal(counts.platform_only_or_denies_entry,9);
const escape=s=>String(s).replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
const displayFont=(await readFile(new URL('../node_modules/@fontsource/space-grotesk/files/space-grotesk-latin-600-normal.woff2',import.meta.url))).toString('base64');
const bodyFont=(await readFile(new URL('../node_modules/@fontsource/dm-sans/files/dm-sans-latin-400-normal.woff2',import.meta.url))).toString('base64');
const html=`<!doctype html><html><head><style>
@font-face{font-family:PolarDisplay;src:url(data:font/woff2;base64,${displayFont})} @font-face{font-family:PolarBody;src:url(data:font/woff2;base64,${bodyFont})}
*{box-sizing:border-box}body{margin:0;background:#F5F8FC;color:#13263A;font:22px/1.5 'Segoe UI',sans-serif;padding:62px 74px;width:1600px;height:900px}header{display:flex;justify-content:space-between;border-bottom:1px solid #D3DDE9;padding-bottom:24px;font-size:21px}header strong{font-size:28px}header span{color:#53667D}h1{font-size:45px;letter-spacing:-1.2px;margin:34px 0 12px;line-height:1.15}.sub{font-size:21px;color:#53667D;margin-bottom:32px}.grid{display:grid;grid-template-columns:1fr 1fr;gap:26px}.panel{background:white;border:1px solid #D3DDE9;border-radius:12px;padding:26px 30px;height:340px}.tag{text-transform:uppercase;letter-spacing:2px;font-size:16px;color:#53667D}h2{font-size:28px;margin:12px 0 18px}p{margin:12px 0}blockquote{margin:16px 0;padding-left:18px;border-left:3px solid #2858D6;font-size:23px}.detail{font-size:19px;color:#53667D}.row{margin-top:28px;padding:22px 28px;background:#EAF1FA;border-radius:10px;display:flex;justify-content:space-between;gap:45px;font-size:22px}.row strong{color:#2858D6}footer{font-size:17px;color:#53667D;margin-top:22px}
body{font-family:PolarBody,sans-serif}h1,h2,header strong{font-family:PolarDisplay,sans-serif}
</style></head><body><header><strong>Adaptive Watch</strong><span>Saved railway evidence · diagnostic comparison</span></header><h1>A negative assessment can still need review</h1><p class="sub">24 completed requests across two existing scenes · 12 railway responses · no additional inference</p><div class="grid"><section class="panel"><div class="tag">Railway · Direct action · repetition 1</div><h2>Hafnia explicitly denies entry</h2><blockquote>“${escape(direct.response_review.evidence_excerpt)}”</blockquote><p class="detail">Both direct-action repetitions answered No.</p><p class="detail">Summary ${escape(direct.summary_id)}</p></section><section class="panel"><div class="tag">Same railway diagnostic source</div><h2>Wording changed; faithful recovery did not</h2><p><strong>${counts.asserts_entry_or_occupancy}/12</strong> responses claim entry or track occupancy.<br><strong>${counts.platform_only_or_denies_entry}/12</strong> describe platform-only movement or deny entry.</p><p class="detail">Separate-stage responses cite crouching at 3–9 s. The reviewed descent is about 10 s; clear occupancy about 10.5 s.</p></section></div><div class="row"><div><strong>Independent CV: proximity only</strong><br>Original October 22 candidate is ${cv.candidate_early_seconds[0]}–${cv.candidate_early_seconds[1]} s earlier than reviewed entry.</div><div><strong>Operator action</strong><br>Review footage → Dismiss or request XProtect review.</div></div><footer>Claim counts are diagnostic findings, not model accuracy. Entry reference is AI-reviewed; human verification remains separate. October 22 CV and October 27 diagnostic timestamps are not joined.</footer></body></html>`;
await writeFile(new URL('comparison.private.html',out),html);
const browser=await chromium.launch({channel:'msedge',headless:true});
try{const page=await browser.newPage({viewport:{width:1600,height:900},deviceScaleFactor:1});await page.setContent(html);await page.evaluate(()=>document.fonts.ready);await page.screenshot({path:fileURLToPath(new URL('diagnostic-comparison.png',out))});}
finally{await browser.close();}
await writeFile(new URL('comparison-sources.json',out),JSON.stringify({report:'results/reliability/completed-diagnostic-24.json',cv:'results/reliability/railway-frame-audit.json',direct:direct.summary_id,separate:separate.summary_id,claimCounts:counts},null,2));
console.log(fileURLToPath(new URL('diagnostic-comparison.png',out)));
