'use strict';

let ascendcData = knowledgeData.ascendc || {basic_api: [], c_api: [], counts: {}, files: {}, limitations: []};
let dialectData = knowledgeData.cce_dialect || {ops: [], intrinsics: [], counts: {}, source: {files: {}}, limitations: []};

function createAscendcRecords() {
  const mapItem = (item, layer) => ({
    id: item.id,
    backend: 'ascendc',
    ascendcLayer: layer,
    ascendc: item,
    kind: 'ascendc_' + layer,
    name: item.name,
    namespace: item.namespace || '',
    group: item.group,
    family: item.family,
    transfer: item.transfer || null,
    signature: item.forms?.[0]?.signature || item.name,
    parameters: item.forms?.[0]?.parameters || [],
    builtins: item.ccec_candidate_op_ids || [],
    conditions: [item.condition_3510],
    source: item.source,
    files: [item.source.file, ...(item.impl_source ? [item.impl_source.file] : [])],
    compatibility: {profiles: {[A5_PROFILE]: item.condition_3510}},
    deprecation: {status: item.deprecated ? 'marked' : 'unmarked'},
  });
  return [
    ...(ascendcData.basic_api || []).map(x => mapItem(x, 'basic')),
    ...(ascendcData.c_api || []).map(x => mapItem(x, 'capi')),
  ];
}

function createDialectRecords() {
  const ops = (dialectData.ops || []).map(o => ({
    id: o.id,
    backend: 'cce-dialect',
    dialectLayer: 'ops',
    dialectOp: o,
    kind: 'dialect_op',
    name: o.name,
    namespace: '',
    group: o.group,
    family: o.family,
    transfer: o.transfer || null,
    signature: `${o.name} ${o.assembly_format || ''}`.trim(),
    parameters: o.arguments ? [o.arguments] : [],
    builtins: [...(o.intrinsic_ids || []), ...(o.ccec_candidate_op_ids || [])],
    conditions: [o.lowering_mode],
    source: o.source,
    files: [o.source.file, ...(o.spec?.source ? [o.spec.source.file] : [])],
    compatibility: {profiles: {[A5_PROFILE]: 'unknown'}},
    deprecation: {status: 'unmarked'},
  }));
  const intrs = (dialectData.intrinsics || []).map(i => ({
    id: i.id,
    backend: 'cce-dialect',
    dialectLayer: 'intrinsics',
    dialectIntr: i,
    kind: 'dialect_intr',
    name: i.name,
    namespace: '',
    group: i.group,
    family: i.family,
    transfer: i.transfer || null,
    signature: i.mlir_intr_ops?.[0]?.mnemonic ? `${i.mlir_intr_ops[0].mnemonic} → ${i.llvm_intrinsic}` : i.llvm_intrinsic,
    parameters: [],
    builtins: [...(i.upstream_op_ids || []), ...(i.ccec_candidate_op_ids || [])],
    conditions: i.mapping_classes || [],
    source: i.source,
    files: [...new Set([...i.mappings, ...i.mlir_intr_ops].map(m => m.source.file))],
    compatibility: {profiles: {[A5_PROFILE]: 'unknown'}},
    deprecation: {status: 'unmarked'},
  }));
  return [...ops, ...intrs];
}

let ascendcRecords = createAscendcRecords();
let dialectRecords = createDialectRecords();

const loweringModeLabels = {
  direct_to_llvm_ir: 'cce-translate 直接翻译',
  lowers_to_cce_intr: '降级为 cce.intr.*',
  simt_translation: 'SIMT 翻译管线',
  scope_or_region: 'Region 作用域',
};

const callKindLabels = {
  direct_ccec_intrinsic: '候选 alias 入口',
  via_ccec_wrapper: '候选封装入口',
  both_intrinsic_and_wrapper: '同名有 alias 与封装，未消歧',
  unresolved: '待确认',
};

