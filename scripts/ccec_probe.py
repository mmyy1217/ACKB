#!/usr/bin/env python3
"""Prepare source-backed compile-only probes; execute only on a separate compile host."""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import subprocess

from catalog import VERSION
from database import Database

PROBES = {
    'baseline': '',
    'pipe_barrier_all': 'pipe_barrier(PIPE_ALL);',
    'set_wait_mte2_scalar': 'set_flag(PIPE_MTE2, PIPE_S, EVENT_ID0);\n  wait_flag(PIPE_MTE2, PIPE_S, EVENT_ID0);',
    'gm_to_cbuf_u32': 'copy_gm_to_cbuf_align_v2((__cbuf__ uint32_t*)0, (__gm__ uint32_t*)src, 0, 1, 32, 0, 0, true, 0, 32, 32);',
}
NAMES = {'baseline': [], 'pipe_barrier_all': ['pipe_barrier'],
         'set_wait_mte2_scalar': ['set_flag', 'wait_flag'], 'gm_to_cbuf_u32': ['copy_gm_to_cbuf_align_v2']}
SOURCE_FILES = {'pipe_barrier_all': 'kernel_operator_sync_impl.h',
                'set_wait_mte2_scalar': 'kernel_operator_sync_impl.h',
                'gm_to_cbuf_u32': 'kernel_operator_data_copy_impl.h'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(toolkit, output, chip):
    db = Database()
    target = next((t for t in db.data['compatibility']['chip_mappings'] if t['chip'] == chip), None)
    if not target or target['npu_arch'] != 3510:
        raise ValueError('Current authored probe forms are scoped to configured 3510 targets')
    version_path = toolkit / 'share/info/bisheng-compiler/version.info'
    metadata = version_path.read_text()
    if 'Version=9.3.0\n' not in metadata or 'timestamp=20261104_' not in metadata:
        raise ValueError('Compiler metadata does not match pinned weekly')
    headers = []
    for f in db.data['files']:
        rel = db.data['source']['resource_root'] + '/' + f['path']
        if digest(toolkit / rel) != f['sha256']:
            raise ValueError('Mismatching pinned header: ' + rel)
        headers.append({'path': rel, 'sha256': f['sha256']})
    binary = 'tools/bisheng_compiler/bin/ccec'
    output.mkdir(parents=True, exist_ok=True)
    probes = []
    for name, body in PROBES.items():
        code = '#include <stdint.h>\nextern "C" __global__ __aicore__ void probe(__gm__ uint8_t* src) {\n  ' + body + '\n}\n'
        path = output / (name + '.cpp')
        path.write_text(code)
        evidence = []
        if name in SOURCE_FILES:
            rel = 'x86_64-linux/asc/impl/basic_api/dav_3510/' + SOURCE_FILES[name]
            source = toolkit / rel
            for number, line in enumerate(source.read_text().splitlines(), 1):
                if any(symbol + '(' in line for symbol in NAMES[name]):
                    evidence.append({'file': rel, 'line': number, 'sha256': digest(source)})
        probes.append({'name': name, 'source': path.name, 'sha256': digest(path),
                       'record_ids': [r['id'] for r in db.records if r['name'] in NAMES[name]],
                       'evidence': evidence, 'status': 'prepared_not_executed'})
    manifest = {'schema_version': 'ackb.ccec-probe-plan.v1', 'version': VERSION,
                'prepared_host': socket.gethostname(), 'chip': chip,
                'cores': sorted(set(target['cores'].values())), 'target_evidence': target['source'],
                'compiler': {'path': binary, 'sha256': digest(toolkit / binary),
                             'version_file': str(version_path.relative_to(toolkit)), 'version_sha256': digest(version_path)},
                'headers': headers, 'catalog_sha256': db.snapshot_sha256, 'probes': probes,
                'coverage': {'authored_forms': 3, 'interface_records': 5714,
                             'other_forms': 'require_source_backed_operands_not_generated_zero_arguments'},
                'limits': ['Compile-only; never execute these kernels.',
                           'Failure remains unclassified; baseline failure is an environment failure.',
                           'Success applies only to the exact source, flags, target and compiler hash.']}
    (output / 'plan.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


def run(plan_path, toolkit, output):
    plan = json.loads(plan_path.read_text())
    if socket.gethostname() == plan['prepared_host']:
        raise ValueError('Compile execution must use the separate authorized compile host')
    compiler = toolkit / plan['compiler']['path']
    if digest(compiler) != plan['compiler']['sha256'] or digest(toolkit / plan['compiler']['version_file']) != plan['compiler']['version_sha256']:
        raise ValueError('Remote compiler differs from pinned plan; no execution')
    for entry in plan['headers']:
        if digest(toolkit / entry['path']) != entry['sha256']:
            raise ValueError('Remote header mismatch; no execution: ' + entry['path'])
    for probe in plan['probes']:
        if digest(plan_path.parent / probe['source']) != probe['sha256']:
            raise ValueError('Probe source differs from plan')
    output.mkdir(parents=True, exist_ok=True)
    results = []
    for core in plan['cores']:
        flags = [str(compiler), '-x', 'cce', '--cce-aicore-only', '--cce-aicore-arch=' + core]
        # Capture both raw diagnostics and output; never infer unsupported from failure.
        jobs = [('macros', ['-E', '-dM', '-'], '')]
        jobs += [(p['name'], ['-O2', '-c', str((plan_path.parent / p['source']).resolve()), '-o', str((output / (core + '-' + p['name'] + '.o')).resolve())], None) for p in plan['probes']]
        baseline_ok = False
        for name, args, stdin in jobs:
            if name not in ('macros', 'baseline') and not baseline_ok:
                results.append({'core': core, 'name': name, 'status': 'blocked_by_baseline'})
                continue
            command = flags + args
            prefix = output / (core + '-' + name)
            try:
                result = subprocess.run(command, input=stdin, text=True, capture_output=True, timeout=60, cwd=output)
                prefix.with_suffix('.stdout').write_text(result.stdout)
                prefix.with_suffix('.stderr').write_text(result.stderr)
                status = 'accepted' if result.returncode == 0 else 'failed_unclassified'
                item = {'core': core, 'name': name, 'command': command, 'returncode': result.returncode,
                        'status': status, 'stdout_sha256': digest(prefix.with_suffix('.stdout')),
                        'stderr_sha256': digest(prefix.with_suffix('.stderr'))}
                object_path = output / (core + '-' + name + '.o')
                if result.returncode == 0 and name != 'macros':
                    if object_path.is_file():
                        item['object_sha256'] = digest(object_path)
                    else:
                        item['status'] = 'no_output_unverified'
                if name == 'baseline':
                    baseline_ok = item['status'] == 'accepted'
            except subprocess.TimeoutExpired as exc:
                prefix.with_suffix('.stdout').write_bytes(exc.stdout or b'')
                prefix.with_suffix('.stderr').write_bytes(exc.stderr or b'')
                item = {'core': core, 'name': name, 'command': command, 'status': 'timeout'}
            except OSError as exc:
                prefix.with_suffix('.stderr').write_text(str(exc))
                item = {'core': core, 'name': name, 'command': command, 'status': 'environment_error'}
            results.append(item)
            (output / 'results.json').write_text(json.dumps({'plan_sha256': digest(plan_path), 'runtime': 'not_executed', 'results': results}, indent=2) + '\n')
    (output / 'results.json').write_text(json.dumps({'plan_sha256': digest(plan_path), 'runtime': 'not_executed', 'results': results}, indent=2) + '\n')
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--toolkit', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--chip', default='Ascend950PR_9579')
    p = sub.add_parser('run')
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--toolkit', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'prepare':
        result = prepare(args.toolkit, args.output, args.chip)
        print(json.dumps({'cores': result['cores'], 'probes': len(result['probes']), 'status': 'prepared_not_executed'}))
    else:
        print(json.dumps(run(args.plan.resolve(), args.toolkit.resolve(), args.output.resolve()), indent=2))


if __name__ == '__main__':
    main()
