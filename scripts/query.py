#!/usr/bin/env python3
"""Bounded JSON queries for agents; no compiler execution or network access."""
import argparse
import contextlib
import io
import hashlib
import json
import sys

from catalog import ROOT, validate
from database import Database, SCHEMA_VERSION
from knowledge import Knowledge, PROTOCOL

LIMITATIONS = ['Declaration conditions are not chip support.',
               'Core macro environments and compiler acceptance are unverified.',
               'Call edges are name references, not resolved overload calls.',
               'Signature variants are lexical, not C++ canonical overload identities.']


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def parser():
    p = Parser(description=__doc__)
    p.add_argument('--backend', choices=['ccec', 'ascendc', 'cce-dialect', 'ptx'], default='ccec')
    p.add_argument('--layer', choices=['declarations', 'ops', 'basic', 'capi', 'intrinsics'])
    p.add_argument('--data', help='Versioned catalog path; defaults to the repository snapshot')
    p.add_argument('--limit', type=int, default=10)
    p.add_argument('--offset', type=int, default=0)
    p.add_argument('--max-chars', type=int, default=24000)
    commands = p.add_subparsers(dest='command', required=True, parser_class=Parser)
    commands.add_parser('info')
    forms = commands.add_parser('forms')
    forms.add_argument('identity')
    commands.add_parser('unresolved')
    schema = commands.add_parser('schema')
    schema.add_argument('--layer', choices=['declarations', 'ops', 'calls', 'basic', 'capi', 'intrinsics'], default='declarations')
    for operation in ('topics', 'builtins', 'categories'):
        topic = commands.add_parser(operation)
        topic.add_argument('query', nargs='?', default='')
        topic.add_argument('--architecture')
    interface = commands.add_parser('interfaces')
    interface.add_argument('--name', default='')
    interface.add_argument('--include-unknown', action='store_true')
    calls = commands.add_parser('calls')
    calls.add_argument('identity', help='CCEC op ID, entry record ID or exact entry name')
    ops = commands.add_parser('ops')
    ops.add_argument('query', nargs='?', default='')
    ops.add_argument('--name')
    ops.add_argument('--chip')
    ops.add_argument('--architecture')
    ops.add_argument('--core')
    ops.add_argument('--condition', choices=['matches', 'excluded', 'unknown', 'possible'], default='matches')
    targets = commands.add_parser('targets')
    targets.add_argument('--name', default='')
    for command in ('search', 'get', 'relations', 'support'):
        sub = commands.add_parser(command)
        if command != 'search':
            sub.add_argument('identity')
        else:
            sub.add_argument('query', nargs='?', default='')
        sub.add_argument('--name')
        sub.add_argument('--builtin')
        sub.add_argument('--signature')
        sub.add_argument('--kind', choices=['all', 'interface', 'type', 'macro', 'constant', 'helper', 'instruction', 'instruction_topic', 'execution_model', 'state_space', 'directive', 'special_register'], default='interface' if command == 'search' else 'all')
        sub.add_argument('--support', choices=['documented_supported', 'documented_not_supported', 'partial', 'unknown'])
        sub.add_argument('--category')
        sub.add_argument('--chip')
        sub.add_argument('--architecture')
        sub.add_argument('--core')
        sub.add_argument('--condition', choices=['matches', 'excluded', 'unknown', 'possible'])
        sub.add_argument('--deprecation', choices=['marked', 'conditional', 'unmarked'])
    evidence = commands.add_parser('evidence')
    evidence.add_argument('identity', help='Exact versioned record ID')
    evidence.add_argument('--field', choices=['excerpt', 'definition'], default='excerpt')
    return p


def page(items, args, context):
    selected = items[args.offset:args.offset + args.limit]
    response = {'schema_version': SCHEMA_VERSION, **context, 'total': len(items), 'offset': args.offset,
                'items': selected, 'next_offset': None, 'truncated': False}
    while selected and len(json.dumps(response, ensure_ascii=False)) + 200 > args.max_chars:
        selected.pop()
    if not selected and args.offset < len(items):
        raise ValueError('One result exceeds max-chars; increase the budget or use a narrower query')
    end = args.offset + len(selected)
    response['next_offset'] = end if end < len(items) else None
    response['truncated'] = end < len(items)
    if len(json.dumps(response, ensure_ascii=False)) > args.max_chars:
        raise ValueError('Response metadata exceeds max-chars')
    return response


