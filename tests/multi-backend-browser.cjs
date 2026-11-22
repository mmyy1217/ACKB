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
    await page.goto(url+'#layer=interfaces');
    await page.waitForSelector('#rows .row-button');

    assert.deepEqual(await page.locator('#backend option').allTextContents(), [
      'NVVM IR', 'LLVM IR', 'CCEC 编程接口', 'CCEC Builtins', 'AscendC 基础 C++ API', 'AscendC C / SIMT API',
      'CCE Dialect 语义 Ops', 'CCE Dialect LLVM Intrinsics', 'PTX 虚拟指令集',
    ]);
    await page.selectOption('#backend', 'ccec-intrinsics');
    assert.match(await page.locator('#unknown-hint').innerText(), /2,839/);
    await page.click('#show-hidden');
    assert.match(await page.locator('#result-count').innerText(), /4,353/);
    await page.uncheck('#include-unknown');
    for (const [name, count] of [['vldsx1_', 34], ['vstsx1_', 34], ['vlds', 68], ['vsts', 37]]) {
      await page.fill('#search', name);
      assert.equal(await page.locator('#rows tr').count(), 0);
      assert.match(await page.locator('#empty p').innerText(), new RegExp(`${count} 个匹配条目因 950 条件待确认被隐藏`));
      await page.click('#empty-unknown');
      assert.match(await page.locator('#result-count').innerText(), new RegExp(`${count} 个唯一 op`));
      assert.equal(await page.locator('#rows tr').count(), Math.min(60, count));
      await page.reload();
      assert.equal(await page.locator('#include-unknown').isChecked(), true);
      await page.uncheck('#include-unknown');
    }
    await page.fill('#search', 'vldsx1_');
    await page.locator('[data-family="矩阵 / Cube"]').click();
    assert.equal(await page.locator('#empty-unknown').isVisible(), false);
    await page.click('#reset');
    await page.fill('#search', 'vldsx1_');
    for (const width of [1440, 320]) {
      await page.setViewportSize({width, height: 950});
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
      await page.screenshot({path: path.join(review, `builtin-hidden-${width}.png`)});
    }
    await page.setViewportSize({width: 1440, height: 950});
    await page.fill('#search', 'no_such_instruction_123');
    assert.equal(await page.locator('#empty-unknown').isVisible(), false);
    assert.equal(await page.locator('#unknown-hint').isVisible(), false);

    // The common DataCopyImpl name must not join load and store paths together.
    await page.selectOption('#backend', 'ascendc');
    for (const [name, expected, forbidden] of [['LoadAlign', /__builtin_cce_vldsx1_/, /__builtin_cce_vstsx1_/],
                                              ['StoreAlign', /__builtin_cce_vstsx1_/, /__builtin_cce_vldsx1_/]]) {
      await page.fill('#search', 'AscendC::Reg::' + name);
      await page.locator('#rows .row-button').filter({hasText: new RegExp(`^${name}$`)}).click();
      assert.match(await page.locator('#detail').innerText(), expected);
      assert.doesNotMatch(await page.locator('#detail').innerText(), forbidden);
      await page.locator('.call-trace > summary').click();
      await page.locator('.call-trace details > summary').first().click();
      assert.match(await page.locator('.call-trace').innerText(), /DataCopyImpl/);
      assert.match(await page.locator('.call-trace').innerText(), /kernel_reg_compute_datacopy_intf_impl.h/);
      assert.match(await page.locator('.call-trace').innerText(), /SHA-256 [a-f0-9]{64}/);
    }
    await page.screenshot({path: path.join(review, 'reg-call-trace-1440.png')});
    await page.locator('#detail [data-op-ref^="ccec_op___builtin_cce_vstsx1_"]').first().click();
    assert.equal(await page.locator('#backend').inputValue(), 'ccec-intrinsics');
    assert.equal(await page.locator('#include-unknown').isChecked(), true);
    assert.match(await page.locator('#detail').innerText(), /__builtin_cce_vstsx1_/);
    await page.click('#reset');

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
    assert.match(await page.locator('#result-count').innerText(), /491 个 AscendC 基础 C\+\+ API/);
    for (const [sym, expectRe] of [['DataCopy', /__builtin_cce_copy_gm_to_ubuf/], ['Add', /__builtin_cce_vadd/], ['Mmad', /__builtin_cce_mad/]]) {
      await page.fill('#search', sym);
      await page.locator('#rows .row-button').filter({hasText: new RegExp(`^${sym}$`)}).first().click();
      assert.match(await page.locator('#detail').innerText(), /AscendC 基础 C\+\+ API \(basic_api\)/);
      assert.match(await page.locator('#detail').innerText(), expectRe);
    }
    await page.fill('#search', 'DataCopy');
    await page.locator('#rows .row-button').filter({hasText: /^DataCopy$/}).first().click();
    await page.screenshot({path: path.join(review, 'ascendc-basic-1440.png'), fullPage: true});

    // 2. Test AscendC lower layer (c_api + simt_api) and jump to CCEC Builtins
    await page.selectOption('#backend', 'ascendc-capi');
    assert.match(await page.locator('#result-count').innerText(), /1,304 个 AscendC C \/ SIMT API/);
    await page.fill('#search', 'asc_copy_gm2ub');
    await page.locator('#rows .row-button').filter({hasText: /^asc_copy_gm2ub$/}).first().click();
    await page.locator('#detail [data-op-ref="ccec_op___builtin_cce_copy_gm_to_ubuf_align_v2"]').first().click();
    assert.equal(await page.locator('#backend').inputValue(), 'ccec-intrinsics');
    assert.match(await page.locator('#detail').innerText(), /__builtin_cce_copy_gm_to_ubuf_align_v2/);
    assert.equal(await page.locator('#rows tr.selected').count(), 1);

    await page.selectOption('#backend', 'ascendc-capi');
    await page.fill('#search', 'asc_mmad');
    await page.locator('#rows .row-button').filter({hasText: /^asc_mmad$/}).first().click();
    assert.match(await page.locator('#detail').innerText(), /AscendC C \/ SIMT API \(c_api \/ simt_api\)/);
    assert.match(await page.locator('#detail').innerText(), /__builtin_cce_mad/);
    await page.screenshot({path: path.join(review, 'ascendc-capi-1440.png'), fullPage: true});

    // Click CCEC Intrinsic link from asc_mmad detail and verify it lands on ccec-intrinsics
    await page.locator('#detail [data-op-ref="ccec_op___builtin_cce_mad"]').first().click();
    assert.equal(await page.locator('#backend').inputValue(), 'ccec-intrinsics');
    assert.match(await page.locator('#detail').innerText(), /__builtin_cce_mad/);

    // 3. Test CCE Dialect upper layer (CCE Dialect 语义 Ops) and jump to lower layer (CCE Dialect LLVM Intrinsics)
    await page.selectOption('#backend', 'cce-dialect');
    assert.match(await page.locator('#result-count').innerText(), /247 个 Dialect Op/);
    await page.fill('#search', 'cce.mad');
    await page.locator('#rows .row-button').filter({hasText: /^cce\.mad$/}).first().click();
    assert.match(await page.locator('#detail').innerText(), /CCESpec\.md 中文规格说明/);
    await page.screenshot({path: path.join(review, 'cce-dialect-ops-1440.png'), fullPage: true});

    // Jump from cce.mad to its lowered CCE Dialect LLVM Intrinsic
    await page.locator('#detail [data-op-ref^="cce_dialect_intr_"]').first().click();
    assert.equal(await page.locator('#backend').inputValue(), 'cce-dialect-intrinsics');
    assert.match(await page.locator('#detail').innerText(), /CCE Dialect LLVM Intrinsic/);
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
    assert.equal(await page.locator('#dialect-path, #dialect-source').count(), 0);
    assert.equal(await page.locator('#group').isVisible(), false);
    assert.equal(await page.locator('#file').isVisible(), false);
    assert.match(await page.locator('#result-count').innerText(), /1,234 个/);
    assert.equal(await page.locator('#dialect-cann-heading').textContent(), 'CANN LLVM intrinsic');
    await page.fill('#search', 'llvm.hivm.vadd.s.z.v128f16');
    await page.locator('#rows .row-button').click();
    assert.match(await page.locator('#detail').innerText(), /20261009.01[\s\S]*exit code 139/);
    await page.fill('#search', 'llvm.hivm.vadd.s.m.v128f16');
    const baseLink = page.locator('#rows a').first();
    assert.match(await baseLink.innerText(), /重载基名.*llvm\.hivm\.vadd\.s\.m$/);
    await baseLink.click();
    await page.waitForFunction(() => document.querySelector('#detail h2')?.textContent === 'llvm.hivm.vadd.s.m');
    await page.selectOption('#backend', 'cce-dialect-intrinsics');
    await page.fill('#search', 'llvm.hivm.vmulscvt.v128f16');
    await page.locator('#rows .row-button').click();
    await page.click('#tab-experiments');
    assert.match(await page.locator('#detail').innerText(), /call .*@llvm\.hivm\.vmulscvt\.v128f16/);
    await page.goto(url + '#backend=cce-dialect&layer=intrinsics&path=rejected&file=old&group=old');
    await page.waitForFunction(() => document.querySelector('#result-count').textContent.includes('1,234'));
    const exportReady = page.waitForEvent('download');
    await page.click('#download');
    const dialectExport = JSON.parse(await fs.readFile(await (await exportReady).path(), 'utf8'));
    assert.equal(dialectExport.records.length, 1234);
    assert.ok(dialectExport.records.every(r => r.path_status === 'confirmed'));
    const matches = dialectExport.records.map(row => row.cann_correspondence);
    assert.equal(matches.filter(m => m.kind === 'exact').length, 536);
    assert.equal(matches.filter(m => m.kind === 'overload_base').length, 446);
    assert.equal(matches.filter(m => m.package_file).length, 1);
    assert.equal(matches.filter(m => m.experiment?.exit_code === 1).length, 249);
    assert.equal(matches.filter(m => m.experiment?.exit_code === 0).length, 3);
    await page.fill('#search', 'llvm.hivm.SET.ATOMIC.f16');
    await page.locator('#rows .row-button').click();
    await page.click('#tab-experiments');
    assert.match(await page.locator('#detail').innerText(), /UND llvm\.hivm\.SET\.ATOMIC\.f16/);
    assert.doesNotMatch(await page.locator('#detail').innerText(), /尚无编译/);
    await page.fill('#search', 'llvm.hivm.atom.ADD.S.s16');
    assert.equal(await page.locator('#rows .row-button').count(), 0);
    await page.fill('#search', 'llvm.hivm.ldg.cache.s32');
    assert.equal(await page.locator('#rows tr').count(), 1);
    assert.match(await page.locator('#rows td:nth-child(2)').innerText(), /CCETranslateSIMT.cpp/);
    await page.locator('#rows .row-button').click();
    assert.match(await page.locator('#detail').innerText(), /cce.intr.simt.load/);
    assert.match(await page.locator('#detail').innerText(), /ldg\.\{cache\|uncache\}\.s<N>/);
    await page.reload();
    assert.match(await page.locator('#detail').innerText(), /cce.intr.simt.load/);
    await page.click('#reset');
    await page.click('#coverage');
    assert.match(await page.locator('#report').innerText(), /未建立静态 LLVM 映射 · 1/);
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
