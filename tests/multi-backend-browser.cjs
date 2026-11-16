const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const {pathToFileURL} = require('node:url');
const {chromium} = require(process.env.CCE_OPS_PLAYWRIGHT || 'playwright');

(async () => {
  const root = path.resolve(__dirname, '..');
  const review = path.join(root, '.impeccable/review');
  await fs.mkdir(review, {recursive: true});
  const browser = await chromium.launch({
    executablePath: process.env.CCE_OPS_CHROME,
    headless: true,
    args: ['--no-sandbox'],
  });
  try {
    const page = await browser.newPage({viewport: {width: 1440, height: 950}});
    const errors = [], network = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('request', r => { if (/^https?:/.test(r.url())) network.push(r.url()); });
    const url = pathToFileURL(path.join(root, 'dist/index.html')).href;
    await page.goto(url);
    await page.waitForSelector('#rows .row-button');

    // 0. Verify no expanded DMA sub-items (transfer:*) in sidebar across backends, and CCEC round-trip direct link <-> intrinsic jump
    for (const backendVal of ['ccec', 'ascendc', 'cce-dialect']) {
      await page.selectOption('#backend', backendVal);
      const transferCount = await page.locator('#families [data-family^="transfer:"]').count();
      assert.equal(transferCount, 0, `unexpected transfer:* sidebar items in ${backendVal}`);
    }
    await page.selectOption('#backend', 'ccec');
    await page.fill('#search', 'copy_gm_to_cbuf_align_v2');
    await page.locator('#rows .row-button').filter({hasText: /copy_gm_to_cbuf_align_v2/}).first().click();
    await page.locator('#detail [data-op-ref="ccec_op___builtin_cce_copy_gm_to_cbuf_align_v2"]').first().click();
    assert.equal(await page.locator('#backend').inputValue(), 'ccec-intrinsics');
    assert.match(await page.locator('#detail').innerText(), /__builtin_cce_copy_gm_to_cbuf_align_v2/);
    assert.equal(await page.locator('#rows tr.selected').count(), 1);
    const backDetails = page.locator('#detail details:has([data-op-ref]:not([data-op-ref^="ccec_op_"]))').first();
    await backDetails.locator('summary').first().click();
    await backDetails.locator('[data-op-ref]:not([data-op-ref^="ccec_op_"])').first().click();
    assert.equal(await page.locator('#backend').inputValue(), 'ccec');

    // 1. Test AscendC upper layer (basic_api)
    await page.selectOption('#backend', 'ascendc');
    assert.match(await page.locator('#result-count').innerText(), /491 个 AscendC 接口/);
    for (const [sym, expectRe] of [['DataCopy', /__builtin_cce_copy_gm_to_ubuf/], ['Add', /__builtin_cce_vadd/], ['Mmad', /__builtin_cce_mad/]]) {
      await page.fill('#search', sym);
      await page.locator('#rows .row-button').filter({hasText: new RegExp(`^${sym}$`)}).first().click();
      assert.match(await page.locator('#detail').innerText(), /AscendC 接口 \(basic_api\)/);
      assert.match(await page.locator('#detail').innerText(), expectRe);
    }
    await page.fill('#search', 'DataCopy');
    await page.locator('#rows .row-button').filter({hasText: /^DataCopy$/}).first().click();
    await page.screenshot({path: path.join(review, 'ascendc-basic-1440.png'), fullPage: true});

    // 2. Test AscendC lower layer (c_api + simt_api) and jump to CCEC Intrinsics
    await page.selectOption('#backend', 'ascendc-capi');
    assert.match(await page.locator('#result-count').innerText(), /1,304 个 ASC 底层接口/);
    await page.fill('#search', 'asc_copy_gm2ub');
    await page.locator('#rows .row-button').filter({hasText: /^asc_copy_gm2ub$/}).first().click();
    await page.locator('#detail [data-op-ref="ccec_op___builtin_cce_copy_gm_to_ubuf_align_v2"]').first().click();
    assert.equal(await page.locator('#backend').inputValue(), 'ccec-intrinsics');
    assert.match(await page.locator('#detail').innerText(), /__builtin_cce_copy_gm_to_ubuf_align_v2/);
    assert.equal(await page.locator('#rows tr.selected').count(), 1);

    await page.selectOption('#backend', 'ascendc-capi');
    await page.fill('#search', 'asc_mmad');
    await page.locator('#rows .row-button').filter({hasText: /^asc_mmad$/}).first().click();
    assert.match(await page.locator('#detail').innerText(), /AscendC 底层接口 \(c_api \/ simt_api\)/);
    assert.match(await page.locator('#detail').innerText(), /__builtin_cce_mad/);
    await page.screenshot({path: path.join(review, 'ascendc-capi-1440.png'), fullPage: true});

    // Click CCEC Intrinsic link from asc_mmad detail and verify it lands on ccec-intrinsics
    await page.locator('#detail [data-op-ref="ccec_op___builtin_cce_mad"]').first().click();
    assert.equal(await page.locator('#backend').inputValue(), 'ccec-intrinsics');
    assert.match(await page.locator('#detail').innerText(), /__builtin_cce_mad/);

    // 3. Test CCE Dialect upper layer (CCE Dialect Ops) and jump to lower layer (CCE Dialect Intrinsics)
    await page.selectOption('#backend', 'cce-dialect');
    assert.match(await page.locator('#result-count').innerText(), /247 个 Dialect Op/);
    await page.fill('#search', 'cce.mad');
    await page.locator('#rows .row-button').filter({hasText: /^cce\.mad$/}).first().click();
    assert.match(await page.locator('#detail').innerText(), /CCESpec\.md 中文规格说明/);
    await page.screenshot({path: path.join(review, 'cce-dialect-ops-1440.png'), fullPage: true});

    // Jump from cce.mad to its lowered CCE Dialect Intrinsic
    await page.locator('#detail [data-op-ref^="cce_dialect_intr_"]').first().click();
    assert.equal(await page.locator('#backend').inputValue(), 'cce-dialect-intrinsics');
    assert.match(await page.locator('#detail').innerText(), /CCE Dialect Intrinsic/);
    await page.screenshot({path: path.join(review, 'cce-dialect-intrinsics-1440.png'), fullPage: true});

    // Verify llvm.hivm.MOV.OUT.TO.UB.ALIGN.V2.f16.DV -> ccec_op___builtin_cce_copy_gm_to_ubuf_align_v2
    await page.fill('#search', 'llvm.hivm.MOV.OUT.TO.UB.ALIGN.V2.f16.DV');
    await page.locator('#rows .row-button').filter({hasText: /^llvm\.hivm\.MOV\.OUT\.TO\.UB\.ALIGN\.V2\.f16\.DV$/}).first().click();
    await page.locator('#detail [data-op-ref="ccec_op___builtin_cce_copy_gm_to_ubuf_align_v2"]').first().click();
    assert.equal(await page.locator('#backend').inputValue(), 'ccec-intrinsics');
    assert.match(await page.locator('#detail').innerText(), /__builtin_cce_copy_gm_to_ubuf_align_v2/);
    assert.equal(await page.locator('#rows tr.selected').count(), 1);

    // Full parameter forms survive selection, deep links and offline export.
    await page.selectOption('#backend', 'ascendc-capi');
    await page.fill('#search', 'asc_cast');
    await page.locator('#rows .row-button').filter({hasText: /^asc_cast$/}).first().click();
    assert.equal(await page.locator('#ascendc-form option').count(), 467);
    await page.selectOption('#ascendc-form', '466');
    await page.reload();
    assert.equal(await page.locator('#ascendc-form').inputValue(), '466');
    assert.match(await page.locator('#detail').innerText(), /候选关联/);
    const downloadPromise = page.waitForEvent('download');
    await page.click('#download');
    const download = await downloadPromise;
    const exported = JSON.parse(await fs.readFile(await download.path(), 'utf8'));
    assert.equal(exported.records.find(r => r.name === 'asc_cast').forms.length, 467);
    assert.ok(Object.keys(exported.files).length > 300);
    assert.ok(exported.limitations.length);
    await page.fill('#search', '__bfloat1622fp4x2_e1m2_rn');
    await page.check('#include-unknown');
    assert.equal(await page.locator('#rows .row-button').count(), 0);

    await page.selectOption('#backend', 'cce-dialect-intrinsics');
    assert.match(await page.locator('#result-count').innerText(), /1,069/);
    await page.click('#coverage');
    assert.match(await page.locator('#report').innerText(), /未建立静态 LLVM 映射 · 5/);
    assert.doesNotMatch(await page.locator('#report').innerText(), /42\.5%/);

    // Inspect each new surface on desktop and narrow layouts, not only the final CCEC jump.
    for (const backend of ['ascendc', 'ascendc-capi', 'cce-dialect', 'cce-dialect-intrinsics']) {
      await page.selectOption('#backend', backend);
      for (const width of [1440, 1024, 390, 320]) {
        await page.setViewportSize({width, height: 950});
        await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
        assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `${backend} overflow at ${width}`);
        await page.screenshot({path: path.join(review, `fixed-${backend}-${width}.png`)});
      }
    }

    assert.deepEqual(errors, []);
    assert.deepEqual(network, []);
    console.log('PASS: AscendC (basic_api & c_api) and CCE Dialect (Ops & Intrinsics) browser checks passed');
  } finally {
    await browser.close();
  }
})().catch(e => {
  console.error(e);
  process.exitCode = 1;
});
