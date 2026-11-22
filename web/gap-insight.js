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
    const snapshot = await response.json();
    const direction = box.querySelector('#gap-direction');
    function activate() {
      const reverse = direction.value === 'match';
      const rows = reverse ? snapshot.matches : snapshot.rows;
      const headers = box.querySelectorAll('th');
      headers[0].textContent = reverse ? 'LLVM 名称 / Dialect 操作键' : 'LLVM 名称';
      headers[2].textContent = reverse ? '包内命中' : '类型 / lowering 复核';
      const families = new Map();
      for (const [,family] of rows) families.set(family,(families.get(family) || 0)+1);
      const nav = box.querySelector('nav');
      nav.replaceChildren();
      let active = '';
      const query = box.querySelector('input');
      const sourceFilter = box.querySelector('#gap-source');
      sourceFilter.replaceChildren(new Option('全部', ''));
      const records = rows.map(([name, family, kind, key, source, file, line]) => ({
        name, family, kind: reverse ? kind : [kind, snapshot.notes[name]].filter(Boolean).join(' · '),
        key: reverse ? key : '', location: reverse ? file + ':' + line : '',
        sources: source ? source.split(' / ') : ['未见同名']
      }));
      const sources = new Set(records.flatMap(record => record.sources));
      for (const source of Array.from(sources).sort()) {
        sourceFilter.add(new Option(source, source));
      }
      function display() {
        const term = query.value.trim().toLowerCase();
        const items = records.filter(({name, family, sources, key}) =>
          (!active || family === active) && (name + ' ' + key).toLowerCase().includes(term) &&
          (!sourceFilter.value || sources.includes(sourceFilter.value)));
        box.querySelector('output').textContent = items.length+' / '+rows.length;
        const body = document.createDocumentFragment();
        for (const {name, kind, sources, key, location} of items) {
          const row = document.createElement('tr');
          const symbol = row.insertCell();
          symbol.textContent = name;
          if (key) {
            const detail = document.createElement('small');
            detail.textContent = key + ' · ' + location;
            symbol.append(document.createElement('br'), detail);
          }
          row.insertCell().textContent = sources.join(' / ');
          row.insertCell().textContent = kind;
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
      sourceFilter.onchange=display;
      query.oninput=display;
      display();
    }
    direction.onchange = activate;
    activate();
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
