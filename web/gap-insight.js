'use strict';
let gapLoading = false;
async function openGapInsight() {
  const box = document.querySelector('#gap-browser');
  if (gapLoading || box.dataset.ready) return;
  gapLoading = true;
  const message = box.querySelector('#gap-message');
  message.textContent = '正在读取差距列表…';
  try {
    const response = await fetch(box.dataset.url);
    if (!response.ok) throw new Error('snapshot unavailable');
    const {rows} = await response.json();
    const families = new Map();
    for (const [,family] of rows) families.set(family,(families.get(family) || 0)+1);
    const nav = box.querySelector('nav');
    let active = '';
    const query = box.querySelector('input');
    function display() {
      const term = query.value.trim().toLowerCase();
      const items = rows.filter(([name,family]) => (!active || family===active) && name.toLowerCase().includes(term));
      box.querySelector('output').textContent = items.length+' / '+rows.length;
      const body = document.createDocumentFragment();
      for (const [name,,kind] of items) {
        const row = document.createElement('tr');
        for (const text of [name,kind]) row.insertCell().textContent=text;
        body.append(row);
      }
      box.querySelector('tbody').replaceChildren(body);
      box.querySelector('.gap-results').scrollTop=0;
      message.textContent=items.length?'':'没有匹配的名称';
      for (const button of nav.children) button.setAttribute('aria-pressed',String(button.value===active));
    }
    for (const [family,count] of [['',rows.length],...Array.from(families).sort((a,b)=>b[1]-a[1])]) {
      const button = document.createElement('button');
      button.type='button';
      button.value=family;
      button.textContent=(family || '全部指令族')+' · '+count;
      button.onclick=()=>{active=family;display();};
      nav.append(button);
    }
    query.oninput=display;
    display();
    box.dataset.ready='true';
  } catch {
    const retry=document.createElement('button');
    retry.textContent='重新读取';
    retry.onclick=openGapInsight;
    message.replaceChildren('列表读取失败。',retry);
  } finally {
    gapLoading=false;
  }
}
