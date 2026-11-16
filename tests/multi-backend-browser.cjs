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

    // 1. Test AscendC upper layer (basic_api)
    await page.selectOption('#backend', 'ascendc');
    assert.match(await page.locator('#result-count').innerText(), /477 个 AscendC 接口/);
    await page.fill('#search', 'DataCopy');
    await page.locator('#rows .row-button').filter({hasText: /^DataCopy$/}).first().click();
    assert.match(await page.locator('#detail').innerText(), /AscendC 接口 \(basic_api\)/);
    await page.screenshot({path: path.join(review, 'ascendc-basic-1440.png'), fullPage: true});

    // 2. Test AscendC lower layer (c_api + simt_api) and jump to CCEC Intrinsics
    await page.selectOption('#backend', 'ascendc-capi');
    assert.match(await page.locator('#result-count').innerText(), /1,372 个 ASC 底层接口/);
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

    // Check responsive widths (1024, 390, 320) have zero horizontal overflow
    for (const width of [1024, 390, 320]) {
      await page.setViewportSize({width, height: 950});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, `overflow at ${width}`);
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
