'use strict';
const $ = selector => document.querySelector(selector);
let data = JSON.parse($('#catalog-data').textContent);
let opRecords = createOpRecords(data);
let allRecords = [...opRecords, ...data.records, ...knowledgeRecords, ...ascendcRecords, ...dialectRecords, ...llvmRecords,...nvvmRecords];
let records = data.records;
const byId = new Map(allRecords.map(r => [r.id, r]));
const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = value => value.toLocaleString('en-US');
const isInterface = r => r.kind === 'interface' || r.kind === 'interface_macro';
const kinds = {interface:'函数接口',interface_macro:'宏接口',type:'类型定义',macro:'宏定义',constant:'常量 / 变量',helper:'辅助函数'};
const shortGroup = {'AI Core':'AI Core','Vector / AVE':'AVE','Legacy SIMD':'Legacy','SIMT':'SIMT','配套定义':'辅助'};
const families = ['搬运 / DMA','矩阵 / Cube','访存 / 布局','计算 / 其他','类型转换','同步 / 流水','原子操作','控制 / 寄存器'];
const BATCH_SIZE = 60;
const state = {home:false,llvmSource:'',llvmScope:'a5-sources',llvmEvidence:'',backend:'ccec',ccecLayer:'wrappers',ascendcLayer:'basic',dialectLayer:'ops',includeUnknown:false,opForm:'',opCaller:'',observedCall:'',ptxTarget:'sm_103a',support:'',proof:'',view:'interfaces',family:'',query:'',group:'',file:'',chip:'',architecture:'',availability:'',deprecation:'',limit:BATCH_SIZE,selected:'',tab:'definition'};
const mobile = window.matchMedia('(max-width:800px)');
let visible = [], timer, readingDetail = false, loadScheduled = false, progressScheduled = false;
let updatePanelWidths = () => {};
const sourceLabel = s => `${s.file}:${s.line}${s.end_line > s.line ? '–' + s.end_line : ''}`;
function searchText(r) {return [r.name,r.signature,r.group,r.family,r.namespace,r.transfer?.label || '',r.transfer?.search_alias || '',...r.builtins,...r.conditions,r.source.file,r.knowledge ? JSON.stringify(r.knowledge) : r.op ? r.op.aliases.join(' ') : r.ascendc ? [r.ascendc.qualified_name || '',...(r.ascendc.ccec_callees || []).map(c=>c.name)].join(' ') : r.dialectOp ? [r.dialectOp.def_name,r.dialectOp.summary,r.dialectOp.spec?.title_zh || ''].join(' ') : r.dialectIntr ? [...(r.dialectIntr.op_keys || []),...(r.dialectIntr.mlir_intr_ops || []).map(m=>m.mnemonic)].join(' ') : ''].join(' ').toLowerCase();}
const searchTexts = new Map(allRecords.map(r => [r.id, searchText(r)]));
let fileMap = new Map(data.files.map(f => [f.path,f]));

function lookupRecord(id) {return byId.get(id) || siteLoader?.lookup(id);}
function installBackend(backend, payload, navigation) {
  if(navigation) knowledgeData.navigation=navigation;
  if(backend==='ccec') {
    data=payload.catalog; knowledgeData.ccec=payload.knowledge;
    opModel=knowledgeData.ccec.ops; ccecStatic=knowledgeData.ccec.static_support;
    callEvidence=knowledgeData.ccec.call_evidence;
    directEntryIDs=new Set(callEvidence.direct_entry_ids);
    opRecords=createOpRecords(data); fileMap=new Map(data.files.map(f=>[f.path,f]));
    refreshKnowledge();
  } else if(backend==='ptx') {
    knowledgeData.ptx=payload; refreshKnowledge();
    learning=payload.learning; lessonViews=learning.chapters.map(c=>c.id);
  } else if(backend==='ascendc') {
    knowledgeData.ascendc=payload; ascendcData=payload; ascendcRecords=createAscendcRecords();
  } else if(backend==='cce-dialect') {
    knowledgeData.cce_dialect=payload; dialectData=payload; dialectRecords=createDialectRecords();
  } else if(backend==='nvvm'){knowledgeData.nvvm=payload;refreshNVVM();}
  else if(backend==='llvm') knowledgeData.llvm=payload;
  if(backend==='llvm' || navigation) refreshLLVM();
  allRecords=[...opRecords,...data.records,...knowledgeRecords,...ascendcRecords,...dialectRecords,...llvmRecords,...nvvmRecords];
  // Previously loaded databases retain their search index when another is opened.
  for(const record of allRecords) {
    byId.set(record.id,record);
    if(!searchTexts.has(record.id)) searchTexts.set(record.id,searchText(record));
  }
}
function navigateHash(reveal) {
  const params=new URLSearchParams(location.hash.slice(1));
  const home=!location.hash || location.hash==='#home' || location.hash==='#ascendc-map' || location.hash==='#insights' || location.hash.startsWith('#insight=');
  const requested=['ptx','ascendc','cce-dialect','llvm','nvvm'].includes(params.get('backend'))?params.get('backend'):'ccec';
  const backend=home?null:backendForLink(params.get('r') || '',requested);
  navigateWithData(backend,()=>{readHash();render(reveal);});
}

