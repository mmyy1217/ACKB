'use strict';
const llvmTargetLabels={c310_direct_call:'950 模块有直接调用',c310_declaration:'950 模块仅有声明',a5_name_only:'A5 工具仅有名称线索',cross_arch_registry:'跨架构注册，缺少 950 模块证据',external_only:'仅外部工程映射',reference_model:'普通 IR 参考模型',insufficient:'目标证据不足'};
function llvmCallHTML(op,form) {
  const table=llvmData.a5_call_table;
  const forms=new Set(form?[form.id]:op.form_ids);
  const indices=new Set((table?.forms || []).flatMap((id,i)=>forms.has(id)?[i]:[]));
  const calls=(table?.rows || []).filter(row=>indices.has(row[1]));
  const cores=[...new Set(calls.map(row=>llvmData.sources[table.sources[row[2]]].path.split('/').pop().split('.c310.')[0].replace('meta_op.','')))];
  const entry=row=>`<div class="evidence-entry"><code>${esc(table.callers[row[0]])}</code><p>${esc(llvmData.sources[table.sources[row[2]]]?.path)} · bit ${row[3]}</p><p class="condition">SHA-256 ${esc(llvmData.sources[table.sources[row[2]]]?.sha256)}</p></div>`;
  window.llvmCallPage={calls,entry,limit:25};
  return `<p>950 证据：${esc(llvmTargetLabels[op.static_target?.status] || '未整理')}。${cores.length?'调用所在模块：'+esc(cores.join(' / '))+'；不表示其他核被排除。':''}</p><details><summary>当前形式的模块调用 · ${calls.length}</summary><p>只解析直接调用；间接调用、未知编码及覆盖见说明页。模块中存在调用不代表该函数实际运行。</p><div id="llvm-call-rows">${calls.slice(0,25).map(entry).join('')}</div>${calls.length>25?'<button id="llvm-call-more" class="quiet-button" type="button">继续显示调用位置</button>':''}${!calls.length?'<p>此形式未取得直接调用证据；注册泛型约束不继承具体重载的调用证据。</p>':''}</details>`;
}
function appendLLVMCalls() {
  const p=window.llvmCallPage;
  document.querySelector('#llvm-call-rows').insertAdjacentHTML('beforeend',p.calls.slice(p.limit,p.limit+25).map(p.entry).join(''));
  p.limit+=25;if(p.limit>=p.calls.length)document.querySelector('#llvm-call-more').hidden=true;
}
const llvmDomains = {target_intrinsic:'目标 Intrinsic',standard_intrinsic:'标准 LLVM Intrinsic',ordinary_ir:'普通 LLVM IR'};
const llvmIdentities = {registered:'编译器已注册',declaration_observed:'模块声明',lowering_reference:'外部 lowering 引用',candidate_only:'仅字符串候选',reference_model:'IR 参考模型'};
let llvmData,llvmForms,llvmRecords,llvmRelationsById;
function refreshLLVM() {
  llvmData = knowledgeData.llvm || {ops:[],forms:[],sources:{},relations:[],coverage:{},limitations:[],scans:[]};
  if(llvmData.web_encoding==='columnar-v1' && !Array.isArray(llvmData.ops)) {
    for(const name of ['ops','forms']) {const table=llvmData[name];llvmData[name]=table.rows.map(row=>Object.fromEntries(table.columns.flatMap((key,i)=>row[i]===null?[]:[[key,row[i]]])));}
    for(const o of llvmData.ops)o.presence=Object.fromEntries(o.presence.map((v,i)=>[llvmData.presence_columns[i],['not_scanned','scanned_absent','observed'][v]]));
  }
  llvmForms = new Map(llvmData.forms.map(f=>[f.id,f]));
  llvmRecords = llvmData.ops.map(op=>({id:op.id,name:op.name,backend:'llvm',kind:'llvm',llvm:op,group:llvmDomains[op.domain],family:op.family,namespace:'',signature:op.form_ids.map(id=>llvmForms.get(id)?.signature || '').join(' '),builtins:[],conditions:[],source:{file:llvmData.sources[op.evidence[0]?.source_id]?.path || 'LLVM LangRef',line:op.evidence[0]?.line || 0},files:op.evidence.map(e=>llvmData.sources[e.source_id]?.path).filter(Boolean)}));
  llvmRelationsById = new Map();
  for(const edge of (knowledgeData.navigation?.llvm_relations || llvmData.relations)) for(const id of [edge.from,edge.to]) {if(!llvmRelationsById.has(id))llvmRelationsById.set(id,[]);llvmRelationsById.get(id).push(edge);}
}
refreshLLVM();
function llvmMatches(r) {
  const o=r.llvm;
  return (state.llvmScope==='all' || (state.llvmScope==='a5-evidence' ? o.static_target?.package_evidence : o.a5_source_lead || o.domain==='ordinary_ir')) && (state.includeUnknown || o.identity_status!=='candidate_only') && (!state.llvmEvidence || (state.llvmEvidence==='bitcode_call' ? o.static_target?.call_count>0 : o.evidence.some(e=>e.kind===state.llvmEvidence)));
}
function llvmRelationHTML(id) {
  const edges=llvmRelationsById.get(id) || [];
  if(!edges.length)return '<p>当前索引没有上游映射；这不等于源码入口不存在。</p>';
  const label={exact_llvm_symbol:'同名 LLVM 符号',dialect_mapping:'Dialect 映射',naming_candidate:'名称候选，未经 lowering 核验',overload_name_candidate:'重载名称候选'};
  return edges.map(e=>{const target=e.from===id?e.to:e.from;return `<div class="evidence-entry">${opLink(target)}<small>${esc(label[e.kind] || e.kind)}</small>${e.via?`<p>经 ${opLink(e.via)}</p>`:''}</div>`;}).join('');
}
function appendLLVMRelations(pane,id) {
  pane.querySelector('.llvm-links')?.remove();
  if(!(llvmRelationsById.get(id)||[]).length)return;
  const body=pane.querySelector('.detail-body') || pane;
  body.insertAdjacentHTML('beforeend',`<details class="llvm-links"><summary>LLVM IR 核心关联 · ${(llvmRelationsById.get(id)||[]).length}</summary>${llvmRelationHTML(id)}</details>`);
}
function llvmEvidenceHTML(e) {
  const s=llvmData.sources[e.source_id];
  return `<div class="evidence-entry"><code>${esc(e.kind || '')}</code><p class="source-ref">${esc(s.path)}${e.line?':'+e.line:''}${e.byte_offset!==undefined?' · byte '+e.byte_offset:''}${e.bit_offset!==undefined?' · bit '+e.bit_offset:''}</p><p class="condition">SHA-256 ${esc(s.sha256)} · ${s.package_status==='verified'?'原包已核对':s.origin==='cce_dialect'?'外部工程':'未核对原包'}</p>${e.excerpt?`<pre><code>${esc(e.excerpt)}</code></pre>`:''}</div>`;
}
function renderLLVMDetail(r) {
  const o=r.llvm, pane=$('#detail'), forms=o.form_ids.map(id=>llvmForms.get(id));
  const current=forms.find(f=>f.id===state.opForm) || forms.find(f=>f.kind==='observed_signature') || forms[0];
  if(current)state.opForm=current.id;
  const formLabel=f=>f.kind==='observed_signature'?`模块声明${f.signature_status==='partial_vendor_types'?' · 含未解析类型':''}`:'注册表类型约束';
  const evidenceSources=Object.entries(llvmData.sources).filter(([sid])=>['hivmc_a5','ccec','llc'].includes(sid) || sid.startsWith('bc_'));
  pane.innerHTML=`<div class="detail-heading"><h2>${esc(o.name)}</h2><div class="detail-domain"><span>${esc(r.group)}</span><span>${esc(r.family)}</span></div><div class="detail-actions"><button id="back-to-list" class="mobile-return text-button">返回列表</button><button id="copy-link" class="quiet-button">复制链接</button><button id="copy-llvm" class="quiet-button" ${current?.signature?'':'disabled'}>复制类型</button></div></div><div class="detail-body"><p>${esc(llvmIdentities[o.identity_status])} · ${esc(llvmTargetLabels[o.static_target?.status] || '证据不足')}</p><p class="condition">固定 Ascend950PR_9579 / 3510。包内声明、调用与目标可编译性分别记录；模块中的调用不保证入口可达或所有参数形式适用。编译 / 运行 / 性能均未验证。</p>${llvmCallHTML(o,current)}${o.summary?`<p>${esc(o.summary)}</p><a href="${esc(o.reference_url)}" target="_blank" rel="noopener">LLVM IR 参考文档</a>`:''}${forms.length?`<label class="overloads">类型形式 · ${forms.length}<select id="llvm-form" aria-label="LLVM 类型形式">${forms.map((f,i)=>`<option value="${f.id}" ${f.id===current.id?'selected':''}>${i+1}. ${esc(formLabel(f))} · ${esc(f.signature || f.error)}</option>`).join('')}</select></label>${current.signature?`<pre><code>${esc(current.signature)}</code></pre><p class="condition">${current.kind==='observed_signature'?'此模块中的具体函数类型；参数名未存储。调用追踪按模块和当前类型形式单列。':'LLVM 15 IIT 格式解释。T(arg_info=N) 是重载类型约束，不是 C/C++ 参数；ptr 保留编码中的地址空间与元素约束。厂商扩展未获独立解释。'}</p><table class="param-table"><thead><tr><th>#</th><th>类型 / 约束</th></tr></thead><tbody><tr><td>返回</td><td><code>${esc(current.return_type)}</code></td></tr>${(current.parameters||[]).map((x,i)=>`<tr><td>${i+1}</td><td><code>${esc(x)}</code></td></tr>`).join('')}</tbody></table>`:`<p>类型编码尚未解析：${esc(current.error)}</p>`}<details><summary>当前形式的编码与来源</summary><pre><code>${esc(JSON.stringify({...current,evidence:undefined},null,2))}</code></pre>${current.evidence.map(llvmEvidenceHTML).join('')}</details>`:o.domain==='ordinary_ir'?'':'<p>仅有名称或外部引用，没有取得 CANN 的类型签名。</p>'}<details><summary>来源矩阵</summary><table class="param-table"><tbody>${evidenceSources.map(([sid,s])=>`<tr><td>${esc(s.path.split('/').pop())}</td><td>${esc({observed:'有此名称',scanned_absent:'本次扫描未见',not_scanned:'未扫描'}[o.presence[sid]] || '未扫描')}</td></tr>`).join('')}<tr><td>CCE Dialect</td><td>${o.presence.dialect==='observed'?'有引用':'本次扫描未见'}</td></tr></tbody></table></details><details open><summary>上下层关联 · ${(llvmRelationsById.get(o.id)||[]).length}</summary>${llvmRelationHTML(o.id)}</details><details><summary>全部来源证据 · ${o.evidence.length}</summary>${o.evidence.map(llvmEvidenceHTML).join('')}</details></div>`;
  if($('#llvm-call-more'))$('#llvm-call-more').onclick=appendLLVMCalls;
  if($('#llvm-form'))$('#llvm-form').onchange=e=>{state.opForm=e.target.value;saveHash();renderLLVMDetail(r);};
  $('#copy-link').onclick=()=>copyText(location.href);
  $('#copy-llvm').onclick=()=>copyText(current?.signature || '');
  $('#back-to-list').onclick=()=>{readingDetail=false;$('#rows [aria-current="true"]')?.scrollIntoView({block:'center'});queueMore();};
  wireOpLinks(pane);
}
function renderLLVMReport() {
  $('#report').innerHTML=`<h2>LLVM IR 核心 · 来源与边界</h2><p>默认仅显示 c310 模块中的声明或调用；A5 相关线索另列。其他跨架构注册项可通过「全部范围」查看；字符串候选需要另行勾选。</p><pre><code>${esc(JSON.stringify({coverage:llvmData.coverage,target_mapping:llvmData.target_mapping,static:llvmData.a5_static_summary},null,2))}</code></pre><ul>${llvmData.limitations.map(x=>`<li>${esc(x)}</li>`).join('')}</ul><details><summary>c310 调用解析缺口</summary><pre><code>${esc(JSON.stringify((llvmData.a5_call_scans || []).map(s=>({...s,issues:undefined})),null,2))}</code></pre><p>完整未解析位置可从数据库快照 a5_call_scans 查询。</p></details><details><summary>提取覆盖与失败记录</summary><pre><code>${esc(JSON.stringify(llvmData.scans,null,2))}</code></pre></details><details><summary>原包核对</summary><pre><code>${esc(JSON.stringify(llvmData.package,null,2))}</code></pre></details>`;
}
function downloadLLVM() {
  const selected=filtered().map(r=>r.llvm), ids=new Set(selected.map(o=>o.id));
  const forms=llvmData.forms.filter(f=>ids.has(f.op_id));
  const sourceIds=new Set([...selected.flatMap(o=>o.evidence),...forms.flatMap(f=>f.evidence)].map(e=>e.source_id));
  const formIds=new Set(forms.map(f=>f.id)), table=llvmData.a5_call_table;
  const callTable=table?{...table,rows:table.rows.filter(row=>formIds.has(table.forms[row[1]]))}:undefined;
  const payload={schema_version:'ackb.llvm.export.v1',version:llvmData.version,target:llvmData.target,target_mapping:llvmData.target_mapping,a5_call_table:callTable,selection:{scope:state.llvmScope,include_candidates:state.includeUnknown,evidence:state.llvmEvidence,query:state.query,group:state.group,file:state.file},limitations:llvmData.limitations,ops:selected,forms,relations:llvmData.relations.filter(e=>ids.has(e.from)||ids.has(e.to)),sources:Object.fromEntries([...sourceIds].map(id=>[id,llvmData.sources[id]]))};
  const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));
  const a=document.createElement('a');a.href=url;a.download='ackb-llvm-ir.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function syncHome() {
  document.body.classList.toggle('home-mode',state.home);
  const reading = state.home && (location.hash==='#insights' || location.hash.startsWith('#insight='));
  const slug = new URLSearchParams(location.hash.slice(1)).get('insight');
  const articles = [...document.querySelectorAll('[data-insight]')];
  const selected = articles.find(article=>article.dataset.insight===slug);
  $('#insights').hidden=!reading;
  $('#insights-index').hidden=!!slug || location.hash.startsWith('#insight=');
  articles.forEach(article=>{article.hidden=!reading || article!==selected;});
  $('#insight-missing').hidden=!reading || !location.hash.startsWith('#insight=') || !!selected;
  if(reading) $('.insights-link').setAttribute('aria-current','page');
  else $('.insights-link').removeAttribute('aria-current');
  document.title=reading?(selected?selected.querySelector('h1').textContent+' · ACKB':'洞察 · ACKB'):'ACKB · AI Compiler 目标知识库';
  const map = state.home && !reading;
  $('#home').hidden=!map;$('#ascendc-map').hidden=!map;$('.workspace').hidden=state.home;
  $('.skip-link').href=reading?'#insights-content':state.home?'#api-map-content':'#main';
  if(state.home){setProgressActive(false);document.body.classList.remove('reading-ptx','lookup-collapsed');window.scrollTo(0,0);}
  return state.home;
}
