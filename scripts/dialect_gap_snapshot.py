"""Rebuild the November 22 reverse-mapping insight from the two pinned indices."""
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERSION = '9.3.0~weekly.20261104.01'


def snapshot():
    directory = ROOT / 'data/cce_dialect'
    dialect = json.loads((directory / 'index.json').read_text())
    llvm = json.loads((ROOT / 'data/llvm' / VERSION / 'index.json').read_text())
    dialect['intrinsics'] = [item for item in dialect['intrinsics'] if item['path_status'] == 'confirmed']
    exact = {item['name'] for item in dialect['intrinsics']}
    registered = {op['name'] for op in llvm['ops'] if op.get('registry')}
    overloaded = {op['name'] for op in llvm['ops'] if op.get('registry', {}).get('overloaded')}
    bases = set()
    for name in exact - registered:
        prefix = name
        while '.' in prefix:
            prefix = prefix.rsplit('.', 1)[0]
            if prefix in overloaded:
                bases.add(prefix)
                break
    mapped = exact | bases
    rows = []
    for op in llvm['ops']:
        if not op['a5_source_lead'] or op['domain'] != 'target_intrinsic' or op['name'] in mapped:
            continue
        count = op['static_target']['call_count']
        tier = ('c310 直接调用' if count else '仅 A5 工具字符串'
                if op['identity_status'] == 'candidate_only' else 'A5 工具名称及注册或声明')
        sources = sorted(Path(llvm['sources'][key]['path']).name for key, value in op['presence'].items()
                         if value == 'observed')
        rows.append([op['name'], op['family'], tier, count, ' / '.join(sources), op['id']])
    return {'version': VERSION, 'commit': dialect['source']['commit'], 'rows': rows}


if __name__ == '__main__':
    print(json.dumps(snapshot(), ensure_ascii=False, separators=(',', ':')))
