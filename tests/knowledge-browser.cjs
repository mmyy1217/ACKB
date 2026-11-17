const assert=require('node:assert/strict');
const fs=require('node:fs/promises'),path=require('node:path');
const {pathToFileURL}=require('node:url');
const {chromium}=require(process.env.CCE_OPS_PLAYWRIGHT||'playwright');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CCE_OPS_CHROME,headless:true,args:['--no-sandbox']});
 const page=await browser.newPage({viewport:{width:1440,height:950}}),errors=[],network=[];
 page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(/^https?:/.test(r.url()))network.push(r.url());});
 const url=pathToFileURL(path.resolve('dist/index.html')).href;
 const setDepth=async value=>page.locator('#symbol-depth').evaluate((el,v)=>{el.value=v;el.dispatchEvent(new Event('input',{bubbles:true}));},value);
 try{
  await page.goto(url+'#backend=ptx');await page.waitForSelector('#rows .row-button');
  assert.equal(await page.evaluate(()=>state.view),'interfaces');assert.equal(await page.locator('.views').isVisible(),false);
  assert.equal(await page.locator('#symbol-depth-label').textContent(),'全部展开');
  const total=await page.evaluate(()=>visible.length);assert.ok(total>221);
  await setDepth(1);assert.ok(await page.evaluate(()=>visible.length)<total);
  await page.fill('#search','add.rn.ftz.sat.f32');
  assert.equal(await page.evaluate(()=>visible[0].name),'add');
  assert.match(await page.locator('#detail').textContent(),/add.rn.ftz.sat.f32/);
  assert.match(await page.locator('#detail').textContent(),/官方完整语法/);
  await setDepth(20);assert.equal(await page.evaluate(()=>visible[0].name),'add.rn.ftz.sat.f32');
  const deep=page.url();await page.reload();assert.equal(page.url(),deep);
  await page.fill('#search','does-not-exist-zzzz');assert.equal(await page.locator('#empty').isVisible(),true);
  for(const backend of ['ptx','llvm','nvvm']){
   await page.goto(url+'#backend='+backend);await page.waitForSelector('#rows .row-button');
   const max=Number(await page.locator('#symbol-depth').getAttribute('max'));assert.ok(max>1);
   const full=await page.evaluate(()=>visible.length);await setDepth(1);
   assert.ok(await page.evaluate(()=>visible.length)<=full);
   assert.equal(await page.evaluate(()=>state.query),'');
   if(await page.locator('#detail .symbol-members select').count()){
    const options=await page.locator('#detail .symbol-members option').count();assert.ok(options>1);
    await page.locator('#detail .symbol-members select').selectOption({index:1});
    assert.equal(await page.evaluate(()=>document.querySelector('#detail .symbol-members select').value===state.selected),true);
   }
   for(const width of [1440,1024,390,320]){
    await page.setViewportSize({width,height:950});
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,backend+' '+width);
    await page.screenshot({path:`.impeccable/review/symbol-${backend}-${width}.png`,fullPage:true});
   }
  }
  assert.deepEqual(errors,[]);assert.deepEqual(network,[]);console.log('PTX / LLVM / NVVM symbol browser checks passed');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