function renderAscendcCallTrace(item) {
  const trace=item.call_trace;
  if (!trace?.edges?.length && !trace?.unresolved?.length) return '';
  const nodes=trace.nodes || {}, groups=new Map();
  for (const edge of trace.edges) {
    const key=JSON.stringify([edge.caller,edge.call.source,edge.call.name,edge.call.arguments]);
    if (!groups.has(key)) groups.set(key,{edge,targets:[]});
    if (edge.callee) groups.get(key).targets.push(nodes[edge.callee]);
  }
  const origin=source=>`<p class="source-ref">${esc(sourceLabel(source))}</p><p class="condition">SHA-256 ${esc(ascendcData.files[source.file]?.sha256 || '未记录')}</p>`;
  return `<details class="call-trace"><summary>逐调用来源 · ${groups.size} 处 · ${trace.unresolved.length} 处待解析</summary><p>公共转发头 → dav_3510 候选实现 → CCEC 符号。按参数数量及显式地址空间排除矛盾候选，保留未排除的模板与重载；最多追踪 ${trace.max_depth} 层 helper，未验证 include 可达性或编译结果。</p>${[...groups.values()].map(({edge,targets})=>`<details><summary><code>${esc(nodes[edge.caller].name)} → ${esc(edge.call.name)}</code>${targets.length?' · '+targets.length+' 个候选实现':''}</summary>${origin(edge.call.source)}<pre><code>${esc(edge.call.name+'('+(edge.call.arguments || []).join(', ')+')')}</code></pre><p>调用位置条件</p><pre><code>${esc((edge.call.conditions || []).join(' && ') || '无局部条件')}</code></pre><p>所在函数</p><pre><code>${esc(nodes[edge.caller].signature)}</code></pre>${targets.map(target=>`<pre><code>${esc(target.signature)}</code></pre>${origin(target.source)}<pre><code>${esc(target.conditions.join(' && ') || '无局部条件')}</code></pre>`).join('')}</details>`).join('')}${trace.unresolved.length?`<h3>待解析调用</h3>${trace.unresolved.map(edge=>`<p><code>${esc(edge.call.name)}</code> · ${edge.reason==='depth_limit'?'达到追踪深度':'未找到兼容的已解析 helper'}</p>${origin(edge.call.source)}`).join('')}`:''}</details>`;
}

