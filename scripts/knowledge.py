"""Backend-aware access to indexed target knowledge and selected-depth notes."""
from collections import Counter
import hashlib
import json
from pathlib import Path
from catalog import ROOT
from ptx_index import entry_id, load_tree, validate_tree
from ptx_targets import assess, DEFAULT_TARGET, TARGETS

PROTOCOL = 'ackb.knowledge-query.v1'


def checksum(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Knowledge:
    def __init__(self, backend, source=None):
        self.backend = backend
        if backend == 'ptx':
            self.root = Path(source) if source else ROOT / 'data/ptx'
            tree = load_tree(self.root)
            errors = validate_tree(tree)
            if errors:
                raise ValueError('; '.join(errors))
            self.tree = tree
            self.version = tree['source']['isa']['version']
            self.source = tree['source']['isa']['html']
            detailed = {x['anchor']: x for key in ('instructions', 'execution', 'directives', 'special_registers') for x in tree[key]}
            self.records = []
            for section in tree['sections']:
                record = dict(detailed.get(section['anchor'], section))
                record.setdefault('entry_id', entry_id(record['anchor'], record['section_number']))
                record.setdefault('depth', 'index')
                self.records.append(record)
            self.device = json.loads((self.root / 'device.json').read_text())
            self.learning = json.loads((self.root / 'learning.json').read_text())
            self.syntax = json.loads((self.root / 'syntax.json').read_text())
            if self.syntax['source_sha256'] != self.source['sha256']:
                raise ValueError('PTX syntax source hash mismatch')
            for record in self.records:
                record['target_assessments'] = {target: assess(record, target) for target in TARGETS}
                record['target_assessment'] = record['target_assessments'][DEFAULT_TARGET]
                record['syntax_detail'] = self.syntax['entries'].get(record['anchor'])
                record['guide'] = next((self.learning['instruction_guides'][m] for m in record.get('mnemonics', []) if m in self.learning['instruction_guides'] and self.learning['instruction_guides'][m]['anchor'] == record['anchor']), None)
            self.notes = [{**n, 'kind': 'lesson', 'citations': [{'anchor': a} for a in n['anchors']]} for n in self.learning['lessons']]
            self.limits = self.learning['limitations'] + ['The documentation archive is not the installed CUDA toolkit.']
        else:
            if source:
                raise ValueError('CCEC knowledge uses the pinned repository snapshot; --data is supported by declaration queries only')
            self.root = ROOT / 'data/ccec'
            self.tree = json.loads((self.root / 'knowledge.json').read_text())
            self.version = self.tree['version']
            catalog = ROOT / 'data' / self.version / 'catalog.json'
            if checksum(catalog) != self.tree['source_catalog_sha256']:
                raise ValueError('CCEC knowledge is stale; rebuild with scripts/ccec_knowledge.py')
            self.records = self.tree['builtins']
            self.notes = self.tree['topics']
            self.limits = self.tree['limitations']

    def context(self, operation):
        return {'target': getattr(self, 'active_target', DEFAULT_TARGET) if self.backend == 'ptx' else None, 'schema_version': PROTOCOL, 'backend': self.backend, 'operation': operation,
                'version': self.version, 'limitations': self.limits,
                'provenance': {p.name: checksum(p) for p in sorted(self.root.glob('*.json'))},
                'verification': {'compile': 'unverified', 'runtime': 'unverified', 'performance': 'unverified'}}

    def find(self, identity):
        found = [r for r in self.records + self.notes if identity in (r.get('entry_id'), r.get('id'), r.get('anchor'))]
        if not found:
            raise ValueError(f'Unknown {self.backend} knowledge identity: {identity}')
        return found[0]

    def evidence(self, record):
        if self.backend == 'ccec':
            return record.get('evidence', [{'record_id': rid, 'lookup': 'query.py evidence ' + rid} for rid in record.get('record_ids', [])])
        refs = record.get('citations', [{'anchor': record['anchor'], 'section': record.get('section_number')}]) if 'anchor' in record else record['citations']
        return [{'url': self.source['url'] + '#' + ref['anchor'], 'anchor': ref['anchor'],
                 'section': ref.get('section'), 'source_sha256': self.source['sha256'],
                 'level': 'official_documentation', 'isa_version': self.version} for ref in refs]

    def item(self, record, full=False):
        if full:
            result = dict(record)
            if self.backend == 'ptx':
                result.pop('target_assessments', None)
                result.pop('sm_89', None)
                if 'target_isa' in result:
                    result['target_isa'] = {**result['target_isa'], 'statements': record['target_assessment']['statements']}
            if self.backend == 'ccec':
                result.pop('evidence', None)
        else:
            keys = ('entry_id', 'id', 'title', 'name', 'kind', 'anchor', 'section_number', 'mnemonics', 'depth', 'status')
            result = {k: record[k] for k in keys if k in record}
        if self.backend == 'ptx' and 'target_assessment' in record:
            result['target_assessment'] = record['target_assessment'] if full else {k: v for k, v in record['target_assessment'].items() if k != 'statements'}
        refs = self.evidence(record)
        result.update({'backend': self.backend, 'evidence': refs[:3], 'evidence_total': len(refs),
                       'evidence_truncated': len(refs) > 3})
        if self.backend == 'ptx':
            result['note_ids'] = [n['id'] for n in self.notes if any(c['anchor'] == record.get('anchor') for c in n['citations'])]
        return result

    def dispatch(self, args):
        command = args.command
        if self.backend == 'ccec':
            for option in ('chip', 'architecture'):
                if getattr(args, option, None):
                    raise ValueError(f'--{option} applies to CCEC declarations, not header-surface topics')
        if command in ('get', 'relations'):
            for option in ('name', 'builtin', 'signature', 'support', 'core', 'condition', 'deprecation'):
                if getattr(args, option, None):
                    raise ValueError(f'--{option} is not supported for knowledge identity lookups')
            if args.kind != 'all':
                raise ValueError('--kind is only supported for knowledge search')
        if command == 'evidence' and args.field != 'excerpt':
            raise ValueError('Knowledge evidence returns source locators, not definition text')
        if self.backend == 'ptx':
            if command == 'builtins':
                raise ValueError('builtins is a CCEC header-reference operation')
            for option in ('builtin', 'signature', 'core', 'condition', 'deprecation'):
                if getattr(args, option, None):
                    raise ValueError(f'--{option} is not supported for PTX index queries; inspect get and use --support')
            if getattr(args, 'architecture', None) not in (None, *TARGETS):
                raise ValueError('Unsupported PTX target; use sm_103, sm_103f, sm_103a or sm_89')
            if getattr(args, 'chip', None) not in (None, 'B300', 'NVIDIA B300'):
                raise ValueError('The primary PTX device is NVIDIA B300; device verification is pending')
        if self.backend == 'ptx':
            target = getattr(args, 'architecture', None) or DEFAULT_TARGET
            self.active_target = target
            for record in self.records:
                record['target_assessment'] = record['target_assessments'][target]
        if command == 'info':
            if self.backend == 'ptx':
                return [{'coverage': {'sections': len(self.records), 'instructions': sum(r['kind'] == 'instruction' for r in self.records), 'lessons': len(self.notes), 'syntax_blocks': len(self.syntax['entries']), 'target_support': dict(Counter(r['target_assessment']['support'] for r in self.records if r['kind'] == 'instruction'))}, 'source': self.source, 'legacy_snapshot': {'target': 'sm_89', 'source_file': 'source.json', 'scan_file': 'scan.json'}, 'default_target': DEFAULT_TARGET, 'device': self.device}]
            return [{'coverage': self.tree['coverage'], 'target': self.tree['target']}]
        if command == 'targets':
            target = {'device': 'NVIDIA B300', 'compute_capability': '10.3', 'default': DEFAULT_TARGET, 'profiles': list(TARGETS), 'source': self.learning['sources']['device']} if self.backend == 'ptx' else {'chip': self.tree['target']}
            return [target] if args.name.lower() in json.dumps(target).lower() else []
        if command == 'topics':
            terms = args.query.lower().split()
            return [self.item(n) for n in self.notes if all(t in json.dumps(n, ensure_ascii=False).lower() for t in terms)]
        if command in ('get', 'evidence', 'relations'):
            record = self.find(args.identity)
            if command == 'evidence':
                return self.evidence(record)
            if command == 'get':
                return [self.item(record, full=True)]
            if self.backend == 'ptx':
                if 'citations' in record:
                    return [{'relation': 'cites_section', 'anchor': c['anchor'], 'entry_id': self.find(c['anchor'])['entry_id']} for c in record['citations']]
                children = [r for r in self.records if r.get('parent_anchor') == record.get('anchor')]
                return [{'relation': 'section_child', 'entry_id': r['entry_id'], 'anchor': r['anchor']} for r in children]
            return [{'relation': 'header_reference', 'record_id': r} for r in record.get('record_ids', [])]
        if command in ('search', 'builtins'):
            terms = args.query.lower().split()
            selected = []
            for record in self.records:
                if command == 'search':
                    kind = args.kind
                    if kind == 'interface':
                        kind = 'instruction'
                    if kind != 'all' and record['kind'] != kind:
                        continue
                    if args.name and args.name not in record.get('mnemonics', []) and args.name != record.get('name'):
                        continue
                    if args.support and record.get('target_assessment', {}).get('support', 'unknown') != args.support:
                        continue
                haystack = json.dumps({k: record.get(k) for k in ('title', 'name', 'anchor', 'mnemonics', 'section_number')}, ensure_ascii=False).lower()
                if all(t in haystack for t in terms):
                    selected.append(self.item(record))
            return selected
        raise ValueError(f'Unsupported knowledge operation: {command}')
