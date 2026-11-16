"""Check conservative source tracing and 950 evidence without executing a compiler."""
import json
from pathlib import Path
import socket
import hashlib
from unittest.mock import patch
from types import SimpleNamespace
import sys
from tempfile import TemporaryDirectory
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from ccec_support import Support, scan_text, core_guard_spans
from ccec_probe import run
from query import parser, run as query


class ScannerTests(unittest.TestCase):
    def test_branches_comments_strings_and_core_guard(self):
        text = '''#ifndef HEADER_H
#define HEADER_H
#if __NPU_ARCH__ == 3510
#include "dav_3510/impl.h"
if ASCEND_IS_AIC {
  const char* s = "op( }";
  op(x); // op(x)
}
#elif OTHER
op(y);
#else
op(z);
#endif
#endif
'''
        refs, includes, errors, guards = scan_text(text, {'op'})
        self.assertEqual(len(refs), 3)
        self.assertEqual(refs[0]['core_guards'], ['ASCEND_IS_AIC'])
        self.assertEqual(refs[1]['core_guards'], [])
        self.assertIn('3510', refs[1]['conditions'][-1])
        self.assertIn('OTHER', refs[2]['conditions'][-1])
        self.assertEqual(includes[0]['name'], 'dav_3510/impl.h')
        self.assertEqual(guards[0]['macro'], 'HEADER_H')
        self.assertEqual(errors, [])

    def test_unbalanced_is_reported(self):
        _, _, errors, _ = scan_text('#else\n#if X\nop(x);', {'op'})
        self.assertEqual(len(errors), 2)

    def test_compile_runner_refuses_preparation_host(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            plan = root / 'plan.json'
            plan.write_text(json.dumps({'prepared_host': socket.gethostname()}))
            with self.assertRaisesRegex(ValueError, 'separate authorized compile host'):
                run(plan, root, root / 'out')

    def test_failed_baseline_retains_blocked_results(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('ccec', 'version', 'baseline.cpp', 'op.cpp'):
                (root / name).write_text('fixture')
            h = hashlib.sha256(b'fixture').hexdigest()
            plan = {'prepared_host': 'other-host', 'compiler': {'path': 'ccec', 'sha256': h,
                    'version_file': 'version', 'version_sha256': h}, 'headers': [], 'cores': ['dav-c310-cube'],
                    'probes': [{'name': 'baseline', 'source': 'baseline.cpp', 'sha256': h},
                               {'name': 'op', 'source': 'op.cpp', 'sha256': h}]}
            path = root / 'plan.json'
            path.write_text(json.dumps(plan))
            with patch('ccec_probe.subprocess.run', return_value=SimpleNamespace(returncode=1, stdout='', stderr='environment error')) as compiler:
                result = run(path, root, root / 'out')
            self.assertEqual(compiler.call_count, 2)
            self.assertEqual(result[-1]['status'], 'blocked_by_baseline')
            saved = json.loads((root / 'out/results.json').read_text())
            self.assertEqual(saved['results'], result)
            self.assertEqual(saved['runtime'], 'not_executed')


class SupportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.support = Support()

    def test_950_counts_and_no_unverified_promotion(self):
        report = self.support.report('Ascend950PR_9579')
        self.assertEqual(report['condition_counts'], {'matches': 3524, 'unknown': 1378, 'excluded': 812})
        self.assertEqual(report['compiler_status'], 'unverified')
        self.assertEqual(report['package_verified_files'], 1608)

    def test_950_reference_has_core_and_route_evidence(self):
        record = self.support.db.by_id['960c673e040dc702bc0a']
        result = self.support.record(record, self.support.db.target(chip='Ascend950PR_9579'))
        self.assertEqual(result['support'], 'unverified')
        self.assertTrue(result['references'][0]['package_verified'])
        self.assertIn('ASCEND_IS_AIC', result['references'][0]['core_guards'])
        self.assertEqual(result['references'][0]['directory_hint'], 'dav_3510')
        self.assertEqual(len(result['references'][0]['sha256']), 64)
        self.assertTrue(result['references'][0]['incoming_include_edges'])
        self.assertTrue(result['references_next_offset'])

    def test_unresolved_sources_remain_reported(self):
        self.assertEqual(len(self.support.data['files']), 1608)
        self.assertEqual(len(self.support.data['parse_issues']), 4)
        self.assertTrue(all(e['reason'] == 'non_utf8_ascii_tokens_only' for e in self.support.data['parse_issues']))
        self.assertTrue(all(ref['file'] in self.support.data['files'] for ref in self.support.data['references']))

    def test_stale_package_proof_is_rejected(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'support-evidence.json'
            path.write_bytes(self.support.path.read_bytes())
            proof = dict(self.support.package_proof)
            proof['matches'] = {}
            path.with_name('support-package.json').write_text(json.dumps(proof))
            with self.assertRaisesRegex(ValueError, 'package proof'):
                Support(path)
            path.with_name('support-package.json').unlink()
            self.assertIsNone(Support(path).package_proof)

    def test_query_support_is_bounded_and_target_specific(self):
        response = query(parser().parse_args(['--limit', '1', 'support', '960c673e040dc702bc0a', '--chip', 'Ascend950PR_9579', '--core', 'dav-c310-cube']))
        self.assertEqual(response['items'][0]['core'], 'dav-c310-cube')
        self.assertEqual(response['items'][0]['support'], 'unverified')
        self.assertLess(len(json.dumps(response)), 24000)
        self.assertIn('support_evidence_sha256', response['provenance'])
        schema = json.loads((Path(__file__).resolve().parents[1] / 'schemas/query-v1.schema.json').read_text())
        self.assertIn('support', schema['oneOf'][1]['properties']['operation']['enum'])
