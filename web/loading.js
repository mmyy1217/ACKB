'use strict';
// Offline builds have no manifest and never fetch a resource.
const siteManifest = document.querySelector('#asset-manifest');
const siteLoader = siteManifest ? (() => {
  const manifest = JSON.parse(siteManifest.textContent);
  const pending = new Map(), snapshots = new Map();
  let labels = new Map();
  const cacheName = 'ackb-data-v1:' + new URL('.', location.href).pathname;
  const assetURL = entry => new URL(entry.url, location.href).href;
  async function cache() {
    try { return await caches.open(cacheName); } catch { return null; }
  }
  async function checked(response, entry) {
    if (!response?.ok) throw new Error(response?.status === 404 ? '此版本的数据文件已更新，请刷新到最新版。' : '数据下载失败，请检查网络后重试。');
    const bytes = await response.arrayBuffer();
    const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), b => b.toString(16).padStart(2, '0')).join('');
    if (bytes.byteLength !== entry.bytes || digest !== entry.sha256) throw new Error('数据校验失败，请重试；若仍失败，请刷新到最新版。');
    return bytes;
  }
  async function fetchBytes(entry) {
    const url = assetURL(entry), storage = await cache();
    const hit = await storage?.match(url).catch(() => null);
    if (hit) {
      try { return await checked(hit, entry); }
      catch { await storage.delete(url).catch(() => {}); }
    }
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 90000);
    try {
      const response = await fetch(url, {signal: controller.signal, cache: 'no-cache'});
      const bytes = await checked(response, entry);
      // Cache failure (quota/private mode) must not prevent reading.
      await storage?.put(url, new Response(bytes)).catch(() => {});
      return bytes;
    } finally { clearTimeout(timeout); }
  }
  async function dataset(name) {
    if (snapshots.has(name)) return snapshots.get(name);
    if (pending.has(name)) return pending.get(name);
    const job = (async () => {
      if (manifest.schema !== 'ackb.site.v1') throw new Error('页面与数据格式不兼容，请刷新到最新版。');
      const entry = manifest.datasets[name];
      if (!entry) throw new Error('当前版本没有此数据库。');
      const compressed = typeof DecompressionStream === 'function';
      const bytes = await fetchBytes(entry[compressed ? 'gzip' : 'plain']);
      const stream = new Blob([bytes]).stream();
      const text = await new Response(compressed ? stream.pipeThrough(new DecompressionStream('gzip')) : stream).text();
      const envelope = JSON.parse(text);
      if (envelope.schema !== manifest.schema || envelope.dataset !== name || !envelope.payload) throw new Error('数据版本或身份不匹配，请刷新到最新版。');
      snapshots.set(name, envelope.payload);
      if (name === 'navigation') labels = new Map(envelope.payload.labels.map(([id, name, backend]) => [id, {id, name, backend}]));
      return envelope.payload;
    })();
    pending.set(name, job);
    try { return await job; } finally { pending.delete(name); }
  }
  async function ensure(backend) {
    const [payload, navigation] = await Promise.all([dataset(backend), backend === 'ptx' ? null : dataset('navigation')]);
    return {payload, navigation};
  }
  async function maintain() {
    const storage = await cache();
    const keep = new Set(Object.values(manifest.datasets).flatMap(pair => Object.values(pair).map(assetURL)));
    for (const key of await storage?.keys().catch(() => []) || []) if (!keep.has(key.url)) await storage.delete(key).catch(() => {});
    try {
      const response = await fetch('manifest.json?check=' + Date.now(), {cache: 'no-store'});
      if (!response.ok) return;
      const latest = await response.json();
      if (latest.revision && latest.revision !== manifest.revision) document.querySelector('#site-update').hidden = false;
    } catch { /* The current snapshot can still be used from cache. */ }
  }
  setTimeout(maintain, 1000);
  return {ensure, lookup: id => labels.get(id), revision: manifest.revision};
})() : null;

function refreshSite() {
  const url = new URL(location.href);
  url.searchParams.set('updated', Date.now());
  location.replace(url.href);
}

function backendForLink(id, fallback = 'ccec') {
  const known = siteLoader?.lookup(id)?.backend;
  if (known) return known;
  if (id.startsWith('llvm_')) return 'llvm';
  if (id.startsWith('ascendc_')) return 'ascendc';
  if (id.startsWith('cce_dialect_')) return 'cce-dialect';
  return fallback;
}

let siteNavigation = 0;
const installedBackends = new Set();
function navigateWithData(backend, action) {
  const request = ++siteNavigation;
  const panel = document.querySelector('#site-loading');
  const finish = () => {
    panel.hidden = true;
    document.body.classList.remove('data-loading');
    action();
  };
  if (!siteLoader || !backend || installedBackends.has(backend)) { finish(); return; }
  document.body.classList.add('data-loading');
  const selector = document.querySelector('#backend');
  if (!selector.value.startsWith(backend)) selector.value = backend;
  panel.hidden = false;
  panel.setAttribute('aria-busy', 'true');
  document.querySelector('#site-loading-title').textContent = '正在加载' + ({ccec:' CCEC',ptx:' PTX',ascendc:' AscendC','cce-dialect':' CCE Dialect',llvm:' LLVM IR'}[backend] || '数据库');
  document.querySelector('#site-loading-message').textContent = '首次打开需要下载此数据库，后续访问会复用本地缓存。';
  document.querySelector('#site-retry').hidden = true;
  // Keep this asynchronous work owned by the latest navigation, including Home/Back.
  siteLoader.ensure(backend).then(({payload, navigation}) => {
    if (!installedBackends.has(backend)) { installBackend(backend, payload, navigation); installedBackends.add(backend); }
    if (request === siteNavigation) { panel.setAttribute('aria-busy','false'); finish(); }
  }).catch(error => {
    if (request !== siteNavigation) return;
    panel.setAttribute('aria-busy','false');
    document.querySelector('#site-loading-title').textContent = '数据库暂未加载';
    document.querySelector('#site-loading-message').textContent = error.name === 'AbortError' ? '下载超时，请检查网络后重试。' : error.name === 'TypeError' ? '无法连接数据文件，请检查网络后重试。' : error.message;
    const retry = document.querySelector('#site-retry');
    retry.hidden = false; retry.onclick = () => navigateWithData(backend, action);
  });
}
