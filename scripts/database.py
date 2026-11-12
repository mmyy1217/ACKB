"""Versioned, source-backed query model shared by tools and the offline manual."""
import hashlib
import json
from pathlib import Path

from catalog import ROOT, VERSION, tokens
from compatibility import analyze, evaluate

SCHEMA_VERSION = 'cce-ops.query.v1'


def stable_id(prefix, values):
    payload = json.dumps(values, ensure_ascii=False, separators=(',', ':')).encode()
    return prefix + hashlib.sha256(payload).hexdigest()[:24]


def identities(record):
    symbol = stable_id('sym_', [record['kind'], record.get('namespace', ''), record['name']])
    variant = stable_id('var_', [symbol, tokens(record['signature'])])
    return symbol, variant


def load_catalog(source, enrich=True):
    data = json.loads(Path(source).read_text())
    target_path = Path(source).with_name('targets.json')
    targets = json.loads(target_path.read_text()) if target_path.exists() else {'version': data['version'], 'targets': []}
    if targets['version'] != data['version']:
        raise ValueError('Target metadata version differs from catalog')
    analyze(data, targets['targets'], evaluate_profiles=enrich)
    data['compatibility']['analyzer_sha256'] = hashlib.sha256((ROOT / 'scripts/compatibility.py').read_bytes()).hexdigest()
    for record in data['records']:
        record['symbol_id'], record['variant_id'] = identities(record)
    data['query_schema_version'] = SCHEMA_VERSION
    return data


class Database:
    def __init__(self, source=None, data=None):
        self.source = Path(source or ROOT / 'data' / VERSION / 'catalog.json')
        self.data = data if data is not None else load_catalog(self.source, enrich=False)
        self.snapshot_sha256 = hashlib.sha256(self.source.read_bytes()).hexdigest() if data is None else None
        self.records = self.data['records']
        self.files = {f['path']: f for f in self.data['files']}
        self.by_id = {r['id']: r for r in self.records}
        self.by_symbol = {}
        self.by_variant = {}
        for r in self.records:
            symbol, variant = identities(r)
            r['symbol_id'], r['variant_id'] = symbol, variant
            self.by_symbol.setdefault(symbol, []).append(r)
            self.by_variant.setdefault(variant, []).append(r)

    def target(self, chip=None, architecture=None, core=None):
        if chip and architecture:
            raise ValueError('Choose chip or architecture, not both')
        targets = self.data['compatibility']['chip_mappings']
        selected = next((t for t in targets if t['chip'] == chip), None)
        if chip and selected is None:
            raise ValueError(f'Unknown chip: {chip}; use targets')
        if core and (not selected or core not in selected['cores'].values()):
            raise ValueError('Core requires a chip and an exact configured CCEC target; use targets')
        profile_id = '__NPU_ARCH__=' + str(selected['npu_arch']) if selected else architecture
        profile = next((p for p in self.data['compatibility']['profiles'] if p['id'] == profile_id), None)
        if profile_id and not profile:
            raise ValueError(f'Unknown architecture scenario: {profile_id}; use targets')
        return {'chip': chip, 'core': core, 'profile': profile,
                'mapping_evidence': selected['source'] if selected else None,
                'core_evaluation': 'unverified' if core else 'not_requested'}

    @staticmethod
    def condition(record, target):
        if not target['profile']:
            return 'not_evaluated'
        values = [evaluate(c, target['profile']['macros']) for c in record['compatibility']['conditions']]
        return 'excluded' if False in values else 'unknown' if None in values else 'matches'

    def evidence(self, record):
        source = record['source']
        return {'record_id': record['id'], 'version': self.data['version'], **source,
                'resource_root': self.data['source']['resource_root'],
                'sha256': self.files[source['file']]['sha256'],
                'package_verified': bool(self.data['source']['package_verified']),
                'level': 'static_declaration'}

    def macro_evidence(self, record):
        return [{**source, 'version': self.data['version'], 'sha256': self.files[source['file']]['sha256'],
                 'package_verified': bool(self.data['source']['package_verified'])}
                for source in record.get('macro_sources', [])]

    def summary(self, record, target):
        return {key: record.get(key, '') for key in ('id', 'symbol_id', 'variant_id', 'name', 'namespace', 'kind', 'signature')} | {
            'generated': bool(record.get('generated')),
            'condition_result': self.condition(record, target),
            'deprecation': record['deprecation']['status'],
            'verification': {'compile': 'unverified', 'runtime': 'unverified', 'performance': 'unverified'},
            'evidence': self.evidence(record)}

    def select(self, query='', name=None, identity=None, builtin=None, kind='interface', signature=None,
               deprecation=None, condition=None, target=None):
        target = target or self.target()
        if condition and not target['profile']:
            raise ValueError('Condition filtering requires a chip or architecture scenario')
        if identity:
            if identity in self.by_id:
                candidates = [self.by_id[identity]]
            else:
                candidates = self.by_symbol.get(identity, self.by_variant.get(identity, []))
            if not candidates:
                raise ValueError(f'Unknown identity: {identity}')
        else:
            candidates = self.records
        terms = query.lower().split()
        result = []
        for r in candidates:
            if kind != 'all' and (not r['kind'].startswith('interface') if kind == 'interface' else r['kind'] != kind):
                continue
            if name and name != r['name']:
                continue
            if builtin and builtin not in r['builtins']:
                continue
            if signature and signature.lower() not in r['signature'].lower():
                continue
            if deprecation and r['deprecation']['status'] != deprecation:
                continue
            haystack = ' '.join([r['name'], r['signature'], r.get('namespace', ''), *r['builtins']]).lower()
            if not all(t in haystack for t in terms):
                continue
            status = self.condition(r, target)
            if condition and (status == 'excluded' if condition == 'possible' else status != condition):
                continue
            result.append(r)
        return sorted(result, key=lambda r: (r['name'], r['variant_id'], r['id']))

    def relations(self, record):
        edges = []
        for builtin in sorted(set(record['builtins'])):
            edges.append({'kind': 'builtin_reference', 'target_name': builtin, 'resolution': 'header_reference',
                          'evidence': self.evidence(record)})
        for name in sorted(set(record.get('calls', []))):
            candidates = sorted({r['symbol_id'] for r in self.records if r['name'] == name})
            edges.append({'kind': 'call_name_reference', 'target_name': name, 'candidate_symbol_ids': candidates,
                          'resolution': 'unresolved_overload', 'evidence': self.evidence(record)})
        return edges
