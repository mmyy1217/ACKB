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
  assert.equal(await page.locator('#gap-rows tr').count(),823);
  await page.getByRole('button',{name:/搬运 \/ DMA/}).click();
  assert.equal(await page.locator('#gap-rows tr').count(),36);
  await page.locator('#gap-query').fill('ND.DMA.OUT.TO.UB');
  assert.equal(await page.locator('#gap-rows tr').count(),3);
  const download=page.waitForEvent('download');
  await page.locator('#gap-browser a[download]').click();
  const file=await download;
  assert.deepEqual(fs.readFileSync(await file.path()), fs.readFileSync('web/insights/files/a5-gap-20261120.xlsx'));
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
