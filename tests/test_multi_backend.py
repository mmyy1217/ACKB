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


class EvidenceRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.asc = json.loads(ascendc.OUTPUT.read_text())
        cls.dialect = json.loads(cce_dialect.OUTPUT.read_text())

    def test_reg_forwarders_preserve_load_store_direction_and_call_sources(self):
        records = {r['qualified_name']: r for r in self.asc['basic_api']}
        for name, expected, forbidden in [('LoadAlign', {'vlds', 'vld'}, {'vsts', 'vst'}),
                                          ('StoreAlign', {'vsts', 'vst'}, {'vlds', 'vld'})]:
            record = records['AscendC::Reg::' + name]
            callees = {c['name'] for c in record['ccec_callees']}
            self.assertTrue(expected <= callees)
            self.assertFalse(forbidden & callees)
            trace = record['call_trace']
            self.assertTrue(any(n['name'] == name and '/reg_compute/kernel_reg_compute_datacopy_intf_impl.h' in n['source']['file']
                                for n in trace['nodes'].values()))
            self.assertTrue(any(e['call']['name'] == 'DataCopyImpl' for e in trace['edges']))
            for edge in trace['edges']:
                self.assertIn(edge['call']['source']['file'], self.asc['files'])
                self.assertNotEqual(ascendc.eval_3510(edge['call']['conditions'], edge['call']['ignored_guards']), 'excluded')
                if 'callee' in edge:
                    target = trace['nodes'][edge['callee']]
                    self.assertNotEqual(ascendc.eval_3510(target['conditions'], target['ignored_guards']), 'excluded')
            result = query.run(query.parser().parse_args(['--backend', 'ascendc', '--limit', '2', 'relations', record['id']]))
            self.assertEqual(result['items'][0]['relation'], 'candidate_call')
            self.assertEqual(len(result['items'][0]['call_sha256']), 64)
            self.assertEqual(len(result['items'][0]['caller_definition']['sha256']), 64)
            self.assertIsNotNone(result['next_offset'])
            result = query.run(query.parser().parse_args(['--backend', 'ascendc', 'get', record['id']]))
            self.assertNotIn('call_trace', result['items'][0])
        self.assertTrue(records['AscendC::Reg::StoreAlign']['call_trace']['unresolved'])

    def test_helper_candidates_use_call_arity_and_address_spaces(self):
        parsed = ascendc.parse_functions_in_header('''
inline void LoadAlign(U& reg, __ubuf__ T* src, int stride) {
  DataCopyImpl<T, Mode>(reg, src, stride);
#if __NPU_ARCH__ == 9201
  vsts(src, reg);
#endif
}
inline void DataCopyImpl(U& reg, __ubuf__ T* src, int stride) {}
inline void DataCopyImpl(__ubuf__ T* dst, U& reg, MaskReg& mask) {}
inline void DataCopyImpl(U& reg, __ubuf__ T* src) {}
''', 'sample.h', {'vsts'})
        caller, load, store, short = parsed
        site = next(c for c in caller['call_sites'] if c['name'] == 'DataCopyImpl')
        self.assertEqual(site['arguments'], ['reg', 'src', 'stride'])
        self.assertEqual(site['source']['line'], 3)
        self.assertTrue(ascendc.compatible_helper(caller, site, load))
        self.assertFalse(ascendc.compatible_helper(caller, site, store))
        self.assertFalse(ascendc.compatible_helper(caller, site, short))
        excluded = next(c for c in caller['call_sites'] if c['name'] == 'vsts')
        self.assertEqual(ascendc.eval_3510(excluded['conditions'], excluded['ignored_guards']), 'excluded')

    def test_architecture_branch_cannot_be_overridden_by_body(self):
        record = next(x for x in self.asc['c_api'] if x['name'] == '__bfloat1622fp4x2_e1m2_rn')
        self.assertEqual(record['condition_3510'], 'excluded')
        import copy
        broken = copy.deepcopy(self.asc)
        next(x for x in broken['c_api'] if x['name'] == record['name'])['condition_3510'] = 'matches'
        self.assertTrue(any('Target condition mismatch' in e for e in ascendc.validate_model(broken)))
        self.assertTrue(any('9201' in c for f in record['forms'] for s in f['sources'] for c in s['conditions']))
        parsed = ascendc.parse_functions_in_header('''
#ifndef SAMPLE_H
#define SAMPLE_H
#if __NPU_ARCH__ == 9201
inline void f(int x) {}
#elif __NPU_ARCH__ == 3510
inline void f(float x) {}
#else
inline void f(double x) {}
#endif
#ifdef FEATURE_UNKNOWN
inline void g() {}
#endif
#endif
''', 'sample.h', set())
        self.assertEqual([ascendc.eval_3510(f['conditions'], f['ignored_guards']) for f in parsed],
                         ['excluded', 'matches', 'excluded', 'unknown'])
        literal = ascendc.parse_functions_in_header('inline void h(const char *s = \"a,b\");', 'sample.h', set())[0]
        self.assertEqual(literal['parameters'], ['const char *s = \"a,b\"'])
        # The guard is retained as provenance, not confused with architecture exclusion.
        self.assertIn('!defined(SAMPLE_H)', parsed[0]['conditions'])

    def test_all_forms_and_conditional_occurrences_survive_export(self):
        record = next(x for x in self.asc['c_api'] if x['name'] == 'asc_cast')
        self.assertEqual(record['overload_count'], 467)
        self.assertEqual(len(record['forms']), 467)
        exported = ascendc.web_payload(self.asc)
        self.assertEqual(next(x for x in exported['c_api'] if x['name'] == 'asc_cast')['forms'], record['forms'])
        parsed = ascendc.parse_functions_in_header('''
#if __NPU_ARCH__ == 3510
inline void f(int x);
#else
inline void f(int x);
#endif
''', 'sample.h', set())
        forms = ascendc.parameter_forms(parsed)
        self.assertEqual(len(forms), 1)
        self.assertEqual(len(forms[0]['sources']), 2)
        self.assertEqual({s['condition_3510'] for s in forms[0]['sources']}, {'matches', 'excluded'})
        import copy
        broken = copy.deepcopy(self.asc)
        next(x for x in broken['c_api'] if x['name'] == 'asc_cast')['forms'].pop()
        self.assertTrue(any('Truncated forms' in e for e in ascendc.validate_model(broken)))

    def test_only_concrete_llvm_symbols_are_counted(self):
        self.assertEqual(self.dialect['counts']['intrinsics'], 1069)
        self.assertEqual(self.dialect['counts']['unresolved_lowerings'], 5)
        for item in self.dialect['intrinsics']:
            self.assertRegex(item['name'], r'^llvm\.hivm\.[A-Za-z0-9_.]+$')
            self.assertNotIn('ccec_op_ids', item)
            self.assertEqual(item['relation_resolution'], 'lexical_name_candidate')
        self.assertTrue(any('print' in r['mnemonic'] for r in self.dialect['unresolved_lowerings']))
        self.assertEqual(cce_dialect.web_payload(self.dialect)['unresolved_lowerings'], self.dialect['unresolved_lowerings'])

    def test_query_contract_forms_pagination_and_source_hashes(self):
        for backend in ('ascendc', 'cce-dialect'):
            schema = query.run(query.parser().parse_args(['--backend', backend, 'schema']))
            result = query.run(query.parser().parse_args(['--backend', backend, 'info']))
            self.assertEqual(result['schema_version'], schema['properties']['schema_version']['const'])
            self.assertIn(backend, schema['properties']['backend']['enum'])
            self.assertTrue(set(schema['oneOf'][1]['required']) <= set(result))
            self.assertEqual(result['verification']['compile'], 'unverified')
        offset, found = 0, []
        while offset is not None:
            result = query.run(query.parser().parse_args(['--backend', 'ascendc', '--limit', '50', '--offset', str(offset),
                                                         'forms', 'ascendc_capi_asc_cast']))
            found.extend(result['items'])
            offset = result['next_offset']
        self.assertEqual(len(found), 467)
        result = query.run(query.parser().parse_args(['--backend', 'ascendc', 'get', 'ascendc_capi_asc_cast']))
        self.assertEqual(result['items'][0]['forms_query']['total'], 467)
        result = query.run(query.parser().parse_args(['--backend', 'ascendc', 'evidence', 'ascendc_capi_asc_cast']))
        self.assertEqual(len(result['items'][0]['sha256']), 64)
        with self.assertRaises(ValueError):
            query.run(query.parser().parse_args(['--backend', 'ascendc', 'search', '--chip', 'Ascend310']))
        with self.assertRaises(ValueError):
            query.run(query.parser().parse_args(['--backend', 'ascendc', 'search', '--signature', 'int']))

if __name__ == '__main__':
    unittest.main()