function renderAscendcDetail(r) {
  const pane = $('#detail'), item = r.ascendc;
  const isBasic = r.ascendcLayer === 'basic';
  const condLabels = {matches: '3510 局部源码条件符合', unknown: '3510 源码条件待确认', excluded: '3510 源码条件排除'};
  const forms = item.forms || [];
  if (!forms.some((_, i) => String(i) === state.opForm)) state.opForm = '0';
  const activeForm = forms[Number(state.opForm)] || forms[0] || {signature: item.name, parameters: [], source: item.source};
  const tabs = [['definition', isBasic ? '接口与调用链' : '底层原语与调用链'], ['source', '源码与条件'], ['experiments', '验证状态']];

  const calleesHTML = (item.ccec_callees || []).length
    ? `<table class="parameter-table"><thead><tr><th>候选 CCEC 符号</th><th>候选入口性质</th><th>候选 CCEC builtin</th></tr></thead><tbody>${item.ccec_callees.map(c => {
      const calleeRefId = (c.wrapper_record_ids || []).find(id => Boolean(lookupRecord(id))) || (c.entry_record_ids || []).find(id => Boolean(lookupRecord(id)));
      const calleeCell = calleeRefId ? opLink(calleeRefId, c.name) : `<code>${esc(c.name)}</code>`;
      return `<tr><td>${calleeCell}</td><td>${esc(callKindLabels[c.call_kind] || c.call_kind)}</td><td>${(c.candidate_op_ids || []).map(oid => opLink(oid, oid.replace('ccec_op___builtin_cce_', '__builtin_cce_'))).join(' ') || '—'}</td></tr>`;
    }).join('')}</tbody></table>`
    : '<p>当前扫描未建立 CCEC 候选关联，不代表没有底层调用。</p>';

  const implFuncsHTML = isBasic && (item.impl_3510_functions || []).length
    ? `<details><summary>候选实现函数（名称匹配） · ${item.impl_3510_functions.length}</summary>` + item.impl_3510_functions.map(im => `<details><summary><code>${esc(im.name)}</code> · ${esc(sourceLabel(im.source))}</summary><pre><code>${esc(im.signature)}</code></pre></details>`).join('') + '</details>'
    : '';

  let body = '';
  if (state.tab === 'source') {
    const declSha = ascendcData.files?.[item.source.file]?.sha256 || '';
    const implSha = item.impl_source ? (ascendcData.files?.[item.impl_source.file]?.sha256 || '') : '';
    body = `<h3>声明来源</h3><p class="source-ref">${esc(sourceLabel(item.source))}</p>${declSha ? `<p class="condition">SHA-256 ${esc(declSha)}</p>` : ''}${item.impl_source ? `<h3>候选实现来源</h3><p class="source-ref">${esc(sourceLabel(item.impl_source))}</p>${implSha ? `<p class="condition">SHA-256 ${esc(implSha)}</p>` : ''}` : ''}<h3>源码摘录（候选实现 / 声明）</h3><pre><code>${esc(item.excerpt || activeForm.signature)}</code></pre><div class="callout">静态提取自 CANN ${esc(ascendcData.version)} 头文件，未完成 C++ 重载解析或设备验证。</div>`;
  } else if (state.tab === 'experiments') {
    body = experimentsContent();
  } else {
    body = `<label class="overloads">声明 / 模板形式 · ${forms.length} 种（共 ${item.overload_count} 条）<select id="ascendc-form" aria-label="选择声明形式">${forms.map((f, i) => `<option value="${i}" ${String(i) === state.opForm ? 'selected' : ''}>${i + 1}. ${esc((f.return_type || 'void') + ' ' + item.name + '(' + (f.parameters || []).join(', ') + ')')}</option>`).join('')}</select></label><pre class="signature"><code>${esc(activeForm.signature)}</code></pre><dl class="detail-meta"><dt>所属层级</dt><dd>${isBasic ? 'AscendC 基础 C++ API (basic_api)' : 'AscendC C / SIMT API (c_api / simt_api)'}</dd><dt>950 状态</dt><dd>${esc(condLabels[item.condition_3510] || item.condition_3510)}</dd>${item.core_guards?.length ? `<dt>核保护线索</dt><dd><code>${esc(item.core_guards.join(' / '))}</code></dd>` : ''}<dt>声明位置</dt><dd class="source-ref">${esc(sourceLabel(activeForm.source || item.source))}</dd>${item.impl_source ? `<dt>候选实现位置</dt><dd class="source-ref">${esc(sourceLabel(item.impl_source))}</dd>` : ''}</dl>${activeForm.parameters?.length ? `<h3>参数列表</h3><table class="parameter-table"><thead><tr><th>序号</th><th>类型 / 名称 / 默认值</th></tr></thead><tbody>${activeForm.parameters.map((p, i) => `<tr><td>${i + 1}</td><td><code>${esc(p)}</code></td></tr>`).join('')}</tbody></table>` : ''}<details><summary>当前形式的条件与全部来源</summary>${(activeForm.sources || []).map(src => `<p class="source-ref">${esc(sourceLabel(src.source))} · ${esc(condLabels[src.condition_3510] || src.condition_3510)}</p><pre><code>${esc(src.conditions.join(' && ') || '无局部条件')}</code></pre>${src.ignored_guards?.length ? `<p>已识别的头文件保护宏：<code>${esc(src.ignored_guards.join(', '))}</code></p>` : ''}`).join('')}</details><p class="callout">局部条件符合不等于头文件可达、实现可用或设备支持。其他条件及全部声明形式保留在选择器中。</p>${implFuncsHTML}${renderAscendcCallTrace(item)}<h3>CCEC 候选关联 · ${(item.ccec_callees || []).length}</h3><p>以下关系来自名称与词法引用匹配，尚未解析命名空间、重载和分支，不能视为已证实的调用链。点击可查阅候选 builtin：</p>${calleesHTML}`;
  }

  pane.innerHTML = `<div class="detail-heading"><h2>${esc(item.name)}</h2><div class="detail-domain"><span>${esc(item.group)}</span><span>${esc(item.family)}</span></div>${item.namespace ? `<div class="qualified">${esc(item.namespace)}::${esc(item.name)}</div>` : ''}<div class="detail-actions"><button id="back-to-list" class="mobile-return text-button">返回列表</button><button id="copy-signature" class="quiet-button">复制签名</button><button id="copy-link" class="quiet-button">复制链接</button><span class="detail-status">${isBasic ? 'AscendC 基础 C++ API' : 'AscendC C / SIMT API'}</span></div></div><div class="detail-tabs" role="tablist" aria-label="详情内容">${tabs.map(([id, title]) => `<button id="tab-${id}" role="tab" data-tab="${id}" aria-controls="detail-content" tabindex="${state.tab === id ? 0 : -1}" aria-selected="${state.tab === id}">${title}</button>`).join('')}</div><div class="detail-body" id="detail-content" role="tabpanel" aria-labelledby="tab-${state.tab}">${body}</div>`;

  if ($('#ascendc-form')) {
    $('#ascendc-form').onchange = e => {
      state.opForm = e.target.value;
      renderAscendcDetail(r);
      saveHash();
      $('#ascendc-form').focus({preventScroll: true});
    };
  }
  $('#copy-signature').onclick = () => copyText(activeForm.signature);
  $('#copy-link').onclick = () => copyText(location.href);
  $('#back-to-list').onclick = () => {
    readingDetail = false;
    const button = $('#rows [aria-current="true"]');
    button?.scrollIntoView({block: 'center'});
    button?.focus({preventScroll: true});
    queueMore();
  };
  pane.querySelectorAll('[data-tab]').forEach(b => b.onclick = () => {
    state.tab = b.dataset.tab;
    renderAscendcDetail(r);
    $('#tab-' + state.tab).focus();
  });
  appendLLVMRelations(pane,r.id);
  wireOpLinks(pane);
}

