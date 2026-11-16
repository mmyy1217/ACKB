'use strict';
const opModel = knowledgeData.ccec.ops;
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
    return {id:op.id,name:op.name,kind:'op',op,group:op.group,family:op.family,namespace:'',
      signature:op.builtin,conditions:[],builtins:[op.builtin],source:related[0].source,
      files:[...new Set(related.map(r=>r.source.file))],
      compatibility:{profiles},deprecation:{status:'unmarked'}};
  });
}
function opNavigate(id) {
  const target=byId.get(id);if(!target)return;
  if(target.op)state.ccecLayer='interfaces';else if(opModel?.record_layers[id]?.layer==='wrapper')state.ccecLayer='wrappers';
  const status=target.compatibility?.profiles[A5_PROFILE];
  if(status==='unknown')state.includeUnknown=true;
  Object.assign(state,{view:status==='excluded'?'references':recordView(target),selected:id,query:'',family:'',group:'',file:'',availability:'',proof:'',deprecation:'',tab:'definition'});
  render(!mobile.matches);
  if(mobile.matches){readingDetail=true;$('#detail').scrollIntoView({block:'start'});}
  $('#detail').focus({preventScroll:true});
}
function wireOpLinks(pane) {pane.querySelectorAll('[data-op-ref]').forEach(b=>b.onclick=()=>opNavigate(b.dataset.opRef));}
function opLink(id,label) {return `<button class="related-link" data-op-ref="${esc(id)}">${esc(label || byId.get(id)?.name || id)}</button>`;}
function opRecordEvidence(id) {
  const r=byId.get(id),status=state.architecture?r.compatibility.profiles[state.architecture]:'not_evaluated';
  const labels={matches:'声明条件符合',unknown:'声明条件未知',excluded:'声明条件排除',not_evaluated:'未指定架构'};
  return `<details><summary>${esc((r.namespace?r.namespace+'::':'::')+r.name)} · ${r.parameters?.includes('...')?'参数未确定':(r.parameters?.length || 0)+' 参数'} · L${r.source.line} · ${esc(labels[status])}</summary><pre><code>${esc(r.signature)}</code></pre><p class="condition">${esc(sourceLabel(r.source))}</p><p class="condition">SHA-256 ${esc(fileMap.get(r.source.file)?.sha256)}</p>${r.conditions.map(c=>`<p class="condition">${esc(c)}</p>`).join('')}${opLink(id,'查看原始声明与实现')}</details>`;
}
function layerContent(r) {
  const layer=opModel?.record_layers[r.id];if(!layer)return '';
  const labels={intrinsic_entry:'Intrinsic 入口声明',wrapper:'上层封装',unresolved_entry:'待解析入口'};
  const edges=opModel.edges.filter(e=>e.source_record===r.id);
  return `<h3>层级 · ${labels[layer.layer]}</h3>${edges.length?edges.map(e=>`<p>${e.kind==='builtin_alias'?'显式 alias →':'函数体引用 →'} ${opLink(e.target_op)}</p>`).join(''):'<p>未解析出可靠的 builtin 关联；保留原始记录。</p>'}<p>这里只展示显式 alias 或完整限定名 / builtin 引用；函数体分支与参数形式仍需分别核对。</p>`;
}
function renderOpDetail(r) {
  const pane=$('#detail'),o=scopedA5Op(r.op);
  const status=state.architecture?r.compatibility.profiles[state.architecture]:'not_evaluated';
  const labels={matches:'至少一个入口声明条件符合',unknown:'入口声明条件未知或没有入口声明',excluded:'入口声明条件全部排除',not_evaluated:'未指定架构条件'};
  pane.innerHTML=`<div class="detail-heading"><h2>${esc(o.name)}</h2><p class="qualified">${esc(o.builtin)}</p><div class="detail-actions"><button id="back-to-list" class="mobile-return text-button">返回列表</button><button id="copy-link" class="quiet-button">复制链接</button></div></div><div class="detail-body"><h3>唯一 op · intrinsic / builtin 层</h3><p>${o.entry_records.length} 条入口声明 · ${o.forms.length?o.forms.length+' 种有类型声明形式':'参数形式待确定'} · ${o.caller_records.length} 条上层调用记录</p><p>${o.identity_evidence==='explicit_alias'?'身份来源：显式 clang_builtin_alias。':'身份来源：函数体内完整 builtin 调用标识符；尚未取得独立入口声明。'}</p><p>同一 builtin 只计一个 op。封装与来源声明单独保存；声明形式为词法签名，不等于已解析的 C++ 重载。</p><h3>架构条件${state.architecture?' · '+esc(state.chip || state.architecture):''}</h3><p>${esc(labels[status])}。</p><p>仅汇总显式入口声明条件；不继承同名封装、名称引用或调用者的支持状态。编译及运行未验证。</p><h3>参数形式</h3>${o.forms.length?o.forms.map(f=>`<details><summary>${f.record_ids.length} 条来源声明</summary><pre><code>${esc(f.signature)}</code></pre>${f.record_ids.map(id=>opLink(id,'原始声明')).join(' ')}</details>`).join(''):'<p>入口使用 ... 或只发现调用，精确参数签名未确定。封装参数不能直接当作 builtin 参数。</p>'}<h3>Intrinsic 入口与来源 · ${o.entry_records.length}</h3>${o.entry_records.map(opRecordEvidence).join('') || '<p>当前扫描范围没有独立 alias 入口。</p>'}<h3>上层调用者 · ${o.caller_records.length}</h3><p>每条关联保留自己的架构条件和实现；可查看源码中的分支与参数转换。</p>${o.caller_records.map(opRecordEvidence).join('') || '<p>未找到经过限定名关联的上层调用；同名不自动连线。</p>'}</div>`;
  if(o.caller_records.length<r.op.caller_records.length)pane.querySelector('.detail-body').insertAdjacentHTML('beforeend','<p>仅列出当前 950 条件筛选下的调用者；待确认项可通过顶部开关显示。</p>');
  wireOpLinks(pane);
  $('#copy-link').onclick=()=>copyText(location.href);
  $('#back-to-list').onclick=()=>{readingDetail=false;const button=$('#rows [aria-current="true"]');button?.scrollIntoView({block:'center'});button?.focus({preventScroll:true});queueMore();};
}
