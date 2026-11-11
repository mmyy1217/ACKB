#!/usr/bin/env python3
"""Match scanned headers against a Makeself Toolkit package without executing it."""

import argparse
import json
from pathlib import Path
import re
import shutil
import tarfile

from catalog import ROOT, VERSION, file_digest, validate


def archive_stream(path):
    source = path.open('rb')
    header = source.read(16384)
    match = re.search(rb'\nskip="(\d+)"', header)
    if not match:
        source.close()
        raise ValueError(f'No Makeself archive offset in {path.name}')
    count = int(match[1])
    if not 0 < count < 10000:
        source.close()
        raise ValueError('Makeself header exceeds supported bounds')
    source.seek(0)
    for _ in range(count):
        source.readline()
    return source


def verify(package, dataset, work_dir):
    data = json.loads(dataset.read_text())
    validate(data)
    if package.name != data['source']['package_name']:
        raise ValueError('Package filename differs from the target dataset version')
    work_dir.mkdir(parents=True, exist_ok=True)
    outer_manifest, inner_manifest, matches = [], [], {}
    nested = None
    with archive_stream(package) as source, tarfile.open(fileobj=source, mode='r|*') as archive:
        for member in archive:
            outer_manifest.append({'path': member.name, 'bytes': member.size})
            if member.isfile() and re.fullmatch(r'cann-bisheng-compiler_[\w.~-]+_linux-x86_64\.run', Path(member.name).name):
                if nested is not None:
                    raise ValueError('Multiple compiler packages require explicit selection')
                nested = work_dir / Path(member.name).name
                with nested.open('wb') as target:
                    shutil.copyfileobj(archive.extractfile(member), target)
    if nested is None:
        raise ValueError('No compiler package found inside the Toolkit')
    expected = {f['path']: f['sha256'] for f in data['files']}
    with archive_stream(nested) as source, tarfile.open(fileobj=source, mode='r|*') as archive:
        for member in archive:
            inner_manifest.append({'path': member.name, 'bytes': member.size})
            if not member.isfile():
                continue
            for name, expected_hash in expected.items():
                if member.name.endswith('/lib/clang/15.0.5/include/' + name):
                    if name in matches:
                        raise ValueError(f'Multiple package entries match {name}')
                    target = work_dir / name
                    with target.open('wb') as output:
                        shutil.copyfileobj(archive.extractfile(member), output)
                    matches[name] = {'file': name, 'package_path': member.name, 'package_sha256': file_digest(target), 'dataset_sha256': expected_hash}
    report = {'scope': 'scanned_resource_headers', 'outer_package': package.name, 'outer_sha256': file_digest(package), 'compiler_package': nested.name, 'compiler_sha256': file_digest(nested), 'matches': list(matches.values()), 'missing': sorted(set(expected) - set(matches)), 'mismatched': sorted(n for n, item in matches.items() if item['package_sha256'] != item['dataset_sha256'])}
    for name, obj in [('outer-manifest.json', outer_manifest), ('compiler-manifest.json', inner_manifest), ('verification.json', report)]:
        (work_dir / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')
    if report['missing'] or report['mismatched']:
        raise ValueError(f'Package header comparison failed: {report["missing"]=}, {report["mismatched"]=}')
    data['source']['package_sha256'] = report['outer_sha256']
    data['source']['package_verified'] = True
    data['source']['package_verification'] = report
    data['report']['limitations'] = [x for x in data['report']['limitations'] if 'have not been compared' not in x]
    validate(data)
    dataset.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    print(f'Package verified: {len(matches)} scanned headers match exactly. SHA-256 {report["outer_sha256"]}')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--data', type=Path, default=ROOT / 'data' / VERSION / 'catalog.json')
    args = parser.parse_args()
    verify(args.package, args.data, args.work_dir)
