'use strict';
// Offline builds have no manifest and never fetch a resource.
const siteManifest = document.querySelector('#asset-manifest');
const siteLoader = siteManifest ? (() => {
  const manifest = JSON.parse(siteManifest.textContent);
  const pending = new Map(), snapshots = new Map();
  let labels = new Map();
  const stale = new Set();
  const states = new Map(), listeners = new Set(), transfers = new Map();
  const emit = () => listeners.forEach(fn => fn());
  const names = backend => backend === 'ptx' ? [backend] : [backend, 'navigation'];
  const entryFor = name => manifest.datasets[name][typeof DecompressionStream === 'function' ? 'gzip' : 'plain'];
  const status = backend => stale.has(backend) ? {phase:'update'} : states.get(backend) || {phase:'checking'};
  const cacheName = 'ackb-data-v1:' + new URL('.', location.href).pathname;
  const assetURL = entry => new URL(entry.url, location.href).href;
  async function cache() {
    try { return await caches.open(cacheName); } catch { return null; }
  }
  async function checked(response, entry, progress) {
    if (!response?.ok) throw new Error(response?.status === 404 ? '此版本的数据文件已更新，请刷新到最新版。' : '数据下载失败，请检查网络后重试。');
    let bytes;
    if (progress && response.body) {
      const reader = response.body.getReader(), chunks = []; let size = 0;
      while (true) { const {done,value} = await reader.read(); if (done) break; chunks.push(value); size += value.length; progress(size); }
      const joined = new Uint8Array(size); let offset = 0;
      for (const chunk of chunks) { joined.set(chunk,offset); offset += chunk.length; }
      bytes = joined.buffer;
    } else bytes = await response.arrayBuffer();
    const digest = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), b => b.toString(16).padStart(2, '0')).join('');
    if (bytes.byteLength !== entry.bytes || digest !== entry.sha256) throw new Error('数据校验失败，请重试；若仍失败，请刷新到最新版。');
    return bytes;
  }
  async function fetchBytes(entry, name) {
    const url = assetURL(entry), storage = await cache();
    const hit = await storage?.match(url).catch(() => null);
    if (hit) {
      try { const bytes = await checked(hit, entry); transfers.set(name, entry.bytes); emit(); return bytes; }
      catch { await storage.delete(url).catch(() => {}); }
    }
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 90000);
    try {
      const response = await fetch(url, {signal: controller.signal, cache: 'no-cache'});
      const bytes = await checked(response, entry, size => {transfers.set(name,size); emit();});
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
      const bytes = await fetchBytes(entry[compressed ? 'gzip' : 'plain'], name);
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
  const initialized = (async () => {
    const storage = await cache(), keys = await storage?.keys().catch(() => []) || [];
    const urls = new Set(keys.map(key => key.url));
    for (const backend of Object.keys(manifest.datasets).filter(name => name !== 'navigation')) {
      const current = names(backend).every(name => urls.has(assetURL(entryFor(name))));
      const old = keys.some(key => new URL(key.url).pathname.split('/').pop().startsWith(backend + '.'));
      states.set(backend, {phase:current ? 'ready' : old ? 'update' : 'missing'});
    }
    emit();
  })();
  async function ensure(backend) {
    await initialized;
    states.set(backend,{phase:'downloading'}); emit();
    try {
      const [payload, navigation] = await Promise.all([dataset(backend), backend === 'ptx' ? null : dataset('navigation')]);
      states.set(backend,{phase:'ready'}); emit();
      const storage = await cache();
      const keep = new Set(names(backend).flatMap(name => Object.values(manifest.datasets[name]).map(assetURL)));
      for (const key of await storage?.keys().catch(() => []) || []) {
        const file = new URL(key.url).pathname.split('/').pop();
        if (names(backend).some(name => file.startsWith(name + '.')) && !keep.has(key.url)) await storage.delete(key).catch(() => {});
      }
      return {payload, navigation};
    } catch(error) {
      states.set(backend,{phase:'error',error:error.name === 'AbortError' ? '下载超时，请重试。' : error.message}); emit(); throw error;
    }
  }
  function progress(backend) {
    const total = names(backend).reduce((sum,name) => sum + entryFor(name).bytes,0);
    const done = names(backend).reduce((sum,name) => sum + Math.min(entryFor(name).bytes,transfers.get(name) || 0),0);
    return {done,total};
  }
  async function maintain() {
    // Retain prior hashes until an explicit download replaces the database.
    try {
      const response = await fetch('manifest.json?check=' + Date.now(), {cache: 'no-store'});
      if (!response.ok) return;
      const latest = await response.json();
      if (latest.revision && latest.revision !== manifest.revision) {
        document.querySelector('#site-update').hidden = false;
        for (const backend of Object.keys(manifest.datasets).filter(name => name !== 'navigation')) {
          if (latest.datasets && names(backend).some(name => latest.datasets[name]?.gzip.sha256 !== manifest.datasets[name].gzip.sha256)) stale.add(backend);
        }
        emit();
      }
    } catch { /* The current snapshot can still be used from cache. */ }
  }
  setTimeout(maintain, 1000);
  return {ensure, status, isStale: backend => stale.has(backend), progress, initialized, subscribe: fn => listeners.add(fn), lookup: id => labels.get(id), revision: manifest.revision};
})() : null;