function renderDialectDetail(r) {
  const pane = $('#detail');
  const isOp = r.dialectLayer === 'ops';
  const tabs = [['definition', isOp ? 'Op 规格与映射候选' : 'Intrinsic 映射与来源 Op'], ['source', 'TableGen 源码证据'], ['experiments', '验证状态']];

  if (isOp) {
    const o = r.dialectOp;
    const intrLinks = (o.intrinsic_ids || []).map(id => opLink(id, lookupRecord(id)?.name || id)).join(' ');
    const ccecLinks = (o.ccec_candidate_op_ids || []).map(id => opLink(id, id.replace('ccec_op___builtin_cce_', '__builtin_cce_'))).join(' ');
    let body = '';
    if (state.tab === 'source') {
      body = `<h3>TableGen 定义来源</h3><p class="source-ref">${esc(sourceLabel(o.source))}</p><p class="condition">SHA-256 ${esc(o.source.sha256)}</p><pre><code>${esc(o.excerpt)}</code></pre>${o.spec ? `<h3>CCESpec.md 文档来源</h3><p class="source-ref">${esc(sourceLabel(o.spec.source))} (§ ${o.spec.section_number} ${esc(o.spec.op_def)})</p>` : ''}`;
    } else if (state.tab === 'experiments') {
      body = experimentsContent();
    } else {
      body = `<pre class="signature"><code>${esc(o.name)} ${esc(o.assembly_format || '')}</code></pre><dl class="detail-meta"><dt>TableGen 定义</dt><dd><code>${esc(o.def_name)} : ${esc(o.op_class)}</code></dd><dt>翻译分类（启发式）</dt><dd>${esc(loweringModeLabels[o.lowering_mode] || o.lowering_mode)}</dd><dt>来源位置</dt><dd class="source-ref">${esc(sourceLabel(o.source))}</dd>${o.has_verifier ? '<dt>Verifier</dt><dd>已启用 (hasVerifier = 1)</dd>' : ''}</dl>${o.summary ? `<h3>概述</h3><p>${esc(o.summary)}</p>` : ''}${o.arguments ? `<h3>操作数与属性 (ins)</h3><pre><code>${esc(o.arguments)}</code></pre>` : ''}${o.results ? `<h3>返回值 (outs)</h3><pre><code>${esc(o.results)}</code></pre>` : ''}${o.description ? `<h3>TableGen 说明</h3><pre class="knowledge-prose"><code>${esc(o.description)}</code></pre>` : ''}<h3>关联映射候选 · CCE Dialect LLVM Intrinsics · ${(o.intrinsic_ids || []).length}</h3>${intrLinks ? `<p>${intrLinks}</p>` : '<p>当前未建立静态映射；可能需要动态翻译或其他 Pass，尚待核实。</p>'}${ccecLinks ? `<h3>候选 CCEC Builtins · ${(o.ccec_candidate_op_ids || []).length}</h3><p>${ccecLinks}</p>` : ''}${o.spec ? `<h3>CCESpec.md 中文规格说明 (§ ${o.spec.section_number} · ${esc(o.spec.title_zh)})</h3><pre class="knowledge-prose"><code>${esc(o.spec.body)}</code></pre>` : ''}`;
    }
    pane.innerHTML = `<div class="detail-heading"><h2>${esc(o.name)}</h2><div class="detail-domain"><span>${esc(o.group)}</span><span>${esc(o.family)}</span></div><div class="qualified">${esc(o.def_name)} · ${esc(loweringModeLabels[o.lowering_mode] || o.lowering_mode)}</div><div class="detail-actions"><button id="back-to-list" class="mobile-return text-button">返回列表</button><button id="copy-signature" class="quiet-button">复制语法</button><button id="copy-link" class="quiet-button">复制链接</button><span class="detail-status">CCE Dialect Op</span></div></div><div class="detail-tabs" role="tablist" aria-label="详情内容">${tabs.map(([id, title]) => `<button id="tab-${id}" role="tab" data-tab="${id}" aria-controls="detail-content" tabindex="${state.tab === id ? 0 : -1}" aria-selected="${state.tab === id}">${title}</button>`).join('')}</div><div class="detail-body" id="detail-content" role="tabpanel" aria-labelledby="tab-${state.tab}">${body}</div>`;
    $('#copy-signature').onclick = () => copyText(`${o.name} ${o.assembly_format || ''}`.trim());
  } else {
    const intr = r.dialectIntr;
    const labels = {confirmed:'源码可达',pending:'待核对',rejected:'入口已拒绝'};
    const upLinks = (intr.upstream_op_ids || []).map(id => opLink(id, lookupRecord(id)?.name || id)).join(' ');
    const ccecLinks = (intr.ccec_candidate_op_ids || []).map(id => opLink(id, id.replace('ccec_op___builtin_cce_', '__builtin_cce_'))).join(' ');
    const mlirOpsHTML = (intr.mlir_intr_ops || []).length
      ? `<h3>显式 MLIR Intrinsic Op (CCEIntrinsicOps.td) · ${intr.mlir_intr_ops.length}</h3>` + intr.mlir_intr_ops.map(m => `<div class="rule-entry"><code>${esc(m.mnemonic)} (${esc(m.def_name)})</code><p>${esc(m.summary)}</p>${m.arguments ? `<pre><code>ins: ${esc(m.arguments)}\nouts: ${esc(m.results || 'empty')}</code></pre>` : ''}<p class="condition">${esc(sourceLabel(m.source))}</p></div>`).join('')
      : '';
    const mapRowsHTML = `<table class="parameter-table"><thead><tr><th>定义 / 源码行</th><th>映射类型</th><th>Op 键</th><th>规格参数 (Lanes / Type / Mode)</th></tr></thead><tbody>${(intr.mappings || []).map(m => {
      const spec = [
        m.name_pattern ? m.name_pattern + '（N 取自输入元素位宽）' : '',
        m.restriction ? '上层原子 Op 的类型校验拒绝此形式' : '',
        m.mapping_class === 'CppNameRule' ? '按翻译分支拼名，未编译验证' : '',
        m.lanes ? `lanes=${m.lanes}` : '',
        m.src_lanes ? `src=${m.src_lanes}×${m.src_element_type}→res=${m.res_lanes}×${m.res_element_type}` : '',
        m.element_type ? `dtype=${m.element_type}` : '',
        m.signedness ? `sign=${m.signedness}` : '',
        m.merge_mode ? `mode=${m.merge_mode}` : '',
        m.mask_bitwidth ? `mask=${m.mask_bitwidth}b` : '',
        m.barrier_kind !== undefined ? `barrierKind=${m.barrier_kind}` : '',
        m.operand_count !== undefined ? `in=${m.operand_count}, out=${m.result_count}` : '',
      ].filter(Boolean).join(', ');
      return `<tr><td><code>${esc(m.def_name)}</code></td><td>${esc(m.mapping_class)}</td><td><code>${esc(m.op_key || '')}</code></td><td><code>${esc(spec || 'direct')}</code></td></tr>`;
    }).join('')}</tbody></table>`;

    let body = '';
    if (state.tab === 'source') {
      body = `<h3>lowering 来源</h3><p class="source-ref">${esc(sourceLabel(intr.source))}</p><p class="condition">SHA-256 ${esc(intr.source.sha256)}</p><pre><code>${esc(intr.excerpt)}</code></pre>`;
    } else if (state.tab === 'experiments') {
      body = experimentsContent();
    } else {
      body = `<pre class="signature"><code>${esc(intr.llvm_intrinsic)}</code></pre><dl class="detail-meta"><dt>后端目标符号</dt><dd><code>${esc(intr.llvm_intrinsic)}</code></dd><dt>映射规则类</dt><dd><code>${esc((intr.mapping_classes || []).join(', '))}</code></dd><dt>来源位置</dt><dd class="source-ref">${esc(sourceLabel(intr.source))}</dd></dl>${mlirOpsHTML}<h3>lowering 条目 · ${(intr.mappings || []).length}</h3>${mapRowsHTML}<h3>上游语义 Op (CCE Dialect 语义 Ops) · ${(intr.upstream_op_ids || []).length}</h3>${upLinks ? `<p>以下为按映射键关联的上游候选，点击查看定义与规格：${upLinks}</p>` : '<p>当前未建立上游语义 Op 关联。</p>'}${ccecLinks ? `<h3>候选 CCEC Builtins · ${(intr.ccec_candidate_op_ids || []).length}</h3><p>${ccecLinks}</p>` : ''}`;
    }
    pane.innerHTML = `<div class="detail-heading"><h2>${esc(intr.name)}</h2><div class="detail-domain"><span>${esc(intr.group)}</span><span>${esc(intr.family)}</span></div><div class="qualified">${esc((intr.op_keys || []).map(k => 'cce.' + k).join(', '))}</div><div class="detail-actions"><button id="back-to-list" class="mobile-return text-button">返回列表</button><button id="copy-signature" class="quiet-button">复制符号</button><button id="copy-link" class="quiet-button">复制链接</button><span class="detail-status">CCE Dialect LLVM Intrinsic</span></div></div><div class="detail-tabs" role="tablist" aria-label="详情内容">${tabs.map(([id, title]) => `<button id="tab-${id}" role="tab" data-tab="${id}" aria-controls="detail-content" tabindex="${state.tab === id ? 0 : -1}" aria-selected="${state.tab === id}">${title}</button>`).join('')}</div><div class="detail-body" id="detail-content" role="tabpanel" aria-labelledby="tab-${state.tab}">${body}</div>`;
    if (state.tab === 'definition') {
      const paths = intr.entry_paths.map(p => `<p><b>${labels[p.status]}</b> · <code>${esc(p.entry)}</code><br>${esc(p.condition)}<br><small>${esc(sourceLabel(p.definition))} → ${esc(sourceLabel(p.dispatch))}</small></p>`).join('');
      $('#detail-content').insertAdjacentHTML('afterbegin', paths || '<p>待核对 · 仍需核对入口约束和实际翻译分支。</p>');
    }
    $('#copy-signature').onclick = () => copyText(intr.llvm_intrinsic);
  }

  if (r.dialectOp) $('#detail-content').insertAdjacentHTML('afterbegin', '<p class="callout">TableGen 映射行来自源码。上游 Op 关联及 CCEC 对应为名称规则生成的候选，尚未验证语义等价或编译结果。</p>');
  $('#copy-link').onclick = () => copyText(location.href);
  $('#back-to-list').onclick = () => {
    readingDetail = false;
    const button = $('#rows [aria-current="true"]');
    button?.scrollIntoView({block: 'center'});
    button?.focus({preventScroll: true});
    queueMore();
  };
  pane.querySelectorAll('[data-tab]').forEach(b => b.onclick = () => {
    state.tab = b.dataset.tab;
    renderDialectDetail(r);
    $('#tab-' + state.tab).focus();
  });
  appendLLVMRelations(pane,r.id);
  wireOpLinks(pane);
}

