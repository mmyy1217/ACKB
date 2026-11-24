"""Generate the full outer alignment for the pinned A5 insight."""
import json
from collections import Counter
from pathlib import Path

from dialect_gap_snapshot import ROOT, VERSION


def snapshot():
    llvm = json.loads((ROOT / 'data/llvm' / VERSION / 'index.json').read_text())
    dialect = json.loads((ROOT / 'data/cce_dialect/index.json').read_text())
    cann = {op['name']: op for op in llvm['ops']
            if op['a5_source_lead'] and op['identity_status'] != 'candidate_only'}
    entries = {op['name']: op for op in dialect['intrinsics'] if op['path_status'] == 'confirmed'}
    registered = {op['name']: op['registry'] for op in llvm['ops'] if op.get('registry')}
    rows = []
    matched = set()

    def append(left, right, kind):
        op = cann.get(left, {})
        entry = entries.get(right, {})
        files = [Path(llvm['sources'][key]['path']).name for key, status in op.get('presence', {}).items()
                 if status == 'observed']
        refs = [entry['source']] + [m['source'] for m in entry['mappings']] if entry else []
        locations = sorted({f"{ref['file']}:{ref['line']}" for ref in refs})
        rows.append([left, right, ' / '.join(sorted(files)), ' / '.join(locations),
                     op.get('family') or entry['family'], kind])
        if left:
            matched.add(left)

    for name in sorted(entries):
        hits = []
        if name in cann:
            hits.append((name, '完整同名'))
        if name not in registered:
            base = name
            while '.' in base:
                base = base.rsplit('.', 1)[0]
                if registered.get(base, {}).get('overloaded'):
                    if base in cann:
                        hits.append((base, '注册重载基名'))
                    break
        for left, kind in hits or [('', '仅 Dialect')]:
            append(left, name, kind)
    for name in cann.keys() - matched:
        append(name, '', '仅 CANN')
    counts = Counter(row[4] for row in rows)
    rows.sort(key=lambda r: (counts[r[4]], r[4], r[0] or r[1], r[1]))
    assert {r[0] for r in rows if r[0]} == set(cann)
    assert {r[1] for r in rows if r[1]} == set(entries)
    assert len({(r[0], r[1]) for r in rows}) == len(rows)
    return {'columns': ['CANN LLVM IR', 'CCE Dialect LLVM', 'CANN 来源', 'Dialect 来源', '指令族', '对应方式'],
            'rows': rows}


if __name__ == '__main__':
    print(json.dumps(snapshot(), ensure_ascii=False, separators=(',', ':')))
