"""Conservative, version-scoped analysis of declaration conditions."""
import ast
import re

ARCH = re.compile(r'\b(?:__CCE_AICORE__|__NPU_ARCH__|__DAV_\w+)\b')
GUARD = re.compile(r'^!defined\((?:__CLANG_\w+_H__|__CCE_\w+_H__|CCE_AICORE_INTRINSICS_H)\)$')


def evaluate(expression, macros):
    expression = re.sub(r'/\*.*?\*/|//[^\n]*', '', expression, flags=re.S)
    expression = expression.replace('\\\n', ' ')
    expression = re.sub(r'\bdefined\s*(?:\(\s*(\w+)\s*\)|(\w+))',
                        lambda m: 'True' if (m[1] or m[2]) in macros else 'UNKNOWN', expression)
    expression = expression.replace('&&', ' and ').replace('||', ' or ')
    expression = re.sub(r'!(?!=)', ' not ', expression)
    try:
        tree = ast.parse(expression.strip(), mode='eval')
    except SyntaxError:
        return None

    def visit(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, bool)):
            return node.value
        if isinstance(node, ast.Name):
            return macros.get(node.id)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            value = visit(node.operand)
            return None if value is None else not value
        if isinstance(node, ast.BoolOp):
            values = [visit(x) for x in node.values]
            if isinstance(node.op, ast.And):
                return False if any(x is not None and not x for x in values) else None if None in values else True
            return True if any(x is not None and bool(x) for x in values) else None if None in values else False
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            a, b = visit(node.left), visit(node.comparators[0])
            if a is None or b is None:
                return None
            operations = {ast.Eq: lambda: a == b, ast.NotEq: lambda: a != b,
                          ast.Lt: lambda: a < b, ast.LtE: lambda: a <= b,
                          ast.Gt: lambda: a > b, ast.GtE: lambda: a >= b}
            op = operations.get(type(node.ops[0]))
            return op() if op else None
        return None
    return visit(tree.body)


def analyze(data, targets=()):
    profiles = {}
    guards = {}
    for r in data['records']:
        if r['kind'] == 'macro' and r['signature'].strip() == '#define ' + r['name'] and r['source']['line'] <= 30:
            guards.setdefault(r['source']['file'], set()).add('!defined(' + r['name'] + ')')
    for record in data['records']:
        for condition in record['conditions']:
            for macro, value in re.findall(r'(__CCE_AICORE__|__NPU_ARCH__)\s*(?:==|!=|>=|<=|>|<)\s*(\d+)', condition):
                key = f'{macro}={value}'
                profiles[key] = {'id': key, 'label': f'{macro} = {value}', 'macros': {macro: int(value)}, 'source': record['source']}
            for macro in ARCH.findall(condition):
                if macro.startswith('__DAV_'):
                    profiles[macro] = {'id': macro, 'label': macro, 'macros': {macro: 1}, 'source': record['source']}
    for target in targets:
        key = '__NPU_ARCH__=' + str(target['npu_arch'])
        profiles.setdefault(key, {'id': key, 'label': key, 'macros': {'__NPU_ARCH__': target['npu_arch']}, 'source': target['source']})
    profiles = sorted(profiles.values(), key=lambda x: x['id'])
    deprecated_macros = [r for r in data['records'] if r['kind'] == 'macro' and 'DEPRECATED' in r['name']]
    for record in data['records']:
        conditions = [c for c in record['conditions'] if c.strip() not in guards.get(record['source']['file'], set()) and not GUARD.fullmatch(c.strip())]
        outcomes = {}
        for profile in profiles:
            values = [evaluate(c, profile['macros']) for c in conditions]
            outcomes[profile['id']] = 'excluded' if False in values else 'unknown' if None in values else 'matches'
        signature = record['signature']
        conditional = bool(re.search(r'\bDEPRECATED_AFTER_\w+\b', signature))
        marked = bool(re.search(r'\bDEPRECATED\b|__attribute__\s*\(\(\s*deprecated\b|\[\[\s*deprecated\b', signature))
        record['compatibility'] = {'conditions': conditions, 'profiles': outcomes, 'compile': 'unverified', 'runtime': 'unverified'}
        definitions = [r for r in deprecated_macros if re.search(r'\b' + re.escape(r['name']) + r'\b', signature) and r['source']['file'] == record['source']['file']]
        record['deprecation'] = {'status': 'conditional' if conditional else 'marked' if marked else 'unmarked', 'evidence': signature if marked or conditional else None, 'since': None, 'replacement': None, 'macro_definitions': [{'signature': r['signature'], 'conditions': r['conditions'], 'source': r['source']} for r in definitions]}
    data['compatibility'] = {'revision': 1, 'profiles': profiles, 'scope': 'declaration_conditions_only',
                             'chip_mappings': list(targets), 'versions': [data['version']],
                             'limitations': ['Single-macro scenarios are not chip profiles.', 'Unknown macros stay unknown; unspecified macros are not assumed undefined.', 'Include reachability, body branches and compiler acceptance are not evaluated.', 'Unmarked does not mean not deprecated; first deprecated version is unknown.']}
    return data
