'use strict';
let learning = knowledgeData.ptx.learning;
let lessonViews = learning.chapters.map(c=>c.id);
let lookupReturn = null;
function isPtxReading() {return state.backend==='ptx' && [...lessonViews,'instruction','search'].includes(state.view);}
function renderPtxNavigation() {
  $('.views').innerHTML=learning.chapters.map(c=>`<details class="chapter-nav" ${c.id===state.view?'open':''}><summary>${esc(c.title)}</summary>${knowledgeData.ptx.notes.filter(n=>n.chapter===c.id).map(n=>`<button class="view lesson-link" data-lesson="${esc(n.id)}">${esc(n.title)}</button>`).join('')}</details>`).join('') + '<div class="reference-nav"><button class="view" data-view="interfaces">指令速查 <span>221</span></button><button class="view" data-view="all">官方手册目录 <span>743</span></button><button class="view" data-view="report">来源与覆盖</button></div>';
  $('.views').addEventListener('click',handleLessonNavigation);
}
function handleLessonNavigation(e) {
  const b=e.target.closest('[data-lesson]');if(!b)return;
  state.view=byId.get(b.dataset.lesson).knowledge.chapter;state.selected=b.dataset.lesson;state.query='';render();
}
function syncPtxNavigation() {
  if(state.backend!=='ptx')return;
  $('#ptx-target').value=state.ptxTarget;
  document.querySelectorAll('.chapter-nav').forEach(d=>{
    const selected=d.querySelector(`[data-lesson="${state.selected}"]`);
    if(selected)d.open=true;
  });
  document.querySelectorAll('[data-lesson]').forEach(b=>{b.classList.toggle('active',b.dataset.lesson===state.selected);if(b.dataset.lesson===state.selected)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current');});
}
function ptxReferenceLink(anchor,label) {
  const k=ptxSections.get(anchor);
  return k ? `<button class="related-link" data-open-ptx="${esc(k.entry_id)}">${esc(label || k.mnemonics?.join(' / ') || k.title || k.anchor)}</button>` : '';
}
function ptxSources(anchors) {
  const base=knowledgeData.ptx.source.isa.html.url;
  return '<ul class="source-list">'+anchors.map(a=>`<li><a target="_blank" rel="noopener" href="${esc(base+'#'+a)}">${esc(ptxSections.get(a)?.title || a)}</a></li>`).join('')+'</ul>';
}
function ptxExportRecord(r) {
  const {sm_89,target_assessments,...k}=r.knowledge;
  if(target_assessments) {k.target_assessment=assessment(r.knowledge);if(k.target_isa)k.target_isa={...k.target_isa,statements:k.target_assessment.statements};}
  return k;
}
function assessment(k) {return k.target_assessments?.[state.ptxTarget] || {support:'unknown',statements:[]};}
function ptxRules(k) {
  const a=assessment(k);
  return `<h3>${esc(state.ptxTarget)} 文档条件 · ${esc(supportLabels[a.support])}</h3><p>按目标说明的替代条件归并。条目级状态不证明每一种操作数组合合法，也不代表编译、运行或性能验证。</p>${ruleTable(a.statements,'target').replaceAll('sm_89',esc(state.ptxTarget))}`;
}
function ptxCategoryMatches(r,filter) {
  if(!filter)return true;
  const tax=r.knowledge?.taxonomy;
  return tax ? [tax.domain,tax.category,tax.subcategory].includes(filter) : r.family===filter;
}
function ptxInstructionCount(filter='') {
  return makeGroups(records.filter(r=>r.kind==='instruction' && compatibilityMatches(r) && ptxCategoryMatches(r,filter))).length;
}
function renderPtxCategoryBrief() {
  const box=$('#ptx-category-brief');
  if(!box)return;
  if(state.backend!=='ptx' || state.view!=='interfaces'){box.hidden=true;box.innerHTML='';return;}
  box.hidden=false;
  const f=state.family;
  const insts=records.filter(r=>r.kind==='instruction' && compatibilityMatches(r) && ptxCategoryMatches(r,f));
  const counts={};insts.forEach(r=>{const s=assessment(r.knowledge).support;counts[s]=(counts[s]||0)+1;});
  const stats=['documented_supported','partial','documented_not_supported'].filter(s=>counts[s]).map(s=>`${supportLabels[s]} ${counts[s]}`).join(' · ');
  if(!f) {
    box.innerHTML=`<div class="brief-head"><strong>PTX 9.7 指令分类探索</strong><span class="muted">${esc(state.ptxTarget)} · ${insts.length} 条指令${stats?'（'+esc(stats)+'）':''}</span></div><p class="brief-desc">按 7 大能力域或左侧 21 个官方 9.7.x 指令类别分层筛选；每个条目均含机制解析、修饰符字典与 B300 目标条件。</p><div class="brief-chips">${ptxTaxonomy.domains.map(d=>`<button class="chip-button" data-ptx-cat="${esc(d.id)}" title="${esc(d.summary)}">${esc(d.title)} <span>${ptxInstructionCount(d.id)}</span></button>`).join('')}</div>`;
  } else if(ptxDomains.has(f)) {
    const d=ptxDomains.get(f);
    box.innerHTML=`<div class="brief-crumb"><button class="text-button" data-ptx-cat="">全部指令</button><span>/</span><strong>${esc(d.title)}</strong><span class="muted">${insts.length} 条${stats?' · '+esc(stats):''}</span></div><p class="brief-desc">${esc(d.summary)}</p><div class="brief-chips">${d.categories.map(cid=>{const c=ptxCategories.get(cid);return c?`<button class="chip-button" data-ptx-cat="${esc(c.id)}">${esc(c.id)} ${esc(c.title_zh)} <span>${ptxInstructionCount(c.id)}</span></button>`:'';}).join('')}</div>`;
  } else {
    const sub=ptxSubcategories.get(f), cat=sub ? sub.category : ptxCategories.get(f);
    if(!cat){box.hidden=true;return;}
    const dom=ptxDomains.get(cat.domain);
    const quals=(cat.key_qualifiers||[]).map(q=>`<li><code>${esc(q.qualifier)}</code> — ${esc(q.meaning)}</li>`).join('');
    const subsHTML=(cat.subcategories||[]).length?`<div class="brief-chips"><button class="chip-button ${!sub?'active':''}" data-ptx-cat="${esc(cat.id)}">全类 (${ptxInstructionCount(cat.id)})</button>${cat.subcategories.map(s=>`<button class="chip-button ${sub?.id===s.id?'active':''}" data-ptx-cat="${esc(s.id)}">${esc(s.title_zh)} <span>${ptxInstructionCount(s.id)}</span></button>`).join('')}</div>`:'';
    const lessonsHTML=(cat.related_lessons||[]).map(lid=>byId.get(lid)).filter(Boolean).map(l=>`<button class="related-inline" data-open-lesson="${esc(l.id)}">专题：${esc(l.name)}</button>`).join('');
    box.innerHTML=`<div class="brief-crumb"><button class="text-button" data-ptx-cat="">全部指令</button><span>/</span>${dom?`<button class="text-button" data-ptx-cat="${esc(dom.id)}">${esc(dom.title)}</button><span>/</span>`:''}${sub?`<button class="text-button" data-ptx-cat="${esc(cat.id)}">${esc(cat.id)} ${esc(cat.title_zh)}</button><span>/</span><strong>${esc(sub.title_zh)}</strong>`:`<strong>${esc(cat.id)} ${esc(cat.title_zh)}</strong>`}<span class="muted">${insts.length} 条${stats?' · '+esc(stats):''}</span></div><p class="brief-desc">${esc(sub ? sub.summary : cat.summary)}</p><p class="brief-focus"><strong>编译器 / 内核视角：</strong>${esc(cat.compiler_focus)}</p>${subsHTML}${quals?`<details class="brief-details"><summary>常用修饰符与深入专题（§ ${esc(cat.id)} ${esc(cat.title_en)}）</summary><ul class="qualifier-list">${quals}</ul>${lessonsHTML?`<div class="brief-lessons">${lessonsHTML}</div>`:''}</details>`:(lessonsHTML?`<div class="brief-lessons">${lessonsHTML}</div>`:'')}`;
  }
  box.querySelectorAll('[data-ptx-cat]').forEach(b=>b.onclick=()=>{state.family=b.dataset.ptxCat;state.selected='';render();});
  box.querySelectorAll('[data-open-lesson]').forEach(b=>b.onclick=()=>openPtxEntry(b.dataset.openLesson));
}
function ptxBreadcrumb(k) {
  const tax=k.taxonomy;
  if(!tax)return '';
  const dom=ptxDomains.get(tax.domain), cat=ptxCategories.get(tax.category), sub=tax.subcategory && ptxSubcategories.get(tax.subcategory);
  return `<div class="reader-crumb">${dom?`<button class="text-button" data-jump-cat="${esc(dom.id)}">${esc(dom.title)}</button><span>/</span>`:''}${cat?`<button class="text-button" data-jump-cat="${esc(cat.id)}">${esc(cat.id)} ${esc(cat.title_zh)}</button>`:''}${sub?`<span>/</span><button class="text-button" data-jump-cat="${esc(sub.id)}">${esc(sub.title_zh)}</button>`:''}<span class="granularity-tag">${esc(tax.granularity)}</span><span class="granularity-tag">${esc(String(tax.form_count))} 种语法形式</span></div>`;
}
function qualifierDefsHTML(k) {
  const g=k.guide, defs=k.taxonomy?.qualifier_defs || {};
  const guideRows=(g?.qualifiers || []).map(q=>`<tr><td><code>${esc(q.token)}</code></td><td>${esc(q.meaning)}</td></tr>`).join('');
  const defRows=Object.entries(defs).map(([name,vals])=>`<tr><td><code>${esc(name)}</code></td><td><code>${esc(vals.join(' , '))}</code></td></tr>`).join('');
  if(!guideRows && !defRows)return '';
  return `<h2>修饰符与参数域</h2>${guideRows?`<table class="parameter-table qualifier-table"><thead><tr><th>修饰符 / 形式</th><th>语义作用</th></tr></thead><tbody>${guideRows}</tbody></table>`:''}${defRows?`<details class="qualifier-details"><summary>官方语法枚举表（从 PTX ISA 9.4 Syntax 块提取）</summary><table class="parameter-table qualifier-table"><thead><tr><th>占位符</th><th>合法取值集合</th></tr></thead><tbody>${defRows}</tbody></table></details>`:''}`;
}
function guideHTML(k) {
  const g=k.guide;
  if(!g)return '<p class="callout">本条已提供官方语法和目标条件；逐操作数中文语义尚未整理。请结合下方原文入口核对，勿从名称推断行为。</p>';
  return `<h2>${esc(g.summary)}</h2>${g.mechanism?`<p>${esc(g.mechanism)}</p>`:''}${qualifierDefsHTML(k)}<h3>典型示例与逐操作数拆解</h3><p class="muted">以下示例覆盖代表性形式（完整变体请对照下方官方语法与目标约束），未经实机编译或运行验证。</p><pre class="signature"><code>${esc(g.example)}</code></pre><h4>怎样读参数</h4><p>${esc(g.operands)}</p><h4>给定输入会发生什么</h4><p>${esc(g.result)}。</p><h4>容易错在哪里</h4><p>${esc(g.pitfall)}</p>`;
}
function instructionArticle(r) {
  const k=r.knowledge;
  const parent=ptxSections.get(k.parent_anchor);
  const children=knowledgeData.ptx.records.filter(x=>x.parent_anchor===k.anchor);
  const syntax=k.syntax_detail;
  const relatedLinks=(k.guide?.related || []).map(a=>ptxReferenceLink(a)).filter(Boolean).join('');
  const lessonLinks=(r.note_ids || k.note_ids || []).map(id=>byId.get(id)).filter(Boolean).map(l=>`<button class="related-link" data-open-ptx="${esc(l.id)}">专题：${esc(l.name)}</button>`).join('');
  return `<div class="reader-actions"><button class="text-button" data-reader-back>返回指令速查</button><button class="text-button" data-copy-entry>复制记录 JSON</button><button class="text-button" data-copy-url>复制链接</button></div>${ptxBreadcrumb(k)}<h1>${esc(r.name)}</h1><p class="reader-intro">${esc(k.title || r.group)}</p>${guideHTML(k)}<h2>官方语法</h2>${syntax ? `<pre><code>${esc(syntax.text)}</code></pre><p class="muted">{} 表示可选部分，形式与限定符应配套阅读。语法摘取自固定版本原文。</p>` : '<p>本章节没有可提取的独立语法块；它可能是概念章节或上级目录。可继续阅读下级条目。</p>'}<details class="reader-evidence"><summary>架构与版本限制 · ${esc(state.ptxTarget)} · ${esc(supportLabels[assessment(k).support])}</summary>${ptxRules(k)}<h3>PTX 版本规则</h3>${ruleTable(k.ptx_isa?.statements,'version')}</details>${relatedLinks?`<h2>协同与关联指令</h2><div class="reference-links">${relatedLinks}</div>`:''}${lessonLinks?`<h2>关联深度专题</h2><div class="reference-links">${lessonLinks}</div>`:''}${parent?'<h2>上级章节</h2>'+ptxReferenceLink(parent.anchor):''}${children.length?'<h2>下级内容</h2>'+children.map(c=>ptxReferenceLink(c.anchor)).join(''):''}<h2>官方来源</h2>${ptxSources([k.anchor])}<details><summary>来源哈希与索引记录</summary><p class="condition">${esc(knowledgeData.ptx.source.isa.html.sha256)}</p><pre><code>${esc(JSON.stringify(ptxExportRecord(r),null,2))}</code></pre></details>`;
}
function overviewDiagram() {
  return `<figure class="ptx-map"><div class="map-row"><span>高级语言 / 代码生成</span><span aria-hidden="true">→</span><strong>PTX</strong><span aria-hidden="true">→</span><span>工具链 → 机器代码</span></div><div class="model-map"><div><strong>执行</strong><p>grid / CTA / warp / 线程</p></div><div><strong>存储</strong><p>寄存器 / 内存空间 / 布局</p></div><div><strong>操作</strong><p>读取 / 计算 / 协作 / 写回</p></div></div><figcaption>这是理解程序的三个角度；软件分组与硬件资源不是一一对应关系。</figcaption></figure>`;
}
function lessonArticle(k) {
  const index=knowledgeData.ptx.notes.findIndex(n=>n.id===k.id),next=knowledgeData.ptx.notes[index+1];
  return `<div class="reader-actions"><button class="text-button" data-copy-url>复制链接</button></div><h1>${esc(k.title)}</h1><p class="reader-intro">${esc(k.intro)}</p>${k.id==='learn_overview'?overviewDiagram():''}<div class="term-strip"><span>随手查：</span>${k.terms.map(t=>`<button class="term-button" data-term="${esc(t)}">${esc(learning.terms[t].name)}</button>`).join('')}</div>${k.sections.map((s,i)=>`<section id="learn-section-${i}"><h2>${esc(s.title)}</h2><p>${esc(s.text)}</p>${s.code?`<div class="code-heading"><span>PTX 示例 · 未编译 / 未运行</span><button class="text-button" data-copy-code="${i}">复制代码</button></div>${programCode(s.code)}`:''}</section>`).join('')}<h2>关联指令与资料</h2><div class="reference-links">${k.anchors.map(a=>ptxReferenceLink(a)).join('')}</div><details class="reader-evidence"><summary>与 CCEC 比较时，关注什么？</summary><p>${esc(k.comparison)}</p><p>本页先解释 PTX，自行建立其执行模型；这里不是两端指令映射表。</p></details><details class="reader-evidence"><summary>依据与验证状态</summary><p>原创中文解释，依据下列官方章节整理。编译、运行、性能均未验证。代码是教学示例，不是生产优化实现。</p>${ptxSources(k.anchors)}</details>${next?`<button class="next-lesson" data-next="${esc(next.id)}">继续阅读：${esc(next.title)}</button>`:''}`;
}
function programCode(code) {
  return '<pre class="program-code"><code>'+code.split('\n').map(line=>{
    const trimmed=line.trim();
    const m=!trimmed.startsWith('//') && trimmed.match(/^(?:@!?%\w+\s+)?([a-z][a-z0-9]*(?:\.[a-z0-9_:]+)*)(?:\s|;|$)/);
    const token=m?.[1],mnemonic=token?.split('.')[0];
    const matches=token && knowledgeData.ptx.records.filter(r=>r.kind==='instruction' && r.mnemonics?.some(m=>token===m || token.startsWith(m+'.')));
    const entry=matches && (matches.find(r=>r.guide && token===r.guide.example.trim().split(/\s+/)[0]) || matches.find(r=>r.anchor.startsWith(token.includes('.f32')?'floating-point-instructions-':'integer-arithmetic-instructions-')) || matches[0]);
    return `<span class="code-line">${esc(line)}${entry?`<button class="code-lookup" data-lookup="${esc(entry.entry_id)}" data-code-line="${esc(trimmed)}" aria-label="查阅 ${esc(mnemonic)}">查 ${esc(mnemonic)}</button>`:''}</span>`;
  }).join('')+'</code></pre>';
}
function ptxSearchResults() {
  const terms=state.query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  return records.filter(r=>terms.every(t=>searchTexts.get(r.id).includes(t)) && compatibilityMatches(r));
}
function searchArticle() {
  const hits=ptxSearchResults();
  return `<h1>搜索结果</h1><p>${hits.length} 项匹配「${esc(state.query)}」；包含主题、指令和手册章节。</p>${hits.length?'<div class="reader-results">'+hits.map(r=>`<button data-open-ptx="${esc(r.id)}"><strong>${esc(r.name)}</strong><span>${esc(r.kind==='lesson'?'学习主题':r.family)}</span></button>`).join('')+'</div>':'<p>没有匹配内容。试试较短的助记符或中文概念。</p><button class="quiet-button" data-reader-home>回到 PTX 全景</button>'}`;
}
function renderPtxReader() {
  readingDetail=false;setProgressActive(false);window.scrollTo(0,0);
  $('#catalog-view').hidden=false;$('#report').hidden=true;$('.toolbar').hidden=false;
  $('#family-section').hidden=true;$('#mobile-family-label').hidden=true;
  if($('#ptx-category-brief'))$('#ptx-category-brief').hidden=true;
  if(lessonViews.includes(state.view)) {
    let r=byId.get(state.selected);
    if(!r || r.kind!=='lesson' || r.knowledge.chapter!==state.view)r=records.find(x=>x.kind==='lesson' && x.knowledge.chapter===state.view);
    state.selected=r.id;
    $('#reader-content').innerHTML=lessonArticle(r.knowledge);
  } else if(state.view==='instruction') {
    let r=byId.get(state.selected);
    if(!r || r.backend!=='ptx' || r.kind==='lesson'){state.view='overview';state.selected='learn_overview';render();return;}
    $('#reader-content').innerHTML=instructionArticle(r);
  } else $('#reader-content').innerHTML=searchArticle();
  $('#page-title').textContent=viewLabels()[state.view];
  syncControls();syncPtxNavigation();saveHash();
  renderReadingLookup();bindReaderActions();
}
function openPtxEntry(id) {
  const r=byId.get(id);if(!r)return;
  Object.assign(state,{view:r.kind==='lesson'?r.knowledge.chapter:'instruction',selected:id,tab:'definition'});
  saveHash(false);render();
  $('#reader-content').setAttribute('tabindex','-1');$('#reader-content').focus({preventScroll:true});
}
function bindReaderActions() {
  const article=$('#reader-content');
  article.querySelectorAll('[data-term]').forEach(b=>b.onclick=()=>{lookupReturn=b;showTerm(b.dataset.term);});
  article.querySelectorAll('[data-open-ptx]').forEach(b=>b.onclick=()=>openPtxEntry(b.dataset.openPtx));
  article.querySelectorAll('[data-next]').forEach(b=>b.onclick=()=>openPtxEntry(b.dataset.next));
  article.querySelectorAll('[data-lookup]').forEach(b=>b.onclick=()=>{lookupReturn=b;renderPtxLookup(byId.get(b.dataset.lookup),b.dataset.codeLine);focusLookup();});
  article.querySelectorAll('[data-jump-cat]').forEach(b=>b.onclick=()=>{state.view='interfaces';state.family=b.dataset.jumpCat;state.selected='';render();});
  article.querySelector('[data-reader-back]')?.addEventListener('click',()=>{state.view='interfaces';render(true);});
  article.querySelector('[data-reader-home]')?.addEventListener('click',()=>{state.view='overview';state.query='';render();});
  article.querySelector('[data-copy-entry]')?.addEventListener('click',()=>copyText(JSON.stringify(ptxExportRecord(byId.get(state.selected)),null,2)));
  article.querySelectorAll('[data-copy-url]').forEach(b=>b.onclick=()=>copyText(location.href));
  article.querySelectorAll('[data-copy-code]').forEach(b=>b.onclick=()=>copyText(byId.get(state.selected).knowledge.sections[Number(b.dataset.copyCode)].code));
}
function lookupShell(title,body) {
  $('#detail').innerHTML=`<div class="detail-heading"><div class="lookup-heading"><h2>${esc(title)}</h2><button id="collapse-lookup" class="text-button" aria-expanded="true">收起</button></div><button id="return-reading" class="text-button">返回正文</button></div><div class="detail-body">${body}</div>`;
  $('#return-reading').onclick=()=>{document.body.classList.remove('lookup-collapsed');(lookupReturn?.isConnected?lookupReturn:$('#reader-content')).focus({preventScroll:true});if(mobile.matches)(lookupReturn?.isConnected?lookupReturn:$('#reader-content')).scrollIntoView({block:'center'});};
  $('#collapse-lookup').onclick=()=>{document.body.classList.add('lookup-collapsed');$('#expand-lookup').focus();};
}
function renderReadingLookup() {
  const r=byId.get(state.selected),k=r?.knowledge;
  lookupShell('随手查',`<p>点击正文中的术语或代码旁的“查”，在这里阅读解释；正文位置保持不变。</p><h3>当前目标</h3><p>NVIDIA B300 · ${esc(state.ptxTarget)}</p><p>文档条件核对，编译与运行未验证。</p>${k?.sections?'<h3>本页内容</h3>'+k.sections.map((s,i)=>`<a class="toc-link" href="#learn-section-${i}" data-section="${i}">${esc(s.title)}</a>`).join(''):''}`);
  $('#detail').querySelectorAll('[data-section]').forEach(a=>a.onclick=e=>{e.preventDefault();$('#learn-section-'+a.dataset.section).scrollIntoView({block:'start'});});
}
function focusLookup() {document.body.classList.remove('lookup-collapsed');$('#detail').focus({preventScroll:true});if(mobile.matches)$('#detail').scrollIntoView({block:'start'});}
function showTerm(id) {
  const t=learning.terms[id];if(!t)return;
  lookupShell(t.name,`<p>${esc(t.definition)}</p><h3>继续阅读</h3>${ptxReferenceLink(t.anchor)}<h3>官方依据</h3>${ptxSources([t.anchor])}`);
  $('#detail').querySelectorAll('[data-open-ptx]').forEach(b=>b.onclick=()=>openPtxEntry(b.dataset.openPtx));focusLookup();
}
function renderPtxLookup(r,line='') {
  if(r.knowledge.concrete_form){renderPTXForm(r);return;}
  const k=r.knowledge, g=k.guide, tax=k.taxonomy;
  const cat=tax && ptxCategories.get(tax.category);
  const exactForm=line && g && line.split(/[\s;]+/)[0]===g.example.trim().split(/[\s;]+/)[0];
  const quals=(g?.qualifiers || []).slice(0,5).map(q=>`<li><code>${esc(q.token)}</code> · ${esc(q.meaning)}</li>`).join('');
  lookupShell(r.name,`${cat?`<p class="muted">${esc(cat.id)} ${esc(cat.title_zh)} · ${esc(tax.granularity)}</p>`:''}${line?'<h3>正文中的这一行</h3><pre><code>'+esc(line)+'</code></pre>':''}${g?`<p><strong>${esc(g.summary)}</strong></p><p>${esc(g.mechanism)}</p>${quals?`<h3>核心修饰符</h3><ul>${quals}</ul>`:''}<h3>${exactForm?'参数解释':'代表性形式'}</h3><pre><code>${esc(g.example)}</code></pre><p>${esc(g.operands)}</p><p class="muted">陷阱：${esc(g.pitfall)}</p>`:'<p>当前形式的逐操作数解释尚未整理。请在完整条目中核对官方语法、限定符与目标条件。</p>'}<p>${esc(state.ptxTarget)}：${esc(supportLabels[assessment(k).support])}</p><button class="quiet-button" id="open-full-entry">在正文阅读完整条目</button><h3>来源</h3>${ptxSources([k.anchor])}`);
  $('#open-full-entry').onclick=()=>openPtxEntry(r.id);
}
function renderPtxReport() {
  const entries=knowledgeData.ptx.records.filter(r=>r.kind==='instruction');
  const counts={};entries.forEach(k=>{const s=assessment(k).support;counts[s]=(counts[s]||0)+1;});
  $('#report').innerHTML=`<h2>PTX 内容与来源</h2><p>主目标：NVIDIA B300 / ${esc(state.ptxTarget)}；固定手册：PTX ISA 9.4。</p><dl class="detail-meta"><dt>手册章节</dt><dd>743</dd><dt>指令条目</dt><dd>221</dd><dt>分类体系</dt><dd>${ptxTaxonomy.domains.length} 个能力域 · ${ptxTaxonomy.categories.length} 个官方 9.7.x 类别</dd><dt>学习主题</dt><dd>${learning.lessons.length}</dd><dt>已提供语法的指令</dt><dd>${entries.filter(k=>k.syntax_detail).length} / 221</dd><dt>已提供深度指南的指令</dt><dd>${entries.filter(k=>k.guide).length} / 221（含机制、修饰符与示例）</dd></dl><h3>当前目标文档判定</h3><p>${Object.entries(counts).map(([s,n])=>`${supportLabels[s]} ${n}`).join(' · ')}</p><p>基础目标、family-specific 与 architecture-specific 功能分别处理。未知和部分形式保留；结果不是逐形式编译证明。</p><h3>来源</h3><p><a href="${esc(learning.sources.device)}" target="_blank" rel="noopener">NVIDIA B300 设备与计算能力表</a></p>${ptxSources(['ptx-module-directives-target'])}<p class="condition">手册 SHA-256 ${esc(knowledgeData.ptx.source.isa.html.sha256)}</p><h3>覆盖边界</h3><p>语法来自固定手册，中文机制解析、修饰符字典与教学程序为原创整理；全文描述未复制入库。所有教学程序均未经编译和设备验证。历史 sm_89 原始快照保留供追溯，不作为当前界面结论。</p>`;
}

function renderPTXForm(r){
 const k=r.knowledge,f=k.concrete_form;
 $('#detail').innerHTML=`<div class="detail-heading"><h2>${esc(r.name)}</h2><p>${esc(r.family)}</p></div><div class="detail-body"><p>${f.evidence.includes('unexpanded_instruction_entry')?'原始指令条目，具体形式尚未展开。':'完整拼写来自 '+esc(f.evidence.join(' / '))+'。'}</p><p>当前形式的目标支持未逐项核验；以下条件属于原始指令条目。</p><h3>官方完整语法</h3><pre><code>${esc(k.syntax_detail?.text || '')}</code></pre>${ptxRules(k)}<h3>来源</h3>${ptxSources([k.anchor])}<p class="condition">${esc(knowledgeData.ptx.forms.source_sha256)}</p></div>`;
}