function saveHash(replace = true) {
  if(state.home)return;
  const p = new URLSearchParams();
  if(state.backend==='nvvm')p.set('backend','nvvm');
  if(state.symbolDepth)p.set('depth',state.symbolDepth);
  if(state.backend==='llvm'){p.set('backend','llvm');p.set('scope',state.llvmScope);if(state.llvmSource)p.set('source',state.llvmSource);if(state.llvmEvidence)p.set('evidence',state.llvmEvidence);if(state.includeUnknown)p.set('unknown','1');if(state.opForm)p.set('form',state.opForm);if(state.view==='report')p.set('view','report');}
  if (state.backend === 'ptx') {p.set('backend','ptx');p.set('target',state.ptxTarget);}
  if(state.backend==='ccec'){p.set('layer',state.ccecLayer==='interfaces'?'intrinsics':'interfaces');if(state.includeUnknown)p.set('unknown','1');}
  if(state.backend==='ascendc'){p.set('backend','ascendc');p.set('layer',state.ascendcLayer);if(state.includeUnknown)p.set('unknown','1');}
  if(state.backend==='cce-dialect'){p.set('backend','cce-dialect');p.set('layer',state.dialectLayer);}
  if (state.support) p.set('support',state.support);
  if (state.backend === 'ccec' && state.view !== 'interfaces' || state.backend === 'ptx' && state.view !== 'interfaces' || (state.backend === 'ascendc' || state.backend === 'cce-dialect') && state.view === 'report') p.set('view',state.view);
  for (const key of ['family','query','group','file','selected']) if (state[key]) p.set(key === 'selected' ? 'r' : key,state[key]);
  if(state.backend==='ascendc' && state.opForm)p.set('form',state.opForm);
  if(state.backend==='ccec' && byId.get(state.selected)?.op){if(state.opForm)p.set('form',state.opForm);if(state.opCaller)p.set('caller',state.opCaller);}
  if(state.backend==='ccec' && observedCalls(byId.get(state.selected) || {}).length && state.observedCall)p.set('call',state.observedCall);
  const target = '#' + p.toString();
  if (location.hash !== target) history[replace ? 'replaceState' : 'pushState'](null,'',target);
}
function readHash() {
  const p = new URLSearchParams(location.hash.slice(1));
  state.symbolDepth=Math.max(0,parseInt(p.get('depth'),10)||0);
  state.home=!location.hash || location.hash==='#home' || location.hash==='#ascendc-map' || location.hash==='#insights' || location.hash.startsWith('#insight=');
  state.llvmScope=['all','a5-evidence'].includes(p.get('scope'))?p.get('scope'):'a5-sources';state.llvmSource=Object.hasOwn(llvmSourceLabels,p.get('source'))?p.get('source'):'';state.llvmEvidence=Array.from($('#llvm-evidence').options).some(o=>o.value===p.get('evidence'))?p.get('evidence'):'';
  const rawBackend = p.get('backend');
  state.backend = ['ptx','ascendc','cce-dialect','llvm','nvvm'].includes(rawBackend) ? rawBackend : 'ccec';
  state.ptxTarget = ['sm_103','sm_103f','sm_103a'].includes(p.get('target')) ? p.get('target') : 'sm_103a';
  state.support = Object.hasOwn(supportLabels,p.get('support')) ? p.get('support') : '';
  state.ascendcLayer = p.get('layer') === 'capi' ? 'capi' : 'basic';
  state.dialectLayer = p.get('layer') === 'intrinsics' ? 'intrinsics' : 'ops';
  configureBackend();
  state.view = Object.hasOwn(viewLabels(),p.get('view')) ? p.get('view') : state.backend === 'nvvm' ? 'nvvm' : state.backend === 'llvm' ? 'llvm' : state.backend === 'ptx' ? 'interfaces' : state.backend === 'ascendc' ? state.ascendcLayer : state.backend === 'cce-dialect' ? (state.dialectLayer === 'intrinsics' ? 'dialect_intrinsics' : 'dialect_ops') : 'interfaces';
  for (const key of ['family','query','group','file','chip','architecture','availability','deprecation','proof']) state[key] = p.get(key) || '';
  state.includeUnknown=p.get('unknown')==='1';state.opForm=p.get('form') || '';state.opCaller=p.get('caller') || '';state.observedCall=p.get('call') || '';
  state.ccecLayer=p.get('layer')==='intrinsics' || p.get('view')==='interfaces'?'interfaces':'wrappers';
  if(state.backend==='ccec' && !p.has('view'))state.view=state.ccecLayer;
  state.selected = p.get('r') || '';
  if (state.selected && byId.has(state.selected)) {
    const sel = byId.get(state.selected);
    if (sel.backend === 'llvm') {state.backend='llvm';state.home=false;state.view=p.get('view')==='report'?'report':'llvm';if(sel.llvm.identity_status==='candidate_only')state.includeUnknown=true;if((!sel.llvm.static_target?.package_evidence && state.llvmScope==='a5-evidence') || (state.llvmScope==='a5-sources' && !sel.llvm.a5_source_lead))state.llvmScope='all';configureBackend();}
    else if (sel.backend === 'ascendc') {state.backend = 'ascendc'; state.ascendcLayer = sel.ascendcLayer; configureBackend(); state.view = recordView(sel);}
    else if (sel.backend === 'cce-dialect') {state.backend = 'cce-dialect'; state.dialectLayer = sel.dialectLayer; configureBackend(); state.view = recordView(sel);}
    else if (!p.has('view') || state.view==='interfaces' && !sel.op && !sel.knowledge) state.view = recordView(sel);
  }
  if(state.backend==='ccec'){if(ccecIsInterface(byId.get(state.selected) || {}))state.ccecLayer='wrappers';else if(byId.get(state.selected)?.op || opModel?.record_layers[state.selected]?.layer==='intrinsic_entry')state.ccecLayer='interfaces';fixedA5();const chosen=byId.get(state.selected),status=chosen?.compatibility?.profiles[A5_PROFILE];if(status==='unknown'){state.includeUnknown=true;fixedA5();}if(status==='excluded')state.view='references';}
  if(state.backend==='cce-dialect' && state.dialectLayer==='intrinsics'){state.file='';state.group='';}
  if(state.backend==='ascendc'){fixedA5();const chosen=byId.get(state.selected),status=chosen?.compatibility?.profiles?.[A5_PROFILE];if(status==='unknown'){state.includeUnknown=true;fixedA5();}}
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
function activeLayerView() {
  if(state.backend==='ptx')return 'interfaces';
  if(state.backend==='nvvm')return 'nvvm';
  if(state.backend==='llvm')return 'llvm';
  if (state.backend === 'ascendc') return state.ascendcLayer === 'capi' ? 'capi' : 'basic';
  if (state.backend === 'cce-dialect') return state.dialectLayer === 'intrinsics' ? 'dialect_intrinsics' : 'dialect_ops';
  return state.ccecLayer;
}
function download() {
  if(state.backend==='nvvm'){const a=document.createElement('a'),u=URL.createObjectURL(new Blob([JSON.stringify({...knowledgeData.nvvm,records:filtered().map(r=>r.nvvm)})],{type:'application/json'}));a.href=u;a.download='ackb-nvvm.json';a.click();setTimeout(()=>URL.revokeObjectURL(u),1000);return;}
  if(state.backend==='llvm')return downloadLLVM();
  if (state.backend === 'ptx' || state.view === 'topics') return downloadKnowledge();
  if (state.backend === 'ascendc' || state.backend === 'cce-dialect') {
    const items = filtered().map(r => r.ascendc || r.dialectOp || r.dialectIntr || r);
    const snapshot = state.backend === 'ascendc' ? ascendcData : dialectData;
    const blob = new Blob([JSON.stringify({version:snapshot.version,files:snapshot.files || snapshot.source.files,source:snapshot.source,limitations:snapshot.limitations,unresolved_lowerings:snapshot.unresolved_lowerings,generator_sha256:snapshot.generator_sha256,catalog_sha256:snapshot.catalog_sha256,schema_version:'ackb.web-export.v1',backend:state.backend,layer:activeLayerView(),target:'Ascend950PR_9579',selection:{...state},total:items.length,records:items},null,2)],{type:'application/json;charset=utf-8'});
    const url = URL.createObjectURL(blob), a = document.createElement('a');
    a.href = url; a.download = `ackb-${state.backend}-${activeLayerView()}.json`;a.click();setTimeout(() => URL.revokeObjectURL(url),1000);
    return;
  }
  const selected=filtered(), selectedIDs=new Set(selected.map(r=>r.id));
  const relatedOps=new Set(opModel.edges.filter(e=>selectedIDs.has(e.source_record)).map(e=>e.target_op));
  const selectedOps=opModel.ops.filter(o=>selectedIDs.has(o.id) || relatedOps.has(o.id)).map(scopedA5Op);
  const sourceIDs=new Set(selectedOps.flatMap(o=>[...o.entry_records,...o.caller_records]));
  const blob = new Blob([JSON.stringify({...data, records: selected, source_records:data.records.filter(r=>sourceIDs.has(r.id)), selection: {layer:state.ccecLayer,include_unknown:state.includeUnknown,view:state.view,family:state.family,query:state.query,group:state.group,file:state.file,chip:state.chip,architecture:state.architecture,availability:state.availability,deprecation:state.deprecation,proof:state.proof},static_evidence:staticExport(filtered()),observed_call_evidence:{coverage:callEvidence.coverage,limitations:callEvidence.limitations,files:callEvidence.files,calls:callEvidence.calls.filter(c=>selectedOps.some(o=>o.id===c.op_id))},op_model:opModel?{schema_version:opModel.schema_version,limitations:opModel.limitations,ops:selectedOps,edges:opModel.edges.filter(e=>sourceIDs.has(e.source_record) && selectedOps.some(o=>o.id===e.target_op))}:null, counts: filtered().reduce((a,r) => (a[r.kind]=(a[r.kind] || 0)+1,a),{})},null,2)],{type:'application/json;charset=utf-8'});
  const url = URL.createObjectURL(blob), a = document.createElement('a');
  a.href = url; a.download = `ackb-ccec-${data.version}.json`;a.click();setTimeout(() => URL.revokeObjectURL(url),1000);
}
function baseRecords() { if(state.backend==='ccec' && !['wrappers','interfaces','report'].includes(state.view))return [byId.get(state.selected)].filter(Boolean);return records.filter(r => (state.view==='records'?isInterface(r):state.view === 'all' ? !['note','lesson'].includes(r.kind) : recordView(r) === state.view)); }
function makeGroups(items) {
  if(depthEnabled())return symbolGroups(items);
  const groups = new Map();
  for (const r of items) {
    const key = r.llvm || r.knowledge || r.op || r.ascendc || r.dialectOp || r.dialectIntr ? r.id : state.view==='wrappers' ? [r.namespace || '',r.name].join('|') : [r.group,r.namespace || '',r.name,r.kind].join('|');
    if (!groups.has(key)) groups.set(key,{key,name:r.name,group:r.group,family:r.family,items:[]});
    groups.get(key).items.push(r);
  }
  return [...groups.values()];
}
function compatibilityMatches(r) {
  if(state.backend==='nvvm')return true;
  if(state.backend==='llvm')return llvmMatches(r);
  if(state.backend==='cce-dialect')return true;
  if(state.backend==='ascendc'){const st=r.compatibility?.profiles?.[A5_PROFILE] || 'matches';return state.includeUnknown ? st!=='excluded' : st==='matches';}
  if(state.backend==='ccec' && !['wrappers','interfaces'].includes(state.view))return true;
  if(r.op) return !state.architecture || !state.availability || (state.availability==='possible'?r.compatibility.profiles[state.architecture]!=='excluded':r.compatibility.profiles[state.architecture]===state.availability);
  if (r.knowledge) return !state.support || (r.knowledge.target_assessments?.[state.ptxTarget]?.support || 'unknown') === state.support;
  return (!state.proof || staticState(r) === state.proof) && (!state.deprecation || r.deprecation.status === state.deprecation) &&
    (!state.architecture || !state.availability || (state.availability === 'possible' ? r.compatibility.profiles[state.architecture] !== 'excluded' : r.compatibility.profiles[state.architecture] === state.availability));
}
function filtered(ignoreCompatibility = false) {
  const terms = state.query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  return baseRecords().filter(r => (ignoreCompatibility || compatibilityMatches(r)) && (!state.family || (state.backend === 'ptx' ? ptxCategoryMatches(r,state.family) : ccecFamilyMatches(r,state.family))) && (!state.group || r.group === state.group) && (!state.file || (r.files || [r.source.file]).includes(state.file)) && terms.every(t => searchTexts.get(r.id).includes(t)));
}
function syncControls() {
  $('#backend').value = state.backend==='nvvm'?'nvvm':state.backend==='llvm'?'llvm':state.backend==='ptx'?'ptx':state.backend==='ascendc'?(state.ascendcLayer==='capi'?'ascendc-capi':'ascendc'):state.backend==='cce-dialect'?(state.dialectLayer==='intrinsics'?'cce-dialect-intrinsics':'cce-dialect'):state.ccecLayer==='interfaces'?'ccec-intrinsics':'ccec';$('#ptx-support').value=state.support;
  $('#include-unknown').checked=state.includeUnknown;
  $('#llvm-scope').value=state.llvmScope;$('#llvm-evidence').value=state.llvmEvidence;
  $('#coverage').textContent=state.view==='report'?'返回指令':'说明 / 覆盖';
  document.querySelectorAll('[data-family] span').forEach(span => {const family = span.parentElement.dataset.family;span.textContent = fmt(state.backend === 'ptx' ? ptxInstructionCount(family) : makeGroups(records.filter(r => (state.backend==='llvm'?true:state.backend==='ascendc'?recordView(r)===activeLayerView():state.backend==='cce-dialect'?recordView(r)===activeLayerView():state.backend==='nvvm'?true:state.ccecLayer==='wrappers'?ccecIsInterface(r):r.op) && compatibilityMatches(r) && (!family || ccecFamilyMatches(r,family)))).length);});
  document.querySelectorAll('[data-cat-subs]').forEach(el => {const cid = el.dataset.catSubs;el.hidden = !(state.family === cid || state.family.startsWith(cid + '.'));});
  $('#search').value = state.query;$('#group').value = state.group;$('#file').value = state.file;
  $('#mobile-view').value = state.view;$('#mobile-family').value = state.family;
  document.querySelectorAll('[data-view]').forEach(b => {b.classList.toggle('active',b.dataset.view === state.view); if (b.dataset.view === state.view) b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
  document.querySelectorAll('[data-family]').forEach(b => {b.classList.toggle('active',b.dataset.family === state.family);b.setAttribute('aria-pressed',String(b.dataset.family === state.family));});
}
function render(revealSelection = false) {
  if(syncHome())return;
  if(state.backend==='ccec' || state.backend==='ascendc')fixedA5();
  document.body.classList.toggle('reading-ptx',isPtxReading());
  $('#reader-content').hidden = !isPtxReading();
  for(const el of document.querySelectorAll('.list-pane > .list-summary,.list-pane > .table-scroll,.list-pane > #load-status,.list-pane > #unknown-hint')) el.hidden=isPtxReading();
  if(isPtxReading()) {renderPtxReader();return;}
  readingDetail = false;
  window.scrollTo(0,0);
  const report = state.view === 'report';
  $('#catalog-view').hidden = report;$('#report').hidden = !report;
  $('#family-section').hidden = state.backend==='ptx'?state.view!=='interfaces':false;$('#mobile-family-label').hidden = state.backend==='ptx'?state.view!=='interfaces':false;
  $('#page-title').textContent = viewLabels()[state.view] || '来源详情';
  $('.toolbar').hidden = report;
  $('#dialect-source-heading')?.remove();
  document.querySelectorAll('.interface-table th')[0].textContent = state.backend === 'nvvm' ? 'NVVM 符号' : state.backend === 'llvm' ? 'LLVM 名称' : state.backend === 'ptx' ? '指令 / 章节' : state.backend === 'cce-dialect' ? (state.dialectLayer === 'intrinsics' ? 'LLVM intrinsic' : 'Dialect Op') : state.view==='interfaces'?'op / builtin':'声明 / 名称';
  document.querySelectorAll('.interface-table th')[2].textContent = state.backend === 'nvvm' ? '来源依据' : state.backend === 'llvm' ? '指令族' : state.backend === 'ptx' ? '文档条件' : state.backend === 'cce-dialect' ? '分类' : '950 条件';
  document.querySelectorAll('.interface-table th')[2].title = state.backend === 'ptx' ? '按官方文档判断 '+state.ptxTarget+' 的适用条件，不代表编译或运行验证' : '按来源头文件分组，不代表设备支持范围';
  document.querySelectorAll('.interface-table th')[3].textContent = depthEnabled() ? '记录数' : state.backend === 'llvm' ? '形式' : state.backend === 'ptx' ? '章节' : state.backend === 'cce-dialect' ? (state.dialectLayer === 'intrinsics' ? '映射' : '关联') : state.backend === 'ascendc' ? '重载' : state.view==='interfaces'?'形式':'声明';
  $('#classification-heading').title = state.backend === 'ptx' ? '按官方手册章节归类' : '按名称关键词归类';
  $('#classification-heading').textContent = state.backend === 'ptx' ? '类别' : state.view === 'definitions' ? '定义类型' : '指令族';
  configureLLVMColumns();configureDialectSourceColumn();syncControls();syncPtxNavigation();syncDepthControl();
  if (report) {setProgressActive(false);if($('#ptx-category-brief'))$('#ptx-category-brief').hidden=true;renderReport();saveHash();return;}
  $('#ptx-category-brief').hidden=true;
  const matches = filtered();
  visible = makeGroups(matches);
  const query = state.query.trim().toLowerCase();
  if (query) {
    const score = g => g.name.toLowerCase() === query ? 0 : g.name.toLowerCase().startsWith(query) ? 1 : g.name.toLowerCase().includes(query) ? 2 : 3;
    visible.sort((a,b) => score(a) - score(b) || a.name.localeCompare(b.name));
  }
  $('#result-count').textContent = state.backend==='ccec' && state.view==='interfaces' ? `${fmt(visible.length)} 个唯一 op` : state.backend==='cce-dialect' ? `${fmt(visible.length)} 个 ${state.dialectLayer==='intrinsics'?'Dialect Intrinsic':'Dialect Op'}` : state.backend==='ascendc' ? `${fmt(visible.length)} 个 ${state.ascendcLayer==='capi'?'AscendC C / SIMT API':'AscendC 基础 C++ API'}` : `${fmt(visible.length)} 个${state.view==='wrappers'?'接口':'名称'} · ${fmt(matches.length)} 条记录`;
  if(depthEnabled())$('#result-count').textContent=`${fmt(visible.length)} 个符号组 · ${fmt(matches.length)} 条记录`;
  const ptxScopeLabel = state.backend === 'ptx' && state.family ? (ptxSubcategories.get(state.family)?.title_zh || ptxCategories.get(state.family)?.title_zh || ptxDomains.get(state.family)?.title || state.family) : ccecFamilyLabel(state.family);
  $('#progress-scope').textContent = ptxScopeLabel || (state.query || state.group || state.file || state.architecture || state.deprecation || state.proof || state.support ? '筛选结果' : state.view === 'definitions' ? '配套定义' : '全部指令');
  setProgressActive(visible.length > 0);
  $('#empty').hidden = visible.length !== 0;
  renderTransferEmpty();
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
    const r0 = g.items[0];
    const selected = g.items.some(r => r.id === state.selected);
    const classification = r0.knowledge ? g.family : state.view === 'definitions' ? kinds[r0.kind] : r0.transfer?.label || g.family;
    const secondColumn = r0.llvm ? [...new Set(g.items.flatMap(r=>r.sourceKeys))].map(k=>llvmSourceLabels[k]).join(' · ') : classification;
    const qualified = [r0.namespace,g.name].filter(Boolean).join('::');
    const col3 = r0.knowledge?.concrete_form ? '形式支持待核对' : g.symbolGroup && g.items.length>1 ? '逐条查看' : r0.nvvm ? '文档符号' : r0.llvm ? llvmIdentities[r0.llvm.identity_status] : state.backend === 'ptx' ? supportLabels[r0.knowledge.target_assessments?.[state.ptxTarget]?.support || 'unknown'] : state.backend === 'cce-dialect' ? (r0.dialectOp ? (loweringModeLabels[r0.dialectOp.lowering_mode] || r0.group) : r0.group) : a5GroupLabel(g.items);
    const col4 = g.symbolGroup ? g.items.length : r0.llvm ? (r0.llvm.form_ids.length || '—') : state.backend === 'ptx' ? esc(r0.knowledge.section_number || '—') : r0.dialectOp ? (r0.dialectOp.intrinsic_ids?.length || '—') : r0.dialectIntr ? (r0.dialectIntr.mappings?.length || 1) : r0.ascendc ? (r0.ascendc.overload_count || 1) : r0.op ? (scopedA5Op(r0.op).forms.length || '—') : g.items.length;
    return `<tr class="${selected ? 'selected' : ''}"><td><button class="row-button" title="${esc(qualified)}" data-id="${r0.id}" ${selected ? 'aria-current="true"' : ''}><span class="row-name">${esc(g.name)}${directEntryIDs.has(r0.id)?' · 直连':''}</span></button></td>${r0.dialectIntr ? dialectSourceCell(r0) : ''}<td title="${esc(secondColumn)}">${esc(secondColumn)}</td><td>${esc(r0.llvm ? classification : col3)}</td><td class="number">${col4}</td></tr>`;
  }).join('');
}
function updateLoadStatus() {
  $('#load-status').hidden = visible.length === 0;
  $('#load-status').textContent = state.limit < visible.length ? `已显示 ${fmt(state.limit)} / ${fmt(visible.length)} 个名称 · 向下滚动继续加载` : `已显示全部 ${fmt(visible.length)} 个名称`;
}
function renderRows() {
  $('#rows').innerHTML = rowHTML(visible.slice(0,state.limit));
  updateLoadStatus();queueProgress();
}
function appendThrough(limit) {
  const start = state.limit;
  state.limit = Math.min(visible.length,Math.max(start,limit));
  if (state.limit > start) $('#rows').insertAdjacentHTML('beforeend',rowHTML(visible.slice(start,state.limit)));
  updateLoadStatus();queueProgress();
}
function markSelectedRow() {
  const group = visible.find(g => g.items.some(r => r.id === state.selected));
  $('#rows').querySelectorAll('.row-button').forEach(button => {
    const selected = button.dataset.id === group?.items[0].id;
    button.closest('tr').classList.toggle('selected',selected);
    if (selected) button.setAttribute('aria-current','true');else button.removeAttribute('aria-current');
  });
  queueProgress();
}
function queueMore() {
  if (loadScheduled) return;
  loadScheduled = true;
  requestAnimationFrame(() => {
    loadScheduled = false;
    if (state.home || document.body.classList.contains('data-loading') || isPtxReading() || state.view === 'report' || readingDetail || state.limit >= visible.length) return;
    const bounds = $('#load-status').getBoundingClientRect();
    if (bounds.top > innerHeight + 300 || bounds.bottom < 0) return;
    appendThrough(state.limit + BATCH_SIZE);
    queueMore();
  });
}
function setProgressActive(active) {
  $('#scroll-navigation').hidden = !active;
  $('.workspace').classList.toggle('progress-active',active);
  updatePanelWidths();queueProgress();
}
function rowMetrics() {
  const row = $('#rows tr');
  if (!row) return null;
  const bounds = row.getBoundingClientRect();
  const top = $('.topbar').getBoundingClientRect().height + $('.list-summary').offsetHeight + $('.interface-table thead').offsetHeight;
  const capacity = Math.max(1,Math.floor((innerHeight - top) / bounds.height));
  return {rowTop:bounds.top,rowHeight:bounds.height,top,capacity,maxOffset:Math.max(0,visible.length - capacity)};
}
function updateProgress() {
  if (state.home || document.body.classList.contains('data-loading') || isPtxReading() || state.view === 'report') return;
  const m = rowMetrics(), total = visible.length;
  if (!m || !total) {$('#viewport-range').textContent = '0–0 / 0';return;}
  const clampIndex = index => Math.max(0,Math.min(state.limit - 1,index));
  let start = clampIndex(Math.floor((m.top - m.rowTop) / m.rowHeight));
  let end = Math.max(start + 1,Math.min(state.limit,Math.ceil((innerHeight - m.rowTop) / m.rowHeight)));
  const detailBounds = $('#detail').getBoundingClientRect();
  const inDetail = readingDetail && detailBounds.top < innerHeight && detailBounds.bottom > m.top;
  if (inDetail) {
    start = Math.max(0,visible.findIndex(g => g.items.some(r => r.id === state.selected)));
    end = start + 1;
  }
  const label = inDetail ? `详情 ${start + 1} / ${total}` : `${start + 1}–${end} / ${total}`;
  $('#viewport-range').textContent = label;
  $('#viewport-range').setAttribute('aria-label',inDetail ? `当前详情为筛选结果第 ${start + 1} 个，共 ${total} 个名称组` : `当前可见第 ${start + 1} 至 ${end} 个，共 ${total} 个名称组`);
  const rail = $('#scroll-rail'), trackHeight = rail.clientHeight;
  const thumbHeight = Math.min(trackHeight,Math.max(28,trackHeight * Math.min(total,m.capacity) / total));
  const thumbTop = m.maxOffset ? Math.min(1,start / m.maxOffset) * (trackHeight - thumbHeight) : 0;
  $('#scroll-thumb').style.height = thumbHeight + 'px';
  $('#scroll-thumb').style.transform = `translateY(${thumbTop}px)`;
  $('#rail-position').style.top = Math.min(trackHeight - 22,thumbTop + thumbHeight / 2) + 'px';
  $('#rail-position').textContent = label;
  rail.setAttribute('aria-valuemax',m.maxOffset + 1);
  rail.setAttribute('aria-valuenow',Math.min(start,m.maxOffset) + 1);
  rail.setAttribute('aria-valuetext',label + ' 个名称组');
}
function queueProgress() {
  if (progressScheduled) return;
  progressScheduled = true;
  requestAnimationFrame(() => {progressScheduled=false;updateProgress();});
}
function jumpToOffset(offset) {
  const m = rowMetrics();
  if (!m || isPtxReading() || state.view === 'report') return;
  readingDetail = false;
  const index = Math.max(0,Math.min(m.maxOffset,Math.round(offset)));
  appendThrough(Math.ceil((index + m.capacity + 1) / BATCH_SIZE) * BATCH_SIZE);
  window.scrollTo(0,index ? m.rowTop + scrollY + index * m.rowHeight - m.top : 0);
  queueProgress();queueMore();
}
function initScrollNavigation() {
  const rail = $('#scroll-rail');
  let grabOffset = null;
  const seek = clientY => {
    const m = rowMetrics();if (!m) return;
    const track = rail.getBoundingClientRect(), thumbHeight = $('#scroll-thumb').getBoundingClientRect().height;
    const fraction = (clientY - track.top - grabOffset) / Math.max(1,track.height - thumbHeight);
    jumpToOffset(Math.max(0,Math.min(1,fraction)) * m.maxOffset);
  };
  rail.onpointerdown = event => {
    if (event.button !== 0) return;
    event.preventDefault();updateProgress();rail.focus({preventScroll:true});
    const thumb = $('#scroll-thumb').getBoundingClientRect();
    grabOffset = event.target === $('#scroll-thumb') ? event.clientY - thumb.top : thumb.height / 2;
    rail.setPointerCapture(event.pointerId);rail.classList.add('dragging');seek(event.clientY);
  };
  rail.onpointermove = event => {if (grabOffset !== null) seek(event.clientY);};
  rail.onpointerup = rail.onpointercancel = rail.onlostpointercapture = () => {grabOffset=null;rail.classList.remove('dragging');};
  rail.onkeydown = event => {
    const m = rowMetrics();if (!m) return;
    const steps = {ArrowUp:-1,ArrowLeft:-1,ArrowDown:1,ArrowRight:1,PageUp:-m.capacity,PageDown:m.capacity};
    if (!(event.key in steps) && !['Home','End'].includes(event.key)) return;
    event.preventDefault();
    const current = Number(rail.getAttribute('aria-valuenow')) - 1;
    jumpToOffset(event.key === 'Home' ? 0 : event.key === 'End' ? m.maxOffset : current + steps[event.key]);
  };
  $('#jump-start').onclick = () => jumpToOffset(0);
  $('#jump-end').onclick = () => jumpToOffset(visible.length);
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
  renderDetailBody();symbolMembers();
}
function renderDetailBody() {
  const r = byId.get(state.selected), pane = $('#detail');
  if (!r) {pane.innerHTML = '<div class="empty detail-empty"><h2>选择条目，阅读详情</h2><p>调整左侧筛选后即可查看接口与来源。</p></div>';return;}
  if(r.nvvm){renderNVVMDetail(r);return;}
  if (r.llvm) {renderLLVMDetail(r);return;}
  if (r.ascendc) {renderAscendcDetail(r);return;}
  if (r.dialectOp || r.dialectIntr) {renderDialectDetail(r);return;}
  if (r.op) {renderOpDetail(r);return;}
  if (r.knowledge) {renderKnowledgeDetail(r);return;}
  const current = visible.find(g => g.items.some(x => x.id === r.id));
  const options = current?.items || [r];
  const countLabel = isInterface(r) ? `${options.length} 条声明记录` : `${options.length} 条定义`;
  pane.innerHTML = `<div class="detail-heading"><h2>${esc(r.name)}</h2><div class="detail-domain"><span>${esc(r.group)}</span><span>${esc(r.family === '配套定义' ? kinds[r.kind] : r.family)}</span></div>${r.namespace ? `<div class="qualified">${esc(r.namespace)}::${esc(r.name)}</div>` : ''}<div class="detail-actions"><button id="back-to-list" class="mobile-return text-button">返回列表</button><button id="copy-signature" class="quiet-button">复制签名</button><button id="copy-link" class="quiet-button">复制链接</button><span class="detail-status">头文件声明</span></div></div><div class="detail-tabs" role="tablist" aria-label="详情内容">${[['definition','接口定义'],['source','来源证据'],['experiments','实验记录']].map(([id,title]) => `<button id="tab-${id}" role="tab" data-tab="${id}" aria-controls="detail-content" tabindex="${state.tab === id ? 0 : -1}" aria-selected="${state.tab === id}">${title}</button>`).join('')}</div><div class="detail-body" id="detail-content" role="tabpanel" aria-labelledby="tab-${state.tab}"><label class="overloads">${esc(countLabel)}<select id="overload" aria-label="选择来源声明">${options.map((x,i) => `<option value="${x.id}" ${x.id === r.id ? 'selected' : ''}>${i + 1}. ${esc(x.return_type || kinds[x.kind])} · ${esc(x.parameters?.join(', ') || x.source.file)}</option>`).join('')}</select></label>${state.tab === 'source' ? sourceContent(r) : state.tab === 'experiments' ? experimentsContent() : definitionContent(r)}</div>`;
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
    Object.assign(state,{view:recordView(target),selected:target.id,query:'',family:'',group:'',file:'',tab:'definition'});
    render(!mobile.matches);
    if (mobile.matches) {readingDetail=true;$('#detail').scrollIntoView({block:'start'});}
    $('#detail').focus({preventScroll:true});
  });
  wireOpLinks(pane);
  if(state.tab==='definition')renderObservedCalls(r);
  pane.querySelector('[role="tablist"]').onkeydown = e => {
    if (!['ArrowLeft','ArrowRight','Home','End'].includes(e.key)) return;
    e.preventDefault();const tabs = ['definition','source','experiments'];let index = tabs.indexOf(state.tab);
    index = e.key === 'Home' ? 0 : e.key === 'End' ? 2 : (index + (e.key === 'ArrowRight' ? 1 : 2)) % 3;
    state.tab = tabs[index];renderDetail();$('#tab-' + state.tab).focus();
  };
}
function compatibilityContent(r) {
  const labels = {matches:'条件符合',excluded:'条件排除',unknown:'待确认'};
  const target = data.compatibility.chip_mappings.find(t => t.chip === state.chip);
  const result = state.architecture ? `${state.architecture}：${labels[r.compatibility.profiles[state.architecture]] || '待确认'}` : '未选择架构条件';
  return `${staticContent(r)}<h3>架构与弃用</h3>${target ? `<p>${esc(target.chip)} · ${esc(target.aic_version)} · ${esc([...new Set(Object.values(target.cores))].join(' / '))}</p><details><summary>芯片映射来源（安装目录，未核验原包）</summary><p class="condition">${esc(target.source.file)} [version]</p><p class="condition">SHA-256 ${esc(target.source.sha256)}</p></details>` : ''}<p class="condition">${esc(result)}</p><p>${r.deprecation.status === 'conditional' ? '条件性弃用标记（需核对宏分支）' : r.deprecation.status === 'marked' ? '有弃用标记（本版本）' : '未检出弃用标记（不代表未弃用）'} · 编译未验证 · 运行未验证</p>${r.deprecation.evidence ? `<details><summary>弃用证据</summary><pre><code>${esc(r.deprecation.evidence)}</code></pre>${r.deprecation.macro_definitions.map(m => `<p>${esc(sourceLabel(m.source))}</p><pre><code>${esc(m.signature)}</code></pre>${m.conditions.map(c => `<div class="condition">${esc(c)}</div>`).join('')}`).join('')}</details>` : ''}<p>仅核对声明条件；包含路径与核目标的宏环境尚未验证。首次弃用版本及替代接口待确认。</p>`;
}
function definitionContent(r) {
  const conds = visibleConditions(r);
  const calls = (r.calls || []).map(name => records.find(x => x.name === name && x.namespace?.endsWith('__cce_scalar'))).filter(Boolean);
  const types = [...new Set((r.parameters || []).join(' ').match(/[A-Za-z_]\w*/g) || [])].map(name => records.find(x => x.kind === 'type' && x.name === name)).filter(Boolean).slice(0,12);
  const links = (items) => items.map(x => `<button class="related-link" data-ref="${x.id}"><code>${esc(x.namespace ? x.namespace + '::' + x.name : x.name)}</code></button>`).join('');
  return `<h3>${r.kind === 'interface' ? '接口签名' : '声明内容'}</h3><pre class="signature"><code>${esc(formatSignature(r))}</code></pre><dl class="detail-meta"><dt>接口形式</dt><dd>${esc(kinds[r.kind])}${r.generated ? ' · 宏展开生成' : ''}</dd><dt>来源位置</dt><dd class="source-ref">${esc(sourceLabel(r.source))}</dd>${r.return_type ? `<dt>返回类型</dt><dd><code>${esc(r.return_type)}</code></dd>` : ''}</dl>${layerContent(r)}${compatibilityContent(r)}${r.parameters?.length ? `<h3>参数声明</h3><table class="parameter-table"><thead><tr><th>序号</th><th>类型 / 名称 / 默认值</th></tr></thead><tbody>${r.parameters.map((p,i) => `<tr><td>${i + 1}</td><td><code>${esc(p)}</code></td></tr>`).join('')}</tbody></table>` : ''}<h3>可见条件</h3>${conds.length ? conds.map(c => `<div class="condition">${esc(c)}</div>`).join('') : '<p>声明处未发现额外条件。调用入口仍可能附加条件，不能据此推断全架构支持。</p>'}${types.length ? '<h3>相关类型</h3>' + links(types) : ''}${calls.length ? '<h3>下层接口调用</h3>' + links(calls) : ''}<h3>关联 builtin</h3>${r.builtins.length ? r.builtins.map(b => `<div class="condition">${esc(b)}</div>`).join('') : '<p>本条声明未提取到直接 builtin 引用。</p>'}<div class="callout">${r.parameters?.includes('...') ? '原始头文件以可变参数声明此接口，精确参数约束尚待核对。' : '参数单位、合法值和设备支持范围尚未逐项验证。'} 指令族按名称规则归类，仅用于导航。</div>`;
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
function renderReport() {if(state.backend==='nvvm')$('#report').innerHTML='<h2>NVVM IR 来源与覆盖</h2><pre>'+esc(JSON.stringify({version:knowledgeData.nvvm.version,source:knowledgeData.nvvm.source,records:nvvmRecords.length,limitations:knowledgeData.nvvm.limitations},null,2))+'</pre>';else if(state.backend==='llvm')renderLLVMReport();else if(state.backend==='ccec')renderA5Report();else if(state.backend==='ascendc')renderAscendcReport();else if(state.backend==='cce-dialect')renderDialectReport();else renderKnowledgeReport();}
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
    const sidebar = clamp(preferences.sidebar ?? (state.backend === 'ptx' ? 210 : 136),128,Math.min(360,width - 26 - 260 - 300));
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
  updatePanelWidths = apply;
  new ResizeObserver(() => {root.style.setProperty('--header-height',$('.topbar').getBoundingClientRect().height + 'px');queueProgress();}).observe($('.topbar'));
  window.addEventListener('resize',() => {apply();queueMore();queueProgress();});
  apply();
}
function reset() {state.llvmScope='a5-sources';state.llvmSource='';state.llvmEvidence='';if(['ccec','ascendc','cce-dialect','llvm','nvvm'].includes(state.backend))state.view=activeLayerView();state.includeUnknown=false;Object.assign(state,{support:'',proof:'',family:'',query:'',group:'',file:'',chip:'',architecture:'',availability:'',deprecation:'',selected:'',tab:'definition'});render();}
function switchView(view) {Object.assign(state,{support:'',proof:'',view,family:'',query:'',group:'',file:'',chip:'',architecture:'',availability:'',deprecation:'',selected:'',tab:'definition'});render();}

