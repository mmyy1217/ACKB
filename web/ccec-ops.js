'use strict';
let opModel = knowledgeData.ccec.ops;
function createOpRecords(data) {
  if(!opModel)return [];
  const sources=new Map(data.records.map(r=>[r.id,r]));
  return opModel.ops.map(op=>{
    const entries=op.entry_records.map(id=>sources.get(id));
    const related=[...entries,...op.caller_records.map(id=>sources.get(id))];
    const profiles=Object.fromEntries(data.compatibility.profiles.map(p=>{
      const values=entries.map(r=>r.compatibility.profiles[p.id]);
      return [p.id,values.includes('matches')?'matches':!values.length || values.includes('unknown')?'unknown':'excluded'];
    }));
    return {id:op.id,name:op.name,kind:'op',op,transfer:op.transfer,group:op.group,family:op.family,namespace:'',
      signature:op.builtin,conditions:[],builtins:[op.builtin],source:related[0].source,
      files:[...new Set(related.map(r=>r.source.file))],
      compatibility:{profiles},deprecation:{status:'unmarked'}};
  });
}
function opNavigate(id) {
  navigateWithData(backendForLink(id, byId.get(id)?.backend || 'ccec'),()=>openOp(id));
}
function openOp(id) {
  const target=byId.get(id);if(!target)return;
  state.home=false;
  if(target.backend==='llvm'){state.backend='llvm';state.llvmSource='';state.llvmScope=target.llvm.a5_source_lead || target.llvm.domain==='ordinary_ir'?'a5-sources':'all';state.includeUnknown=target.llvm.identity_status==='candidate_only';state.llvmEvidence='';configureBackend();}
  else if(target.backend==='ascendc'){
    state.backend='ascendc';state.ascendcLayer=target.ascendcLayer;configureBackend();
  }else if(target.backend==='cce-dialect'){
    state.backend='cce-dialect';state.dialectLayer=target.dialectLayer;configureBackend();
  }else{
    if(state.backend!=='ccec'){state.backend='ccec';configureBackend();}
    if(target.op)state.ccecLayer='interfaces';else if(ccecIsInterface(target))state.ccecLayer='wrappers';
  }
  const status=target.compatibility?.profiles?.[A5_PROFILE];
  if(status==='unknown')state.includeUnknown=true;
  Object.assign(state,{view:status==='excluded' && state.backend==='ccec'?'references':recordView(target),selected:id,query:'',family:'',group:'',file:'',availability:'',proof:'',deprecation:'',tab:'definition'});
  render(!mobile.matches);
  if(mobile.matches){readingDetail=true;$('#detail').scrollIntoView({block:'start'});}
  $('#detail').focus({preventScroll:true});
}
function wireOpLinks(pane) {pane.querySelectorAll('[data-op-ref]').forEach(b=>b.onclick=()=>opNavigate(b.dataset.opRef));}
function opLink(id,label) {return `<button class="related-link" data-op-ref="${esc(id)}">${esc(label || lookupRecord(id)?.name || id)}</button>`;}
function opRecordEvidence(id) {
  const r=byId.get(id),status=state.architecture?r.compatibility.profiles[state.architecture]:'not_evaluated';
  const labels={matches:'声明条件符合',unknown:'声明条件未知',excluded:'声明条件排除',not_evaluated:'未指定架构'};
  return `<details><summary>${esc((r.namespace?r.namespace+'::':'::')+r.name)} · ${r.parameters?.includes('...')?'参数未确定':(r.parameters?.length || 0)+' 参数'} · L${r.source.line} · ${esc(labels[status])}</summary><pre><code>${esc(r.signature)}</code></pre><p class="condition">${esc(sourceLabel(r.source))}</p><p class="condition">SHA-256 ${esc(fileMap.get(r.source.file)?.sha256)}</p>${r.conditions.map(c=>`<p class="condition">${esc(c)}</p>`).join('')}${opLink(id,'查看原始声明与实现')}</details>`;
}
function layerContent(r) {
  const layer=opModel?.record_layers[r.id];if(!layer)return '';
  const labels={intrinsic_entry:'直连编译器入口（alias）',wrapper:'上层封装',unresolved_entry:'待解析入口'};
  const edges=opModel.edges.filter(e=>e.source_record===r.id);
  return `<h3>层级 · ${labels[layer.layer]}</h3>${edges.length?edges.map(e=>`<p>${e.kind==='builtin_alias'?'显式 alias →':'函数体引用 →'} ${opLink(e.target_op)}</p>`).join(''):'<p>未解析出可靠的 builtin 关联；保留原始记录。</p>'}<p>这里只展示显式 alias 或完整限定名 / builtin 引用；函数体分支与参数形式仍需分别核对。</p>`;
}
function opParameterPanel(o) {
  const callers=new Map();
  for(const id of o.caller_records){const r=byId.get(id),key=JSON.stringify([r.namespace,r.name,r.return_type,r.template,r.parameters]);if(!callers.has(key))callers.set(key,{id,record_ids:[]});callers.get(key).record_ids.push(id);}
  const choices=[...callers.values()];
  if(!o.forms.some(f=>f.id===state.opForm))state.opForm=o.forms[0]?.id || '';
  if(!choices.some(f=>f.id===state.opCaller))state.opCaller=choices[0]?.id || '';
  const optionLabel=r=>`${r.namespace?r.namespace+'::':''}${r.name}(${(r.parameters || []).join(', ')})`;
  return `<label class="overloads">Intrinsic 参数形式 · ${o.forms.length || '未确定'}<select id="op-form" aria-label="选择 Intrinsic 参数形式" ${o.forms.length?'':'disabled'}>${o.forms.length?o.forms.map((f,i)=>`<option value="${esc(f.id)}" ${f.id===state.opForm?'selected':''}>${i+1}. ${esc(optionLabel(byId.get(f.record_ids[0])))}</option>`).join(''):'<option>仅有 ... 声明或调用引用</option>'}</select></label><div id="op-form-content"></div>${choices.length?`<label class="overloads">关联封装参数 · ${choices.length}<select id="op-caller" aria-label="选择关联封装参数">${choices.map((f,i)=>`<option value="${esc(f.id)}" ${f.id===state.opCaller?'selected':''}>${i+1}. ${esc(optionLabel(byId.get(f.id)))}</option>`).join('')}</select></label><div id="op-caller-content"></div>`:''}`;
}
function renderOpParameters(o) {
  const content=(ids,wrapper)=>{const r=byId.get(ids[0]);return `<p>${wrapper?'这是上层封装的参数，不是 builtin 的参数；关联依据为源码引用。':'来自显式 alias 入口；保留声明参数，未做 C++ 重载解析。'}</p><pre class="signature"><code>${esc(formatSignature(r))}</code></pre>${r.parameters?.length?`<table class="parameter-table"><thead><tr><th>序号</th><th>类型 / 名称 / 默认值</th></tr></thead><tbody>${r.parameters.map((p,i)=>`<tr><td>${i+1}</td><td><code>${esc(p)}</code></td></tr>`).join('')}</tbody></table>`:''}<p>${ids.map(id=>opLink(id,sourceLabel(byId.get(id).source))).join(' · ')}</p>`;};
  const form=o.forms.find(f=>f.id===state.opForm);
  $('#op-form-content').innerHTML=form?content(form.record_ids,false):'<p>入口声明为 ...；源码调用形式见上方，正式参数规范未验证。</p>';
  if($('#op-caller-content'))$('#op-caller-content').innerHTML=content([state.opCaller],true);
  appendLLVMRelations($('#detail'),o.id);
  wireOpLinks($('#detail'));
}
function renderOpDetail(r) {
  const pane=$('#detail'),o=scopedA5Op(r.op);
  const status=r.compatibility.profiles[A5_PROFILE];
  const labels={matches:'至少一个入口声明条件符合',unknown:'入口声明条件未知或没有入口声明',excluded:'入口声明条件全部排除'};
  pane.innerHTML=`<div class="detail-heading"><h2>${esc(o.name)}</h2><p class="qualified">${esc(o.builtin)}</p><div class="detail-actions"><button id="back-to-list" class="mobile-return text-button">返回列表</button><button id="copy-link" class="quiet-button">复制链接</button></div></div><div class="detail-body">${opParameterPanel(o)}<h3>唯一 op · intrinsic / builtin 层</h3><p>${o.entry_records.length} 条入口声明 · ${o.forms.length?o.forms.length+' 种有类型声明形式':'参数形式待确定'} · ${o.caller_records.length} 条上层调用记录</p><p>${o.identity_evidence==='explicit_alias'?'身份来源：显式 clang_builtin_alias。':'身份来源：函数体内完整 builtin 调用标识符；尚未取得独立入口声明。'}</p><h3>架构条件 · ${A5_CHIP}</h3><p>${esc(labels[status])}。</p><p>仅汇总显式入口声明条件；不继承同名封装、名称引用或调用者的支持状态。编译及运行未验证。</p><h3>Intrinsic 入口与来源 · ${o.entry_records.length}</h3>${o.entry_records.map(opRecordEvidence).join('') || '<p>当前扫描范围没有独立 alias 入口。</p>'}<h3>上层调用者 · ${o.caller_records.length}</h3><p>每条关联保留自己的架构条件和实现；可查看源码中的分支与参数转换。</p>${o.caller_records.map(opRecordEvidence).join('') || '<p>未找到经过限定名关联的上层调用；同名不自动连线。</p>'}</div>`;
  if(o.caller_records.length<r.op.caller_records.length)pane.querySelector('.detail-body').insertAdjacentHTML('beforeend','<p>仅列出当前 950 条件筛选下的调用者；待确认项可通过顶部开关显示。</p>');
  renderOpParameters(o);
  renderObservedCalls(r);
  $('#op-form').onchange=e=>{state.opForm=e.target.value;renderOpParameters(o);saveHash();};
  if($('#op-caller'))$('#op-caller').onchange=e=>{state.opCaller=e.target.value;renderOpParameters(o);saveHash();};
  $('#copy-link').onclick=()=>copyText(location.href);
  $('#back-to-list').onclick=()=>{readingDetail=false;const button=$('#rows [aria-current="true"]');button?.scrollIntoView({block:'center'});button?.focus({preventScroll:true});queueMore();};
}
