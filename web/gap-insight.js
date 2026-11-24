'use strict';
async function openGapInsight(box) {
  if (box.dataset.loading || box.dataset.ready) return;
  box.dataset.loading = 'true';
  const message = box.querySelector('[role=status]');
  message.textContent = '正在读取差距列表…';
  try {
    const response = await fetch(box.dataset.url);
    if (!response.ok) throw new Error('snapshot unavailable');
    const {rows, columns} = await response.json();
    const families = new Map();
    const nav = box.querySelector('nav');
    let active = '';
    const query = box.querySelector('input');
    const sourceFilter = box.querySelector('#gap-source');
    const matchFilter = box.querySelector('[data-match-filter]');
    const records = columns
      ? rows.map(row => ({name: row.slice(0, 2).join(' '), family: row[4], sources: [], cells: row.slice(0, 4).concat(row[5])}))
      : rows.map(([name, family, kind, , source]) => ({
          name, family, sources: source.split(' / '), cells: sourceFilter ? [name, source, kind] : [name, kind]
        }));
    for (const {family} of records) families.set(family, (families.get(family) || 0) + 1);
    const sources = new Set(records.flatMap(record => record.sources));
    for (const source of Array.from(sources).sort()) {
      sourceFilter?.add(new Option(source, source));
    }
    function display() {
      const term = query.value.trim().toLowerCase();
      const items = records.filter(({name, family, sources, cells}) =>
        (!active || family === active) && name.toLowerCase().includes(term) &&
        (!sourceFilter?.value || sources.includes(sourceFilter.value)) &&
        (!matchFilter?.value || cells[4] === matchFilter.value));
      box.querySelector('output').textContent = items.length+' / '+rows.length;
      const body = document.createDocumentFragment();
      for (const {cells} of items) {
        const row = document.createElement('tr');
        for (const text of cells) row.insertCell().textContent=text;
        body.append(row);
      }
      box.querySelector('tbody').replaceChildren(body);
      box.querySelector('.gap-results').scrollTop=0;
      message.textContent=items.length?'':'没有匹配的名称';
      for (const button of nav.children) button.setAttribute('aria-pressed',String(button.value===active));
    }
    for (const [family,count] of [['',rows.length],...Array.from(families).sort((a,b)=>columns ? a[1]-b[1] : b[1]-a[1])]) {
      const button = document.createElement('button');
      button.type='button';
      button.value=family;
      button.textContent=(family || '全部指令族')+' · '+count;
      button.onclick=()=>{active=family;display();};
      nav.append(button);
    }
    if (sourceFilter) sourceFilter.onchange=display;
    if (matchFilter) matchFilter.onchange=display;
    query.oninput=display;
    display();
    box.dataset.ready='true';
  } catch {
    const retry=document.createElement('button');
    retry.textContent='重新读取';
    retry.onclick=()=>openGapInsight(box);
    message.replaceChildren('列表读取失败。',retry);
  } finally {
    delete box.dataset.loading;
  }
}
