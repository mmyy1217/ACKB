const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require(process.env.CCE_OPS_PLAYWRIGHT || 'playwright');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CCE_OPS_CHROME,headless:true,args:['--no-sandbox']});
 try {
 const page=await browser.newPage({viewport:{width:1440,height:950}}),errors=[],network=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))network.push(r.url());});
 const url=pathToFileURL(path.resolve('dist/index.html')).href;
 await page.goto(url);await page.waitForSelector('#rows .row-button');
 assert.equal(await page.locator('#page-title').innerText(),'底层 op');
 assert.match(await page.locator('#result-count').innerText(),/唯一 op/);
 await page.fill('#search','copy_gm_to_ubuf');
 assert.equal(await page.locator('#rows .row-button').filter({hasText:/^copy_gm_to_ubuf$/}).count(),1);
 await page.locator('#rows .row-button').filter({hasText:/^copy_gm_to_ubuf$/}).click();
 assert.match(await page.locator('#detail').innerText(),/__builtin_cce_copy_gm_to_ubuf/);
 assert.match(await page.locator('#detail').innerText(),/精确参数签名未确定/);
 assert.equal(await page.locator('#detail [data-op-ref="41997fe279e39ece787b"]').count(),0);
 const original=page.url();await page.reload();assert.equal(page.url(),original);
 await page.locator('#rows .row-button').filter({hasText:/^copy_gm_to_ubuf_align_v2$/}).click();
 const wrapper=page.locator('#detail [data-op-ref="41997fe279e39ece787b"]');
 await wrapper.locator('xpath=ancestor::details').locator('summary').click();
 for(const width of [1440,1024,390,320]){
  await page.setViewportSize({width,height:950});await page.evaluate(()=>scrollTo(0,0));
  await page.screenshot({path:`.impeccable/review/ccec-ops-${width}.png`,fullPage:true});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`overflow ${width}`);
 }
 await wrapper.click();assert.equal(await page.locator('#page-title').innerText(),'上层封装');
 assert.match(await page.locator('#detail').innerText(),/层级 · 上层封装/);
 await page.locator('#detail [data-op-ref="ccec_op___builtin_cce_copy_gm_to_ubuf_align_v2"]').click();
 assert.equal(await page.locator('#page-title').innerText(),'底层 op');
 await page.setViewportSize({width:1440,height:950});await page.fill('#search','copy_gm_to_ubuf_align_v2');
 const download=page.waitForEvent('download');await page.locator('#download').click();
 const payload=JSON.parse(await fs.readFile(await (await download).path(),'utf8'));
 assert.equal(payload.op_model.ops.length,1);
 assert.ok(payload.source_records.some(r=>r.id==='41997fe279e39ece787b'));
 assert.equal(payload.op_model.ops[0].builtin,'__builtin_cce_copy_gm_to_ubuf_align_v2');
 await page.goto(url+'#r=41997fe279e39ece787b');assert.equal(await page.locator('#page-title').innerText(),'上层封装');
 assert.match(await page.locator('#detail').innerText(),/copy_gm_to_ubuf/);
 await page.locator('[data-view="interfaces"]').click();await page.locator('#jump-end').click();
 const ids=await page.locator('#rows .row-button').evaluateAll(rows=>rows.map(r=>r.dataset.id));
 assert.equal(ids.length,new Set(ids).size);assert.equal(ids.length,4353);
 assert.deepEqual(errors,[]);assert.deepEqual(network,[]);
 console.log('PASS: unique ops, wrapper direction, original IDs, source-backed exports and responsive offline views');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
