"""Calculate the exact-name difference for the dated LLVM insight."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = '9.3.0~weekly.20261104.01'


def snapshot():
    dialect = json.loads((ROOT / 'data/cce_dialect/index.json').read_text())
    llvm = json.loads((ROOT / 'data/llvm' / VERSION / 'index.json').read_text())
    mappings = {op['name']: op for op in dialect['intrinsics']}
    leads = {op['name']: op for op in llvm['ops']
             if op['a5_source_lead']
             and op['identity_status'] != 'candidate_only'}
    rows = []
    domains = {'target_intrinsic': '目标 intrinsic', 'standard_intrinsic': '标准 LLVM intrinsic',
               'ordinary_ir': '普通 IR 阅读模型'}
    for name in sorted(leads.keys() - mappings.keys()):
        op = leads[name]
        sources = sorted({Path(llvm['sources'][sid]['path']).name
                          for sid, status in op['presence'].items() if status == 'observed'})
        if not sources:
            raise ValueError(f'Missing CANN provenance: {name}')
        rows.append([name, op['family'], domains[op['domain']], '仅 A5 线索',
                     ' / '.join(sources), op['static_target']['call_count'], op['id']])
    package = {op['name']: op for op in llvm['ops']}
    review = json.loads((ROOT / 'web/insights/files/dialect-lowering-review.json').read_text())
    if review['commit'] != dialect['source']['commit'] or review['version'] != VERSION:
        raise ValueError('Lowering review version mismatch')
    matches = []
    for name, mapping in sorted(mappings.items()):
        op = package.get(name)
        sources = sorted(Path(llvm['sources'][sid]['path']).name for sid, status in
                         (op['presence'].items() if op else []) if status == 'observed')
        if name in leads:
            status = 'A5 默认范围命中'
        elif op is None:
            status = '扫描范围未见同名'
        elif op['identity_status'] == 'candidate_only':
            status = '仅字符串'
        else:
            status = '跨架构注册'
        matches.append([name, mapping['family'], status, ', '.join(mapping['op_keys']),
                        ' / '.join(sources), mapping['source']['file'], mapping['source']['line']])
    notes = dict(review['review'])
    notes.update({name: 'C++ 完整名称引用' for name in review['cpp_literals']})
    return {'dialect': len(mappings), 'a5': len(leads), 'common': len(mappings.keys() & leads.keys()),
            'dialect_only': len(mappings.keys() - leads.keys()), 'version': VERSION, 'commit': dialect['source']['commit'], 'rows': rows, 'matches': matches, 'notes': notes}


if __name__ == '__main__':
    print(json.dumps(snapshot(), ensure_ascii=False, separators=(',', ':')))