function renderAscendcReport() {
  const c = ascendcData.counts || {};
  const bCond = c.basic_api_by_condition_3510 || {};
  const cCond = c.capi_by_condition_3510 || {};
  $('#report').innerHTML = `<h2>AscendC 双层知识库 · Huawei Ascend 950 / A5</h2><p>固定目标 <code>Ascend950PR_9579</code> · <code>__NPU_ARCH__ = 3510</code>。上层 <strong>AscendC 基础 C++ API (basic_api)</strong> 提供基于 <code>LocalTensor</code> / <code>GlobalTensor</code> / <code>RegTensor</code> / <code>AscendC::Simt</code> 的 C++ 模板接口；下层 <strong>AscendC C / SIMT API (c_api + simt_api)</strong> 提供统一层级的 DMA、Cube、UB↔Reg、Vector Reg、同步与 SIMT 原语。</p><table class="parameter-table"><thead><tr><th>纵向层级</th><th>3510 局部条件符合</th><th>待确认</th><th>3510 条件排除</th><th>合计</th></tr></thead><tbody><tr><td>上层：AscendC 基础 C++ API (basic_api)</td><td>${bCond.matches || 0}</td><td>${bCond.unknown || 0}</td><td>${bCond.excluded || 0}</td><td>${c.basic_api_total || 0}</td></tr><tr><td>下层：AscendC C / SIMT API (c_api + simt_api)</td><td>${cCond.matches || 0}</td><td>${cCond.unknown || 0}</td><td>${cCond.excluded || 0}</td><td>${c.capi_total || 0}</td></tr></tbody></table><h3>底层 c_api / simt_api 子域分布</h3><table class="parameter-table"><thead><tr><th>接口域</th><th>接口数量</th></tr></thead><tbody>${Object.entries(c.capi_by_group || {}).map(([g, n]) => `<tr><td>${esc(g)}</td><td>${n}</td></tr>`).join('')}</tbody></table><h3>证据与限制</h3><p>条件计数只评估每条声明的局部预处理条件；不代表 include 路径可达、实现可用或设备支持。缺少宏定义时保留待确认。分类与跨层关联使用名称规则，均为候选，不提供未经核验的调用比例。</p><p>每个条目保留全部声明形式、原始条件和来源；编译、运行、性能均未验证。</p>`;
}

