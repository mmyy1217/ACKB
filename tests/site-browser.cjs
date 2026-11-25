const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const {gunzipSync} = require('node:zlib');
const {chromium} = require(process.env.CCE_OPS_PLAYWRIGHT || 'playwright');

(async () => {
  const root = path.resolve('dist/site'), manifest = JSON.parse(fs.readFileSync(path.join(root, 'manifest.json')));
  const snapshot = backend => JSON.parse(gunzipSync(fs.readFileSync(path.join(root,manifest.datasets[backend].gzip.url)))).payload;
  const llvmDefaultCount = snapshot('llvm').coverage.default_a5_source_view;
  const ptxInstructionCount = new Set(snapshot('ptx').forms.forms.map(r=>r.name)).size;
  const requests = [], faults = new Map();
  let revision = manifest.revision, latestDatasets = manifest.datasets;
  const server = http.createServer(async (req, res) => {
    const pathname = new URL(req.url, 'http://localhost').pathname;
    requests.push(pathname);
    const name = pathname.split('/').pop().split('.')[0], fault = faults.get(name);
    if (fault === 'delay') await new Promise(resolve => setTimeout(resolve, 1200));
    if (fault === '404') {res.writeHead(404); res.end(); return;}
    if (fault === 'corrupt') {res.end('corrupt asset'); return;}
    if (pathname === '/manifest.json') {res.setHeader('Content-Type', 'application/json'); res.end(JSON.stringify({...manifest, revision, datasets:latestDatasets})); return;}
    const file = path.join(root, pathname === '/' ? 'index.html' : pathname);
    if (!file.startsWith(root + path.sep) || !fs.existsSync(file)) {res.writeHead(404); res.end(); return;}
    res.setHeader('Content-Length', fs.statSync(file).size);
    res.setHeader('Content-Type', file.endsWith('.js') ? 'text/javascript' : file.endsWith('.css') ? 'text/css' : file.endsWith('.html') ? 'text/html' : 'application/octet-stream');
    if (fault === 'stream') {
      const bytes = fs.readFileSync(file);
      for(let offset=0;offset<bytes.length;offset+=32768) {res.write(bytes.subarray(offset,offset+32768)); await new Promise(resolve=>setTimeout(resolve,100));}
      res.end(); return;
    }
    fs.createReadStream(file).pipe(res);
  });
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const url = `http://127.0.0.1:${server.address().port}/`;
  const browser = await chromium.launch({executablePath: process.env.CCE_OPS_CHROME, headless: true, args: ['--no-sandbox']});
  const errors = [];
  const makePage = async (context = null) => {
    const page = await (context || await browser.newContext({viewport: {width:1440,height:950}})).newPage();
    page.on('pageerror', e => errors.push(e.message));
    return page;
  };
  const ready = async (page, backend) => {
    await page.waitForFunction(backend => installedBackends.has(backend) || (pendingNavigation?.backend === backend && ['missing','update','error'].includes(siteLoader.status(backend).phase)),backend);
    if (await page.evaluate(backend => !installedBackends.has(backend) && ['missing','update','error'].includes(siteLoader.status(backend).phase),backend)) await page.click('#site-retry');
    await page.waitForFunction(backend => !document.body.classList.contains('data-loading') && typeof state !== 'undefined' && state.backend === backend && installedBackends.has(backend), backend);
  };
  try {
    const page = await makePage();
    await page.goto(url); await page.waitForFunction(() => typeof state !== 'undefined');
    assert.equal(await page.locator('#home').isVisible(), true);
    assert.equal(requests.filter(p => /\.json(?:\.gz)?$/.test(p) && p !== '/manifest.json').length, 0, 'homepage must not download databases');
    assert.equal(await page.evaluate(() => allRecords.length), 0, 'homepage must not index databases');
    assert.ok(fs.statSync(path.join(root, 'index.html')).size < 40000);
    const initialBytes = await page.evaluate(() => performance.getEntriesByType('resource').reduce((n,r)=>n+r.encodedBodySize,0) + performance.getEntriesByType('navigation')[0].encodedBodySize);
    assert.ok(initialBytes < 300000, `homepage transfer budget exceeded: ${initialBytes}`);
    for (const width of [1440,1024,390,320]) {
      await page.setViewportSize({width,height:950});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      assert.equal(await page.locator('#ascendc-map').evaluate(el=>el.scrollWidth <= el.clientWidth),true,'topology must fit without horizontal scrolling');
      const placement = await page.evaluate(() => {
        const a = document.querySelector('.ecosystem-ascend').getBoundingClientRect();
        const n = document.querySelector('.ecosystem-nvidia').getBoundingClientRect();
        return innerWidth > 1100 ? n.left >= a.right : n.top >= a.bottom;
      });
      assert.equal(placement,true,'ecosystems must sit side by side on desktop and stack on narrow screens');
      assert.equal(await page.locator('.ecosystem-nvidia a[data-database]').count(),2);
      await page.screenshot({path:`.impeccable/review/loading-home-${width}.png`,fullPage:true});
    }
    await page.evaluate(()=>location.hash='ascendc-map');
    await page.locator('#ascendc-map:not([hidden])').waitFor();
    assert.equal(await page.evaluate(()=>installedBackends.size),0,'API map must not download a database');
    for(const width of [1440,1024,390,320]) {
      await page.setViewportSize({width,height:950});
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
      await page.screenshot({path:`.impeccable/review/api-map-${width}.png`,fullPage:true});
    }
    assert.equal(await page.locator('[data-library]').count(),8);
    const libraryLinks = await page.locator('[data-library]').evaluateAll(nodes=>nodes.map(n=>n.hash));
    for (const link of libraryLinks) {
      await page.evaluate(hash=>location.hash=hash,link);
      await page.locator('#site-loading:not([hidden])').waitFor();
      assert.equal(await page.evaluate(()=>installedBackends.size),0,'library requires explicit download');
      await page.evaluate(()=>location.hash='ascendc-map');
      await page.locator('#ascendc-map:not([hidden])').waitFor();
    }
    await page.reload(); await page.locator('#ascendc-map:not([hidden])').waitFor();
    assert.equal(await page.evaluate(()=>installedBackends.size),0);
    await page.evaluate(()=>location.hash='home');
    await page.setViewportSize({width:1440,height:950});
    assert.equal(await page.locator('#home a[data-database][href*="backend=llvm"]').getAttribute('aria-disabled'),'true');
    await page.locator('#home [data-download-backend=llvm] button').click();
    await page.waitForFunction(() => siteLoader.status('llvm').phase === 'ready');
    await page.locator('#home a[data-database][href*="backend=llvm"]').click(); await ready(page,'llvm');
    assert.equal(await page.evaluate(() => visible.length), llvmDefaultCount);
    assert.equal(await page.evaluate(() => data.records.length), 0, 'LLVM must not download CCEC');
    assert.equal(await page.evaluate(() => ascendcRecords.length), 0);
    await page.fill('#search','llvm.hivm.BARRIER');
    await page.locator('#rows .row-button').filter({hasText:/^llvm\.hivm\.BARRIER$/}).click();
    assert.ok(await page.locator('#llvm-form option').count() > 0);
    const selected = await page.evaluate(() => state.selected);
    const loadedRequests = requests.filter(p=>p.endsWith('.json.gz')).length;
    await page.reload(); await ready(page,'llvm');
    assert.equal(await page.evaluate(() => state.selected), selected);
    assert.equal(requests.filter(p=>p.endsWith('.json.gz')).length, loadedRequests, 'repeat visit must reuse validated persistent data');
    await page.evaluate(async entry => {
      const cache=await caches.open('ackb-data-v1:'+new URL('.',location.href).pathname);
      await cache.put(new URL(entry.url,location.href).href,new Response('bad cache'));
    },manifest.datasets.llvm.gzip);
    await page.reload(); await ready(page,'llvm');
    assert.equal(requests.filter(p=>p.endsWith('.json.gz')).length,loadedRequests+1,'corrupt cache must be replaced');
    await page.locator('#detail [data-op-ref="cce_dialect_intr_barrier"]').first().click(); await ready(page,'cce-dialect');
    assert.equal(await page.evaluate(() => state.selected), 'cce_dialect_intr_barrier');
    await page.locator('.llvm-links > summary').click();
    await page.locator('.llvm-links [data-op-ref^="llvm_ir_"]').first().click(); await ready(page,'llvm');

    await page.selectOption('#backend','cce-dialect-intrinsics'); await ready(page,'cce-dialect');
    await page.fill('#search','llvm.hivm.vadd.s.m.v128f16');
    await page.locator('#rows a').first().click(); await ready(page,'llvm');
    assert.equal(await page.locator('#detail h2').textContent(), 'llvm.hivm.vadd.s.m');

    for (const [value, backend] of [['ccec','ccec'],['ccec-intrinsics','ccec'],['ascendc','ascendc'],['ascendc-capi','ascendc'],['cce-dialect','cce-dialect'],['cce-dialect-intrinsics','cce-dialect'],['ptx','ptx'],['nvvm','nvvm'],['hivm-defs','hivm-defs']]) {
      await page.selectOption('#backend',value); await ready(page,backend);
      assert.equal(await page.locator('#backend').inputValue(), value);
      assert.ok(await page.evaluate(() => records.length) > 0, value);
    }
    await page.fill('#search','int_hivm_vsstb_post');
    assert.equal(await page.locator('#rows .row-button').count(),1);
    assert.match(await page.locator('#detail').innerText(),/llvm\.hivm\.vsstb\.post\.v64f32/);
    await page.selectOption('#backend','ccec'); await ready(page,'ccec');
    await page.fill('#search','copy_gm_to_cbuf');
    assert.ok(await page.locator('#rows .row-button').count() > 0);
    await page.locator('#rows .row-button').first().click();
    await page.locator('#detail [data-op-ref="ccec_op___builtin_cce_copy_gm_to_cbuf_align_v2"]').first().click();
    assert.equal(await page.evaluate(() => state.selected), 'ccec_op___builtin_cce_copy_gm_to_cbuf_align_v2');
    assert.ok(await page.locator('#detail .llvm-links').count() > 0, 'upstream details retain LLVM links');

    // A cold cross-layer jump must load CCEC rather than silently drop a link.
    const cold = await makePage();
    await cold.goto(url+'#backend=ascendc&r=ascendc_basic_ascendc_reg_StoreAlign'); await ready(cold,'ascendc');
    assert.equal(await cold.evaluate(() => data.records.length), 0);
    await cold.locator('.call-trace > summary').click();
    await cold.locator('#detail [data-op-ref^="ccec_op___builtin_cce_vstsx1_"]').first().click(); await ready(cold,'ccec');
    assert.match(await cold.evaluate(() => state.selected), /^ccec_op___builtin_cce_vstsx1_/);
    await cold.close();

    // Failure, retry, cancellation and narrow-screen loading are part of navigation.
    const failure = await makePage(); faults.set('ptx','404');
    await failure.goto(url+'#backend=ptx'); await failure.locator('#site-retry:enabled').click(); await failure.waitForFunction(() => siteLoader.status('ptx').phase === 'error'); await failure.waitForSelector('#site-retry:not([hidden])');
    assert.match(await failure.locator('#site-loading-message').textContent(), /最新版/);
    for(const width of [1440,1024,390,320]) {
      await failure.setViewportSize({width,height:950});
      assert.equal(await failure.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      await failure.screenshot({path:`.impeccable/review/loading-error-${width}.png`,fullPage:true});
    }
    faults.delete('ptx'); await failure.click('#site-retry'); await ready(failure,'ptx');
    await failure.close();
    faults.set('llvm','delay');
    const raced = await makePage(); await raced.goto(url+'#backend=llvm'); await raced.locator('#site-retry:enabled').click();
    await raced.locator('#site-loading a').click();
    await raced.waitForFunction(() => state.home && !document.body.classList.contains('data-loading'));
    await raced.waitForFunction(() => installedBackends.has('llvm'));
    assert.equal(await raced.locator('#home').isVisible(),true,'late completion must not replace Home');
    faults.delete('llvm'); await raced.close();

    faults.set('ccec','delay');
    const switched = await makePage(); await switched.goto(url+'#layer=interfaces');
    await switched.locator('#site-loading').waitFor({state:'visible'}); await switched.locator('#site-retry:enabled').click();
    await switched.selectOption('#backend','ptx'); await ready(switched,'ptx');
    await switched.waitForFunction(()=>installedBackends.has('ccec'));
    assert.equal(await switched.evaluate(()=>state.backend),'ptx','late load must not override a new selection');
    faults.delete('ccec'); await switched.close();

    faults.set('ptx','corrupt');
    const corrupted = await makePage(); await corrupted.goto(url+'#backend=ptx'); await corrupted.locator('#site-retry:enabled').click(); await corrupted.waitForFunction(() => siteLoader.status('ptx').phase === 'error');
    await corrupted.waitForSelector('#site-retry:not([hidden])');
    assert.match(await corrupted.locator('#site-loading-message').textContent(), /校验失败/);
    assert.equal(await corrupted.evaluate(() => installedBackends.has('ptx')), false);
    faults.delete('ptx'); await corrupted.click('#site-retry'); await ready(corrupted,'ptx'); await corrupted.close();

    // Existing older data requires an explicit update; cold navigation never fetches silently.
    const old = await makePage(); await old.goto(url);
    await old.evaluate(async () => {
      const cache = await caches.open('ackb-data-v1:' + new URL('.',location.href).pathname);
      await cache.put(new URL('assets/ptx.old.json.gz',location.href),new Response('previous version'));
    });
    await old.reload(); await old.waitForFunction(() => siteLoader.status('ptx').phase === 'update');
    assert.equal(await old.locator('#home [data-download-backend=ptx] button').getAttribute('aria-label'),'更新');
    const beforeUpdate = requests.filter(p=>p.includes('/ptx.')).length;
    await old.locator('#home a[data-database][href="#backend=ptx"]').click({force:true});
    assert.equal(await old.locator('#home').isVisible(),true);
    assert.equal(requests.filter(p=>p.includes('/ptx.')).length,beforeUpdate);
    faults.set('ptx','stream');
    await old.locator('#home [data-download-backend=ptx] button').click();
    await old.locator('#home [data-download-backend=ptx] progress').waitFor({state:'visible'});
    assert.equal(await old.locator('#home a[data-database][href="#backend=ptx"]').getAttribute('aria-disabled'),'true');
    await old.waitForFunction(() => {const {done,total}=siteLoader.progress('ptx'); return done>0 && done<total;});
    await old.screenshot({path:'.impeccable/review/download-progress.png',fullPage:true});
    await old.waitForFunction(()=>siteLoader.status('ptx').phase === 'ready'); faults.delete('ptx');
    await old.locator('#home a[data-database][href="#backend=ptx"]').click(); await ready(old,'ptx');
    assert.equal(await old.evaluate(async () => !!(await (await caches.open('ackb-data-v1:/')).match(new URL('assets/ptx.old.json.gz',location.href)))),false);
    await old.selectOption('#backend','llvm');
    await old.waitForFunction(()=>siteLoader.status('llvm').phase === 'missing');
    assert.equal(await old.locator('#database-download button').textContent(),'下载');
    assert.equal(await old.evaluate(()=>installedBackends.has('llvm')),false);
    await old.locator('#database-download button').click(); await ready(old,'llvm'); await old.close();

    // Older browsers and disabled persistent storage retain the same data.
    const fallback = await makePage();
    await fallback.addInitScript(() => {window.DecompressionStream=undefined; Object.defineProperty(window,'caches',{get(){throw new Error('storage unavailable');}});});
    await fallback.goto(url+'#backend=ptx&view=interfaces'); await ready(fallback,'ptx');
    assert.equal(await fallback.evaluate(() => visible.length),ptxInstructionCount);
    assert.ok(requests.includes('/'+manifest.datasets.ptx.plain.url)); await fallback.close();

    latestDatasets = {...manifest.datasets,ptx:{...manifest.datasets.ptx,gzip:{...manifest.datasets.ptx.gzip,sha256:'new-content'}}};
    revision='changed-data';
    const fresh = await makePage(); await fresh.goto(url);
    await fresh.waitForFunction(()=>siteLoader.isStale('ptx'));
    assert.equal(await fresh.locator('#home [data-download-backend=ptx] button').getAttribute('aria-label'),'更新');
    await fresh.evaluate(()=>location.hash='backend=ptx');
    await fresh.waitForFunction(()=>pendingNavigation?.backend === 'ptx');
    assert.equal(await fresh.locator('#database-download button').getAttribute('aria-label'),'更新');
    latestDatasets=manifest.datasets; revision=manifest.revision;
    await fresh.locator('#database-download button').click(); await fresh.waitForURL(/updated=/); await ready(fresh,'ptx');
    assert.equal(await fresh.evaluate(()=>state.backend),'ptx'); await fresh.close();

    revision='next-version';
    const updated = await makePage(); await updated.goto(url+'#backend=llvm'); await ready(updated,'llvm');
    await updated.waitForSelector('#site-update:not([hidden])');
    assert.equal(await updated.evaluate(() => siteLoader.revision),manifest.revision,'updates must not mix snapshots in an open page');
    await updated.locator('#site-update button').click(); await updated.waitForURL(/updated=/); await ready(updated,'llvm');
    assert.equal(new URL(updated.url()).hash.includes('backend=llvm'),true); await updated.close();
    faults.set('app','404');
    const stale = await makePage(); await stale.goto(url+'#backend=llvm');
    await stale.waitForSelector('#site-update:not([hidden])');
    assert.equal(await stale.locator('#home').isVisible(),true,'HTML remains readable when a stale script URL is gone');
    faults.delete('app');
    await stale.locator('#site-update button').click(); await stale.waitForURL(/updated=/); await ready(stale,'llvm'); await stale.close();
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({ok:true,initialBytes,compressedDatasets:Object.fromEntries(Object.entries(manifest.datasets).map(([k,v])=>[k,v.gzip.bytes]))}));
  } finally {await browser.close(); await new Promise(resolve=>server.close(resolve));}
})().catch(error=>{console.error(error);process.exitCode=1;});
