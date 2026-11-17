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
 await page.goto(url);await page.waitForSelector('#home:not([hidden])');
 assert.equal(await page.locator('.workspace').isVisible(),false);
 assert.equal(await page.locator('.home-databases a').count(),8);
 for(const width of [1440,1024,390,320]){
  await page.setViewportSize({width,height:950});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`home overflow ${width}`);
  await page.screenshot({path:`.impeccable/review/llvm-home-${width}.png`,fullPage:true});
 }
 await page.locator('.home-guide a').click();
 await page.locator('#ascendc-map:not([hidden])').waitFor();
 await page.selectOption('#api-map-filter','resources');
 assert.equal(await page.locator('[data-map-tags]:visible').count(),1);
 await page.reload(); await page.locator('#ascendc-map:not([hidden])').waitFor();
 await page.locator('.map-nav a[href="#home"]').click();
 await page.setViewportSize({width:1440,height:950});
 await page.locator('.home-databases a').filter({hasText:'LLVM IR 目标核心'}).click();
 await page.waitForSelector('#rows .row-button');
 assert.equal(await page.locator('#backend').inputValue(),'llvm');
 const baseline=await page.evaluate(()=>visible.length);
 await page.reload();assert.equal(await page.evaluate(()=>visible.length),baseline);assert.equal(await page.locator('#llvm-scope').inputValue(),'a5-evidence');
 assert.equal(baseline,await page.evaluate(()=>llvmData.coverage.default_a5_evidence_view));
 await page.fill('#search','llvm.hivm.BARRIER');
 await page.locator('#rows .row-button').filter({hasText:/^llvm\.hivm\.BARRIER$/}).click();
 assert.match(await page.locator('#detail').innerText(),/950 模块有直接调用/);
 assert.ok(await page.locator('#llvm-form option').count()>1);
 assert.match(await page.locator('#detail').innerText(),/950 模块有直接调用/);
 assert.ok(await page.locator('#llvm-call-rows .evidence-entry').count()>0);
 assert.ok(await page.locator('#llvm-call-rows .evidence-entry').count()<=25);
 await page.locator('#detail details:has(#llvm-call-rows) > summary').click();
 await page.screenshot({path:'.impeccable/review/llvm-a5-calls-1440.png'});
 if(await page.locator('#llvm-call-more').count()){await page.click('#llvm-call-more');assert.equal(await page.locator('#llvm-call-rows .evidence-entry').count(),50);}
 await page.locator('#detail details:has(#llvm-call-rows) > summary').click();
 const forms=await page.locator('#llvm-form option').evaluateAll(xs=>xs.map(x=>x.value));
 await page.selectOption('#llvm-form',forms[0]);await page.reload();
 assert.equal(await page.locator('#llvm-form').inputValue(),forms[0]);
 await page.locator('#detail [data-op-ref="cce_dialect_intr_barrier"]').first().click();
 assert.equal(await page.locator('#backend').inputValue(),'cce-dialect-intrinsics');
 await page.locator('.llvm-links summary').click();
 await page.locator('.llvm-links [data-op-ref^="llvm_ir_"]').first().click();
 assert.equal(await page.locator('#backend').inputValue(),'llvm');
 await page.click('#reset');await page.selectOption('#llvm-scope','all');
 assert.ok(await page.evaluate(()=>visible.length)>12000);
 await page.check('#include-unknown');
 await page.reload();assert.equal(await page.locator('#include-unknown').isChecked(),true);
 const candidate=await page.evaluate(()=>llvmRecords.find(r=>r.llvm.identity_status==='candidate_only').name);
 await page.fill('#search',candidate);
 await page.locator('#rows .row-button').filter({hasText:candidate}).first().click();
 assert.match(await page.locator('#detail').innerText(),/仅字符串候选/);
 assert.equal(await page.locator('#llvm-form').count(),0);
 await page.click('#reset');
 await page.selectOption('#llvm-evidence','bitcode_declaration');
 assert.ok(await page.evaluate(()=>visible.length)>400);
 const event=page.waitForEvent('download');await page.click('#download');
 const exported=JSON.parse(await fs.readFile(await (await event).path(),'utf8'));
 assert.equal(exported.schema_version,'ackb.llvm.export.v1');
 assert.ok(exported.ops.every(o=>o.evidence.some(e=>e.kind==='bitcode_declaration')));
 assert.ok(exported.forms.every(f=>f.evidence.every(e=>exported.sources[e.source_id])));
 assert.ok(exported.a5_call_table.rows.length>0);
 const exportedForms=new Set(exported.forms.map(f=>f.id));
 assert.ok(exported.a5_call_table.rows.every(row=>exportedForms.has(exported.a5_call_table.forms[row[1]])));
 assert.equal(exported.target_mapping.npu_arch,3510);
 await page.click('#reset');
 await page.locator('#load-status').scrollIntoViewIfNeeded();
 await page.waitForFunction(()=>document.querySelectorAll('#rows tr').length>60);
 await page.locator('#jump-end').click();assert.equal(await page.locator('#rows tr').count(),baseline);
 await page.locator('#jump-start').click();
 await page.fill('#search','llvm.hivm.vldsx1');
 for(const width of [1440,1024,390,320]){
  await page.setViewportSize({width,height:950});await page.evaluate(()=>scrollTo(0,0));
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`LLVM overflow ${width}`);
  await page.screenshot({path:`.impeccable/review/llvm-core-${width}.png`,fullPage:true});
 }
 await page.click('.brand');await page.waitForSelector('#home:not([hidden])');
 const hrefs=await page.locator('.home-databases a').evaluateAll(as=>as.map(a=>a.hash));
 for(const hash of hrefs){
  await page.goto(url+hash);await page.waitForFunction(()=>!state.home);
  assert.equal(await page.locator('.workspace').isVisible(),true);
 }
 assert.deepEqual(errors,[]);assert.deepEqual(network,[]);
 console.log('LLVM/home browser checks passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
