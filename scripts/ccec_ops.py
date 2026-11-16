#!/usr/bin/env python3
"""Index unique builtin operations separately from declarations and wrappers."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import re

from catalog import ROOT, VERSION, clean, COMMENT
from database import Database, stable_id
from ccec_transfer import transfer_for

OUTPUT = ROOT / 'data' / VERSION / 'ops.json'
BUILTIN = r'__builtin_cce_[A-Za-z0-9_]+'
ALIAS = re.compile(r'clang_builtin_alias\s*\(\s*(' + BUILTIN + r')\s*\)')
CALL = re.compile(r'(?<![\w#])(' + BUILTIN + r')\s*\(')
QUALIFIED = re.compile(r'\b(__cce_[A-Za-z0-9_]+)\s*::\s*([A-Za-z_]\w*)\s*\(')
LIMITS = ['Builtin identity is not a hardware opcode or a complete compiler inventory.',
          'Typed declaration forms are lexical, not C++ canonical overload identities.',
          'Wrapper body references retain branches as text; no overload or control-flow resolution.',
          'Name-only AscendC references are not transferred into op architecture support.',
          'Declaration visibility, compiler acceptance and runtime support are separate.']


def build_model(db):
    ops, layers, edges, pending = {}, {}, [], []
    aliases = defaultdict(set)

    def op(name, record):
        if name not in ops:
            ops[name] = {'id': 'ccec_op_' + name, 'builtin': name, 'name': name.removeprefix('__builtin_cce_'),
                         'entry_records': [], 'caller_records': [], 'forms': [], 'aliases': [],
                         'group': record['group'], 'family': record['family'], 'transfer': transfer_for(name)}
        return ops[name]

    interfaces = [r for r in db.records if r['kind'].startswith('interface')]
    for r in interfaces:
        alias = ALIAS.search(r['signature'])
        if alias:
            name = alias[1]
            item = op(name, r)
            item['entry_records'].append(r['id'])
            qualified = (r.get('namespace') + '::' if r.get('namespace') else '::') + r['name']
            item['aliases'].append(qualified)
            aliases[qualified].add(name)
            layers[r['id']] = {'layer': 'intrinsic_entry', 'op_ids': [item['id']]}
            edges.append({'source_record': r['id'], 'target_op': item['id'], 'kind': 'builtin_alias',
                          'resolution': 'explicit_attribute', 'conditions': r['conditions']})
            # Names/default expressions remain intact: do not invent canonical overloads.
            if r.get('parameters') != ['...']:
                shape = [r.get('return_type'), r.get('template'), r.get('parameters')]
                form_id = stable_id('form_', [name, shape])
                form = next((f for f in item['forms'] if f['id'] == form_id), None)
                if form is None:
                    form = {'id': form_id, 'signature': r['signature'], 'record_ids': []}
                    item['forms'].append(form)
                form['record_ids'].append(r['id'])
        else:
            has_body = '{' in r.get('definition', '') or r['kind'] == 'interface_macro'
            layers[r['id']] = {'layer': 'wrapper' if has_body else 'unresolved_entry', 'op_ids': []}
    for r in interfaces:
        if layers[r['id']]['layer'] == 'intrinsic_entry':
            continue
        definition = COMMENT.sub(lambda m: ' ' * len(m[0]), clean(r.get('definition', '')))
        body = definition[definition.find('{') + 1:] if '{' in definition else definition
        found = set()
        for m in CALL.finditer(body):
            name = m[1]
            if re.search(r'##\s*$', body[:m.start()]):
                continue
            found.add((name, 'direct_builtin_call', name))
        for m in QUALIFIED.finditer(body):
            qualified = m[1] + '::' + m[2]
            targets = aliases.get(qualified, set())
            if len(targets) == 1:
                found.add((next(iter(targets)), 'qualified_intrinsic_reference', qualified))
            else:
                pending.append({'record_id': r['id'], 'reference': qualified,
                                'reason': 'ambiguous_alias' if targets else 'no_alias_declaration'})
        for name, kind, spelling in sorted(found):
            item = op(name, r)
            item['caller_records'].append(r['id'])
            layers[r['id']]['op_ids'].append(item['id'])
            edges.append({'source_record': r['id'], 'target_op': item['id'], 'kind': kind,
                          'reference': spelling, 'resolution': 'lexical_body_reference',
                          'conditions': r['conditions'], 'body_conditions': 'preserved_in_source_not_evaluated'})
        if not found:
            pending.append({'record_id': r['id'], 'reason': 'no_resolved_builtin_identity'})
    for item in ops.values():
        for key in ('entry_records', 'caller_records', 'aliases'):
            item[key] = sorted(set(item[key]))
        item['identity_evidence'] = 'explicit_alias' if item['entry_records'] else 'literal_builtin_call'
        item['signature_status'] = 'typed_declarations' if item['forms'] else 'unspecified'
    identified = set(ops)
    candidates = [{'name': name, 'reason': 'raw_name_without_alias_or_literal_call'}
                  for name in db.data['report']['raw_builtin_names'] if name not in identified]
    return {'schema_version': 'ackb.ccec-ops.v1', 'version': db.data['version'],
            'catalog_sha256': db.snapshot_sha256, 'generator_sha256': hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes()).hexdigest(),
            'ops': sorted(ops.values(), key=lambda r: r['builtin']), 'record_layers': layers,
            'edges': edges, 'unresolved': pending, 'builtin_candidates': candidates,
            'counts': {'ops': len(ops), 'interface_records': len(interfaces),
                       'layers': dict(Counter(v['layer'] for v in layers.values())),
                       'edges': len(edges), 'unresolved': len(pending), 'builtin_candidates': len(candidates)},
            'limitations': LIMITS}


def validate(model, db):
    assert model['catalog_sha256'] == db.snapshot_sha256, 'Stale op source snapshot'
    assert model['version'] == db.data['version'], 'Wrong op version'
    ids = {o['id'] for o in model['ops']}
    assert len(ids) == len(model['ops']) == len({o['builtin'] for o in model['ops']}), 'Duplicate op identity'
    assert set(model['record_layers']) == {r['id'] for r in db.records if r['kind'].startswith('interface')}, 'Incomplete layer coverage'
    for edge in model['edges']:
        assert edge['source_record'] in db.by_id and edge['target_op'] in ids, 'Dangling relation'
    for o in model['ops']:
        assert o['entry_records'] or o['caller_records'], 'Op without evidence'
        for rid in o['entry_records']:
            assert ALIAS.search(db.by_id[rid]['signature'])[1] == o['builtin'], 'False alias mapping'
    return True


def assessment(op, db, target):
    values = [db.condition(db.by_id[rid], target) for rid in op['entry_records']]
    status = ('not_evaluated' if not target['profile'] else 'matches' if 'matches' in values
              else 'unknown' if not values or 'unknown' in values else 'excluded')
    return {'condition': status, 'basis': 'explicit_entry_declarations_only',
            'entry_conditions': [{'record_id': rid, 'condition': db.condition(db.by_id[rid], target)} for rid in op['entry_records']],
            'support': 'unverified', 'wrapper_support_inherited': False}


class Ops:
    def __init__(self, db=None):
        self.db = db or Database()
        self.model = build_model(self.db)
        self.by_id = {o['id']: o for o in self.model['ops']}

    def summary(self, op, target):
        return {k: op[k] for k in ('id', 'name', 'builtin', 'aliases', 'group', 'family', 'identity_evidence', 'signature_status')} | {
            'transfer': op['transfer'],
            'typed_declaration_forms': len(op['forms']), 'entry_declarations': len(op['entry_records']),
            'caller_declarations': len(op['caller_records']), 'assessment': assessment(op, self.db, target)}

    def relations(self, identity):
        return [e for e in self.model['edges'] if e['target_op'] == identity or e['source_record'] == identity]

    def detail(self, op, target):
        return self.summary(op, target) | {'forms': op['forms'], 'entry_record_ids': op['entry_records'],
                                         'caller_record_ids': op['caller_records'],
                                         'relation_query': 'relations ' + op['id']}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['build', 'validate'], default='build', nargs='?')
    args = p.parse_args()
    db = Database()
    model = build_model(db) if args.command == 'build' else json.loads(OUTPUT.read_text())
    validate(model, db)
    if args.command == 'build':
        OUTPUT.write_text(json.dumps(model, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(json.dumps(model['counts'], ensure_ascii=False, indent=2))
