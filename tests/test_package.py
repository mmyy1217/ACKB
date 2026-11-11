import hashlib
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import tarfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from verify_package import archive_stream, verify


def makeself(entries):
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode='w:gz') as archive:
        for name, content in entries.items():
            member = tarfile.TarInfo(name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
    return b'#!/bin/sh\nskip="3"\nexit 99\n' + payload.getvalue()


class PackageVerificationTests(unittest.TestCase):
    def fixture(self, root, actual=b'header declaration'):
        nested = makeself({'tools/bisheng_compiler/lib/clang/15.0.5/include/sample.h': actual})
        package = root / 'Ascend-cann-toolkit_test_linux-x86_64.run'
        package.write_bytes(makeself({'run_package/cann-bisheng-compiler_9.3.0_linux-x86_64.run': nested}))
        dataset = root / 'catalog.json'
        dataset.write_text(json.dumps({'source': {'package_name': package.name, 'package_verified': False}, 'files': [{'path': 'sample.h', 'sha256': hashlib.sha256(b'header declaration').hexdigest()}], 'records': [], 'counts': {}, 'report': {'limitations': []}}))
        return package, dataset

    def test_nested_package_matches_scoped_headers(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            package, dataset = self.fixture(root)
            verify(package, dataset, root / 'artifacts')
            source = json.loads(dataset.read_text())['source']
            self.assertTrue(source['package_verified'])
            self.assertEqual(source['package_verification']['scope'], 'scanned_resource_headers')
            self.assertEqual(source['package_verification']['matches'][0]['file'], 'sample.h')
            self.assertEqual(source['package_sha256'], hashlib.sha256(package.read_bytes()).hexdigest())

    def test_mismatch_does_not_promote_dataset(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            package, dataset = self.fixture(root, b'different header')
            with self.assertRaisesRegex(ValueError, 'comparison failed'):
                verify(package, dataset, root / 'artifacts')
            self.assertFalse(json.loads(dataset.read_text())['source']['package_verified'])
            report = json.loads((root / 'artifacts/verification.json').read_text())
            self.assertEqual(report['mismatched'], ['sample.h'])

    def test_non_makeself_input_is_rejected(self):
        with TemporaryDirectory() as directory:
            package = Path(directory) / 'invalid.run'
            package.write_bytes(b'not a Makeself file')
            with self.assertRaisesRegex(ValueError, 'No Makeself archive offset'):
                archive_stream(package)


if __name__ == '__main__':
    unittest.main()
