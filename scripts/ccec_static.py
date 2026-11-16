#!/usr/bin/env python3
"""Build a complete, conservative architecture-branch reference matrix from CANN sources."""
import argparse
from collections import Counter, defaultdict, deque
import hashlib
import json
from pathlib import Path
import re

from catalog import ROOT, VERSION
from compatibility import evaluate
from ccec_support import Support, DEFAULT

OUTPUT = DEFAULT.with_name('static-support.json')
LABELS = {
    'architecture_reference': '架构分支有引用',
    'conditional_reference': '架构分支条件引用',
    'generic_reference': '仅通用源码引用',
    'declaration_only': '仅声明证据',
    'condition_unknown': '声明条件缺少宏依据',
    'declaration_excluded': '声明条件排除',
    'source_conflict': '声明排除但同名形式有引用',
}


def file_guards(meta):
    return {g['condition'] for g in meta.get('guards', [])
            if re.search(r'(?:_H|_H_|_H__|_HPP|_HPP__)$', g['macro'])}


def conditions_result(conditions, arch, guards=()):
    values = [evaluate(c, {'__NPU_ARCH__': arch}) for c in conditions if c.strip() not in guards]
    return False if False in values else None if None in values else True


def architecture_routes(data, arch):
    """Start at explicit architecture selectors, not directory-name guesses."""
    edges = defaultdict(list)
    guards = {f: file_guards(m) for f, m in data['files'].items()}
    for i, edge in enumerate(data['includes']):
        if edge['resolved_relative_path'] in data['files']:
            edges[edge['file']].append((i, edge))
    best, queue = {}, deque()

    def offer(file, state, path):
        old = best.get(file)
        if old is None or (old['state'] is None and state is True) or (old['state'] == state and len(path) < len(old['edges'])):
            best[file] = {'state': state, 'edges': path}
            queue.append(file)

    for entries in edges.values():
        for i, edge in entries:
            if not any('__NPU_ARCH__' in c for c in edge['conditions']):
                continue
            state = conditions_result(edge['conditions'], arch, guards[edge['file']])
            if state is True:
                offer(edge['resolved_relative_path'], True, [i])
    while queue:
        file = queue.popleft()
        route = best[file]
        for i, edge in edges[file]:
            state = conditions_result(edge['conditions'], arch, guards[file])
            if state is False or i in route['edges']:
                continue
            offer(edge['resolved_relative_path'], True if state is True and route['state'] is True else None, route['edges'] + [i])
    return best


class StaticAnalysis:
    def __init__(self, support):
        self.support = support
        self.data = support.data
        self.by_name = defaultdict(list)
        for i, ref in enumerate(self.data['references']):
            self.by_name[ref['name']].append(i)
        self.guards = {f: file_guards(m) for f, m in self.data['files'].items()}
        self.routes = {}
        self.cache = {}

    def assess(self, record, arch):
        if arch not in self.routes:
            self.routes[arch] = architecture_routes(self.data, arch)
        names = tuple(sorted({record['name'], *record['builtins']}))
        key = (names, arch)
        if key not in self.cache:
            buckets = {'architecture_reference': [], 'conditional_reference': [], 'generic_reference': []}
            for i in sorted({i for n in names for i in self.by_name[n]}):
                ref = self.data['references'][i]
                local = conditions_result(ref['conditions'], arch, self.guards[ref['file']])
                if local is False:
                    continue
                route = self.routes[arch].get(ref['file'])
                if route:
                    bucket = 'architecture_reference' if local is True and route['state'] is True else 'conditional_reference'
                    buckets[bucket].append(i)
                elif ref['directory_hint'] is None:
                    # Generic use does not prove any architecture's support.
                    buckets['generic_reference'].append(i)
            self.cache[key] = buckets
        buckets = self.cache[key]
        declaration = conditions_result(record['compatibility']['conditions'], arch)
        evidence_state = next((k for k, v in buckets.items() if v), None)
        if declaration is False:
            state = 'source_conflict' if buckets['architecture_reference'] else 'declaration_excluded'
        elif evidence_state:
            state = evidence_state
        else:
            state = 'condition_unknown' if declaration is None else 'declaration_only'
        chosen = buckets[evidence_state] if evidence_state else []
        cores = sorted({g for i in chosen for g in self.data['references'][i]['core_guards']})
        # Representative indices are locators, not the full set of references.
        return {'state': state, 'references': chosen[:2], 'reference_count': len(chosen), 'core_guards': cores}

    def trace(self, assessment, arch):
        traces = []
        for i in assessment['references']:
            ref = self.data['references'][i]
            route = self.routes.get(arch, {}).get(ref['file'])
            path = []
            if route:
                for e in route['edges']:
                    edge = self.data['includes'][e]
                    path.append({**edge, 'sha256': self.data['files'][edge['file']]['sha256']})
            traces.append({'reference': {**ref, 'sha256': self.data['files'][ref['file']]['sha256']},
                           'architecture_selector_path': path})
        return traces


