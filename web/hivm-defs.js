'use strict';
function definitionRecords() {
  const db = knowledgeData['hivm-defs'];
  return (db?.records || []).map(def => ({
    id: 'def_' + def.name, name: def.name, backend: 'hivm-defs', kind: 'definition',
    group: 'Issue 33', family: def.family, signature: def.signature,
    builtins: [], conditions: [], source: {file: db.source, line: def.row}, def
  }));
}
let hivmDefs = definitionRecords();
function renderDefinition(r) {
  const {def} = r, db = knowledgeData['hivm-defs'];
  const probe = def.probe;
  $('#detail').innerHTML = `<div class="detail-heading"><h2>${esc(def.name)}</h2><p>${esc(def.family)}</p></div>
    <div class="detail-body"><h3>定义签名</h3><pre>${esc(def.signature)}</pre><p>${esc(def.tag)}</p>
    <h3>工作簿探针 · ${esc(db.probe_toolchain)}</h3><p>${esc(probe?.result || '无探针记录')}</p>
    ${probe?.ir ? '<h3>探针记录的 LLVM IR 调用</h3><pre>' + esc(probe.ir) + '</pre>' : ''}
    ${probe?.assembly ? '<h3>探针汇编</h3><pre>' + esc(probe.assembly) + '</pre>' : ''}
    <h3>来源</h3><p>${esc(db.source)} · 全量条目!C${def.row} · 原序号 ${def.number}</p></div>`;
}
function definitionReport() {
  const db = knowledgeData['hivm-defs'];
  $('#report').innerHTML = `<h2>A5 Intrinsic 定义</h2><p>${fmt(db.records.length)} 个定义名来自工作簿「全量条目」C 列，保留原签名、标签及分类。另有 ${db.empty_rows} 行此列为空。</p>
    <p>定义名与 IR 调用描述同一抽象层。泛型定义可有多个具体类型实例。探针结果按原序号和定义名对齐，工具链为 ${esc(db.probe_toolchain)}。CANN 9.3 包内证据独立收录于 LLVM IR 库。</p>
    <p>${esc(db.source)}</p><pre>SHA-256 ${esc(db.sha256)}</pre>`;
}
