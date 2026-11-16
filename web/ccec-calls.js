'use strict';
let callEvidence=knowledgeData.ccec.call_evidence || {calls:[],files:{},direct_entry_ids:[],coverage:{},issues:[]};
let directEntryIDs=new Set(callEvidence.direct_entry_ids);
function ccecIsInterface(r){return opModel?.record_layers[r.id]?.layer==='wrapper' || directEntryIDs.has(r.id);}
function observedCalls(r){return callEvidence.calls.filter(c=>(r.op?c.op_id===r.id:c.entry_record_ids.includes(r.id)) && (c.condition_result==='matches' || state.includeUnknown && c.condition_result==='unknown'));}
function observedGroups(r){
 const groups=new Map();
 const calls=observedCalls(r).sort((a,b)=>Number(!a.source.file.includes('/c_api/') || a.source.file.includes('composite'))-Number(!b.source.file.includes('/c_api/') || b.source.file.includes('composite')));
 for(const c of calls){const key=JSON.stringify(c.arguments);if(!groups.has(key))groups.set(key,{id:c.id,calls:[]});groups.get(key).calls.push(c);}
 return [...groups.values()];
}
function renderObservedCalls(r){
 const groups=observedGroups(r);if(!groups.length)return;
 if(!groups.some(g=>g.id===state.observedCall))state.observedCall=groups[0].id;
 const pane=$('#detail'),anchor=pane.querySelector('#overload')?.parentElement || pane.querySelector('.detail-body');
 const html=`<section class="observed-calls"><label class="overloads">950 源码调用形式 · ${groups.length}<select id="observed-call" aria-label="选择 950 源码调用形式">${groups.map((g,i)=>{const c=g.calls[0];return `<option value="${esc(g.id)}" ${g.id===state.observedCall?'selected':''}>${i+1}. ${c.argument_count} 实参 · ${esc(c.caller.name)} · ${esc(c.arguments[0]?.observed_type || '类型待解析')}</option>`;}).join('')}</select></label><div id="observed-call-content"></div></section>`;
 anchor.insertAdjacentHTML(anchor.matches('.detail-body')?'afterbegin':'afterend',html);
 const draw=()=>{
  const g=groups.find(x=>x.id===state.observedCall),c=g.calls[0];
  $('#observed-call-content').innerHTML=`<p>${directEntryIDs.has(r.id)?'直连编译器入口；':''}下面是 950 实现实际传入的 ${c.argument_count} 个实参。表达式类型来自调用源码，不等于 builtin 正式形参类型；编译与运行未验证。</p><pre class="signature"><code>${esc(c.expression)}</code></pre><table class="parameter-table"><thead><tr><th>#</th><th>实参表达式</th><th>源码类型</th></tr></thead><tbody>${c.arguments.map((a,i)=>`<tr><td>${i+1}</td><td><code>${esc(a.expression)}</code></td><td><code>${esc(a.observed_type || '待解析')}</code></td></tr>`).join('')}</tbody></table><p>核 / 分支保护：${esc(c.block_guards.join('；') || '未发现局部保护')}。地址空间核对：${c.transfer_check.status==='agrees'?'源、目标与名称一致':esc(c.transfer_check.status)}。</p><details><summary>调用来源与架构选择 · ${g.calls.length} 处</summary>${g.calls.map(call=>{const file=callEvidence.files[call.source.file];return `<p class="source-ref">${esc(sourceLabel(call.source))}</p><pre><code>${esc(call.caller.signature)}</code></pre><p class="condition">SHA-256 ${esc(file.sha256)} · ${file.package_verified?'原包已核验':'原包未核验'}</p><p class="condition">${esc(call.conditions.join(' && '))}</p><p class="condition">${esc(call.block_guards.join('；'))}</p>${file.architecture_selector_path.map(e=>`<p class="condition">${esc(e.file)}:${e.line}<br>${esc(e.conditions.join(' && '))}<br>→ ${esc(e.resolved_relative_path)}</p>`).join('')}`;}).join('')}</details>`;
 };
 draw();$('#observed-call').onchange=e=>{state.observedCall=e.target.value;draw();saveHash();};
}
