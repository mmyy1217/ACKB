'use strict';
let nvvmRecords=[];
function refreshNVVM() {
  nvvmRecords=(knowledgeData.nvvm?.records || []).map(n=>({id:n.id,name:n.name,nvvm:n,backend:'nvvm',kind:'nvvm',group:'NVVM IR',family:n.family,namespace:'',signature:n.signatures.join('\n'),builtins:[],conditions:[],source:{file:'NVVM IR Specification 13.4.3'}}));
}
refreshNVVM();
function dotShape(names) {
  const parts=names.map(n=>n.split('.'));
  let common=0;
  if(parts.length) while(common < Math.min(...parts.map(p=>p.length))-1 && parts.every(p=>p[common]===parts[0][common]))common++;
  return {common,max:Math.max(1,...parts.map(p=>p.length-common)),prefix:parts[0]?.slice(0,common).join('.') || ''};
}
function depthEnabled(){return ['ptx','llvm','nvvm'].includes(state.backend) && state.view!=='report';}
function depthShape(){return dotShape(records.filter(r=>state.backend!=='ptx'||r.kind==='instruction').map(r=>r.name));}
function symbolGroups(items) {
  const shape=depthShape(),depth=state.symbolDepth || shape.max, map=new Map();
  for(const r of items){const name=r.name.split('.').slice(0,shape.common+depth).join('.');
    if(!map.has(name))map.set(name,{key:name,name,group:r.group,family:r.family,items:[],symbolGroup:true});
    map.get(name).items.push(r);
  }
  return [...map.values()].map(g=>({...g,family:new Set(g.items.map(r=>r.family)).size>1?'多个指令族':g.family}));
}
function syncDepthControl(){
  const el=$('#symbol-depth-control');el.hidden=!depthEnabled();if(el.hidden)return;
  const s=depthShape(),input=$('#symbol-depth');input.max=s.max;input.value=Math.min(state.symbolDepth||s.max,s.max);
  $('#symbol-depth-label').textContent=Number(input.value)===s.max?'全部展开':`${input.value} 级`;
  input.setAttribute('aria-valuetext',$('#symbol-depth-label').textContent);
  el.title=`按点号分段；固定公共前缀：${s.prefix || '无'}`;
}
function symbolMembers(){
 const g=visible.find(g=>g.items.some(r=>r.id===state.selected));if(!g?.symbolGroup || g.items.length<2)return;
 const box=document.createElement('label');box.className='overloads symbol-members';box.textContent=`组内记录 · ${g.items.length}`;
 const select=document.createElement('select');select.setAttribute('aria-label','组内完整符号');
 for(const r of g.items){const o=document.createElement('option');o.value=r.id;o.textContent=r.name;o.selected=r.id===state.selected;select.append(o);}
 select.onchange=()=>{state.selected=select.value;renderDetail();markSelectedRow();saveHash();};box.append(select);$('#detail').prepend(box);
}
function renderNVVMDetail(r){
 const n=r.nvvm,d=knowledgeData.nvvm;
 $('#detail').innerHTML=`<div class="detail-heading"><h2>${esc(n.name)}</h2><p>${esc(n.family)}</p></div><div class="detail-body"><p>${n.name_kind==='template'?'官方泛型名称模板（未实例化）':'官方规范显式符号'} · 目标支持未逐项验证</p>${n.signatures.map(s=>`<pre><code>${esc(s)}</code></pre>`).join('') || '<p>未提取到签名行。</p>'}<h3>来源</h3>${n.evidence.map(e=>`<p><a href="${esc(d.source.url+'#'+e.anchor)}" target="_blank" rel="noopener">${esc(e.anchor)}</a> · HTML 行 ${e.line}</p>`).join('')}<p class="condition">SHA-256 ${esc(d.source.sha256)}</p>${d.limitations.map(s=>`<p>${esc(s)}</p>`).join('')}</div>`;
}
