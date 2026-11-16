#!/usr/bin/env python3
"""Trace CCEC declaration conditions and AscendC lexical references, without compiling."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re

from catalog import ROOT, VERSION, clean, tokens, COMMENT
from database import Database
from compatibility import evaluate

DEFAULT = ROOT / 'data' / VERSION / 'support-evidence.json'
ROOTS = ('x86_64-linux/ascendc/include/basic_api', 'x86_64-linux/asc/include', 'x86_64-linux/asc/impl/basic_api', 'x86_64-linux/asc/impl/simt_api', 'x86_64-linux/asc/impl/c_api', 'x86_64-linux/asc/impl/utils')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def core_guard_spans(text):
    # These lexical block guards are evidence, not a C++ control-flow proof.
    stripped = COMMENT.sub(lambda m: re.sub(r'[^\n]', ' ', m[0]), text)
    spans = []
    for m in re.finditer(r'\bif\s+(ASCEND_IS_AI[CV])\s*\{', stripped):
        depth, end = 1, m.end()
        while end < len(stripped) and depth:
            depth += (stripped[end] == '{') - (stripped[end] == '}')
            end += 1
        if depth == 0:
            spans.append((stripped.count('\n', 0, m.start()) + 1,
                          stripped.count('\n', 0, end) + 1, m[1]))
    return spans


def scan_text(text, names, definitions=None):
    """Preserve lexical conditions; never claim C++ overload or include resolution."""
    lines = clean(text).splitlines()
    core_guards = core_guard_spans(text)
    frames, refs, includes, errors, guards = [], [], [], [], []
    index = 0
    while index < len(lines):
        start = index + 1
        line = lines[index]
        index += 1
        while line.rstrip().endswith('\\') and index < len(lines):
            line = line.rstrip()[:-1] + ' ' + lines[index]
            index += 1
        directive = re.match(r'\s*#\s*(\w+)\s*(.*)', line)
        if directive:
            op, body = directive.groups()
            if op in ('if', 'ifdef', 'ifndef'):
                expr = body if op == 'if' else f'{"!" if op == "ifndef" else ""}defined({body.strip()})'
                frames.append({'seen': [expr], 'active': expr})
            elif op in ('elif', 'else'):
                if not frames:
                    errors.append({'line': start, 'reason': 'unmatched_' + op})
                    continue
                frame = frames[-1]
                prior = ' || '.join('(' + s + ')' for s in frame['seen'])
                frame['active'] = '!(' + prior + ')' + (' && (' + body + ')' if op == 'elif' else '')
                if op == 'elif':
                    frame['seen'].append(body)
            elif op == 'endif':
                if frames:
                    frames.pop()
                else:
                    errors.append({'line': start, 'reason': 'unmatched_endif'})
            elif op == 'include':
                includes.append({'name': body.strip(' <>"'), 'line': start,
                                 'conditions': [f['active'] for f in frames]})
            elif op == 'define' and re.fullmatch(r'\w+', body.strip()):
                condition = '!defined(' + body.strip() + ')'
                if frames and frames[-1]['active'] == condition:
                    guards.append({'macro': body.strip(), 'line': start, 'condition': condition})
            if definitions is not None and op in ('define', 'undef'):
                match = re.match(r'(\w+)(.*)', body)
                if match:
                    definitions.append({'name': match[1], 'operation': op, 'value': match[2].strip(),
                                        'line': start, 'conditions': [f['active'] for f in frames]})
            # Macro definitions can contain intrinsic references too.
            if op != 'define':
                continue
        # Token matches are candidates, including declarations and macro bodies.
        ts = tokens(line)
        for i, token in enumerate(ts[:-1]):
            if token in names and ts[i + 1] in ('(', '<'):
                refs.append({'name': token, 'line': start, 'end_line': index,
                             'conditions': [f['active'] for f in frames],
                             'core_guards': [g for a, b, g in core_guards if a <= start <= b],
                             'resolution': 'lexical_reference_not_resolved_call'})
    if frames:
        errors.append({'line': len(lines), 'reason': 'unterminated_conditional'})
    return refs, includes, errors, guards


def extract(toolkit, output=DEFAULT):
    db = Database()
    root = toolkit.resolve()
    metadata_path = root / 'share/info/bisheng-compiler/version.info'
    metadata = metadata_path.read_text()
    if 'Version=9.3.0\n' not in metadata or 'timestamp=20261104_' not in metadata:
        raise ValueError('Toolkit version differs from pinned weekly')
    for target in db.data['compatibility']['chip_mappings']:
        if sha(root / target['source']['file']) != target['source']['sha256']:
            raise ValueError('Platform configuration differs from pinned target snapshot')
    names = {r['name'] for r in db.records if r['kind'].startswith('interface')}
    names.update(b for r in db.records for b in r['builtins'])
    files, references, edges, issues, definitions = {}, [], [], [], []
    paths = sorted({p.resolve() for rel in ROOTS for p in (root / rel).rglob('*.h')})
    if not paths:
        raise ValueError('No AscendC headers in pinned scan roots')
    # Reject a mismatching toolkit before deriving any evidence.
    for source in db.data['files']:
        path = root / db.data['source']['resource_root'] / source['path']
        if sha(path) != source['sha256']:
            raise ValueError('Resource header differs from pinned catalog: ' + str(path))
    for path in paths:
        rel = path.relative_to(root).as_posix()
        raw = path.read_bytes()
        encoding = 'utf-8'
        try:
            text = raw.decode(encoding)
        except UnicodeDecodeError:
            encoding = 'latin-1-byte-preserving-fallback'
            text = raw.decode('latin-1')
            issues.append({'file': rel, 'reason': 'non_utf8_ascii_tokens_only'})
        file_definitions = []
        refs, includes, errors, guards = scan_text(text, names, file_definitions)
        definitions.extend({**d, 'file': rel} for d in file_definitions)
        files[rel] = {'sha256': sha(path), 'encoding': encoding, 'guards': guards, 'package_verified': False}
        hint = next((s for s in path.parts if re.fullmatch(r'dav_[a-z0-9]+', s)), None)
        for ref in refs:
            references.append({**ref, 'file': rel, 'directory_hint': hint})
        for inc in includes:
            candidate = (path.parent / inc['name']).resolve()
            resolved = candidate.relative_to(root).as_posix() if candidate.is_relative_to(root) and candidate.is_file() else None
            edges.append({**inc, 'file': rel, 'resolved_relative_path': resolved})
        issues.extend({**e, 'file': rel} for e in errors)
    resource_definitions = []
    for source in db.data['files']:
        rel = db.data['source']['resource_root'] + '/' + source['path']
        collected = []
        scan_text((root / rel).read_text(), set(), collected)
        resource_definitions.extend({**d, 'file': rel, 'sha256': source['sha256']} for d in collected)
    flags_file = root / 'compiler/tikcpp/ascendc_kernel_cmake/legacy_modules/bisheng_intf.cmake'
    flags = []
    if flags_file.exists():
        lines = flags_file.read_text().splitlines()
        for i, line in enumerate(lines):
            m = re.search(r'--cce-aicore-arch=(dav-c310-(?:vec|cube))', line)
            if m and '-D__DAV_C310__' in lines[i-1]:
                flags.append({'core': m[1], 'explicit_defines': {'__DAV_C310__': 1},
                              'file': str(flags_file.relative_to(root)), 'line': i + 1,
                              'sha256': sha(flags_file), 'level': 'build_recipe_not_predefined_macros'})
    payload = {'schema_version': 'ackb.ccec-support-evidence.v1', 'version': VERSION,
               'compiler_version_metadata': {'file': str(metadata_path.relative_to(root)), 'sha256': sha(metadata_path)},
               'catalog_sha256': db.snapshot_sha256, 'extractor_sha256': sha(Path(__file__)), 'roots': ROOTS,
               'files': files, 'references': references, 'includes': edges, 'parse_issues': issues,
               'macro_definitions': definitions, 'resource_macro_definitions': resource_definitions, 'build_recipes': flags, 'verification': {'compile': 'unverified', 'runtime': 'unverified'},
               'limits': ['Lexical references do not resolve overloads, templates, runtime branches or include reachability.',
                          'Directory names are navigation hints, not architecture support proofs.',
                          'No reference does not imply unsupported; source-package verification is recorded separately.']}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, separators=(',', ':')) + '\n')
    return {'files': len(files), 'references': len(references), 'includes': len(edges), 'parse_issues': len(issues)}


class Support:
    def __init__(self, path=DEFAULT, db=None):
        self.db = db or Database()
        self.path = path
        self.data = json.loads(path.read_text())
        if self.data['version'] != VERSION or self.data['catalog_sha256'] != self.db.snapshot_sha256:
            raise ValueError('Support evidence does not match catalog')
        self.package_proof = None
        proof_path = path.with_name('support-package.json')
        if proof_path.exists():
            proof = json.loads(proof_path.read_text())
            if (proof['version'] != VERSION or not proof['verified'] or proof['missing'] or proof['mismatched']
                    or proof['outer_sha256'] != self.db.data['source']['package_sha256']
                    or any(proof['matches'].get(name) != meta['sha256'] for name, meta in self.data['files'].items())):
                raise ValueError('Source package proof does not match evidence')
            self.package_proof = proof
        self.by_name = defaultdict(list)
        self.routes = defaultdict(list)
        for edge in self.data['includes']:
            if edge['resolved_relative_path']:
                self.routes[edge['resolved_relative_path']].append(edge)
        for ref in self.data['references']:
            self.by_name[ref['name']].append(ref)

    def record(self, record, target, offset=0, limit=5):
        macros = target['profile']['macros'] if target['profile'] else {}
        details = []
        for expression in record['compatibility']['conditions']:
            value = evaluate(expression, macros)
            identifiers = set(re.findall(r'\b[A-Za-z_]\w*\b', expression)) - {'defined', 'and', 'or', 'not'}
            details.append({'expression': expression, 'result': 'unknown' if value is None else 'true' if value else 'false',
                            'missing_macros': sorted(identifiers - macros.keys()) if value is None else []})
        refs = [ref for name in sorted({record['name'], *record['builtins']}) for ref in self.by_name[name]]
        hint = 'dav_' + str(macros.get('__NPU_ARCH__', ''))
        refs.sort(key=lambda ref: (ref['directory_hint'] != hint, ref['file'], ref['line']))
        from ccec_static import StaticAnalysis
        if not hasattr(self, 'static_analysis'):
            self.static_analysis = StaticAnalysis(self)
        arch = macros.get('__NPU_ARCH__')
        static = self.static_analysis.assess(record, arch) if arch is not None else None
        return {'id': record['id'], 'name': record['name'], 'signature': record['signature'],
                'chip': target['chip'], 'core': target['core'],
                'declaration_condition': self.db.condition(record, target),
                'support': 'unverified', 'conditions': details,
                'static_assessment': static,
                'static_trace': self.static_analysis.trace(static, arch) if static else [],
                'ignored_guards': record['compatibility']['ignored_guards'],
                'declaration_evidence': self.db.evidence(record),
                'references_total': len(refs), 'references_offset': offset,
                'references_next_offset': offset + limit if offset + limit < len(refs) else None,
                'references': [{**ref, 'sha256': self.data['files'][ref['file']]['sha256'], 'package_verified': self.package_proof is not None,
                                'incoming_include_edges': self.routes[ref['file']][:3],
                                'incoming_include_edges_total': len(self.routes[ref['file']])}
                               for ref in refs[offset:offset + limit]],
                'gaps': ['compiler_predefined_macro_environment', 'include_reachability', 'overload_acceptance',
                         'target_codegen', 'runtime_validation']}

    def report(self, chip):
        target = self.db.target(chip=chip)
        records = [r for r in self.db.records if r['kind'].startswith('interface')]
        missing = Counter()
        counts = Counter()
        for r in records:
            status = self.db.condition(r, target)
            counts[status] += 1
            if status == 'unknown':
                for expression in r['compatibility']['conditions']:
                    if evaluate(expression, target['profile']['macros']) is None:
                        missing.update(set(re.findall(r'\b[A-Za-z_]\w*\b', expression)) - {'defined', 'and', 'or', 'not'} - target['profile']['macros'].keys())
        return {'chip': chip, 'condition_counts': dict(counts), 'missing_macro_occurrences': dict(missing.most_common()),
                'interfaces_with_references': sum(bool(self.by_name[r['name']] or any(self.by_name[b] for b in r['builtins'])) for r in records),
                'scan': {k: len(self.data[k]) for k in ('files', 'references', 'includes', 'parse_issues')},
                'source_issues': self.data['parse_issues'],
                'unresolved_relative_includes': sum(e['resolved_relative_path'] is None for e in self.data['includes']),
                'package_verified_files': len(self.data['files']) if self.package_proof else 0,
                'compiler_status': 'unverified', 'runtime_status': 'unverified'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    e = sub.add_parser('extract');e.add_argument('--toolkit', type=Path, required=True);e.add_argument('--output', type=Path, default=DEFAULT)
    for command in ('report', 'get', 'matrix'):
        q = sub.add_parser(command)
        if command != 'matrix':
            q.add_argument('--chip', default='Ascend950PR_9579')
        if command in ('get', 'matrix'):
            q.add_argument('identity')
        if command == 'get':
            q.add_argument('--core');q.add_argument('--offset', type=int, default=0);q.add_argument('--limit', type=int, default=5)
    args = p.parse_args()
    if args.command == 'extract':
        result = extract(args.toolkit, args.output)
    else:
        db = Support()
        if args.command == 'report':
            result = db.report(args.chip)
        else:
            if args.command == 'get' and (args.offset < 0 or not 1 <= args.limit <= 50):
                p.error('offset >= 0 and limit 1..50 required')
            r = db.db.by_id.get(args.identity)
            if r is None:
                p.error('Use a record ID returned by query.py search')
            if args.command == 'matrix':
                from ccec_static import StaticAnalysis
                analysis = StaticAnalysis(db)
                result = {'id': r['id'], 'name': r['name'], 'version': VERSION, 'support': 'unverified',
                          'targets': [{'chip': t['chip'], 'npu_arch': t['npu_arch'], 'cores': t['cores'],
                                       'condition': db.db.condition(r, db.db.target(chip=t['chip'])),
                                       'static_assessment': analysis.assess(r, t['npu_arch']),
                                       'mapping_evidence': t['source']} for t in db.db.data['compatibility']['chip_mappings']]}
            else:
                result = db.record(r, db.db.target(chip=args.chip, core=args.core), args.offset, args.limit)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
