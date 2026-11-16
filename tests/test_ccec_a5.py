"""A5 interface identity and default query scope regressions."""
import sys
from pathlib import Path
import unittest
from collections import Counter
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from database import Database
from ccec_a5 import interfaces
from query import parser, run


class A5Tests(unittest.TestCase):
    def test_interface_partition_and_uniqueness(self):
        items = interfaces(Database())
        self.assertEqual(Counter(i['condition'] for i in items), {'matches':357,'unknown':191,'excluded':66})
        self.assertEqual(len({i['id'] for i in items}),614)
        copy = next(i for i in items if i['name']=='copy_gm_to_ubuf' and not i['namespace'])
        self.assertIn('41997fe279e39ece787b',copy['record_ids'])
        self.assertIn('ccec_op___builtin_cce_copy_gm_to_ubuf_align_v2',copy['op_ids'])
        self.assertNotIn('ccec_op___builtin_cce_copy_gm_to_ubuf',copy['op_ids'])

    def test_defaults_and_unknown_opt_in(self):
        response=run(parser().parse_args(['interfaces']))
        self.assertEqual(response['total'],357)
        self.assertEqual(response['target']['chip'],'Ascend950PR_9579')
        self.assertTrue(all(i['condition']=='matches' for i in response['items']))
        self.assertEqual(run(parser().parse_args(['interfaces','--include-unknown']))['total'],548)
        item=response['items'][0]
        self.assertEqual(run(parser().parse_args(['get',item['id']]))['items'][0],item)
        with self.assertRaisesRegex(ValueError,'fixed to'):
            run(parser().parse_args(['get',item['id'],'--chip','Ascend910B2']))
        ops=run(parser().parse_args(['ops']))
        self.assertEqual(ops['target']['chip'],'Ascend950PR_9579')
        self.assertTrue(all(i['assessment']['condition']=='matches' for i in ops['items']))
