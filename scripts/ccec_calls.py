#!/usr/bin/env python3
"""Recover observed transfer calls from pinned, explicitly selected A5 source branches."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

from catalog import ROOT, VERSION, COMMENT, tokens, split_args, pretty
from database import Database, stable_id
from ccec_support import Support
from ccec_static import architecture_routes, conditions_result, file_guards
from ccec_transfer import transfer_for

OUTPUT = ROOT / 'data' / VERSION / 'a5-calls.json'
TOOLKIT = Path('/home/zuomin/Ascend/cann-weekly-9.3.0-20261104.01/cann-9.3.0')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def closing(text, start, left='(', right=')'):
    depth = 0
    for i in range(start, len(text)):
        if text[i] == left:
            depth += 1
        elif text[i] == right:
            depth -= 1
            if not depth:
                return i
    raise ValueError('Unclosed delimiter')


def functions(text):
    result = []
    for m in re.finditer(r'\b__aicore__\s+inline\s+([\w:*<>]+)\s+([\w:<>]+)\s*\(', text):
        end = closing(text, m.end() - 1)
        body_start = end + 1
        while body_start < len(text) and text[body_start].isspace():
            body_start += 1
        if body_start >= len(text) or text[body_start] != '{':
            continue
        body_end = closing(text, body_start, '{', '}')
        parameters = [pretty(p) for p in split_args(tokens(text[m.end():end]))]
        bindings = {}
        for parameter in parameters:
            declaration = parameter.split('=')[0].strip()
            name = re.search(r'([A-Za-z_]\w*)\s*$', declaration)
            if name:
                bindings[name[1]] = declaration[:name.start()].strip()
        result.append({'name': m[2], 'signature': text[m.start():end + 1], 'parameters': parameters,
                       'bindings': bindings, 'start': m.start(), 'body_start': body_start, 'end': body_end})
    return result


def argument_evidence(expression, bindings, local_declarations=None):
    expression = pretty(tokens(expression))
    if expression in bindings:
        return {'expression': expression, 'observed_type': bindings[expression], 'type_basis': 'caller_parameter'}
    local_declarations = local_declarations or {}
    if expression in local_declarations:
        declarations = local_declarations[expression]
        types = {d['type'] for d in declarations}
        if len(types) == 1:
            return {'expression': expression, 'observed_type': next(iter(types)),
                    'type_basis': 'local_declaration', 'declarations': declarations}
    cast = re.match(r'(?:reinterpret_cast|static_cast)\s*<\s*([^<>]+)\s*>', expression)
    if not cast:
        cast = re.match(r'^\(\s*([^()]+\*)\s*\)', expression)
    if cast:
        return {'expression': expression, 'observed_type': cast[1].strip(), 'type_basis': 'explicit_cast'}
    if expression in ('true', 'false'):
        return {'expression': expression, 'observed_type': 'bool', 'type_basis': 'literal'}
    if re.fullmatch(r'\d+', expression):
        return {'expression': expression, 'observed_type': 'int', 'type_basis': 'literal'}
    return {'expression': expression, 'observed_type': None, 'type_basis': 'unresolved_expression'}


def block_guards(text, start, position):
    result = []
    for m in re.finditer(r'\bif\s+(?:constexpr\s*)?(?:\([^{};]*\)|ASC(?:END)?_IS_AI[CV])\s*\{', text[start:position]):
        brace = start + m.end() - 1
        if closing(text, brace, '{', '}') >= position:
            result.append(m[0][:-1].strip())
    return result


def resolved_routes(support):
    data = dict(support.data)
    edges = []
    for edge in data['includes']:
        edge = dict(edge)
        if not edge['resolved_relative_path']:
            candidates = [prefix + edge['name'] for prefix in ('x86_64-linux/asc/', 'x86_64-linux/asc/include/')]
            matches = [f for f in candidates if f in data['files']]
            if len(matches) == 1:
                edge['resolved_relative_path'] = matches[0]
        edges.append(edge)
    data['includes'] = edges
    return data, architecture_routes(data, 3510)


def extract(toolkit=TOOLKIT):
    from ccec_ops import Ops
    db = Database()
    support = Support(db=db)
    model = Ops(db).model
    aliases = defaultdict(list)
    for r in db.records:
        if model['record_layers'].get(r['id'], {}).get('layer') == 'intrinsic_entry' and transfer_for(r['name']):
            aliases[r['name']].append(r)
    route_data, routes = resolved_routes(support)
    refs = defaultdict(list)
    for ref in support.data['references']:
        if ref['name'] in aliases:
            refs[ref['file']].append(ref)
    selected = sorted(f for f in refs if routes.get(f, {}).get('state') is True
                      and ('/npu_arch_3510/' in f or '/dav_3510/' in f))
    calls, issues, files, candidates = [], [], {}, 0
    pattern = re.compile(r'(?<![\w])(' + '|'.join(map(re.escape, sorted(aliases, key=len, reverse=True))) + r')\s*\(')
    for file in selected:
        path = toolkit / file
        meta = support.data['files'][file]
        if sha(path) != meta['sha256']:
            raise ValueError('Source changed: ' + file)
        raw = path.read_text()
        text = COMMENT.sub(lambda m: re.sub(r'[^\n]', ' ', m[0]), raw)
        # String contents cannot contribute a call or disrupt balanced braces.
        text = re.sub(r'"(?:\\.|[^"\\])*"', lambda m: re.sub(r'[^\n]', ' ', m[0]), text)
        funcs = functions(text)
        files[file] = {'sha256': meta['sha256'], 'package_verified': bool(support.package_proof),
                       'architecture_selector_path': []}
        for i in routes[file]['edges']:
            edge = route_data['includes'][i]
            if sha(toolkit / edge['file']) != support.data['files'][edge['file']]['sha256']:
                raise ValueError('Selector source changed: ' + edge['file'])
            files[file]['architecture_selector_path'].append({**edge, 'sha256': support.data['files'][edge['file']]['sha256']})
        for m in pattern.finditer(text):
            candidates += 1
            line = text.count('\n', 0, m.start()) + 1
            location = {'file': file, 'line': line}
            fn = next((f for f in funcs if f['body_start'] < m.start() < f['end']), None)
            if fn is None:
                issues.append({**location, 'name': m[1], 'reason': 'not_in_parsed_function_body'})
                continue
            entry = aliases[m[1]]
            op_ids = {oid for r in entry for oid in model['record_layers'][r['id']]['op_ids']}
            if len(op_ids) != 1:
                issues.append({**location, 'name': m[1], 'reason': 'ambiguous_alias_identity'})
                continue
            end = closing(text, m.end() - 1)
            arguments = [pretty(x) for x in split_args(tokens(text[m.end():end]))]
            reference = next((r for r in refs[file] if r['line'] == line and r['name'] == m[1]), None)
            if reference is None:
                issues.append({**location, 'name': m[1], 'reason': 'missing_preprocessor_reference'})
                continue
            conditions = reference['conditions']
            state = conditions_result(conditions, 3510, file_guards(meta))
            locals_here = defaultdict(list)
            prefix = text[fn['body_start']:m.start()]
            for declaration in re.finditer(r'\b((?:const\s+)?(?:u?int(?:8|16|32|64)_t|bool|float|double))\s+(\w+)\s*(?:=[^;]*|)\s*;', prefix):
                locals_here[declaration[2]].append({'type': declaration[1], 'text': declaration[0].strip(),
                    'line': text.count('\n', 0, fn['body_start'] + declaration.start()) + 1})
            call = {'id': stable_id('ccec_call_', [file, line, m[1], arguments]), 'name': m[1],
                    'op_id': next(iter(op_ids)), 'entry_record_ids': [r['id'] for r in entry],
                    'argument_count': len(arguments),
                    'arguments': [argument_evidence(a, fn['bindings'], locals_here) for a in arguments],
                    'caller': {'name': fn['name'], 'signature': fn['signature'], 'parameters': fn['parameters'],
                               'line': text.count('\n', 0, fn['start']) + 1},
                    'source': {**location, 'end_line': text.count('\n', 0, end) + 1},
                    'expression': raw[m.start():end + 1], 'conditions': conditions,
                    'condition_result': 'matches' if state is True else 'unknown' if state is None else 'excluded',
                    'block_guards': block_guards(text, fn['body_start'], m.start()),
                    'resolution': 'unique_alias_spelling_not_cpp_overload_resolution',
                    'formal_signature': 'unverified', 'compile': 'unverified', 'runtime': 'unverified'}
            direction = transfer_for(m[1])
            spaces = []
            for argument in call['arguments'][:2]:
                space = re.search(r'__(gm|ubuf|cbuf)__', argument['observed_type'] or '')
                spaces.append(space[1] if space else None)
            call['transfer_check'] = {'expected_destination': direction['destination'],
                                      'expected_source': direction['source'], 'observed_address_spaces': spaces,
                                      'status': 'agrees' if spaces == [direction['destination'], direction['source']]
                                      else 'unknown' if None in spaces else 'conflict'}
            calls.append(call)
    wrapper_names = {r['name'] for r in db.records if model['record_layers'].get(r['id'], {}).get('layer') == 'wrapper'
                     and db.condition(r, db.target(chip='Ascend950PR_9579')) == 'matches'}
    direct = sorted({i for c in calls if c['condition_result'] == 'matches' and c['name'] not in wrapper_names
                     for i in c['entry_record_ids'] if db.condition(db.by_id[i], db.target(chip='Ascend950PR_9579')) == 'matches'})
    result = {'schema_version': 'ackb.ccec-calls.v1', 'version': VERSION, 'chip': 'Ascend950PR_9579',
              'catalog_sha256': db.snapshot_sha256, 'source_evidence_sha256': sha(support.path),
              'generator_sha256': sha(Path(__file__)), 'files': files, 'calls': calls,
              'direct_entry_ids': direct, 'issues': issues,
              'coverage': {'files': len(files), 'candidates': candidates, 'parsed_calls': len(calls),
                           'unresolved': len(issues), 'entries': len({c['name'] for c in calls}),
                           'added_direct_entries': len(direct)},
              'scope': 'Explicit 3510 include routes; transfer names with GM/UB/L1 endpoints in AscendC implementations.',
              'limitations': ['Observed argument types are not compiler formal parameter types.',
                              'Unique alias spelling does not resolve C++ lookup or overloads.',
                              'Runtime/core/template guards are preserved, not evaluated.',
                              'A5 source use does not prove compiler or device support.']}
    validate(result, db)
    return result


def validate(data, db):
    assert data['catalog_sha256'] == db.snapshot_sha256, 'Stale call catalog'
    assert data['source_evidence_sha256'] == sha(OUTPUT.with_name('support-evidence.json')), 'Stale call source'
    assert data['version'] == db.data['version']
    assert data['generator_sha256'] == sha(Path(__file__)), 'Stale call extractor'
    assert data['coverage']['files'] == len(data['files'])
    assert data['coverage']['parsed_calls'] == len(data['calls'])
    assert data['coverage']['unresolved'] == len(data['issues'])
    assert data['coverage']['entries'] == len({c['name'] for c in data['calls']})
    target = db.target(chip='Ascend950PR_9579')
    observed_entries = {i for c in data['calls'] if c['condition_result']=='matches' for i in c['entry_record_ids']}
    assert set(data['direct_entry_ids']) <= observed_entries
    assert all(db.condition(db.by_id[i], target)=='matches' for i in data['direct_entry_ids'])
    assert len({c['id'] for c in data['calls']}) == len(data['calls'])
    assert data['coverage']['candidates'] == len(data['calls']) + len(data['issues'])
    for c in data['calls']:
        assert c['argument_count'] == len(c['arguments'])
        assert all(i in db.by_id for i in c['entry_record_ids'])
        for i in c['entry_record_ids']:
            entry = db.by_id[i]
            assert entry['name'] == c['name']
            alias = re.search(r'clang_builtin_alias\s*\(\s*(__builtin_cce_\w+)\s*\)', entry['signature'])
            assert alias and c['op_id'] == 'ccec_op_' + alias[1]
        assert data['files'][c['source']['file']]['architecture_selector_path']


def load_calls(db):
    if db.source.resolve() != (ROOT / 'data' / VERSION / 'catalog.json').resolve() or not OUTPUT.exists():
        return {'calls': [], 'files': {}, 'direct_entry_ids': [], 'coverage': {}, 'issues': []}
    data = json.loads(OUTPUT.read_text())
    validate(data, db)
    return data


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['extract', 'validate'])
    p.add_argument('--toolkit', type=Path, default=TOOLKIT)
    args = p.parse_args()
    result = extract(args.toolkit) if args.command == 'extract' else load_calls(Database())
    if args.command == 'extract':
        OUTPUT.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(json.dumps(result['coverage'], ensure_ascii=False))
