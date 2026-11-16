"""Source-derived A5 call evidence must not masquerade as a formal signature."""
import copy
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from ccec_calls import load_calls, validate, functions, argument_evidence
from database import Database
from query import parser, run


class CallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db = Database()
        cls.data = load_calls(cls.db)

    def test_coverage_and_source_guards(self):
        d = self.data
        self.assertEqual(d['coverage']['candidates'], 256)
        self.assertEqual(d['coverage']['unresolved'], 0)
        validate(d, self.db)
        calls = [c for c in d['calls'] if c['name']=='copy_gm_to_cbuf_align_v2']
        self.assertTrue(calls)
        self.assertEqual({c['argument_count'] for c in calls}, {11})
        self.assertTrue(all(c['formal_signature']=='unverified' for c in calls))
        capi = next(c for c in calls if '/c_api/' in c['source']['file'] and 'composite' not in c['source']['file'])
        self.assertEqual(capi['arguments'][0]['observed_type'],'__cbuf__ uint8_t *')
        self.assertIn('if ASC_IS_AIC',capi['block_guards'])
        self.assertEqual(capi['arguments'][8]['observed_type'],'uint8_t')
        self.assertTrue(all(c['transfer_check']['status']=='agrees' for c in d['calls']))
        self.assertTrue(all(f['package_verified'] for f in d['files'].values()))
        self.assertTrue(all(f['architecture_selector_path'] for f in d['files'].values()))
        self.assertEqual(self.db.by_id['0cc57031be88bd3f259d']['name'],'copy_gm_to_cbuf')
        self.assertEqual(self.db.condition(self.db.by_id['0cc57031be88bd3f259d'],self.db.target(chip='Ascend950PR_9579')),'unknown')

    def test_query_and_stale_source(self):
        result = run(parser().parse_args(['--limit','1','calls','copy_gm_to_cbuf_align_v2']))
        self.assertGreater(result['total'],1)
        self.assertEqual(len(result['items']),1)
        self.assertEqual(result['next_offset'],1)
        item = result['items'][0]
        self.assertEqual(run(parser().parse_args(['get',item['id']]))['items'][0],item)
        bad = copy.deepcopy(self.data)
        bad['catalog_sha256']='wrong'
        with self.assertRaisesRegex(AssertionError,'Stale'):
            validate(bad,self.db)

    def test_parameter_types_remain_observed(self):
        self.assertEqual(argument_evidence('static_cast<uint8_t>(mode)',{})['observed_type'],'uint8_t')
        self.assertIsNone(argument_evidence('count * 2',{'count':'uint16_t'})['observed_type'])
        self.assertEqual(argument_evidence('0',{})['observed_type'],'int')
        f = functions('__aicore__ inline void X<T>::run(__gm__ T* src) { f(src, g(1, 2)); }')[0]
        self.assertEqual(f['name'],'X<T>::run')
        self.assertEqual(f['bindings']['src'],'__gm__ T *')
