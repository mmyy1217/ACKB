import json
from pathlib import Path
import unittest

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

import ascendc
import cce_dialect
import query


class MultiBackendTests(unittest.TestCase):
    def test_cce_dialect_two_layers_are_valid_and_linked(self):
        data = json.loads(cce_dialect.OUTPUT.read_text())
        self.assertEqual(cce_dialect.validate_model(data), [])
        self.assertGreaterEqual(data['counts']['ops'], 240)
        self.assertGreaterEqual(data['counts']['intrinsics'], 1000)
        # Verify cce.vadd and cce.mad lowerings
        ops_by_name = {o['name']: o for o in data['ops']}
        self.assertIn('cce.vadd', ops_by_name)
        self.assertIn('cce.mad', ops_by_name)
        self.assertTrue(len(ops_by_name['cce.vadd']['intrinsic_ids']) >= 18)
        self.assertTrue(len(ops_by_name['cce.mad']['intrinsic_ids']) >= 8)
        self.assertIsNotNone(ops_by_name['cce.mad']['spec'])

    def test_ascendc_two_layers_are_valid_and_linked_to_ccec(self):
        data = json.loads(ascendc.OUTPUT.read_text())
        self.assertEqual(ascendc.validate_model(data), [])
        self.assertGreaterEqual(data['counts']['basic_api_total'], 500)
        self.assertGreaterEqual(data['counts']['capi_total'], 1500)
        capi_by_name = {x['name']: x for x in data['c_api']}
        self.assertIn('asc_mmad', capi_by_name)
        self.assertIn('asc_loadalign', capi_by_name)
        self.assertIn('asc_sub', capi_by_name)
        self.assertEqual(capi_by_name['asc_mmad']['condition_3510'], 'matches')
        self.assertTrue(any(c['name'] == 'mad' for c in capi_by_name['asc_mmad']['ccec_callees']))

    def test_query_cli_supports_ascendc_and_cce_dialect_layers(self):
        for argv, expected_backend in [
            (['--backend', 'cce-dialect', 'info'], 'cce-dialect'),
            (['--backend', 'cce-dialect', '--layer', 'ops', 'search', 'vadd'], 'cce-dialect'),
            (['--backend', 'cce-dialect', '--layer', 'intrinsics', 'search', 'vadd'], 'cce-dialect'),
            (['--backend', 'ascendc', 'info'], 'ascendc'),
            (['--backend', 'ascendc', '--layer', 'basic', 'search', 'DataCopy'], 'ascendc'),
            (['--backend', 'ascendc', '--layer', 'capi', 'search', 'asc_mmad'], 'ascendc'),
        ]:
            args = query.parser().parse_args(argv)
            res = query.run(args)
            self.assertEqual(res['backend'], expected_backend)
            self.assertGreater(res['total'], 0)


if __name__ == '__main__':
    unittest.main()
