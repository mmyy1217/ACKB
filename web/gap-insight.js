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
      ? rows.map(row => ({name: row.slice(0, 3).join(' '), family: row[5], sources: [], cells: row.slice(0, 5).concat(row[6])}))
      : rows.map(([name, family, kind, , source]) => ({
          name, family, sources: source.split(' / '), cells: sourceFilter ? [name, source, kind] : [name, kind]
        }));
    for (const {family} of records) families.set(family, (families.get(family) || 0) + 1);
    const sources = new Set(records.flatMap(record => record.sources));
    for (const source of Array.from(sources).sort()) {
      sourceFilter?.add(new Option(source, source));
    }
    const nameFilters = [...box.querySelectorAll('[data-name-column]')];
    const fileFilters = [...box.querySelectorAll('[data-source-column]')];
    for (const filter of fileFilters) {
      const index = Number(filter.dataset.sourceColumn);
      const paths = new Set();
      for (const record of records) {
        const files = record.cells[index].split(' / ').filter(Boolean).map(path => path.replace(/:\d+$/, ''));
        (record.files ??= {})[index] = files;
        for (const file of files) paths.add(file);
      }
      for (const path of [...paths].sort()) filter.add(new Option(path, path));
    }
    function display() {
      const term = query.value.trim().toLowerCase();
      const items = records.filter(({name, family, sources, cells, files}) =>
        (!active || family === active) && name.toLowerCase().includes(term) &&
        (!sourceFilter?.value || sources.includes(sourceFilter.value)) &&
        (!matchFilter?.value || cells.at(-1) === matchFilter.value) &&
        nameFilters.every(filter => cells[filter.dataset.nameColumn].toLowerCase().includes(filter.value.trim().toLowerCase())) &&
        fileFilters.every(filter => !filter.value || files[filter.dataset.sourceColumn].includes(filter.value)));
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
    for (const filter of nameFilters) filter.oninput = display;
    for (const filter of fileFilters) filter.onchange = display;
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
