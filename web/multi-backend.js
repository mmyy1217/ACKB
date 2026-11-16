'use strict';

const ascendcData = knowledgeData.ascendc || {basic_api: [], c_api: [], counts: {}, files: {}, limitations: []};
const dialectData = knowledgeData.cce_dialect || {ops: [], intrinsics: [], counts: {}, source: {files: {}}, limitations: []};

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
    builtins: item.ccec_op_ids || [],
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
    builtins: [...(o.intrinsic_ids || []), ...(o.ccec_op_ids || [])],
    conditions: [o.lowering_mode],
    source: o.source,
    files: [o.source.file, ...(o.spec?.source ? [o.spec.source.file] : [])],
    compatibility: {profiles: {[A5_PROFILE]: 'matches'}},
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
    builtins: [...(i.upstream_op_ids || []), ...(i.ccec_op_ids || [])],
    conditions: i.mapping_classes || [],
    source: i.source,
    files: [i.source.file, ...(i.mlir_intr_ops || []).map(m => m.source.file)],
    compatibility: {profiles: {[A5_PROFILE]: 'matches'}},
    deprecation: {status: 'unmarked'},
  }));
  return [...ops, ...intrs];
}

const ascendcRecords = createAscendcRecords();
const dialectRecords = createDialectRecords();

const loweringModeLabels = {
  direct_to_llvm_ir: 'cce-translate 直接翻译',
  lowers_to_cce_intr: '降级为 cce.intr.*',
  simt_translation: 'SIMT 翻译管线',
  scope_or_region: 'Region 作用域',
};

const callKindLabels = {
  direct_ccec_intrinsic: '直调 CCEC Intrinsics (clang_builtin_alias)',
  via_ccec_wrapper: '调用 CCEC 接口 (wrapper)',
  both_intrinsic_and_wrapper: '同名含 Intrinsics 与封装重载',
  unresolved: '待确认',
};

