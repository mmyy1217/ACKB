const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const http=require('node:http');
const {pathToFileURL}=require('node:url');
const {chromium}=require(process.env.CCE_OPS_PLAYWRIGHT||'playwright');
(async()=>{
 const root=path.resolve('dist/site');
 const server=http.createServer((req,res)=>{
  const file=path.join(root,new URL(req.url,'http://localhost').pathname==='/'?'index.html':new URL(req.url,'http://localhost').pathname);
  if(!file.startsWith(root+path.sep)||!fs.existsSync(file)){res.writeHead(404);res.end();return;}
  res.setHeader('Content-Type',file.endsWith('.js')?'text/javascript':file.endsWith('.css')?'text/css':file.endsWith('.html')?'text/html':'application/json');
  fs.createReadStream(file).pipe(res);
 });
 await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
 const browser=await chromium.launch({executablePath:process.env.CCE_OPS_CHROME,headless:true,args:['--no-sandbox']});
 try{
 for(const base of [`http://127.0.0.1:${server.address().port}/`,pathToFileURL(path.resolve('dist/index.html')).href]){
  const context=await browser.newContext(),page=await context.newPage(),errors=[],requests=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>requests.push(r.url()));
  await page.goto(base+'#insights');await page.waitForSelector('#insights-index:visible');
  assert.equal(await page.locator('#home').isVisible(),false);
  await page.locator('.insights-list a[href="#insight=dialect-a5-gap"]').click();await page.waitForSelector('article[data-insight]:visible');
  await page.waitForSelector('#gap-browser[data-ready="true"]');
  assert.equal(await page.locator('#gap-rows tr').count(),684);
  await page.getByRole('button',{name:/搬运 \/ DMA/}).click();
  assert.equal(await page.locator('#gap-rows tr').count(),36);
  await page.locator('#gap-query').fill('ND.DMA.OUT.TO.UB');
  assert.equal(await page.locator('#gap-rows tr').count(),3);
  const source = page.getByRole('combobox', {name:'来源'});
  await page.locator('#gap-query').fill('absent-symbol');
  assert.equal(await page.locator('#gap-rows tr').count(),0);
  await page.locator('#gap-query').fill('ND.DMA.OUT.TO.UB');
  await source.selectOption('libbisheng-llc.so');
  assert.equal(await page.locator('#gap-rows tr').count(),3);
  for (const cell of await page.locator('#gap-rows td:nth-child(2)').allTextContents())
    assert(cell.split(' / ').includes('libbisheng-llc.so'));
  await source.selectOption('');
  const download=page.waitForEvent('download');
  await page.locator('#gap-browser a[download]').click();
  const file=await download;
  assert.deepEqual(fs.readFileSync(await file.path()), fs.readFileSync('web/insights/files/a5-gap-20261122.xlsx'));
  await page.getByRole('button',{name:/全部指令族/}).click();
  await page.locator('#gap-query').fill('');
  for(const width of [1440,1024,390,320]){
   await page.setViewportSize({width,height:950});
   await page.waitForTimeout(150);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`overflow ${width} ${await page.evaluate(()=>[document.documentElement.scrollWidth,document.body.scrollWidth,innerWidth])}: ${await page.evaluate(()=>[...document.querySelectorAll('body *')].filter(e=>e.scrollWidth>e.clientWidth+2&&e.getBoundingClientRect().width).map(e=>e.tagName+'.'+e.className).slice(0,8))}`);
   if(base.startsWith('http'))await page.screenshot({path:`.impeccable/review/insight-${width}.png`,fullPage:true});
  }
  await page.reload();await page.waitForSelector('article[data-insight]:visible');
  await page.locator('.insight-back:visible').click();await page.waitForSelector('#insights-index:visible');
  await page.goBack();await page.waitForSelector('article[data-insight]:visible');
  await page.locator('.insight-back:visible').click();
  await page.locator('a[href="#insight=dialect-a5-gap-20261120"]').click();
  const archive = page.locator('#archive-gap-browser[data-ready="true"]');
  await archive.waitFor();
  assert.equal(await archive.locator('tbody tr').count(),823);
  assert.equal(await archive.locator('th').count(),2);
  await archive.locator('input').fill('atomicrmw');
  assert.equal(await archive.locator('tbody tr').count(),1);
  const archivedDownload=page.waitForEvent('download');
  await archive.locator('a[download]').click();
  assert.deepEqual(fs.readFileSync(await (await archivedDownload).path()),fs.readFileSync('web/insights/files/a5-gap-20261120.xlsx'));
  await page.evaluate(()=>location.hash='insight=llvm-full-alignment');
  const alignment=page.locator('.alignment-browser[data-ready="true"]');
  await alignment.waitFor();
  assert.equal(await alignment.locator('tbody tr').count(),1885);
  await alignment.locator('[data-match-filter]').selectOption('注册重载基名');
  assert.equal(await alignment.locator('tbody tr').count(),509);
  await alignment.locator('[data-match-filter]').selectOption('');
  await alignment.locator('.gap-tools input').fill('llvm.hivm.ceilf');
  assert.deepEqual((await alignment.locator('tbody td').allTextContents()).slice(0,2),['','llvm.hivm.ceilf']);
  await alignment.locator('.gap-tools input').fill('');
  for (const [index,term] of [[0,'llvm.hivm.vabs.x'],[1,'v128f16']]) {
   await alignment.locator('[data-name-column="'+index+'"]').fill(term);
  }
  for (const index of [2,3]) {
   const file=(await alignment.locator('tbody tr').first().locator('td').nth(index).innerText()).split(' / ')[0].replace(/:\d+$/,'');
   await alignment.locator('[data-source-column="'+index+'"]').selectOption(file);
   assert((await alignment.locator('tbody tr').count())>0);
   for(const cell of await alignment.locator('tbody td:nth-child('+(index+1)+')').allTextContents()) assert(cell.includes(file));
  }
  assert(await alignment.locator('tbody tr').count()<509);
  for(const filter of await alignment.locator('[data-source-column]').all()) await filter.selectOption('');
  for(const filter of await alignment.locator('[data-name-column]').all()) await filter.fill('');
  assert.equal(await alignment.locator('tbody tr').count(),1885);
  await alignment.locator('nav button').nth(1).click();
  assert(await alignment.locator('tbody tr').count()<1885);
  const fullDownload=page.waitForEvent('download');
  await alignment.locator('a[download]').click();
  assert.deepEqual(fs.readFileSync(await (await fullDownload).path()),fs.readFileSync('web/insights/files/a5-gap-20261123.xlsx'));
  await page.evaluate(()=>location.hash='insight=missing');await page.waitForSelector('#insight-missing:visible');
  await page.locator('.brand').click();await page.waitForSelector('#home:visible');
  assert.equal(await page.locator('#insights').isVisible(),false);
  assert.equal(requests.filter(url=>/\/data\//.test(url)&&!url.includes('/navigation.')).length,0,'Articles must not load databases');
  if(base.startsWith('file:'))assert.equal(requests.filter(url=>/^https?:/.test(url)).length,0);
  assert.deepEqual(errors,[]);
  await context.close();
 }
 console.log('Insights online/offline, routes, history and responsive checks passed');
 }finally{await browser.close();server.close();}
})().catch(e=>{console.error(e);process.exit(1);});
