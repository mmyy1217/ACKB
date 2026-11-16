"""Check op identity, layer partitioning and conservative architecture evidence."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from ccec_ops import Ops, build_model, validate, assessment
from database import Database
from query import parser, run


class OpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ops = Ops()
        cls.db = cls.ops.db

    def test_unique_builtin_and_complete_partition(self):
        self.assertTrue(validate(self.ops.model, self.db))
        self.assertEqual(len(self.ops.by_id), len({o['builtin'] for o in self.ops.model['ops']}))
        self.assertEqual(len(self.ops.model['record_layers']), 5714)
        self.assertEqual(self.ops.model['record_layers']['13c808703f3d6b63c4c4']['layer'], 'intrinsic_entry')
        self.assertEqual(self.ops.model['record_layers']['41997fe279e39ece787b']['layer'], 'wrapper')

    def test_950_wrapper_targets_align_v2_not_same_name(self):
        edges = self.ops.relations('41997fe279e39ece787b')
        self.assertEqual({e['target_op'] for e in edges}, {'ccec_op___builtin_cce_copy_gm_to_ubuf_align_v2'})
        self.assertEqual(edges[0]['reference'], '__cce_scalar::copy_gm_to_ubuf_align_v2')
        self.assertIn('3510', ' '.join(edges[0]['conditions']))
        original = self.ops.by_id['ccec_op___builtin_cce_copy_gm_to_ubuf']
        self.assertNotIn('41997fe279e39ece787b', original['caller_records'])
        self.assertEqual(original['entry_records'], ['13c808703f3d6b63c4c4'])
        self.assertEqual(original['forms'], [])

    def test_call_only_op_does_not_inherit_wrapper_architecture(self):
        op = next(o for o in self.ops.model['ops'] if not o['entry_records'])
        result = assessment(op, self.db, self.db.target(chip='Ascend950PR_9579'))
        self.assertEqual(result['condition'], 'unknown')
        self.assertFalse(result['wrapper_support_inherited'])
        self.assertEqual(result['support'], 'unverified')

    def test_duplicate_alias_sources_merge_without_losing_evidence(self):
        db = copy.deepcopy(self.db)
        original = db.by_id['13c808703f3d6b63c4c4']
        alias = copy.deepcopy(original)
        alias.update(id='test-alias', name='different_alias')
        db.records.append(alias)
        model = build_model(db)
        op = next(o for o in model['ops'] if o['builtin'] == '__builtin_cce_copy_gm_to_ubuf')
        self.assertEqual(set(op['entry_records']), {original['id'], 'test-alias'})
        self.assertIn('__cce_scalar::different_alias', op['aliases'])
        self.assertEqual(len(model['ops']), len(self.ops.model['ops']))

    def test_string_builtin_and_unqualified_same_name_are_not_relations(self):
        db = copy.deepcopy(self.db)
        record = copy.deepcopy(db.by_id['41997fe279e39ece787b'])
        record.update(id='test-wrapper', definition='void test(){ const char* s="__builtin_cce_fake()"; copy_gm_to_ubuf(); }')
        db.records.append(record)
        model = build_model(db)
        self.assertEqual(model['record_layers']['test-wrapper']['op_ids'], [])
        self.assertFalse(any(o['builtin']=='__builtin_cce_fake' for o in model['ops']))
        self.assertTrue(any(p.get('record_id')=='test-wrapper' for p in model['unresolved']))

    def test_queries_keep_original_record_ids_and_op_ids(self):
        result = run(parser().parse_args(['ops', '--name', 'copy_gm_to_ubuf', '--chip', 'Ascend950PR_9579']))
        self.assertEqual(result['schema_version'], 'ackb.ccec-ops.query.v1')
        opid = 'ccec_op___builtin_cce_copy_gm_to_ubuf'
        self.assertEqual(sum(o['id']==opid for o in result['items']), 1)
        detail = run(parser().parse_args(['get', opid]))['items'][0]
        self.assertEqual(detail['entry_record_ids'], ['13c808703f3d6b63c4c4'])
        raw = run(parser().parse_args(['get', '41997fe279e39ece787b']))['items'][0]
        self.assertEqual(raw['name'], 'copy_gm_to_ubuf')
        self.assertEqual(raw['op_layer']['layer'], 'wrapper')
        self.assertEqual(raw['op_layer']['op_ids'], ['ccec_op___builtin_cce_copy_gm_to_ubuf_align_v2'])
        relations = run(parser().parse_args(['relations', '41997fe279e39ece787b']))['items']
        self.assertTrue(any(e.get('target_op')=='ccec_op___builtin_cce_copy_gm_to_ubuf_align_v2' for e in relations))
