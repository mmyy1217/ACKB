"""Check learning links, syntax provenance and architecture-specific boundaries."""
import hashlib
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from knowledge import Knowledge
from ptx_targets import assess, judge


def statement(sm, relation='minimum_sm', subject=None, **extra):
    return dict(sm=sm, relation=relation, subject=subject, **extra)


class LearningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.k = Knowledge('ptx')

    def test_links_resolve_and_examples_are_unverified(self):
        anchors = {r['anchor'] for r in self.k.records}
        lessons = self.k.learning['lessons']
        self.assertEqual(len({l['id'] for l in lessons}), 22)
        for lesson in lessons:
            self.assertTrue(set(lesson['anchors']) <= anchors, lesson['id'])
            self.assertTrue(set(lesson['terms']) <= self.k.learning['terms'].keys())
            self.assertTrue(all(v == 'unverified' for v in lesson['verification'].values()))
        for lesson in lessons[-3:]:
            code = next(s['code'] for s in lesson['sections'] if 'code' in s)
            self.assertIn('\n.target sm_103\n', code)
            self.assertNotIn('\\n', code)
        for term in self.k.learning['terms'].values():
            self.assertIn(term['anchor'], anchors)

    def test_syntax_coverage_and_fingerprints(self):
        self.assertEqual(self.k.syntax['source_sha256'], self.k.source['sha256'])
        instructions = [r for r in self.k.records if r['kind'] == 'instruction']
        self.assertEqual(len(instructions), 221)
        for record in instructions:
            syntax = record['syntax_detail']
            self.assertIsNotNone(syntax, record['anchor'])
            self.assertEqual(syntax['source_anchor'], record['anchor'])
            self.assertEqual(syntax['sha256'], hashlib.sha256(syntax['text'].encode()).hexdigest())
            self.assertIsNotNone(record['guide'], record['anchor'])
            self.assertEqual(record['guide']['anchor'], record['anchor'])
            self.assertIn('taxonomy', record, record['anchor'])
            self.assertGreaterEqual(record['taxonomy']['form_count'], 1)
        self.assertEqual(len(self.k.taxonomy['domains']), 7)
        self.assertEqual(len(self.k.taxonomy['categories']), 21)
        self.assertEqual(len(self.k.taxonomy['instructions']), 221)

    def test_architecture_and_family_are_distinct(self):
        self.assertEqual(judge(statement('sm_100a', 'exact_sm'), 'sm_103a'), 'no')
        self.assertEqual(judge(statement('sm_103a', 'exact_sm'), 'sm_103a'), 'yes')
        self.assertEqual(judge(statement('sm_100f'), 'sm_103a'), 'yes')
        self.assertEqual(judge(statement('sm_100f'), 'sm_103f'), 'yes')
        self.assertEqual(judge(statement('sm_100f'), 'sm_103'), 'no')
        self.assertEqual(judge(statement('sm_110f'), 'sm_103a'), 'no')
        self.assertEqual(judge(statement('sm_107f'), 'sm_103a'), 'no')
        self.assertEqual(judge(statement('sm_89'), 'sm_103'), 'yes')

    def test_alternatives_exclusions_and_unknowns(self):
        rules = [statement('sm_100a', 'exact_sm'), statement('sm_100f')]
        record = {'target_isa': {'statements': rules}}
        self.assertEqual(assess(record)['support'], 'documented_supported')
        rules.append(statement('sm_110a', 'exact_sm', 'new qualifier'))
        self.assertEqual(assess(record)['support'], 'partial')
        rules.append(statement('sm_70', 'excluded_minimum', scope='entry'))
        self.assertEqual(assess(record)['support'], 'documented_not_supported')
        record['target_isa']['unparsed'] = ['unrecognized']
        self.assertEqual(assess(record)['support'], 'unknown')
        self.assertEqual(assess({})['support'], 'unknown')

    def test_real_instruction_boundaries(self):
        wgmma = self.k.find('asynchronous-warpgroup-level-matrix-instructions-wgmma-mma')
        self.assertEqual(assess(wgmma)['support'], 'documented_not_supported')
        mma = self.k.find('tcgen05-mma-instructions-mma')
        self.assertEqual(assess(mma)['support'], 'partial')
        self.assertEqual(assess(mma, 'sm_103')['support'], 'documented_not_supported')
        result = self.k.item(mma, full=True)
        self.assertNotIn('sm_89', result)
        self.assertEqual(result['target_assessment']['target'], 'sm_103a')
