#!/usr/bin/env python3
"""Bounded JSON queries for agents; no compiler execution or network access."""
import argparse
import contextlib
import io
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
    p.add_argument('--backend', choices=['ccec', 'ptx'], default='ccec')
    p.add_argument('--data', help='Versioned catalog path; defaults to the repository snapshot')
    p.add_argument('--limit', type=int, default=10)
    p.add_argument('--offset', type=int, default=0)
    p.add_argument('--max-chars', type=int, default=24000)
    commands = p.add_subparsers(dest='command', required=True, parser_class=Parser)
    commands.add_parser('info')
    commands.add_parser('schema')
    for operation in ('topics', 'builtins'):
        topic = commands.add_parser(operation)
        topic.add_argument('query', nargs='?', default='')
    targets = commands.add_parser('targets')
    targets.add_argument('--name', default='')
    for command in ('search', 'get', 'relations'):
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


def run(args):
    if not 1 <= args.limit <= 50 or args.offset < 0 or not 2000 <= args.max_chars <= 100000:
        raise ValueError('Expected limit 1..50, offset >= 0, max-chars 2000..100000')
    if args.command == 'schema':
        schema = 'knowledge-v1.schema.json' if args.backend == 'ptx' else 'query-v1.schema.json'
        return json.loads((ROOT / 'schemas' / schema).read_text())
    knowledge_identity = getattr(args, 'identity', '').startswith(('ccec_topic_', 'ccec_builtin_'))
    if args.backend == 'ptx' or args.command in ('topics', 'builtins') or knowledge_identity:
        knowledge = Knowledge(args.backend, args.data)
        return page(knowledge.dispatch(args), args, knowledge.context(args.command))
    if getattr(args, 'support', None):
        raise ValueError('--support is for PTX documentation assessments; CCEC uses --condition')
    if getattr(args, 'kind', 'all') not in ('all', 'interface', 'type', 'macro', 'constant', 'helper'):
        raise ValueError('This kind belongs to the PTX backend')
    db = Database(args.data)
    with contextlib.redirect_stdout(io.StringIO()):
        validate(db.data)
    context = {'backend': 'ccec', 'operation': args.command, 'version': db.data['version'], 'limitations': LIMITATIONS,
               'provenance': {'catalog_sha256': db.snapshot_sha256, 'extractor_revision': db.data.get('extractor_revision'),
                              'compatibility_revision': db.data['compatibility']['revision'],
                              'analyzer_sha256': db.data['compatibility']['analyzer_sha256']}}
    if args.command == 'info':
        return page([{'records': len(db.records), 'symbols': len(db.by_symbol), 'signature_variants': len(db.by_variant),
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
    if args.command == 'relations':
        items = [{'source_record_id': r['id'], **edge} for r in selected for edge in db.relations(r)]
    else:
        items = [db.summary(r, target) for r in selected]
        if args.command == 'get':
            for item, r in zip(items, selected):
                item.update({'conditions': r['conditions'], 'evaluated_conditions': r['compatibility']['conditions'],
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
        print(json.dumps({'schema_version': PROTOCOL if args and (args.backend == 'ptx' or args.command in ('topics', 'builtins') or getattr(args, 'identity', '').startswith(('ccec_topic_', 'ccec_builtin_'))) else SCHEMA_VERSION, 'error': {'code': 'invalid_request_or_data', 'message': str(exc)}}, ensure_ascii=False))
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
