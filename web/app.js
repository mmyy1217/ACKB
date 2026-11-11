'use strict';
const $ = selector => document.querySelector(selector);
const data = JSON.parse($('#catalog-data').textContent);
const records = data.records;
const byId = new Map(records.map(r => [r.id, r]));
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = value => value.toLocaleString('en-US');
const isInterface = r => r.kind === 'interface' || r.kind === 'interface_macro';
const kinds = {interface:'函数接口',interface_macro:'宏接口',type:'类型定义',macro:'宏定义',constant:'常量 / 变量',helper:'辅助函数'};
const shortGroup = {'AI Core':'AI Core','Vector / AVE':'AVE','Legacy SIMD':'Legacy','SIMT':'SIMT','配套定义':'辅助'};
const families = ['搬运 / DMA','矩阵 / Cube','访存 / 布局','计算 / 其他','类型转换','同步 / 流水','原子操作','控制 / 寄存器'];
const BATCH_SIZE = 60;
const state = {view:'interfaces',family:'',query:'',group:'',file:'',limit:BATCH_SIZE,selected:'',tab:'definition'};
const mobile = window.matchMedia('(max-width:800px)');
let visible = [], timer, readingDetail = false, loadScheduled = false;
const sourceLabel = s => `${s.file}:${s.line}${s.end_line > s.line ? '–' + s.end_line : ''}`;
const searchTexts = new Map(records.map(r => [r.id,[r.name,r.signature,r.group,r.family,r.namespace,...r.builtins,...r.conditions,r.source.file].join(' ').toLowerCase()]));
const fileMap = new Map(data.files.map(f => [f.path,f]));