function renderDialectReport() {
  const c = dialectData.counts || {};
  const modes = c.ops_by_lowering_mode || {};
  $('#report').innerHTML = `<h2>CCE Dialect 双层知识库 · MLIR ⇄ BiSheng LLVM IR</h2><p>固定来源仓库 <code>${esc(dialectData.source?.repository || '')}</code> · Commit <code>${esc((dialectData.source?.commit || '').slice(0, 12))}</code> · 目标硬件 <code>dav-351x</code>（UB 256KiB，向量寄存器 256B，对应 Huawei Ascend 950 / A5）。</p><table class="parameter-table"><thead><tr><th>纵向层级</th><th>条目数</th><th>说明</th></tr></thead><tbody><tr><td>上层：CCE Dialect 语义 Ops (语义算子层)</td><td>${c.ops || 0}</td><td>来自 <code>CCEOps.td</code> (207) 与 <code>CCESIMTOps.td</code> (40)，挂载 <code>CCESpec.md</code> 中文规格 (${c.ops_with_spec_doc || 0} 项匹配)</td></tr><tr><td>下层：CCE Dialect LLVM Intrinsics (后端 Intrinsic 层)</td><td>${c.intrinsics || 0}</td><td>仅计具体 <code>llvm.hivm.*</code> 符号；来源 <code>CCEIntrinsicOps.td</code> (${c.explicit_mlir_intr_ops || 0} 个 <code>cce.intr.*</code>) 与 <code>CCEIntrinsicMap.td</code> / <code>CCESIMTIntrinsicMap.td</code> (${c.tablegen_mapping_rows || 0} 行 TableGen 映射)，另计 C++ 调用、内嵌 IR 和按翻译分支生成的名称。动态拼名未验证入口可达性；访存位宽取自输入类型，当前展开 8/16/32/64 位。</td></tr></tbody></table><h3>源码可达 · ${c.path_status?.confirmed || 0} 个目标符号</h3><p>待核对 ${c.path_status?.pending || 0} 个，入口已拒绝 ${c.path_status?.rejected || 0} 个。直接编写 cce.intr.* 与上层语义 Op 分别核对。</p><h3>已追踪的普通 LLVM IR</h3>${(dialectData.ordinary_lowerings || []).map(p=>`<p><code>${esc(p.entry)} → ${esc(p.opcode)}</code> · ${esc(p.condition)}</p>`).join('')}<h3>上层 Op 翻译分类（启发式）</h3><table class="parameter-table"><thead><tr><th>翻译模式</th><th>Op 数量</th></tr></thead><tbody>${Object.entries(modes).map(([k, v]) => `<tr><td>${esc(loweringModeLabels[k] || k)}</td><td>${v}</td></tr>`).join('')}</tbody></table><h3>未建立静态 LLVM 映射 · ${c.unresolved_lowerings || 0}</h3><p>以下 MLIR Op 保留为待解析项，不生成占位 LLVM 符号，也不计入上面的具体 intrinsic 数量。</p>${(dialectData.unresolved_lowerings || []).map(item => `<details><summary><code>${esc(item.mnemonic)}</code> · ${esc(sourceLabel(item.source))}</summary><pre><code>${esc(item.excerpt)}</code></pre></details>`).join('')}`;
}