def dispatch_ascendc_or_dialect(args):
    from pathlib import Path
    import ascendc
    import cce_dialect
    identity = getattr(args, 'identity', '')
    backend = 'cce-dialect' if identity.startswith('cce_dialect_') else 'ascendc' if identity.startswith('ascendc_') else args.backend
    module = cce_dialect if backend == 'cce-dialect' else ascendc
    allowed = {'info', 'search', 'get', 'relations', 'evidence', 'interfaces', 'ops'}
    allowed |= {'forms'} if backend == 'ascendc' else {'unresolved'}
    if args.command not in allowed:
        raise ValueError(f'{args.command} is not implemented for {backend}')
    for field in ('builtin', 'signature', 'support', 'category', 'core', 'deprecation'):
        if getattr(args, field, None):
            raise ValueError(f'--{field} is not implemented for {backend}')
    if getattr(args, 'kind', 'interface') not in ('all', 'interface'):
        raise ValueError('--kind is not implemented for this backend')
    if getattr(args, 'chip', None) not in (None, 'Ascend950PR_9579') or getattr(args, 'architecture', None) not in (None, '__NPU_ARCH__=3510'):
        raise ValueError('This snapshot is scoped to Ascend950PR_9579 / __NPU_ARCH__=3510')
    layers = ('ops', 'intrinsics') if backend == 'cce-dialect' else ('basic', 'capi')
    layer = getattr(args, 'layer', None) or layers[args.command == 'ops']
    if layer not in layers:
        raise ValueError(f'Invalid {backend} layer: {layer}')
    path = Path(args.data) if args.data else module.OUTPUT
    if path.is_dir():
        path = path / 'index.json'
    data = json.loads(path.read_text())
    errors = module.validate_model(data)
    if errors:
        raise ValueError('; '.join(errors))
    context = {
        'schema_version': 'ackb.multi-backend.query.v1', 'backend': backend,
        'operation': args.command, 'version': data['version'], 'target': data['target'],
        'layer': layer, 'limitations': data['limitations'],
        'verification': {'compile': 'unverified', 'runtime': 'unverified', 'performance': 'unverified'},
        'provenance': {'index_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
                       'generator_sha256': data['generator_sha256'], 'catalog_sha256': data['catalog_sha256']},
    }
    if backend == 'cce-dialect':
        context['provenance']['commit'] = data['source']['commit']
    if args.command == 'info':
        return page([{'counts': data['counts'], 'target': data['target']}], args, context)
    if args.command == 'unresolved':
        return page(data['unresolved_lowerings'], args, context)
    keys = ('ops', 'intrinsics') if backend == 'cce-dialect' else ('basic_api', 'c_api')
    by_id = {r['id']: r for key in keys for r in data[key]}
    if identity:
        if identity not in by_id:
            raise ValueError(f'Unknown {backend} identity: {identity}')
        rec = by_id[identity]
        if args.command == 'get':
            # Keep large forms/relations pageable instead of silently cutting the underlying data.
            item = {k: v for k, v in rec.items() if k not in ('forms', 'excerpt', 'ccec_callees', 'implementation_candidates', 'impl_3510_functions')}
            item['evidence_query'] = {'operation': 'evidence', 'identity': identity}
            item['relations_query'] = {'operation': 'relations', 'identity': identity}
            if backend == 'ascendc':
                item['forms_query'] = {'operation': 'forms', 'identity': identity, 'total': len(rec['forms'])}
            return page([item], args, context)
        if args.command == 'forms':
            return page(rec['forms'], args, context)
        if args.command == 'relations':
            rels = [{'relation': 'candidate_intrinsic_mapping', 'target_id': i, 'resolution': 'lexical_name_candidate'} for i in rec.get('intrinsic_ids', [])]
            rels += [{'relation': 'candidate_source_op', 'source_id': i, 'resolution': 'lexical_name_candidate'} for i in rec.get('upstream_op_ids', [])]
            rels += [{'relation': 'candidate_ccec_op', 'target_id': i, 'resolution': 'lexical_name_candidate'} for i in rec.get('ccec_candidate_op_ids', [])]
            for c in rec.get('ccec_callees', []):
                rels.append({'relation': 'candidate_ccec_symbol', **c})
            for fn in rec.get('implementation_candidates', []) + rec.get('impl_3510_functions', []):
                rels.append({'relation': 'candidate_implementation', 'resolution': 'name_based_not_overload_resolved', **fn})
            return page(rels, args, context)
        if args.command == 'evidence':
            files = data['source']['files'] if backend == 'cce-dialect' else data['files']
            source = rec.get('impl_source') or rec['source']
            lines = rec.get('excerpt', '').splitlines()
            return page([{'source': source, 'sha256': files[source['file']]['sha256'],
                          'excerpt_line': i + 1, 'text': line} for i, line in enumerate(lines)], args, context)
    pool = data[keys[layers.index(layer)]]
    q = (getattr(args, 'name', None) or getattr(args, 'query', '') or '').lower()
    cond = getattr(args, 'condition', None)
    if backend == 'cce-dialect' and args.command == 'ops':
        cond = None
    if backend == 'cce-dialect' and cond:
        raise ValueError('Dialect mappings have no verified architecture condition assessment')
    if backend == 'ascendc' and args.command == 'interfaces' and not cond:
        cond = 'possible' if getattr(args, 'include_unknown', False) else 'matches'
    items = []
    for x in pool:
        if cond and x['condition_3510'] not in (('matches', 'unknown') if cond == 'possible' else (cond,)):
            continue
        if q and q not in json.dumps({k: x.get(k) for k in ('id', 'name', 'qualified_name', 'mnemonic', 'def_name', 'summary', 'family', 'group', 'ccec_candidate_op_ids')}, ensure_ascii=False).lower():
            continue
        item = {k: x[k] for k in ('id', 'name', 'qualified_name', 'family', 'group', 'condition_3510', 'overload_count', 'source', 'relation_resolution') if k in x}
        item['sample_signature'] = (x.get('forms') or [{}])[0].get('signature', '')
        items.append(item)
    return page(items, args, context)


