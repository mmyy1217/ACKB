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
             if (op['a5_source_lead'] or op['domain'] == 'ordinary_ir')
             and op['identity_status'] != 'candidate_only'}
    rows = []
    domains = {'target_intrinsic': '目标 intrinsic', 'standard_intrinsic': '标准 LLVM intrinsic',
               'ordinary_ir': '普通 IR 阅读模型'}
    for name in sorted(mappings.keys() ^ leads.keys()):
        if name in leads:
            op = leads[name]
            sources = {llvm['sources'][key]['path'].split('/')[-1] if key in llvm['sources'] else 'CCE Dialect'
                       for key, status in op['presence'].items() if status == 'observed'}
            rows.append([name, op['family'], domains[op['domain']], '仅 A5 线索',
                         ' / '.join(sorted(sources)) or 'LLVM LangRef', op['static_target']['call_count'], op['id']])
        else:
            op = mappings[name]
            rows.append([name, op['family'], 'Dialect LLVM 映射', '仅 Dialect', op['source']['file'], None, op['id']])
    return {'dialect': len(mappings), 'a5': len(leads), 'common': len(mappings.keys() & leads.keys()),
            'version': VERSION, 'commit': dialect['source']['commit'], 'rows': rows}


if __name__ == '__main__':
    print(json.dumps(snapshot(), ensure_ascii=False, separators=(',', ':')))
