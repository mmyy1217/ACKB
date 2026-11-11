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
        continuousPage: getComputedStyle(document.querySelector('.table-scroll')).overflowY === 'visible' && document.documentElement.scrollHeight > innerHeight,
        rowNameLines: box('.row-name').height / parseFloat(getComputedStyle(document.querySelector('.row-name')).lineHeight)
      };
    });
    assert.ok(density.headerHeight <= 40 && density.singleToolbar, 'Desktop controls must share one compact topbar');
    assert.ok(density.sidebarWidth <= 136 && density.detailWidth <= 330 && density.listWidth > density.detailWidth * 2, 'Catalog must own most of the width');
    assert.ok(density.rowHeight <= 26 && density.rowNameLines <= 1 && density.columns === 4, 'Name, family, domain and overload count must share one compact row');
    assert.ok(density.continuousPage, 'The instruction list must flow vertically in the document');
    assert.equal(await page.locator('#rows tr').count(), 60);
    assert.equal(await page.locator('#previous, #next').count(), 0);
    const drag = async (selector, delta) => {
      const bounds = await page.locator(selector).boundingBox();
      await page.mouse.move(bounds.x + bounds.width / 2, bounds.y + 120);
      await page.mouse.down();
      await page.mouse.move(bounds.x + bounds.width / 2 + delta, bounds.y + 120, { steps: 5 });
      await page.mouse.up();
    };
    await drag('#resize-sidebar', 80);
    await drag('#resize-detail', -100);
    assert.equal(await page.locator('#resize-sidebar').getAttribute('aria-valuenow'), '216');
    assert.equal(await page.locator('#resize-detail').getAttribute('aria-valuenow'), '430');
    await fit();
    await capture('resized');
    await page.reload();
    assert.equal(await page.locator('#resize-sidebar').getAttribute('aria-valuenow'), '216');
    assert.equal(await page.locator('#resize-detail').getAttribute('aria-valuenow'), '430');
    await page.locator('#resize-sidebar').focus();
    await page.keyboard.press('ArrowRight');
    assert.equal(await page.locator('#resize-sidebar').getAttribute('aria-valuenow'), '226');
    await page.keyboard.press('Home');
    assert.equal(await page.locator('#resize-sidebar').getAttribute('aria-valuenow'), '128');
    await page.keyboard.press('End');
    assert.equal(await page.locator('#resize-sidebar').getAttribute('aria-valuenow'), await page.locator('#resize-sidebar').getAttribute('aria-valuemax'));
    await page.locator('#resize-sidebar').dblclick({ position: { x: 2, y: 100 } });
    await page.locator('#resize-detail').focus();
    await page.keyboard.press('ArrowLeft');
    assert.equal(await page.locator('#resize-detail').getAttribute('aria-valuenow'), '440');
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('#resize-sidebar').getAttribute('aria-valuenow'), '136');
    assert.equal(await page.locator('#resize-detail').getAttribute('aria-valuenow'), '330');
    const initialIDs = await page.locator('#rows .row-button').evaluateAll(rows => rows.map(row => row.dataset.id));
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    await page.waitForFunction(() => document.querySelectorAll('#rows tr').length >= 120);
    assert.deepEqual((await page.locator('#rows .row-button').evaluateAll(rows => rows.map(row => row.dataset.id))).slice(0, 60), initialIDs, 'Appending must retain all earlier rows in order');
    const sticky = await page.evaluate(() => ['.topbar', '.sidebar', '#detail'].map(selector => document.querySelector(selector).getBoundingClientRect().top));
    assert.deepEqual(sticky, [0, 40, 40]);
    assert.ok(await page.evaluate(() => scrollY > 0), 'Loading must retain document scroll position');
    await page.screenshot({ path: path.join(review, 'desktop-continuous.png') });
    await page.locator('#rows .row-button').nth(90).click();
    const laterName = await page.locator('.detail-heading h2').innerText();
    await page.reload();
    assert.equal(await page.locator('.detail-heading h2').innerText(), laterName);
    assert.ok(await page.locator('#rows tr').count() >= 91, 'Deep links must load the selected row beyond the first batch');
    await page.waitForFunction(() => scrollY > 0);
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
    for (let batch = 0; batch < 5 && !/已显示全部/.test(await page.locator('#load-status').innerText()); batch++) {
      const before = await page.locator('#rows tr').count();
      await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
      await page.waitForFunction(count => document.querySelectorAll('#rows tr').length > count, before);
    }
    assert.match(await page.locator('#load-status').innerText(), /已显示全部/);
    assert.equal(await page.locator('#rows tr').count(), 127, 'The final partial batch must load without omissions or duplicates');
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
    assert.equal(await page.locator('#resize-sidebar').isVisible(), false);
    const mobileCount = await page.locator('#rows tr').count();
    await page.evaluate(() => window.scrollTo(0, document.documentElement.scrollHeight));
    await page.waitForFunction(count => document.querySelectorAll('#rows tr').length > count, mobileCount);
    const beforeDetail = await page.locator('#rows tr').count();
    await page.locator('#rows .row-button').first().click();
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert.equal(await page.locator('#rows tr').count(), beforeDetail, 'Reading mobile detail must not push it away by loading more rows');
    await page.locator('#back-to-list').click();
    assert.equal(await page.locator('#rows [aria-current="true"]').evaluate(el => el === document.activeElement), true);
    await page.locator('#search').fill('__abs');
    await page.locator('#group').selectOption('SIMT');
    await page.locator('#rows .row-button').first().click();
    await page.locator('.related-link').first().click();
    assert.match(await page.locator('#page-title').innerText(), /配套定义/);
    const relatedDetailVisible = await page.locator('#detail').evaluate(el => {
      const bounds = el.getBoundingClientRect();
      return bounds.top >= document.querySelector('.topbar').getBoundingClientRect().bottom && bounds.bottom <= innerHeight;
    });
    assert.ok(relatedDetailVisible, 'Following a related type on mobile must keep its detail fully in view');
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
    console.log('PASS: continuous append/final batch, resizable panels/persistence/keyboard, sticky panes, deep links, mobile detail return, offline search/filters/overloads/source/report/export, 1440/1024/390/320 layouts.');
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
