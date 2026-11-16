'use strict';
const ccecStatic = knowledgeData.ccec.static_support;
function staticArch() {
  return state.architecture.startsWith('__NPU_ARCH__=') ? state.architecture.split('=')[1] : null;
}
function staticRow(r,arch=staticArch()) {return ccecStatic?.architectures[arch]?.[r.id];}
function staticState(r) {const row=staticRow(r);return row ? ccecStatic.states[row[0]] : '';}
function staticReference(index,arch) {
  const ref=ccecStatic.references[index];
  const route=ccecStatic.paths[arch]?.[ref.file] || [];
  return `<details><summary><code>${esc(ref.name)}</code> · ${esc(ref.core_guards.join(' / ') || '未标明核保护块')}</summary><p class="condition">${esc(ref.file)}:${ref.line}</p><p class="condition">SHA-256 ${esc(ref.sha256)}</p><h3>引用处条件</h3>${ref.conditions.map(c=>`<p class="condition">${esc(c)}</p>`).join('') || '<p>无附加预处理条件。</p>'}<h3>架构选择路径</h3>${route.length ? route.map(i=>{const e=ccecStatic.edges[i];return `<p class="condition">${esc(e.file)}:${e.line} → ${esc(e.name)}</p><p class="condition">${esc(e.conditions.join(' && '))}</p><p class="condition">SHA-256 ${esc(e.sha256)}</p>`;}).join('') : '<p>未取得明确架构选择路径；此引用不能证明目标适用。</p>'}</details>`;
}
function staticContent(r) {
  if(!ccecStatic || !isInterface(r))return '';
  const arch=staticArch(),row=staticRow(r),status=staticState(r);
  const otherMacros=[...new Set(r.compatibility.conditions.join(' ').match(/\b(?:__\w+|ENABLE_\w+)\b/g) || [])].filter(m=>m!=='__NPU_ARCH__');
  return `<section class="static-evidence"><h3>名称级源码线索${arch?' · '+esc(arch):''}</h3>${row?`<p><strong>${esc(ccecStatic.labels[status])}</strong></p><p>名称引用 ${row[1]} 处；核保护线索：${esc(row[2].join(' / ') || '未标明')}。</p>${row[3].map(i=>staticReference(i,arch)).join('')}${row[1]>row[3].length?'<p>展示代表性引用；完整引用可通过 support 查询分页获取。</p>':''}`:'<p>请选择芯片或 NpuArch 条件，查看对应源码证据。</p>'}<p>此线索不用于 op 支持判定。引用按名称关联，不保证当前重载、类型或模板形式适用；核保护线索也不证明其他核不支持。未执行编译或设备验证。</p>${otherMacros.length?`<details><summary>声明条件涉及的其他宏</summary><p class="condition">${esc(otherMacros.join(' · '))}</p><p>未获得完整定义环境，不能擅自当作未定义或零。</p></details>`:''}${r.compatibility.ignored_guards?.length?`<details><summary>已排除的声明保护宏</summary><p class="condition">${esc(r.compatibility.ignored_guards.join(' && '))}</p><p>这是重复声明保护，不作为架构功能判断。</p></details>`:''}</section>`;
}
function staticExport(items) {
  if(!ccecStatic)return null;
  const arch=staticArch();
  return {scope:'name_level_static_source_evidence',architecture:arch,source_evidence_sha256:ccecStatic.source_hash,
    records:items.filter(isInterface).map(r=>{const row=staticRow(r);return {id:r.id,state:staticState(r) || 'not_evaluated',reference_count:row?.[1] || 0,core_guards:row?.[2] || [],references:(row?.[3] || []).map(i=>({reference:ccecStatic.references[i],selector_path:(ccecStatic.paths[arch]?.[ccecStatic.references[i].file] || []).map(e=>ccecStatic.edges[e])}))};})};
}
