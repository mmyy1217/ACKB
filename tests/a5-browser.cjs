const assert=require('node:assert/strict');
const fs=require('node:fs/promises');
const path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require(process.env.CCE_OPS_PLAYWRIGHT || 'playwright');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CCE_OPS_CHROME,headless:true,args:['--no-sandbox']});
 try{
 const page=await browser.newPage({viewport:{width:1440,height:950}}),errors=[],network=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))network.push(r.url());});
 const url=pathToFileURL(path.resolve('dist/index.html')).href;
 await page.goto(url);await page.waitForSelector('#rows .row-button');
 assert.equal(await page.locator('#backend').inputValue(),'ccec');
 assert.equal(await page.locator('#chip,#architecture,.compatibility-menu').count(),0);
 assert.equal(await page.locator('.views').isVisible(),false);
 assert.match(await page.locator('#fixed-chip').innerText(),/950/);
 assert.match(await page.locator('#result-count').innerText(),/357 个接口/);
 assert.equal(await page.locator('#rows tr').count(),60);
 const first=await page.locator('#rows .row-button').evaluateAll(rs=>rs.map(r=>r.dataset.id));
 await page.locator('#load-status').scrollIntoViewIfNeeded();
 await page.waitForFunction(()=>document.querySelectorAll('#rows tr').length>60);
 assert.deepEqual((await page.locator('#rows .row-button').evaluateAll(rs=>rs.map(r=>r.dataset.id))).slice(0,60),first);
 await page.locator('#jump-end').click();assert.equal(await page.locator('#rows tr').count(),357);
 await page.locator('#scroll-rail').focus();await page.keyboard.press('Home');await page.keyboard.press('End');
 assert.match(await page.locator('#scroll-rail').getAttribute('aria-valuetext'),/357/);
 await page.locator('#jump-start').click();
 await page.locator('#resize-sidebar').focus();await page.keyboard.press('ArrowRight');
 assert.equal(await page.locator('#resize-sidebar').getAttribute('aria-valuenow'),'146');
 await page.reload();assert.equal(await page.locator('#resize-sidebar').getAttribute('aria-valuenow'),'146');
 await page.locator('#resize-sidebar').focus();await page.keyboard.press('Enter');
 const handle=await page.locator('#resize-detail').boundingBox();await page.mouse.move(handle.x+2,handle.y+100);await page.mouse.down();await page.mouse.move(handle.x-60,handle.y+100);await page.mouse.up();
 assert.ok(Number(await page.locator('#resize-detail').getAttribute('aria-valuenow'))>330);
 await page.locator('#resize-detail').focus();await page.keyboard.press('Enter');
 await page.check('#include-unknown');assert.match(await page.locator('#result-count').innerText(),/548 个接口/);
 await page.reload();assert.equal(await page.locator('#include-unknown').isChecked(),true);
 await page.uncheck('#include-unknown');
 await page.fill('#search','copy_gm_to_ubuf');
 assert.equal(await page.locator('#rows .row-button').filter({hasText:/^copy_gm_to_ubuf$/}).count(),1);
 await page.locator('#rows .row-button').filter({hasText:/^copy_gm_to_ubuf$/}).click();
 assert.match(await page.locator('#detail').innerText(),/层级 · 上层封装/);
 for(const width of [1440,1024,390,320]){
  await page.setViewportSize({width,height:950});await page.evaluate(()=>scrollTo(0,0));
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`interface overflow ${width}`);
  await page.screenshot({path:`.impeccable/review/a5-interfaces-${width}.png`,fullPage:true});
 }
 await page.locator('#detail [data-op-ref="ccec_op___builtin_cce_copy_gm_to_ubuf_align_v2"]').first().click();
 assert.equal(await page.locator('#backend').inputValue(),'ccec-intrinsics');
 assert.match(await page.locator('#detail').innerText(),/唯一 op/);
 for(const width of [1440,1024,390,320]){
  await page.setViewportSize({width,height:950});await page.evaluate(()=>scrollTo(0,0));
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`intrinsic overflow ${width}`);
  await page.screenshot({path:`.impeccable/review/a5-intrinsics-${width}.png`,fullPage:true});
 }
 await page.setViewportSize({width:1440,height:950});
 await page.fill('#search','copy_gm_to_ubuf_align_v2');
 const download=page.waitForEvent('download');await page.locator('#download').click();
 const payload=JSON.parse(await fs.readFile(await (await download).path(),'utf8'));
 assert.equal(payload.selection.chip,'Ascend950PR_9579');assert.equal(payload.selection.architecture,'__NPU_ARCH__=3510');
 assert.equal(payload.selection.layer,'interfaces');assert.equal(payload.op_model.ops.length,1);
 assert.ok(payload.source_records.some(r=>r.id==='41997fe279e39ece787b'));
 await page.selectOption('#backend','ccec');assert.match(await page.locator('#result-count').innerText(),/357 个接口/);
 await page.fill('#search','not_an_existing_abcdef');assert.equal(await page.locator('#empty').isVisible(),true);
 assert.equal(await page.locator('#scroll-navigation').isVisible(),false);await page.locator('#empty-reset').click();
 await page.locator('#coverage').click();assert.match(await page.locator('#report').innerText(),/357/);assert.match(await page.locator('#report').innerText(),/191/);
 await page.locator('#coverage').click();assert.match(await page.locator('#result-count').innerText(),/357 个接口/);
 await page.goto(url+'#view=wrappers&r=41997fe279e39ece787b&chip=Ascend910B2&architecture=__NPU_ARCH__%3D2201');
 assert.match(await page.locator('#detail').innerText(),/Ascend950PR_9579/);assert.ok(!page.url().includes('2201'));
 await page.setViewportSize({width:390,height:950});await page.locator('#rows .row-button').first().click();
 const count=await page.locator('#rows tr').count();await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
 assert.equal(await page.locator('#rows tr').count(),count);await page.locator('#back-to-list').click();
 assert.equal(await page.locator('#rows [aria-current="true"]').evaluate(n=>n===document.activeElement),true);
 assert.deepEqual(errors,[]);assert.deepEqual(network,[]);
 console.log('PASS: fixed A5, 357/548 interfaces, two layers, source relations, deep links, progress, append, resizing, export and offline responsive views');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
