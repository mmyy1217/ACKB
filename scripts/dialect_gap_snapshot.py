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
    return {'dialect': len(mappings), 'a5': len(leads), 'common': len(mappings.keys() & leads.keys()),
            'dialect_only': len(mappings.keys() - leads.keys()), 'version': VERSION, 'commit': dialect['source']['commit'], 'rows': rows}


if __name__ == '__main__':
    print(json.dumps(snapshot(), ensure_ascii=False, separators=(',', ':')))