$('#expand-lookup').onclick=()=>{document.body.classList.remove('lookup-collapsed');$('#detail').focus({preventScroll:true});};
$('.skip-link').onclick=e=>{e.preventDefault();const target=state.home?(!$('#insights').hidden?$('#insights-content'):$('#home-content')):$('#main');target.focus();target.scrollIntoView({block:'start'});};
$('#download').onclick = download;
$('#backend').onchange=e=>{
  const val=e.target.value;
  const backend=val.startsWith('ccec')?'ccec':val.startsWith('ascendc')?'ascendc':val.startsWith('cce-dialect')?'cce-dialect':val;
  navigateWithData(backend,()=>{
  state.home=false;
  if(val==='nvvm'){state.backend='nvvm';}
  else if(val==='llvm'){state.backend='llvm';}
  else if(val==='ptx'){state.backend='ptx';}
  else if(val==='ascendc' || val==='ascendc-capi'){state.backend='ascendc';state.ascendcLayer=val==='ascendc-capi'?'capi':'basic';}
  else if(val==='cce-dialect' || val==='cce-dialect-intrinsics'){state.backend='cce-dialect';state.dialectLayer=val==='cce-dialect-intrinsics'?'intrinsics':'ops';}
  else{state.backend='ccec';state.ccecLayer=val==='ccec-intrinsics'?'interfaces':'wrappers';}
  state.symbolDepth=0;state.includeUnknown=false;configureBackend();state.view=state.backend==='ptx'?'interfaces':activeLayerView();state.ptxTarget='sm_103a';reset();
  });
};
$('#llvm-scope').onchange=e=>{state.llvmScope=e.target.value;state.selected='';render();};
$('#llvm-evidence').onchange=e=>{state.llvmEvidence=e.target.value;state.selected='';render();};
$('#include-unknown').onchange=e=>{state.includeUnknown=e.target.checked;state.selected='';render();};
$('#coverage').onclick=()=>switchView(state.view==='report'?activeLayerView():'report');
$('#ptx-target').onchange=e=>{state.ptxTarget=e.target.value;render();};
$('#ptx-support').onchange = e => {state.support=e.target.value;state.selected='';render();};
$('#search').addEventListener('input',e => {state.query=e.target.value;state.selected='';if(['ccec','ascendc','cce-dialect','llvm','nvvm'].includes(state.backend))state.view=activeLayerView();if(state.backend==='ptx' && isPtxReading())state.view=state.query?'search':'overview';render();});
for(const key of ['group','file'])$('#'+key).onchange=e=>{state[key]=e.target.value;state.selected='';render();};
$('#reset').onclick = reset;$('#empty-reset').onclick = reset;
$('#mobile-view').onchange = e => switchView(e.target.value);
$('#mobile-family').onchange = e => {if(['ccec','ascendc','cce-dialect','llvm','nvvm'].includes(state.backend))state.view=activeLayerView();state.family=e.target.value;state.selected='';render();};
$('.views').onclick = e => {const b=e.target.closest('[data-view]');if(b) switchView(b.dataset.view);};
$('#families').onclick = e => {const b=e.target.closest('[data-family]');if(b){if(['ccec','ascendc','cce-dialect','llvm','nvvm'].includes(state.backend))state.view=activeLayerView();state.family=b.dataset.family;state.selected='';render();}};
$('#rows').addEventListener('click',e => {
  const button = e.target.closest('[data-id]');if (!button) return;
  if(state.backend==='ptx' && !depthEnabled()){openPtxEntry(button.dataset.id);return;}
  state.selected=button.dataset.id;state.tab='definition';saveHash(false);markSelectedRow();renderDetail();
  $('#detail').scrollTop=0;
  if (mobile.matches) {readingDetail=true;$('#detail').scrollIntoView({block:'start'});$('#detail').focus({preventScroll:true});}
  else $('#detail').focus({preventScroll:true});
});
document.addEventListener('keydown',e => {
  if (!state.home && e.key === '/' && !['INPUT','SELECT','TEXTAREA'].includes(document.activeElement.tagName) && state.view !== 'report') {e.preventDefault();$('#search').focus();}
  if (e.key === 'Escape' && document.activeElement === $('#search')) {reset();$('#search').focus();}
});
window.addEventListener('hashchange',() => navigateHash(true));
window.addEventListener('scroll',queueMore,{passive:true});
window.addEventListener('scroll',queueProgress,{passive:true});
if ('IntersectionObserver' in window) new IntersectionObserver(queueMore,{rootMargin:'300px 0px'}).observe($('#load-status'));
initPanelResize();
initScrollNavigation();
navigateHash(Boolean(new URLSearchParams(location.hash.slice(1)).get('r')));

$('#symbol-depth').oninput=e=>{state.symbolDepth=Number(e.target.value);render(true);};
