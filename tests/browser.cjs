const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require(process.env.CCE_OPS_PLAYWRIGHT || 'playwright');

(async () => {
  const root = path.resolve(__dirname, '..');
  const review = path.join(root, '.impeccable/review');
  await fs.mkdir(review, { recursive: true });
  const browser = await chromium.launch({
    ...(process.env.CCE_OPS_CHROME ? { executablePath: process.env.CCE_OPS_CHROME } : {}),
    headless: true,
    args: ['--no-sandbox']
  });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
  const errors = [], network = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => { if (/^https?:/.test(request.url())) network.push(request.url()); });
  const entry = pathToFileURL(path.join(root, 'dist/index.html')).href;
  const capture = async name => {
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: path.join(review, name + '.png'), fullPage: true });
  };
  const fit = async () => assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true, 'Page overflows horizontally');
  try {
    await page.goto(entry);
    await page.locator('.detail-heading h2').waitFor();
    await fit();
    assert.match(await page.locator('#result-count').innerText(), /5,714/);
    const density = await page.evaluate(() => {
      const box = selector => document.querySelector(selector).getBoundingClientRect();
      const header = box('.topbar');
      return {
        headerHeight: header.height,
        sidebarWidth: box('.sidebar').width,
        detailWidth: box('#detail').width,
        listWidth: box('.list-pane').width,
        rowHeight: box('#rows tr').height,
        singleToolbar: ['.brand','#page-title','#search','#group','#file','#download'].every(selector => {
          const bounds = box(selector);
          return bounds.top >= header.top && bounds.bottom <= header.bottom;
        }),
        columns: document.querySelector('#rows tr').children.length,
        panelsFit: box('.list-pane').bottom <= box('footer').top && box('#detail').bottom <= box('footer').top,
        rowNameLines: box('.row-name').height / parseFloat(getComputedStyle(document.querySelector('.row-name')).lineHeight)
      };
    });
    assert.ok(density.headerHeight <= 40 && density.singleToolbar, 'Desktop controls must share one compact topbar');
    assert.ok(density.sidebarWidth <= 136 && density.detailWidth <= 330 && density.listWidth > density.detailWidth * 2, 'Catalog must own most of the width');
    assert.ok(density.rowHeight <= 26 && density.rowNameLines <= 1 && density.columns === 4, 'Name, family, domain and overload count must share one compact row');
    assert.ok(density.panelsFit, 'List and detail must scroll inside the workspace above the footer');
    await page.keyboard.press('/');
    assert.equal(await page.locator('#search').evaluate(el => el === document.activeElement), true);
    await page.locator('#search').fill('avld');
    await page.locator('#group').selectOption('Vector / AVE');
    await page.locator('#rows .row-button').first().focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('#detail').evaluate(el => el === document.activeElement), true);
    assert.equal(await page.locator('.detail-heading h2').innerText(), 'avld');
    assert.equal(await page.locator('#overload option').count(), 11);
    await page.locator('#overload').selectOption({ index: 1 });
    assert.equal(await page.locator('#overload').evaluate(el => el === document.activeElement), true);
    assert.match(await page.locator('.signature').innerText(), /int16_t/);
    await page.locator('#tab-source').click();
    assert.match(await page.locator('#detail-content').innerText(), /__builtin_cce_avld_s16/);
    await page.locator('#tab-experiments').click();
    assert.match(await page.locator('#detail-content').innerText(), /尚未开展设备实验/);
    await page.locator('#tab-definition').click();
    await page.keyboard.press('ArrowRight');
    assert.equal(await page.locator('#tab-source').getAttribute('aria-selected'), 'true');
    const deepLink = page.url();
    await page.reload();
    assert.equal(page.url(), deepLink);
    assert.equal(await page.locator('.detail-heading h2').innerText(), 'avld');
    assert.match(await page.locator('.signature').innerText(), /int16_t/);
    await page.locator('#search').fill('no_such_interface_abcdefghijklmnopqrstuvwxyz');
    assert.equal(await page.locator('#empty').isVisible(), true);
    assert.equal(await page.locator('#rows tr').count(), 0);
    await page.locator('#empty-reset').click();
    await page.locator('[data-family="搬运 / DMA"]').click();
    assert.equal(await page.locator('#families .active').getAttribute('data-family'), '搬运 / DMA');
    await page.locator('#file').selectOption('__clang_cce_aicore_functions.h');
    assert.ok(await page.locator('#rows tr').count() > 0);
    await page.locator('[data-view="definitions"]').click();
    await page.locator('#search').fill('vector_f32');
    await page.locator('#rows .row-button').first().click();
    assert.match(await page.locator('.signature').innerText(), /typedef float vector_f32/);
    await page.locator('[data-view="report"]').click();
    assert.equal(await page.locator('.report-table').first().locator('tbody tr').count(), 23);
    await fit();
    await capture('report');
    const downloadEvent = page.waitForEvent('download');
    await page.locator('#download').click();
    const download = await downloadEvent;
    const exported = JSON.parse(await fs.readFile(await download.path(), 'utf8'));
    assert.equal(exported.version, '9.3.0~weekly.20261104.01');
    assert.equal(exported.files.length, 23);
    await page.locator('[data-view="interfaces"]').click();
    await capture('desktop');
    await page.locator('#tab-source').click();
    await capture('source');
    await page.setViewportSize({ width: 1024, height: 768 });
    await fit();
    await capture('tablet');
    await page.setViewportSize({ width: 390, height: 844 });
    await page.locator('#mobile-view').selectOption('interfaces');
    await page.locator('#search').fill('avld');
    await page.locator('#group').selectOption('Vector / AVE');
    await page.locator('#rows .row-button').first().click();
    await page.locator('#tab-source').click();
    await fit();
    await capture('mobile-source');
    await page.locator('#tab-definition').click();
    await page.evaluate(() => window.scrollTo(0, 0));
    await capture('mobile');
    await page.locator('#mobile-view').selectOption('report');
    await fit();
    await page.locator('#mobile-view').selectOption('definitions');
    await page.locator('#search').fill('no_results');
    await fit();
    assert.equal(await page.locator('#empty').isVisible(), true);
    await page.setViewportSize({ width: 320, height: 700 });
    await fit();
    assert.deepEqual(errors, [], 'Browser console errors');
    assert.deepEqual(network, [], 'Offline manual requested network resources');
    console.log('PASS: offline load, search, combined filters, overloads, source, tabs/keyboard, deep link, empty/reset, type lookup, report, export, 1440/1024/390/320 layouts.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
