"""Generate the full outer alignment for the pinned A5 insight."""
import json
import re
from collections import Counter
from pathlib import Path

from dialect_gap_snapshot import ROOT, VERSION


def definition_key(name):
    return name.replace('llvm.', 'int_', 1).replace('.', '_')


def overloaded_base(name, registered):
    if name in registered:
        return ''
    base = name
    while '.' in base:
        base = base.rsplit('.', 1)[0]
        if registered.get(base, {}).get('overloaded'):
            return base
    return ''


def call_arity(call, name):
    marker = '@' + name + '('
    if marker not in call:
        return None
    args = call.split(marker, 1)[1]
    depth = 0
    count = 0
    for char in args:
        if char == ')' and depth == 0:
            return count + int(not args.startswith(')'))
        if char in '(<[{':
            depth += 1
        elif char in ')>]}':
            depth -= 1
        elif char == ',' and depth == 0:
            count += 1
    return None


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
        base = overloaded_base(name, registered)
        if base in cann:
            hits.append((base, '注册重载基名'))
        for left, kind in hits or [('', '仅 Dialect')]:
            append(left, name, kind)
    for name in cann.keys() - matched:
        append(name, '', '仅 CANN')
    assert {r[0] for r in rows if r[0]} == set(cann)
    assert {r[1] for r in rows if r[1]} == set(entries)
    assert len({(r[0], r[1]) for r in rows}) == len(rows)
    definitions = json.loads((ROOT / 'data/hivm_defs/index.json').read_text())['records']
    by_name = {record['name']: record for record in definitions}
    ops = {op['name']: op for op in llvm['ops']}
    forms = {f['id']: f for f in llvm['forms']}
    registered_keys = {definition_key(name) for name in registered}
    audit = json.loads((ROOT / 'data/cce_dialect/translation-audit.json').read_text())
    calls = {case['name']: case.get('call', '') for case in audit['cases'] if case['status'] == 'confirmed'}
    used = set()
    aligned = []
    for row in rows:
        left, right = row[:2]
        target = right or left
        base = overloaded_base(target, registered)
        key = definition_key(left or right)
        definition = by_name.get(key)
        relation = '名称对应' if definition else ''
        check = ''
        if definition and right and not left and right not in ops and '_' in right and key in registered_keys:
            definition = None
            relation = ''
            check = '点号与下划线歧义'

        parent = by_name.get(definition_key(base))
        if parent and base:
            suffix = target[len(base) + 1:].split('.')
            constraints = next(f for f in (forms[i] for i in ops[base]['form_ids'])
                               if f['kind'] == 'registry_constraints')
            slots = {int(n) >> 3 for n in re.findall(r'arg_info=(\d+)', constraints['signature'])
                     if int(n) % 8 == 3}
            valid = len(suffix) == len(slots) and all(re.fullmatch(r'v\d+(?:i\d+|f\d+|bf16)', t) for t in suffix)
            observed = cann.get(target, {}).get('identity_status') == 'declaration_observed'
            if observed:
                definition = parent
                relation = '已观测重载实例'
            elif valid and not left and right:
                params = parent['signature'].rsplit(' (', 1)[-1].rstrip(')')
                expected = len(params.split(',')) if params else 0
                actual = call_arity(calls.get(right, ''), right)
                mappings = entries[right]['mappings']
                if actual == expected or (actual is None and any(m.get('operand_count') == expected for m in mappings)):
                    definition = parent
                    relation = 'Dialect 重载实例'
                else:
                    check = '映射参数数待核对'
            elif left == base:
                relation = '注册基名'
                row[5] = '注册重载候选' if valid else '重载后缀不符'
            elif not definition and not valid:
                check = '类型后缀待核对'

        if definition and right:
            params = definition['signature'].rsplit(' (', 1)[-1].rstrip(')')
            arity = len(params.split(',')) if params else 0
            actual = call_arity(calls.get(right, ''), right)
            counts = {m['operand_count'] for m in entries[right]['mappings'] if m.get('operand_count') is not None}
            if actual is not None and actual != arity:
                check = '调用签名冲突'
            elif actual is None and counts and arity not in counts:
                check = '映射参数数待核对'
        if definition:
            used.add(definition['name'])
        aligned.append([definition['name'] if definition else '', *row, relation, check])
    for name in by_name.keys() - used:
        aligned.append([name, '', '', '', '', by_name[name]['family'], '仅定义', '', ''])
    counts = Counter(row[5] for row in aligned)
    rows = sorted(aligned, key=lambda r: (counts[r[5]], r[5], r[1] or r[2] or r[0], r[2], r[0]))
    assert {r[0] for r in rows if r[0]} == set(by_name)
    return {'columns': ['A5 Intrinsic 定义', 'CANN LLVM IR', 'CCE Dialect LLVM', 'CANN 来源', 'Dialect 来源', '指令族', 'LLVM 两列对应方式', '定义关联', '核对结果'],
            'rows': rows}


if __name__ == '__main__':
    print(json.dumps(snapshot(), ensure_ascii=False, separators=(',', ':')))