def run(args):
    if not 1 <= args.limit <= 50 or args.offset < 0 or not 2000 <= args.max_chars <= 100000:
        raise ValueError('Expected limit 1..50, offset >= 0, max-chars 2000..100000')
    if args.command == 'schema':
        schema = 'multi-backend-query-v1.schema.json' if args.backend in ('ascendc', 'cce-dialect') else 'knowledge-v1.schema.json' if args.backend == 'ptx' else 'calls-query-v1.schema.json' if args.layer == 'calls' else 'ops-query-v1.schema.json' if args.layer == 'ops' else 'query-v1.schema.json'
        return json.loads((ROOT / 'schemas' / schema).read_text())
    if args.backend in ('ascendc', 'cce-dialect') or getattr(args, 'identity', '').startswith(('ascendc_', 'cce_dialect_')):
        return dispatch_ascendc_or_dialect(args)
    if args.command in ('forms', 'unresolved'):
        raise ValueError('Use --backend ascendc for forms or --backend cce-dialect for unresolved')
    knowledge_identity = getattr(args, 'identity', '').startswith(('ccec_topic_', 'ccec_builtin_'))
    if args.backend == 'ptx' or args.command in ('topics', 'builtins', 'categories') or knowledge_identity:
        knowledge = Knowledge(args.backend, args.data)
        return page(knowledge.dispatch(args), args, knowledge.context(args.command))
    if getattr(args, 'support', None):
        raise ValueError('--support is for PTX documentation assessments; CCEC uses --condition')
    if getattr(args, 'category', None):
        raise ValueError('--category is for PTX instruction taxonomy')
    if getattr(args, 'kind', 'all') not in ('all', 'interface', 'type', 'macro', 'constant', 'helper'):
        raise ValueError('This kind belongs to the PTX backend')
    db = Database(args.data)
    with contextlib.redirect_stdout(io.StringIO()):
        validate(db.data)
    context = {'backend': 'ccec', 'operation': args.command, 'version': db.data['version'], 'limitations': LIMITATIONS,
               'provenance': {'catalog_sha256': db.snapshot_sha256, 'extractor_revision': db.data.get('extractor_revision'),
                              'compatibility_revision': db.data['compatibility']['revision'],
                              'analyzer_sha256': db.data['compatibility']['analyzer_sha256']}}
    if args.command == 'calls' or getattr(args, 'identity', '').startswith('ccec_call_'):
        from ccec_calls import load_calls
        if getattr(args, 'chip', None) not in (None, 'Ascend950PR_9579') or getattr(args, 'architecture', None) not in (None, '__NPU_ARCH__=3510'):
            raise ValueError('Observed calls are fixed to Ascend950PR_9579')
        evidence = load_calls(db)
        identity = args.identity
        items = [c for c in evidence['calls'] if identity in (c['id'], c['op_id'], c['name']) or identity in c['entry_record_ids']]
        if not items:
            raise ValueError('No observed A5 calls for this identity')
        items = [{**c, 'source_evidence': evidence['files'][c['source']['file']]} for c in items]
        context.update(schema_version='ackb.ccec-calls.query.v1', target=db.target(chip='Ascend950PR_9579'),
                       limitations=evidence['limitations'])
        return page(items, args, context)
    if args.command == 'interfaces' or getattr(args, 'identity', '').startswith('ccec_interface_'):
        from ccec_a5 import interfaces, CHIP
        if getattr(args, 'chip', None) not in (None, CHIP) or getattr(args, 'architecture', None) not in (None, '__NPU_ARCH__=3510'):
            raise ValueError('Interface summaries are fixed to Ascend950PR_9579 / NpuArch 3510')
        items = interfaces(db)
        identity = getattr(args, 'identity', None)
        if identity:
            if args.command != 'get':
                raise ValueError('Use get for interface IDs, then relations/evidence for returned record IDs')
            items = [item for item in items if item['id'] == identity]
            if not items:
                raise ValueError('Unknown interface identity')
        else:
            allowed = ('matches', 'unknown') if args.include_unknown else ('matches',)
            items = [item for item in items if item['condition'] in allowed and args.name.lower() in item['name'].lower()]
        context.update(schema_version='ackb.ccec-ops.query.v1', target=db.target(chip=CHIP, core=getattr(args, 'core', None)))
        return page(items, args, context)
    if args.command == 'ops' or getattr(args, 'identity', '').startswith('ccec_op_'):
        from ccec_ops import Ops, LIMITS
        ops = Ops(db)
        target = db.target(getattr(args, 'chip', None) or (None if getattr(args, 'architecture', None) else 'Ascend950PR_9579'), getattr(args, 'architecture', None), getattr(args, 'core', None))
        context.update(schema_version='ackb.ccec-ops.query.v1', limitations=LIMITS, target=target)
        identity = getattr(args, 'identity', None)
        if identity and identity not in ops.by_id:
            raise ValueError('Unknown op identity')
        if args.command == 'relations':
            items = ops.relations(identity)
        elif identity:
            if args.command not in ('get', 'support'):
                raise ValueError('Use get, support or relations for op IDs; original source evidence uses record IDs')
            items = [ops.detail(ops.by_id[identity], target)]
            from ccec_calls import load_calls
            evidence = load_calls(db)
            items[0]['observed_a5_call_ids'] = [c['id'] for c in evidence['calls'] if c['op_id'] == identity]
            items[0]['observed_a5_calls_query'] = 'calls ' + identity
        else:
            query = (args.name or args.query).lower()
            items = [ops.summary(o, target) for o in ops.model['ops'] if query in (' '.join([o['name'], o['builtin'], *o['aliases']])).lower()]
            if args.condition:
                items = [o for o in items if o['assessment']['condition'] in (('matches', 'unknown') if args.condition == 'possible' else (args.condition,))]
        return page(items, args, context)
    if args.command == 'info':
        from ccec_ops import Ops
        return page([{'op_inventory': Ops(db).model['counts'], 'primary_query': 'interfaces', 'default_chip': 'Ascend950PR_9579', 'records': len(db.records), 'symbols': len(db.by_symbol), 'signature_variants': len(db.by_variant),
                      'counts': db.data['counts'], 'scanned_headers': len(db.files),
                      'unresolved': len(db.data['report']['unresolved']),
                      'header_builtin_names': len(db.data['report']['raw_builtin_names']),
                      'compiler_builtin_inventory': 'incomplete', 'device_experiments': 0,
                      'package_verification_scope': 'scanned_resource_headers',
                      'versions_available': [db.data['version']]}], args, context)
    if args.command == 'targets':
        items = [{'kind': 'chip', **t} for t in db.data['compatibility']['chip_mappings']]
        items += [{'kind': 'macro_scenario', **p} for p in db.data['compatibility']['profiles']]
        return page([t for t in items if args.name.lower() in json.dumps(t).lower()], args, context)
    if args.command == 'evidence':
        if args.identity not in db.by_id:
            raise ValueError('Evidence requires an exact record ID; use get to find record IDs')
        r = db.by_id[args.identity]
        text = r.get(args.field) or r['signature']
        length = min(len(text), max(100, (args.max_chars - 1800) // 2))
        item = {'evidence': db.evidence(r), 'field': args.field, 'text': text[:length],
                'representation': 'original_source_excerpt' if args.field == 'excerpt' and r.get('excerpt') else 'extracted_declaration',
                'text_characters': len(text), 'text_truncated': len(text) > length,
                'macro_sources': db.macro_evidence(r)}
        return page([item], args, context)
    target = db.target(args.chip, args.architecture, args.core)
    context['target'] = target
    selected = db.select(query=getattr(args, 'query', ''), name=args.name, identity=getattr(args, 'identity', None),
                         builtin=args.builtin, kind=args.kind, signature=args.signature,
                         deprecation=args.deprecation, condition=args.condition, target=target)
    if args.command == 'support':
        from ccec_support import Support
        evidence = Support(db=db)
        context['provenance']['support_evidence_sha256'] = hashlib.sha256(evidence.path.read_bytes()).hexdigest()
        items = [evidence.record(r, target) for r in selected]
    elif args.command == 'relations':
        from ccec_ops import Ops
        op_index = Ops(db)
        items = [{'source_record_id': r['id'], **edge} for r in selected for edge in db.relations(r)]
        items += [edge for r in selected for edge in op_index.relations(r['id'])]
    else:
        items = [db.summary(r, target) for r in selected]
        if args.command == 'get':
            from ccec_ops import Ops
            op_index = Ops(db)
            for item, r in zip(items, selected):
                item['op_layer'] = op_index.model['record_layers'].get(r['id'])
                item.update({'conditions': r['conditions'], 'evaluated_conditions': r['compatibility']['conditions'],
                             'ignored_guards': r['compatibility']['ignored_guards'],
                             'parameters': r.get('parameters'), 'builtins': r['builtins'], 'macro_sources': db.macro_evidence(r),
                             'deprecation_evidence': r['deprecation'],
                             'semantics': {'status': 'unreviewed', 'parameter_meanings': None, 'alignment': None,
                                           'side_effects': None, 'synchronization': None},
                             'experiments': []})
    return page(items, args, context)


def main():
    args = None
    try:
        args = parser().parse_args()
        result = run(args)
        print(json.dumps(result, ensure_ascii=False, separators=(',', ':')))
    except (ValueError, AssertionError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'schema_version': 'ackb.multi-backend.query.v1' if args and (args.backend in ('ascendc', 'cce-dialect') or getattr(args, 'identity', '').startswith(('ascendc_', 'cce_dialect_'))) else PROTOCOL if args and (args.backend == 'ptx' or args.command in ('topics', 'builtins', 'categories') or getattr(args, 'identity', '').startswith(('ccec_topic_', 'ccec_builtin_'))) else SCHEMA_VERSION, 'error': {'code': 'invalid_request_or_data', 'message': str(exc)}}, ensure_ascii=False))
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
