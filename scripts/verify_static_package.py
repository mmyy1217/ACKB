#!/usr/bin/env python3
"""Verify AscendC source-index hashes against the pinned nested package, without installation."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tarfile

from catalog import ROOT, VERSION, file_digest
from ccec_support import DEFAULT
from verify_package import archive_stream

OUTPUT = DEFAULT.with_name('support-package.json')
NESTED = 'cann-asc-devkit_9.3.0_linux-x86_64.run'


def compare_archive(nested, expected):
    matches = {}
    with archive_stream(nested) as source, tarfile.open(fileobj=source, mode='r|*') as archive:
        for member in archive:
            name = member.name.removeprefix('./')
            if member.isfile() and name in expected:
                if name in matches:
                    raise ValueError('Duplicate archive source: ' + name)
                h = hashlib.sha256()
                stream = archive.extractfile(member)
                for block in iter(lambda: stream.read(1024 * 1024), b''):
                    h.update(block)
                matches[name] = h.hexdigest()
    return matches


def verify(package, work_dir, output=OUTPUT):
    catalog = json.loads((ROOT / 'data' / VERSION / 'catalog.json').read_text())
    evidence = json.loads(DEFAULT.read_text())
    outer_hash = file_digest(package)
    if package.name != catalog['source']['package_name'] or outer_hash != catalog['source']['package_sha256']:
        raise ValueError('Package differs from pinned catalog package')
    work_dir.mkdir(parents=True, exist_ok=True)
    nested = work_dir / NESTED
    found = False
    with archive_stream(package) as source, tarfile.open(fileobj=source, mode='r|*') as archive:
        for member in archive:
            if member.isfile() and Path(member.name).name == NESTED:
                with nested.open('wb') as dest:
                    shutil.copyfileobj(archive.extractfile(member), dest)
                found = True
                break
    if not found:
        raise ValueError('AscendC source package not found')
    expected = {name: m['sha256'] for name, m in evidence['files'].items()}
    matches = compare_archive(nested, expected)
    missing = sorted(set(expected) - matches.keys())
    mismatched = sorted(name for name, value in matches.items() if expected[name] != value)
    report = {'schema_version': 'ackb.ccec-source-package.v1', 'version': VERSION,
              'scope': 'scanned_ascendc_source_files', 'outer_package': package.name, 'outer_sha256': outer_hash,
              'nested_package': NESTED, 'nested_sha256': file_digest(nested),
              'matches': matches, 'missing': missing, 'mismatched': mismatched,
              'verified': not missing and not mismatched}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    if missing or mismatched:
        raise ValueError(f'Source verification incomplete: missing={missing}, mismatched={mismatched}')
    print(f'Verified {len(matches)} AscendC source files against pinned package')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    args = parser.parse_args()
    verify(args.package, args.work_dir)
