'use strict';
const knowledgeData = JSON.parse(document.querySelector('#knowledge-data').textContent);
const supportLabels = {documented_supported:'文档支持',documented_not_supported:'文档排除',partial:'部分形式',unknown:'待确认'};
const ptxKinds = {instruction:'指令',instruction_topic:'指令章节',execution_model:'执行模型',state_space:'状态空间',directive:'伪指令',directive_topic:'伪指令章节',special_register:'特殊寄存器',special_register_topic:'寄存器章节',introduction:'概述',release_note:'版本历史',notice:'声明',other:'其他章节',note:'深度笔记'};
let ptxSections,ptxTaxonomy,ptxDomains,ptxCategories,ptxSubcategories,knowledgeRecords;
function refreshKnowledge() {
  ptxSections = new Map(knowledgeData.ptx.records.map(r => [r.anchor,r]));
  ptxTaxonomy = knowledgeData.ptx.taxonomy || {domains:[],categories:[],instructions:{}};
  ptxDomains = new Map(ptxTaxonomy.domains.map(d => [d.id,d]));
  ptxCategories = new Map(ptxTaxonomy.categories.map(c => [c.id,c]));
  ptxSubcategories = new Map(ptxTaxonomy.categories.flatMap(c => (c.subcategories || []).map(s => [s.id,{...s,category:c}])));
  knowledgeRecords = [
    ...knowledgeData.ptx.records.map(k => wrapKnowledge(k,'ptx')),
    ...knowledgeData.ptx.notes.map(k => wrapKnowledge({...k,kind:'lesson'},'ptx')),
    ...knowledgeData.ccec.topics.map(k => wrapKnowledge({...k,kind:'note'},'ccec'))
  ];
}
refreshKnowledge();
function wrapKnowledge(k,backend) {
  const tax = k.taxonomy;
  const cat = tax && ptxCategories.get(tax.category);
  const sub = tax && tax.subcategory && ptxSubcategories.get(tax.subcategory);
  return {id:k.entry_id || k.id,backend,knowledge:k,kind:k.kind,
    name:k.mnemonics?.join(' / ') || k.title,group:backend === 'ptx' ? ptxKinds[k.kind] || k.kind : '知识主题',
    family:backend === 'ptx' ? (k.kind === 'instruction' ? (sub?.title_zh || cat?.title_zh || '指令') : ptxKinds[k.kind] || k.kind) : '深度笔记',
    signature:'',namespace:'',builtins:[],conditions:[],source:{file:backend === 'ptx' ? 'PTX ISA 9.4' : 'CANN 头文件'}};
}
function recordView(r) {
  if(r.backend==='llvm')return 'llvm';
  if (r.backend === 'ascendc') return r.ascendcLayer === 'capi' ? 'capi' : 'basic';
  if (r.backend === 'cce-dialect') return r.dialectLayer === 'intrinsics' ? 'dialect_intrinsics' : 'dialect_ops';
  if (r.knowledge) {
    if(r.kind === 'lesson') return r.knowledge.chapter;
    if(r.kind === 'note') return 'topics';
    if(r.kind === 'instruction') return 'interfaces';
    if(['execution_model','state_space'].includes(r.kind)) return 'execution';
    if(r.kind === 'directive') return 'directives';
    if(r.kind === 'special_register') return 'registers';
    return 'all';
  }
  if(r.op)return 'interfaces';
  if(ccecIsInterface(r))return 'wrappers';
  if(isInterface(r)){const layer=opModel?.record_layers[r.id]?.layer;return layer==='wrapper'?'wrappers':layer==='unresolved_entry'?'unresolved':'declarations';}
  return 'definitions';
}
function viewLabels() {
  if(state.backend==='llvm')return {llvm:'LLVM IR 目标核心',report:'来源与覆盖'};
  if (state.backend === 'ascendc') return {basic:'AscendC 高层 API',capi:'AscendC C / SIMT API',report:'说明 / 覆盖'};
  if (state.backend === 'cce-dialect') return {dialect_ops:'CCE Dialect 语义 Op',dialect_intrinsics:'CCE Dialect → LLVM Intrinsics',report:'说明 / 覆盖'};
  return state.backend === 'ptx' ? {...Object.fromEntries(knowledgeData.ptx.learning.chapters.map(c=>[c.id,c.title])), interfaces:'指令速查', all:'官方手册目录', report:'来源与覆盖', instruction:'指令阅读', search:'搜索结果'} : {interfaces:'CCEC Builtins',declarations:'入口声明',wrappers:'CCEC 编程接口',records:'原始记录',unresolved:'待解析入口',definitions:'配套定义',topics:'知识主题',report:'说明 / 覆盖',references:'来源详情'};
}
function configureBackend() {
  const ptx = state.backend === 'ptx';
  const isLLVM=state.backend==='llvm';
  const isAscendc = state.backend === 'ascendc';
  const isDialect = state.backend === 'cce-dialect';
  $('#page-title').hidden=!ptx;
  records = isLLVM ? llvmRecords : ptx ? knowledgeRecords.filter(r => r.backend === 'ptx') : isAscendc ? ascendcRecords : isDialect ? dialectRecords : [...opRecords,...data.records,...knowledgeRecords.filter(r => r.backend === 'ccec')];
  document.body.classList.toggle('ptx-mode',ptx);
  document.body.classList.toggle('llvm-mode',isLLVM);
  const labels = viewLabels();
  $('.views').innerHTML = Object.entries(labels).map(([key,label]) => {
    const count = key === 'report' ? '' : fmt(makeGroups(records.filter(r => key==='records'?isInterface(r):key === 'all' ? !['note','lesson'].includes(r.kind) : recordView(r) === key)).length);
    return `<button data-view="${key}" class="view">${esc(label)} <span id="nav-${key}">${count}</span></button>`;
  }).join('');
  $('.views').hidden=!ptx;
  if(ptx) renderPtxNavigation();
  $('#mobile-view').innerHTML = Object.entries(labels).map(([key,label]) => `<option value="${key}">${esc(label)}</option>`).join('');
  if (ptx) {
    $('#family-section h2').textContent = '指令分类探索';
    $('#family-section h2').title = '按能力域、PTX 9.7 类别及功能子类分层探索';
    $('#families').innerHTML = `<button class="family" data-family="">全部指令<span></span></button>` + ptxTaxonomy.domains.map(d => {
      const cats = d.categories.map(cid => ptxCategories.get(cid)).filter(Boolean);
      const catsHTML = cats.map(c => {
        const subs = (c.subcategories || []).map(s => `<button class="family family-sub" data-family="${esc(s.id)}" data-parent-cat="${esc(c.id)}" title="${esc(s.summary)}">${esc(s.title_zh)}<span></span></button>`).join('');
        return `<button class="family family-cat" data-family="${esc(c.id)}" title="${esc(c.title_en)}">${esc(c.title_zh)}<span></span></button>${subs ? `<div class="family-subs" data-cat-subs="${esc(c.id)}">${subs}</div>` : ''}`;
      }).join('');
      return `<div class="family-domain"><button class="family family-dom" data-family="${esc(d.id)}" title="${esc(d.summary)}">${esc(d.title)}<span></span></button>${catsHTML}</div>`;
    }).join('');
    $('#mobile-family').innerHTML = '<option value="">全部指令 (221)</option>' + ptxTaxonomy.domains.map(d => `<optgroup label="${esc(d.title)}"><option value="${esc(d.id)}">${esc(d.title)}（全部）</option>${d.categories.map(cid => {const c=ptxCategories.get(cid);return c?`<option value="${esc(c.id)}">${esc(c.id)} ${esc(c.title_zh)}</option>`+(c.subcategories||[]).map(s=>`<option value="${esc(s.id)}">　└ ${esc(s.title_zh)}</option>`).join(''):'';}).join('')}</optgroup>`).join('');
  } else {
    $('#family-section h2').textContent = '指令族';
    $('#family-section h2').title = '按接口名称关键词归类，仅用于导航';
    $('#families').innerHTML = [['','全部指令'],...families.map(f=>[f,f])].map(([key,label])=>`<button class="family" data-family="${esc(key)}">${esc(label)}<span></span></button>`).join('');
    $('#mobile-family').innerHTML = '<option value="">全部指令</option>' + families.map(f=>`<option>${esc(f)}</option>`).join('');
  }
  const activePool = isLLVM || isAscendc || isDialect ? records : data.records;
  const activeFiles = isLLVM ? Object.values(llvmData.sources).map(s=>s.path).sort() : isAscendc ? Object.keys(ascendcData.files || {}).sort() : isDialect ? Object.keys(dialectData.source?.files || {}).sort() : data.files.map(f => f.path);
  $('#group').innerHTML = '<option value="">全部接口域</option>' + [...new Set(activePool.map(r => r.group))].sort().map(g => `<option>${esc(g)}</option>`).join('');
  $('#file').innerHTML = '<option value="">全部源文件</option>' + activeFiles.map(f => `<option>${esc(f)}</option>`).join('');
  $('#version').textContent = ptx ? 'PTX ISA 9.4' : isDialect ? `CCEDialect ${dialectData.version || ''}` : data.version;
  $('#footer-source').textContent = isLLVM ? `${Object.keys(llvmData.sources).length} 个版本化来源 · CANN ${data.version} · LLVM IR` : ptx ? 'PTX ISA 9.4 · CUDA 文档归档 13.4.3 · NVIDIA B300' : isDialect ? `${activeFiles.length} 个 TableGen/文档源文件 · CCEDialect ${dialectData.version || ''} · dav-351x` : isAscendc ? `${activeFiles.length} 个 AscendC 头文件 · CANN ${data.version} · 950 / dav_3510` : `${data.files.length} 个源文件 · CANN ${data.version}`;
  $('#search').placeholder = isLLVM ? '搜索 LLVM 名称、类型…' : ptx ? '搜索指令、章节、目标条件…' : isDialect ? '搜索 cce.* Op、llvm.hivm.*、语法…' : '搜索名称、类型、builtin、条件…';
  $('#search').setAttribute('aria-label',ptx ? '搜索 PTX 指令与章节' : '搜索接口或配套定义');
  for(const node of [$('#group').closest('label'),$('#file').closest('label')]) node.hidden=ptx;
  $('#fixed-chip').hidden=ptx;$('#unknown-filter').hidden=ptx || isDialect;$('#unknown-label').textContent=isLLVM?'含字符串候选':'显示待确认';document.querySelectorAll('.llvm-filter').forEach(n=>n.hidden=!isLLVM);$('#coverage').hidden=ptx;
  $('#mobile-view').closest('label').hidden=!ptx;
  document.querySelectorAll('.ptx-filter').forEach(n => n.hidden=!ptx);
  $('.sidebar-note').innerHTML = isLLVM ? 'Huawei Ascend · LLVM IR<p>A5 来源 ≠ 950 支持</p><p>跨架构注册表独立保留</p>' : ptx ? '官方文档索引<p>NVIDIA B300 · CC 10.3</p><p>编译与运行尚未验证</p>' : isDialect ? 'CCE Dialect · dav-351x<p>MLIR ⇄ llvm.hivm.* 双层映射</p>' : 'Huawei Ascend 950 / A5<p>声明条件符合 ≠ 已验证支持</p>';
}
function knowledgeLink(r,label) {
  return `<button class="related-link" data-knowledge-ref="${esc(r.id)}">${esc(label || r.name)}</button>`;
}
function sourceLinks(k,backend) {
  if(backend === 'ccec') return (k.evidence || []).map(e => {
    const r=byId.get(e.record_id);
    return `<div class="evidence-entry">${r ? knowledgeLink(r,r.name) : ''}<p class="source-ref">${esc(e.file)}:${esc(e.line)}</p><p class="condition">SHA-256 ${esc(e.sha256)}</p></div>`;
  }).join('');
  const source=knowledgeData.ptx.source.isa.html;
  const citations=k.citations || [{anchor:k.anchor,section:k.section_number}];
  return citations.map(c => `<p><a href="${esc(source.url + '#' + c.anchor)}" target="_blank" rel="noopener">官方手册 § ${esc(c.section || c.anchor)}</a></p>`).join('') + `<p class="condition">HTML SHA-256 ${esc(source.sha256)}</p>`;
}
function ruleTable(statements,type) {
  if(!statements?.length) return '<p>本章节没有结构化规则；待确认。</p>';
  const relationLabels={all_architectures:'全部架构',minimum_sm:'最低目标',exact_sm:'指定目标',removed:'已移除',introduced:'引入',deprecated:'弃用'};
  return `<div class="rule-list">${statements.map(s => `<div class="rule-entry"><code>${esc(s.subject || '条目基础形式')}</code><p>${esc(relationLabels[s.relation || s.kind] || s.relation || s.kind)} · ${esc(type === 'target' ? s.sm || '见规则' : 'PTX ' + (s.version || '待确认'))}${s.applies ? ' · sm_89：' + esc({yes:'符合',no:'排除',unknown:'待确认'}[s.applies] || s.applies) : ''}</p><details><summary>完整结构化规则</summary><pre><code>${esc(JSON.stringify(s,null,2))}</code></pre></details></div>`).join('')}</div>`;
}
function knowledgeBody(r) {
  const k=r.knowledge;
  if(k.kind === 'note') return `<h3>${r.backend === 'ccec' ? '头文件表面解释' : '文档解读'}</h3><p class="knowledge-prose">${esc(k.body)}</p><h3>尚待确认</h3><ul>${(k.unknowns || []).map(x => `<li>${esc(x)}</li>`).join('')}</ul>${k.missing_seeds?.length ? `<p>未找到的种子：${esc(k.missing_seeds.join(', '))}</p>` : ''}<h3>引用与关联</h3>${r.backend === 'ptx' ? (k.citations || []).map(c => {const target=records.find(x=>x.knowledge?.anchor===c.anchor);return target ? knowledgeLink(target,`§ ${c.section} ${target.name}`) : '';}).join('') : (k.record_ids || []).map(id=>byId.get(id)).filter(Boolean).map(x=>knowledgeLink(x)).join('')}`;
  const notes=records.filter(x=>x.kind === 'note' && x.knowledge.citations?.some(c=>c.anchor===k.anchor));
  const children=records.filter(x=>x.knowledge?.parent_anchor === k.anchor);
  const parent=records.find(x=>x.knowledge?.anchor === k.parent_anchor);
  return `<dl class="detail-meta"><dt>章节</dt><dd>${esc(k.section_number)}</dd><dt>类别</dt><dd>${esc(ptxKinds[k.kind])}</dd><dt>sm_89 文档</dt><dd>${esc(supportLabels[k.sm_89?.support || 'unknown'])}</dd></dl><div class="callout">文档条件不等于编译或运行验证。部分形式需逐项核对目标规则。语法与手册正文未收录，原文可通过来源链接查看（需联网）。</div>${k.target_isa ? '<h3>目标架构条件</h3>' + ruleTable(k.target_isa.statements,'target') : ''}${k.ptx_isa ? '<h3>PTX 版本与生命周期</h3>' + ruleTable(k.ptx_isa.statements,'version') : ''}${notes.length ? '<h3>相关深度笔记</h3>' + notes.map(n=>knowledgeLink(n)).join('') : ''}${parent ? '<h3>上级章节</h3>' + knowledgeLink(parent) : ''}${children.length ? '<h3>下级章节</h3>' + children.map(c=>knowledgeLink(c)).join('') : ''}<h3>官方原文</h3>${sourceLinks(k,'ptx')}`;
}
function renderKnowledgeDetail(r) {
  if(r.backend === 'ptx') {renderPtxLookup(r);return;}
  const pane=$('#detail'),k=r.knowledge;
  const tabs=[['definition',k.kind==='note'?'主题解读':'条件与关联'],['source','来源证据'],['experiments','验证状态']];
  const body=state.tab === 'source' ? `<h3>来源与身份</h3><p class="condition">${esc(r.id)}</p>${sourceLinks(k,r.backend)}<details><summary>完整索引记录</summary><pre><code>${esc(JSON.stringify(k,null,2))}</code></pre></details>` : state.tab === 'experiments' ? '<h3>尚未开展设备实验</h3><p>编译验证：未执行</p><p>运行验证：未执行</p><p>性能测量：未执行</p><p>现有依据仅为头文件或官方文档。</p>' + (r.backend === 'ptx' ? '<p>NVIDIA B300 尚未进行设备核验。</p>' : '<p>Huawei Ascend 目标设备尚未进行编译或运行验证。</p>') : knowledgeBody(r);
  pane.innerHTML=`<div class="detail-heading"><h2>${esc(r.name)}</h2><div class="detail-domain">${esc(r.backend.toUpperCase())} · ${esc(r.group)}</div>${k.title !== r.name ? `<p class="knowledge-title">${esc(k.title)}</p>` : ''}<div class="detail-actions"><button id="back-to-list" class="mobile-return text-button">返回列表</button><button id="copy-record" class="quiet-button">复制记录</button><button id="copy-link" class="quiet-button">复制链接</button></div></div><div class="detail-tabs" role="tablist" aria-label="详情内容">${tabs.map(([id,label])=>`<button id="tab-${id}" role="tab" data-tab="${id}" aria-controls="detail-content" tabindex="${state.tab===id?0:-1}" aria-selected="${state.tab===id}">${label}</button>`).join('')}</div><div id="detail-content" class="detail-body" role="tabpanel" aria-labelledby="tab-${state.tab}">${body}</div>`;
  $('#copy-record').onclick=()=>copyText(JSON.stringify(k,null,2));$('#copy-link').onclick=()=>copyText(location.href);
  $('#back-to-list').onclick=()=>{readingDetail=false;const b=$('#rows [aria-current="true"]');b?.scrollIntoView({block:'center'});b?.focus({preventScroll:true});queueMore();queueProgress();};
  pane.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{state.tab=b.dataset.tab;renderDetail();$('#tab-'+state.tab).focus();});
  pane.querySelector('[role="tablist"]').onkeydown=e=>{if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;e.preventDefault();const ids=tabs.map(t=>t[0]);state.tab=ids[e.key==='Home'?0:e.key==='End'?2:(ids.indexOf(state.tab)+(e.key==='ArrowRight'?1:2))%3];renderDetail();$('#tab-'+state.tab).focus();};
  pane.querySelectorAll('[data-knowledge-ref]').forEach(b=>b.onclick=()=>{
    if(state.backend==='ccec'){opNavigate(b.dataset.knowledgeRef);return;}
    const target=byId.get(b.dataset.knowledgeRef);Object.assign(state,{view:recordView(target),selected:target.id,query:'',family:'',group:'',file:'',support:'',chip:'',architecture:'',availability:'',deprecation:'',tab:'definition'});render(!mobile.matches);
    if(mobile.matches){readingDetail=true;pane.scrollIntoView({block:'start'});}pane.focus({preventScroll:true});
  });
}
function renderKnowledgeReport() {
  return renderPtxReport();
}

function downloadKnowledge() {
  const ptx=state.backend==='ptx';
  const items=state.view==='report' ? records : ptx && state.view==='search' ? ptxSearchResults() : isPtxReading() ? [byId.get(state.selected)].filter(Boolean) : filtered();
  const payload={schema_version:'ackb.web-export.v1',backend:state.backend,version:ptx?'9.4':data.version,selection:{...state},source:ptx?{isa:knowledgeData.ptx.source.isa,device:learning.sources.device}:{catalog_sha256:knowledgeData.ccec.source_catalog_sha256},scan:ptx?{sections:knowledgeData.ptx.records.length,instructions:221,lessons:learning.lessons.length}:knowledgeData.ccec.coverage, target:ptx?state.ptxTarget:undefined,records:items.map(r=>ptx ? ptxExportRecord(r) : r.knowledge || r),verification:{compile:'unverified',runtime:'unverified',performance:'unverified'}};
  const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=`ackb-${state.backend}-${state.view}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
