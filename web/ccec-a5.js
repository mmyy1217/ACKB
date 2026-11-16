'use strict';
const A5_CHIP='Ascend950PR_9579', A5_PROFILE='__NPU_ARCH__=3510';
function fixedA5(){state.chip=A5_CHIP;state.architecture=A5_PROFILE;state.availability=state.includeUnknown?'possible':'matches';state.proof='';state.deprecation='';}
function a5GroupLabel(items){const values=items.map(r=>r.compatibility?.profiles[A5_PROFILE]);return values.includes('matches')?'条件符合':values.includes('unknown')?'待确认':values.includes('excluded')?'条件排除':'参考';}
function a5Related(ids){return ids.filter(id=>{const status=byId.get(id)?.compatibility?.profiles[A5_PROFILE];return status==='matches' || state.includeUnknown && status==='unknown';});}
function scopedA5Op(op){return {...op,entry_records:a5Related(op.entry_records),caller_records:a5Related(op.caller_records),forms:op.forms.filter(f=>a5Related(f.record_ids).length).map(f=>({...f,record_ids:a5Related(f.record_ids)}))};}
function a5Stats(layer){const groups=new Map();for(const r of allRecords){if(layer==='wrappers'?!ccecIsInterface(r):!r.op)continue;const key=r.op?r.id:[r.namespace,r.name].join('::');if(!groups.has(key))groups.set(key,[]);groups.get(key).push(r);}const result={matches:0,unknown:0,excluded:0};for(const rs of groups.values()){const values=rs.map(r=>r.compatibility.profiles[A5_PROFILE]);result[values.includes('matches')?'matches':values.includes('unknown')?'unknown':'excluded']++;}return result;}
function renderA5Report(){
 const wrappers=a5Stats('wrappers'),ops=a5Stats('interfaces');
 $('#report').innerHTML=`<h2>Huawei Ascend 950 / A5</h2><p>固定配置 ${A5_CHIP} · NpuArch 3510。CCEC 编程接口包含封装与已追踪的 950 搬运直连入口；CCEC Builtins 用于核对精确 builtin。两层可沿详情中的调用关系互相跳转。</p><table class="parameter-table"><thead><tr><th>层级</th><th>条件符合</th><th>待确认</th><th>条件排除</th></tr></thead><tbody><tr><td>CCEC 调用接口</td><td>${wrappers.matches}</td><td>${wrappers.unknown}</td><td>${wrappers.excluded}</td></tr><tr><td>唯一 builtin</td><td>${ops.matches}</td><td>${ops.unknown}</td><td>${ops.excluded}</td></tr></tbody></table><p>默认仅显示声明条件符合的条目；“显示待确认”加入缺少宏依据的条目。条件排除不进入主目录。条件符合仅表示至少一个声明分支符合，并非通过编译或设备验证。</p><p>Intrinsic 不继承封装或同名引用的支持状态。仅在函数体发现的 builtin 若缺少入口条件，保留为待确认。参数、来源声明和原始实现均在详情中保留。</p><p>950 搬运追踪：${callEvidence.coverage.files || 0} 个源码文件、${callEvidence.coverage.parsed_calls || 0} 处调用、${callEvidence.coverage.added_direct_entries || 0} 个补充直连入口。仅保存观测调用形式；不等于编译器完整签名。</p><details><summary>来源与覆盖</summary><p>CANN ${esc(data.version)}；${data.files.length} 个声明头文件已核验原包。${ccecStatic?.package_verified_files || 0} 个 AscendC 源码文件已核验。${data.report.unresolved.length} 个原始解析问题，${opModel.counts.unresolved} 项关联缺口。</p><p>编译、运行、性能均未验证。未知不代表不支持。</p></details><details><summary>相关知识说明</summary>${knowledgeRecords.filter(r=>r.backend==='ccec').map(r=>opLink(r.id,r.name)).join('')}</details>`;
 wireOpLinks($('#report'));
}

function ccecFamilyMatches(r,family){return family.startsWith('transfer:')?r.transfer?.id===family:r.family===family || family==='搬运 / DMA' && Boolean(r.transfer);}
function ccecTransferRoutes(){return [...new Map(allRecords.filter(r=>r.transfer).map(r=>[r.transfer.id,r.transfer])).values()].sort((a,b)=>a.label.localeCompare(b.label));}
function ccecFamilyLabel(family){return ccecTransferRoutes().find(t=>t.id===family)?.label || family;}
function renderTransferEmpty(){
  const active=state.backend==='ccec' && state.family.startsWith('transfer:');
  const scoped=['ccec','ascendc'].includes(state.backend) && ['wrappers','interfaces','basic','capi'].includes(state.view);
  const visibleKeys=new Set(visible.map(g=>g.key));
  const hiddenCount=scoped && !state.includeUnknown ? makeGroups(filtered(true).filter(r=>r.compatibility?.profiles?.[A5_PROFILE]==='unknown')).filter(g=>!visibleKeys.has(g.key)).length : 0;
  const reveal=()=>{state.includeUnknown=true;render();};
  const message=`另有 ${fmt(hiddenCount)} 个匹配条目因 950 条件待确认被隐藏。`;
  $('#unknown-hint').hidden=!hiddenCount || !visible.length;
  $('#unknown-hint-text').textContent=message;
  $('#show-hidden').onclick=reveal;
  $('#empty p').textContent=hiddenCount?message+'待确认不代表不支持。':active?'当前层级和筛选下没有条目，不代表该搬运路径不存在或芯片不支持。可切换层级查阅。':'试试更短的名称，或重置筛选。';
  $('#empty-unknown').hidden=!hiddenCount;
  $('#empty-layer').hidden=!active;
  $('#empty-layer').textContent=state.ccecLayer==='wrappers'?'查看同路径 Builtins':'查看同路径编程接口';
  $('#empty-unknown').onclick=reveal;
  $('#empty-layer').onclick=()=>{state.ccecLayer=state.ccecLayer==='wrappers'?'interfaces':'wrappers';state.view=state.ccecLayer;state.query='';state.file='';state.group='';state.selected='';render();};
}