function refreshSite(backend = null) {
  const url = new URL(location.href);
  url.searchParams.set('updated', Date.now());
  if (backend) {
    url.searchParams.set('download',backend);
    const target = new URLSearchParams(url.hash.slice(1));
    if (!pendingNavigation || downloadBackend(target.get('backend') || 'ccec') !== backend) {
      const selected = document.querySelector('#backend').value;
      const layer = {'ccec':'interfaces','ccec-intrinsics':'intrinsics','ascendc':'basic','ascendc-capi':'capi','cce-dialect':'ops','cce-dialect-intrinsics':'intrinsics'}[selected];
      url.hash = 'backend=' + backend + (layer ? '&layer=' + layer : '');
    }
  }
  location.replace(url.href);
}

function backendForLink(id, fallback = 'ccec') {
  const known = siteLoader?.lookup(id)?.backend;
  if (known) return known;
  if(id.startsWith('nvvm_'))return 'nvvm';
  if (id.startsWith('llvm_')) return 'llvm';
  if (id.startsWith('ascendc_')) return 'ascendc';
  if (id.startsWith('cce_dialect_')) return 'cce-dialect';
  return fallback;
}

let siteNavigation = 0;
const installedBackends = new Set();
let pendingNavigation = null;
function navigateWithData(backend, action) {
  const request = ++siteNavigation;
  const panel = document.querySelector('#site-loading');
  const finish = () => {
    pendingNavigation = null;
    panel.hidden = true;
    document.body.classList.remove('data-loading');
    action();
    renderDownloads();
  };
  if (!siteLoader || !backend || (installedBackends.has(backend) && !siteLoader.isStale(backend))) { finish(); return; }
  pendingNavigation = {backend, request, finish};
  document.body.classList.add('data-loading');
  const selector = document.querySelector('#backend');
  if (!selector.value.startsWith(backend)) selector.value = backend;
  panel.hidden = false;
  siteLoader.initialized.then(() => {
    if (request !== siteNavigation) return;
    renderDownloads();
    if (['ready','downloading'].includes(siteLoader.status(backend).phase)) downloadDatabase(backend,true);
  });
}
function downloadBackend(value) {
  if (value.startsWith('cce-dialect')) return 'cce-dialect';
  if (value.startsWith('ascendc')) return 'ascendc';
  if (value.startsWith('ccec')) return 'ccec';
  return value;
}
const downloadJobs = new Map();
async function downloadDatabase(backend, open = false) {
  if (siteLoader.isStale(backend)) {refreshSite(backend); return;}
  if (!downloadJobs.has(backend)) {
    const job = siteLoader.ensure(backend).then(({payload,navigation}) => {
      if (!installedBackends.has(backend)) {installBackend(backend,payload,navigation); installedBackends.add(backend);}
    });
    downloadJobs.set(backend,job);
    job.finally(() => {downloadJobs.delete(backend); renderDownloads();}).catch(() => {});
  }
  try {
    await downloadJobs.get(backend);
    if (open && !siteLoader.isStale(backend) && pendingNavigation?.backend === backend && pendingNavigation.request === siteNavigation) pendingNavigation.finish();
  } catch { /* The shared status provides the retry action. */ }
}
function renderDownloads() {
  if (!siteLoader) return;
  if (pendingNavigation) document.querySelector('#database-download').dataset.downloadBackend = pendingNavigation.backend;
  for (const host of document.querySelectorAll('[data-download-backend]')) {
    const backend = host.dataset.downloadBackend, status = siteLoader.status(backend);
    const {done,total} = siteLoader.progress(backend), busy = ['checking','downloading'].includes(status.phase);
    const label = {checking:'检查缓存…',missing:'下载',update:'更新',ready:'已下载',downloading:done >= total ? '校验中…' : '下载中',error:'重试'}[status.phase];
    const button = host.querySelector('button'), text = host.querySelector('span'), bar = host.querySelector('progress');
    button.textContent = label;
    button.setAttribute('aria-label', label); button.title = label + (status.error ? '：' + status.error : ' · ' + (total / 1e6).toFixed(2) + ' MB');
    if (host.classList.contains('round-download')) {
      const paths = status.phase === 'ready' ? '<path d="m6 12 4 4 8-8"/>' : status.phase === 'update' || status.phase === 'error' ? '<path d="M19 8a8 8 0 1 0 1 7M19 3v5h-5"/>' : '<path d="M12 4v11m-4-4 4 4 4-4M5 17v3h14v-3"/>';
      button.innerHTML = '<svg viewBox="0 0 24 24" aria-hidden="true">' + paths + '</svg>';
    }
    button.disabled = busy || status.phase === 'ready';
    text.textContent = status.error || (status.phase === 'downloading' ? `${Math.floor(done / total * 100)}% · ${(done / 1e6).toFixed(2)} / ${(total / 1e6).toFixed(2)} MB` : status.phase === 'ready' ? '可打开' : `${(total / 1e6).toFixed(2)} MB`);
    if (host.classList.contains('round-download')) {
      host.title = button.title; text.textContent = status.phase === 'downloading' ? (done >= total ? '校验' : Math.floor(done / total * 100) + '%') : '';
    }
    bar.hidden = status.phase !== 'downloading'; bar.max = total; bar.value = done;
  }
  for (const link of document.querySelectorAll('#home a[data-database]')) {
    if (link.hash === '#ascendc-map') continue;
    const params = new URLSearchParams(link.hash.slice(1)), backend = downloadBackend(params.get('backend') || 'ccec');
    link.setAttribute('aria-disabled', String(siteLoader.status(backend).phase !== 'ready'));
  }
  const top = document.querySelector('#database-download');
  top.hidden = !pendingNavigation;
  if (pendingNavigation) {
    const {backend} = pendingNavigation, status = siteLoader.status(backend);
    top.dataset.downloadBackend = backend;
    document.querySelector('#site-loading-title').textContent = status.phase === 'downloading' ? '正在准备数据库' : '下载数据库后打开';
    document.querySelector('#site-loading-message').textContent = status.error || (status.phase === 'update' ? '本地数据库有新版本，请先更新。' : '下载并校验完成后才能进入；相同内容会复用本地缓存。');
    document.querySelector('#site-loading').setAttribute('aria-busy',String(status.phase === 'downloading'));
    const retry = document.querySelector('#site-retry'); retry.hidden = false;
    retry.textContent = status.phase === 'update' ? '更新并打开' : status.phase === 'error' ? '重试' : status.phase === 'ready' ? '打开' : '下载并打开';
    retry.disabled = ['checking','downloading'].includes(status.phase);
    retry.onclick = () => downloadDatabase(backend,true);
  }
}
function downloadControl(backend) {
  const host = document.createElement('div'); host.className = 'database-download'; host.dataset.downloadBackend = backend;
  host.innerHTML = '<button type="button">检查缓存…</button><span></span><progress hidden aria-label="数据库下载进度"></progress>';
  host.querySelector('button').onclick = () => downloadDatabase(host.dataset.downloadBackend,host.id === 'database-download');
  return host;
}
if (siteLoader) {
  for (const link of document.querySelectorAll('#home a[data-database]')) {
    const params = new URLSearchParams(link.hash.slice(1));
    const wrap = document.createElement('div'); wrap.className = 'library-entry';
    link.before(wrap); wrap.append(link);
    const control = downloadControl(downloadBackend(params.get('backend') || 'ccec'));
    control.classList.add('round-download'); wrap.append(control);
  }
  const top = downloadControl('llvm'); top.id = 'database-download'; top.hidden = true;
  document.querySelector('.backend-switch').after(top);
  document.querySelector('#home').addEventListener('click', event => {
    const link = event.target.closest('a[aria-disabled="true"]');
    if (link) {event.preventDefault(); const params = new URLSearchParams(link.hash.slice(1)); const backend = downloadBackend(params.get('backend') || 'ccec'); document.querySelector(`#home [data-download-backend="${backend}"] button`)?.focus();}
  });
  siteLoader.subscribe(renderDownloads);
  siteLoader.initialized.then(() => {
    renderDownloads();
    const url = new URL(location.href), backend = url.searchParams.get('download');
    if (['llvm','ccec','ascendc','cce-dialect','ptx','nvvm'].includes(backend)) {
      url.searchParams.delete('download'); history.replaceState(null,'',url); downloadDatabase(backend,true);
    }
  });
}