def macro_audit(support, arch):
    affected = defaultdict(set)
    for r in support.db.records:
        if not r['kind'].startswith('interface') or conditions_result(r['compatibility']['conditions'], arch) is not None:
            continue
        for c in r['compatibility']['conditions']:
            if evaluate(c, {'__NPU_ARCH__': arch}) is None:
                for name in set(re.findall(r'\b[A-Za-z_]\w*\b', c)) - {'defined', '__NPU_ARCH__', 'and', 'or', 'not'}:
                    affected[name].add(r['id'])
    definitions = defaultdict(list)
    for d in support.data.get('macro_definitions', []) + support.data.get('resource_macro_definitions', []):
        definitions[d['name']].append(d)
    return {name: {'affected_records': sorted(ids), 'definition_count': len(definitions[name]),
                   'definitions': definitions[name],
                   'finding': 'conditional_source_definitions' if definitions[name] else 'no_definition_in_scanned_headers'}
            for name, ids in sorted(affected.items())}


def web_payload(data, support):
    """Use compact rows and shared provenance; avoid duplicating whole records in HTML."""
    states = list(LABELS)
    used = {i for items in data['architectures'].values() for r in items.values() for i in r['references']}
    refs = {str(i): {**support.data['references'][i],
                    'sha256': support.data['files'][support.data['references'][i]['file']]['sha256']}
            for i in sorted(used)}
    paths, edges = {}, {}
    for arch, items in data['architectures'].items():
        routes = architecture_routes(support.data, int(arch))
        paths[arch] = {}
        for r in items.values():
            for i in r['references']:
                file = refs[str(i)]['file']
                if file in routes:
                    route = routes[file]['edges']
                    paths[arch][file] = route
                    for e in route:
                        edge = support.data['includes'][e]
                        edges[str(e)] = {**edge, 'sha256': support.data['files'][edge['file']]['sha256']}
    return {'labels': LABELS, 'states': states, 'counts': data['counts'], 'coverage': data['coverage'],
            'source_hash': data['source_evidence_sha256'],
            'package_verified_files': len(support.data['files']) if support.package_proof else 0,
            'architectures': {arch: {rid: [states.index(r['state']), r['reference_count'], r['core_guards'], r['references']]
                                     for rid, r in items.items()} for arch, items in data['architectures'].items()},
            'references': refs, 'paths': paths, 'edges': edges, 'source_issues': support.data['parse_issues']}


def build(output=OUTPUT):
    support = Support()
    analysis = StaticAnalysis(support)
    records = [r for r in support.db.records if r['kind'].startswith('interface')]
    targets = support.db.data['compatibility']['chip_mappings']
    architectures = sorted({t['npu_arch'] for t in targets})
    matrix, reports = {}, {}
    for arch in architectures:
        items = {r['id']: analysis.assess(r, arch) for r in records}
        matrix[str(arch)] = items
        reports[str(arch)] = dict(Counter(item['state'] for item in items.values()))
    result = {'schema_version': 'ackb.ccec-static-support.v1', 'version': VERSION,
              'catalog_sha256': support.db.snapshot_sha256,
              'source_evidence_sha256': hashlib.sha256(DEFAULT.read_bytes()).hexdigest(),
              'analyzer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'scope': 'architecture_selector_and_name_reference_not_device_support',
              'labels': LABELS, 'chips': {t['chip']: t['npu_arch'] for t in targets},
              'architectures': matrix, 'counts': reports,
              'macro_audit': {str(arch): macro_audit(support, arch) for arch in architectures},
              'coverage': {'records': len(records), 'architectures': len(architectures), 'chips': len(targets),
                           'assessments': len(records) * len(architectures)},
              'limitations': ['A reference is matched by name, not an exact overload or template instantiation.',
                             'Selector paths are local include paths, not proof of reachability from a full translation unit.',
                             'Core guards describe observed uses; absence does not mean both cores support the operation.',
                             'Unknown macros remain unknown. No compile, runtime or performance claim.']}
    output.write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n')
    return result


def validate(data, support):
    errors = []
    if data['source_evidence_sha256'] != hashlib.sha256(support.path.read_bytes()).hexdigest():
        errors.append('Stale source evidence hash')
    if data['catalog_sha256'] != support.db.snapshot_sha256:
        errors.append('Stale catalog hash')
    expected_arches = {str(t['npu_arch']) for t in support.db.data['compatibility']['chip_mappings']}
    if set(data['architectures']) != expected_arches:
        errors.append('Incomplete architecture coverage')
    ids = {r['id'] for r in support.db.records if r['kind'].startswith('interface')}
    for arch, items in data['architectures'].items():
        if set(items) != ids:
            errors.append('Incomplete record coverage: ' + arch)
        if dict(Counter(i['state'] for i in items.values())) != data['counts'][arch]:
            errors.append('Count mismatch: ' + arch)
        for identity, item in items.items():
            if item['state'] not in LABELS:
                errors.append('Unknown state: ' + identity)
            if any(not 0 <= i < len(support.data['references']) for i in item['references']):
                errors.append('Invalid reference: ' + identity)
    return errors


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['build', 'validate', 'report'])
    args = parser.parse_args()
    if args.command == 'build':
        data = build()
        print(json.dumps({'coverage': data['coverage'], '950': data['counts']['3510']}, ensure_ascii=False, indent=2))
    else:
        data = json.loads(OUTPUT.read_text())
        if args.command == 'validate':
            errors = validate(data, Support())
            if errors:
                raise SystemExit('; '.join(errors))
            print('ok')
        else:
            print(json.dumps({'coverage': data['coverage'], 'labels': LABELS, 'counts': data['counts']}, ensure_ascii=False, indent=2))