function renderAscendcDetail(r) {
  const pane = $('#detail'), item = r.ascendc;
  const isBasic = r.ascendcLayer === 'basic';
  const condLabels = {matches: '950 (dav_3510) 已实现 / 条件符合', unknown: '950 条件待确认', excluded: '950 排除 (仅 2201 声明)'};
  const forms = item.forms || [];
  if (!forms.some((_, i) => String(i) === state.opForm)) state.opForm = '0';
  const activeForm = forms[Number(state.opForm)] || forms[0] || {signature: item.name, parameters: [], source: item.source};
  const tabs = [['definition', isBasic ? '接口与调用链' : '底层原语与调用链'], ['source', '3510 实现与来源'], ['experiments', '验证状态']];

  const calleesHTML = (item.ccec_callees || []).length
    ? `<table class="parameter-table"><thead><tr><th>调用的 CCEC 符号</th><th>调用层级性质</th><th>关联唯一 CCEC Intrinsics</th></tr></thead><tbody>${item.ccec_callees.map(c => {
      const calleeRefId = (c.wrapper_record_ids || []).find(id => byId.has(id)) || (c.entry_record_ids || []).find(id => byId.has(id));
      const calleeCell = calleeRefId ? opLink(calleeRefId, c.name) : `<code>${esc(c.name)}</code>`;
      return `<tr><td>${calleeCell}</td><td>${esc(callKindLabels[c.call_kind] || c.call_kind)}</td><td>${(c.op_ids || []).map(oid => opLink(oid, oid.replace('ccec_op___builtin_cce_', '__builtin_cce_'))).join(' ') || '—'}</td></tr>`;
    }).join('')}</tbody></table>`
    : '<p>当前 3510 静态扫描未检出直接 CCEC 指令调用（可能为纯辅助或宏转发）。</p>';

  const implFuncsHTML = isBasic && (item.impl_3510_functions || []).length
    ? `<h3>dav_3510 内部实现函数 · ${item.impl_3510_functions.length}</h3>` + item.impl_3510_functions.map(im => `<details><summary><code>${esc(im.name)}</code> · ${esc(sourceLabel(im.source))}</summary><pre><code>${esc(im.signature)}</code></pre></details>`).join('')
    : '';

  let body = '';
  if (state.tab === 'source') {
    const declSha = ascendcData.files?.[item.source.file]?.sha256 || '';
    const implSha = item.impl_source ? (ascendcData.files?.[item.impl_source.file]?.sha256 || '') : '';
    body = `<h3>声明来源</h3><p class="source-ref">${esc(sourceLabel(item.source))}</p>${declSha ? `<p class="condition">SHA-256 ${esc(declSha)}</p>` : ''}${item.impl_source ? `<h3>950 (dav_3510 / reg_base_impl) 实现来源</h3><p class="source-ref">${esc(sourceLabel(item.impl_source))}</p>${implSha ? `<p class="condition">SHA-256 ${esc(implSha)}</p>` : ''}` : ''}<h3>源码摘录（3510 实现 / 声明）</h3><pre><code>${esc(item.excerpt || activeForm.signature)}</code></pre><div class="callout">静态提取自 CANN ${esc(ascendcData.version)} 头文件，保留位域拼接与核保护分支。</div>`;
  } else if (state.tab === 'experiments') {
    body = experimentsContent();
  } else {
    body = `<label class="overloads">重载 / 模板形式 · ${forms.length} 种（共 ${item.overload_count} 条）<select id="ascendc-form" aria-label="选择重载形式">${forms.map((f, i) => `<option value="${i}" ${String(i) === state.opForm ? 'selected' : ''}>${i + 1}. ${esc((f.return_type || 'void') + ' ' + item.name + '(' + (f.parameters || []).join(', ') + ')')}</option>`).join('')}</select></label><pre class="signature"><code>${esc(activeForm.signature)}</code></pre><dl class="detail-meta"><dt>所属层级</dt><dd>${isBasic ? 'AscendC 接口 (basic_api)' : 'AscendC 底层接口 (c_api / simt_api)'}</dd><dt>950 状态</dt><dd>${esc(condLabels[item.condition_3510] || item.condition_3510)}</dd>${item.core_guards?.length ? `<dt>核保护线索</dt><dd><code>${esc(item.core_guards.join(' / '))}</code></dd>` : ''}<dt>声明位置</dt><dd class="source-ref">${esc(sourceLabel(activeForm.source || item.source))}</dd>${item.impl_source ? `<dt>3510 实现位置</dt><dd class="source-ref">${esc(sourceLabel(item.impl_source))}</dd>` : ''}</dl>${activeForm.parameters?.length ? `<h3>参数列表</h3><table class="parameter-table"><thead><tr><th>序号</th><th>类型 / 名称 / 默认值</th></tr></thead><tbody>${activeForm.parameters.map((p, i) => `<tr><td>${i + 1}</td><td><code>${esc(p)}</code></td></tr>`).join('')}</tbody></table>` : ''}${implFuncsHTML}<h3>底层 CCEC 调用关系 · ${(item.ccec_callees || []).length}</h3><p>点击右侧 builtin 链接可直接跳转到 CCEC Intrinsics 层查看对应编译器原语：</p>${calleesHTML}`;
  }

  pane.innerHTML = `<div class="detail-heading"><h2>${esc(item.name)}</h2><div class="detail-domain"><span>${esc(item.group)}</span><span>${esc(item.family)}</span></div>${item.namespace ? `<div class="qualified">${esc(item.namespace)}::${esc(item.name)}</div>` : ''}<div class="detail-actions"><button id="back-to-list" class="mobile-return text-button">返回列表</button><button id="copy-signature" class="quiet-button">复制签名</button><button id="copy-link" class="quiet-button">复制链接</button><span class="detail-status">${isBasic ? 'AscendC 接口' : 'ASC 底层接口'}</span></div></div><div class="detail-tabs" role="tablist" aria-label="详情内容">${tabs.map(([id, title]) => `<button id="tab-${id}" role="tab" data-tab="${id}" aria-controls="detail-content" tabindex="${state.tab === id ? 0 : -1}" aria-selected="${state.tab === id}">${title}</button>`).join('')}</div><div class="detail-body" id="detail-content" role="tabpanel" aria-labelledby="tab-${state.tab}">${body}</div>`;

  if ($('#ascendc-form')) {
    $('#ascendc-form').onchange = e => {
      state.opForm = e.target.value;
      renderAscendcDetail(r);
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
  wireOpLinks(pane);
}

function renderDialectDetail(r) {
  const pane = $('#detail');
  const isOp = r.dialectLayer === 'ops';
  const tabs = [['definition', isOp ? 'Op 规格与降级映射' : 'Intrinsic 映射与来源 Op'], ['source', 'TableGen 源码证据'], ['experiments', '验证状态']];

  if (isOp) {
    const o = r.dialectOp;
    const intrLinks = (o.intrinsic_ids || []).map(id => opLink(id, byId.get(id)?.name || id)).join(' ');
    const ccecLinks = (o.ccec_op_ids || []).map(id => opLink(id, id.replace('ccec_op___builtin_cce_', '__builtin_cce_'))).join(' ');
    let body = '';
    if (state.tab === 'source') {
      body = `<h3>TableGen 定义来源</h3><p class="source-ref">${esc(sourceLabel(o.source))}</p><p class="condition">SHA-256 ${esc(o.source.sha256)}</p><pre><code>${esc(o.excerpt)}</code></pre>${o.spec ? `<h3>CCESpec.md 文档来源</h3><p class="source-ref">${esc(sourceLabel(o.spec.source))} (§ ${o.spec.section_number} ${esc(o.spec.op_def)})</p>` : ''}`;
    } else if (state.tab === 'experiments') {
      body = experimentsContent();
    } else {
      body = `<pre class="signature"><code>${esc(o.name)} ${esc(o.assembly_format || '')}</code></pre><dl class="detail-meta"><dt>TableGen 定义</dt><dd><code>${esc(o.def_name)} : ${esc(o.op_class)}</code></dd><dt>翻译管线模式</dt><dd>${esc(loweringModeLabels[o.lowering_mode] || o.lowering_mode)}</dd><dt>来源位置</dt><dd class="source-ref">${esc(sourceLabel(o.source))}</dd>${o.has_verifier ? '<dt>Verifier</dt><dd>已启用 (hasVerifier = 1)</dd>' : ''}</dl>${o.summary ? `<h3>概述</h3><p>${esc(o.summary)}</p>` : ''}${o.arguments ? `<h3>操作数与属性 (ins)</h3><pre><code>${esc(o.arguments)}</code></pre>` : ''}${o.results ? `<h3>返回值 (outs)</h3><pre><code>${esc(o.results)}</code></pre>` : ''}${o.description ? `<h3>TableGen 说明</h3><pre class="knowledge-prose"><code>${esc(o.description)}</code></pre>` : ''}<h3>降级到的 CCE Dialect Intrinsics · ${(o.intrinsic_ids || []).length}</h3>${intrLinks ? `<p>${intrLinks}</p>` : '<p>该 Op 为作用域终结符或通过独立 Pass 处理，无静态 llvm.hivm.* 表项。</p>'}${ccecLinks ? `<h3>关联 CCEC Intrinsics · ${(o.ccec_op_ids || []).length}</h3><p>${ccecLinks}</p>` : ''}${o.spec ? `<h3>CCESpec.md 中文规格说明 (§ ${o.spec.section_number} · ${esc(o.spec.title_zh)})</h3><pre class="knowledge-prose"><code>${esc(o.spec.body)}</code></pre>` : ''}`;
    }
    pane.innerHTML = `<div class="detail-heading"><h2>${esc(o.name)}</h2><div class="detail-domain"><span>${esc(o.group)}</span><span>${esc(o.family)}</span></div><div class="qualified">${esc(o.def_name)} · ${esc(loweringModeLabels[o.lowering_mode] || o.lowering_mode)}</div><div class="detail-actions"><button id="back-to-list" class="mobile-return text-button">返回列表</button><button id="copy-signature" class="quiet-button">复制语法</button><button id="copy-link" class="quiet-button">复制链接</button><span class="detail-status">CCE Dialect Op</span></div></div><div class="detail-tabs" role="tablist" aria-label="详情内容">${tabs.map(([id, title]) => `<button id="tab-${id}" role="tab" data-tab="${id}" aria-controls="detail-content" tabindex="${state.tab === id ? 0 : -1}" aria-selected="${state.tab === id}">${title}</button>`).join('')}</div><div class="detail-body" id="detail-content" role="tabpanel" aria-labelledby="tab-${state.tab}">${body}</div>`;
    $('#copy-signature').onclick = () => copyText(`${o.name} ${o.assembly_format || ''}`.trim());
  } else {
    const intr = r.dialectIntr;
    const upLinks = (intr.upstream_op_ids || []).map(id => opLink(id, byId.get(id)?.name || id)).join(' ');
    const ccecLinks = (intr.ccec_op_ids || []).map(id => opLink(id, id.replace('ccec_op___builtin_cce_', '__builtin_cce_'))).join(' ');
    const mlirOpsHTML = (intr.mlir_intr_ops || []).length
      ? `<h3>显式 MLIR Intrinsic Op (CCEIntrinsicOps.td) · ${intr.mlir_intr_ops.length}</h3>` + intr.mlir_intr_ops.map(m => `<div class="rule-entry"><code>${esc(m.mnemonic)} (${esc(m.def_name)})</code><p>${esc(m.summary)}</p>${m.arguments ? `<pre><code>ins: ${esc(m.arguments)}\nouts: ${esc(m.results || 'empty')}</code></pre>` : ''}<p class="condition">${esc(sourceLabel(m.source))}</p></div>`).join('')
      : '';
    const mapRowsHTML = `<table class="parameter-table"><thead><tr><th>TableGen Def</th><th>映射类型</th><th>Op 键</th><th>规格参数 (Lanes / Type / Mode)</th></tr></thead><tbody>${(intr.mappings || []).map(m => {
      const spec = [
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
      body = `<h3>TableGen 映射来源</h3><p class="source-ref">${esc(sourceLabel(intr.source))}</p><p class="condition">SHA-256 ${esc(intr.source.sha256)}</p><pre><code>${esc(intr.excerpt)}</code></pre>`;
    } else if (state.tab === 'experiments') {
      body = experimentsContent();
    } else {
      body = `<pre class="signature"><code>${esc(intr.llvm_intrinsic)}</code></pre><dl class="detail-meta"><dt>后端目标符号</dt><dd><code>${esc(intr.llvm_intrinsic)}</code></dd><dt>映射规则类</dt><dd><code>${esc((intr.mapping_classes || []).join(', '))}</code></dd><dt>来源位置</dt><dd class="source-ref">${esc(sourceLabel(intr.source))}</dd></dl>${mlirOpsHTML}<h3>TableGen 映射条目 · ${(intr.mappings || []).length}</h3>${mapRowsHTML}<h3>上游语义 Op (CCE Dialect Ops) · ${(intr.upstream_op_ids || []).length}</h3>${upLinks ? `<p>点击可回到上层查看语义定义与 CCESpec.md 位域打包规则：${upLinks}</p>` : '<p>该 Intrinsic 由 cce.intr.* 或底层通道直接暴露。</p>'}${ccecLinks ? `<h3>对应 CCEC Intrinsics · ${(intr.ccec_op_ids || []).length}</h3><p>${ccecLinks}</p>` : ''}`;
    }
    pane.innerHTML = `<div class="detail-heading"><h2>${esc(intr.name)}</h2><div class="detail-domain"><span>${esc(intr.group)}</span><span>${esc(intr.family)}</span></div><div class="qualified">${esc((intr.op_keys || []).map(k => 'cce.' + k).join(', '))}</div><div class="detail-actions"><button id="back-to-list" class="mobile-return text-button">返回列表</button><button id="copy-signature" class="quiet-button">复制符号</button><button id="copy-link" class="quiet-button">复制链接</button><span class="detail-status">CCE Dialect Intrinsic</span></div></div><div class="detail-tabs" role="tablist" aria-label="详情内容">${tabs.map(([id, title]) => `<button id="tab-${id}" role="tab" data-tab="${id}" aria-controls="detail-content" tabindex="${state.tab === id ? 0 : -1}" aria-selected="${state.tab === id}">${title}</button>`).join('')}</div><div class="detail-body" id="detail-content" role="tabpanel" aria-labelledby="tab-${state.tab}">${body}</div>`;
    $('#copy-signature').onclick = () => copyText(intr.llvm_intrinsic);
  }

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
  wireOpLinks(pane);
}

function renderAscendcReport() {
  const c = ascendcData.counts || {};
  const bCond = c.basic_api_by_condition_3510 || {};
  const cCond = c.capi_by_condition_3510 || {};
  $('#report').innerHTML = `<h2>AscendC 双层知识库 · Huawei Ascend 950 / A5</h2><p>固定目标 <code>Ascend950PR_9579</code> · <code>__NPU_ARCH__ = 3510</code>。上层 <strong>AscendC 接口 (basic_api)</strong> 提供基于 <code>LocalTensor</code> / <code>GlobalTensor</code> / <code>RegTensor</code> / <code>AscendC::Simt</code> 的 C++ 模板接口；下层 <strong>AscendC 底层接口 (c_api + simt_api)</strong> 提供统一层级的 DMA、Cube、UB↔Reg、Vector Reg、同步与 SIMT 原语。</p><table class="parameter-table"><thead><tr><th>纵向层级</th><th>950 已实现 / 条件符合</th><th>待确认</th><th>950 排除 (仅 2201 等)</th><th>合计</th></tr></thead><tbody><tr><td>上层：AscendC 接口 (basic_api)</td><td>${bCond.matches || 0}</td><td>${bCond.unknown || 0}</td><td>${bCond.excluded || 0}</td><td>${c.basic_api_total || 0}</td></tr><tr><td>下层：AscendC 底层接口 (c_api + simt_api)</td><td>${cCond.matches || 0}</td><td>${cCond.unknown || 0}</td><td>${cCond.excluded || 0}</td><td>${c.capi_total || 0}</td></tr></tbody></table><h3>底层 c_api / simt_api 子域分布</h3><table class="parameter-table"><thead><tr><th>接口域</th><th>接口数量</th></tr></thead><tbody>${Object.entries(c.capi_by_group || {}).map(([g, n]) => `<tr><td>${esc(g)}</td><td>${n}</td></tr>`).join('')}</tbody></table><h3>与 CCEC 双层的调用关系说明</h3><p>经静态源码核验，AscendC 的 950 (<code>dav_3510</code> / <code>reg_base_impl</code>) 实现中，约 42.5% 的底层被调符号（如 <code>copy_gm_to_ubuf_align_v2</code>、<code>nddma_out_to_ub_b8</code>、<code>set_loop_size_outtoub</code>）直接调用 <strong>CCEC Intrinsics</strong> (<code>clang_builtin_alias</code>)，不经过 CCEC 上层包装；其余（如 <code>vsub</code>、<code>mad</code>、<code>__atomic_add</code>）经 <strong>CCEC 接口</strong> 包装函数转发至 <code>__builtin_cce_*</code>。</p>`;
}

function renderDialectReport() {
  const c = dialectData.counts || {};
  const modes = c.ops_by_lowering_mode || {};
  $('#report').innerHTML = `<h2>CCE Dialect 双层知识库 · MLIR ⇄ BiSheng LLVM IR</h2><p>固定来源仓库 <code>${esc(dialectData.source?.repository || '')}</code> · Commit <code>${esc((dialectData.source?.commit || '').slice(0, 12))}</code> · 目标硬件 <code>dav-351x</code>（UB 256KiB，向量寄存器 256B，对应 Huawei Ascend 950 / A5）。</p><table class="parameter-table"><thead><tr><th>纵向层级</th><th>条目数</th><th>说明</th></tr></thead><tbody><tr><td>上层：CCE Dialect Ops (语义算子层)</td><td>${c.ops || 0}</td><td>来自 <code>CCEOps.td</code> (207) 与 <code>CCESIMTOps.td</code> (40)，挂载 <code>CCESpec.md</code> 中文规格 (${c.ops_with_spec_doc || 0} 项匹配)</td></tr><tr><td>下层：CCE Dialect Intrinsics (后端 Intrinsic 层)</td><td>${c.intrinsics || 0}</td><td>聚合 <code>CCEIntrinsicOps.td</code> (${c.explicit_mlir_intr_ops || 0} 个 <code>cce.intr.*</code>) 与 <code>CCEIntrinsicMap.td</code> / <code>CCESIMTIntrinsicMap.td</code> (${c.tablegen_mapping_rows || 0} 行 TableGen 映射)</td></tr></tbody></table><h3>上层 Op 翻译管线分布</h3><table class="parameter-table"><thead><tr><th>翻译模式</th><th>Op 数量</th></tr></thead><tbody>${Object.entries(modes).map(([k, v]) => `<tr><td>${esc(loweringModeLabels[k] || k)}</td><td>${v}</td></tr>`).join('')}</tbody></table>`;
}