function dialectPathMatches(item, scope) {
  if (!item || scope === 'all' || item.path_status === scope) return true;
  if (scope !== 'semantic' && scope !== 'raw') return false;
  return item.entry_paths.some(p => p.status === 'confirmed' && p.entry.startsWith('cce.intr.') === (scope === 'raw'));
}

function dialectSourceCell(record) {
  const labels = record.files.map(path => path.split('/').pop());
  return `<td title="${esc(record.files.join(' · '))}">${esc(labels.join(' · '))}</td>`;
}

function configureDialectSourceColumn() {
  if (state.backend !== 'cce-dialect' || state.dialectLayer !== 'intrinsics') return;
  const heading = document.createElement('th');
  heading.id = 'dialect-source-heading';
  const select = document.createElement('select');
  select.id = 'dialect-source';
  select.setAttribute('aria-label', '筛选 Dialect LLVM 来源');
  select.add(new Option('来源', ''));
  const paths = new Set(dialectRecords.filter(r => r.dialectIntr).flatMap(r => r.files));
  if (state.file) paths.add(state.file);
  for (const path of [...paths].sort()) select.add(new Option(path.split('/').pop(), path));
  select.value = state.file;
  select.onchange = () => {
    state.file = select.value;
    state.selected = '';
    render();
    $('#dialect-source')?.focus();
  };
  heading.append(select);
  $('#classification-heading').before(heading);
}