function saveHash(replace = true) {
  const p = new URLSearchParams();
  if (state.view !== 'interfaces') p.set('view',state.view);
  for (const key of ['family','query','group','file','selected']) if (state[key]) p.set(key === 'selected' ? 'r' : key,state[key]);
  const target = '#' + p.toString();
  if (location.hash !== target) history[replace ? 'replaceState' : 'pushState'](null,'',target);
}
function readHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  state.view = ['interfaces','definitions','report'].includes(p.get('view')) ? p.get('view') : 'interfaces';
  for (const key of ['family','query','group','file']) state[key] = p.get(key) || '';
  state.selected = p.get('r') || '';
  if (!p.has('view') && byId.has(state.selected) && !isInterface(byId.get(state.selected))) state.view = 'definitions';
  state.limit = BATCH_SIZE;
}
function toast(message) {
  $('#announcement').textContent = message;
  clearTimeout(timer);
  timer = setTimeout(() => {$('#announcement').textContent = '';},2500);
}
async function copyText(value) {
  try { await navigator.clipboard.writeText(value); }
  catch {
    const t = document.createElement('textarea');
    t.value = value; t.style.position = 'fixed'; t.style.top = '-2000px'; document.body.append(t);t.select();
    const ok = document.execCommand('copy'); t.remove();
    if (!ok) {toast('复制未成功，请选中代码后手动复制。');return;}
  }
  toast('已复制');
}
function download() {
  const blob = new Blob([JSON.stringify(data,null,2)],{type:'application/json;charset=utf-8'});
  const url = URL.createObjectURL(blob), a = document.createElement('a');
  a.href = url; a.download = `cce-ops-${data.version}.json`;a.click();setTimeout(() => URL.revokeObjectURL(url),1000);
}
function baseRecords() { return records.filter(r => state.view === 'definitions' ? !isInterface(r) : isInterface(r)); }
function makeGroups(items) {
  const groups = new Map();
  for (const r of items) {
    const key = [r.group,r.namespace || '',r.name,r.kind].join('|');
    if (!groups.has(key)) groups.set(key,{key,name:r.name,group:r.group,family:r.family,items:[]});
    groups.get(key).items.push(r);
  }
  return [...groups.values()];
}
function filtered() {
  const terms = state.query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  return baseRecords().filter(r => (!state.family || r.family === state.family) && (!state.group || r.group === state.group) && (!state.file || r.source.file === state.file) && terms.every(t => searchTexts.get(r.id).includes(t)));
}
function syncControls() {
  $('#search').value = state.query;$('#group').value = state.group;$('#file').value = state.file;
  $('#mobile-view').value = state.view;$('#mobile-family').value = state.family;
  document.querySelectorAll('[data-view]').forEach(b => {b.classList.toggle('active',b.dataset.view === state.view); if (b.dataset.view === state.view) b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
  document.querySelectorAll('[data-family]').forEach(b => {b.classList.toggle('active',b.dataset.family === state.family);b.setAttribute('aria-pressed',String(b.dataset.family === state.family));});
}
function render(revealSelection = false) {
  readingDetail = false;
  window.scrollTo(0,0);
  const report = state.view === 'report';
  $('#catalog-view').hidden = report;$('#report').hidden = !report;
  $('#family-section').hidden = state.view !== 'interfaces';$('#mobile-family-label').hidden = state.view !== 'interfaces';
  $('#page-title').textContent = {interfaces:'指令接口',definitions:'配套定义',report:'扫描报告'}[state.view];
  $('.toolbar').hidden = report;
  $('#classification-heading').textContent = state.view === 'definitions' ? '定义类型' : '指令族';
  syncControls();
  if (report) {renderReport();saveHash();return;}
  const matches = filtered();
  visible = makeGroups(matches);
  const query = state.query.trim().toLowerCase();
  if (query) {
    const score = g => g.name.toLowerCase() === query ? 0 : g.name.toLowerCase().startsWith(query) ? 1 : g.name.toLowerCase().includes(query) ? 2 : 3;
    visible.sort((a,b) => score(a) - score(b) || a.name.localeCompare(b.name));
  }
  $('#result-count').textContent = `${fmt(visible.length)} 个名称 · ${fmt(matches.length)} 条记录`;
  $('#empty').hidden = visible.length !== 0;
  if (!matches.some(r => r.id === state.selected)) {
    state.selected = matches[0]?.id || '';
    state.tab = 'definition';
  }
  const selectedGroup = visible.findIndex(g => g.items.some(r => r.id === state.selected));
  state.limit = Math.min(visible.length,Math.max(BATCH_SIZE,Math.ceil((selectedGroup + 1) / BATCH_SIZE) * BATCH_SIZE));
  renderRows();renderDetail();saveHash();
  if (revealSelection) requestAnimationFrame(() => {
    const button = $(`#rows [data-id="${visible[selectedGroup]?.items[0].id}"]`);
    button?.scrollIntoView({block:'center'});
  });
  queueMore();
}
function rowHTML(groups) {
  return groups.map(g => {
    const selected = g.items.some(r => r.id === state.selected);
    const classification = state.view === 'definitions' ? kinds[g.items[0].kind] : g.family;
    const qualified = [g.items[0].namespace,g.name].filter(Boolean).join('::');
    return `<tr class="${selected ? 'selected' : ''}"><td><button class="row-button" title="${esc(qualified)}" data-id="${g.items[0].id}" ${selected ? 'aria-current="true"' : ''}><span class="row-name">${esc(g.name)}</span></button></td><td>${esc(classification)}</td><td>${esc(shortGroup[g.group])}</td><td class="number">${g.items.length}</td></tr>`;
  }).join('');
}
function updateLoadStatus() {
  $('#load-status').hidden = visible.length === 0;
  $('#load-status').textContent = state.limit < visible.length ? `已显示 ${fmt(state.limit)} / ${fmt(visible.length)} 个名称 · 向下滚动继续加载` : `已显示全部 ${fmt(visible.length)} 个名称`;
}
function renderRows() {
  $('#rows').innerHTML = rowHTML(visible.slice(0,state.limit));
  updateLoadStatus();
}
function markSelectedRow() {
  const group = visible.find(g => g.items.some(r => r.id === state.selected));
  $('#rows').querySelectorAll('.row-button').forEach(button => {
    const selected = button.dataset.id === group?.items[0].id;
    button.closest('tr').classList.toggle('selected',selected);
    if (selected) button.setAttribute('aria-current','true');else button.removeAttribute('aria-current');
  });
}
function queueMore() {
  if (loadScheduled) return;
  loadScheduled = true;
  requestAnimationFrame(() => {
    loadScheduled = false;
    if (state.view === 'report' || readingDetail || state.limit >= visible.length) return;
    const bounds = $('#load-status').getBoundingClientRect();
    if (bounds.top > innerHeight + 300 || bounds.bottom < 0) return;
    const start = state.limit;
    state.limit = Math.min(state.limit + BATCH_SIZE,visible.length);
    $('#rows').insertAdjacentHTML('beforeend',rowHTML(visible.slice(start,state.limit)));
    updateLoadStatus();
    queueMore();
  });
}
function formatSignature(r) {
  if (r.kind !== 'interface') return r.signature;
  const prefix = r.template ? r.template + '\n' : '';
  return `${prefix}${r.return_type} ${r.name}(${r.parameters.length ? '\n  ' + r.parameters.join(',\n  ') + '\n' : ''});`;
}
function visibleConditions(r) {
  return r.conditions.filter(c => !/^!defined\(__CLANG_|^!defined\(__CCE_INTRINSICS_H|^!defined\(CCE_AICORE_INTRINSICS/.test(c));
}
function renderDetail() {
  const r = byId.get(state.selected), pane = $('#detail');
  if (!r) {pane.innerHTML = '<div class="empty detail-empty"><h2>选择条目，阅读详情</h2><p>调整左侧筛选后即可查看接口与来源。</p></div>';return;}
  const current = visible.find(g => g.items.some(x => x.id === r.id));
  const options = current?.items || [r];
  const countLabel = isInterface(r) ? `${options.length} 条重载 / 声明` : `${options.length} 条定义`;
  pane.innerHTML = `<div class="detail-heading"><h2>${esc(r.name)}</h2><div class="detail-domain"><span>${esc(r.group)}</span><span>${esc(r.family === '配套定义' ? kinds[r.kind] : r.family)}</span></div>${r.namespace ? `<div class="qualified">${esc(r.namespace)}::${esc(r.name)}</div>` : ''}<div class="detail-actions"><button id="back-to-list" class="mobile-return text-button">返回列表</button><button id="copy-signature" class="quiet-button">复制签名</button><button id="copy-link" class="quiet-button">复制链接</button><span class="detail-status">头文件声明</span></div></div><div class="detail-tabs" role="tablist" aria-label="详情内容">${[['definition','接口定义'],['source','来源证据'],['experiments','实验记录']].map(([id,title]) => `<button id="tab-${id}" role="tab" data-tab="${id}" aria-controls="detail-content" tabindex="${state.tab === id ? 0 : -1}" aria-selected="${state.tab === id}">${title}</button>`).join('')}</div><div class="detail-body" id="detail-content" role="tabpanel" aria-labelledby="tab-${state.tab}"><label class="overloads">${esc(countLabel)}<select id="overload" aria-label="选择重载或声明">${options.map((x,i) => `<option value="${x.id}" ${x.id === r.id ? 'selected' : ''}>${i + 1}. ${esc(x.return_type || kinds[x.kind])} · ${esc(x.parameters?.join(', ') || x.source.file)}</option>`).join('')}</select></label>${state.tab === 'source' ? sourceContent(r) : state.tab === 'experiments' ? experimentsContent() : definitionContent(r)}</div>`;
  $('#back-to-list').onclick = () => {
    readingDetail = false;
    const button = $('#rows [aria-current="true"]');
    button?.scrollIntoView({block:'center'});button?.focus({preventScroll:true});queueMore();
  };
  $('#copy-signature').onclick = () => copyText(formatSignature(r));
  $('#copy-link').onclick = () => copyText(location.href);
  $('#overload').onchange = e => {state.selected = e.target.value;saveHash();renderDetail();$('#overload').focus({preventScroll:true});};
  pane.querySelectorAll('[data-tab]').forEach(b => b.onclick = () => {state.tab = b.dataset.tab;renderDetail();$('#tab-' + state.tab).focus();});
  pane.querySelectorAll('[data-ref]').forEach(b => b.onclick = () => {
    const target = byId.get(b.dataset.ref);
    Object.assign(state,{view:isInterface(target) ? 'interfaces' : 'definitions',selected:target.id,query:'',family:'',group:'',file:'',tab:'definition'});
    render(!mobile.matches);
    if (mobile.matches) {readingDetail=true;$('#detail').scrollIntoView({block:'start'});}
    $('#detail').focus({preventScroll:true});
  });
  pane.querySelector('[role="tablist"]').onkeydown = e => {
    if (!['ArrowLeft','ArrowRight','Home','End'].includes(e.key)) return;
    e.preventDefault();const tabs = ['definition','source','experiments'];let index = tabs.indexOf(state.tab);
    index = e.key === 'Home' ? 0 : e.key === 'End' ? 2 : (index + (e.key === 'ArrowRight' ? 1 : 2)) % 3;
    state.tab = tabs[index];renderDetail();$('#tab-' + state.tab).focus();
  };
}
function definitionContent(r) {
  const conds = visibleConditions(r);
  const calls = (r.calls || []).map(name => records.find(x => x.name === name && x.namespace?.endsWith('__cce_scalar'))).filter(Boolean);
  const types = [...new Set((r.parameters || []).join(' ').match(/[A-Za-z_]\w*/g) || [])].map(name => records.find(x => x.kind === 'type' && x.name === name)).filter(Boolean).slice(0,12);
  const links = (items) => items.map(x => `<button class="related-link" data-ref="${x.id}"><code>${esc(x.namespace ? x.namespace + '::' + x.name : x.name)}</code></button>`).join('');
  return `<h3>${r.kind === 'interface' ? '接口签名' : '声明内容'}</h3><pre class="signature"><code>${esc(formatSignature(r))}</code></pre><dl class="detail-meta"><dt>接口形式</dt><dd>${esc(kinds[r.kind])}${r.generated ? ' · 宏展开生成' : ''}</dd><dt>来源位置</dt><dd class="source-ref">${esc(sourceLabel(r.source))}</dd>${r.return_type ? `<dt>返回类型</dt><dd><code>${esc(r.return_type)}</code></dd>` : ''}</dl>${r.parameters?.length ? `<h3>参数声明</h3><table class="parameter-table"><thead><tr><th>序号</th><th>类型 / 名称 / 默认值</th></tr></thead><tbody>${r.parameters.map((p,i) => `<tr><td>${i + 1}</td><td><code>${esc(p)}</code></td></tr>`).join('')}</tbody></table>` : ''}<h3>可见条件</h3>${conds.length ? conds.map(c => `<div class="condition">${esc(c)}</div>`).join('') : '<p>声明处未发现额外条件。调用入口仍可能附加条件，不能据此推断全架构支持。</p>'}${types.length ? '<h3>相关类型</h3>' + links(types) : ''}${calls.length ? '<h3>下层接口调用</h3>' + links(calls) : ''}<h3>关联 builtin</h3>${r.builtins.length ? r.builtins.map(b => `<div class="condition">${esc(b)}</div>`).join('') : '<p>本条声明未提取到直接 builtin 引用。</p>'}<div class="callout">${r.parameters?.includes('...') ? '原始头文件以可变参数声明此接口，精确参数约束尚待核对。' : '参数单位、合法值和设备支持范围尚未逐项验证。'} 指令族按名称规则归类，仅用于导航。</div>`;
}
function sourceContent(r) {
  const file = fileMap.get(r.source.file);
  const macroSources = r.macro_sources.map(s => {
    const macro = records.find(m => m.kind === 'macro' && m.source.file === s.file && m.source.line === s.line);
    return `<h3>生成宏 · ${esc(sourceLabel(s))}</h3>${macro ? `<pre><code>${esc(macro.excerpt)}</code></pre>` : '<p>生成宏位置已记录。</p>'}`;
  }).join('');
  return `<h3>原始来源</h3><p class="source-ref">${esc(sourceLabel(r.source))}</p><pre><code>${esc(r.excerpt)}</code></pre>${macroSources}<h3>完整声明与函数体</h3><pre><code>${esc(r.definition || r.signature)}</code></pre><h3>全部条件（含头文件保护）</h3>${r.conditions.map(c => `<div class="condition">${esc(c)}</div>`).join('') || '<p>无条件记录。</p>'}<h3>来源标识</h3><dl class="detail-meta"><dt>CANN</dt><dd><code>${esc(data.version)}</code></dd><dt>文件 SHA-256</dt><dd><code>${esc(file.sha256)}</code></dd><dt>记录 ID</dt><dd><code>${r.id}</code></dd></dl><div class="callout">${data.source.package_verified ? '已与原始 .run 包中的扫描头文件逐一核对 SHA-256。' : '来源为已安装工具链；原始 .run 包尚未核对。'}宏展开由静态提取器完成，保留符号条件，不代表编译器接受此调用。</div>`;
}
function experimentsContent() {
  return `<h3>尚未开展设备实验</h3><p>当前依据来自头文件静态提取。本条接口尚无编译、运行正确性或性能记录。</p><dl class="detail-meta"><dt>静态声明</dt><dd>已提取，来源可追溯</dd><dt>编译验证</dt><dd>未执行</dd><dt>运行验证</dt><dd>未执行</dd><dt>性能测量</dt><dd>未执行</dd></dl><div class="callout">后续实验将附目标设备、完整工具链版本、样例、执行命令与原始结果。</div>`;
}
function renderReport() {
  const unresolved = data.report.unresolved;
  const verified = data.source.package_verified;
  const packageNote = verified ? '原包内 ' + data.files.length + ' 个扫描头文件与数据源完全一致' : '原始安装包未核对';
  const packageProof = verified ? `<h2>安装包校验</h2><p>直接读取原包及内层编译器归档，未执行安装脚本。校验范围为本次扫描的 ${data.files.length} 个头文件，不代表完整工具链或设备行为验证。</p><dl class="detail-meta"><dt>原包</dt><dd><code>${esc(data.source.package_name)}</code></dd><dt>SHA-256</dt><dd><code>${esc(data.source.package_sha256)}</code></dd><dt>编译器包</dt><dd><code>${esc(data.source.package_verification.compiler_package)}</code></dd><dt>SHA-256</dt><dd><code>${esc(data.source.package_verification.compiler_sha256)}</code></dd></dl>` : '';
  $('#report').innerHTML = `<div class="report-intro"><span><strong>${data.files.length}</strong>扫描文件</span><span><strong>${fmt(records.filter(isInterface).length)}</strong>接口声明记录</span><span><strong>${unresolved.length}</strong>待处理项</span><span><strong>0</strong>设备实验</span></div><div class="callout">已安装工具链 ${esc(data.version)} · ${packageNote}。当前为静态接口索引，不宣称硬件指令全集或设备支持。记录数包含重载、条件分支和重复声明。</div>${packageProof}<h2>扫描文件与来源校验</h2><div class="report-table-wrap"><table class="report-table"><thead><tr><th>文件</th><th>大小</th><th>SHA-256</th></tr></thead><tbody>${data.files.map(f => `<tr><td><code>${esc(f.path)}</code></td><td>${fmt(f.bytes)} B</td><td class="hash"><code>${f.sha256}</code></td></tr>`).join('')}</tbody></table></div><h2>待处理项 · ${unresolved.length}</h2><p>以下结构未被提取器可靠识别，保留位置和原文；不计为成功解析接口。</p>${unresolved.map(e => `<details><summary><code>${esc(e.file)}:${e.line}</code> · ${esc(e.reason)}</summary><pre>${esc(e.text)}</pre></details>`).join('') || '<p>本轮未报告未解析结构；这不等于完成硬件支持验证。</p>'}<h2>范围边界</h2><ul><li>条件表达式原样保存，未求值为设备支持矩阵。</li><li>函数宏支持参数替换、可变参数和 token paste；对象宏保持符号形式。</li><li>包含关系已盘点，外部标准库与运行时依赖未递归提取。</li><li>函数体内的条件分支仅保存文本，不代表实际执行路径。</li><li>${verified ? "原包与已扫描头文件一致性已核验；未校验整个 Toolkit 的所有文件。" : "原始 .run 包与安装目录一致性尚未核验。"}</li><li>编译、运行和性能验证尚未开展。</li></ul><h2>排除文件</h2>${data.report.excluded_files.map(f => `<p><code>${esc(f.path)}</code> · AI CPU NEON，位于 AI Core 范围之外。</p>`).join('')}${(data.report.excluded_records || []).map(r => `<p><code>${esc(r.name)}</code> · ${esc(sourceLabel(r.source))} · PTO 专用封装，排除出指令接口范围。</p>`).join('')}<h2>包含关系</h2><div class="report-table-wrap"><table class="report-table"><thead><tr><th>来源</th><th>包含文件</th><th>条件</th></tr></thead><tbody>${data.report.includes.map(i => `<tr><td><code>${esc(i.file)}:${i.line}</code></td><td><code>${esc(i.name)}</code></td><td><code>${esc(i.conditions.join(' && '))}</code></td></tr>`).join('')}</tbody></table></div><h2>尚未关联到接口的 builtin 名称</h2><p>原始文本发现 ${fmt(data.report.raw_builtin_names.length)} 个名称，其中 ${fmt(data.report.unlinked_builtin_names.length)} 个未直接关联到接口。包含宏拼接前缀及辅助函数引用，不能作为额外指令数量。</p><details><summary>展开名称列表</summary><pre>${esc(data.report.unlinked_builtin_names.join('\n'))}</pre></details>`;
}
function initPanelResize() {
  const root = document.documentElement, storageKey = 'cce-ops.panel-widths.v1';
  const preferences = {sidebar:null,detail:null};
  try {
    const saved = JSON.parse(localStorage.getItem(storageKey));
    for (const kind of Object.keys(preferences)) if (Number.isFinite(saved?.[kind])) preferences[kind] = saved[kind];
  } catch { /* Storage may be unavailable for local files. */ }
  const clamp = (value,min,max) => Math.round(Math.max(min,Math.min(max,value)));
  const save = () => {try {localStorage.setItem(storageKey,JSON.stringify(preferences));} catch { /* Keep resizing available without storage. */ }};
  function limits(kind) {
    const width = $('.workspace').getBoundingClientRect().width;
    const sidebar = parseFloat(root.style.getPropertyValue('--sidebar-width')) || 136;
    const detail = parseFloat(root.style.getPropertyValue('--detail-width')) || 330;
    return kind === 'sidebar' ? [128,Math.min(360,width - 26 - detail - 300)] : [260,Math.min(720,width - 26 - sidebar - 300)];
  }
  function apply() {
    if (mobile.matches) return;
    readingDetail = false;
    const width = $('.workspace').getBoundingClientRect().width;
    const sidebar = clamp(preferences.sidebar ?? 136,128,Math.min(360,width - 26 - 260 - 300));
    const detail = clamp(preferences.detail ?? (innerWidth <= 1220 ? 300 : 330),260,Math.min(720,width - 26 - sidebar - 300));
    root.style.setProperty('--sidebar-width',sidebar + 'px');
    root.style.setProperty('--detail-width',detail + 'px');
    for (const [kind,value] of [['sidebar',sidebar],['detail',detail]]) {
      const handle = $('#resize-' + kind), [min,max] = limits(kind);
      handle.setAttribute('aria-valuemin',min);
      handle.setAttribute('aria-valuemax',Math.floor(max));
      handle.setAttribute('aria-valuenow',value);
      handle.setAttribute('aria-valuetext',value + ' 像素');
    }
  }
  for (const kind of Object.keys(preferences)) {
    const handle = $('#resize-' + kind), direction = kind === 'sidebar' ? 1 : -1;
    let drag = null;
    const reset = () => {preferences[kind] = null;apply();save();};
    const change = value => {preferences[kind] = clamp(value,...limits(kind));apply();};
    const finish = () => {drag = null;handle.classList.remove('dragging');document.body.classList.remove('resizing');save();};
    handle.onpointerdown = event => {
      if (event.button !== 0 || mobile.matches) return;
      event.preventDefault();handle.focus({preventScroll:true});
      drag = {x:event.clientX,width:Number(handle.getAttribute('aria-valuenow'))};
      handle.setPointerCapture(event.pointerId);
      handle.classList.add('dragging');document.body.classList.add('resizing');
    };
    handle.onpointermove = event => {if (drag) change(drag.width + direction * (event.clientX - drag.x));};
    handle.onpointerup = handle.onpointercancel = handle.onlostpointercapture = finish;
    handle.ondblclick = reset;
    handle.onkeydown = event => {
      if (event.key === 'Enter') {event.preventDefault();reset();return;}
      if (!['ArrowLeft','ArrowRight','Home','End'].includes(event.key)) return;
      event.preventDefault();const [min,max] = limits(kind), current = Number(handle.getAttribute('aria-valuenow'));
      change(event.key === 'Home' ? min : event.key === 'End' ? max : current + (event.key === 'ArrowRight' ? 1 : -1) * direction * (event.shiftKey ? 40 : 10));
      save();
    };
  }
  new ResizeObserver(() => root.style.setProperty('--header-height',$('.topbar').getBoundingClientRect().height + 'px')).observe($('.topbar'));
  window.addEventListener('resize',() => {apply();queueMore();});
  apply();
}
function reset() {Object.assign(state,{family:'',query:'',group:'',file:'',selected:'',tab:'definition'});render();}
function switchView(view) {Object.assign(state,{view,family:'',query:'',group:'',file:'',selected:'',tab:'definition'});render();}

$('#version').textContent = data.version;
$('#footer-source').textContent = `${data.files.length} 个源文件 · CANN ${data.version}`;
$('#nav-interfaces').textContent = fmt(makeGroups(records.filter(isInterface)).length);
$('#nav-definitions').textContent = fmt(makeGroups(records.filter(r => !isInterface(r))).length);
$('#families').innerHTML = [['','全部指令'],...families.map(f => [f,f])].map(([value,label]) => `<button class="family" data-family="${esc(value)}">${label}<span>${fmt(makeGroups(records.filter(r => isInterface(r) && (!value || r.family === value))).length)}</span></button>`).join('');
$('#mobile-family').innerHTML = '<option value="">全部指令</option>' + families.map(f => `<option>${esc(f)}</option>`).join('');
$('#group').innerHTML += [...new Set(records.map(r => r.group))].sort().map(g => `<option>${esc(g)}</option>`).join('');
$('#file').innerHTML += data.files.map(f => `<option>${esc(f.path)}</option>`).join('');
$('#download').onclick = download;
$('#search').addEventListener('input',e => {state.query=e.target.value;state.selected='';render();});
for (const key of ['group','file']) $('#' + key).onchange = e => {state[key]=e.target.value;state.selected='';render();};
$('#reset').onclick = reset;$('#empty-reset').onclick = reset;
$('#mobile-view').onchange = e => switchView(e.target.value);
$('#mobile-family').onchange = e => {state.family=e.target.value;state.selected='';render();};
document.querySelectorAll('[data-view]').forEach(b => b.onclick = () => switchView(b.dataset.view));
document.querySelectorAll('[data-family]').forEach(b => b.onclick = () => {state.family=b.dataset.family;state.selected='';render();});
$('#rows').addEventListener('click',e => {
  const button = e.target.closest('[data-id]');if (!button) return;
  state.selected=button.dataset.id;state.tab='definition';saveHash(false);markSelectedRow();renderDetail();
  $('#detail').scrollTop=0;
  if (mobile.matches) {readingDetail=true;$('#detail').scrollIntoView({block:'start'});$('#detail').focus({preventScroll:true});}
  else $('#detail').focus({preventScroll:true});
});
document.addEventListener('keydown',e => {
  if (e.key === '/' && !['INPUT','SELECT','TEXTAREA'].includes(document.activeElement.tagName) && state.view !== 'report') {e.preventDefault();$('#search').focus();}
  if (e.key === 'Escape' && document.activeElement === $('#search')) {reset();$('#search').focus();}
});
window.addEventListener('hashchange',() => {readHash();render(true);});
window.addEventListener('scroll',queueMore,{passive:true});
if ('IntersectionObserver' in window) new IntersectionObserver(queueMore,{rootMargin:'300px 0px'}).observe($('#load-status'));
initPanelResize();
readHash();render(Boolean(new URLSearchParams(location.hash.slice(1)).get('r')));
