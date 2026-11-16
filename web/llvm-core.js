'use strict';
const llvmData = knowledgeData.llvm || {ops:[],forms:[],sources:{},relations:[],coverage:{},limitations:[],scans:[]};
if(llvmData.web_encoding==='columnar-v1') {
  for(const name of ['ops','forms']) {const table=llvmData[name];llvmData[name]=table.rows.map(row=>Object.fromEntries(table.columns.flatMap((key,i)=>row[i]===null?[]:[[key,row[i]]])));}
  for(const o of llvmData.ops)o.presence=Object.fromEntries(o.presence.map((v,i)=>[llvmData.presence_columns[i],['not_scanned','scanned_absent','observed'][v]]));
}
const llvmForms = new Map(llvmData.forms.map(f=>[f.id,f]));
const llvmDomains = {target_intrinsic:'目标 Intrinsic',standard_intrinsic:'标准 LLVM Intrinsic',ordinary_ir:'普通 LLVM IR'};
const llvmIdentities = {registered:'编译器已注册',declaration_observed:'模块声明',lowering_reference:'外部 lowering 引用',candidate_only:'仅字符串候选',reference_model:'IR 参考模型'};
const llvmRecords = llvmData.ops.map(op=>({id:op.id,name:op.name,backend:'llvm',kind:'llvm',llvm:op,group:llvmDomains[op.domain],family:op.family,namespace:'',signature:op.form_ids.map(id=>llvmForms.get(id)?.signature || '').join(' '),builtins:[],conditions:[],source:{file:llvmData.sources[op.evidence[0]?.source_id]?.path || 'LLVM LangRef',line:op.evidence[0]?.line || 0},files:op.evidence.map(e=>llvmData.sources[e.source_id]?.path).filter(Boolean)}));
const llvmRelationsById = new Map();
for(const edge of llvmData.relations) for(const id of [edge.from,edge.to]) {if(!llvmRelationsById.has(id))llvmRelationsById.set(id,[]);llvmRelationsById.get(id).push(edge);}
function llvmMatches(r) {
  const o=r.llvm;
  return (state.llvmScope==='all' || o.a5_source_lead || o.domain==='ordinary_ir') && (state.includeUnknown || o.identity_status!=='candidate_only') && (!state.llvmEvidence || o.evidence.some(e=>e.kind===state.llvmEvidence));
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
  pane.innerHTML=`<div class="detail-heading"><h2>${esc(o.name)}</h2><div class="detail-domain"><span>${esc(r.group)}</span><span>${esc(r.family)}</span></div><div class="detail-actions"><button id="back-to-list" class="mobile-return text-button">返回列表</button><button id="copy-link" class="quiet-button">复制链接</button><button id="copy-llvm" class="quiet-button" ${current?.signature?'':'disabled'}>复制类型</button></div></div><div class="detail-body"><p>${esc(llvmIdentities[o.identity_status])} · ${o.target_status==='c310_module_declaration'?'c310 模块有声明':'950 支持未确定'}</p><p class="condition">注册、模块声明和设备支持是独立证据。编译 / 运行 / 性能均未验证。</p>${o.summary?`<p>${esc(o.summary)}</p><a href="${esc(o.reference_url)}" target="_blank" rel="noopener">LLVM IR 参考文档</a>`:''}${forms.length?`<label class="overloads">类型形式 · ${forms.length}<select id="llvm-form" aria-label="LLVM 类型形式">${forms.map((f,i)=>`<option value="${f.id}" ${f.id===current.id?'selected':''}>${i+1}. ${esc(formLabel(f))} · ${esc(f.signature || f.error)}</option>`).join('')}</select></label>${current.signature?`<pre><code>${esc(current.signature)}</code></pre><p class="condition">${current.kind==='observed_signature'?'此模块中的具体函数类型；参数名未存储。函数体与调用未扫描。':'LLVM 15 IIT 格式解释。T(arg_info=N) 是重载类型约束，不是 C/C++ 参数；ptr 保留编码中的地址空间与元素约束。厂商扩展未获独立解释。'}</p><table class="param-table"><thead><tr><th>#</th><th>类型 / 约束</th></tr></thead><tbody><tr><td>返回</td><td><code>${esc(current.return_type)}</code></td></tr>${(current.parameters||[]).map((x,i)=>`<tr><td>${i+1}</td><td><code>${esc(x)}</code></td></tr>`).join('')}</tbody></table>`:`<p>类型编码尚未解析：${esc(current.error)}</p>`}<details><summary>当前形式的编码与来源</summary><pre><code>${esc(JSON.stringify({...current,evidence:undefined},null,2))}</code></pre>${current.evidence.map(llvmEvidenceHTML).join('')}</details>`:o.domain==='ordinary_ir'?'':'<p>仅有名称或外部引用，没有取得 CANN 的类型签名。</p>'}<details><summary>来源矩阵</summary><table class="param-table"><tbody>${evidenceSources.map(([sid,s])=>`<tr><td>${esc(s.path.split('/').pop())}</td><td>${esc({observed:'有此名称',scanned_absent:'本次扫描未见',not_scanned:'未扫描'}[o.presence[sid]] || '未扫描')}</td></tr>`).join('')}<tr><td>CCE Dialect</td><td>${o.presence.dialect==='observed'?'有引用':'本次扫描未见'}</td></tr></tbody></table></details><details open><summary>上下层关联 · ${(llvmRelationsById.get(o.id)||[]).length}</summary>${llvmRelationHTML(o.id)}</details><details><summary>全部来源证据 · ${o.evidence.length}</summary>${o.evidence.map(llvmEvidenceHTML).join('')}</details></div>`;
  if($('#llvm-form'))$('#llvm-form').onchange=e=>{state.opForm=e.target.value;saveHash();renderLLVMDetail(r);};
  $('#copy-link').onclick=()=>copyText(location.href);
  $('#copy-llvm').onclick=()=>copyText(current?.signature || '');
  $('#back-to-list').onclick=()=>{readingDetail=false;$('#rows [aria-current="true"]')?.scrollIntoView({block:'center'});queueMore();};
  wireOpLinks(pane);
}
function renderLLVMReport() {
  $('#report').innerHTML=`<h2>LLVM IR 核心 · 来源与边界</h2><p>默认视图按 A5 来源线索收束。其他跨架构注册项可通过「全部范围」查看；字符串候选需要另行勾选。</p><pre><code>${esc(JSON.stringify(llvmData.coverage,null,2))}</code></pre><ul>${llvmData.limitations.map(x=>`<li>${esc(x)}</li>`).join('')}</ul><details><summary>提取覆盖与失败记录</summary><pre><code>${esc(JSON.stringify(llvmData.scans,null,2))}</code></pre></details><details><summary>原包核对</summary><pre><code>${esc(JSON.stringify(llvmData.package,null,2))}</code></pre></details>`;
}
function downloadLLVM() {
  const selected=filtered().map(r=>r.llvm), ids=new Set(selected.map(o=>o.id));
  const forms=llvmData.forms.filter(f=>ids.has(f.op_id));
  const sourceIds=new Set([...selected.flatMap(o=>o.evidence),...forms.flatMap(f=>f.evidence)].map(e=>e.source_id));
  const payload={schema_version:'ackb.llvm.export.v1',version:llvmData.version,target:llvmData.target,selection:{scope:state.llvmScope,include_candidates:state.includeUnknown,evidence:state.llvmEvidence,query:state.query,group:state.group,file:state.file},limitations:llvmData.limitations,ops:selected,forms,relations:llvmData.relations.filter(e=>ids.has(e.from)||ids.has(e.to)),sources:Object.fromEntries([...sourceIds].map(id=>[id,llvmData.sources[id]]))};
  const url=URL.createObjectURL(new Blob([JSON.stringify(payload,null,2)],{type:'application/json'}));
  const a=document.createElement('a');a.href=url;a.download='ackb-llvm-ir.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function syncHome() {
  document.body.classList.toggle('home-mode',state.home);
  $('#home').hidden=!state.home;$('.workspace').hidden=state.home;
  $('.skip-link').href=state.home?'#home-content':'#main';
  if(state.home){setProgressActive(false);document.body.classList.remove('reading-ptx','lookup-collapsed');window.scrollTo(0,0);}
  return state.home;
}
